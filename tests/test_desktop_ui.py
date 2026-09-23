"""
Desktop shell smoke tests.

The main window is the primary product surface, and until now nothing in the
suite touched it: a page that raised during construction or refresh would only
be discovered by a user opening that section. These tests build the real window
against a stub orchestrator so they need no microphone, hotkeys or network, and
switching sections exercises the lazy page construction the app relies on.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt5.QtWidgets", reason="PyQt5 is required for the desktop app")

from PyQt5.QtWidgets import QApplication  # noqa: E402

from config.constants import HOTKEY_DEFAULT  # noqa: E402

EXPECTED_SECTIONS = [
    "Home",
    "History",
    "Microphone",
    "AI Providers",
    "Shortcuts",
    "Privacy",
    "Account",
    "Diagnostics",
    "About",
]


class StubHistory:
    enabled = True
    max_entries = 500

    def __len__(self) -> int:
        return 0

    def db_path(self) -> str:
        return "(stub)"

    def get_all(self, limit=None):
        return []

    def get_recent(self, n: int = 10):
        return []

    def count(self) -> int:
        return 0

    def export(self, *_args, **_kwargs):
        return None

    def delete(self, *_args, **_kwargs) -> bool:
        return True

    def clear(self) -> bool:
        return True


class StubStats:
    def get_today(self) -> dict:
        return {"transcriptions": 0, "words": 0, "commands": 0}

    def get_total(self) -> dict:
        return {"transcriptions": 0, "words": 0}


class StubRecorder:
    def list_devices(self) -> list:
        return [{"index": 0, "name": "Stub Microphone"}]

    def is_recording(self) -> bool:
        return False


class StubInjector:
    def diagnostics(self) -> dict:
        return {"strategies": ["clipboard", "typing"], "last": None}


class StubHotkeyListener:
    def describe(self) -> dict:
        return {"alive": True, "enabled": True, "hotkey": HOTKEY_DEFAULT}


class StubOrchestrator:
    """Minimum surface the pages read; nothing here records or calls a provider."""

    def __init__(self) -> None:
        self.config = {
            "hotkey": HOTKEY_DEFAULT,
            "mode_hotkeys": {},
            "theme": "dark",
            "language": "auto",
            "secondary_language": "auto",
            "enhancement_mode": "formal",
            "enable_ai_enhancement": False,
            "history_enabled": True,
            "history_retention_days": 0,
            "max_history": 500,
            "auto_inject": True,
            "toggle_mode": False,
            "custom_modes": {},
            "app_profiles": {},
            "voice_commands": {},
            "audio_device": None,
            "sound_feedback": True,
            "startup_on_boot": False,
        }
        self.history = StubHistory()
        self.stats = StubStats()
        self.recorder = StubRecorder()
        self.injector = StubInjector()
        self.hotkey_listener = StubHotkeyListener()
        self.last_error = None
        self.calls: list = []

    def get_config(self, key=None, default=None):
        if key is None:
            return dict(self.config)
        return self.config.get(key, default)

    #: Config keys the app refuses to persist (the real orchestrator validates
    #: shortcuts before saving; this mirrors that contract closely enough to
    #: test the page's reaction to a refusal).
    REJECTED = {"alt+f4", "win+l"}

    def update_config(self, key, value=None) -> bool:
        self.calls.append((key, value))
        if key == "hotkey" and isinstance(value, str) and value.strip().lower() in self.REJECTED:
            return False
        if value is not None:
            self.config[key] = value
        return True

    def get_status(self) -> dict:
        return {"stage": "idle", "mode": "formal", "language": ""}

    def provider_status(self) -> dict:
        return {
            "groq": {"configured": False},
            "openai": {"configured": False},
            "openrouter": {"configured": False},
            "backend": "dpapi",
            "secure_storage": True,
            "transcriber_ready": False,
            "enhancer_ready": False,
        }

    def toggle_recording(self) -> None:
        pass

    def stop_recording(self) -> None:
        pass

    def cancel_recording(self) -> None:
        pass


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def window(qt_app):
    from ui.main_window import MainWindow

    win = MainWindow(StubOrchestrator())
    yield win
    win.close()
    win.deleteLater()


def test_main_window_exposes_every_navigation_section(window):
    labels = [window.nav.item(i).text() for i in range(window.nav.count())]
    assert labels == EXPECTED_SECTIONS


def test_window_identity_uses_the_canonical_version(window):
    from config import version

    assert window.windowTitle() == f"{version.APP_NAME} {version.__version__}"


def test_every_section_constructs_and_refreshes(window):
    """Switching sections must not raise, including the first visit."""
    failures = []
    for index in range(window.nav.count()):
        label = window.nav.item(index).text()
        try:
            window.nav.setCurrentRow(index)
            window.stack.currentWidget().refresh()
        except Exception as exc:  # pragma: no cover - only on regression
            failures.append(f"{label}: {exc!r}")
    assert not failures, "page construction/refresh failed: " + "; ".join(failures)


def test_show_page_accepts_tray_targets(window):
    for key in ("home", "history", "shortcuts", "diagnostics", "about"):
        window.show_page(key)
        assert window.stack.currentWidget().title == window.nav.currentItem().text()


def test_shortcut_page_rejects_a_reserved_combination(window):
    """Windows steals these, so the writer must refuse them rather than register."""
    window.show_page("shortcuts")
    page = window.stack.currentWidget()
    page._set_main("win+l")
    assert page.conflict_label.text() != ""


def test_privacy_page_can_turn_history_off(window):
    window.show_page("privacy")
    page = window.stack.currentWidget()
    page.enabled.setChecked(False)
    assert ("history_enabled", False) in window.orchestrator.calls


def test_diagnostics_never_include_secrets(window):
    """The support bundle is copied into public issue trackers."""
    from ui.diagnostics import as_text

    text = as_text(orchestrator=window.orchestrator)
    lowered = text.lower()
    for forbidden in ("gsk_", "sk-", "api_key", "password", "vault"):
        assert forbidden not in lowered, f"diagnostics leaked {forbidden!r}"
