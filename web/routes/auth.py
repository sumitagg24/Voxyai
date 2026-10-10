"""Auth blueprint: signup/login/verify/reset/auth0/qr/admin (moved from web/app.py)."""

import json
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta

from flask import Blueprint, g, jsonify, request
from flask_limiter.util import get_remote_address

from web.auth_helpers import (
    _check_password,
    _create_session,
    _ensure_admin,
    _hash_password,
    _is_disposable_email,
    _issue_email_token,
    _load_onboarding,
    _onboarding_steps,
    _password_domain_allowed,
    _text,
    _valid_identifier,
    _valid_name,
    _valid_password,
    _verify_session,
    get_user_tier,
    is_admin,
    is_owner,
    normalize_email,
    require_admin,
    require_auth,
)
from web.auth_helpers import _EMAIL_RE
from web.db import _get_db, utcnow
from web.extensions import limiter
from web.services import email_preferences, email_service

import requests as http_requests

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


_QR_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


_jwks_cache: dict = {"keys": [], "fetched_at": None}


def _new_qr_code() -> str:
    return "".join(secrets.choice(_QR_ALPHABET) for _ in range(6))


def _auth0_jwks(domain: str) -> dict:
    now = utcnow()
    if _jwks_cache["keys"] and _jwks_cache["fetched_at"] and (now - _jwks_cache["fetched_at"]) < timedelta(hours=12):
        return {"keys": _jwks_cache["keys"]}
    resp = http_requests.get(f"https://{domain}/.well-known/jwks.json", timeout=10)
    resp.raise_for_status()
    data = resp.json()
    _jwks_cache.update(keys=data.get("keys", []), fetched_at=now)
    return data


def _verify_auth0_token(id_token: str) -> dict:
    """Verify an Auth0 ID token (RS256 via JWKS). Raises on any failure."""
    import jwt as pyjwt

    domain = os.environ.get("AUTH0_DOMAIN", "").strip().strip("/")
    client_id = os.environ.get("AUTH0_CLIENT_ID", "").strip()
    if not domain or not client_id:
        raise ValueError("Auth0 is not configured on this server")
    header = pyjwt.get_unverified_header(id_token)
    jwks = _auth0_jwks(domain)
    key_data = next(
        (k for k in jwks.get("keys", []) if k.get("kid") == header.get("kid")),
        None,
    )
    if not key_data:
        _jwks_cache.update(keys=[], fetched_at=None)  # force refetch next time
        raise ValueError("Unknown token signing key")
    public_key = pyjwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key_data))
    return pyjwt.decode(
        id_token,
        public_key,
        algorithms=["RS256"],
        audience=client_id,
        issuer=f"https://{domain}/",
    )


@auth_bp.route("/api/auth/auth0/config", methods=["GET"])
def auth0_config():
    """Public Auth0 settings for the frontend (client IDs are public by design)."""
    domain = os.environ.get("AUTH0_DOMAIN", "").strip()
    client_id = os.environ.get("AUTH0_CLIENT_ID", "").strip()
    desktop_client_id = os.environ.get("AUTH0_DESKTOP_CLIENT_ID", "").strip() or client_id
    return jsonify(
        {
            "enabled": bool(domain and client_id),
            "domain": domain,
            "clientId": client_id,
            "desktopClientId": desktop_client_id,
        }
    )


