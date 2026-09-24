"""
Update flow for the Voxylis desktop app.

Design rules
------------
  * **Never replace a running binary.** The updater downloads an installer into
    ``%LOCALAPPDATA%\\Voxylis\\updates``, verifies its size and SHA-256 against
    the release manifest, then hands off to the installer, which is the only
    component allowed to move files.
  * **Verify before executing.** A download without a published checksum is
    reported as unverifiable and is not launched.
  * **Always degrade gracefully.** An unreachable update feed is not an error
    the user needs to see; it is logged and the app continues.

The manifest is a small JSON document (see ``docs/RELEASE.md``)::

    {
      "version": "3.0.1",
      "channel": "stable",
      "notes": "https://github.com/sumitagg24/Voxyai/releases/tag/v3.0.1",
      "installers": {
        "windows": {
          "url": "https://.../Voxylis-Setup-3.0.1.exe",
          "sha256": "…",
          "size": 12345678
        }
      }
    }
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import requests

from config import version
from utils import paths
from utils.logger import log_error, log_info, log_warning

DEFAULT_FEED = os.environ.get(
    "VOXYLIS_UPDATE_FEED",
    f"{version.RELEASES_URL}/latest/download/update-manifest.json",
)

TIMEOUT = 12
CHUNK = 64 * 1024
MANIFEST_CACHE = "update-manifest.json"


def _version_tuple(text: str) -> tuple:
    parts = []
    for chunk in str(text).lstrip("vV").split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


@dataclass
class UpdateInfo:
    available: bool = False
    current: str = version.__version__
    latest: str = ""
    notes_url: str = ""
    channel: str = version.UPDATE_CHANNEL
    download_url: str = ""
    sha256: str = ""
    size: int = 0
    error: str = ""

    def as_dict(self) -> dict:
        return {
            "available": self.available,
            "current": self.current,
            "latest": self.latest,
            "notes_url": self.notes_url,
            "channel": self.channel,
            "size": self.size,
            "has_checksum": bool(self.sha256),
            "error": self.error,
        }


@dataclass
class DownloadResult:
    ok: bool = False
    path: Optional[Path] = None
    detail: str = ""
    verified: bool = False
    error: str = ""
    progress: list = field(default_factory=list)


class Updater:
    """Checks for, downloads and hands off updates."""

    def __init__(self, feed_url: str = DEFAULT_FEED):
        self.feed_url = feed_url

    # ── manifest ─────────────────────────────────────────────────────────

    def fetch_manifest(self) -> Optional[dict]:
        try:
            response = requests.get(self.feed_url, timeout=TIMEOUT)
            if response.status_code == 404:
                log_info("No update manifest published yet")
                return None
            response.raise_for_status()
            manifest = response.json()
            if not isinstance(manifest, dict) or "version" not in manifest:
                log_warning("Update manifest is malformed")
                return None
            try:
                (paths.cache_dir() / MANIFEST_CACHE).write_text(json.dumps(manifest), encoding="utf-8")
            except OSError:
                pass
            return manifest
        except requests.RequestException as exc:
            log_info(f"Update check failed (offline or unpublished): {exc}")
            cached = self._cached_manifest()
            return cached
        except (ValueError, TypeError) as exc:
            log_warning(f"Update manifest could not be parsed: {exc}")
            return None

    def _cached_manifest(self) -> Optional[dict]:
        try:
            path = paths.cache_dir() / MANIFEST_CACHE
            if path.is_file():
                return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
        return None

    def _platform_key(self) -> str:
        if sys.platform.startswith("win"):
            return "windows"
        if sys.platform == "darwin":
            return "macos"
        return "linux"

    def check(self) -> UpdateInfo:
        """Return whether a newer version is published."""
        info = UpdateInfo()
        manifest = self.fetch_manifest()
        if not manifest:
            info.error = "unavailable"
            return info

        latest = str(manifest.get("version", "")).strip()
        if not latest:
            info.error = "manifest-missing-version"
            return info
        info.latest = latest
        info.channel = str(manifest.get("channel") or version.UPDATE_CHANNEL)
        info.notes_url = str(manifest.get("notes") or "")

        if _version_tuple(latest) <= _version_tuple(version.__version__):
            return info

        installer = (manifest.get("installers") or {}).get(self._platform_key())
        if not isinstance(installer, dict) or not installer.get("url"):
            info.error = "no-installer-for-platform"
            return info

        info.available = True
        info.download_url = str(installer.get("url"))
        info.sha256 = str(installer.get("sha256") or "")
        info.size = int(installer.get("size") or 0)
        return info

    # ── download ─────────────────────────────────────────────────────────

    def _verify(self, path: Path, expected_sha256: str, expected_size: int) -> tuple:
        if expected_size and path.stat().st_size != expected_size:
            return False, f"size mismatch (expected {expected_size}, got {path.stat().st_size})"
        if expected_sha256:
            digest = hashlib.sha256()
            with open(path, "rb") as handle:
                for block in iter(lambda: handle.read(CHUNK), b""):
                    digest.update(block)
            if digest.hexdigest().lower() != expected_sha256.lower():
                return False, "checksum mismatch"
            return True, "checksum verified"
        return False, "no checksum published — update cannot be verified"

    def download(
        self,
        info: UpdateInfo,
        progress: Optional[Callable[[int, int], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> DownloadResult:
        result = DownloadResult()
        if not info.available or not info.download_url:
            result.error = "no-update"
            result.detail = "No update to download."
            return result

        target = paths.updates_dir() / f"Voxylis-Setup-{info.latest}.exe"
        partial = target.with_suffix(".part")
        try:
            with requests.get(info.download_url, stream=True, timeout=TIMEOUT * 4) as response:
                response.raise_for_status()
                total = int(response.headers.get("Content-Length") or info.size or 0)
                done = 0
                with open(partial, "wb") as handle:
                    for block in response.iter_content(CHUNK):
                        if cancel_event is not None and cancel_event.is_set():
                            handle.close()
                            partial.unlink(missing_ok=True)
                            result.error = "cancelled"
                            result.detail = "Download cancelled."
                            return result
                        if not block:
                            continue
                        handle.write(block)
                        done += len(block)
                        if progress is not None:
                            progress(done, total)
                        result.progress.append(done)
        except (requests.RequestException, OSError) as exc:
            partial.unlink(missing_ok=True)
            result.error = "download-failed"
            result.detail = str(exc)
            log_error(f"Update download failed: {exc}")
            return result

        os.replace(partial, target)
        verified, detail = self._verify(target, info.sha256, info.size)
        result.path = target
        result.verified = verified
        result.ok = True
        result.detail = detail
        if not verified:
            log_warning(f"Update downloaded but not verified: {detail}")
        else:
            log_info(f"Update {info.latest} downloaded and verified")
        return result

    # ── apply ────────────────────────────────────────────────────────────

    def launch_installer(self, path: Path, silent: bool = False) -> bool:
        """Run the verified installer. The app must exit for files to replace."""
        if not path or not path.is_file():
            return False
        if sys.platform.startswith("win"):
            args = [str(path)]
            if silent:
                args += ["/SILENT", "/CLOSEAPPLICATIONS"]
            try:
                subprocess.Popen(args, close_fds=True)
                return True
            except OSError as exc:
                log_error(f"Could not start the installer: {exc}")
                return False
        # Non-Windows builds are source bundles; open the release page instead.
        return open_release_page(f"file://{path}")

    def diagnostics(self) -> dict:
        return {
            "feed": self.feed_url,
            "channel": version.UPDATE_CHANNEL,
            "current": version.__version__,
            "updates_dir": str(paths.updates_dir()),
        }


def open_release_page(url: str = "") -> bool:
    """Open a URL in the default browser (manual download fallback)."""
    import webbrowser

    target = url or version.RELEASES_URL
    try:
        webbrowser.open(target)
        return True
    except Exception as exc:  # pragma: no cover
        log_error(f"Could not open {target}: {exc}")
        return False


def check_async(callback: Callable[[UpdateInfo], None], feed_url: str = DEFAULT_FEED) -> threading.Thread:
    """Run :meth:`Updater.check` off the UI thread."""

    def worker() -> None:
        try:
            callback(Updater(feed_url).check())
        except Exception as exc:  # pragma: no cover - must never crash the app
            log_error(f"Update check crashed: {exc}")
            callback(UpdateInfo(error="check-failed"))

    thread = threading.Thread(target=worker, daemon=True, name="voxylis-update-check")
    thread.start()
    return thread
