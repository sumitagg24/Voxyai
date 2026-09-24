"""
Error monitoring for the Voxylis backend.

What gets sent
--------------
    * unhandled exceptions and explicit ``capture_*`` calls from the pipeline;
    * a small, non-sensitive context: route, method, status, app version,
      environment, tier, and the internal user id (never the email address);
    * performance traces, sampled by ``SENTRY_TRACES_SAMPLE_RATE``.

What never gets sent
--------------------
    * request bodies — disabled at the SDK level with
      ``max_request_body_size="never"`` and stripped again in ``before_send``;
    * cookies, ``Authorization``, ``X-Session-Id`` and any other credential
      header (the whole header map is dropped, not filtered);
    * passwords, API keys, tokens, session ids, transcripts, prompts, audio,
      clipboard contents and user email addresses;
    * query strings, which can carry one-time tokens.

Why both a denylist and "drop everything"
-----------------------------------------
A denylist alone fails open: the day someone adds a field name nobody thought
of, it ships to a third party.  So the SDK is told not to attach bodies at all,
credentials are removed wholesale by key, and the denylist then catches the
free-form extras our own code attaches.

Non-fatal by design
-------------------
If ``sentry_sdk`` is not installed, or ``SENTRY_DSN`` is empty, every function
here degrades to a no-op and Voxylis keeps working.  Monitoring must never be a
reason the product is down.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from config.version import __version__

logger = logging.getLogger(__name__)

#: Keys whose *value* is a credential or user content. Matched case-insensitively
#: as a substring, so ``email_or_phone``, ``reset_token`` and ``api_key`` all hit.
_SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "auth",
    "cookie",
    "session",
    "apikey",
    "api_key",
    "key",
    "credential",
    "vault",
    "phone",
    "email",
    "transcript",
    "audio",
    "prompt",
    "clipboard",
    "content",
    "message",
    "text",
)

_REDACTED = "[redacted]"
_MAX_DEPTH = 8

_state: Dict[str, Any] = {
    "initialized": False,
    "enabled": False,
    "reason": "not initialised",
    "environment": "",
    "release": "",
    "traces_sample_rate": 0.0,
    "sdk": False,
}


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _traces_sample_rate(environment: str) -> float:
    raw = _env("SENTRY_TRACES_SAMPLE_RATE")
    if raw:
        try:
            return max(0.0, min(1.0, float(raw)))
        except ValueError:
            logger.warning("SENTRY_TRACES_SAMPLE_RATE is not a number; using the default")
    return 0.05 if environment == "production" else 1.0


def release_name() -> str:
    return _env("SENTRY_RELEASE") or f"voxylis@{__version__}"


def browser_dsn() -> str:
    """Public DSN handed to the website bundle (empty when unset)."""
    return _env("SENTRY_DSN_BROWSER")


# ---------------------------------------------------------------------------
# Scrubbing
# ---------------------------------------------------------------------------


def _is_sensitive(key: str) -> bool:
    lowered = str(key).lower()
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)


def scrub(value: Any, depth: int = 0) -> Any:
    """Recursively redact credential- and content-shaped values."""
    if depth > _MAX_DEPTH:
        return _REDACTED
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            cleaned[key] = _REDACTED if _is_sensitive(key) else scrub(item, depth + 1)
        return cleaned
    if isinstance(value, (list, tuple)):
        return [scrub(item, depth + 1) for item in value]
    if isinstance(value, str) and len(value) > 500:
        # Long free text is almost always a transcript or a prompt.
        return f"[{len(value)} chars withheld]"
    return value


def _scrub_event_messages(event: Dict[str, Any]) -> None:
    """Scrub free-text fields that the structural scrub cannot reach.

    ``scrub()`` only redacts dict *values by key name*. Exception messages are
    plain strings hanging off a list, so ``{"exception": ...}`` passes through
    untouched — and exception text frequently embeds untrusted input (a path
    that contains a user name, a repr of a request object, a session id). The
    same applies to ``logentry.formatted`` on message events. Length-capping
    is deliberately conservative: an exception message is not a credential on
    its own, but a 400-character cap keeps any embedded blob unusable.
    """
    exception = event.get("exception")
    values = exception.get("values") if isinstance(exception, dict) else None
    for entry in values or []:
        if isinstance(entry, dict) and isinstance(entry.get("value"), str):
            entry["value"] = entry["value"][:400]

    logentry = event.get("logentry")
    if isinstance(logentry, dict) and isinstance(logentry.get("formatted"), str):
        logentry["formatted"] = logentry["formatted"][:400]


def _scrub_breadcrumbs(event: Dict[str, Any]) -> None:
    """Drop breadcrumbs that carry a one-time token in their URL.

    Outbound HTTP breadcrumbs record the request URL verbatim; a password
    reset or verification call would otherwise embed a working credential in
    every event. The browser bundle applies the same rule to its own events.
    """
    import re

    token_param = re.compile(r"(?:token|reset_token|verify_token|session|key|secret|code)=", re.IGNORECASE)
    breadcrumbs = event.get("breadcrumbs")
    if not isinstance(breadcrumbs, dict):
        return
    values = breadcrumbs.get("values")
    if not isinstance(values, list):
        return
    breadcrumbs["values"] = [
        crumb
        for crumb in values
        if not (
            isinstance(crumb, dict)
            and isinstance((crumb.get("data") or {}).get("url"), str)
            and token_param.search(crumb["data"]["url"])
        )
    ]


def before_send(event: Dict[str, Any], hint: Optional[Dict] = None) -> Optional[Dict[str, Any]]:  # noqa: ARG001
    """Last line of defence before an event leaves the process."""
    event.pop("query_string", None)

    request = event.get("request")
    if isinstance(request, dict):
        request.pop("data", None)
        request.pop("cookies", None)
        request.pop("headers", None)
        request.pop("query_string", None)
        # The raw WSGI environ repeats every header, including credentials.
        request.pop("env", None)
        if isinstance(request.get("url"), str) and "?" in request["url"]:
            request["url"] = request["url"].split("?", 1)[0]

    _drop_frame_locals(event)

    if "user" in event and isinstance(event["user"], dict):
        # Keep only the internal id; an email address is personal data.
        event["user"] = {
            "id": str(event["user"].get("id", "") or "") or None,
        }
        if not event["user"]["id"]:
            event.pop("user", None)

    for section in ("extra", "contexts", "breadcrumbs", "tags"):
        if section in event:
            event[section] = scrub(event[section])
    if "exception" in event:
        event["exception"] = scrub(event["exception"])
    _scrub_event_messages(event)
    _scrub_breadcrumbs(event)
    return event


def _drop_frame_locals(event: Dict[str, Any]) -> None:
    """Remove captured local variables from every stack frame.

    Sentry can attach frame locals, which is where an unscanned password, API
    key or transcript would actually sit. Their names are unknowable, so they
    are dropped rather than filtered. Message-type events (``capture_message``)
    carry their stack under ``threads`` instead of ``exception``, so both
    shapes are covered.
    """
    sections = []
    exception = event.get("exception")
    if isinstance(exception, dict):
        sections.extend(exception.get("values") or [])
    threads = event.get("threads")
    if isinstance(threads, dict):
        sections.extend(threads.get("values") or [])
    for entry in sections:
        stacktrace = entry.get("stacktrace") if isinstance(entry, dict) else None
        for frame in (stacktrace or {}).get("frames", []) or []:
            if isinstance(frame, dict):
                frame.pop("vars", None)


def before_send_transaction(
    event: Dict[str, Any], hint: Optional[Dict] = None
) -> Optional[Dict[str, Any]]:  # noqa: ARG001
    """Performance events get the same treatment as errors."""
    event.pop("query_string", None)
    request = event.get("request")
    if isinstance(request, dict):
        request.pop("data", None)
        request.pop("cookies", None)
        request.pop("headers", None)
        request.pop("env", None)
    for section in ("extra", "contexts", "tags"):
        if section in event:
            event[section] = scrub(event[section])
    return event


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


def init_sentry(app=None) -> bool:
    """Initialise the SDK once. Returns True when monitoring is active."""
    if _state["initialized"]:
        return bool(_state["enabled"])

    _state["initialized"] = True
    dsn = _env("SENTRY_DSN")
    from web.services import subscription_service

    environment = _env("SENTRY_ENVIRONMENT") or subscription_service.environment()
    _state["environment"] = environment
    _state["release"] = release_name()
    _state["traces_sample_rate"] = _traces_sample_rate(environment)

    if not dsn:
        _state["enabled"] = False
        _state["reason"] = "SENTRY_DSN is not set"
        logger.info("Sentry is disabled (no SENTRY_DSN); Voxylis runs without error reporting")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
    except ImportError:
        _state["enabled"] = False
        _state["reason"] = "sentry-sdk is not installed"
        logger.error(
            "SENTRY_DSN is set but sentry-sdk is not installed — error reporting is OFF. "
            "Install it with: pip install sentry-sdk[flask]"
        )
        return False

    _state["sdk"] = True
    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=_state["release"],
            traces_sample_rate=_state["traces_sample_rate"],
            # Bodies are never attached: this is what keeps transcripts out.
            max_request_body_size="never",
            send_default_pii=False,
            attach_stacktrace=True,
            before_send=before_send,
            before_send_transaction=before_send_transaction,
            integrations=[FlaskIntegration()],
            # Profiles and replays would collect content we refuse to ship.
            profiles_sample_rate=0.0,
        )
    except Exception as exc:  # pragma: no cover - SDK/transport problems
        _state["enabled"] = False
        _state["reason"] = f"sentry_sdk.init failed: {type(exc).__name__}"
        logger.error("Sentry could not be initialised (%s); continuing without it", type(exc).__name__)
        return False

    _state["enabled"] = True
    _state["reason"] = "active"
    logger.info(
        "Sentry enabled (environment=%s release=%s traces=%.3f)",
        environment,
        _state["release"],
        _state["traces_sample_rate"],
    )
    if app is not None:
        _wrap_request_context(app)
    return True


def _wrap_request_context(app) -> None:
    """Attach safe per-request context (route, status, tier) to every event."""

    @app.after_request
    def _sentry_context(resp):  # pragma: no cover - exercised via test client
        try:
            _set_request_context(resp.status_code)
        except Exception:
            pass
        return resp


def _set_request_context(status_code: Optional[int] = None) -> None:
    if not _state["enabled"]:
        return
    try:
        import sentry_sdk
        from flask import request

        scope = sentry_sdk.get_current_scope()
        scope.set_tag("route", request.endpoint or "unmatched")
        scope.set_tag("method", request.method)
        scope.set_tag("app_version", __version__)
        if status_code is not None:
            scope.set_tag("status_code", str(status_code))
        session_id = request.headers.get("X-Session-Id", "")
        if session_id:
            # The id itself is a credential; send only a stable, non-reversible
            # marker so repeated errors can still be correlated.
            scope.set_tag("session", _anonymise(session_id))
    except Exception:
        pass


def _anonymise(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def set_user(user_id: Optional[int], tier: str = "") -> None:
    """Record the internal user id and tier — never the email address."""
    if not _state["enabled"]:
        return
    try:
        import sentry_sdk

        scope = sentry_sdk.get_current_scope()
        if user_id is None:
            scope.set_user(None)
        else:
            scope.set_user({"id": str(user_id)})
        if tier:
            scope.set_tag("tier", tier)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Capture helpers (safe to call even when monitoring is off)
# ---------------------------------------------------------------------------


def is_enabled() -> bool:
    return bool(_state["enabled"])


def status() -> Dict[str, Any]:
    return {
        "enabled": bool(_state["enabled"]),
        "reason": _state["reason"],
        "environment": _state["environment"],
        "release": _state["release"],
        "traces_sample_rate": _state["traces_sample_rate"],
        "browser_dsn_configured": bool(browser_dsn()),
    }


def capture_exception(exc: BaseException, category: str = "", **extra: Any) -> None:
    """Report an exception with an error category and scrubbed extras."""
    if not _state["enabled"]:
        return
    try:
        import sentry_sdk

        with sentry_sdk.new_scope() as scope:
            if category:
                scope.set_tag("error_category", category)
            for key, value in (extra or {}).items():
                scope.set_extra(key, scrub(value))
            sentry_sdk.capture_exception(exc)
    except Exception:  # pragma: no cover - monitoring must never raise
        pass


def capture_message(message: str, level: str = "error", category: str = "", **extra: Any) -> None:
    if not _state["enabled"]:
        return
    try:
        import sentry_sdk

        with sentry_sdk.new_scope() as scope:
            if category:
                scope.set_tag("error_category", category)
            for key, value in (extra or {}).items():
                scope.set_extra(key, scrub(value))
            sentry_sdk.capture_message(message, level=level)
    except Exception:  # pragma: no cover
        pass


def capture_email_failure(kind: str, recipient: str, exc: BaseException) -> None:
    """Report a mail failure without the recipient address."""
    from web.services import email_service

    capture_exception(
        exc,
        category="email_delivery",
        template=kind,
        recipient=email_service.mask_email(recipient),
        provider=email_service.configured_provider_name(),
    )


def capture_pipeline_failure(stage: str, exc: BaseException, provider: str = "") -> None:
    """Report a transcription/enhancement failure (no transcript, no audio)."""
    capture_exception(exc, category="ai_pipeline", stage=stage, provider=provider)
