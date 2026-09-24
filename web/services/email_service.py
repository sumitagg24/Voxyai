"""
Transactional email delivery for Voxylis.

Design
------
A *provider adapter* is the only place a vendor is named.  Everything else
calls :func:`send_transactional` / :func:`send_marketing` with a template kind
and a context, so swapping Resend for SES or Postmark is a new class, not a
tour of the codebase.

    ConsoleEmailProvider   development aid: logs the message, sends nothing
    ResendEmailProvider    HTTP API (RESEND-style POST /emails)
    SmtpEmailProvider      stdlib smtplib + STARTTLS, no vendor at all

Selection order (``EMAIL_PROVIDER=auto``, the default):
    EMAIL_API_KEY set  -> resend
    SMTP_HOST set      -> smtp
    otherwise          -> console

Failure policy
--------------
Email must never break a request.  Every send is best-effort: failures are
logged, reported to Sentry with the recipient redacted, and swallowed.  A
signup whose welcome email failed still creates the account — the user can ask
for a new verification link.

Privacy rules
-------------
* Bodies and subjects are never logged, and tokens are never logged — a reset
  link in a log file is a working credential.
* Recipients are masked to ``a***@domain`` in every log line and Sentry event.
* A missing provider in production is surfaced loudly at startup instead of
  silently dropping the mail.
"""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage as _MimeMessage
from typing import Dict, List, Optional

import requests

from web.services import email_templates as templates

logger = logging.getLogger(__name__)

_TRUTHY = {"1", "true", "yes", "on"}
_TIMEOUT_SECONDS = 10


class EmailDeliveryError(RuntimeError):
    """Raised by a provider when a message could not be handed off."""


@dataclass
class EmailMessage:
    """A fully rendered message, ready for a provider."""

    to: str
    subject: str
    text: str
    html: str
    kind: str
    reply_to: str = ""
    headers: Dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def configured_provider_name() -> str:
    """Resolve the provider name from the environment (``console`` when unsure)."""
    explicit = _env("EMAIL_PROVIDER").lower()
    if explicit and explicit != "auto":
        return explicit
    if _env("EMAIL_API_KEY"):
        return "resend"
    if _env("SMTP_HOST"):
        return "smtp"
    return "console"


def email_configured() -> bool:
    """True when real mail can actually leave the process.

    A provider *name* is not enough: ``EMAIL_PROVIDER=resend`` with no API key
    selects a provider that will refuse every message, and reporting that as
    "configured" would hide the breakage until a user reports a missing email.
    """
    name = configured_provider_name()
    if name == "resend":
        return bool(_env("EMAIL_API_KEY"))
    if name == "smtp":
        return bool(_env("SMTP_HOST"))
    return False


def from_address() -> str:
    return _env("EMAIL_FROM") or "Voxylis <no-reply@voxylis.com>"


def reply_to() -> str:
    return _env("EMAIL_REPLY_TO") or _env("SUPPORT_EMAIL")


def support_address() -> str:
    return _env("SUPPORT_EMAIL") or _env("EMAIL_REPLY_TO") or "support@voxylis.com"


def site_base_url() -> str:
    return (_env("FRONTEND_URL") or templates.WEBSITE).rstrip("/")


def describe_configuration() -> Dict[str, object]:
    """Non-secret description for ``/api/health`` and operations docs."""
    return {
        "provider": configured_provider_name(),
        "configured": email_configured(),
        "from": from_address(),
        "frontend_url": site_base_url(),
    }


def warn_if_unconfigured() -> None:
    """Log once at startup when production is running the console provider."""
    from web.services import subscription_service

    provider = configured_provider_name()
    if provider == "console":
        level = logger.error if subscription_service.is_production() else logger.warning
        level(
            "Email provider is 'console': verification and password-reset mail will NOT be "
            "delivered. Set EMAIL_API_KEY (Resend) or SMTP_HOST before release."
        )


def mask_email(address: str) -> str:
    """``someone@example.com`` -> ``s***@example.com`` (safe for logs)."""
    address = (address or "").strip()
    if "@" not in address:
        return "***"
    local, _, domain = address.partition("@")
    head = local[:1] if local else ""
    return f"{head}***@{domain}"


