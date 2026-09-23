"""
User-facing error model.

Developer strings such as ``Error: HTTP 401`` are useless to a non-technical
user, and useless to us in a bug report.  Every failure that can reach the user
is classified into a :class:`VoxylisError` that answers three questions:

    what happened  -> ``summary``
    why it happened -> ``cause``
    what to do now  -> ``action``

Technical detail is kept separately in ``diagnostics`` and is only revealed
behind the "Show diagnostics" disclosure in the error dialog.  Nothing here is
ever populated with a credential: use :func:`utils.credentials.redact`.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VoxylisError:
    code: str
    title: str
    summary: str
    cause: str = ""
    action: str = ""
    diagnostics: str = ""
    retryable: bool = False
    settings_section: str = ""
    docs_slug: str = ""
    detail: str = field(default="", repr=False)

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "title": self.title,
            "summary": self.summary,
            "cause": self.cause,
            "action": self.action,
            "diagnostics": self.diagnostics,
            "retryable": self.retryable,
            "settings_section": self.settings_section,
        }

    def __str__(self) -> str:
        return f"{self.code}: {self.summary}"


_CATALOG = {
    "no_api_key": VoxylisError(
        code="no_api_key",
        title="No AI provider configured",
        summary="Voxylis needs a speech-to-text key before it can transcribe.",
        cause="No Groq or OpenAI credential is stored yet.",
        action="Open Settings → AI Providers and paste a free Groq key, then try again.",
        settings_section="AI Providers",
        docs_slug="configuration",
    ),
    "invalid_api_key": VoxylisError(
        code="invalid_api_key",
        title="{provider} rejected the API key",
        summary="Your API key was rejected by {provider}.",
        cause="The key is wrong, expired, or was revoked.",
        action="Check the key in Settings → AI Providers, or create a new one and paste it there.",
        retryable=True,
        settings_section="AI Providers",
        docs_slug="configuration",
    ),
    "rate_limited": VoxylisError(
        code="rate_limited",
        title="{provider} is throttling requests",
        summary="Too many requests were sent in a short window.",
        cause="Free provider tiers allow a limited number of requests per minute.",
        action="Wait a few seconds and try again. Voxylis will retry automatically.",
        retryable=True,
        docs_slug="troubleshooting",
    ),
    "quota_exceeded": VoxylisError(
        code="quota_exceeded",
        title="Provider quota exhausted",
        summary="{provider} reports that the account quota is used up.",
        cause="The free allowance for this billing period has been consumed.",
        action="Wait for the quota to reset, switch provider in Settings → AI Providers, or upgrade the provider plan.",
        settings_section="AI Providers",
        docs_slug="troubleshooting",
    ),
    "network_error": VoxylisError(
        code="network_error",
        title="No connection to the AI provider",
        summary="Voxylis could not reach {provider}.",
        cause="The network is offline, blocked by a firewall/proxy, or the provider is down.",
        action="Check your internet connection and try again. Your recording is kept until the pipeline finishes.",
        retryable=True,
        docs_slug="troubleshooting",
    ),
    "provider_unavailable": VoxylisError(
        code="provider_unavailable",
        title="AI provider unavailable",
        summary="Every configured provider failed.",
        cause="Credentials are missing or all providers are unreachable.",
        action="Open Settings → AI Providers to verify your keys. Voice commands still work without AI.",
        settings_section="AI Providers",
        docs_slug="troubleshooting",
    ),
    "mic_unavailable": VoxylisError(
        code="mic_unavailable",
        title="Microphone unavailable",
        summary="Voxylis could not open the selected microphone.",
        cause="Another application may be using it exclusively, it may be unplugged, or access is denied by Windows privacy settings.",
        action="Close other recording apps, then pick a device in Settings → Microphone.",
        settings_section="Microphone",
        docs_slug="troubleshooting",
    ),
    "no_speech": VoxylisError(
        code="no_speech",
        title="Nothing was recorded",
        summary="No speech was detected in that recording.",
        cause="The microphone may be muted, too quiet, or the recording was silent.",
        action="Check the input level meter in Settings → Microphone and try again.",
        settings_section="Microphone",
        docs_slug="tips-tricks",
    ),
    "transcription_failed": VoxylisError(
        code="transcription_failed",
        title="Transcription failed",
        summary="{provider} did not return any text for this recording.",
        cause="The audio may have been too short, too noisy, or the request timed out.",
        action="Try again, speaking a little longer. If it keeps failing, check your key in Settings → AI Providers.",
        retryable=True,
        settings_section="AI Providers",
        docs_slug="troubleshooting",
    ),
    "enhancement_failed": VoxylisError(
        code="enhancement_failed",
        title="AI enhancement failed",
        summary="The text was transcribed but could not be enhanced.",
        cause="The enhancement provider rejected the request or returned an empty result.",
        action="The plain transcript is used instead. Check Settings → Enhancement.  Your text was still inserted.",
        settings_section="Enhancement",
        docs_slug="configuration",
    ),
    "injection_failed": VoxylisError(
        code="injection_failed",
        title="Could not insert the text",
        summary="Voxylis could not type into the window that had focus.",
        cause="{cause}",
        action="Click into the field you want the text in, then press the hotkey again. The text is also in History so you can copy it.",
        docs_slug="troubleshooting",
    ),
    "recording_failed": VoxylisError(
        code="recording_failed",
        title="Recording failed",
        summary="The recording could not be captured.",
        cause="The audio device stopped or returned no samples.",
        action="Try again. If it repeats, pick a different device in Settings → Microphone.",
        settings_section="Microphone",
        docs_slug="troubleshooting",
    ),
    "hotkey_conflict": VoxylisError(
        code="hotkey_conflict",
        title="Shortcut conflict",
        summary="{cause}",
        cause="{cause}",
        action="Choose a different shortcut in Settings → Shortcuts, or reset to the default (Win+Shift).",
        settings_section="Shortcuts",
        docs_slug="configuration",
    ),
    "hotkey_listener_failed": VoxylisError(
        code="hotkey_listener_failed",
        title="Global shortcuts stopped working",
        summary="The keyboard listener stopped unexpectedly.",
        cause="Windows blocked the low-level keyboard hook, or another app grabbed the shortcut.",
        action="Restart Voxylis. If it keeps happening, enable 'Disable global shortcuts' in Settings → Shortcuts and use the tray menu instead.",
        settings_section="Shortcuts",
        docs_slug="troubleshooting",
    ),
    "history_disabled": VoxylisError(
        code="history_disabled",
        title="History is turned off",
        summary="This recording was not saved to history.",
        cause="'Save transcription history' is disabled in Settings → Privacy.",
        action="Enable it in Settings → Privacy if you want transcriptions stored locally.",
        settings_section="Privacy",
        docs_slug="configuration",
    ),
    "pipeline_error": VoxylisError(
        code="pipeline_error",
        title="Something went wrong",
        summary="The voice pipeline hit an unexpected error.",
        cause="{cause}",
        action="Try again. If it repeats, use Help → Copy diagnostics and include it in a bug report.",
        retryable=True,
        docs_slug="troubleshooting",
    ),
    "update_failed": VoxylisError(
        code="update_failed",
        title="Update failed",
        summary="Voxylis could not download or verify the update.",
        cause="{cause}",
        action="Try again later, or download the installer manually from the website.",
        retryable=True,
        docs_slug="installation",
    ),
}


def friendly_error(code: str, **context) -> VoxylisError:
    """Build a :class:`VoxylisError` from the catalog, filling placeholders."""
    template = _CATALOG.get(code) or _CATALOG["pipeline_error"]
    data = template.as_dict()
    data["detail"] = str(context.get("detail", ""))
    for key, value in context.items():
        if key == "detail":
            continue
        for field_name in ("summary", "cause", "action", "title"):
            marker = "{" + key + "}"
            if marker in data[field_name]:
                data[field_name] = data[field_name].replace(marker, str(value))
    context.setdefault("provider", "the AI provider")
    for field_name in ("summary", "cause", "action", "title"):
        if "{provider}" in data[field_name]:
            data[field_name] = data[field_name].replace("{provider}", str(context.get("provider", "the AI provider")))
        if "{cause}" in data[field_name]:
            data[field_name] = data[field_name].replace("{cause}", data["cause"] or "An unknown cause.")
    return VoxylisError(**data)


def classify_exception(exc: BaseException, provider: str = "") -> VoxylisError:
    """Map a raw exception onto the closest catalog entry."""
    text = f"{type(exc).__name__}: {exc}".lower()
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)

    if status == 401 or "401" in text or "invalid api key" in text or "unauthorized" in text:
        return friendly_error("invalid_api_key", provider=provider or "the AI provider", detail=str(exc))
    if status == 429 or "429" in text or "rate limit" in text:
        return friendly_error("rate_limited", provider=provider or "the AI provider", detail=str(exc))
    quota_markers = ("quota", "insufficient_quota", "billing")
    if any(marker in text for marker in quota_markers):
        return friendly_error("quota_exceeded", provider=provider or "the AI provider", detail=str(exc))
    if isinstance(exc, (TimeoutError,)) or "timeout" in text or "timed out" in text:
        return friendly_error("network_error", provider=provider or "the AI provider", detail=str(exc))
    connection_markers = ("connection", "network", "getaddrinfo")
    if isinstance(exc, ConnectionError) or any(m in text for m in connection_markers):
        return friendly_error("network_error", provider=provider or "the AI provider", detail=str(exc))
    audio_failure_markers = (
        "audiodevice",
        "portaudio",
        "no default input device",
        "unanticipated host error",
    )
    if any(marker in text for marker in audio_failure_markers):
        return friendly_error("mic_unavailable", detail=str(exc))
    return friendly_error("pipeline_error", cause=str(exc), detail=str(exc))


def catalog() -> dict:
    return dict(_CATALOG)
