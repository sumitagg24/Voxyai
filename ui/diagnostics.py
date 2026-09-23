"""
Redacted diagnostics collection.

Everything here is safe to paste into a public bug report: no transcripts, no
API keys, no session tokens, no email addresses.  Secrets are reported only as
``configured: true/false`` or as ``abcd****`` hints produced by
:func:`utils.credentials.redact`.
"""

from __future__ import annotations

import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import version
from utils import credentials, paths


def _safe(fn, default=None):
    try:
        return fn()
    except Exception as exc:  # pragma: no cover - diagnostics must never raise
        return f"<unavailable: {type(exc).__name__}>" if default is None else default


def collect(orchestrator=None, extra: Optional[dict] = None) -> dict:
    """Build the redacted diagnostics payload."""
    data = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "app": {
            "name": version.APP_NAME,
            "version": version.__version__,
            "channel": version.UPDATE_CHANNEL,
            "engine": version.ENGINE_NAME,
        },
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
            "frozen": paths.is_frozen(),
            "frozen_note": "packaged build" if paths.is_frozen() else "source checkout",
        },
        # Paths are included because they are the first thing support needs,
        # but the home directory is collapsed to `~`.
        "paths": _collapse_home(paths.describe_paths()),
        "credentials": _safe(lambda: credentials.credential_store.describe()),
    }

    if orchestrator is not None:
        data["providers"] = _safe(orchestrator.provider_status)
        data["injection"] = _safe(orchestrator.injector.diagnostics)
        data["shortcuts"] = _safe(orchestrator.hotkey_listener.describe)
        data["status"] = _safe(orchestrator.get_status)
        history = getattr(orchestrator, "history", None)
        if history is not None:
            data["history"] = _safe(
                lambda: {
                    "enabled": history.enabled,
                    "max_entries": history.max_entries,
                    "stored_entries": len(history),
                    "database": "sqlite",
                }
            )
        if data.get("status", {}).get("last_transcript"):
            # Never include transcript text, not even a prefix.
            data["status"]["last_transcript"] = "<redacted>"
        error = getattr(orchestrator, "last_error", None)
        if error is not None:
            data["last_error"] = {
                "code": error.code,
                "summary": error.summary,
                "detail": error.detail,
            }

    data["audio"] = _safe(_audio_devices)
    if extra:
        data.update(extra)
    return data


def _audio_devices() -> dict:
    from audio.recorder import AudioRecorder

    recorder = AudioRecorder()
    devices = recorder.list_devices()
    names = []
    for device in devices:
        name = device.get("name") if isinstance(device, dict) else getattr(device, "name", None)
        if name:
            names.append(str(name))
    return {
        "count": len(names),
        "devices": names[:12],
        "default_input": _safe(_default_input_name),
    }


def _default_input_name() -> str:
    import sounddevice as sd

    device = sd.query_devices(kind="input")
    if device is None:
        return "none"
    try:
        return str(device["name"])
    except Exception:
        return str(getattr(device, "name", "unknown"))


def _collapse_home(payload: dict) -> dict:
    """Replace the user's home directory with ``~`` in reported paths."""
    home = str(Path.home())
    out = {}
    for key, value in payload.items():
        if isinstance(value, str) and home and home in value:
            out[key] = value.replace(home, "~")
        else:
            out[key] = value
    return out


def as_text(payload: Optional[dict] = None, orchestrator=None) -> str:
    """Render diagnostics as plain text suitable for pasting into an issue."""
    import json

    data = payload if payload is not None else collect(orchestrator)
    lines = [
        f"Voxylis diagnostics — {data.get('app', {}).get('version', '?')}",
        f"Generated: {data.get('generated_at', '')}",
        "",
    ]
    lines.append(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    lines.append("")
    lines.append("(No transcripts, API keys, tokens or email addresses are included.)")
    return "\n".join(lines)
