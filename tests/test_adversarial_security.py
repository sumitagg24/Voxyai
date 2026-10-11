"""P6.7 adversarial security pass: regressions for the holes a hostile
reviewer would poke at — type confusion, QR session theft, token oracles,
spoofed proxy headers, and webhook tampering.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid

from tests.conftest import ApiUser, signup

# ── JSON type confusion: no endpoint may 500 on a non-object body ─────────────

_BODIES = [
    b"[1, 2, 3]",
    b'"just a string"',
    b"12345",
    b"true",
    b"null",
]


def test_type_confused_bodies_never_500_on_public_endpoints(app_client):
    client, _ = app_client
    endpoints = [
        "/api/auth/signup",
        "/api/auth/login",
        "/api/auth/auth0",
        "/api/auth/qr/start",
        "/api/auth/verify",
        "/api/auth/logout",
        "/api/auth/forgot-password",
        "/api/auth/reset-password",
        "/api/auth/confirm-email",
        "/api/contact",
        "/api/newsletter",
        "/api/download/track",
        "/api/subscription/upgrade",
        "/unsubscribe",
    ]
    for path in endpoints:
        for body in _BODIES:
            response = client.post(path, data=body, content_type="application/json")
            assert response.status_code < 500, (path, body, response.status_code)


def test_type_confused_bodies_never_500_on_authenticated_endpoints(app_client):
    client, _ = app_client
    user = ApiUser(client, "typeconfuse-adversarial@gmail.com")
    endpoints = [
        "/api/settings",
        "/api/hotkeys",
        "/api/onboarding",
        "/api/history",
        "/api/qa",
        "/api/enhance",
        "/api/auth/update-profile",
        "/api/auth/qr/approve",
        "/api/auth/verify-email",
        "/api/account/delete",
    ]
    for path in endpoints:
        for body in _BODIES:
            response = client.post(path, data=body, content_type="application/json", headers=user.headers)
            assert response.status_code < 500, (path, body, response.status_code)


def test_session_lookup_survives_non_object_json_body(app_client):
    """The X-Session-Id-less path parses the body; a non-dict must not 500.
    (The authed endpoints above send the session via header; this one forces
    the body-parsing branch of _extract_session.)"""
    client, _ = app_client
    for body in _BODIES:
        response = client.post("/api/settings", data=body, content_type="application/json")
        assert response.status_code in (400, 401), (body, response.status_code)


# ── QR sign-in: the code alone must not be enough to steal the session ───────


def _start_qr(client, device_name="adversary test rig"):
    started = client.post("/api/auth/qr/start", json={"device_name": device_name}).get_json()
    assert started["success"] is True
    return started


def test_qr_status_without_device_token_is_refused(app_client):
    """Seeing the QR (and its 6-char code) must not let you claim a session."""
    client, web_app = app_client
    user = ApiUser(client, "qr-victim@gmail.com")
    started = _start_qr(client)
    code = started["code"]

    assert client.post("/api/auth/qr/approve", json={"code": code}, headers=user.headers).status_code == 200

    missing = client.get(f"/api/auth/qr/status?code={code}")
    assert missing.status_code == 403
    wrong = client.get(f"/api/auth/qr/status?code={code}&device_token=not-the-token")
    assert wrong.status_code == 403
    via_header = client.get(f"/api/auth/qr/status?code={code}", headers={"X-QR-Device-Token": "nope"})
    assert via_header.status_code == 403

    right = client.get(f"/api/auth/qr/status?code={code}&device_token={started['device_token']}")
    assert right.status_code == 200
    assert right.get_json()["status"] == "approved"

    # The stolen-session count: exactly one session for the approving account
    # beyond its own login.
    conn = web_app._get_db()
    count = conn.execute("SELECT COUNT(*) AS c FROM sessions WHERE user_id = ?", (user.user_id,)).fetchone()["c"]
    conn.close()
    assert count == 2


def test_qr_second_approve_does_not_expire_the_ticket(app_client):
    """Regression: approving an already-approved ticket used to flip it to
    'expired', destroying the desktop's pending login."""
    client, web_app = app_client
    user = ApiUser(client, "qr-double-approve@gmail.com")
    started = _start_qr(client)
    code = started["code"]

    first = client.post("/api/auth/qr/approve", json={"code": code}, headers=user.headers)
    assert first.status_code == 200
    second = client.post("/api/auth/qr/approve", json={"code": code}, headers=user.headers)
    assert second.status_code == 200
    assert "already approved" in second.get_json()["message"].lower()

    status = client.get(f"/api/auth/qr/status?code={code}&device_token={started['device_token']}")
    payload = status.get_json()
    assert payload["status"] == "approved"
    assert payload["session_id"], "the ticket must still mint a session"


