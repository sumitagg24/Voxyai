"""
First-run onboarding for Voxylis.

Goals, in order of importance for a new user:
  1. explain what the product does in one screen;
  2. confirm the microphone actually works (before they blame the app);
  3. let them record a shortcut instead of typing one;
  4. connect an AI provider - or skip it, because voice commands and local
     settings still work without one;
  5. end with the single instruction they need: "press your shortcut and speak".

The wizard never forces an account: the local/BYOK workflow is a first-class
path.  State is written to ``%LOCALAPPDATA%\\Voxylis\\config\\onboarding.json``
and API keys go to the OS credential store.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from config import version
from config.constants import ENHANCEMENT_MODES, HOTKEY_DEFAULT
from ui import theme
from ui.pages import LANGUAGES, MicrophoneTestThread
from ui.shortcut_recorder import ShortcutRecorder, format_hotkey
from utils import credentials, paths
from utils.logger import log_error, log_info

STEPS = [
    ("welcome", "Welcome to Voxylis", "Speak naturally — Voxylis types it for you."),
    ("microphone", "Check your microphone", "Record three seconds so we know Voxylis can hear you."),
    ("shortcut", "Choose your shortcut", "Click the field and press the keys you want to use."),
    ("provider", "Connect an AI provider", "Optional. Groq is free and fast."),
    ("language", "Language and style", "How should your speech be transcribed and shaped?"),
    ("done", "You're ready", "One shortcut is all you need."),
]


def _onboarding_file() -> Path:
    return paths.onboarding_path()


def _load_onboarding_state() -> dict:
    try:
        path = _onboarding_file()
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        pass
    # Legacy location (install directory) - read-only fallback for one release.
    try:
        legacy = Path(__file__).resolve().parent.parent / "config" / "onboarding.json"
        if legacy.exists():
            data = json.loads(legacy.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _save_onboarding_state(state: dict) -> None:
    try:
        path = _onboarding_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError as exc:
        log_error(f"Failed to save onboarding state: {exc}")


def has_completed_onboarding() -> bool:
    return bool(_load_onboarding_state().get("completed", False))


def reset_onboarding() -> None:
    _save_onboarding_state({"completed": False})


class OnboardingWindow(QDialog):
    """Guided first-run wizard."""

    finished_signal = pyqtSignal()
    settings_ready = pyqtSignal(dict)
    credential_ready = pyqtSignal(str, str)

    def __init__(self, config: dict, orchestrator=None, parent=None):
        super().__init__(parent)
        self.config = config or {}
        self.orchestrator = orchestrator
        self.step_index = 0
        self._answered = {
            "microphone_ok": False,
            "shortcut": self.config.get("hotkey", HOTKEY_DEFAULT),
            "provider_key": "",
            "provider": "",
            "language": self.config.get("language", "auto"),
            "enable_enhancement": bool(self.config.get("enable_ai_enhancement", False)),
            "mode": self.config.get("enhancement_mode", "formal"),
        }
        self.setWindowTitle(f"{version.APP_NAME} setup")
        self.setStyleSheet(theme.stylesheet(self.config.get("theme", "dark")))
        self.setFixedSize(560, 470)
        self.setModal(True)
        self._build_ui()
        self._render()

    # ── UI ───────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 22)
        root.setSpacing(14)

        self.step_label = QLabel("")
        self.step_label.setObjectName("Hint")
        root.addWidget(self.step_label)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._step_welcome())
        self.stack.addWidget(self._step_microphone())
        self.stack.addWidget(self._step_shortcut())
        self.stack.addWidget(self._step_provider())
        self.stack.addWidget(self._step_language())
        self.stack.addWidget(self._step_done())
        root.addWidget(self.stack, 1)

        nav = QHBoxLayout()
        self.skip_button = QPushButton("Skip setup")
        self.skip_button.setObjectName("Link")
        self.skip_button.clicked.connect(self._finish)
        nav.addWidget(self.skip_button)
        nav.addStretch()

        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self._go_back)
        nav.addWidget(self.back_button)

        self.next_button = QPushButton("Continue")
        self.next_button.setObjectName("Primary")
        self.next_button.clicked.connect(self._go_next)
        nav.addWidget(self.next_button)
        root.addLayout(nav)

    def _title_block(self, title: str, subtitle: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        heading = QLabel(title)
        heading.setFont(QFont("Segoe UI", 17, QFont.Bold))
        layout.addWidget(heading)
        body = QLabel(subtitle)
        body.setWordWrap(True)
        body.setObjectName("PageSubtitle")
        layout.addWidget(body)
        return widget

    def _step_welcome(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.addWidget(
            self._title_block(
                "Speak, don't type",
                "Voxylis listens while you work, transcribes your speech, optionally rewrites it with AI, "
                "and types the result into whatever window has focus.\n\n"
                "Setup takes about a minute, and everything stays on this machine except the audio you "
                "choose to send to your own speech provider.",
            )
        )
        local_note = QLabel(
            f"Version {version.__version__} · data folder: {paths.user_data_root()}"
        )
        local_note.setObjectName("Mono")
        local_note.setWordWrap(True)
        layout.addWidget(local_note)
        layout.addStretch()
        return widget

    def _step_microphone(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.addWidget(
            self._title_block(
                "Check your microphone",
                "We will record three seconds and check that speech is detected. "
                "Nothing is uploaded during this test.",
            )
        )
        row = QHBoxLayout()
        self.mic_button = QPushButton("Test microphone")
        self.mic_button.setObjectName("Primary")
        self.mic_button.clicked.connect(self._test_microphone)
        row.addWidget(self.mic_button)
        self.mic_result = QLabel("Not tested yet")
        self.mic_result.setObjectName("Hint")
        self.mic_result.setWordWrap(True)
        row.addWidget(self.mic_result, 1)
        layout.addLayout(row)

        self.mic_device = QComboBox()
        self.mic_device.addItem("System default microphone", None)
        try:
            from audio.recorder import AudioRecorder

            for index, device in enumerate(AudioRecorder().list_devices()):
                name = device.get("name") if isinstance(device, dict) else getattr(device, "name", "")
                channels = device.get("max_input_channels", 0) if isinstance(device, dict) else 0
                if name and channels:
                    self.mic_device.addItem(str(name), index)
        except Exception:
            pass
        self.mic_device.currentIndexChanged.connect(
            lambda: self._answered.update({"audio_device": self.mic_device.currentData()})
        )
        layout.addWidget(self.mic_device)
        layout.addStretch()
        return widget

    def _step_shortcut(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.addWidget(
            self._title_block(
                "Choose your shortcut",
                "Click the field, then press the combination you want. "
                "Hold it to record, release it to insert the text.",
            )
        )
        self.recorder = ShortcutRecorder(self._answered["shortcut"])
        self.recorder.changed.connect(self._on_shortcut_changed)
        self.recorder.invalid.connect(lambda reason: self._shortcut_error.setText(reason))
        layout.addWidget(self.recorder)

        self._shortcut_error = QLabel("")
        self._shortcut_error.setObjectName("BadgeWarn")
        self._shortcut_error.setWordWrap(True)
        layout.addWidget(self._shortcut_error)

        self.toggle_mode = QCheckBox("Toggle mode — press once to start, press again to stop")
        layout.addWidget(self.toggle_mode)
        self.hold_hint = QLabel("")
        self.hold_hint.setObjectName("Hint")
        self.hold_hint.setWordWrap(True)
        layout.addWidget(self.hold_hint)
        layout.addStretch()
        return widget

    def _step_provider(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.addWidget(
            self._title_block(
                "Connect an AI provider",
                "Voxylis needs a speech-to-text key to transcribe. Groq's free tier is the recommended "
                "starting point. You can skip this and add a key later in Settings → AI Providers.",
            )
        )
        link = QLabel('<a href="https://console.groq.com/keys">Open console.groq.com/keys to create a free key</a>')
        link.setOpenExternalLinks(True)
        layout.addWidget(link)

        self.provider_key = QLineEdit()
        self.provider_key.setEchoMode(QLineEdit.Password)
        self.provider_key.setPlaceholderText("gsk_… (Groq) or sk-… (OpenAI)")
        layout.addWidget(self.provider_key)

        show = QCheckBox("Show key")
        show.stateChanged.connect(
            lambda state: self.provider_key.setEchoMode(QLineEdit.Normal if state else QLineEdit.Password)
        )
        layout.addWidget(show)
        layout.addWidget(
            QLabel(
                f"Stored in the operating system credential store "
                f"({credentials.credential_store.backend_name}), never in a plaintext settings file."
            )
        )
        layout.addStretch()
        return widget

    def _step_language(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.addWidget(
            self._title_block(
                "Language and style",
                "Auto-detect works well for most people. Pin a language if detection keeps guessing wrong.",
            )
        )
        language_row = QHBoxLayout()
        language_row.addWidget(QLabel("Language"))
        self.language_combo = QComboBox()
        for label, code in LANGUAGES:
            self.language_combo.addItem(label, code)
        language_row.addWidget(self.language_combo, 1)
        layout.addLayout(language_row)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Enhancement mode"))
        self.mode_combo = QComboBox()
        for mode in ENHANCEMENT_MODES:
            self.mode_combo.addItem(mode.capitalize(), mode)
        mode_row.addWidget(self.mode_combo, 1)
        layout.addLayout(mode_row)

        self.enhance_checkbox = QCheckBox("Rewrite my text with AI before inserting it")
        layout.addWidget(self.enhance_checkbox)
        layout.addWidget(
            QLabel(
                "Enhancement sends the transcript (not the audio) to the provider and can add a moment of latency."
            )
        )
        layout.addStretch()
        return widget

    def _step_done(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.addWidget(
            self._title_block(
                "You're ready to dictate",
                "Voxylis now sits in the system tray. Open the main window any time from the tray menu.",
            )
        )
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        layout.addStretch()
        return widget

    # ── flow ─────────────────────────────────────────────────────────────

    def _render(self) -> None:
        key, title, _ = STEPS[self.step_index]
        self.step_label.setText(f"Step {self.step_index + 1} of {len(STEPS)} · {title}")
        self.stack.setCurrentIndex(self.step_index)
        self.back_button.setEnabled(self.step_index > 0)
        self.next_button.setText("Finish" if self.step_index == len(STEPS) - 1 else "Continue")
        self.skip_button.setVisible(self.step_index == 0)

        if key == "language":
            index = self.language_combo.findData(self._answered["language"])
            self.language_combo.setCurrentIndex(max(0, index))
            index = self.mode_combo.findData(self._answered["mode"])
            self.mode_combo.setCurrentIndex(max(0, index))
            self.enhance_checkbox.setChecked(self._answered["enable_enhancement"])
        if key == "done":
            hotkey = format_hotkey(self._answered["shortcut"])
            provider = self._answered["provider"] or "no AI provider yet"
            self.summary.setText(
                f"<b>Shortcut:</b> {hotkey}<br>"
                f"<b>Provider:</b> {provider}<br>"
                f"<b>Microphone:</b> {'checked' if self._answered['microphone_ok'] else 'not tested'}<br><br>"
                f"Press <b>{hotkey}</b> and start speaking."
            )

    def _go_back(self) -> None:
        if self.step_index > 0:
            self.step_index -= 1
            self._render()

    def _go_next(self) -> None:
        key = STEPS[self.step_index][0]
        if key == "provider":
            self._capture_provider()
        elif key == "language":
            self._answered["language"] = self.language_combo.currentData()
            self._answered["mode"] = self.mode_combo.currentData()
            self._answered["enable_enhancement"] = self.enhance_checkbox.isChecked()
        elif key == "shortcut":
            self._answered["shortcut"] = self.recorder.value() or HOTKEY_DEFAULT
            self._answered["toggle_mode"] = self.toggle_mode.isChecked()

        if self.step_index == len(STEPS) - 1:
            self._finish()
            return
        self.step_index += 1
        self._render()

    # ── step logic ───────────────────────────────────────────────────────

    def _on_shortcut_changed(self, value: str) -> None:
        self._answered["shortcut"] = value
        self._shortcut_error.setText("")
        self.hold_hint.setText(
            f"Voxylis will listen while {format_hotkey(value)} is held down."
            if value
            else ""
        )

    def _test_microphone(self) -> None:
        self.mic_button.setEnabled(False)
        self.mic_result.setText("Recording three seconds — say anything…")
        self._mic_thread = MicrophoneTestThread(self.mic_device.currentData(), seconds=3.0)
        self._mic_thread.finished_test.connect(self._mic_test_done)
        self._mic_thread.start()

    def _mic_test_done(self, result: dict) -> None:
        self.mic_button.setEnabled(True)
        if result.get("ok") and result.get("speech"):
            self._answered["microphone_ok"] = True
            self.mic_result.setText("Microphone works and speech was detected.")
        elif result.get("ok"):
            self.mic_result.setText(
                "Audio captured, but no speech detected. Move closer to the microphone and try again."
            )
        else:
            self.mic_result.setText(
                f"Could not open the microphone ({result.get('detail', 'unknown error')}). "
                "You can continue and fix this later in Settings → Microphone."
            )

    def _capture_provider(self) -> None:
        value = self.provider_key.text().strip()
        if not value:
            return
        key_name = "groq_api_key" if value.startswith("gsk_") else "openai_api_key"
        if credentials.credential_store.set(key_name, value):
            self._answered["provider_key"] = value
            self._answered["provider"] = "Groq" if key_name == "groq_api_key" else "OpenAI"
            self.credential_ready.emit(key_name, value)
        self.provider_key.clear()

    # ── completion ───────────────────────────────────────────────────────

    def _finish(self) -> None:
        payload = {k: v for k, v in self._answered.items() if k != "provider_key"}
        payload["hotkey"] = self._answered["shortcut"] or HOTKEY_DEFAULT
        if payload.get("enable_enhancement") and not self._answered.get("provider"):
            # Enhancement without a provider key would silently do nothing.
            payload["enable_ai_enhancement"] = False
        else:
            payload["enable_ai_enhancement"] = bool(self._answered.get("enable_enhancement"))

        try:
            _persist_settings(payload)
        except Exception as exc:
            log_error(f"Onboarding could not persist settings: {exc}")

        _save_onboarding_state(
            {
                "completed": True,
                "completed_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
                "version": version.__version__,
                "microphone_checked": bool(self._answered.get("microphone_ok")),
            }
        )
        log_info("Onboarding completed")
        self.settings_ready.emit(payload)
        self.finished_signal.emit()
        self.accept()

    def closeEvent(self, event):  # noqa: N802
        # Closing the wizard counts as completing it; we never nag on next start.
        if not has_completed_onboarding():
            _save_onboarding_state({"completed": True, "skipped": True})
        super().closeEvent(event)


def _persist_settings(payload: dict) -> None:
    """Persist onboarding answers into settings.json (no secrets)."""
    from utils.helpers import load_json
    from utils.helpers import save_json as write_json

    path = paths.settings_path()
    current = load_json(str(path))
    mapping = {
        "hotkey": "hotkey",
        "toggle_mode": "toggle_mode",
        "audio_device": "audio_device",
        "language": "language",
        "mode": "enhancement_mode",
        "enable_enhancement": "enable_ai_enhancement",
    }
    for source, target in mapping.items():
        if source in payload:
            current[target] = payload[source]
    if payload.get("enable_enhancement"):
        current["enable_ai_enhancement"] = True
    current.pop("onboarding", None)
    write_json(str(path), current)


def run_onboarding(config: dict, orchestrator=None, parent=None) -> Optional[dict]:
    """Convenience helper used by the app when onboarding is skipped."""
    dialog = OnboardingWindow(config, orchestrator=orchestrator, parent=parent)
    dialog.exec_()
    return dialog._answered
