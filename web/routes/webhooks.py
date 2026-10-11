"""Webhooks blueprint: verified payment-provider callbacks (Dodo Payments).

The only production path to a paid tier is a signed webhook from Dodo. Every
request is verified Standard-Webhooks style before anything is trusted:

* the HMAC-SHA256 is computed over ``"{id}.{timestamp}.{raw_body}"`` with the
  ``DODO_WEBHOOK_SECRET`` (``whsec_...``), base64-encoded;
* ``webhook-signature`` may carry several space-separated ``v1,<sig>``
  candidates (key rotation); comparison is constant-time;
* ``webhook-timestamp`` must be within 5 minutes of now (replay window);
* the body is read raw via ``request.get_data()`` — never re-serialised JSON,
  whose whitespace would break the signature.

Responses: 503 while Dodo is unconfigured, 4xx for a missing/bad signature or
an unreadable payload, and always 2xx (``acked: true``) once a request is
verified — including replays, which are dropped via the ``processed_events``
table (``event_id`` UNIQUE) and reported as duplicates.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
import time

from flask import Blueprint, jsonify, request

from web.db import _get_db
from web.services import subscription_service
from web.tier import TIER_BUSINESS, TIER_FREE, TIER_PRO

logger = logging.getLogger(__name__)

webhooks_bp = Blueprint("webhooks", __name__)

#: Maximum age of a webhook delivery (seconds). Anything older is a replay.
_WEBHOOK_TOLERANCE_SECONDS = 5 * 60


def _signing_key(secret: str) -> bytes | None:
    """Decode a ``whsec_<base64>`` secret to raw key bytes (None if malformed)."""
    candidate = (secret or "").strip()
    if candidate.startswith("whsec_"):
        candidate = candidate[len("whsec_") :]
    try:
        return base64.b64decode(candidate, validate=True)
    except (binascii.Error, ValueError):
        return None


def verify_dodo_signature(
    secret: str,
    webhook_id: str,
    timestamp: str,
    signature_header: str,
    raw_body: bytes,
) -> bool:
    """Verify a Standard-Webhooks-style Dodo delivery. Fail closed."""
    if not secret or not webhook_id or not timestamp or not signature_header or raw_body is None:
        return False
    key = _signing_key(secret)
    if key is None:
        logger.warning("Dodo webhook secret is not valid base64 after the whsec_ prefix")
        return False
    try:
        delivered_at = int(str(timestamp).strip())
    except (TypeError, ValueError):
        return False
    if abs(time.time() - delivered_at) > _WEBHOOK_TOLERANCE_SECONDS:
        return False
    try:
        body_text = raw_body.decode("utf-8")
    except UnicodeDecodeError:
        return False
    signed = f"{webhook_id}.{str(timestamp).strip()}.{body_text}".encode("utf-8")
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode("ascii")
    for candidate in signature_header.split():
        scheme, _, value = candidate.partition(",")
        if scheme.strip().lower() != "v1" or not value:
            continue
        if hmac.compare_digest(value.strip(), expected):
            return True
    return False


def _nested(data: dict, *paths: str):
    """First non-empty string found by walking dotted paths (``a.b.c``)."""
    for path in paths:
        current = data
        for part in path.split("."):
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(part)
        if isinstance(current, str) and current.strip():
            return current.strip()
        if isinstance(current, (int, float)) and not isinstance(current, bool):
            return str(current)
    return ""


def _resolve_user(conn, data: dict):
    """Return the user id for a webhook payload, or None when unroutable.

    An explicit ``metadata.user_id`` (set by checkout) wins; otherwise the
    customer email is matched case-insensitively against ``email_or_phone``.
    """
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    for key in ("user_id", "voxylis_user_id"):
        raw = (metadata or {}).get(key)
        try:
            user_id = int(raw) if raw is not None and str(raw).strip() else None
        except (TypeError, ValueError):
            user_id = None
        if user_id:
            row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
            if row is not None:
                return user_id
    email = _nested(
        data,
        "metadata.email",
        "customer.email",
        "customer_email",
        "email",
        "customer.id",
    )
    if email and "@" in email:
        row = conn.execute(
            "SELECT id FROM users WHERE LOWER(email_or_phone) = ?",
            (email.lower(),),
        ).fetchone()
        if row is not None:
            return row["id"]
    return None


def _classify(event_type: str) -> str:
    """Map a Dodo event type to ``grant`` / ``revoke`` / ``ignore``.

    Successful payments and (re)activated subscriptions grant the paid tier;
    expired or cancelled subscriptions drop back to free; everything else
    (failed payments, disputes, refunds, unknown future types) is acknowledged
    without touching the tier.
    """
    kind = (event_type or "").strip().lower()
    if kind in ("payment.succeeded", "subscription.active", "subscription.renewed"):
        return "grant"
    if kind.rsplit(".", 1)[-1] in ("expired", "cancelled"):
        return "revoke"
    return "ignore"


@webhooks_bp.route("/api/webhooks/dodo", methods=["POST"])
def dodo_webhook():
    """Receive a signed Dodo Payments event and apply the tier change."""
    if not subscription_service.dodo_configured():
        return (
            jsonify(
                {
                    "success": False,
                    "code": "payments_not_configured",
                    "error": "Dodo Payments is not configured on this deployment.",
                }
            ),
            503,
        )

    webhook_id = (request.headers.get("webhook-id") or "").strip()
    timestamp = (request.headers.get("webhook-timestamp") or "").strip()
    signature = (request.headers.get("webhook-signature") or "").strip()
    raw_body = request.get_data()
    if not webhook_id or not timestamp or not signature:
        return (
            jsonify(
                {
                    "success": False,
                    "code": "missing_signature",
                    "error": "Missing webhook-id, webhook-timestamp or webhook-signature.",
                }
            ),
            400,
        )
    if not verify_dodo_signature(
        subscription_service.dodo_webhook_secret(), webhook_id, timestamp, signature, raw_body
    ):
        return (
            jsonify({"success": False, "code": "invalid_signature", "error": "Invalid webhook signature."}),
            400,
        )

    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except (UnicodeDecodeError, ValueError):
        return jsonify({"success": False, "code": "invalid_payload", "error": "Request body is not valid JSON."}), 400
    if not isinstance(payload, dict):
        return jsonify({"success": False, "code": "invalid_payload", "error": "Request body is not valid JSON."}), 400

    event_type = str(payload.get("type") or "").strip()
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    event_id = str(payload.get("event_id") or payload.get("id") or webhook_id).strip() or webhook_id

    conn = _get_db()
    try:
        # processed_events is created by schema migration 10 (web.db), not here.
        if conn.execute("SELECT 1 FROM processed_events WHERE event_id = ?", (event_id,)).fetchone():
            return jsonify({"success": True, "acked": True, "duplicate": True, "event_id": event_id}), 200

        action = _classify(event_type)
        if action == "ignore":
            conn.execute("INSERT OR IGNORE INTO processed_events (event_id, source) VALUES (?, ?)", (event_id, "dodo"))
            conn.commit()
            logger.info("Dodo webhook %s (%s) acknowledged without tier change", event_id, event_type)
            return jsonify({"success": True, "acked": True, "applied": False, "event_type": event_type}), 200

        user_id = _resolve_user(conn, data)
        if user_id is None:
            # Acknowledge so the provider stops retrying; the warning in the
            # log is the signal that checkout metadata needs the account.
            conn.execute("INSERT OR IGNORE INTO processed_events (event_id, source) VALUES (?, ?)", (event_id, "dodo"))
            conn.commit()
            logger.warning("Dodo webhook %s (%s) has no matching Voxylis account", event_id, event_type)
            return (
                jsonify({"success": True, "acked": True, "applied": False, "reason": "unknown_customer"}),
                200,
            )

        if action == "revoke":
            new_tier = TIER_FREE
        else:
            plan_ref = _nested(
                data,
                "metadata.plan",
                "plan",
                "plan_id",
                "product_id",
                "product_name",
                "product.name",
                "subscription.product_id",
            )
            new_tier = subscription_service.dodo_plan_to_tier(plan_ref)
            if new_tier not in (TIER_PRO, TIER_BUSINESS):
                new_tier = TIER_PRO

        try:
            result = subscription_service.apply_tier_change(
                conn,
                user_id=user_id,
                new_tier=new_tier,
                source=subscription_service.SOURCE_PAYMENT_WEBHOOK,
                actor="dodo-webhook",
                webhook_verified=True,
                note=f"dodo {event_type} {event_id}",
            )
        except subscription_service.TierChangeDenied as denied:
            conn.rollback()
            logger.warning("Dodo webhook %s refused tier change: %s", event_id, denied.code)
            return jsonify({"success": True, "acked": True, "applied": False, "reason": denied.code}), 200

        conn.execute("INSERT OR IGNORE INTO processed_events (event_id, source) VALUES (?, ?)", (event_id, "dodo"))
        conn.commit()
    finally:
        conn.close()

    logger.warning("Dodo webhook applied tier %s for user %s (%s)", result.tier, user_id, event_type)
    return (
        jsonify(
            {
                "success": True,
                "acked": True,
                "applied": True,
                "tier": result.tier,
                "event_type": event_type,
                "event_id": event_id,
            }
        ),
        200,
    )
