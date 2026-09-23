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
    remaining = conn.execute(
        "SELECT COUNT(*) AS c FROM sessions WHERE id = ?", (user.session_id,)
    ).fetchone()["c"]
    conn.close()
    assert remaining == 0


def test_session_rotates_after_a_day(app_client):
    client, web_app = app_client
    user = ApiUser(client, "rotate@gmail.com")
    conn = web_app._get_db()
    conn.execute(
        "UPDATE sessions SET created_at = '2020-01-01 00:00:00' WHERE id = ?", (user.session_id,)
    )
    conn.commit()
    conn.close()

    # A stale session must still authenticate, but issue a new identifier.
    response = client.post("/api/auth/verify", json={"session_id": user.session_id})
    assert response.get_json()["valid"] is True
    conn = web_app._get_db()
    old = conn.execute(
        "SELECT COUNT(*) AS c FROM sessions WHERE id = ?", (user.session_id,)
    ).fetchone()["c"]
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
    response = client.post(
        "/api/enhance", json={"text": "hello world", "mode": "creative"}, headers=user.headers
    )
    assert response.status_code == 403
    assert response.get_json()["current_tier"] == "free"


def test_free_tier_quota_is_enforced(app_client):
    client, web_app = app_client
    user = ApiUser(client, "quota@gmail.com")
    conn = web_app._get_db()
    for _ in range(web_app.FREE_MONTHLY_TRANSCRIPTIONS):
        conn.execute(
            "INSERT INTO transcriptions (user_id, text) VALUES (?, ?)", (user.user_id, "x")
        )
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
    client, _ = app_client
    body = client.get("/definitely-not-a-route").get_json()
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
    statuses = [
        signup(client, f"flood{i}@gmail.com").status_code for i in range(15)
    ]
    assert 429 in statuses, "signup should be rate limited"
