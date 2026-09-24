"""
Optional crash reporting for the desktop application.

Consent first
-------------
The desktop app sends **nothing** unless the user turns on
"Send crash reports" in *Settings → Privacy*.  There is no default-on
telemetry, no analytics endpoint and no install ping.  A DSN alone is not
enough: :func:`init_observability` needs explicit consent from settings or from
``SENTRY_DESKTOP_CRASH_REPORTS=true`` (a developer/CI escape hatch).

What a report contains
----------------------
    * the exception type and stack trace;
    * an ``error_category`` (``pipeline``, ``transcription``, ``updater``,
      ``hotkey``, ``microphone``, ``injection``, ``startup``, ``auth``) and, for
      classified failures, the :class:`core.errors.VoxylisError` code;
    * app version, OS, Python version, whether the build is frozen, and the
      configured provider *name* (``groq``/``openai``, never the key).

What it never contains
----------------------
    * API keys, credential-vault contents, session ids or auth tokens;
    * transcripts, enhanced text, clipboard contents or audio;
    * the account email address;
    * filesystem paths under the user's profile — the home directory and
      user-data root are rewritten to placeholders, because a Windows path
      contains the account name.

Non-fatal by design: without ``sentry-sdk``, or with consent off, every
function here is a no-op and the app behaves exactly as before.
"""

from __future__ import annotations

import logging
import os
import platform
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from config.version import __version__

logger = logging.getLogger("voxylis")

_TRUTHY = {"1", "true", "yes", "on"}
_REDACTED = "[redacted]"
_MAX_DEPTH = 8

#: Key fragments whose values must never leave the machine.
_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "key",
    "token",
    "secret",
    "password",
    "passwd",
    "credential",
    "vault",
    "session",
    "cookie",
    "authorization",
    "auth",
    "transcript",
    "text",
    "audio",
    "clipboard",
    "prompt",
    "email",
    "user",
)

_state: Dict[str, Any] = {
    "initialized": False,
    "enabled": False,
    "reason": "not initialised",
    "environment": "",
    "release": "",
    "consent": False,
}


# ---------------------------------------------------------------------------
# Consent + configuration
# ---------------------------------------------------------------------------


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def dsn() -> str:
    """Resolve the desktop DSN at runtime; never baked into the build.

    Priority:
      1. ``SENTRY_DSN`` in the environment (tests, CI, manual runs);
      2. a file whose absolute path is in ``SENTRY_DSN_FILE`` and whose entire
         contents are the DSN — machine-level configuration for frozen builds,
         where editing the environment of the installed app is impractical.
         The file is read only when the build is frozen, so a developer
         workstation cannot pick one up by accident.

    No DSN ever travels inside the PyInstaller bundle, the installer or the
    source tree: shipping one would embed a secret in an artifact that users
    can unpack, and would enable reporting before the user has opted in.
    """
    from_env = _env("SENTRY_DSN")
    if from_env:
        return from_env
    if getattr(sys, "frozen", False):
        return _read_dsn_file()
    return ""


def _read_dsn_file() -> str:
    """Read the DSN named by ``SENTRY_DSN_FILE`` (frozen builds only)."""
    path = _env("SENTRY_DSN_FILE")
    if not path:
        return ""
    try:
        value = Path(path).read_text(encoding="utf-8-sig").strip()
    except OSError:
        logger.warning("SENTRY_DSN_FILE points at an unreadable file; ignoring it")
        return ""
    if not value.startswith(("http://", "https://")):
        logger.warning("SENTRY_DSN_FILE does not contain a DSN URL; ignoring it")
        return ""
    return value


def consent_from_environment() -> bool:
    """Developer/CI override. Not the user-facing switch."""
    return _env("SENTRY_DESKTOP_CRASH_REPORTS").lower() in _TRUTHY


def consent_from_config(config: Optional[dict]) -> bool:
    """User-facing switch: Settings → Privacy → Send crash reports."""
    if not config:
        return False
    return bool(config.get("share_crash_reports", False))


def environment() -> str:
    override = _env("SENTRY_ENVIRONMENT")
    if override:
        return override
    return "production" if getattr(sys, "frozen", False) else "development"


def release_name() -> str:
    return _env("SENTRY_RELEASE") or f"voxylis-desktop@{__version__}"


def _sample_rate() -> float:
    raw = _env("SENTRY_TRACES_SAMPLE_RATE")
    if raw:
        try:
            return max(0.0, min(1.0, float(raw)))
        except ValueError:
            pass
    return 0.1 if environment() == "production" else 1.0