def test_qr_expired_ticket_cannot_be_approved(app_client):
    client, web_app = app_client
    user = ApiUser(client, "qr-expired@gmail.com")
    started = _start_qr(client)
    code = started["code"]

    conn = web_app._get_db()
    conn.execute("UPDATE qr_tickets SET expires_at = datetime('now', '-1 minute') WHERE code = ?", (code,))
    conn.commit()
    conn.close()

    assert client.post("/api/auth/qr/approve", json={"code": code}, headers=user.headers).status_code == 410


# ── Token oracles: identical error for unknown, used and expired tokens ───────


def _reset_token_row(web_app, user_id: int, expires_sql: str) -> str:
    import secrets as _secrets

    token = _secrets.token_urlsafe(32)
    conn = web_app._get_db()
    conn.execute(
        f"INSERT INTO password_resets (user_id, token, expires_at) VALUES (?, ?, datetime('now', '{expires_sql}'))",
        (user_id, token),
    )
    conn.commit()
    conn.close()
    return token


def test_reset_password_errors_do_not_reveal_token_state(app_client):
    client, web_app = app_client
    user = ApiUser(client, "oracle-reset@gmail.com")

    expired = _reset_token_row(web_app, user.user_id, "-1 minute")
    unknown = client.post(
        "/api/auth/reset-password",
        json={"token": "never-issued-token", "password": "correct-horse-battery"},
    ).get_json()
    expired_response = client.post(
        "/api/auth/reset-password",
        json={"token": expired, "password": "correct-horse-battery"},
    ).get_json()
    assert unknown == expired_response, "unknown and expired tokens must be indistinguishable"

    # A used token answers the same way (single-use claim after a success).
    fresh = _reset_token_row(web_app, user.user_id, "+1 hour")
    ok = client.post("/api/auth/reset-password", json={"token": fresh, "password": "correct-horse-battery"})
    assert ok.status_code == 200
    replay = client.post(
        "/api/auth/reset-password",
        json={"token": fresh, "password": "correct-horse-battery"},
    )
    assert replay.status_code == 400
    assert replay.get_json() == unknown, "a used token must look exactly like an unknown one"


def test_confirm_email_errors_do_not_reveal_token_state(app_client):
    client, web_app = app_client
    user = ApiUser(client, "oracle-confirm@gmail.com")

    conn = web_app._get_db()
    expired = "expired-" + uuid.uuid4().hex
    used = "used-" + uuid.uuid4().hex
    conn.execute(
        "INSERT INTO email_verifications (user_id, token, expires_at) " "VALUES (?, ?, datetime('now', '-1 minute'))",
        (user.user_id, expired),
    )
    conn.execute(
        "INSERT INTO email_verifications (user_id, token, used, expires_at) "
        "VALUES (?, ?, 1, datetime('now', '+1 hour'))",
        (user.user_id, used),
    )
    conn.commit()
    conn.close()

    unknown = client.post("/api/auth/confirm-email", json={"token": "nope"}).get_json()
    expired_response = client.post("/api/auth/confirm-email", json={"token": expired}).get_json()
    used_response = client.post("/api/auth/confirm-email", json={"token": used}).get_json()
    assert unknown == expired_response == used_response


