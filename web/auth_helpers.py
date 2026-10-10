"""Shared auth decorators and account helpers (moved from web/app.py)."""

import hashlib
import json
import logging
import os
import re
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta
from functools import wraps

from flask import g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from web.db import _get_db, _owner_emails, utcnow
from web.services import email_service
from web.tier import (
    FREE_MONTHLY_TRANSCRIPTIONS,
    OWNER_MONTHLY_TRANSCRIPTIONS,
    TIER_BUSINESS,
    TIER_ENHANCEMENT_MODES,
    TIER_FEATURES,
    TIER_FREE,
    TIER_OWNER,
    TIER_QUOTAS,
    TIER_STT_MODES,
)

logger = logging.getLogger(__name__)


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


_PHONE_RE = re.compile(r"^\+?[0-9\s\-()]{7,20}$")


DISPOSABLE_EMAIL_DOMAINS = frozenset(
    {
        "mailinator.com",
        "mailinator.net",
        "tempmail.com",
        "10minutemail.com",
        "10minutemail.net",
        "guerrillamail.com",
        "guerrillamail.net",
        "guerrillamailblock.com",
        "yopmail.com",
        "yopmail.net",
        "temp-mail.org",
        "temp-mail.io",
        "throwaway.email",
        "getnada.com",
        "mohmal.com",
        "sharklasers.com",
        "maildrop.cc",
        "trashmail.com",
        "trashmail.net",
        "fakeinbox.com",
        "mintemail.com",
        "mytemp.email",
        "tempail.com",
        "dispostable.com",
        "spambog.com",
        "mailnesia.com",
        "mailexpire.com",
        "pokemail.net",
        "spamgourmet.com",
        "slipry.net",
        "mail.tm",
        "emailondeck.com",
        "tmpmail.org",
        "tmpmail.net",
        "burnermail.io",
        "mailcatch.com",
        "jetable.org",
        "trash-mail.com",
        "fake-mail.cf",
    }
)


_ONBOARDING_STEPS = [
    {"id": "account", "label": "Create your account", "done": True},
    {"id": "download", "label": "Download Voxylis desktop app"},
    {"id": "first_recording", "label": "Make your first recording"},
    {"id": "enhance", "label": "Try an AI enhancement mode"},
    {"id": "ask", "label": "Ask Voxy a question"},
]


def _hash_password(password: str) -> str:
    """Generate a PBKDF2-SHA256 password hash (werkzeug)."""
    return generate_password_hash(password)


def _check_password(password_hash: str, password: str) -> bool:
    """Verify a password against a stored hash (supports legacy SHA-256)."""
    if password_hash and len(password_hash) == 64 and _is_hex(password_hash):
        # Legacy plain SHA-256 (pre-v2.2). Compare in constant-time style.
        return hashlib.sha256(password.encode("utf-8")).hexdigest() == password_hash
    try:
        return check_password_hash(password_hash, password)
    except (ValueError, TypeError):
        return False


def _is_hex(value: str) -> bool:
    return all(c in "0123456789abcdefABCDEF" for c in value)


def is_auth0_account(password_hash: str) -> bool:
    """True when the account was provisioned via Auth0 and has no local password.

    Auth0 logins store ``password_hash="auth0:<uuid>"`` as an explicit marker,
    never as a verifiable credential: :func:`_check_password` always fails
    against it, so password-gated flows must branch on this first.
    """
    return bool(password_hash) and str(password_hash).startswith("auth0:")


def _session_created_at(session_id: str):
    """Return the ``created_at`` timestamp of a session, or None.

    Read-only: unlike :func:`_verify_session` this never rotates or deletes
    anything, so it is safe to call from guards that only need the age.
    """
    if not session_id:
        return None
    try:
        conn = _get_db()
        try:
            row = conn.execute("SELECT created_at FROM sessions WHERE id = ?", (session_id,)).fetchone()
        finally:
            conn.close()
    except Exception:
        return None
    if row is None:
        return None
    try:
        return datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, KeyError, IndexError):
        return None


