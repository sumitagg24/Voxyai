"""Usage blueprint: qa/enhance/transcribe/history/stats/subscription (moved from web/app.py)."""

import logging
import os
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request
from flask_limiter.util import get_remote_address

from web import observability
from web.auth_helpers import (
    _extract_session,
    _text,
    _verify_session,
    check_transcription_quota,
    get_monthly_transcription_count,
    get_user_tier,
    has_feature,
    is_admin,
    record_usage,
    require_auth,
    require_verified_email,
)
from web.auth_helpers import _notify_usage_threshold
from web.db import _get_db
from web.extensions import limiter
from web.services import email_service, llm_service, subscription_service
from web.tier import (
    FREE_MONTHLY_TRANSCRIPTIONS,
    TIER_ENHANCEMENT_MODES,
    TIER_FREE,
    TIER_OWNER,
    TIER_QUOTAS,
    TIER_STT_MODES,
)

logger = logging.getLogger(__name__)

usage_bp = Blueprint("usage", __name__)


_MODE_PROMPTS = {
    "formal": "Rewrite the following text in a formal, professional tone. Fix grammar, punctuation, and clarity. Preserve the original meaning. Output ONLY the enhanced text, nothing else.",
    "casual": "Rewrite the following text in a relaxed, friendly, conversational tone. Fix obvious errors. Preserve the original meaning. Output ONLY the enhanced text, nothing else.",
    "technical": "Rewrite the following text in a precise, technical tone suitable for documentation or engineering audiences. Fix grammar and clarity. Preserve the original meaning. Output ONLY the enhanced text, nothing else.",
    "concise": "Rewrite the following text as concisely as possible while preserving all key information. Remove filler words and redundancy. Output ONLY the enhanced text, nothing else.",
    "creative": "Rewrite the following text with creative flair — vivid language, varied sentence structure, engaging tone. Preserve the original meaning. Output ONLY the enhanced text, nothing else.",
}

#: Modes accepted by POST /api/history (enhancement modes + translate:<iso>).
_HISTORY_MODES = frozenset(_MODE_PROMPTS)

#: ISO 639-1 codes accepted by POST /api/history (plus common variants).
_HISTORY_LANGUAGES = frozenset(
    {
        "en",
        "hi",
        "hi-en",
        "es",
        "fr",
        "de",
        "it",
        "pt",
        "ru",
        "ar",
        "ur",
        "bn",
        "pa",
        "gu",
        "ta",
        "te",
        "ml",
        "mr",
        "ja",
        "zh",
        "ko",
        "tr",
        "nl",
        "pl",
        "vi",
        "th",
        "id",
        "ms",
        "sv",
        "no",
        "da",
        "fi",
        "cs",
        "hu",
        "ro",
        "uk",
        "el",
        "he",
        "auto",
    }
)

#: Free-tier history-write cap per hour (abuse guard; well above normal use and
#: above the 100/month STT quota so the P1.5 regression test can exceed 100).
_HISTORY_FREE_HOURLY_CAP = 500


@usage_bp.route("/api/qa", methods=["POST"])
@limiter.limit("30 per minute", key_func=get_remote_address)
def qa_endpoint():
    session_id = _extract_session()
    user_id = _verify_session(session_id)
    if user_id is None:
        return jsonify({"error": "Login required for Q&A"}), 401

    if not has_feature(user_id, "qa"):
        tier = get_user_tier(user_id)
        return (
            jsonify(
                {
                    "error": "Q&A requires a Pro or Business plan",
                    "current_tier": tier,
                    "upgrade_url": "/pricing",
                }
            ),
            403,
        )

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400
    question = _text(data.get("question"))
    if not question:
        return jsonify({"error": "Question required"}), 400

    answer = _call_llm_for_qa(question)
    record_usage(user_id, "qa", count=1)
    return jsonify(
        {
            "status": "success",
            "question": question,
            "answer": answer,
            "timestamp": datetime.now().isoformat(),
        }
    )


def _call_llm_for_qa(question: str) -> str:
    """Call LLM for Q&A using centralized service (OpenRouter -> Groq -> OpenAI)."""
    try:
        return llm_service.chat(question)
    except RuntimeError as e:
        logger.warning("All LLM providers failed for Q&A: %s", e)
        return "I'm sorry, the AI service is currently unavailable. Please try again later or configure a GROQ_API_KEY, OPENAI_API_KEY, or OPENROUTER_API_KEY in your settings."


