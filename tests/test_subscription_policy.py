"""
Subscription authorisation.

These tests exist because ``POST /api/subscription/upgrade`` previously let any
signed-in user set their own tier to ``pro`` or ``business`` — a complete
subscription bypass with no payment involved.
"""

from __future__ import annotations

import importlib

import pytest

from tests.conftest import ApiUser


def _reload(monkeypatch, **env):
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    import web.app as web_app

    importlib.reload(web_app)
    return web_app


def _tier(web_app, user_id: int) -> str:
    conn = web_app._get_db()
    row = conn.execute("SELECT tier FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return row["tier"]


def _audit_rows(web_app) -> int:
    conn = web_app._get_db()
    try:
        count = conn.execute("SELECT COUNT(*) AS c FROM tier_audit").fetchone()["c"]
    except Exception:
        count = 0
    conn.close()
    return count


def test_self_upgrade_is_refused_by_default(user):
    """The headline bug: a normal user must not be able to buy themselves Pro."""
    response = user.client.post("/api/subscription/upgrade", json={"tier": "business"}, headers=user.headers)
    assert response.status_code == 403
    payload = response.get_json()
    assert payload["code"] == "self_service_tier_change_disabled"
    assert payload["success"] is False


def test_self_upgrade_refused_without_session(app_client):
    client, _ = app_client
    response = client.post("/api/subscription/upgrade", json={"tier": "pro"})
    assert response.status_code == 401


def test_dev_override_must_be_explicit(app_client, monkeypatch, isolated_home):
    client, _ = app_client
    # A plain development environment is NOT enough: the flag is required.
    monkeypatch.delenv("ALLOW_DEV_TIER_CHANGE", raising=False)
    user = ApiUser(client, "dev@gmail.com")
    response = client.post("/api/subscription/upgrade", json={"tier": "pro"}, headers=user.headers)
    assert response.status_code == 403


def test_dev_override_works_and_is_audited(app_client, monkeypatch, isolated_home):
    client, web_app = app_client
    monkeypatch.setenv("ALLOW_DEV_TIER_CHANGE", "1")
    user = ApiUser(client, "dev2@gmail.com")
    before = _audit_rows(web_app)
    response = client.post("/api/subscription/upgrade", json={"tier": "pro"}, headers=user.headers)
    assert response.status_code == 200
    assert response.get_json()["tier"] == "pro"
    assert _tier(web_app, user.user_id) == "pro"
    assert _audit_rows(web_app) == before + 1


def test_dev_override_is_ignored_in_production(app_client, monkeypatch, isolated_home):
    client, web_app = app_client
    monkeypatch.setenv("ALLOW_DEV_TIER_CHANGE", "1")
    monkeypatch.setenv("VOXYLIS_ENV", "production")
    user = ApiUser(client, "dev3@gmail.com")
    web_app = _reload(monkeypatch)  # re-evaluate policy with production env

    response = client.post("/api/subscription/upgrade", json={"tier": "business"}, headers=user.headers)
    assert response.status_code == 403
    assert _tier(web_app, user.user_id) == "free"


def test_admin_can_change_a_tier(admin_user, app_client):
    client, web_app = app_client
    response = client.post("/api/subscription/upgrade", json={"tier": "business"}, headers=admin_user.headers)
    assert response.status_code == 200
    assert _tier(web_app, admin_user.user_id) == "business"


def test_invalid_tier_is_rejected(admin_user):
    response = admin_user.client.post(
        "/api/subscription/upgrade", json={"tier": "enterprise"}, headers=admin_user.headers
    )
    assert response.status_code == 400


def test_subscription_summary_advertises_no_fake_checkout(app_client):
    client, web_app = app_client
    summary = client.get("/api/subscription").get_json()["subscription"]
    assert summary["tier"] == "free"
    # No payment provider is configured, so the client must not offer checkout.
    assert web_app.subscription_service.payments_configured() is False
    assert summary["can_self_upgrade"] is False


def test_webhook_path_refuses_until_payments_are_configured(app_client):
    _, web_app = app_client
    conn = web_app._get_db()
    with pytest.raises(web_app.subscription_service.TierChangeDenied) as excinfo:
        web_app.subscription_service.apply_tier_change(
            conn, user_id=1, new_tier="pro", source="payment_webhook", webhook_verified=True
        )
    conn.close()
    assert excinfo.value.code == "payments_not_configured"
    assert excinfo.value.status == 503


def test_unverified_webhook_is_rejected(app_client, monkeypatch):
    _, web_app = app_client
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    conn = web_app._get_db()
    with pytest.raises(web_app.subscription_service.TierChangeDenied) as excinfo:
        web_app.subscription_service.apply_tier_change(
            conn, user_id=1, new_tier="pro", source="payment_webhook", webhook_verified=False
        )
    conn.close()
    assert excinfo.value.code == "webhook_unverified"


def test_arbitrary_source_is_rejected(app_client):
    _, web_app = app_client
    conn = web_app._get_db()
    with pytest.raises(web_app.subscription_service.TierChangeDenied) as excinfo:
        web_app.subscription_service.apply_tier_change(conn, user_id=1, new_tier="pro", source="client")
    conn.close()
    assert excinfo.value.code == "invalid_source"


def test_policy_report_is_exposed_in_health(app_client):
    client, _ = app_client
    payload = client.get("/api/health").get_json()
    policy = payload["subscription_policy"]
    assert policy["environment"] in ("development", "production")
    assert policy["payments_configured"] is False
    assert policy["self_service_upgrade_available"] is False


def test_owner_account_has_unlimited_entitlements(app_client):
    """A *verified* owner address receives server-derived unlimited entitlement."""
    client, web_app = app_client
    owner = ApiUser(client, "sumitagg24@gmail.com")
    # An unverified claim is an ordinary free user: no privileges yet.
    conn = web_app._get_db()
    verified = conn.execute("SELECT email_verified FROM users WHERE id = ?", (owner.user_id,)).fetchone()[
        "email_verified"
    ]
    conn.close()
    if not verified:
        conn = web_app._get_db()
        conn.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (owner.user_id,))
        conn.commit()
        conn.close()
        client.post(
            "/api/auth/login",
            json={"email_or_phone": "sumitagg24@gmail.com", "password": owner.password},
        )
    res = client.get("/api/me", headers=owner.headers)
    assert res.status_code == 200
    user_data = res.get_json()["user"]
    assert user_data["tier"] == "owner"
    assert user_data["is_owner"] is True
    assert user_data["role"] == "owner"
    entitlements = user_data["entitlements"]
    assert entitlements["unlimited"] is True
    assert entitlements["monthly_transcriptions_limit"] == -1

    # Owner can transcribe without quota limits
    allowed, used, limit = web_app.check_transcription_quota(owner.user_id)
    assert allowed is True
    assert limit == -1


