"""
Voxylis Desktop Onboarding - First-run wizard for new users.
"""

import json
from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QCheckBox,
    QLineEdit,
    QStackedWidget,
    QWidget,
    QMessageBox,
    QFrame,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap

from utils.logger import log_error, log_info


ONBOARDING_STEPS = [
    {
        "id": "welcome",
        "title": "Welcome to Voxylis!",
        "subtitle": "Your AI-powered voice-to-text assistant",
        "description": "Voxylis lets you speak naturally and have your words enhanced by AI before they're typed anywhere. Let's get you set up in 30 seconds.",
    },
    {
        "id": "api_key",
        "title": "Configure API Key",
        "subtitle": "Required for transcription and AI enhancement",
        "description": "Voxylis uses Groq (FREE) or OpenAI for transcription. Get a free Groq key at console.groq.com/keys",
    },
    {
        "id": "hotkey",
        "title": "Learn the Hotkey",
        "subtitle": "Win+Shift to record",
        "description": "Press and hold Win+Shift to record. Release to stop and transcribe. You can also use Win+Alt (casual) or Win+Ctrl (technical).",
    },
    {
        "id": "voice_commands",
        "title": "Voice Commands",
        "subtitle": "Control with your voice",
        "description": "While recording, say:\n\n• 'clear that' — undo last injection\n• 'new line' — insert a line break\n• 'undo' — undo the last action",
    },
    {
        "id": "done",
        "title": "You're All Set!",
        "subtitle": "Start using Voxylis",
        "description": "Press Win+Shift to make your first recording. Right-click the tray icon for settings, history, and more.",
    },
]


ONBOARDING_FILE = Path(__file__).resolve().parent.parent / "config" / "onboarding.json"


def _load_onboarding_state() -> dict:
    try:
        if ONBOARDING_FILE.exists():
            return json.loads(ONBOARDING_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_onboarding_state(state: dict):
    try:
        ONBOARDING_FILE.parent.mkdir(parents=True, exist_ok=True)
        ONBOARDING_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as e:
        log_error(f"Failed to save onboarding state: {e}")


def has_completed_onboarding() -> bool:
    state = _load_onboarding_state()
    return state.get("completed", False)


class OnboardingWindow(QDialog):
    """First-run onboarding wizard."""

    finished_signal = pyqtSignal()

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config
        self.current_step = 0
        self._setup_ui()
        self._update_step()

    def _setup_ui(self):
        self.setWindowTitle("Voxylis Setup")
        self.setFixedSize(520, 420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(32, 32, 32, 32)

        # Step indicator
        self.step_label = QLabel()
        self.step_label.setAlignment(Qt.AlignCenter)
        self.step_label.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(self.step_label)

        # Title
        self.title_label = QLabel()
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setFont(QFont("Segoe UI", 18, QFont.Bold))
        self.title_label.setStyleSheet("color: #1a1a2e;")
        layout.addWidget(self.title_label)

        # Subtitle
        self.subtitle_label = QLabel()
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setFont(QFont("Segoe UI", 11))
        self.subtitle_label.setStyleSheet("color: #555;")
        layout.addWidget(self.subtitle_label)

        # Description
        self.desc_label = QLabel()
        self.desc_label.setAlignment(Qt.AlignCenter)
        self.desc_label.setWordWrap(True)
        self.desc_label.setFont(QFont("Segoe UI", 10))
        self.desc_label.setStyleSheet("color: #333; line-height: 1.5;")
        layout.addWidget(self.desc_label)

        # API key input (hidden by default)
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("gsk_... (Groq) or sk-... (OpenAI)")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setStyleSheet(
            "QLineEdit { padding: 8px; border: 1px solid #ccc; border-radius: 6px; font-size: 13px; }"
        )
        self.api_key_input.setVisible(False)
        layout.addWidget(self.api_key_input)

        self.show_key_cb = QCheckBox("Show key")
        self.show_key_cb.stateChanged.connect(self._toggle_key_visibility)
        self.show_key_cb.setVisible(False)
        self.show_key_cb.setStyleSheet("font-size: 12px; color: #666;")
        layout.addWidget(self.show_key_cb)

        layout.addStretch()

        # Navigation buttons
        nav = QHBoxLayout()
        nav.addStretch()

        self.back_btn = QPushButton("Back")
        self.back_btn.setFixedWidth(100)
        self.back_btn.setStyleSheet(
            "QPushButton { padding: 8px 16px; border: 1px solid #ccc; border-radius: 6px; }"
            "QPushButton:hover { background: #f0f0f0; }"
        )
        self.back_btn.clicked.connect(self._go_back)
        nav.addWidget(self.back_btn)

        self.next_btn = QPushButton("Next")
        self.next_btn.setFixedWidth(100)
        self.next_btn.setStyleSheet(
            "QPushButton { padding: 8px 16px; background: #6c5ce7; color: white; border: none; border-radius: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #5a4bd1; }"
        )
        self.next_btn.clicked.connect(self._go_next)
        nav.addWidget(self.next_btn)

        layout.addLayout(nav)

        self.setStyleSheet("QDialog { background: #fafafa; }")

    def _update_step(self):
        step = ONBOARDING_STEPS[self.current_step]
        total = len(ONBOARDING_STEPS)
        self.step_label.setText(f"Step {self.current_step + 1} of {total}")
        self.title_label.setText(step["title"])
        self.subtitle_label.setText(step["subtitle"])
        self.desc_label.setText(step["description"])

        # Show/hide API key input
        show_key = step["id"] == "api_key"
        self.api_key_input.setVisible(show_key)
        self.show_key_cb.setVisible(show_key)
        if show_key:
            existing = self.config.get("groq_api_key", "")
            if existing:
                self.api_key_input.setText(existing)

        # Button states
        self.back_btn.setVisible(self.current_step > 0)
        if self.current_step == total - 1:
            self.next_btn.setText("Finish")
            self.next_btn.setStyleSheet(
                "QPushButton { padding: 8px 16px; background: #00b894; color: white; border: none; border-radius: 6px; font-weight: bold; }"
                "QPushButton:hover { background: #00a381; }"
            )
        else:
            self.next_btn.setText("Next")
            self.next_btn.setStyleSheet(
                "QPushButton { padding: 8px 16px; background: #6c5ce7; color: white; border: none; border-radius: 6px; font-weight: bold; }"
                "QPushButton:hover { background: #5a4bd1; }"
            )

    def _toggle_key_visibility(self, state):
        if state == Qt.Checked:
            self.api_key_input.setEchoMode(QLineEdit.Normal)
        else:
            self.api_key_input.setEchoMode(QLineEdit.Password)

    def _go_back(self):
        if self.current_step > 0:
            self.current_step -= 1
            self._update_step()

    def _go_next(self):
        # Save API key if on that step
        if ONBOARDING_STEPS[self.current_step]["id"] == "api_key":
            key = self.api_key_input.text().strip()
            if key:
                if key.startswith("gsk_"):
                    self.config["groq_api_key"] = key
                elif key.startswith("sk-"):
                    self.config["openai_api_key"] = key
                self._save_config()

        if self.current_step < len(ONBOARDING_STEPS) - 1:
            self.current_step += 1
            self._update_step()
        else:
            self._finish()

    def _save_config(self):
        config_path = Path(__file__).resolve().parent.parent / "config" / "settings.json"
        try:
            config_path.write_text(json.dumps(self.config, indent=2), encoding="utf-8")
        except Exception as e:
            log_error(f"Failed to save config: {e}")

    def _finish(self):
        _save_onboarding_state({"completed": True})
        log_info("Onboarding completed")
        self.finished_signal.emit()
        self.accept()
