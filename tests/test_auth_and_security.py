"""Authentication lifecycle, session handling and API security posture."""

from __future__ import annotations

import os
from tests.conftest import REPO_ROOT, ApiUser, login, signup


# ── account lifecycle ────────────────────────────────────────────────────────


def test_signup_login_verify_logout(app_client):
    client, _ = app_client
    created = signup(client, "lifecycle@gmail.com")
    assert created.status_code == 201
    session_id = created.get_json()["session_id"]

    verified = client.post("/api/auth/verify", json={"session_id": session_id})
    assert verified.status_code == 200
    assert verified.get_json()["valid"] is True

    # Re-login issues a different session and both remain usable.
    second = login(client, "lifecycle@gmail.com").get_json()["session_id"]
    assert second != session_id
    assert client.post("/api/auth/verify", json={"session_id": second}).get_json()["valid"] is True

    assert client.post("/api/auth/logout", json={"session_id": second}).status_code == 200
    assert client.post("/api/auth/verify", json={"session_id": second}).get_json()["valid"] is False
    # Logging out one session must not invalidate the other.
    assert client.post("/api/auth/verify", json={"session_id": session_id}).get_json()["valid"] is True


def test_duplicate_signup_is_rejected(app_client):
    client, _ = app_client
    assert signup(client, "dupe@gmail.com").status_code == 201
    again = signup(client, "dupe@gmail.com")
    assert again.status_code == 400
    assert "already exists" in again.get_json()["error"].lower()


def test_password_policy_and_disposable_domains(app_client):
    client, _ = app_client
    assert signup(client, "short@gmail.com", password="abc").status_code == 400
    disposable = signup(client, "user@mailinator.com")
    assert disposable.status_code == 400
    assert "temporary" in disposable.get_json()["error"].lower()
    other_domain = signup(client, "user@example.org")
    assert other_domain.status_code == 400


def test_login_with_wrong_password_fails(app_client):
    client, _ = app_client
    signup(client, "wrongpw@gmail.com")
    response = login(client, "wrongpw@gmail.com", password="not-the-password")
    assert response.status_code == 401


def test_expired_session_is_rejected_and_removed(app_client):
    client, web_app = app_client
    user = ApiUser(client, "expiry@gmail.com")
    conn = web_app._get_db()
    conn.execute(
        "UPDATE sessions SET expires_at = '2000-01-01 00:00:00' WHERE id = ?",
        (user.session_id,),
    )
    conn.commit()
    conn.close()

    assert client.post("/api/auth/verify", json={"session_id": user.session_id}).get_json()["valid"] is False
    conn = web_app._get_db()
    remaining = conn.execute("SELECT COUNT(*) AS c FROM sessions WHERE id = ?", (user.session_id,)).fetchone()["c"]
    conn.close()
    assert remaining == 0


def test_session_rotates_after_a_day(app_client):
    client, web_app = app_client
    user = ApiUser(client, "rotate@gmail.com")
    conn = web_app._get_db()
    conn.execute("UPDATE sessions SET created_at = '2020-01-01 00:00:00' WHERE id = ?", (user.session_id,))
    conn.commit()
    conn.close()

    # A stale session must still authenticate, but issue a new identifier.
    response = client.post("/api/auth/verify", json={"session_id": user.session_id})
    assert response.get_json()["valid"] is True
    conn = web_app._get_db()
    old = conn.execute("SELECT COUNT(*) AS c FROM sessions WHERE id = ?", (user.session_id,)).fetchone()["c"]
    conn.close()
    assert old == 0, "rotated session should no longer exist under the old id"


def test_protected_endpoints_require_auth(app_client):
    client, _ = app_client
    for path in ("/api/me", "/api/settings", "/api/history", "/api/hotkeys"):
        assert client.get(path).status_code == 401, path


def test_me_reports_server_side_tier(app_client):
    client, _ = app_client
    user = ApiUser(client, "me@gmail.com")
    payload = client.get("/api/me", headers=user.headers).get_json()
    assert payload["user"]["tier"] == "free"
    assert payload["user"]["role"] == "user"


# ── tier enforcement on real features ────────────────────────────────────────


def test_free_tier_cannot_use_paid_enhancement_modes(app_client):
    client, _ = app_client
    user = ApiUser(client, "freemode@gmail.com")
    response = client.post("/api/enhance", json={"text": "hello world", "mode": "creative"}, headers=user.headers)
    assert response.status_code == 403
    assert response.get_json()["current_tier"] == "free"