@auth_bp.route("/api/auth/auth0", methods=["POST"])
@limiter.limit("20 per hour", key_func=get_remote_address)
def auth_auth0():
    """Log in (or auto-register) with a verified Auth0 ID token."""
    data = request.json or {}
    id_token = data.get("id_token", "")
    if not id_token:
        return jsonify({"success": False, "error": "Missing id_token"}), 400
    try:
        # Resolve via web.app at call time so tests that monkeypatch
        # web.app._verify_auth0_token keep working after the blueprint split.
        try:
            import web.app as _app_mod

            _verify_fn = getattr(_app_mod, "_verify_auth0_token", None) or _verify_auth0_token
        except Exception:
            _verify_fn = _verify_auth0_token
        claims = _verify_fn(id_token)
    except Exception as e:
        logger.warning("Auth0 token verification failed: %s", e)
        return jsonify({"success": False, "error": "Invalid Auth0 token"}), 401

    email = normalize_email(claims.get("email") or "")
    if not email or "@" not in email:
        return jsonify({"success": False, "error": "No email in Auth0 profile"}), 400
    # Identity linking is only safe when the IdP has actually verified the
    # address. Without this check, a malicious IdP tenant could hand out a
    # token claiming someone else's (possibly privileged) email and inherit
    # that account — including the designated owner's.
    if not claims.get("email_verified"):
        logger.warning("Auth0 login refused: email in the ID token is not verified")
        return jsonify({"success": False, "error": "Auth0 account email is not verified"}), 403
    sub = claims.get("sub", "") or ""
    name = ((claims.get("name") or email.split("@")[0]).strip()[:80]) or "Voxy User"

    conn = _get_db()
    user = None
    if sub:
        user = conn.execute("SELECT id FROM users WHERE auth0_sub = ?", (sub,)).fetchone()
    if user is None:
        user = conn.execute("SELECT id FROM users WHERE LOWER(email_or_phone) = LOWER(?)", (email,)).fetchone()
    if user is None:
        cur = conn.execute(
            "INSERT INTO users (name, email_or_phone, password_hash, "
            "email_verified, auth0_sub) VALUES (?, ?, ?, 1, ?)",
            (name, email, "auth0:" + uuid.uuid4().hex, sub or None),
        )
        user_id = cur.lastrowid
    else:
        user_id = user["id"]
        try:
            conn.execute(
                "UPDATE users SET auth0_sub = COALESCE(auth0_sub, ?), " "email_verified = 1 WHERE id = ?",
                (sub or None, user_id),
            )
        except Exception:
            pass
    _ensure_admin(conn, user_id, email)
    conn.commit()
    row = conn.execute(
        "SELECT id, name, email_or_phone, tier, role FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    conn.close()

    session_id = _create_session(user_id)
    return (
        jsonify(
            {
                "success": True,
                "user_id": user_id,
                "session_id": session_id,
                "name": row["name"],
                "email_or_phone": row["email_or_phone"],
                "tier": get_user_tier(user_id),
                "role": "owner" if is_owner(user_id=user_id) else ("admin" if is_admin(user_id=user_id) else "user"),
                "is_owner": is_owner(user_id=user_id),
            }
        ),
        200,
    )


@auth_bp.route("/api/auth/qr/start", methods=["POST"])
@limiter.limit("20 per hour", key_func=get_remote_address)
def qr_start():
    """Create a QR login ticket (5-minute expiry). No auth needed to start."""
    data = request.json or {}
    device = str(data.get("device_name", ""))[:60]
    conn = _get_db()
    code = None
    for _ in range(5):
        candidate = _new_qr_code()
        if not conn.execute("SELECT 1 FROM qr_tickets WHERE code = ?", (candidate,)).fetchone():
            code = candidate
            break
    if not code:
        conn.close()
        return jsonify({"success": False, "error": "Try again"}), 500
    expires = (utcnow() + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO qr_tickets (code, device_name, expires_at) VALUES (?, ?, ?)",
        (code, device, expires),
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True, "code": code, "expires_in": 300}), 200


@auth_bp.route("/api/auth/qr/status", methods=["GET"])
@limiter.limit("60 per hour", key_func=get_remote_address)
def qr_status():
    """Poll a QR ticket. Returns a Voxylis session once approved on the phone."""
    code = (request.args.get("code", "") or "").upper().strip()
    if not code:
        return jsonify({"success": False, "error": "Missing code"}), 400
    conn = _get_db()
    t = conn.execute("SELECT * FROM qr_tickets WHERE code = ?", (code,)).fetchone()
    if t is None:
        conn.close()
        return jsonify({"success": False, "error": "Unknown code"}), 404
    if t["status"] == "expired" or utcnow() > datetime.strptime(t["expires_at"], "%Y-%m-%d %H:%M:%S"):
        conn.execute("UPDATE qr_tickets SET status = 'expired' WHERE code = ?", (code,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "status": "expired"}), 200
    if t["status"] == "approved":
        if t["session_id"]:
            conn.close()
            return (
                jsonify(
                    {
                        "success": True,
                        "status": "approved",
                        "session_id": t["session_id"],
                    }
                ),
                200,
            )
        session_id = _create_session(t["approved_user_id"])
        conn.execute("UPDATE qr_tickets SET session_id = ? WHERE code = ?", (session_id, code))
        conn.commit()
        row = conn.execute(
            "SELECT name, email_or_phone FROM users WHERE id = ?",
            (t["approved_user_id"],),
        ).fetchone()
        conn.close()
        return (
            jsonify(
                {
                    "success": True,
                    "status": "approved",
                    "session_id": session_id,
                    "name": row["name"] if row else "",
                    "email_or_phone": row["email_or_phone"] if row else "",
                }
            ),
            200,
        )
    conn.close()
    return jsonify({"success": True, "status": "pending"}), 200