def build_link(kind: str, token: str) -> str:
    """Public URL that carries a one-time token.

    Verification and reset links are deliberately built from ``FRONTEND_URL``
    so a hosted deployment can never email a ``localhost`` link by accident.
    """
    base = site_base_url()
    if kind == "verify_email":
        override = _env("EMAIL_VERIFICATION_URL")
        if override:
            return override.replace("{token}", token)
        return f"{base}/auth?verify_token={token}"
    if kind == "password_reset":
        override = _env("PASSWORD_RESET_URL")
        if override:
            return override.replace("{token}", token)
        return f"{base}/auth?reset_token={token}"
    return base


def unsubscribe_link(user_id: int, email: str) -> str:
    """Signed opt-out link for product news."""
    from web.services import email_preferences

    return f"{site_base_url()}/unsubscribe?token={email_preferences.unsubscribe_token(user_id, email)}"


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


class EmailProvider:
    """Adapter interface: one method, no state beyond configuration."""

    name = "base"

    def send(self, message: EmailMessage) -> Optional[str]:  # pragma: no cover - interface
        raise NotImplementedError

    def is_live(self) -> bool:
        return True


class ConsoleEmailProvider(EmailProvider):
    """Development provider: records what *would* be sent, sends nothing.

    Bodies are withheld from the log on purpose — they contain one-time tokens.
    """

    name = "console"

    def __init__(self) -> None:
        self.outbox: List[EmailMessage] = []

    def is_live(self) -> bool:
        return False

    def send(self, message: EmailMessage) -> Optional[str]:
        self.outbox.append(message)
        logger.info(
            "email:console kind=%s to=%s subject-length=%d (not delivered)",
            message.kind,
            mask_email(message.to),
            len(message.subject),
        )
        return "console"


class ResendEmailProvider(EmailProvider):
    """HTTP transactional provider (Resend-compatible ``POST /emails``)."""

    name = "resend"
    endpoint = "https://api.resend.com/emails"

    def __init__(self, api_key: str = "", sender: str = "") -> None:
        self.api_key = api_key or _env("EMAIL_API_KEY")
        self.sender = sender or from_address()

    def send(self, message: EmailMessage) -> Optional[str]:
        if not self.api_key:
            raise EmailDeliveryError("EMAIL_API_KEY is not set")
        payload = {
            "from": self.sender,
            "to": [message.to],
            "subject": message.subject,
            "text": message.text,
            "html": message.html,
        }
        if message.reply_to:
            payload["reply_to"] = message.reply_to
        # Provider-side tagging helps debugging without exposing recipients.
        payload["headers"] = {"X-Voxylis-Kind": message.kind, **message.headers}
        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise EmailDeliveryError(f"resend transport error: {exc}") from exc
        if response.status_code >= 400:
            # The body can echo the message; keep only the status.
            raise EmailDeliveryError(f"resend rejected the message (HTTP {response.status_code})")
        try:
            return (response.json() or {}).get("id")
        except ValueError:
            return None


class SmtpEmailProvider(EmailProvider):
    """Vendor-neutral SMTP (STARTTLS on 587 by default, implicit TLS on 465)."""

    name = "smtp"

    def __init__(self) -> None:
        self.host = _env("SMTP_HOST")
        self.port = int(_env("SMTP_PORT", "587") or 587)
        self.username = _env("SMTP_USERNAME")
        self.password = _env("SMTP_PASSWORD")
        self.use_tls = _env("SMTP_USE_TLS", "true").lower() in _TRUTHY

    def send(self, message: EmailMessage) -> Optional[str]:
        if not self.host:
            raise EmailDeliveryError("SMTP_HOST is not set")
        mime = _MimeMessage()
        mime["From"] = from_address()
        mime["To"] = message.to
        mime["Subject"] = message.subject
        if message.reply_to:
            mime["Reply-To"] = message.reply_to
        for key, value in message.headers.items():
            mime[key] = value
        mime.set_content(message.text)
        mime.add_alternative(message.html, subtype="html")

        try:
            if self.port == 465:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.host, self.port, timeout=_TIMEOUT_SECONDS, context=context) as server:
                    if self.username:
                        server.login(self.username, self.password)
                    server.send_message(mime)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=_TIMEOUT_SECONDS) as server:
                    server.ehlo()
                    if self.use_tls:
                        server.starttls(context=ssl.create_default_context())
                        server.ehlo()
                    if self.username:
                        server.login(self.username, self.password)
                    server.send_message(mime)
        except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
            raise EmailDeliveryError(f"smtp delivery failed: {type(exc).__name__}") from exc
        return None