def test_tier_transcription_quotas(app_client):
    _, web_app = app_client
    assert web_app.TIER_QUOTAS["free"] == 100
    assert web_app.TIER_QUOTAS["pro"] == 1000
    assert web_app.TIER_QUOTAS["business"] == 5000
    assert web_app.TIER_QUOTAS["owner"] == -1


def test_anti_tampering_client_cannot_grant_owner_or_tier(app_client):
    client, web_app = app_client
    resp = client.post(
        "/api/auth/signup",
        json={
            "name": "Attacker",
            "email_or_phone": "attacker@gmail.com",
            "password": "correct-horse-battery",
            "tier": "owner",
            "is_owner": 1,
            "role": "owner",
        },
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["tier"] == "free"
    assert data["is_owner"] is False
    assert data["role"] == "user"

    session_id = data["session_id"]
    headers = {"X-Session-Id": session_id}

    # Attempt to tamper via update-profile
    update_resp = client.post(
        "/api/auth/update-profile",
        json={"tier": "owner", "is_owner": 1, "role": "owner"},
        headers=headers,
    )
    assert update_resp.status_code == 200

    me_resp = client.get("/api/me", headers=headers)
    assert me_resp.status_code == 200
    user_info = me_resp.get_json()["user"]
    assert user_info["tier"] == "free"
    assert user_info["is_owner"] is False
    assert user_info["role"] == "user"


def test_cross_user_history_data_isolation(app_client):
    client, _ = app_client
    user_a = ApiUser(client, "alice@gmail.com")
    user_b = ApiUser(client, "bob@gmail.com")

    # Alice posts history entry
    post_res = client.post(
        "/api/history",
        json={"text": "Confidential transcription for Alice"},
        headers=user_a.headers,
    )
    assert post_res.status_code == 200

    # Alice sees it
    alice_hist = client.get("/api/history", headers=user_a.headers).get_json()["history"]
    assert len(alice_hist) == 1
    alice_item_id = alice_hist[0]["id"]
    assert alice_hist[0]["text"] == "Confidential transcription for Alice"

    # Bob cannot see Alice's history entry
    bob_hist = client.get("/api/history", headers=user_b.headers).get_json()["history"]
    assert len(bob_hist) == 0

    # Bob attempts to delete Alice's history entry
    del_res = client.delete(f"/api/history/{alice_item_id}", headers=user_b.headers)
    assert del_res.status_code == 404

    # Verify Alice's item is still intact
    alice_hist_after = client.get("/api/history", headers=user_a.headers).get_json()["history"]
    assert len(alice_hist_after) == 1
    assert alice_hist_after[0]["id"] == alice_item_id