def test_free_tier_quota_is_enforced(app_client):
    client, web_app = app_client
    user = ApiUser(client, "quota@gmail.com")
    conn = web_app._get_db()
    for _ in range(web_app.FREE_MONTHLY_TRANSCRIPTIONS):
        conn.execute("INSERT INTO transcriptions (user_id, text) VALUES (?, ?)", (user.user_id, "x"))
    conn.commit()
    conn.close()

    allowed, used, limit = web_app.check_transcription_quota(user.user_id)
    assert allowed is False
    assert used == limit == web_app.FREE_MONTHLY_TRANSCRIPTIONS


# ── security posture ─────────────────────────────────────────────────────────


def test_security_headers_are_present(app_client):
    client, _ = app_client
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert "Content-Security-Policy" in response.headers
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_cors_is_never_wildcard(app_client):
    client, web_app = app_client
    response = client.get("/api/health", headers={"Origin": "https://evil.example"})
    allowed = response.headers.get("Access-Control-Allow-Origin", "")
    assert allowed != "*"
    assert "evil.example" not in allowed


def test_oversized_request_body_is_rejected(app_client):
    client, _ = app_client
    payload = {"text": "x" * (2 * 1024 * 1024)}
    response = client.post("/api/enhance", json=payload)
    assert response.status_code in (400, 413)


def test_errors_do_not_leak_internals(app_client):
    """Error responses expose no internals.

    Site paths get the HTML 404 page; API paths keep the structured JSON body.
    Neither may echo back the requested URL or any internal detail.
    """
    client, _ = app_client

    site_resp = client.get("/definitely-not-a-route")
    assert site_resp.status_code == 404
    assert site_resp.content_type.startswith("text/html")
    assert b"definitely-not-a-route" not in site_resp.data

    api_resp = client.get("/api/definitely-not-a-route")
    assert api_resp.status_code == 404
    body = api_resp.get_json()
    assert set(body.keys()) == {"error"}
    assert body["error"] == "Not found"


def _import_app_in_subprocess(env: dict) -> tuple[int, str, str]:
    """Import web.app in a clean interpreter and return the exit code.

    A subprocess is used because a failed module reload leaves importlib in a
    state that makes the assertion about *this* import meaningless.
    """
    import subprocess
    import sys as _sys

    code = "import web.app; print('loaded', web.app.app.config['SECRET_KEY'][:4])"
    completed = subprocess.run(
        [_sys.executable, "-c", code],
        cwd=str(REPO_ROOT),
        env={**os.environ, **env},
        capture_output=True,
        text=True,
    )
    return completed.returncode, completed.stdout, completed.stderr


def test_production_requires_a_real_secret_key(tmp_path):
    db = str(tmp_path / "prod.db")
    code, _, err = _import_app_in_subprocess(
        {
            "VOXYLIS_DB_PATH": db,
            "VOXYLIS_ENV": "production",
            "SECRET_KEY": "change-me-in-production",
        }
    )
    assert code != 0, "production must refuse a placeholder SECRET_KEY"
    assert "SECRET_KEY must be set" in err

    code, out, err = _import_app_in_subprocess(
        {
            "VOXYLIS_DB_PATH": db,
            "VOXYLIS_ENV": "production",
            "SECRET_KEY": "f" * 48,
        }
    )
    assert code == 0, err
    assert "loaded ffff" in out


def test_development_tolerates_a_missing_secret_key_with_a_warning(tmp_path):
    code, _, err = _import_app_in_subprocess(
        {
            "VOXYLIS_DB_PATH": str(tmp_path / "dev.db"),
            "VOXYLIS_ENV": "development",
            "SECRET_KEY": "",
        }
    )
    assert code == 0, err
    assert "SECRET_KEY is unset or too weak" in err


def test_rate_limiting_is_configured(app_client):
    client, web_app = app_client
    assert web_app.limiter is not None
    # The signup route is explicitly limited; hammering it must not be unbounded.
    statuses = [signup(client, f"flood{i}@gmail.com").status_code for i in range(15)]
    assert 429 in statuses, "signup should be rate limited"


# ── adversarial verification regressions (entitlement / type confusion) ─────


def test_signup_ignores_client_supplied_privilege_fields(app_client):
    """Mass assignment: tier/role/is_owner/unlimited in the body must be ignored."""
    client, web_app = app_client
    response = signup(client, "privilege@gmail.com")
    assert response.status_code == 201
    conn = web_app._get_db()
    row = conn.execute(
        "SELECT tier, role, is_owner, email_verified FROM users WHERE email_or_phone = ?",
        ("privilege@gmail.com",),
    ).fetchone()
    conn.close()
    assert (row["tier"], row["role"], bool(row["is_owner"]), bool(row["email_verified"])) == ("free", "user", 0, 0)