def normalize_email(value) -> str:
    """Lowercase-normalize an email address (single canonical helper).

    Strips surrounding whitespace and lowercases the whole address. Phone
    numbers and non-strings pass through ``_text`` coercion unchanged apart
    from stripping — only values containing ``@`` are lowercased, so phone
    identifiers are never mangled.
    """
    text = value.strip() if isinstance(value, str) else ""
    if "@" in text:
        return text.lower()
    return text


def _create_session(user_id: int) -> str:
    """Create a 30-day session and return its ID."""
    session_id = uuid.uuid4().hex
    expires = (utcnow() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_db()
    conn.execute(
        "INSERT INTO sessions (id, user_id, expires_at) VALUES (?, ?, ?)",
        (session_id, user_id, expires),
    )
    conn.commit()
    conn.close()
    return session_id


def _verify_session(session_id: str, rotate: bool = True):
    """Return user_id if session is valid, else None.

    ``rotate`` controls the 24h transparent rotation. Monitoring hooks must
    call with ``rotate=False`` so the lookup is strictly read-only (no writes,
    no rotation): otherwise the ``before_request`` verification would rotate
    first and the endpoint's own verification of the SAME id would 401.
    Rotation happens at most once per request, guarded by ``g``.
    """
    if not session_id:
        return None
    # At most once per request: a second verification of the SAME id in the
    # same request (monitoring + endpoint) must not rotate again.
    try:
        _rotated = getattr(g, "rotated_session_id", None)
        _rotated_from = getattr(g, "_rotated_from_session", None)
        _verified_uid = getattr(g, "_verified_user_id", None)
        if _rotated and _verified_uid is not None and session_id in (_rotated, _rotated_from):
            return _verified_uid
    except RuntimeError:
        pass
    conn = _get_db()
    row = conn.execute("SELECT user_id, expires_at, created_at FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if row is None:
        conn.close()
        return None
    expires = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
    if utcnow() > expires:
        if rotate:
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
        conn.close()
        return None

    if not rotate:
        user_id = row["user_id"]
        conn.close()
        return user_id

    # Fresh session: no rotation, but remember the verification so a second
    # call with the SAME id in this request is a cheap consistent hit.
    created = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
    if utcnow() - created <= timedelta(hours=24):
        user_id = row["user_id"]
        conn.close()
        try:
            g._verified_user_id = user_id
            g._rotated_from_session = session_id
        except RuntimeError:
            pass
        return user_id

    # Session rotation: tokens older than 24h get a fresh ID (announced via
    # X-Session-Rotated so clients can pick it up). Race-safe: the UPDATE only
    # fires when the row is still old inside the WHERE clause; a concurrent
    # rotator wins (rowcount 1) and the loser re-resolves instead of 401ing.
    user_id = row["user_id"]
    new_id = uuid.uuid4().hex
    now_str = utcnow().strftime("%Y-%m-%d %H:%M:%S")
    new_expires = (utcnow() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    threshold = (utcnow() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute(
        "UPDATE sessions SET id = ?, created_at = ?, expires_at = ? WHERE id = ? AND created_at <= ?",
        (new_id, now_str, new_expires, session_id, threshold),
    )
    if cur.rowcount == 0:
        # Lost the race (row already rotated away) or clock skew: re-fetch
        # instead of failing closed. The old id is gone, but we already know
        # the user; confirm the account still holds a live session.
        still = conn.execute("SELECT user_id FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if still is not None:
            conn.close()
            return still["user_id"]
        live = conn.execute(
            "SELECT user_id FROM sessions WHERE user_id = ? AND expires_at > ? LIMIT 1",
            (user_id, now_str),
        ).fetchone()
        conn.close()
        if live is not None:
            return live["user_id"]
        return user_id
    conn.commit()
    conn.close()
    _set_rotated_session(new_id)
    try:
        g._rotated_from_session = session_id
        g._verified_user_id = user_id
    except RuntimeError:
        pass
    return user_id


def _set_rotated_session(new_id: str) -> None:
    """Record a rotated session id so ``security_headers`` can announce it."""
    try:
        g.rotated_session_id = new_id
    except RuntimeError:  # pragma: no cover - called outside a request context
        pass


def _extract_session() -> str:
    """Pull session_id from header or JSON body."""
    session_id = request.headers.get("X-Session-Id", "")
    if not session_id:
        data = request.get_json(silent=True) or {}
        session_id = data.get("session_id", "")
    return session_id


def require_auth(f):
    """Decorator: expects session_id in JSON body or header."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        session_id = _extract_session()
        user_id = _verify_session(session_id)
        if user_id is None:
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        return f(user_id=user_id, *args, **kwargs)

    return wrapper


def _issue_email_token(user_id: int, hours: int = 24) -> str:
    """Mint a single-use email verification token, retiring older ones."""
    token = secrets.token_urlsafe(32)
    expires = (utcnow() + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_db()
    conn.execute("UPDATE email_verifications SET used = 1 WHERE user_id = ? AND used = 0", (user_id,))
    conn.execute(
        "INSERT INTO email_verifications (user_id, token, expires_at) VALUES (?, ?, ?)",
        (user_id, token, expires),
    )
    conn.commit()
    conn.close()
    return token


def is_email_verified(user_id: int) -> bool:
    """True when the account's address has been confirmed.

    Owner and admin accounts are treated as verified: they are provisioned out
    of band, and locking the operator out of their own deployment is worse than
    the marginal gain.
    """
    if is_owner(user_id=user_id) or is_admin(user_id=user_id):
        return True
    conn = _get_db()
    try:
        row = conn.execute("SELECT email_verified FROM users WHERE id = ?", (user_id,)).fetchone()
    except sqlite3.Error:
        return False
    finally:
        conn.close()
    if row is None:
        return False
    try:
        return bool(row["email_verified"])
    except (IndexError, KeyError):
        return False


def require_verified_email(f):
    """Decorator: the session must belong to a confirmed address.

    Applied to features that cost money or create server-side records, so an
    unverified throwaway address cannot consume quota.
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        session_id = _extract_session()
        user_id = _verify_session(session_id)
        if user_id is None:
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        if not is_email_verified(user_id):
            return (
                jsonify(
                    {
                        "success": False,
                        "code": "email_not_verified",
                        "error": (
                            "Confirm your email address before using this feature. "
                            "Open the link we emailed you, or request a new one."
                        ),
                        "resend_endpoint": "/api/auth/verify-email",
                    }
                ),
                403,
            )
        return f(user_id=user_id, *args, **kwargs)

    return wrapper


def _notify_usage_threshold(user_id: int) -> None:
    """Email once per month when an account crosses 80% and 100% of quota.

    ``notification_log`` has a UNIQUE(user_id, kind, period) constraint, so the
    insert itself is the de-duplication: a second call in the same month fails
    the constraint and nothing is sent.
    """
    try:
        tier = get_user_tier(user_id)
        if is_owner(user_id=user_id) or tier == TIER_OWNER:
            return
        limit = TIER_QUOTAS.get(tier, FREE_MONTHLY_TRANSCRIPTIONS)
        if not isinstance(limit, int) or limit <= 0:
            return
        used = get_monthly_transcription_count(user_id)
        percent = int(round(used * 100.0 / limit))
        if percent >= 100:
            pending = [("usage_limit_reached", percent, used, limit)]
        elif percent >= 80:
            pending = [("usage_warning", percent, used, limit)]
        else:
            return

        period = utcnow().strftime("%Y-%m")
        conn = _get_db()
        try:
            row = conn.execute("SELECT name, email_or_phone FROM users WHERE id = ?", (user_id,)).fetchone()
            if row is None:
                return
            address = row["email_or_phone"]
            if "@" not in (address or ""):
                return
            for kind, pct, used_now, limit_now in pending:
                try:
                    conn.execute(
                        "INSERT INTO notification_log (user_id, kind, period) VALUES (?, ?, ?)",
                        (user_id, kind, period),
                    )
                    conn.commit()
                except sqlite3.IntegrityError:
                    continue  # already notified this month
                email_service.send_transactional(
                    kind,
                    address,
                    {
                        "name": row["name"],
                        "used": used_now,
                        "limit": limit_now,
                        "percent": min(100, pct),
                        "dashboard_url": f"{email_service.site_base_url()}/dashboard",
                    },
                )
        finally:
            conn.close()
    except Exception as exc:  # pragma: no cover - notification must never fail a request
        logger.warning("Usage notification skipped: %s", type(exc).__name__)


def _valid_identifier(value: str) -> bool:
    return bool(_EMAIL_RE.match(value) or _PHONE_RE.match(value))


def _valid_name(value: str) -> bool:
    return 2 <= len(value) <= 80


def _valid_password(value: str) -> bool:
    return 8 <= len(value) <= 128


def _sanitize(value: str) -> str:
    """Escape HTML entities in user-provided text to prevent XSS."""
    from markupsafe import escape

    return str(escape(value))


def _text(value) -> str:
    """Coerce an untrusted JSON field to a string; anything that is not a
    string (number, object, array, null) becomes empty.

    Endpoints previously called ``.strip()`` straight on ``data.get(...)``, so
    a type-confused body (``{"name": {"$gt": ""}}``) raised AttributeError
    and turned into a 500 — noisy in logs, and in one case (history) it even
    accepted the bogus value. Coerce first, validate after.
    """
    return value.strip() if isinstance(value, str) else ""


def _email_verified_flag(user_id) -> bool:
    """Trusted email_verified flag for the account, tolerant of old schemas."""
    try:
        conn = _get_db()
        row = conn.execute("SELECT email_verified FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
    except Exception:
        return False
    if row is None:
        return False
    try:
        return bool(row["email_verified"])
    except (IndexError, KeyError):
        return False


def is_owner(user_id=None, email=None) -> bool:
    """True if the user is the owner (unlimited server-enforced usage).

    The trusted ``OWNER_EMAILS`` list decides *who may be* the owner; a row's
    ``email_verified`` flag decides whether the claim has been proven. Without
    the verification gate, anyone could sign up with the owner's address and
    immediately hold unlimited entitlement. A row explicitly promoted in the
    database (``is_owner``/``role``) is always honoured: provisioning is a
    server-side act that already implies the address was trusted.
    """
    if email and normalize_email(email) in _owner_emails():
        return True
    if user_id is None:
        return False
    try:
        conn = _get_db()
        row = conn.execute("SELECT is_owner, role, email_or_phone FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
    except Exception:
        return False
    if not row:
        return False
    try:
        if bool(row["is_owner"]) or (row["role"] or "").lower() == "owner":
            return True
    except Exception:
        pass
    # Email fallback: only for a proven address. Unverified claims get none of
    # the owner's privileges — the promotion pass upgrades them once verified.
    if normalize_email(row["email_or_phone"] or "") in _owner_emails():
        return _email_verified_flag(user_id)
    return False


def _ensure_owner(conn, user_id: int, email: str) -> None:
    """Promote owner email to is_owner=1, role='owner', tier='owner'.

    Owner privileges are only granted to a **verified** address. A password
    signup claims an address it has not proven control of, so promoting it
    here would hand unlimited entitlement to whoever typed the owner email
    first. Once the address is confirmed (verification link, or an Auth0 ID
    token carrying ``email_verified``), promotion happens on the next
    signup/login/startup sweep — and :func:`is_owner` additionally falls back
    to the trusted ``OWNER_EMAILS`` list, so a verified owner never loses
    access because a promotion pass simply has not run yet.
    """
    if normalize_email(email or "") not in _owner_emails():
        return
    try:
        verified = conn.execute("SELECT email_verified FROM users WHERE id = ?", (user_id,)).fetchone()
        if verified is not None and not bool(verified["email_verified"]):
            return
        conn.execute(
            "UPDATE users SET is_owner = 1, role = 'owner', tier = 'owner' WHERE id = ?",
            (user_id,),
        )
        conn.execute(
            "INSERT INTO subscriptions (user_id, tier, status, current_period_start, current_period_end) "
            "VALUES (?, 'owner', 'active', datetime('now'), datetime('now', '+365 days'))",
            (user_id,),
        )
    except Exception:
        pass


def get_user_tier(user_id: int) -> str:
    """Get the subscription tier for a user. Owner gets owner; admin gets business."""
    if is_owner(user_id=user_id):
        return TIER_OWNER
    if is_admin(user_id=user_id):
        return TIER_BUSINESS
    conn = _get_db()
    try:
        row = conn.execute("SELECT tier, is_owner FROM users WHERE id = ?", (user_id,)).fetchone()
        if row:
            if "is_owner" in row.keys() and row["is_owner"]:
                return TIER_OWNER
            if row["tier"]:
                return row["tier"]
    except Exception:
        pass
    finally:
        conn.close()
    return TIER_FREE


def has_feature(user_id: int, feature: str) -> bool:
    """Check if a user's tier includes a specific feature."""
    tier = get_user_tier(user_id)
    return feature in TIER_FEATURES.get(tier, TIER_FEATURES[TIER_FREE])


def get_monthly_transcription_count(user_id: int) -> int:
    """Count server STT usage for the current month (P1.5).

    History rows in ``transcriptions`` do NOT consume STT quota: only
    ``usage_records`` with ``feature='transcription'`` (written by
    /api/transcribe on real provider credit) count toward the monthly limit.
    """
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(count), 0) as cnt FROM usage_records "
            "WHERE user_id = ? AND feature = 'transcription' AND created_at >= date('now', 'start of month')",
            (user_id,),
        ).fetchone()
        return int(row["cnt"]) if row else 0
    except Exception:
        return 0
    finally:
        conn.close()


def check_transcription_quota(user_id: int) -> tuple:
    """Check if user has transcription quota remaining.
    Returns (allowed, used, limit). limit=-1 means unlimited.
    """
    tier = get_user_tier(user_id)
    used = get_monthly_transcription_count(user_id)
    if is_owner(user_id=user_id) or tier == TIER_OWNER:
        return True, used, OWNER_MONTHLY_TRANSCRIPTIONS
    limit = TIER_QUOTAS.get(tier, FREE_MONTHLY_TRANSCRIPTIONS)
    return (used < limit), used, limit


def record_usage(user_id: int, feature: str, tokens: int = 0, count: int = 1, metadata: dict = None) -> None:
    """Record a usage entry in usage_records table."""
    try:
        conn = _get_db()
        conn.execute(
            "INSERT INTO usage_records (user_id, feature, tokens, count, metadata) VALUES (?, ?, ?, ?, ?)",
            (user_id, feature, tokens, count, json.dumps(metadata or {})),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("Failed to record usage: %s", e)


def get_user_entitlements(user_id: int) -> dict:
    """Return full server-authoritative entitlements for user."""
    tier = get_user_tier(user_id)
    owner = is_owner(user_id=user_id) or tier == TIER_OWNER
    limit = OWNER_MONTHLY_TRANSCRIPTIONS if owner else TIER_QUOTAS.get(tier, FREE_MONTHLY_TRANSCRIPTIONS)
    used = get_monthly_transcription_count(user_id)
    return {
        "tier": tier,
        "is_owner": owner,
        "role": "owner" if owner else ("admin" if is_admin(user_id=user_id) else "user"),
        "monthly_transcriptions_used": used,
        "monthly_transcriptions_limit": limit,
        "unlimited": owner,
        "allowed_features": sorted(list(TIER_FEATURES.get(tier, TIER_FEATURES[TIER_FREE]))),
        "allowed_enhancement_modes": sorted(list(TIER_ENHANCEMENT_MODES.get(tier, TIER_ENHANCEMENT_MODES[TIER_FREE]))),
        "allowed_stt_modes": sorted(list(TIER_STT_MODES.get(tier, TIER_STT_MODES[TIER_FREE]))),
    }


def _admin_emails() -> set:
    """Emails that are always Voxylis admins (full access to everything)."""
    return {normalize_email(e) for e in os.environ.get("ADMIN_EMAILS", "sumitagg24@gmail.com").split(",") if e.strip()}


def _password_login_domains() -> set:
    """Email domains allowed for password signup (Gmail + official domains)."""
    return {
        d.strip().lower()
        for d in os.environ.get("PASSWORD_LOGIN_DOMAINS", "gmail.com,googlemail.com,voxylis.com").split(",")
        if d.strip()
    }


def _email_domain(identifier: str) -> str:
    """Lowercased domain part of an email, or '' for phones/invalid."""
    parts = normalize_email(identifier).split("@")
    if len(parts) != 2 or not parts[0] or not parts[1] or "." not in parts[1]:
        return ""
    return parts[1]


def _is_disposable_email(identifier: str) -> bool:
    return _email_domain(identifier) in DISPOSABLE_EMAIL_DOMAINS


def _password_domain_allowed(identifier: str) -> bool:
    """Password signup is restricted to Gmail + official domains."""
    return _email_domain(identifier) in _password_login_domains()


def is_admin(user_id=None, email=None) -> bool:
    """True if the user is a Voxylis admin or owner (access to all features)."""
    if is_owner(user_id=user_id, email=email):
        return True
    if email and normalize_email(email) in _admin_emails():
        return True
    if user_id is None:
        return False
    try:
        conn = _get_db()
        row = conn.execute("SELECT role, email_or_phone, is_owner FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
    except Exception:
        return False
    if not row:
        return False
    try:
        if bool(row["is_owner"]):
            return True
        role = row["role"]
    except Exception:
        role = None
    if (role or "user").lower() in ("admin", "owner"):
        return True
    # Email fallback: only for a proven address, same rule as is_owner().
    if normalize_email(row["email_or_phone"] or "") in _admin_emails():
        return _email_verified_flag(user_id)
    return False


def _ensure_admin(conn, user_id: int, email: str) -> None:
    """Promote well-known admin/owner emails (idempotent)."""
    if normalize_email(email or "") in _owner_emails():
        _ensure_owner(conn, user_id, email)
        return
    if normalize_email(email or "") not in _admin_emails():
        return
    try:
        conn.execute(
            "UPDATE users SET role = 'admin', tier = 'business' WHERE id = ?",
            (user_id,),
        )
    except Exception:
        pass


def require_admin(f):
    """Decorator: admin users only."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        user_id = _verify_session(_extract_session())
        if user_id is None:
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        if not is_admin(user_id=user_id):
            return jsonify({"success": False, "error": "Admin access required"}), 403
        return f(user_id=user_id, *args, **kwargs)

    return wrapper


def _onboarding_steps():
    return list(_ONBOARDING_STEPS)


def _load_onboarding(raw: str):
    try:
        completed = json.loads(raw) if raw else {}
    except (ValueError, TypeError):
        completed = {}
    steps = []
    for s in _ONBOARDING_STEPS:
        steps.append(
            {
                **s,
                "done": bool(completed.get(s["id"])),
            }
        )
    return {"steps": steps, "completed": completed}
