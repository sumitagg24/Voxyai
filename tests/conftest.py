"""
Shared test fixtures.

Every test runs against a throwaway user-data root and a throwaway database, so
running the suite can never touch a developer's real Voxylis settings, history
or credentials.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Point every user-data path at a temporary directory."""
    home = tmp_path / "voxylis-home"
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("VOXYLIS_HOME", str(home))
    yield home


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    """A Flask test client backed by a fresh SQLite database."""
    monkeypatch.setenv("VOXYLIS_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.delenv("VOXYLIS_ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.delenv("ALLOW_DEV_TIER_CHANGE", raising=False)
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-that-is-long-enough-0001")

    import web.app as web_app

    importlib.reload(web_app)
    web_app.app.config.update(TESTING=True)
    with web_app.app.test_client() as client:
        yield client, web_app
    importlib.reload(web_app)


def signup(client, identifier: str, password: str = "correct-horse-battery", name: str = "Test User"):
    """Create an account and return the parsed response."""
    return client.post(
        "/api/auth/signup",
        json={"name": name, "email_or_phone": identifier, "password": password},
    )


def login(client, identifier: str, password: str = "correct-horse-battery"):
    return client.post("/api/auth/login", json={"email_or_phone": identifier, "password": password})


class ApiUser:
    """A signed-in test user with a session id."""

    def __init__(self, client, identifier: str, password: str = "correct-horse-battery"):
        self.client = client
        self.identifier = identifier
        self.password = password
        response = signup(client, identifier, password)
        payload = response.get_json() or {}
        self.session_id = payload.get("session_id") or ""
        if not self.session_id:
            payload = login(client, identifier, password).get_json() or {}
            self.session_id = payload.get("session_id", "")
        self.user_id = payload.get("user_id")

    @property
    def headers(self) -> dict:
        return {"X-Session-Id": self.session_id}


@pytest.fixture
def user(app_client):
    client, _ = app_client
    return ApiUser(client, "tester@gmail.com")


@pytest.fixture
def admin_user(app_client, monkeypatch):
    """An admin whose address has been verified (trusted-promotion precondition)."""
    monkeypatch.setenv("ADMIN_EMAILS", "admin@gmail.com")
    client, _ = app_client
    user = ApiUser(client, "admin@gmail.com")
    conn = __import__("web.app", fromlist=["_get_db"])._get_db()
    conn.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (user.user_id,))
    conn.commit()
    conn.close()
    # Re-login so the response metadata reflects the promoted role.
    login(client, "admin@gmail.com")
    user.session_id = client.post(
        "/api/auth/login",
        json={"email_or_phone": "admin@gmail.com", "password": user.password},
    ).get_json()["session_id"]
    return user


os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
