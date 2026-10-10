"""Account blueprint: me/onboarding/settings/hotkeys/profile/delete (moved from web/app.py)."""

import json
import logging

from datetime import timedelta

from flask import Blueprint, jsonify, request
from flask_limiter.util import get_remote_address

from web.auth_helpers import (
    _check_password,
    _extract_session,
    _hash_password,
    _load_onboarding,
    _session_created_at,
    _text,
    _valid_name,
    _valid_password,
    _verify_session,
    get_user_entitlements,
    is_auth0_account,
    is_owner,
    require_auth,
)
from web.auth_helpers import _ONBOARDING_STEPS
from web.db import _get_db, utcnow
from web.extensions import limiter
from web.services import email_service

logger = logging.getLogger(__name__)

account_bp = Blueprint("account", __name__)


@account_bp.route("/api/me", methods=["GET"])
def me():
    """Return the current user's profile (or 401 when logged out)."""
    session_id = _extract_session()
    user_id = _verify_session(session_id)
    if user_id is None:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    conn = _get_db()
    user = conn.execute(
        "SELECT id, name, email_or_phone, onboarding, created_at, tier, role, email_verified "
        "FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    if user is None:
        return jsonify({"success": False, "error": "Not found"}), 404

    entitlements = get_user_entitlements(user_id)
    role = entitlements["role"]
    is_owner_val = entitlements["is_owner"]

    return jsonify(
        {
            "success": True,
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email_or_phone": user["email_or_phone"],
                "created_at": user["created_at"],
                "tier": entitlements["tier"],
                "role": role,
                "is_owner": is_owner_val,
                "email_verified": bool(user["email_verified"]) if "email_verified" in user.keys() else False,
                "entitlements": entitlements,
                "onboarding": _load_onboarding(user["onboarding"]),
            },
        }
    )


