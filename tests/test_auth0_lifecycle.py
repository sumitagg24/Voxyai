"""Auth0 account lifecycle: deletion and first-password flows.

Auth0-provisioned accounts store ``password_hash="auth0:<uuid>"`` — a marker,
never a verifiable credential — so every password-gated flow must branch on it
instead of comparing a password the user never set.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from web.db import utcnow


def _make_auth0_user(web_app, email: str = "social@gmail.com") -> int:
    conn = web_app._get_db()
    cur = conn.execute(
        "INSERT INTO users (name, email_or_phone, password_hash, email_verified, auth0_sub)" " VALUES (?, ?, ?, 1, ?)",
        ("Social User", email, "auth0:" + uuid.uuid4().hex, "auth0|123"),
    )
    user_id = cur.lastrowid
    conn.commit()
    conn.close()
    return user_id


def _backdate_session(web_app, session_id: str, minutes: int) -> None:
    import hashlib

    stale = (utcnow() - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
    session_hash = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    conn = web_app._get_db()
    conn.execute("UPDATE sessions SET created_at = ? WHERE id = ?", (stale, session_hash))
    conn.commit()
    conn.close()


def test_auth0_account_deletes_with_fresh_session_and_delete_confirmation(app_client):
    client, web_app = app_client
    user_id = _make_auth0_user(web_app)
    session_id = web_app._create_session(user_id)
    headers = {"X-Session-Id": session_id}

    # No local password exists, so none is asked for: DELETE + fresh session.
    response = client.post("/api/account/delete", json={"confirm": "DELETE"}, headers=headers)
    assert response.status_code == 200, response.get_json()

    conn = web_app._get_db()
    remaining = conn.execute("SELECT COUNT(*) AS c FROM users WHERE id = ?", (user_id,)).fetchone()["c"]
    conn.close()
    assert remaining == 0


def test_auth0_account_deletion_needs_delete_confirmation(app_client):
    client, web_app = app_client
    user_id = _make_auth0_user(web_app, "social2@gmail.com")
    headers = {"X-Session-Id": web_app._create_session(user_id)}

    response = client.post("/api/account/delete", json={"confirm": "yes"}, headers=headers)
    assert response.status_code == 400
    assert response.get_json()["code"] == "confirmation_required"


def test_auth0_account_deletion_with_stale_session_needs_reauth(app_client):
    client, web_app = app_client
    user_id = _make_auth0_user(web_app, "social3@gmail.com")
    session_id = web_app._create_session(user_id)
    _backdate_session(web_app, session_id, minutes=6)
    headers = {"X-Session-Id": session_id}

    response = client.post("/api/account/delete", json={"confirm": "DELETE"}, headers=headers)
    assert response.status_code == 403
    assert response.get_json()["code"] == "reauth_required"

    # A fresh login (new session) unlocks the same request.
    fresh = web_app._create_session(user_id)
    retry = client.post("/api/account/delete", json={"confirm": "DELETE"}, headers={"X-Session-Id": fresh})
    assert retry.status_code == 200, retry.get_json()


def test_password_login_never_works_for_auth0_marker_hash(app_client):
    """Documents why the branch exists: the marker hash verifies against nothing."""
    client, web_app = app_client
    _make_auth0_user(web_app, "social4@gmail.com")

    response = client.post("/api/auth/login", json={"email_or_phone": "social4@gmail.com", "password": "anything"})
    assert response.status_code == 401


def test_auth0_user_can_set_initial_password_without_current_password(app_client):
    client, web_app = app_client
    user_id = _make_auth0_user(web_app, "social5@gmail.com")
    first_session = web_app._create_session(user_id)
    other_session = web_app._create_session(user_id)

    response = client.post(
        "/api/auth/update-profile",
        json={"new_password": "a-brand-new-password"},
        headers={"X-Session-Id": first_session},
    )
    assert response.status_code == 200, response.get_json()

    # The marker is replaced by a real hash, and password login works now.
    conn = web_app._get_db()
    stored = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()["password_hash"]
    conn.close()
    assert not stored.startswith("auth0:")
    login = client.post(
        "/api/auth/login", json={"email_or_phone": "social5@gmail.com", "password": "a-brand-new-password"}
    )
    assert login.status_code == 200

    # Setting the password still signs out every *other* device.
    assert client.post("/api/auth/verify", json={"session_id": first_session}).get_json()["valid"] is True
    assert client.post("/api/auth/verify", json={"session_id": other_session}).get_json()["valid"] is False


def test_auth0_initial_password_must_meet_policy(app_client):
    client, web_app = app_client
    user_id = _make_auth0_user(web_app, "social6@gmail.com")
    headers = {"X-Session-Id": web_app._create_session(user_id)}

    response = client.post("/api/auth/update-profile", json={"new_password": "short"}, headers=headers)
    assert response.status_code == 400


def test_password_account_still_needs_current_password(app_client, user):
    response = user.client.post(
        "/api/auth/update-profile", json={"new_password": "a-brand-new-password"}, headers=user.headers
    )
    assert response.status_code == 400
    assert "current password" in response.get_json()["error"].lower()