@usage_bp.route("/api/enhance", methods=["POST"])
@limiter.limit("30 per minute", key_func=get_remote_address)
def enhance_endpoint():
    session_id = _extract_session()
    user_id = _verify_session(session_id)
    if user_id is None:
        return jsonify({"error": "Login required for enhancement"}), 401

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400
    text = _text(data.get("text"))
    mode = (_text(data.get("mode")) or "formal").lower()
    if not text:
        return jsonify({"error": "Text required"}), 400
    if mode not in _MODE_PROMPTS:
        return jsonify({"error": f"Invalid mode. Choose from: {', '.join(_MODE_PROMPTS)}"}), 400

    tier = get_user_tier(user_id)
    allowed_modes = TIER_ENHANCEMENT_MODES.get(tier, TIER_ENHANCEMENT_MODES[TIER_FREE])
    if mode not in allowed_modes:
        return (
            jsonify(
                {
                    "error": f"Mode '{mode}' requires a paid plan. Free tier: formal only.",
                    "current_tier": tier,
                    "allowed_modes": list(allowed_modes),
                    "upgrade_url": "/pricing",
                }
            ),
            403,
        )

    # Without a provider key there is nothing to enhance with. Returning the
    # original text as "success" would look like the feature worked.
    if not _any_llm_key_configured():
        return jsonify({"error": "Enhancement is unavailable: no AI provider key is configured on this server."}), 503

    enhanced = _call_llm_for_enhancement(text, mode)
    record_usage(user_id, "enhancement", count=1)
    return jsonify(
        {
            "status": "success",
            "original": text,
            "enhanced": enhanced,
            "mode": mode,
        }
    )


def _any_llm_key_configured() -> bool:
    """True when at least one provider credential exists for enhancement/Q&A."""
    return llm_service.is_configured()


def _call_llm_for_enhancement(text: str, mode: str) -> str:
    """Call LLM for text enhancement using centralized service."""
    system_prompt = _MODE_PROMPTS.get(mode, _MODE_PROMPTS["formal"])
    try:
        return llm_service.chat(text, system_prompt=system_prompt, max_tokens=2048, temperature=0.7)
    except RuntimeError as e:
        logger.warning("All LLM providers failed for enhancement: %s", e)
        return text


@usage_bp.route("/api/transcribe", methods=["POST"])
@require_verified_email
@limiter.limit("20 per minute", key_func=get_remote_address)
def transcribe_endpoint(user_id):
    """Transcribe uploaded audio: Groq Whisper -> OpenAI Whisper (fallback chain).

    Requires a confirmed email address: this endpoint spends provider credit and
    writes a server-side record, so an unverified throwaway address must not be
    able to consume the monthly allowance.
    """
    allowed, used, limit = check_transcription_quota(user_id)
    if not allowed:
        return (
            jsonify(
                {
                    "error": f"Monthly transcription limit reached ({limit})",
                    "used": used,
                    "limit": limit,
                    "upgrade_url": "/pricing",
                }
            ),
            403,
        )

    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["audio"]
    if not audio_file.filename:
        return jsonify({"error": "Empty audio file"}), 400

    mode = request.form.get("mode", "PUSH_TO_TALK").upper()
    if mode not in ("PUSH_TO_TALK", "ENDPOINTING", "DIARIZATION"):
        mode = "PUSH_TO_TALK"

    tier = get_user_tier(user_id)
    allowed_modes = TIER_STT_MODES.get(tier, TIER_STT_MODES[TIER_FREE])
    if mode not in allowed_modes:
        return (
            jsonify(
                {
                    "error": f"STT mode '{mode}' requires a paid plan",
                    "current_tier": tier,
                    "allowed_modes": list(allowed_modes),
                    "upgrade_url": "/pricing",
                }
            ),
            403,
        )

    audio_bytes = audio_file.read()
    if len(audio_bytes) > 32 * 1024 * 1024:
        return jsonify({"error": "Audio file exceeds 32 MB limit"}), 413

    if not llm_service.is_transcribe_configured():
        return jsonify({"error": "Transcription unavailable. Configure GROQ_API_KEY or OPENAI_API_KEY."}), 503

    try:
        result = llm_service.transcribe(audio_bytes, audio_file.filename, mode)
        transcript = result["transcript"]
        provider = result["provider"]

        if transcript.strip():
            try:
                conn = _get_db()
                conn.execute(
                    "INSERT INTO transcriptions (user_id, text, enhanced, mode, language) VALUES (?, ?, ?, ?, ?)",
                    (user_id, transcript.strip(), 0, mode, request.form.get("language", "en")),
                )
                conn.commit()
                conn.close()
                record_usage(user_id, "transcription", count=1)
                _notify_usage_threshold(user_id)
            except Exception as save_err:
                logger.warning("Failed to record transcription: %s", save_err)

            return jsonify(
                {
                    "status": "success",
                    "transcript": transcript.strip(),
                    "provider": provider,
                    "mode": mode,
                }
            )
    except RuntimeError as e:
        logger.warning("All transcription providers failed: %s", e)
        observability.capture_pipeline_failure("transcribe", e, provider="all")

    return jsonify({"error": "Transcription unavailable. Configure GROQ_API_KEY or OPENAI_API_KEY."}), 503