def test_confirm_email_token_is_single_use_under_concurrency(app_client):
    """Two simultaneous confirmations of one token: exactly one may win."""
    import threading

    client, web_app = app_client
    user = ApiUser(client, "confirm-race@gmail.com")
    token = "race-" + uuid.uuid4().hex
    conn = web_app._get_db()
    conn.execute(
        "INSERT INTO email_verifications (user_id, token, expires_at) " "VALUES (?, ?, datetime('now', '+1 hour'))",
        (user.user_id, token),
    )
    conn.commit()
    conn.close()

    outcomes = []

    def confirm():
        c = web_app.app.test_client()
        r = c.post("/api/auth/confirm-email", json={"token": token})
        outcomes.append(r.status_code)

    threads = [threading.Thread(target=confirm) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    assert sorted(outcomes) == [200, 400, 400, 400], outcomes


# ── Proxy headers: without TRUST_PROXY, X-Forwarded-For must be ignored ─────


def test_spoofed_forwarded_for_does_not_bypass_rate_limits(app_client):
    """Without TRUST_PROXY the limiter keys on the socket address, so a
    client cycling fake X-Forwarded-For values still gets throttled."""
    client, _ = app_client
    signup(client, "xff-target@gmail.com")
    seen_429 = False
    for i in range(16):
        response = client.post(
            "/api/auth/login",
            json={"email_or_phone": "xff-target@gmail.com", "password": "wrong-password"},
            headers={"X-Forwarded-For": f"203.0.113.{i}"},
        )
        if response.status_code == 429:
            seen_429 = True
            break
    assert seen_429, "spoofed X-Forwarded-For must not widen the rate-limit bucket"


def test_trust_proxy_defaults_off(app_client):
    _, web_app = app_client
    from werkzeug.middleware.proxy_fix import ProxyFix

    assert web_app.trust_proxy() is False
    assert not isinstance(web_app.app.wsgi_app, ProxyFix), "ProxyFix must not wrap the app unless TRUST_PROXY is set"


# ── Dodo webhook: tampering and replay ───────────────────────────────────────

KEY = b"dodo-adversarial-signing-key-01"
SECRET = "whsec_" + base64.b64encode(KEY).decode("ascii")


def _signed_headers(raw: bytes, key: bytes = KEY, age: int = 0) -> dict:
    wid = f"msg_{uuid.uuid4().hex}"
    stamp = str(int(time.time()) - age)
    digest = hmac.new(key, f"{wid}.{stamp}.{raw.decode('utf-8')}".encode("utf-8"), hashlib.sha256).digest()
    return {
        "webhook-id": wid,
        "webhook-timestamp": stamp,
        "webhook-signature": f"v1,{base64.b64encode(digest).decode('ascii')}",
    }


def _configure_dodo(monkeypatch):
    monkeypatch.setenv("DODO_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("DODO_CHECKOUT_URL_PRO", "https://checkout.example/pro")
    monkeypatch.setenv("DODO_CHECKOUT_URL_BUSINESS", "https://checkout.example/biz")


def test_webhook_tampered_body_fails_signature(app_client, monkeypatch):
    """A captured signature is worthless against a modified body: the
    signature covers the raw bytes, so changing the payload breaks it."""
    client, _ = app_client
    _configure_dodo(monkeypatch)
    ApiUser(client, "dodo-tamper@gmail.com")

    raw = json.dumps({"type": "payment.succeeded", "data": {}}).encode()
    headers = _signed_headers(raw)
    tampered = json.dumps({"type": "payment.succeeded", "data": {"metadata": {"user_id": 1}}}).encode()
    response = client.post("/api/webhooks/dodo", data=tampered, content_type="application/json", headers=headers)
    assert response.status_code == 400
    assert response.get_json()["code"] == "invalid_signature"


def test_webhook_replayed_after_window_is_rejected(app_client, monkeypatch):
    client, _ = app_client
    _configure_dodo(monkeypatch)
    raw = json.dumps({"type": "payment.succeeded", "data": {}}).encode()
    headers = _signed_headers(raw, age=3600)
    response = client.post("/api/webhooks/dodo", data=raw, content_type="application/json", headers=headers)
    assert response.status_code == 400
    assert response.get_json()["code"] == "invalid_signature"


def test_webhook_wrong_scheme_prefix_is_rejected(app_client, monkeypatch):
    client, _ = app_client
    _configure_dodo(monkeypatch)
    raw = json.dumps({"type": "payment.succeeded", "data": {}}).encode()
    wid = f"msg_{uuid.uuid4().hex}"
    stamp = str(int(time.time()))
    digest = hmac.new(KEY, f"{wid}.{stamp}.{raw.decode('utf-8')}".encode("utf-8"), hashlib.sha256).digest()
    for bogus in (
        f"v2,{base64.b64encode(digest).decode('ascii')}",  # wrong scheme
        f"v1,{base64.b64encode(digest[::-1]).decode('ascii')}",  # wrong digest
        "v1,",  # empty candidate
        "noscheme",
    ):
        response = client.post(
            "/api/webhooks/dodo",
            data=raw,
            content_type="application/json",
            headers={
                "webhook-id": wid,
                "webhook-timestamp": stamp,
                "webhook-signature": bogus,
            },
        )
        assert response.status_code == 400, bogus


# ── Admin surface ───────────────────────────────────────────────────────────


def test_admin_users_listing_is_gated(app_client):
    client, _ = app_client
    assert client.get("/api/admin/users").status_code == 401
    pleb = ApiUser(client, "not-admin-adversarial@gmail.com")
    assert client.get("/api/admin/users", headers=pleb.headers).status_code == 403


# ── History delete stays owner-scoped ───────────────────────────────────────


def test_history_delete_of_missing_id_is_404(app_client):
    client, _ = app_client
    user = ApiUser(client, "history-404@gmail.com")
    assert client.delete("/api/history/999999", headers=user.headers).status_code == 404
    # A non-integer id must not crash the router into a 500.
    assert client.delete("/api/history/abc", headers=user.headers).status_code == 404