@account_bp.route("/api/onboarding", methods=["GET", "POST"])
def onboarding():
    """GET returns steps + progress; POST marks a step complete."""
    session_id = _extract_session()
    user_id = _verify_session(session_id)
    if user_id is None:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    conn = _get_db()
    row = conn.execute("SELECT onboarding FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        conn.close()
        return jsonify({"success": False, "error": "Not found"}), 404

    try:
        completed = json.loads(row["onboarding"]) if row["onboarding"] else {}
    except (ValueError, TypeError):
        completed = {}

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        step_id = _text(data.get("step"))
        valid_ids = {s["id"] for s in _ONBOARDING_STEPS}
        if step_id not in valid_ids:
            conn.close()
            return jsonify({"success": False, "error": "Unknown step"}), 400
        done = bool(data.get("done", True))
        completed[step_id] = done
        conn.execute("UPDATE users SET onboarding = ? WHERE id = ?", (json.dumps(completed), user_id))
        conn.commit()

    conn.close()
    return jsonify(
        {
            "success": True,
            "onboarding": {
                "steps": [{**s, "done": bool(completed.get(s["id"]))} for s in _ONBOARDING_STEPS],
                "completed": completed,
            },
        }
    )


@account_bp.route("/api/settings", methods=["GET", "POST"])
@require_auth
@limiter.limit("30 per minute", key_func=get_remote_address)
def settings(user_id):
    conn = _get_db()
    row = conn.execute("SELECT settings FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        conn.close()
        return jsonify({"status": "error", "message": "User not found"}), 404

    try:
        current = json.loads(row["settings"]) if row["settings"] else {}
    except (ValueError, TypeError):
        current = {}

    if request.method == "POST":
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            conn.close()
            return jsonify({"status": "error", "message": "Invalid JSON body"}), 400
        current.update(data)
        conn.execute("UPDATE users SET settings = ? WHERE id = ?", (json.dumps(current), user_id))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Settings saved successfully", "settings": current})

    conn.close()
    defaults = {
        "theme": "light",
        "language": "en",
        "notifications": True,
        "sound": True,
        "autoStart": False,
        "hotkey": "Win+Shift",
    }
    defaults.update(current)
    return jsonify({"status": "success", "settings": defaults})


@account_bp.route("/api/hotkeys", methods=["GET", "POST"])
@require_auth
@limiter.limit("30 per minute", key_func=get_remote_address)
def hotkeys(user_id):
    conn = _get_db()
    row = conn.execute("SELECT hotkeys FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        conn.close()
        return jsonify({"status": "error", "message": "User not found"}), 404

    try:
        current = json.loads(row["hotkeys"]) if row["hotkeys"] else {}
    except (ValueError, TypeError):
        current = {}

    if request.method == "POST":
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            conn.close()
            return jsonify({"status": "error", "message": "Invalid JSON body"}), 400
        current.update(data)
        conn.execute("UPDATE users SET hotkeys = ? WHERE id = ?", (json.dumps(current), user_id))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Hotkey updated successfully", "hotkeys": current})

    conn.close()
    defaults = {
        "record": "Win+Shift",
        "casual": "Win+Alt",
        "technical": "Win+Ctrl",
        "settings": "Win+;",
    }
    defaults.update(current)
    return jsonify({"status": "success", "hotkeys": defaults})


@account_bp.route("/api/auth/update-profile", methods=["POST"])
@require_auth
@limiter.limit("10 per hour", key_func=get_remote_address)
def update_profile(user_id):
    data = request.json or {}
    if "name" in data and not isinstance(data["name"], str):
        # Fail closed rather than silently ignoring a type-confused field.
        return jsonify({"success": False, "error": "Invalid name"}), 400
    name = _text(data.get("name"))
    current_password = _text(data.get("current_password"))
    new_password = _text(data.get("new_password"))

    conn = _get_db()
    user = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        conn.close()
        return jsonify({"success": False, "error": "User not found"}), 404

    if new_password:
        if is_auth0_account(user["password_hash"]):
            # Auth0-provisioned accounts have no local password yet: there is
            # no current password to check, so setting the first one only
            # needs to meet the policy. The session revocation and the
            # notification email below still run, exactly as for a change.
            if not _valid_password(new_password):
                conn.close()
                return jsonify({"success": False, "error": "New password must be 8-128 characters"}), 400
        else:
            if not current_password:
                conn.close()
                return jsonify({"success": False, "error": "Current password required"}), 400
            if not _check_password(user["password_hash"], current_password):
                conn.close()
                return jsonify({"success": False, "error": "Incorrect current password"}), 400
            if not _valid_password(new_password):
                conn.close()
                return jsonify({"success": False, "error": "New password must be 8-128 characters"}), 400
        pw_hash = _hash_password(new_password)
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, user_id))
        # A password change signs out every *other* device and keeps this one.
        conn.execute("DELETE FROM sessions WHERE user_id = ? AND id != ?", (user_id, _extract_session()))
        password_changed = True
    else:
        password_changed = False

    if name:
        if not _valid_name(name):
            conn.close()
            return jsonify({"success": False, "error": "Name must be 2-80 characters"}), 400
        conn.execute("UPDATE users SET name = ? WHERE id = ?", (name, user_id))

    account = conn.execute("SELECT name, email_or_phone FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.commit()
    conn.close()

    if password_changed and account is not None:
        email_service.send_transactional(
            "password_changed",
            account["email_or_phone"],
            {
                "name": account["name"],
                "changed_at": utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            },
        )
    return jsonify({"success": True, "message": "Profile updated"})


@account_bp.route("/api/account/delete", methods=["POST"])
@require_auth
@limiter.limit("5 per hour", key_func=get_remote_address)
def delete_account(user_id):
    """Delete the account and everything the server holds for it.

    Requires the account password, not just a session: deleting an account is
    irreversible, and a stolen unlocked laptop should not be enough. Every
    related row goes with the user through ``ON DELETE CASCADE`` (sessions,
    transcriptions, usage, tokens, preferences); the confirmation email is sent
    last, after the address has been captured.
    """
    data = request.get_json(silent=True) or {}
    password = _text(data.get("password"))
    confirm = _text(data.get("confirm")).upper()

    if confirm != "DELETE":
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Type DELETE to confirm account deletion.",
                    "code": "confirmation_required",
                }
            ),
            400,
        )

    conn = _get_db()
    user = conn.execute(
        "SELECT name, email_or_phone, password_hash, is_owner FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if user is None:
        conn.close()
        return jsonify({"success": False, "error": "User not found"}), 404
    if bool(user["is_owner"]) or is_owner(user_id=user_id):
        # Guard against locking the operator out of their own deployment.
        conn.close()
        return (
            jsonify(
                {
                    "success": False,
                    "error": "The owner account cannot be deleted from the app.",
                    "code": "owner_protected",
                }
            ),
            403,
        )
    if is_auth0_account(user["password_hash"]):
        # Auth0 accounts have no local password (``password_hash="auth0:..."``
        # never verifies), so a password check would 401 forever. Instead the
        # typed DELETE confirmation above plus a freshly minted session prove
        # intent: the session must have been created less than 5 minutes ago
        # (i.e. the user just re-authenticated with the identity provider).
        created = _session_created_at(_extract_session())
        if created is None or utcnow() - created > timedelta(minutes=5):
            conn.close()
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Sign in again, then retry deleting your account within 5 minutes.",
                        "code": "reauth_required",
                    }
                ),
                403,
            )
    else:
        if not password:
            conn.close()
            return jsonify({"success": False, "error": "Password required"}), 400
        if not _check_password(user["password_hash"], password):
            conn.close()
            return jsonify({"success": False, "error": "Incorrect password"}), 401

    name = user["name"]
    address = user["email_or_phone"]
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    # Sent after the row is gone: this is the last message that address receives.
    if address and "@" in address:
        email_service.send_transactional("account_deleted", address, {"name": name})
    logger.info("account deleted for user %s", user_id)
    return jsonify({"success": True, "message": "Your account has been deleted."})