@usage_bp.route("/api/history", methods=["GET", "POST"])
@limiter.limit("30 per minute", key_func=get_remote_address)
def history():
    # Attempt to get session from header or body
    session_id = request.headers.get("X-Session-Id", "")
    if not session_id:
        data = request.get_json(silent=True) or {}
        session_id = data.get("session_id", "")

    user_id = _verify_session(session_id)

    if request.method == "POST":
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"status": "error", "message": "Invalid JSON body"}), 400

        if user_id is None:
            return jsonify({"success": False, "error": "Unauthorized"}), 401

        text = _text(data.get("text"))
        if not text:
            return jsonify({"success": False, "error": "Text is required"}), 400

        mode = (_text(data.get("mode")) or "formal").lower()
        if mode not in _HISTORY_MODES and not (
            mode.startswith("translate:") and mode.split(":", 1)[1] in _HISTORY_LANGUAGES
        ):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"Invalid mode. Choose from: {', '.join(sorted(_HISTORY_MODES))} "
                        "or translate:<language>",
                    }
                ),
                400,
            )
        language = (_text(data.get("language")) or "en").lower()
        if language not in _HISTORY_LANGUAGES:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"Invalid language. Choose an ISO code such as: {', '.join(sorted(_HISTORY_LANGUAGES))}",
                    }
                ),
                400,
            )

        # Free-tier abuse guard (history writes are cheap but not free to store).
        # Paid/owner tiers skip the hourly cap; the generic 30/min limiter still
        # applies to everyone.
        try:
            tier = get_user_tier(user_id)
        except Exception:
            tier = TIER_FREE
        if tier == TIER_FREE:
            conn = _get_db()
            try:
                recent = conn.execute(
                    "SELECT COUNT(*) AS c FROM usage_records WHERE user_id = ? AND feature = 'history_write' "
                    "AND created_at >= datetime('now', '-1 hour')",
                    (user_id,),
                ).fetchone()["c"]
            except Exception:
                recent = 0
            finally:
                conn.close()
            if recent >= _HISTORY_FREE_HOURLY_CAP:
                return jsonify({"success": False, "error": "History write limit reached, try again later."}), 429

        conn = _get_db()
        conn.execute(
            "INSERT INTO transcriptions (user_id, text, enhanced, mode, language) VALUES (?, ?, ?, ?, ?)",
            (
                user_id,
                text,
                1 if data.get("enhanced") else 0,
                mode,
                language,
            ),
        )
        conn.commit()
        conn.close()
        # History rows never consume STT quota (P1.5): quota counts
        # usage_records feature='transcription' only.
        record_usage(user_id, "history_write")
        return jsonify({"success": True, "message": "Transcription saved"})

    # GET
    #
    # Previously this returned three hard-coded sample transcriptions to
    # logged-out callers, which presented fabricated data as the visitor's own
    # history. An unauthenticated read is simply unauthorised.
    if user_id is None:
        return jsonify({"success": False, "error": "Login required"}), 401

    conn = _get_db()
    rows = conn.execute(
        "SELECT id, text, enhanced, mode, language, created_at "
        "FROM transcriptions WHERE user_id = ? ORDER BY created_at DESC LIMIT 100",
        (user_id,),
    ).fetchall()
    conn.close()

    history = [
        {
            "id": r["id"],
            "text": r["text"],
            "enhanced": bool(r["enhanced"]),
            "mode": r["mode"],
            "language": r["language"],
            "timestamp": r["created_at"],
        }
        for r in rows
    ]
    return jsonify({"status": "success", "history": history})


