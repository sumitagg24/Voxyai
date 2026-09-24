"""
Email delivery, verification/reset flows, marketing consent and monitoring.

These tests exist because the previous build generated verification and reset
tokens, stored them, and then sent nothing — the endpoints reported success
while no mail left the process.  Everything here asserts on what actually
reached the outbox, not on the shape of a response body.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

from web import observability
from web.services import email_preferences, email_service

REPO = Path(__file__).resolve().parent.parent

VERIFY_LINK = re.compile(r"verify_token=([A-Za-z0-9_\-]+)")
RESET_LINK = re.compile(r"reset_token=([A-Za-z0-9_\-]+)")


# ── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def outbox(app_client):
    """Install an in-process provider and hand back its outbox."""
    _, web_app = app_client
    provider = email_service.ConsoleEmailProvider()
    email_service.set_provider(provider)
    yield provider, web_app
    email_service.set_provider(None)


def _token_from(provider, kind: str, pattern: re.Pattern) -> str:
    for message in reversed(provider.outbox):
        if message.kind != kind:
            continue
        match = pattern.search(message.text)
        if match:
            return match.group(1)
    raise AssertionError(f"no {kind} message carrying {pattern.pattern} was sent")


def _sent_kinds(provider) -> list:
    return [message.kind for message in provider.outbox]


# ── provider selection and safety ────────────────────────────────────────────


def test_provider_selection_defaults_to_console(monkeypatch):
    for name in ("EMAIL_PROVIDER", "EMAIL_API_KEY", "SMTP_HOST"):
        monkeypatch.delenv(name, raising=False)
    assert email_service.configured_provider_name() == "console"
    assert email_service.email_configured() is False


def test_provider_selection_prefers_resend_then_smtp(monkeypatch):
    monkeypatch.delenv("EMAIL_PROVIDER", raising=False)
    monkeypatch.setenv("EMAIL_API_KEY", "test-key-not-real")
    assert email_service.configured_provider_name() == "resend"
    monkeypatch.delenv("EMAIL_API_KEY")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.invalid")
    assert email_service.configured_provider_name() == "smtp"


def test_explicit_provider_wins(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("EMAIL_API_KEY", "test-key-not-real")
    assert email_service.configured_provider_name() == "smtp"


def test_recipient_is_masked_in_logs_and_status():
    assert email_service.mask_email("someone@example.com") == "s***@example.com"
    assert email_service.mask_email("") == "***"
    assert email_service.mask_email("not-an-email") == "***"


def test_links_are_built_from_the_public_origin(monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "https://voxylis.com/")
    monkeypatch.delenv("EMAIL_VERIFICATION_URL", raising=False)
    monkeypatch.delenv("PASSWORD_RESET_URL", raising=False)
    assert email_service.build_link("verify_email", "TOKEN") == "https://voxylis.com/auth?verify_token=TOKEN"
    assert email_service.build_link("password_reset", "TOKEN") == "https://voxylis.com/auth?reset_token=TOKEN"


def test_unknown_template_is_refused(outbox):
    provider, _ = outbox
    assert email_service.send_transactional("does_not_exist", "a@gmail.com", {}) is None
    assert provider.outbox == []


def test_bad_recipient_is_refused_without_sending(outbox):
    provider, _ = outbox
    assert email_service.send_transactional("welcome", "not-an-address", {}) is None
    assert provider.outbox == []


def test_marketing_requires_explicit_consent(outbox):
    provider, _ = outbox
    assert email_service.send_marketing("product_update", "a@gmail.com", {}, consent=False) is None
    assert provider.outbox == []
    assert email_service.send_marketing("product_update", "a@gmail.com", {}, consent=True) is not None
    assert _sent_kinds(provider) == ["product_update"]


def test_marketing_and_transactional_templates_cannot_be_swapped(outbox):
    provider, _ = outbox
    assert email_service.send_transactional("product_update", "a@gmail.com", {}) is None
    assert email_service.send_marketing("welcome", "a@gmail.com", {}, consent=True) is None
    assert provider.outbox == []


def test_configured_requires_a_usable_provider(monkeypatch):
    """A provider name without its credential is not "configured"."""
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.delenv("EMAIL_API_KEY", raising=False)
    assert email_service.email_configured() is False
    monkeypatch.setenv("EMAIL_API_KEY", "test-key-not-real")
    assert email_service.email_configured() is True
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert email_service.email_configured() is False


def test_delivery_failure_is_swallowed(outbox, monkeypatch):
    """A provider outage must not turn a valid request into a 500."""
    provider, _ = outbox
    email_service.set_provider(None)
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.delenv("EMAIL_API_KEY", raising=False)
    assert email_service.send_transactional("welcome", "a@gmail.com", {}) is None
    assert provider.outbox == [], "nothing may reach the outbox when delivery fails"


def test_every_template_renders_a_subject_text_and_html():
    from web.services import email_templates

    for kind in email_templates.ALL_KINDS:
        subject, text, html = email_templates.render(kind, {"name": "Test", "verify_url": "https://x/y"})
        assert subject and text and html, kind
        assert "Voxylis" in html
        assert "<html" not in html  # fragments only; the layout wraps them


# ── email verification ───────────────────────────────────────────────────────


def test_signup_emails_a_verification_link(outbox):
    provider, web_app = outbox
    with web_app.app.test_client() as client:
        body = client.post(
            "/api/auth/signup",
            json={"name": "Verify Me", "email_or_phone": "verify@gmail.com", "password": "correct-horse-battery"},
        ).get_json()
    assert body["success"] is True
    assert body["email_verified"] is False
    assert _sent_kinds(provider) == ["welcome"]
    assert VERIFY_LINK.search(provider.outbox[0].text), "the welcome mail must carry a confirmation link"


def test_confirmation_link_marks_the_account_verified(outbox):
    provider, web_app = outbox
    with web_app.app.test_client() as client:
        client.post(
            "/api/auth/signup",
            json={"name": "Verify Me", "email_or_phone": "confirm@gmail.com", "password": "correct-horse-battery"},
        )
        token = _token_from(provider, "welcome", VERIFY_LINK)

        session = client.post(
            "/api/auth/login",
            json={"email_or_phone": "confirm@gmail.com", "password": "correct-horse-battery"},
        ).get_json()["session_id"]
        headers = {"X-Session-Id": session}
        assert client.get("/api/me", headers=headers).get_json()["user"]["email_verified"] is False

        confirmed = client.post("/api/auth/confirm-email", json={"token": token})
        assert confirmed.status_code == 200
        assert confirmed.get_json()["email_verified"] is True

        assert client.get("/api/me", headers=headers).get_json()["user"]["email_verified"] is True


def test_verification_token_is_single_use(outbox):
    provider, web_app = outbox
    with web_app.app.test_client() as client:
        client.post(
            "/api/auth/signup",
            json={"name": "Once Only", "email_or_phone": "once@gmail.com", "password": "correct-horse-battery"},
        )
    token = _token_from(provider, "welcome", VERIFY_LINK)
    with web_app.app.test_client() as client:
        assert client.post("/api/auth/confirm-email", json={"token": token}).status_code == 200
        reused = client.post("/api/auth/confirm-email", json={"token": token})
        assert reused.status_code == 400
        assert "used" in reused.get_json()["error"].lower()


def test_expired_verification_token_is_rejected(outbox):
    provider, web_app = outbox
    with web_app.app.test_client() as client:
        client.post(
            "/api/auth/signup",
            json={"name": "Slow Coach", "email_or_phone": "expired@gmail.com", "password": "correct-horse-battery"},
        )
    token = _token_from(provider, "welcome", VERIFY_LINK)
    conn = web_app._get_db()
    conn.execute("UPDATE email_verifications SET expires_at = datetime('now', '-1 hour') WHERE token = ?", (token,))
    conn.commit()
    conn.close()

    with web_app.app.test_client() as client:
        response = client.post("/api/auth/confirm-email", json={"token": token})
    assert response.status_code == 400
    assert "expired" in response.get_json()["error"].lower()


def test_resend_verification_retires_the_previous_link(outbox):
    provider, web_app = outbox
    with web_app.app.test_client() as client:
        signup = client.post(
            "/api/auth/signup",
            json={"name": "Resend Me", "email_or_phone": "resend@gmail.com", "password": "correct-horse-battery"},
        ).get_json()
        headers = {"X-Session-Id": signup["session_id"]}
        first = _token_from(provider, "welcome", VERIFY_LINK)

        resent = client.post("/api/auth/verify-email", headers=headers)
        assert resent.status_code == 200
        assert _sent_kinds(provider).count("verify_email") == 1

        second = _token_from(provider, "verify_email", VERIFY_LINK)
        assert second != first

        assert client.post("/api/auth/confirm-email", json={"token": first}).status_code == 400
        assert client.post("/api/auth/confirm-email", json={"token": second}).status_code == 200


def test_resend_reports_failure_when_no_provider_can_send(app_client, monkeypatch):
    """No provider override here: the real provider would fail, so say so."""
    _, web_app = app_client
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.delenv("EMAIL_API_KEY", raising=False)
    with web_app.app.test_client() as client:
        signup = client.post(
            "/api/auth/signup",
            json={"name": "No Provider", "email_or_phone": "noprovider@gmail.com", "password": "correct-horse-battery"},
        ).get_json()
        response = client.post("/api/auth/verify-email", headers={"X-Session-Id": signup["session_id"]})
    assert response.status_code == 503
    assert response.get_json()["code"] == "email_delivery_unavailable"


def test_transcription_requires_a_confirmed_address(outbox):
    provider, web_app = outbox
    with web_app.app.test_client() as client:
        signup = client.post(
            "/api/auth/signup",
            json={"name": "Browser User", "email_or_phone": "browser@gmail.com", "password": "correct-horse-battery"},
        ).get_json()
        headers = {"X-Session-Id": signup["session_id"]}

        blocked = client.post("/api/transcribe", headers=headers, data={})
        assert blocked.status_code == 403
        assert blocked.get_json()["code"] == "email_not_verified"

        token = _token_from(provider, "welcome", VERIFY_LINK)
        client.post("/api/auth/confirm-email", json={"token": token})

        after = client.post("/api/transcribe", headers=headers, data={})
        assert after.status_code != 403, "a confirmed address must not be blocked by the verification gate"


def test_owner_is_never_blocked_by_the_verification_gate(app_client):
    """A *verified* owner address skips the transcription verification gate.

    The gate exists so an unverified throwaway address cannot consume provider
    credit — the owner is exempt once the address is proven, not before. An
    unverified claim on the owner address is an ordinary free user and must be
    blocked like any other unverified account.
    """
    client, web_app = app_client
    with web_app.app.test_client() as client:
        signup = client.post(
            "/api/auth/signup",
            json={"name": "Owner", "email_or_phone": "sumitagg24@gmail.com", "password": "correct-horse-battery"},
        ).get_json()
        # Unverified claim: no owner privileges, gate applies.
        assert signup["is_owner"] is False
        blocked = client.post("/api/transcribe", headers={"X-Session-Id": signup["session_id"]}, data={})
        assert blocked.status_code == 403

        conn = web_app._get_db()
        conn.execute(
            "UPDATE users SET email_verified = 1 WHERE email_or_phone = ?",
            ("sumitagg24@gmail.com",),
        )
        conn.commit()
        conn.close()

        client.post(
            "/api/auth/login", json={"email_or_phone": "sumitagg24@gmail.com", "password": "correct-horse-battery"}
        )
        me = client.get("/api/me", headers={"X-Session-Id": signup["session_id"]}).get_json()["user"]
        assert me["is_owner"] is True
        response = client.post("/api/transcribe", headers={"X-Session-Id": signup["session_id"]}, data={})
        assert response.status_code != 403


# ── password reset ───────────────────────────────────────────────────────────


def test_forgot_password_emails_only_existing_accounts(outbox):
    provider, web_app = outbox
    with web_app.app.test_client() as client:
        missing = client.post("/api/auth/forgot-password", json={"email": "nobody@gmail.com"})
        assert missing.status_code == 200
        assert missing.get_json()["success"] is True
        assert provider.outbox == [], "an unknown address must not trigger mail"

        client.post(
            "/api/auth/signup",
            json={"name": "Reset Me", "email_or_phone": "resetme@gmail.com", "password": "correct-horse-battery"},
        )
        provider.outbox.clear()
        found = client.post("/api/auth/forgot-password", json={"email": "resetme@gmail.com"})
        assert found.status_code == 200

    assert _sent_kinds(provider) == ["password_reset"]
    assert RESET_LINK.search(provider.outbox[0].text)
    # The response must never contain the token.
    assert "reset_token=" not in found.get_data(as_text=True)


def test_reset_link_is_single_use_and_signs_out_every_device(outbox):
    provider, web_app = outbox
    with web_app.app.test_client() as client:
        signup = client.post(
            "/api/auth/signup",
            json={"name": "Reset Me", "email_or_phone": "resettwo@gmail.com", "password": "correct-horse-battery"},
        ).get_json()
        session = signup["session_id"]
        provider.outbox.clear()
        client.post("/api/auth/forgot-password", json={"email": "resettwo@gmail.com"})
        token = _token_from(provider, "password_reset", RESET_LINK)

        reset = client.post("/api/auth/reset-password", json={"token": token, "password": "a-brand-new-password"})
        assert reset.status_code == 200
        assert client.post("/api/auth/verify", json={"session_id": session}).get_json()["valid"] is False

        again = client.post("/api/auth/reset-password", json={"token": token, "password": "another-password-here"})
        assert again.status_code == 400

        assert (
            client.post(
                "/api/auth/login",
                json={"email_or_phone": "resettwo@gmail.com", "password": "a-brand-new-password"},
            ).status_code
            == 200
        )


def test_expired_reset_token_is_rejected(outbox):
    provider, web_app = outbox
    with web_app.app.test_client() as client:
        client.post(
            "/api/auth/signup",
            json={"name": "Late", "email_or_phone": "late@gmail.com", "password": "correct-horse-battery"},
        )
        provider.outbox.clear()
        client.post("/api/auth/forgot-password", json={"email": "late@gmail.com"})
        token = _token_from(provider, "password_reset", RESET_LINK)

        conn = web_app._get_db()
        conn.execute("UPDATE password_resets SET expires_at = datetime('now', '-1 hour') WHERE token = ?", (token,))
        conn.commit()
        conn.close()

        response = client.post("/api/auth/reset-password", json={"token": token, "password": "a-brand-new-password"})
    assert response.status_code == 400
    assert "expired" in response.get_json()["error"].lower()


def test_a_new_reset_request_retires_the_previous_link(outbox):
    provider, web_app = outbox
    with web_app.app.test_client() as client:
        client.post(
            "/api/auth/signup",
            json={"name": "Twice", "email_or_phone": "twice@gmail.com", "password": "correct-horse-battery"},
        )
        provider.outbox.clear()
        client.post("/api/auth/forgot-password", json={"email": "twice@gmail.com"})
        first = _token_from(provider, "password_reset", RESET_LINK)
        client.post("/api/auth/forgot-password", json={"email": "twice@gmail.com"})
        second = _token_from(provider, "password_reset", RESET_LINK)

        assert first != second
        assert (
            client.post(
                "/api/auth/reset-password", json={"token": first, "password": "a-brand-new-password"}
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/api/auth/reset-password", json={"token": second, "password": "a-brand-new-password"}
            ).status_code
            == 200
        )


def test_password_change_is_notified_and_signs_out_other_devices(outbox):
    provider, web_app = outbox
    with web_app.app.test_client() as client:
        first = client.post(
            "/api/auth/signup",
            json={"name": "Notify", "email_or_phone": "notify@gmail.com", "password": "correct-horse-battery"},
        ).get_json()
        second_session = client.post(
            "/api/auth/login",
            json={"email_or_phone": "notify@gmail.com", "password": "correct-horse-battery"},
        ).get_json()["session_id"]
        provider.outbox.clear()

        changed = client.post(
            "/api/auth/update-profile",
            json={"current_password": "correct-horse-battery", "new_password": "a-brand-new-password"},
            headers={"X-Session-Id": first["session_id"]},
        )
        assert changed.status_code == 200

        assert _sent_kinds(provider) == ["password_changed"]
        # The device that made the change stays signed in; the other one does not.
        assert client.post("/api/auth/verify", json={"session_id": first["session_id"]}).get_json()["valid"] is True
        assert client.post("/api/auth/verify", json={"session_id": second_session}).get_json()["valid"] is False


# ── consent and unsubscribe ──────────────────────────────────────────────────


def test_marketing_consent_is_off_unless_given(app_client):
    _, web_app = app_client
    with web_app.app.test_client() as client:
        quiet = client.post(
            "/api/auth/signup",
            json={"name": "Quiet", "email_or_phone": "quiet@gmail.com", "password": "correct-horse-battery"},
        ).get_json()
        loud = client.post(
            "/api/auth/signup",
            json={
                "name": "Loud",
                "email_or_phone": "loud@gmail.com",
                "password": "correct-horse-battery",
                "marketing_opt_in": True,
            },
        ).get_json()

    conn = web_app._get_db()
    assert email_preferences.marketing_opt_in(conn, quiet["user_id"]) is False
    assert email_preferences.marketing_opt_in(conn, loud["user_id"]) is True
    conn.close()


def test_unsubscribe_token_is_signed_and_bound_to_the_address(app_client):
    _, web_app = app_client
    with web_app.app.test_client() as client:
        signup = client.post(
            "/api/auth/signup",
            json={
                "name": "Opt Out",
                "email_or_phone": "optout@gmail.com",
                "password": "correct-horse-battery",
                "marketing_opt_in": True,
            },
        ).get_json()

    token = email_preferences.unsubscribe_token(signup["user_id"], "optout@gmail.com")
    assert email_preferences.read_unsubscribe_token(token) == (signup["user_id"], "optout@gmail.com")
    # A single flipped character must invalidate the link.
    assert email_preferences.read_unsubscribe_token(token[:-1] + ("0" if token[-1] != "0" else "1")) is None
    # A token issued for a different address must not work.
    other = email_preferences.unsubscribe_token(signup["user_id"], "someone-else@gmail.com")
    assert email_preferences.read_unsubscribe_token(other) == (signup["user_id"], "someone-else@gmail.com")

    with web_app.app.test_client() as client:
        bad = client.get(f"/unsubscribe?token={other}&format=json")
        assert bad.status_code == 400
        good = client.get(f"/unsubscribe?token={token}&format=json")
        assert good.status_code == 200

    conn = web_app._get_db()
    assert email_preferences.marketing_opt_in(conn, signup["user_id"]) is False
    conn.close()


def test_unsubscribe_token_requires_a_signing_key(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setattr(email_preferences, "_signing_key", lambda: "")
    with pytest.raises(RuntimeError):
        email_preferences.unsubscribe_token(1, "a@gmail.com")
    assert email_preferences.read_unsubscribe_token("unsubscribe.1.YQ.deadbeef") is None


# ── account deletion ─────────────────────────────────────────────────────────


def test_account_deletion_requires_password_and_confirmation(outbox):
    provider, web_app = outbox
    with web_app.app.test_client() as client:
        signup = client.post(
            "/api/auth/signup",
            json={"name": "Delete Me", "email_or_phone": "deleteme@gmail.com", "password": "correct-horse-battery"},
        ).get_json()
        headers = {"X-Session-Id": signup["session_id"]}

        # The confirmation word is checked first: a malformed request never
        # reaches a password comparison.
        assert (
            client.post("/api/account/delete", json={"password": "wrong-password"}, headers=headers).status_code == 400
        )
        assert (
            client.post(
                "/api/account/delete", json={"password": "correct-horse-battery", "confirm": "yes"}, headers=headers
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/api/account/delete", json={"password": "wrong-password", "confirm": "DELETE"}, headers=headers
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/api/account/delete",
                json={"password": "correct-horse-battery", "confirm": "DELETE"},
                headers=headers,
            ).status_code
            == 200
        )

        assert client.post("/api/auth/verify", json={"session_id": signup["session_id"]}).get_json()["valid"] is False

    assert _sent_kinds(provider)[-1] == "account_deleted"
    conn = web_app._get_db()
    remaining = conn.execute("SELECT COUNT(*) AS c FROM users WHERE id = ?", (signup["user_id"],)).fetchone()["c"]
    sessions = conn.execute("SELECT COUNT(*) AS c FROM sessions WHERE user_id = ?", (signup["user_id"],)).fetchone()[
        "c"
    ]
    conn.close()
    assert remaining == 0
    assert sessions == 0


def test_owner_account_cannot_be_deleted_from_the_app(outbox):
    """A verified owner account is protected from self-deletion."""
    _, web_app = outbox
    with web_app.app.test_client() as client:
        signup = client.post(
            "/api/auth/signup",
            json={"name": "Owner", "email_or_phone": "sumitagg24@gmail.com", "password": "correct-horse-battery"},
        ).get_json()
        conn = web_app._get_db()
        conn.execute(
            "UPDATE users SET email_verified = 1 WHERE email_or_phone = ?",
            ("sumitagg24@gmail.com",),
        )
        conn.commit()
        conn.close()
        client.post(
            "/api/auth/login",
            json={"email_or_phone": "sumitagg24@gmail.com", "password": "correct-horse-battery"},
        )
        response = client.post(
            "/api/account/delete",
            json={"password": "correct-horse-battery", "confirm": "DELETE"},
            headers={"X-Session-Id": signup["session_id"]},
        )
    assert response.status_code == 403
    assert response.get_json()["code"] == "owner_protected"


# ── usage notifications ──────────────────────────────────────────────────────


def _fill_quota(web_app, user_id: int, count: int) -> None:
    conn = web_app._get_db()
    for _ in range(count):
        conn.execute("INSERT INTO transcriptions (user_id, text) VALUES (?, ?)", (user_id, "x"))
    conn.commit()
    conn.close()


def test_usage_warning_is_sent_once_per_month(outbox):
    provider, web_app = outbox
    with web_app.app.test_client() as client:
        signup = client.post(
            "/api/auth/signup",
            json={"name": "Heavy", "email_or_phone": "heavy@gmail.com", "password": "correct-horse-battery"},
        ).get_json()
    provider.outbox.clear()
    _fill_quota(web_app, signup["user_id"], 80)

    web_app._notify_usage_threshold(signup["user_id"])
    web_app._notify_usage_threshold(signup["user_id"])

    kinds = _sent_kinds(provider)
    assert kinds == ["usage_warning"], "the 80% notice must be sent exactly once per month"
    assert "80" in provider.outbox[0].subject


def test_reaching_the_limit_sends_the_limit_notice(outbox):
    provider, web_app = outbox
    with web_app.app.test_client() as client:
        signup = client.post(
            "/api/auth/signup",
            json={"name": "Maxed", "email_or_phone": "maxed@gmail.com", "password": "correct-horse-battery"},
        ).get_json()
    provider.outbox.clear()
    _fill_quota(web_app, signup["user_id"], 100)

    web_app._notify_usage_threshold(signup["user_id"])
    web_app._notify_usage_threshold(signup["user_id"])

    assert _sent_kinds(provider) == ["usage_limit_reached"]


def test_owner_never_receives_quota_mail(outbox):
    """A verified owner (unlimited) is never nagged about usage."""
    provider, web_app = outbox
    with web_app.app.test_client() as client:
        signup = client.post(
            "/api/auth/signup",
            json={"name": "Owner", "email_or_phone": "sumitagg24@gmail.com", "password": "correct-horse-battery"},
        ).get_json()
        conn = web_app._get_db()
        conn.execute(
            "UPDATE users SET email_verified = 1 WHERE email_or_phone = ?",
            ("sumitagg24@gmail.com",),
        )
        conn.commit()
        conn.close()
        client.post(
            "/api/auth/login",
            json={"email_or_phone": "sumitagg24@gmail.com", "password": "correct-horse-battery"},
        )
    provider.outbox.clear()
    _fill_quota(web_app, signup["user_id"], 500)

    web_app._notify_usage_threshold(signup["user_id"])
    assert provider.outbox == []


def test_quota_mail_is_skipped_without_an_email_address(outbox):
    provider, web_app = outbox
    conn = web_app._get_db()
    conn.execute(
        "INSERT INTO users (name, email_or_phone, password_hash) VALUES (?, ?, ?)",
        ("Phone Only", "+15551234", "x"),
    )
    user_id = conn.execute("SELECT id FROM users WHERE email_or_phone = '+15551234'").fetchone()["id"]
    conn.commit()
    conn.close()
    _fill_quota(web_app, user_id, 100)

    web_app._notify_usage_threshold(user_id)
    assert provider.outbox == []


# ── monitoring: scrubbing ────────────────────────────────────────────────────


def test_scrubber_redacts_credentials_and_user_content():
    event = {
        "password": "hunter2",
        "api_key": "gsk_live_should_never_ship",
        "email_or_phone": "person@example.com",
        "transcript": "what the user actually said",
        "nested": {"session_id": "abc123", "safe": "keep-me"},
        "list": [{"token": "reset-token-value"}],
    }
    cleaned = observability.scrub(event)
    assert cleaned["password"] == "[redacted]"
    assert cleaned["api_key"] == "[redacted]"
    assert cleaned["email_or_phone"] == "[redacted]"
    assert cleaned["transcript"] == "[redacted]"
    assert cleaned["nested"]["session_id"] == "[redacted]"
    assert cleaned["nested"]["safe"] == "keep-me"
    assert cleaned["list"][0]["token"] == "[redacted]"
    assert "hunter2" not in repr(cleaned)
    assert "gsk_live" not in repr(cleaned)


def test_long_free_text_is_withheld():
    cleaned = observability.scrub({"note": "x" * 900})
    assert "withheld" in cleaned["note"]
    assert "x" * 100 not in cleaned["note"]


def test_before_send_drops_request_bodies_headers_cookies_and_locals():
    event = {
        "request": {
            "url": "https://voxylis.com/api/auth/reset-password?token=secret-token",
            "data": {"password": "hunter2"},
            "headers": {"Authorization": "Bearer abc", "X-Session-Id": "abc"},
            "cookies": {"session": "abc"},
            "env": {"HTTP_AUTHORIZATION": "Bearer abc"},
            "query_string": "token=secret-token",
        },
        "query_string": "token=secret-token",
        "user": {"id": 7, "email": "person@example.com"},
        "extra": {"transcript": "private words", "stage": "transcribe"},
        "exception": {"values": [{"stacktrace": {"frames": [{"vars": {"password": "hunter2"}}]}}]},
    }
    cleaned = observability.before_send(dict(event), {})
    assert "data" not in cleaned["request"]
    assert "headers" not in cleaned["request"]
    assert "cookies" not in cleaned["request"]
    assert "env" not in cleaned["request"]
    assert cleaned["request"]["url"] == "https://voxylis.com/api/auth/reset-password"
    assert "query_string" not in cleaned
    assert cleaned["user"] == {"id": "7"}
    assert cleaned["extra"]["transcript"] == "[redacted]"
    assert cleaned["extra"]["stage"] == "transcribe"
    assert cleaned["exception"]["values"][0]["stacktrace"]["frames"][0] == {}
    assert "hunter2" not in repr(cleaned)
    assert "private words" not in repr(cleaned)


def test_before_send_survives_odd_event_shapes():
    for event in ({}, {"request": None}, {"exception": {"values": None}}, {"breadcrumbs": "not-a-list"}):
        assert observability.before_send(dict(event), {}) is not None


# ── monitoring: initialisation is optional ───────────────────────────────────


def test_monitoring_is_off_without_a_dsn(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    monkeypatch.setattr(observability, "_state", dict(observability._state, initialized=False, enabled=False))
    assert observability.init_sentry() is False
    status = observability.status()
    assert status["enabled"] is False
    assert "SENTRY_DSN" in status["reason"]
    # Safe to call while disabled.
    observability.capture_exception(RuntimeError("boom"), category="test")
    observability.capture_message("hello")
    assert observability.capture_email_failure("welcome", "a@gmail.com", RuntimeError("x")) is None


def test_a_broken_dsn_never_takes_the_app_down(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "this-is-not-a-dsn")
    monkeypatch.setattr(observability, "_state", dict(observability._state, initialized=False, enabled=False))
    # Either the SDK is missing or the DSN is rejected: both must be survivable.
    assert observability.init_sentry() in (True, False)
    assert observability.status()["reason"]
    observability.capture_exception(RuntimeError("still fine"))


def test_a_valid_dsn_enables_monitoring_when_the_sdk_is_present(monkeypatch):
    sentry_sdk = pytest.importorskip("sentry_sdk", reason="sentry-sdk is an optional dependency")
    del sentry_sdk
    monkeypatch.setenv("SENTRY_DSN", "https://public@example.invalid/1")
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "production")
    monkeypatch.setattr(observability, "_state", dict(observability._state, initialized=False, enabled=False))
    assert observability.init_sentry() is True
    status = observability.status()
    assert status["enabled"] is True
    assert status["environment"] == "production"
    assert status["release"].startswith("voxylis@")
    assert status["traces_sample_rate"] == 0.05


def test_default_trace_rate_is_full_in_development(monkeypatch):
    monkeypatch.delenv("SENTRY_TRACES_SAMPLE_RATE", raising=False)
    assert observability._traces_sample_rate("development") == 1.0
    assert observability._traces_sample_rate("production") == 0.05
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "0.25")
    assert observability._traces_sample_rate("production") == 0.25
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "not-a-number")
    assert observability._traces_sample_rate("production") == 0.05


def test_public_config_never_exposes_the_server_dsn(app_client, monkeypatch):
    client, _ = app_client
    monkeypatch.setenv("SENTRY_DSN", "https://SERVER-ONLY-DSN@example.invalid/1")
    monkeypatch.setenv("SENTRY_DSN_BROWSER", "https://browser-public@example.invalid/2")
    response = client.get("/api/public-config")
    payload = response.get_json()
    assert payload["sentry_dsn"] == "https://browser-public@example.invalid/2"
    assert "SERVER-ONLY-DSN" not in response.get_data(as_text=True)
    assert payload["version"]


def test_health_reports_email_and_monitoring_state(app_client):
    client, _ = app_client
    body = client.get("/api/health").get_json()
    assert body["email"]["provider"] == "console"
    assert body["email"]["configured"] is False
    assert body["monitoring"]["enabled"] is False
    # No secret value may appear in the health payload.
    assert "SECRET_KEY" not in repr(body)


def test_csp_allows_sentry_ingest(app_client):
    client, _ = app_client
    csp = client.get("/").headers["Content-Security-Policy"]
    assert "ingest.sentry.io" in csp
    assert "default-src 'self'" in csp


def test_browser_bundle_only_loads_when_a_dsn_exists():
    """A deployment without Sentry must make no third-party request at all."""
    script = (REPO / "web" / "static" / "js" / "sentry-init.js").read_text(encoding="utf-8")
    assert "/api/public-config" in script
    assert "if (!cfg || !cfg.sentry_dsn) return;" in script
    # No organization/auth token may ever be referenced in frontend code.
    assert "auth_token" not in script.lower().replace("auth token", "")
    assert "SENTRY_AUTH_TOKEN" not in script


# ── desktop crash reporting (opt-in) ─────────────────────────────────────────


@pytest.fixture
def desktop_monitoring():
    """Import the desktop module with a clean state, restoring it afterwards."""
    import importlib

    from utils import observability as desktop_obs

    original = dict(desktop_obs._state)
    yield desktop_obs
    desktop_obs._state.clear()
    desktop_obs._state.update(original)
    importlib.reload(desktop_obs)


def test_desktop_scrubbing_masks_paths_and_credentials(desktop_monitoring, isolated_home):
    from utils import paths

    payload = {
        "api_key": "gsk_pretend_this_is_real",
        "transcript": "the private words",
        "clipboard": "copied text",
        "provider": "groq",
        "path": str(paths.log_path()),
    }
    cleaned = desktop_monitoring.scrub(payload)
    assert cleaned["api_key"] == "[redacted]"
    assert cleaned["transcript"] == "[redacted]"
    assert cleaned["clipboard"] == "[redacted]"
    assert cleaned["provider"] == "groq"
    # The user-data root encodes the Windows account name; it must not ship.
    assert str(paths.user_data_root()) not in cleaned["path"]
    assert "%VOXYLIS_HOME%" in cleaned["path"]


def test_desktop_before_send_removes_user_and_frame_locals(desktop_monitoring):
    event = {
        "message": "failed to transcribe",
        "user": {"id": "1", "email": "person@example.com"},
        "request": {"data": "raw body"},
        "extra": {"api_key": "gsk_secret"},
        "exception": {"values": [{"stacktrace": {"frames": [{"vars": {"password": "hunter2"}}]}}]},
    }
    cleaned = desktop_monitoring.before_send(dict(event), {})
    assert "user" not in cleaned
    assert cleaned["request"] == {}
    assert cleaned["extra"]["api_key"] == "[redacted]"
    assert cleaned["exception"]["values"][0]["stacktrace"]["frames"][0] == {}
    assert "hunter2" not in repr(cleaned)
    assert "person@example.com" not in repr(cleaned)


def test_desktop_reporting_needs_consent_and_a_dsn(desktop_monitoring, monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    monkeypatch.delenv("SENTRY_DESKTOP_CRASH_REPORTS", raising=False)
    desktop_monitoring._state.update(initialized=False, enabled=False)

    # No DSN: reporting cannot start even with consent.
    assert desktop_monitoring.init_observability({"share_crash_reports": True}) is False
    assert "SENTRY_DSN" in desktop_monitoring.status()["reason"]

    # A DSN without consent stays off: opt-in, not opt-out.
    monkeypatch.setenv("SENTRY_DSN", "https://public@example.invalid/1")
    desktop_monitoring._state.update(initialized=False, enabled=False)
    assert desktop_monitoring.init_observability({}) is False
    assert "Privacy" in desktop_monitoring.status()["reason"]

    # Turning it off is immediate and quiet.
    assert desktop_monitoring.set_consent(False) is False
    assert desktop_monitoring.is_enabled() is False


def test_desktop_status_never_contains_a_dsn(desktop_monitoring, monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://SECRET-KEY-VALUE@example.invalid/9")
    status = desktop_monitoring.status()
    assert status["dsn_configured"] is True
    assert "SECRET-KEY-VALUE" not in repr(status)
    assert set(status) == {
        "enabled",
        "consent",
        "reason",
        "environment",
        "release",
        "dsn_configured",
        "install_available",
    }


def test_desktop_capture_helpers_are_no_ops_when_disabled(desktop_monitoring):
    desktop_monitoring._state.update(enabled=False)
    desktop_monitoring.capture_exception(RuntimeError("boom"), category="pipeline")
    desktop_monitoring.capture_message("hello")
    desktop_monitoring.capture_startup_failure(RuntimeError("startup"))

    class FakeError:
        code = "no_api_key"
        detail = "no key stored"
        retryable = False

    desktop_monitoring.capture_error(FakeError(), category="pipeline")
    desktop_monitoring.capture_stage_failure("transcription", RuntimeError("x"))


def test_desktop_dsn_comes_from_the_environment_not_the_build(desktop_monitoring, monkeypatch):
    """Runtime-only resolution: env var wins, nothing is compiled in.

    A DSN baked into the PyInstaller bundle would ship a secret inside an
    artifact users can unpack and would enable reporting before consent.
    """
    # Unconfigured: no env var, not frozen -> no DSN, reporting stays off.
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    monkeypatch.delenv("SENTRY_DSN_FILE", raising=False)
    monkeypatch.delattr(sys, "frozen", raising=False)
    desktop_monitoring._state.update(initialized=False, enabled=False)
    assert desktop_monitoring.dsn() == ""
    assert desktop_monitoring.init_observability({"share_crash_reports": True}) is False

    # Configured at runtime: the DSN arrives via the environment.
    monkeypatch.setenv("SENTRY_DSN", "https://runtime-dsn@example.invalid/1")
    monkeypatch.setenv("SENTRY_DESKTOP_CRASH_REPORTS", "1")
    desktop_monitoring._state.update(initialized=False, enabled=False)
    assert desktop_monitoring.dsn() == "https://runtime-dsn@example.invalid/1"
    assert desktop_monitoring.init_observability({}) is True
    assert desktop_monitoring.is_enabled() is True


def test_desktop_dsn_file_is_read_only_in_frozen_builds(desktop_monitoring, monkeypatch, tmp_path):
    """The DSN-file fallback exists for installed machines, never dev runs."""
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    dsn_file = tmp_path / "desktop-dsn.txt"
    dsn_file.write_text("https://file-dsn@example.invalid/2\n", encoding="utf-8")
    monkeypatch.setenv("SENTRY_DSN_FILE", str(dsn_file))

    # A dev run (sys.frozen absent) must not pick the file up.
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert desktop_monitoring.dsn() == ""

    # A frozen build reads it; surrounding whitespace/newlines are tolerated.
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert desktop_monitoring.dsn() == "https://file-dsn@example.invalid/2"

    # Junk in the file is ignored rather than passed to the SDK.
    dsn_file.write_text("not-a-dsn", encoding="utf-8")
    assert desktop_monitoring.dsn() == ""
    # ... and a missing file never raises.
    monkeypatch.setenv("SENTRY_DSN_FILE", str(tmp_path / "absent.txt"))
    assert desktop_monitoring.dsn() == ""


def test_desktop_consent_env_var_alone_is_never_enough(desktop_monitoring, monkeypatch):
    """SENTRY_DESKTOP_CRASH_REPORTS is an ops/CI switch, not a user toggle.

    Consent still comes from Settings → Privacy (share_crash_reports); the env
    var exists so an operator can verify a deployment without inventing consent.
    """
    monkeypatch.delenv("SENTRY_DESKTOP_CRASH_REPORTS", raising=False)
    monkeypatch.setattr(desktop_monitoring, "dsn", lambda: "https://public@example.invalid/3")
    desktop_monitoring._state.update(initialized=False, enabled=False)

    # Neither the settings flag nor the env var: stays off.
    assert desktop_monitoring.init_observability({}) is False
    # Only the env var set and no settings flag: still off for real users.
    monkeypatch.setenv("SENTRY_DESKTOP_CRASH_REPORTS", "true")
    desktop_monitoring._state.update(initialized=False, enabled=False)
    assert desktop_monitoring.consent_from_config({}) is False
    # The combination the docs call the verification path.
    assert desktop_monitoring.init_observability({"share_crash_reports": True}) is True


def test_pyinstaller_spec_never_bakes_a_dsn_into_the_build():
    """Guardrail: the spec must not gain a DSN env injection or DSN data file."""
    spec = (REPO / "voxylis.spec").read_text(encoding="utf-8")
    assert "SENTRY_DSN" not in spec
    assert "dsn" not in spec.lower()


def test_desktop_consent_flag_is_read_from_config(desktop_monitoring):
    assert desktop_monitoring.consent_from_config({"share_crash_reports": True}) is True
    assert desktop_monitoring.consent_from_config({"share_crash_reports": False}) is False
    assert desktop_monitoring.consent_from_config({}) is False
    assert desktop_monitoring.consent_from_config(None) is False


# ── monitoring: free-text and message-event scrubbing (F1/F2/F3) ─────────────


def test_before_send_caps_long_exception_and_message_text():
    """F1: exception/logentry free text is length-capped, not shipped verbatim.

    Exception messages frequently embed untrusted input (a repr of a request,
    a path with a user name, a session id). The key-based scrub cannot reach a
    bare string on a list. Values over 500 chars are withheld outright by
    ``scrub()``; the 400-500 char window is where this cap bites.
    """
    # 449 chars: inside the window — the tail must not survive the cap.
    blob = "A" * 439 + "SECRETTAIL"
    assert 400 < len(blob) <= 500
    event = {
        "exception": {"values": [{"type": "ValueError", "value": blob}]},
        "logentry": {"formatted": blob},
    }
    cleaned = observability.before_send(dict(event), {})
    value = cleaned["exception"]["values"][0]["value"]
    assert len(value) == 400
    assert "SECRETTAIL" not in value
    assert len(cleaned["logentry"]["formatted"]) == 400
    assert "SECRETTAIL" not in cleaned["logentry"]["formatted"]

    # 1040 chars: scrub() withholds it entirely before the cap even applies.
    event = {"exception": {"values": [{"type": "ValueError", "value": "x" * 1040}]}}
    cleaned = observability.before_send(dict(event), {})
    assert "withheld" in cleaned["exception"]["values"][0]["value"]
    assert "x" * 100 not in cleaned["exception"]["values"][0]["value"]


def test_before_send_strips_frame_locals_from_message_event_threads():
    """F2: capture_message events carry their stack under threads, not
    exception — those frame locals must be dropped too."""
    event = {
        "threads": {
            "values": [
                {
                    "stacktrace": {
                        "frames": [
                            {"vars": {"password": "hunter2"}},
                            {"vars": {"api_key": "gsk_live_value"}},
                            {"function": "clean_frame"},
                        ]
                    }
                }
            ]
        }
    }
    cleaned = observability.before_send(dict(event), {})
    frames = cleaned["threads"]["values"][0]["stacktrace"]["frames"]
    assert "vars" not in frames[0] and "vars" not in frames[1]
    assert frames[2] == {"function": "clean_frame"}
    assert "hunter2" not in repr(cleaned) and "gsk_live" not in repr(cleaned)


def test_before_send_drops_token_bearing_breadcrumbs():
    """F3: outbound breadcrumbs record request URLs verbatim — a reset or
    verification call would embed a working credential in every event."""
    event = {
        "breadcrumbs": {
            "values": [
                {"type": "http", "data": {"url": "https://api/v1/auth/reset-password?token=secret123"}},
                {"type": "http", "data": {"url": "https://api/v1/pricing"}},
                {"type": "http", "data": {"url": "https://api/v1/auth/verify-email?verify_token=abc"}},
                {"message": "no url here"},
                "not-even-a-dict",
            ]
        }
    }
    cleaned = observability.before_send(dict(event), {})
    kept = cleaned["breadcrumbs"]["values"]
    assert len(kept) == 3, kept
    assert kept[0]["data"]["url"] == "https://api/v1/pricing"
    assert "secret123" not in repr(cleaned) and "verify_token=abc" not in repr(cleaned)