@auth_bp.route("/api/auth/qr/approve", methods=["POST"])
@require_auth
@limiter.limit("30 per hour", key_func=get_remote_address)
def qr_approve(user_id):
    """Approve a QR login from the logged-in phone. Logs the other device in as you."""
    data = request.json or {}
    code = _text(data.get("code")).upper()
    if not code:
        return jsonify({"success": False, "error": "Missing code"}), 400
    conn = _get_db()
    t = conn.execute("SELECT status, expires_at FROM qr_tickets WHERE code = ?", (code,)).fetchone()
    if t is None:
        conn.close()
        return jsonify({"success": False, "error": "Unknown code"}), 404
    if t["status"] != "pending" or utcnow() > datetime.strptime(t["expires_at"], "%Y-%m-%d %H:%M:%S"):
        conn.execute("UPDATE qr_tickets SET status = 'expired' WHERE code = ?", (code,))
        conn.commit()
        conn.close()
        return jsonify({"success": False, "error": "Code expired"}), 410
    conn.execute(
        "UPDATE qr_tickets SET status = 'approved', approved_user_id = ? WHERE code = ?",
        (user_id, code),
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Login approved"}), 200


@auth_bp.route("/api/admin/users", methods=["GET"])
@require_admin
@limiter.limit("60 per hour", key_func=get_remote_address)
def admin_users(user_id):
    """Admin-only user listing."""
    conn = _get_db()
    rows = conn.execute("SELECT id, name, email_or_phone, tier, role, created_at " "FROM users ORDER BY id").fetchall()
    conn.close()
    return (
        jsonify(
            {
                "success": True,
                "users": [
                    {
                        "id": r["id"],
                        "name": r["name"],
                        "email_or_phone": r["email_or_phone"],
                        "tier": r["tier"] or "free",
                        "role": (r["role"] or "user"),
                        "created_at": r["created_at"],
                    }
                    for r in rows
                ],
            }
        ),
        200,
    )


@auth_bp.route("/api/auth/signup", methods=["POST"])
@limiter.limit("10 per hour", key_func=get_remote_address)
def auth_signup():
    data = request.json or {}
    name = _text(data.get("name"))
    email_or_phone = normalize_email(_text(data.get("email_or_phone")))
    password = _text(data.get("password"))

    if not name or not email_or_phone or not password:
        return jsonify({"success": False, "error": "Missing required fields"}), 400
    if not _valid_name(name):
        return jsonify({"success": False, "error": "Name must be 2-80 characters"}), 400
    if not _valid_identifier(email_or_phone):
        return jsonify({"success": False, "error": "Enter a valid email or phone number"}), 400
    if not _valid_password(password):
        return jsonify({"success": False, "error": "Password must be 8-128 characters"}), 400
    # Password accounts: Gmail / official-domain mail only, never temp mail.
    # (Auth0 social logins bypass this — the IdP already verified the identity.)
    if "@" not in email_or_phone:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Please sign up with your Gmail or company email address.",
                }
            ),
            400,
        )
    if _is_disposable_email(email_or_phone):
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Temporary email addresses are not allowed.",
                }
            ),
            400,
        )
    if not _password_domain_allowed(email_or_phone):
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Password signup is limited to Gmail and official company email.",
                }
            ),
            400,
        )

    conn = _get_db()
    existing = conn.execute("SELECT id FROM users WHERE LOWER(email_or_phone) = LOWER(?)", (email_or_phone,)).fetchone()
    if existing:
        conn.close()
        return jsonify({"success": False, "error": "Account already exists"}), 400

    pw_hash = _hash_password(password)
    cur = conn.execute(
        "INSERT INTO users (name, email_or_phone, password_hash) VALUES (?, ?, ?)",
        (name, email_or_phone, pw_hash),
    )
    user_id = cur.lastrowid
    _ensure_admin(conn, user_id, email_or_phone)
    conn.commit()
    conn.close()

    # Marketing consent is explicit and separate from the account itself.
    try:
        prefs_conn = _get_db()
        email_preferences.set_marketing_opt_in(
            prefs_conn,
            user_id,
            bool(data.get("marketing_opt_in")),
            source="signup",
        )
        prefs_conn.commit()
        prefs_conn.close()
    except Exception as exc:
        logger.warning("Could not store email preferences for new user: %s", type(exc).__name__)

    # Verification is an email flow, not a client-side flag: the token is
    # minted here and only the emailed link can set `email_verified`.
    verify_token = _issue_email_token(user_id, hours=24)
    session_id = _create_session(user_id)
    email_service.send_transactional(
        "welcome",
        email_or_phone,
        {
            "name": name,
            "verify_url": email_service.build_link("verify_email", verify_token) if verify_token else "",
        },
    )
    return (
        jsonify(
            {
                "success": True,
                "user_id": user_id,
                "session_id": session_id,
                "name": name,
                "email_or_phone": email_or_phone,
                "tier": get_user_tier(user_id),
                "role": "owner" if is_owner(user_id=user_id) else ("admin" if is_admin(user_id=user_id) else "user"),
                "is_owner": is_owner(user_id=user_id),
                "email_verified": False,
                "verification_email_sent": email_service.email_configured(),
                "onboarding": {
                    "steps": _onboarding_steps(),
                    "completed": {},
                },
            }
        ),
        201,
    )