@usage_bp.route("/api/history/<int:item_id>", methods=["DELETE"])
@limiter.limit("30 per minute", key_func=get_remote_address)
def history_delete(item_id):
    """Delete one history entry. Auth required; users can only delete their own."""
    session_id = _extract_session()
    user_id = _verify_session(session_id)
    if user_id is None:
        return jsonify({"success": False, "error": "Login required"}), 401

    conn = _get_db()
    cur = conn.execute(
        "DELETE FROM transcriptions WHERE id = ? AND user_id = ?",
        (item_id, user_id),
    )
    conn.commit()
    deleted = cur.rowcount
    conn.close()

    if not deleted:
        return jsonify({"success": False, "error": "Entry not found"}), 404
    return jsonify({"success": True, "message": "Entry deleted"})


@usage_bp.route("/api/stats", methods=["GET"])
def stats():
    """Real usage stats. Scoped to the logged-in user when a session is
    present, otherwise global. All numbers come from the transcriptions table."""
    user_id = _verify_session(_extract_session())
    scope = "WHERE user_id = ?" if user_id is not None else ""
    params: tuple = (user_id,) if user_id is not None else ()

    conn = _get_db()
    try:
        total = conn.execute(f"SELECT COUNT(*) as c FROM transcriptions {scope}", params).fetchone()["c"]
        langs = conn.execute(f"SELECT COUNT(DISTINCT language) as c FROM transcriptions {scope}", params).fetchone()[
            "c"
        ]
        enhanced = conn.execute(
            f"SELECT COUNT(*) as c FROM transcriptions {scope}" f"{' AND' if scope else 'WHERE'} enhanced = 1",
            params,
        ).fetchone()["c"]

        # Text-derived metrics (word counts, languages, weekly series) are only
        # computed for the authenticated user: an anonymous visitor must not
        # have other people's transcripts summarised for them.
        month_filter = "created_at >= date('now', 'start of month')"
        if user_id is not None:
            month_rows = conn.execute(
                f"SELECT text, language FROM transcriptions {scope} AND {month_filter}",
                params,
            ).fetchall()
            all_texts = conn.execute(f"SELECT text FROM transcriptions {scope}", params).fetchall()
        else:
            month_rows = []
            all_texts = []

        weekly_counts = []
        weekly_labels = []
        for i in range(6, -1, -1):
            day = (datetime.now() - timedelta(days=i)).date().isoformat()
            c = conn.execute(
                f"SELECT COUNT(*) as n FROM transcriptions {scope}"
                f"{' AND' if scope else 'WHERE'} date(created_at) = ?",
                (*params, day),
            ).fetchone()["n"]
            weekly_counts.append(c)
            weekly_labels.append((datetime.now() - timedelta(days=i)).strftime("%a"))
    finally:
        conn.close()

    words = sum(len((r["text"] or "").split()) for r in all_texts)
    month_words = sum(len((r["text"] or "").split()) for r in month_rows)
    month_langs = len({r["language"] for r in month_rows if r["language"]})
    minutes = max(1, round(words / 150)) if words else 0
    total_time = f"{minutes // 60}h {minutes % 60}m" if minutes >= 60 else f"{minutes}m"

    return jsonify(
        {
            "status": "success",
            "stats": {
                "transcriptions": total,
                "totalTime": total_time,
                "languages": langs,
                "enhancements": enhanced,
                "words": words,
                "thisMonth": {
                    "transcriptions": len(month_rows),
                    "words": month_words,
                    "languages": month_langs,
                },
                "weekly": {"labels": weekly_labels, "counts": weekly_counts},
            },
        }
    )