# ---------------------------------------------------------------------------
# Scrubbing
# ---------------------------------------------------------------------------


def _redact_paths(value: str) -> str:
    """Replace the user's profile directory with a placeholder."""
    try:
        from utils import paths

        root = str(paths.user_data_root())
        home = str(Path.home())
    except Exception:  # pragma: no cover - import/config problems
        root, home = "", ""
    for candidate, placeholder in ((root, r"%VOXYLIS_HOME%"), (home, r"%USERPROFILE%")):
        if candidate:
            value = re.sub(re.escape(candidate), placeholder, value, flags=re.IGNORECASE)
    return value


def _is_sensitive(key: str) -> bool:
    lowered = str(key).lower()
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)


def scrub(value: Any, depth: int = 0) -> Any:
    """Recursively redact credentials, user content and profile paths."""
    if depth > _MAX_DEPTH:
        return _REDACTED
    if isinstance(value, dict):
        return {
            key: (_REDACTED if _is_sensitive(key) else scrub(item, depth + 1))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [scrub(item, depth + 1) for item in value]
    if isinstance(value, str):
        if len(value) > 400:
            return f"[{len(value)} chars withheld]"
        return _redact_paths(value)
    return value


def _drop_frame_locals(event: dict) -> None:
    """Frame locals are where a raw key or transcript would sit: drop them."""
    # A capture_message() event has no ``exception`` — its stack lives under
    # ``threads.values[].stacktrace``, which needs the same treatment.
    sections = []
    exception = event.get("exception")
    if isinstance(exception, dict):
        sections.extend(exception.get("values") or [])
    threads = event.get("threads")
    if isinstance(threads, dict):
        sections.extend(threads.get("values") or [])
    for entry in sections:
        if not isinstance(entry, dict):
            continue
        stacktrace = entry.get("stacktrace") if isinstance(entry, dict) else None
        for frame in (stacktrace or {}).get("frames", []) or []:
            if isinstance(frame, dict):
                frame.pop("vars", None)


def before_send(event: dict, hint: Optional[dict] = None) -> Optional[dict]:  # noqa: ARG001
    event.pop("query_string", None)
    _drop_frame_locals(event)
    request = event.get("request")
    if isinstance(request, dict):
        request.clear()
    for section in ("extra", "contexts", "breadcrumbs", "tags"):
        if section in event:
            event[section] = scrub(event[section])
    if "exception" in event:
        event["exception"] = scrub(event["exception"])
    if event.get("message"):
        event["message"] = scrub(str(event["message"]))
    # Exception text is free text: it can embed a profile path (which contains
    # the Windows account name) or a repr of user data, and the key-based
    # scrub cannot see inside a plain string.
    exception = event.get("exception")
    values = exception.get("values") if isinstance(exception, dict) else None
    for entry in values or []:
        if isinstance(entry, dict) and isinstance(entry.get("value"), str):
            entry["value"] = _redact_paths(entry["value"][:400])
    logentry = event.get("logentry")
    if isinstance(logentry, dict) and isinstance(logentry.get("formatted"), str):
        logentry["formatted"] = _redact_paths(logentry["formatted"][:400])
    event.pop("user", None)
    return event


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


def init_observability(config: Optional[dict] = None) -> bool:
    """Start crash reporting when a DSN and consent are both present."""
    if _state["initialized"]:
        return bool(_state["enabled"])
    _state["initialized"] = True

    configured_dsn = dsn()
    consent = consent_from_config(config) or consent_from_environment()
    _state["consent"] = consent
    _state["environment"] = environment()
    _state["release"] = release_name()

    if not configured_dsn:
        _state["reason"] = "no DSN is configured (SENTRY_DSN / SENTRY_DSN_FILE)"
        logger.debug("Crash reporting off: no SENTRY_DSN")
        return False
    if not consent:
        _state["reason"] = "crash reporting is off in Settings → Privacy"
        logger.debug("Crash reporting off: user has not opted in")
        return False

    try:
        import sentry_sdk
    except ImportError:
        _state["reason"] = "sentry-sdk is not installed"
        logger.warning(
            "Crash reports are enabled in Settings but sentry-sdk is missing; "
            "no reports will be sent."
        )
        return False

    try:
        sentry_sdk.init(
            dsn=configured_dsn,
            environment=_state["environment"],
            release=_state["release"],
            traces_sample_rate=_sample_rate(),
            max_request_body_size="never",
            send_default_pii=False,
            attach_stacktrace=True,
            before_send=before_send,
            profiles_sample_rate=0.0,
        )
        sentry_sdk.set_tag("platform", sys.platform)
        sentry_sdk.set_tag("python", platform.python_version())
        sentry_sdk.set_tag("frozen", str(getattr(sys, "frozen", False)).lower())
    except Exception as exc:  # pragma: no cover - transport/SDK problems
        _state["enabled"] = False
        _state["reason"] = f"sentry_sdk.init failed: {type(exc).__name__}"
        logger.warning("Crash reporting could not start (%s); continuing without it", type(exc).__name__)
        return False

    _state["enabled"] = True
    _state["reason"] = "active"
    logger.info(
        "Crash reporting enabled (release=%s environment=%s)",
        _state["release"],
        _state["environment"],
    )
    return True


def set_consent(enabled: bool, config: Optional[dict] = None) -> bool:
    """Apply a live change from the Privacy page.

    Turning reporting off takes effect immediately; turning it on starts the SDK
    only when a DSN is resolvable in the machine's environment (never one baked
    into the build).
    """
    if not enabled:
        if _state["enabled"]:
            try:
                import sentry_sdk

                sentry_sdk.init(dsn="")  # disable the client
            except Exception:  # pragma: no cover
                pass
        _state["enabled"] = False
        _state["consent"] = False
        _state["reason"] = "turned off by the user"
        return False
    _state["initialized"] = False
    return init_observability(config)


def is_enabled() -> bool:
    return bool(_state["enabled"])


def status() -> Dict[str, Any]:
    """Redacted status for the diagnostics bundle."""
    return {
        "enabled": bool(_state["enabled"]),
        "consent": bool(_state["consent"]),
        "reason": _state["reason"],
        "environment": _state["environment"],
        "release": _state["release"],
        "dsn_configured": bool(dsn()),
        "install_available": _sdk_available(),
    }


def _sdk_available() -> bool:
    try:
        import sentry_sdk  # noqa: F401

        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Capture helpers — safe no-ops when reporting is off
# ---------------------------------------------------------------------------


def capture_exception(exc: BaseException, category: str = "unexpected", **extra: Any) -> None:
    if not _state["enabled"]:
        return
    try:
        import sentry_sdk

        with sentry_sdk.new_scope() as scope:
            scope.set_tag("error_category", category)
            scope.set_tag("app_version", __version__)
            for key, value in (extra or {}).items():
                scope.set_extra(key, scrub(value))
            sentry_sdk.capture_exception(exc)
    except Exception:  # pragma: no cover - never let monitoring break the app
        pass


def capture_error(error, category: str = "pipeline", **extra: Any) -> None:
    """Report a classified :class:`core.errors.VoxylisError` as a message.

    Classified errors are expected states (bad key, no microphone), so they are
    reported without a stack trace and without the user-facing prose.
    """
    if not _state["enabled"]:
        return
    code = getattr(error, "code", "unknown")
    try:
        import sentry_sdk

        with sentry_sdk.new_scope() as scope:
            scope.set_tag("error_category", category)
            scope.set_tag("error_code", str(code))
            scope.set_tag("retryable", str(bool(getattr(error, "retryable", False))).lower())
            scope.set_extra("detail", scrub(getattr(error, "detail", "") or ""))
            scope.set_level("warning")
            sentry_sdk.capture_message(f"voxylis error: {code}", level="warning")
    except Exception:  # pragma: no cover
        pass


def capture_message(message: str, level: str = "warning", category: str = "", **extra: Any) -> None:
    """Report a notable event that is not an exception (a recoverable failure)."""
    if not _state["enabled"]:
        return
    try:
        import sentry_sdk

        with sentry_sdk.new_scope() as scope:
            if category:
                scope.set_tag("error_category", category)
            for key, value in (extra or {}).items():
                scope.set_extra(key, scrub(value))
            sentry_sdk.capture_message(str(scrub(message)), level=level)
    except Exception:  # pragma: no cover
        pass


def capture_stage_failure(stage: str, exc: BaseException) -> None:
    """Report a failure inside a named pipeline stage."""
    capture_exception(exc, category="pipeline", stage=stage)


def capture_startup_failure(exc: BaseException) -> None:
    capture_exception(exc, category="startup")