@auth_bp.route("/api/auth/login", methods=["POST"])
@limiter.limit("10 per 15 minutes", key_func=get_remote_address)
def auth_login():
    data = request.json or {}
    email_or_phone = normalize_email(_text(data.get("email_or_phone")))
    password = _text(data.get("password"))

    if not email_or_phone or not password:
        return jsonify({"success": False, "error": "Missing required fields"}), 400

    conn = _get_db()
    user = conn.execute(
        "SELECT id, name, password_hash FROM users WHERE LOWER(email_or_phone) = LOWER(?)",
        (email_or_phone,),
    ).fetchone()
    conn.close()

    if user is None or not _check_password(user["password_hash"], password):
        return jsonify({"success": False, "error": "Invalid credentials"}), 401
    if _is_disposable_email(email_or_phone):
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Temporary email addresses are not allowed.",
                }
            ),
            403,
        )

    try:
        admin_conn = _get_db()
        _ensure_admin(admin_conn, user["id"], email_or_phone)
        admin_conn.commit()
        admin_conn.close()
    except Exception:
        pass
    session_id = _create_session(user["id"])
    return (
        jsonify(
            {
                "success": True,
                "user_id": user["id"],
                "session_id": session_id,
                "name": user["name"],
                "email_or_phone": email_or_phone,
                "tier": get_user_tier(user["id"]),
                "role": (
                    "owner" if is_owner(user_id=user["id"]) else ("admin" if is_admin(user_id=user["id"]) else "user")
                ),
                "is_owner": is_owner(user_id=user["id"]),
            }
        ),
        200,
    )


@auth_bp.route("/api/auth/verify", methods=["POST"])
def auth_verify():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "") or request.headers.get("X-Session-Id", "")
    if not session_id or not isinstance(session_id, str):
        return jsonify({"valid": False, "error": "Missing session_id"}), 400

    user_id = _verify_session(session_id)
    if user_id is None:
        return jsonify({"valid": False, "error": "Invalid or expired session"}), 200

    conn = _get_db()
    user = conn.execute(
        "SELECT id, name, email_or_phone, onboarding, email_verified FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()

    return (
        jsonify(
            {
                "valid": True,
                "user_id": user["id"],
                "name": user["name"],
                "email_or_phone": user["email_or_phone"],
                "email_verified": bool(user["email_verified"]),
                "onboarding": _load_onboarding(user["onboarding"]),
                # Present when the server rotated the session; also sent as the
                # X-Session-Rotated header. Clients must persist the new id.
                "session_id": getattr(g, "rotated_session_id", None) or session_id,
            }
        ),
        200,
    )


@auth_bp.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    data = request.json or {}
    session_id = data.get("session_id", "")
    if not session_id:
        return jsonify({"success": False, "error": "Missing session_id"}), 400

    conn = _get_db()
    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Logged out"}), 200


@auth_bp.route("/api/auth/forgot-password", methods=["POST"])
@limiter.limit("5 per hour", key_func=get_remote_address)
def forgot_password():
    data = request.json or {}
    email = normalize_email(_text(data.get("email")))
    if not email or not _EMAIL_RE.match(email):
        return jsonify({"success": False, "error": "Valid email required"}), 400

    conn = _get_db()
    user = conn.execute("SELECT id FROM users WHERE LOWER(email_or_phone) = LOWER(?)", (email,)).fetchone()
    if user is None:
        conn.close()
        return jsonify({"success": True, "message": "If an account exists, a reset link has been sent."})

    token = secrets.token_urlsafe(32)
    expires = (utcnow() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    # A new request invalidates every outstanding link for this account.
    conn.execute("UPDATE password_resets SET used = 1 WHERE user_id = ? AND used = 0", (user["id"],))
    conn.execute(
        "INSERT INTO password_resets (user_id, token, expires_at) VALUES (?, ?, ?)",
        (user["id"], token, expires),
    )
    conn.commit()
    conn.close()

    # The token goes into the email only. It is never logged and never returned:
    # a reset link in a log file or an API response is a working credential.
    email_service.send_transactional(
        "password_reset",
        email,
        {"reset_url": email_service.build_link("password_reset", token), "expires_in": "1 hour"},
    )
    # Deliberately identical whether or not the address exists.
    return jsonify(
        {
            "success": True,
            "message": "If an account exists, a reset link has been sent.",
        }
    )


@auth_bp.route("/api/auth/reset-password", methods=["POST"])
@limiter.limit("10 per hour", key_func=get_remote_address)
def reset_password():
    data = request.json or {}
    token = _text(data.get("token"))
    new_password = _text(data.get("password"))

    if not token or not new_password:
        return jsonify({"success": False, "error": "Token and password required"}), 400
    if not _valid_password(new_password):
        return jsonify({"success": False, "error": "Password must be 8-128 characters"}), 400

    conn = _get_db()
    row = conn.execute("SELECT id, user_id, expires_at, used FROM password_resets WHERE token = ?", (token,)).fetchone()
    if row is None or row["used"]:
        conn.close()
        return jsonify({"success": False, "error": "Invalid or used token"}), 400

    expires = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
    if utcnow() > expires:
        conn.close()
        return jsonify({"success": False, "error": "Token expired"}), 400

    pw_hash = _hash_password(new_password)
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, row["user_id"]))
    # Single use: every other outstanding link for this account is retired too.
    conn.execute("UPDATE password_resets SET used = 1 WHERE user_id = ?", (row["user_id"],))
    # A password change signs out every device, including the attacker's.
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (row["user_id"],))
    account = conn.execute("SELECT name, email_or_phone FROM users WHERE id = ?", (row["user_id"],)).fetchone()
    conn.commit()
    conn.close()

    if account is not None:
        email_service.send_transactional(
            "password_changed",
            account["email_or_phone"],
            {
                "name": account["name"],
                "changed_at": utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            },
        )
    return jsonify(
        {
            "success": True,
            "message": "Password reset successful. Sign in again with your new password.",
        }
    )