@usage_bp.route("/api/stats/public", methods=["GET"])
def public_stats():
    conn = _get_db()
    users_count = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    transcriptions_count = conn.execute("SELECT COUNT(*) as c FROM transcriptions").fetchone()["c"]
    conn.close()

    return jsonify(
        {
            "status": "success",
            "stats": {
                "total_users": users_count,
                "total_transcriptions": transcriptions_count,
            },
        }
    )


@usage_bp.route("/api/subscription", methods=["GET"])
def subscription():
    """Subscription summary. Logged-out visitors get Free-tier defaults."""
    user_id = _verify_session(_extract_session())
    if user_id is None:
        # Logged-out visitors see the free plan only, and are told plainly that
        # there is nothing to buy (no payment provider is wired up).
        return jsonify(
            {
                "status": "success",
                "authenticated": False,
                "subscription": {
                    "plan": "Free",
                    "tier": TIER_FREE,
                    "price": 0,
                    "renewalDate": None,
                    "status": "active",
                    "usage": {
                        "transcriptions": 0,
                        "limit": "100/month",
                        "percentage": 0,
                    },
                    "can_self_upgrade": subscription_service.self_service_upgrade_available(),
                    "checkout_available": subscription_service.payments_configured(),
                    "checkout_urls": subscription_service.public_checkout_urls(),
                },
            }
        )

    # The plan is computed and owned by the server; the client only reads it.
    summary = subscription_service.tier_summary(user_id, get_user_tier, get_monthly_transcription_count)
    return jsonify({"status": "success", "subscription": summary})


@usage_bp.route("/api/subscription/upgrade", methods=["POST"])
@require_auth
@limiter.limit("10 per hour", key_func=get_remote_address)
def upgrade_tier(user_id):
    """Manual tier change.

    A client can never grant itself a paid plan. This endpoint only succeeds
    for an administrator, or for an explicitly enabled non-production
    development override; the real production path is a verified payment
    webhook handled by :mod:`web.services.subscription_service`.
    """
    data = request.get_json(silent=True) or {}
    new_tier = _text(data.get("tier")).lower()
    actor_is_admin = is_admin(user_id=user_id)
    source = subscription_service.resolve_actor_source(actor_is_admin)

    if source is None:
        return (
            jsonify(
                {
                    "success": False,
                    "code": "self_service_tier_change_disabled",
                    "error": (
                        "Plans cannot be changed from the app. Paid plans must be purchased through the "
                        "payment provider."
                    ),
                    "payments_configured": subscription_service.payments_configured(),
                }
            ),
            403,
        )

    conn = _get_db()
    try:
        result = subscription_service.apply_tier_change(
            conn,
            user_id=user_id,
            new_tier=new_tier,
            source=source,
            actor=os.environ.get("ADMIN_EMAILS", "") if actor_is_admin else "dev-override",
            actor_is_admin=actor_is_admin,
            note="admin console" if actor_is_admin else "development override (ALLOW_DEV_TIER_CHANGE)",
        )
        conn.commit()
    except subscription_service.TierChangeDenied as denied:
        conn.rollback()
        return jsonify(denied.as_dict()), denied.status
    finally:
        conn.close()

    logger.warning("tier change applied to user %s -> %s via %s", user_id, result.tier, result.source)
    # The plan owner is told, even when an admin made the change.
    try:
        notify_conn = _get_db()
        account = notify_conn.execute("SELECT name, email_or_phone FROM users WHERE id = ?", (user_id,)).fetchone()
        notify_conn.close()
        if account is not None and "@" in (account["email_or_phone"] or ""):
            email_service.send_transactional(
                "subscription_changed",
                account["email_or_phone"],
                {
                    "name": account["name"],
                    "plan": result.tier.capitalize(),
                    "limit": (
                        "Unlimited"
                        if result.tier == TIER_OWNER
                        else f"{TIER_QUOTAS.get(result.tier, FREE_MONTHLY_TRANSCRIPTIONS)}/month"
                    ),
                    "dashboard_url": f"{email_service.site_base_url()}/dashboard",
                    "note": f"Changed by {result.source}.",
                },
            )
    except Exception as exc:
        logger.warning("Plan-change email skipped: %s", type(exc).__name__)
    return jsonify({"success": True, **result.as_dict()})
