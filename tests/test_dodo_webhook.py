"""Dodo Payments webhook: signature verification, tier mapping, idempotency."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid

from tests.conftest import ApiUser

KEY = b"dodo-test-signing-key-0123456789"
SECRET = "whsec_" + base64.b64encode(KEY).decode("ascii")


def _configure(monkeypatch):
    monkeypatch.setenv("DODO_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("DODO_CHECKOUT_URL_PRO", "https://checkout.example/pro")
    monkeypatch.setenv("DODO_CHECKOUT_URL_BUSINESS", "https://checkout.example/biz")


def _deliver(client, payload: dict, key: bytes = KEY, webhook_id: str | None = None, age: int = 0):
    """POST a Dodo delivery with a correctly computed Standard-Webhooks signature."""
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    wid = webhook_id or f"msg_{uuid.uuid4().hex}"
    stamp = str(int(time.time()) - age)
    digest = hmac.new(key, f"{wid}.{stamp}.{raw.decode('utf-8')}".encode("utf-8"), hashlib.sha256).digest()
    headers = {
        "webhook-id": wid,
        "webhook-timestamp": stamp,
        "webhook-signature": f"v1,{base64.b64encode(digest).decode('ascii')}",
    }
    return client.post("/api/webhooks/dodo", data=raw, content_type="application/json", headers=headers), wid


def _tier(web_app, user_id: int) -> str:
    conn = web_app._get_db()
    row = conn.execute("SELECT tier FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return row["tier"]


def _audit_count(web_app, user_id: int) -> int:
    conn = web_app._get_db()
    try:
        count = conn.execute("SELECT COUNT(*) AS c FROM tier_audit WHERE user_id = ?", (user_id,)).fetchone()["c"]
    except Exception:
        count = 0
    conn.close()
    return count


def test_unconfigured_webhook_is_503_and_checkout_hidden(app_client):
    client, _ = app_client
    response, _ = _deliver(client, {"type": "payment.succeeded", "data": {}})
    assert response.status_code == 503
    assert response.get_json()["code"] == "payments_not_configured"

    summary = client.get("/api/subscription").get_json()["subscription"]
    assert summary["checkout_available"] is False
    assert summary["can_self_upgrade"] is False


def test_bad_signature_is_rejected(app_client, monkeypatch):
    client, _ = app_client
    _configure(monkeypatch)

    forged, _ = _deliver(client, {"type": "payment.succeeded", "data": {}}, key=b"wrong-key-00000000000000000000")
    assert forged.status_code == 400
    assert forged.get_json()["code"] == "invalid_signature"

    stale, _ = _deliver(client, {"type": "payment.succeeded", "data": {}}, age=601)
    assert stale.status_code == 400

    bare = client.post("/api/webhooks/dodo", json={"type": "payment.succeeded"})
    assert bare.status_code == 400


def test_multi_signature_header_accepts_rotation(app_client, monkeypatch):
    client, _ = app_client
    _configure(monkeypatch)

    payload = {"type": "payment.failed", "data": {}}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    wid = f"msg_{uuid.uuid4().hex}"
    stamp = str(int(time.time()))
    good = base64.b64encode(hmac.new(KEY, f"{wid}.{stamp}.{raw.decode()}".encode(), hashlib.sha256).digest()).decode()
    response = client.post(
        "/api/webhooks/dodo",
        data=raw,
        content_type="application/json",
        headers={
            "webhook-id": wid,
            "webhook-timestamp": stamp,
            "webhook-signature": f"v1,{base64.b64encode(b'0' * 32).decode()} v1,{good}",
        },
    )
    assert response.status_code == 200
    assert response.get_json()["acked"] is True


def test_valid_payment_grants_tier_per_plan(app_client, monkeypatch):
    client, web_app = app_client
    _configure(monkeypatch)
    user = ApiUser(client, "buyer@gmail.com")

    response, _ = _deliver(
        client,
        {
            "type": "payment.succeeded",
            "data": {"customer": {"email": "buyer@gmail.com"}, "product_name": "Voxylis Pro Monthly"},
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["acked"] is True and body["applied"] is True and body["tier"] == "pro"
    assert _tier(web_app, user.user_id) == "pro"
    assert _audit_count(web_app, user.user_id) == 1


def test_business_product_grants_business(app_client, monkeypatch):
    client, web_app = app_client
    _configure(monkeypatch)
    user = ApiUser(client, "team@gmail.com")

    response, _ = _deliver(
        client,
        {
            "type": "subscription.active",
            "data": {"metadata": {"user_id": user.user_id}, "product_id": "Voxylis Business Monthly"},
        },
    )
    assert response.get_json()["tier"] == "business"
    assert _tier(web_app, user.user_id) == "business"


def test_replay_is_acknowledged_without_reapplying(app_client, monkeypatch):
    client, web_app = app_client
    _configure(monkeypatch)
    user = ApiUser(client, "replay@gmail.com")
    payload = {
        "type": "payment.succeeded",
        "data": {"customer": {"email": "replay@gmail.com"}, "plan": "pro"},
    }

    first, wid = _deliver(client, payload)
    assert first.get_json()["applied"] is True
    audits = _audit_count(web_app, user.user_id)

    second, _ = _deliver(client, payload, webhook_id=wid)
    assert second.status_code == 200
    assert second.get_json()["duplicate"] is True
    assert _audit_count(web_app, user.user_id) == audits
    assert _tier(web_app, user.user_id) == "pro"


def test_cancelled_subscription_returns_account_to_free(app_client, monkeypatch):
    client, web_app = app_client
    _configure(monkeypatch)
    user = ApiUser(client, "churn@gmail.com")
    _deliver(client, {"type": "payment.succeeded", "data": {"customer": {"email": "churn@gmail.com"}}})
    assert _tier(web_app, user.user_id) == "pro"

    response, _ = _deliver(
        client, {"type": "subscription.cancelled", "data": {"customer": {"email": "churn@gmail.com"}}}
    )
    assert response.status_code == 200
    assert response.get_json()["applied"] is True
    assert _tier(web_app, user.user_id) == "free"


def test_unknown_customer_is_acknowledged_without_change(app_client, monkeypatch):
    client, _ = app_client
    _configure(monkeypatch)

    response, _ = _deliver(client, {"type": "payment.succeeded", "data": {"customer": {"email": "ghost@example.com"}}})
    assert response.status_code == 200
    body = response.get_json()
    assert body["acked"] is True and body["applied"] is False


def test_subscription_reports_checkout_urls_when_configured(app_client, monkeypatch):
    client, _ = app_client
    _configure(monkeypatch)

    summary = client.get("/api/subscription").get_json()["subscription"]
    assert summary["checkout_available"] is True
    assert summary["checkout_urls"] == {
        "pro": "https://checkout.example/pro",
        "business": "https://checkout.example/biz",
    }