_PROVIDER_OVERRIDE: Optional[EmailProvider] = None


def set_provider(provider: Optional[EmailProvider]) -> None:
    """Install a provider for tests, or restore env-driven selection with None."""
    global _PROVIDER_OVERRIDE
    _PROVIDER_OVERRIDE = provider


def get_provider() -> EmailProvider:
    """Return the active provider (env-driven unless a test installed one)."""
    if _PROVIDER_OVERRIDE is not None:
        return _PROVIDER_OVERRIDE
    name = configured_provider_name()
    if name == "resend":
        return ResendEmailProvider()
    if name == "smtp":
        return SmtpEmailProvider()
    return ConsoleEmailProvider()


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------


def _capture_failure(kind: str, recipient: str, exc: BaseException) -> None:
    """Report a delivery failure to Sentry without leaking the recipient."""
    try:
        from web import observability

        observability.capture_email_failure(kind, recipient, exc)
    except Exception:  # pragma: no cover - monitoring must never raise
        pass


def send(kind: str, to: str, context: Optional[Dict] = None) -> Optional[str]:
    """Render and deliver one template. Returns a provider message id or None.

    Never raises: a mail problem must not turn a valid request into a 500.
    """
    recipient = (to or "").strip()
    if not recipient or "@" not in recipient:
        logger.warning("email: refusing to send kind=%s with an invalid recipient", kind)
        return None
    if not templates.is_known(kind):
        logger.error("email: unknown template kind=%s", kind)
        return None

    subject, text, html = templates.render(kind, context or {})
    message = EmailMessage(
        to=recipient,
        subject=subject,
        text=text,
        html=html,
        kind=kind,
        reply_to=reply_to(),
    )

    provider = get_provider()
    try:
        message_id = provider.send(message)
    except EmailDeliveryError as exc:
        logger.error(
            "email: delivery failed kind=%s provider=%s to=%s (%s)",
            kind,
            provider.name,
            mask_email(recipient),
            exc,
        )
        _capture_failure(kind, recipient, exc)
        return None
    except Exception as exc:  # pragma: no cover - defensive
        logger.error(
            "email: unexpected failure kind=%s provider=%s to=%s (%s)",
            kind,
            provider.name,
            mask_email(recipient),
            type(exc).__name__,
        )
        _capture_failure(kind, recipient, exc)
        return None

    # Be explicit about whether mail actually left the process: logging
    # "delivered" for the console provider would tell an operator that
    # verification mail is working when it is not.
    logger.info(
        "email:%s kind=%s to=%s outcome=%s",
        provider.name,
        kind,
        mask_email(recipient),
        "sent" if provider.is_live() else "recorded-not-delivered",
    )
    return message_id


def send_transactional(kind: str, to: str, context: Optional[Dict] = None) -> Optional[str]:
    """Account/security mail. Delivered regardless of marketing preferences."""
    if templates.is_marketing(kind):
        logger.error("email: %s is a marketing template; use send_marketing()", kind)
        return None
    return send(kind, to, context)


def send_marketing(kind: str, to: str, context: Optional[Dict] = None, consent: bool = False) -> Optional[str]:
    """Product news. Requires explicit consent — silence is not consent."""
    if not consent:
        logger.info("email: skipped marketing kind=%s to=%s (no consent)", kind, mask_email(to))
        return None
    if not templates.is_marketing(kind):
        logger.error("email: %s is not a marketing template; use send_transactional()", kind)
        return None
    return send(kind, to, context)