def test_subscription_upgrade_cannot_be_granted_via_body_or_headers(app_client):
    """A user cannot talk the server into applying an admin tier change."""
    client, web_app = app_client
    user = ApiUser(client, "upgrader@gmail.com")
    for payload in (
        {"tier": "owner"},
        {"tier": "business", "source": "admin", "actor_is_admin": True},
        {"tier": "owner", "actor": "sumitagg24@gmail.com", "source": "admin"},
    ):
        response = client.post("/api/subscription/upgrade", json=payload, headers=user.headers)
        assert response.status_code == 403, payload
    conn = web_app._get_db()
    tier = conn.execute("SELECT tier FROM users WHERE id = ?", (user.user_id,)).fetchone()["tier"]
    conn.close()
    assert tier == "free"


def test_owner_email_cannot_be_claimed_via_profile_update(app_client):
    """Renaming/re-emailing to the owner address must not confer owner rights."""
    client, web_app = app_client
    user = ApiUser(client, "wannabe@gmail.com")
    client.post(
        "/api/auth/update-profile",
        json={"name": "sumitagg24@gmail.com"},
        headers=user.headers,
    )
    payload = client.get("/api/me", headers=user.headers).get_json()["user"]
    assert payload["is_owner"] is False and payload["role"] == "user"
    conn = web_app._get_db()
    row = conn.execute("SELECT email_or_phone, is_owner FROM users WHERE id = ?", (user.user_id,)).fetchone()
    conn.close()
    assert row["email_or_phone"] == "wannabe@gmail.com" and not row["is_owner"]


def test_type_confused_bodies_are_rejected_not_500(app_client):
    """Object/number-typed JSON fields must be refused cleanly, never crash."""
    client, _ = app_client
    user = ApiUser(client, "typeconfused@gmail.com")
    cases = [
        ("/api/auth/signup", {"name": {"$gt": ""}, "email_or_phone": "x1@gmail.com", "password": "password-123"}),
        ("/api/auth/login", {"email_or_phone": ["array"], "password": None}),
        ("/api/auth/forgot-password", {"email": {"obj": 1}}),
        ("/api/history", {"text": 12345}),
        ("/api/enhance", {"text": {"deep": {"nest": 1}}, "mode": "formal"}),
        ("/api/qa", {"question": [1, 2, 3]}),
        ("/api/auth/update-profile", {"name": {"x": 1}}, user.headers),
        ("/api/subscription/upgrade", {"tier": {"$ne": None}}, user.headers),
    ]
    for path, payload, *h in cases:
        headers = h[0] if h else {}
        response = client.post(path, json=payload, headers=headers)
        assert response.status_code in (400, 401, 403, 415), (path, payload, response.status_code)


def test_history_rejects_non_string_text(app_client):
    """A number in the text field previously slipped through and stored "12345"."""
    client, _ = app_client
    user = ApiUser(client, "numbertext@gmail.com")
    response = client.post("/api/history", json={"text": 12345}, headers=user.headers)
    assert response.status_code == 400


def test_auth0_login_refuses_unverified_email_claims(app_client, monkeypatch):
    """Identity linking requires an IdP-verified address, or a hostile IdP
    tenant could claim someone else's (possibly owner) email."""
    client, web_app = app_client
    monkeypatch.setenv("AUTH0_DOMAIN", " tenants.example.invalid")
    monkeypatch.setenv("AUTH0_CLIENT_ID", "client-id")

    from web import app as web_app_module

    # A *verifiable* token whose claims carry email_verified=false must be
    # refused before any account lookup or session creation.
    monkeypatch.setattr(
        web_app_module,
        "_verify_auth0_token",
        lambda token: {
            "iss": "https://tenants.example.invalid/",
            "aud": "client-id",
            "email": "sumitagg24@gmail.com",
            "email_verified": False,
            "sub": "attacker|1",
        },
    )
    response = client.post("/api/auth/auth0", json={"id_token": "any"})
    assert response.status_code == 403
    assert "not verified" in response.get_json()["error"].lower()

    # No account was created or linked for the owner address.
    conn = web_app._get_db()
    assert (
        conn.execute("SELECT COUNT(*) AS c FROM users WHERE email_or_phone = 'sumitagg24@gmail.com'").fetchone()["c"]
        == 0
    )
    conn.close()


def test_idor_on_history_endpoints(app_client):
    """A second user must not read or delete the first user's transcriptions."""
    client, _ = app_client
    victim = ApiUser(client, "idor-victim@gmail.com")
    attacker = ApiUser(client, "idor-attacker@gmail.com")
    client.post("/api/history", json={"text": "victim private note"}, headers=victim.headers)

    listing = client.get("/api/history", headers=attacker.headers).get_json()
    assert all("victim private note" not in h["text"] for h in listing.get("history", []))

    conn = None
    from web import app as web_app_module

    conn = web_app_module._get_db()
    victim_item = conn.execute("SELECT id FROM transcriptions WHERE user_id = ?", (victim.user_id,)).fetchone()["id"]
    conn.close()

    response = client.delete(f"/api/history/{victim_item}", headers=attacker.headers)
    assert response.status_code == 404
    conn = web_app_module._get_db()
    assert conn.execute("SELECT COUNT(*) AS c FROM transcriptions WHERE id = ?", (victim_item,)).fetchone()["c"] == 1
    conn.close()