@auth_bp.route("/api/auth/verify-email", methods=["POST"])
@require_auth
@limiter.limit("5 per hour", key_func=get_remote_address)
def send_verification(user_id):
    conn = _get_db()
    user = conn.execute("SELECT email_or_phone, email_verified FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        conn.close()
        return jsonify({"success": False, "error": "User not found"}), 404
    if user["email_verified"]:
        conn.close()
        return jsonify({"success": True, "message": "Email already verified"})

    address = user["email_or_phone"]
    conn.close()
    if "@" not in (address or ""):
        return (
            jsonify(
                {
                    "success": False,
                    "error": "This account has no email address to verify.",
                }
            ),
            400,
        )

    token = _issue_email_token(user_id, hours=24)
    delivered = email_service.send_transactional(
        "verify_email",
        address,
        {"verify_url": email_service.build_link("verify_email", token), "expires_in": "24 hours"},
    )
    if delivered is None:
        # Be explicit instead of claiming an email went out that did not.
        return (
            jsonify(
                {
                    "success": False,
                    "code": "email_delivery_unavailable",
                    "error": (
                        "We could not send the verification email. This deployment has no email "
                        "provider configured — contact support."
                    ),
                }
            ),
            503,
        )
    return jsonify(
        {
            "success": True,
            "message": "Verification email sent. The link expires in 24 hours.",
        }
    )


@auth_bp.route("/api/auth/confirm-email", methods=["POST"])
@limiter.limit("10 per hour", key_func=get_remote_address)
def confirm_email():
    data = request.json or {}
    token = _text(data.get("token"))
    if not token:
        return jsonify({"success": False, "error": "Token required"}), 400

    conn = _get_db()
    row = conn.execute(
        "SELECT id, user_id, expires_at, used FROM email_verifications WHERE token = ?", (token,)
    ).fetchone()
    if row is None or row["used"]:
        conn.close()
        return jsonify({"success": False, "error": "Invalid or used token"}), 400

    expires = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
    if utcnow() > expires:
        conn.close()
        return jsonify({"success": False, "error": "Token expired"}), 400

    conn.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (row["user_id"],))
    conn.execute("UPDATE email_verifications SET used = 1 WHERE id = ?", (row["id"],))
    conn.commit()
    conn.close()
    return jsonify(
        {
            "success": True,
            "email_verified": True,
            "message": "Email verified successfully. Thanks for confirming.",
        }
    )
