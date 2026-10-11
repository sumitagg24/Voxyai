"""P6.8: the desktop update flow, end to end against a locally stubbed feed.

check() (feed URL -> manifest) -> version comparison -> download() ->
SHA-256 + size verification -> launch_installer gating. The feed and the
installer bytes are served from a local HTTP server, so the test exercises
the real network path with no external dependency.

Set ``VOXYLIS_UPDATE_E2E_NETWORK=1`` to additionally run the live-feed checks
against the real GitHub releases (skipped by default; CI has no reason to
depend on github.com being up).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from config import version
from core import updater as updater_module
from core.updater import DownloadResult, Updater

#: A stand-in installer payload: 64 KiB of bytes, as if it were the .exe.
FAKE_INSTALLER = b"MZ" + bytes(range(256)) * 256
FAKE_SHA256 = hashlib.sha256(FAKE_INSTALLER).hexdigest()
FAKE_SIZE = len(FAKE_INSTALLER)

STUB_VERSION = "3.1.0"


class _FeedHandler(BaseHTTPRequestHandler):
    """Serves the manifest and the installer bytes for one stub release."""

    base_url = ""

    def do_GET(self):  # noqa: N802  (http.server API)
        if self.path == "/update-manifest.json":
            manifest = {
                "version": STUB_VERSION,
                "channel": "stable",
                "notes": f"{self.base_url}/release-notes",
                "installers": {
                    "windows": {
                        "url": f"{self.base_url}/Voxylis-Setup-{STUB_VERSION}.exe",
                        "sha256": FAKE_SHA256,
                        "size": FAKE_SIZE,
                    }
                },
            }
            body = json.dumps(manifest).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == f"/Voxylis-Setup-{STUB_VERSION}.exe":
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(FAKE_SIZE))
            self.end_headers()
            self.wfile.write(FAKE_INSTALLER)
        elif self.path == "/garbage-manifest.json":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"this is not json")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):  # silence request logging in test output
        pass


@pytest.fixture
def stub_feed():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FeedHandler)
    port = server.server_address[1]
    _FeedHandler.base_url = f"http://127.0.0.1:{port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield _FeedHandler.base_url
    server.shutdown()
    thread.join(timeout=5)


@pytest.fixture
def installed_3000(monkeypatch):
    """Pretend this client is the previous release (installed == 3.0.0)."""
    monkeypatch.setattr(version, "__version__", "3.0.0")
    yield


def _updater(base_url: str) -> Updater:
    return Updater(feed_url=f"{base_url}/update-manifest.json")


def test_check_reports_newer_release_with_checksum(stub_feed, installed_3000):
    info = _updater(stub_feed).check()
    assert info.error == ""
    assert info.available is True
    assert info.latest == STUB_VERSION
    assert info.sha256 == FAKE_SHA256
    assert info.size == FAKE_SIZE
    # The version comparison itself: 3.1.0 must rank above the installed 3.0.0.
    assert updater_module._version_tuple(STUB_VERSION) > updater_module._version_tuple(version.__version__)


def test_check_says_up_to_date_when_feed_matches_installed(stub_feed, monkeypatch):
    monkeypatch.setattr(version, "__version__", STUB_VERSION)
    info = _updater(stub_feed).check()
    assert info.available is False
    assert info.latest == STUB_VERSION


def test_check_degrades_gracefully_on_malformed_feed(stub_feed, installed_3000):
    broken = Updater(feed_url=f"{stub_feed}/garbage-manifest.json")
    info = broken.check()
    assert info.available is False
    assert info.error == "unavailable"  # fetch_manifest rejects the bad JSON


def test_download_verifies_sha256_and_size(stub_feed, installed_3000):
    updater = _updater(stub_feed)
    info = updater.check()
    result = updater.download(info)
    assert result.ok is True
    assert result.verified is True
    assert result.path is not None and result.path.is_file()
    assert result.path.stat().st_size == FAKE_SIZE
    assert hashlib.sha256(result.path.read_bytes()).hexdigest() == FAKE_SHA256


@pytest.fixture
def popen_recorder(monkeypatch):
    """Record subprocess.Popen calls instead of ever executing a file."""
    calls: list = []

    def fake_popen(args, **kwargs):  # noqa: ANN001, ANN202
        calls.append(args)
        return object()

    monkeypatch.setattr(updater_module.subprocess, "Popen", fake_popen)
    return calls


def test_launch_installer_refuses_unverified_results(stub_feed, installed_3000, popen_recorder):
    updater = _updater(stub_feed)

    # Never downloaded anything: refused.
    assert updater.launch_installer(DownloadResult()) is False
    # Downloaded but not verified: refused.
    not_verified = DownloadResult(ok=True, path=None, verified=False)
    assert updater.launch_installer(not_verified) is False
    # Path-typed call (old contract) is refused too, not silently misused.
    assert updater.launch_installer("/tmp/anything.exe") is False
    assert popen_recorder == []


def test_launch_installer_refuses_tampered_file_after_download(stub_feed, installed_3000, popen_recorder):
    updater = _updater(stub_feed)
    info = updater.check()
    result = updater.download(info)
    assert result.verified is True

    # Swap the bytes on disk between download and launch.
    result.path.write_bytes(b"tampered payload")
    assert updater.launch_installer(result) is False
    assert popen_recorder == [], "a tampered installer must never be executed"


def test_launch_installer_runs_only_the_verified_download(stub_feed, installed_3000, popen_recorder, monkeypatch):
    updater = _updater(stub_feed)
    info = updater.check()
    result = updater.download(info)
    assert result.verified is True

    # Force the Windows branch regardless of the host OS so the spawn path
    # itself is what gets tested.
    monkeypatch.setattr(sys, "platform", "win32")
    assert updater.launch_installer(result) is True
    assert len(popen_recorder) == 1
    assert popen_recorder[0] == [str(result.path)]


def test_download_rejects_checksum_mismatch_from_feed(stub_feed, installed_3000):
    """A manifest whose checksum does not match the served bytes must not
    produce a verified download (and launch_installer then refuses it)."""
    original = _FeedHandler.do_GET

    def lying_manifest(self):
        if self.path == "/update-manifest.json":
            manifest = {
                "version": STUB_VERSION,
                "channel": "stable",
                "installers": {
                    "windows": {
                        "url": f"{self.base_url}/Voxylis-Setup-{STUB_VERSION}.exe",
                        "sha256": "0" * 64,
                        "size": FAKE_SIZE,
                    }
                },
            }
            body = json.dumps(manifest).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            original(self)

    _FeedHandler.do_GET = lying_manifest
    try:
        updater = _updater(stub_feed)
        info = updater.check()
        result = updater.download(info)
        assert result.ok is True
        assert result.verified is False
        assert "checksum" in result.detail.lower()
    finally:
        _FeedHandler.do_GET = original


# ── live-feed checks (opt-in: VOXYLIS_UPDATE_E2E_NETWORK=1) ──────────────────

_live = pytest.mark.skipif(
    not os.environ.get("VOXYLIS_UPDATE_E2E_NETWORK"),
    reason="live GitHub feed check; set VOXYLIS_UPDATE_E2E_NETWORK=1 to run",
)


@_live
def test_real_latest_release_serves_a_wellformed_manifest():
    """The updater's default feed must be a parseable manifest on the Latest
    release, with a checksummed windows entry (a 3.0.0 client then correctly
    reports 'up to date' until a newer release is published)."""
    import requests

    response = requests.get(updater_module.DEFAULT_FEED, timeout=15)
    assert response.status_code == 200, response.status_code
    manifest = response.json()
    assert manifest["version"] >= "3.0.0"
    windows = manifest["installers"]["windows"]
    assert windows["url"].endswith(".exe")
    assert len(windows["sha256"]) == 64 and windows["size"] > 0

    # The manifest's checksum must describe the actual published asset: ask
    # GitHub's API for the asset digest and compare (no 70 MB download).
    latest = requests.get("https://api.github.com/repos/sumitagg24/Voxyai/releases/latest", timeout=15).json()
    digest = next(a["digest"] for a in latest["assets"] if a["name"].endswith(".exe"))
    assert windows["sha256"] in digest, "manifest checksum disagrees with the published asset"
    assert windows["size"] == next(a["size"] for a in latest["assets"] if a["name"].endswith(".exe"))

    info = Updater().check()
    assert info.latest == manifest["version"]