def test_cross_user_user_id_parameters_are_ignored(app_client):
    """user_id in query or body must never widen what a session can read."""
    client, _ = app_client
    victim = ApiUser(client, "param-victim@gmail.com")
    attacker = ApiUser(client, "param-attacker@gmail.com")
    client.post("/api/history", json={"text": "param secret"}, headers=victim.headers)

    leak = client.get("/api/history", query_string={"user_id": victim.user_id}, headers=attacker.headers)
    assert "param secret" not in leak.get_data(as_text=True)
    leak = client.get("/api/history", json={"user_id": victim.user_id, "session_id": attacker.session_id})
    assert "param secret" not in leak.get_data(as_text=True)
    leak = client.get("/api/subscription", query_string={"user_id": victim.user_id}, headers=attacker.headers)
    assert (leak.get_json() or {}).get("subscription", {}).get("tier") == "free"


# ── owner provisioning security regressions ───────────────────────────────────


def test_owner_signup_is_not_promoted_until_the_address_is_verified(app_client):
    """The owner email arrives by password signup: no owner rights yet.

    A password signup claims an address it has not proven control of, so the
    account must stay a normal free user until the emailed verification link
    is consumed. Only then may the promotion pass confer owner privileges.
    """
    client, web_app = app_client
    owner_email = "sumitagg24@gmail.com"
    response = signup(client, owner_email)
    assert response.status_code == 201
    user_id = response.get_json()["user_id"]

    me = client.get("/api/me", headers={"X-Session-Id": response.get_json()["session_id"]}).get_json()["user"]
    assert me["is_owner"] is False
    assert me["tier"] == "free" and me["role"] == "user"
    assert me["entitlements"]["unlimited"] is False

    conn = web_app._get_db()
    row = conn.execute("SELECT tier, role, is_owner FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    assert (row["tier"], row["role"], bool(row["is_owner"])) == ("free", "user", False)


def test_verified_owner_address_is_promoted_on_next_login(app_client):
    """Once the owner address is verified, trusted promotion resumes."""
    client, web_app = app_client
    owner_email = "sumitagg24@gmail.com"
    response = signup(client, owner_email)
    assert response.status_code == 201

    conn = web_app._get_db()
    conn.execute("UPDATE users SET email_verified = 1 WHERE email_or_phone = ?", (owner_email,))
    conn.commit()
    conn.close()

    login_response = login(client, owner_email)
    assert login_response.status_code == 200
    payload = login_response.get_json()
    assert payload["is_owner"] is True
    assert payload["tier"] == "owner" and payload["role"] == "owner"

    me = client.get("/api/me", headers={"X-Session-Id": payload["session_id"]}).get_json()["user"]
    assert me["entitlements"]["unlimited"] is True
    assert me["entitlements"]["monthly_transcriptions_limit"] == -1


def test_unverified_owner_claim_gets_no_owner_privileges_via_any_surface(app_client):
    """End-to-end: an unverified owner-email account cannot use owner powers."""
    client, web_app = app_client
    owner_email = "sumitagg24@gmail.com"
    response = signup(client, owner_email)
    session_id = response.get_json()["session_id"]
    headers = {"X-Session-Id": session_id}

    # Admin surface must stay closed.
    assert client.get("/api/admin/users", headers=headers).status_code == 403
    # Quota behaviour must stay free-tier (100), not unlimited.
    conn = web_app._get_db()
    user_id = conn.execute("SELECT id FROM users WHERE email_or_phone = ?", (owner_email,)).fetchone()["id"]
    conn.executemany(
        "INSERT INTO transcriptions (user_id, text, created_at) VALUES (?, ?, datetime('now'))",
        [(user_id, f"entry {i}") for i in range(100)],
    )
    conn.commit()
    conn.close()
    quota = web_app.check_transcription_quota(user_id)
    assert quota == (False, 100, 100), quota

    # A second account must not be able to pull the unverified claim up either.
    other = ApiUser(client, "helper@gmail.com")
    assert client.post("/api/subscription/upgrade", json={"tier": "owner"}, headers=other.headers).status_code == 403

    conn = web_app._get_db()
    row = conn.execute("SELECT tier, is_owner FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    assert row["tier"] == "free" and not row["is_owner"]
