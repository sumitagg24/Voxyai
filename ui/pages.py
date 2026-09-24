"""
Pages for the Voxylis main window.

Each page owns one concern, reads its initial state from the orchestrator
config, and writes changes back through ``orchestrator.update_config`` so
persistence, live effects (hotkey rebinding, credential storage, history
retention) and the settings-changed event all stay in one place.

Nothing here writes a credential to disk: API keys go to the OS credential
store via the orchestrator, and ``settings.json`` only ever records
``{"configured": true}``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import version
from config.constants import (
    ENHANCEMENT_MODES,
    HOTKEY_DEFAULT,
    MODE_HOTKEY_DEFAULTS,
)
from core import errors as error_catalog
from ui import diagnostics as diagnostics_mod
from ui import theme
from ui.shortcut_recorder import ShortcutRecorder, format_hotkey

LANGUAGES = [
    ("Auto-detect", "auto"),
    ("English", "en"),
    ("Hindi", "hi"),
    ("Hinglish", "hi-en"),
    ("Bengali", "bn"),
    ("Punjabi", "pa"),
    ("Gujarati", "gu"),
    ("Tamil", "ta"),
    ("Telugu", "te"),
    ("Malayalam", "ml"),
    ("Marathi", "mr"),
    ("Urdu", "ur"),
    ("Arabic", "ar"),
    ("Spanish", "es"),
    ("French", "fr"),
    ("German", "de"),
    ("Italian", "it"),
    ("Portuguese", "pt"),
    ("Russian", "ru"),
    ("Turkish", "tr"),
    ("Dutch", "nl"),
    ("Polish", "pl"),
    ("Japanese", "ja"),
    ("Chinese", "zh"),
    ("Korean", "ko"),
    ("Vietnamese", "vi"),
    ("Indonesian", "id"),
    ("Thai", "th"),
    ("Swedish", "sv"),
    ("Norwegian", "no"),
    ("Danish", "da"),
    ("Finnish", "fi"),
    ("Czech", "cs"),
    ("Hungarian", "hu"),
    ("Romanian", "ro"),
    ("Ukrainian", "uk"),
    ("Greek", "el"),
    ("Hebrew", "he"),
]


# ── shared widgets ───────────────────────────────────────────────────────────


def card() -> QFrame:
    frame = QFrame()
    frame.setObjectName("Card")
    frame.setFrameShape(QFrame.NoFrame)
    return frame


def scrollable(inner: QWidget) -> QWidget:
    from PyQt5.QtWidgets import QScrollArea

    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    area.setWidget(inner)
    return area


def hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Hint")
    label.setWordWrap(True)
    return label


def section(title: str, subtitle: str = "") -> QVBoxLayout:
    layout = QVBoxLayout()
    layout.setSpacing(4)
    title_label = QLabel(title)
    title_label.setObjectName("SectionTitle")
    layout.addWidget(title_label)
    if subtitle:
        layout.addWidget(hint(subtitle))
    return layout


class BasePage(QWidget):
    """Common page scaffolding: a title, a scrolling body and refresh()."""

    title = "Page"
    subtitle = ""

    def __init__(self, orchestrator=None, parent=None):
        super().__init__(parent)
        self.orchestrator = orchestrator

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 20)
        outer.setSpacing(14)

        header = QVBoxLayout()
        header.setSpacing(2)
        title_label = QLabel(self.title)
        title_label.setObjectName("PageTitle")
        header.addWidget(title_label)
        if self.subtitle:
            header.addWidget(hint(self.subtitle))
        outer.addLayout(header)

        self.body = QVBoxLayout()
        self.body.setSpacing(14)
        container = QWidget()
        container.setLayout(self.body)
        outer.addWidget(scrollable(container), 1)

    def refresh(self) -> None:  # pragma: no cover - overridden
        pass

    def on_show(self) -> None:
        self.refresh()


# ── Home ─────────────────────────────────────────────────────────────────────


class HomePage(BasePage):
    title = "Home"
    subtitle = "Your voice, typed into whatever you are working in."

    def __init__(self, orchestrator, parent=None):
        super().__init__(orchestrator, parent)

        # status card
        status_card = card()
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(20, 18, 20, 18)
        status_layout.setSpacing(10)

        row = QHBoxLayout()
        self.state_label = QLabel("Ready")
        self.state_label.setObjectName("PageTitle")
        row.addWidget(self.state_label)
        row.addStretch()
        self.mode_label = QLabel("")
        self.mode_label.setObjectName("Mono")
        row.addWidget(self.mode_label)
        status_layout.addLayout(row)

        self.stage_label = QLabel("Press your shortcut or use the button below.")
        self.stage_label.setObjectName("PageSubtitle")
        status_layout.addWidget(self.stage_label)

        self.level_bar = QProgressBar()
        self.level_bar.setRange(0, 100)
        self.level_bar.setTextVisible(False)
        self.level_bar.setFixedHeight(8)
        status_layout.addWidget(self.level_bar)

        actions = QHBoxLayout()
        self.record_button = QPushButton("Start recording")
        self.record_button.setObjectName("Record")
        self.record_button.setProperty("recording", "false")
        self.record_button.setMinimumHeight(40)
        self.record_button.clicked.connect(self._toggle_recording)
        actions.addWidget(self.record_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("Danger")
        self.cancel_button.clicked.connect(self._cancel)
        actions.addWidget(self.cancel_button)
        actions.addStretch()
        self.shortcut_hint = QLabel("")
        self.shortcut_hint.setObjectName("Mono")
        actions.addWidget(self.shortcut_hint)
        status_layout.addLayout(actions)
        self.body.addWidget(status_card)

        # stats
        stats_card = card()
        stats_layout = QGridLayout(stats_card)
        stats_layout.setContentsMargins(20, 16, 20, 16)
        stats_layout.setHorizontalSpacing(28)
        self.stat_values = {}
        for column, (key, label) in enumerate(
            [
                ("transcriptions", "Transcriptions today"),
                ("words", "Words today"),
                ("total", "Words all time"),
                ("commands", "Commands today"),
            ]
        ):
            value = QLabel("0")
            value.setObjectName("StatValue")
            name = QLabel(label)
            name.setObjectName("StatLabel")
            stats_layout.addWidget(value, 0, column)
            stats_layout.addWidget(name, 1, column)
            self.stat_values[key] = value
        self.body.addWidget(stats_card)

        # readiness
        ready_card = card()
        ready_layout = QVBoxLayout(ready_card)
        ready_layout.setContentsMargins(20, 16, 20, 16)
        ready_layout.addLayout(section("Setup", "Everything Voxylis needs to run."))
        self.readiness = QGridLayout()
        self.readiness.setHorizontalSpacing(24)
        self.readiness.setVerticalSpacing(6)
        ready_layout.addLayout(self.readiness)
        self.body.addWidget(ready_card)

        # last error banner
        self.error_banner = QFrame()
        self.error_banner.setObjectName("BannerError")
        error_layout = QHBoxLayout(self.error_banner)
        error_layout.setContentsMargins(16, 12, 16, 12)
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        error_layout.addWidget(self.error_label, 1)
        self.error_button = QPushButton("Details")
        self.error_button.clicked.connect(self._show_last_error)
        error_layout.addWidget(self.error_button)
        self.error_banner.setVisible(False)
        self.body.addWidget(self.error_banner)

        self.body.addStretch()
        self.refresh()

    # -- actions -----------------------------------------------------------

    def _toggle_recording(self) -> None:
        if self.orchestrator is None:
            return
        if self.orchestrator.get_status().get("stage") == "recording":
            self.orchestrator.stop_recording()
        else:
            self.orchestrator.toggle_recording()

    def _cancel(self) -> None:
        if self.orchestrator is not None:
            self.orchestrator.cancel_recording()
            self.error_banner.setVisible(False)

    def _show_last_error(self) -> None:
        from ui.error_dialog import build_diagnostics_text, show_error

        if self.orchestrator is None or self.orchestrator.last_error is None:
            return
        result = show_error(
            self.orchestrator.last_error,
            parent=self,
            diagnostics=lambda: build_diagnostics_text(self.orchestrator),
        )
        if result == "retry":
            self.orchestrator.toggle_recording()

    # -- state -------------------------------------------------------------

    def set_stage(self, stage: str) -> None:
        labels = {
            "idle": ("Ready", "Press your shortcut or use the button below."),
            "recording": ("Listening…", "Speak now. Release the shortcut or press Stop when done."),
            "transcribing": ("Transcribing…", "Sending audio to your speech provider."),
            "enhancing": ("Enhancing…", "Rewriting your text with AI."),
            "injecting": ("Inserting…", "Typing the result into the focused window."),
        }
        title, subtitle = labels.get(stage, ("Working…", ""))
        self.state_label.setText(title)
        self.stage_label.setText(subtitle)
        recording = stage == "recording"
        self.record_button.setText("Stop recording" if recording else "Start recording")
        self.record_button.setProperty("recording", "true" if recording else "false")
        self.record_button.style().unpolish(self.record_button)
        self.record_button.style().polish(self.record_button)

    def set_level(self, level: float) -> None:
        self.level_bar.setValue(int(max(0.0, min(100.0, level))))

    def show_error(self, error) -> None:
        self.error_label.setText(f"{error.title} — {error.action or error.summary}")
        self.error_banner.setVisible(True)
        self.set_stage("idle")

    def refresh(self) -> None:
        if self.orchestrator is None:
            return
        status = self.orchestrator.get_status()
        today = status.get("today_stats") or {}
        total = self.orchestrator.stats.get_total()
        self.stat_values["transcriptions"].setText(str(today.get("transcriptions", 0)))
        self.stat_values["words"].setText(str(today.get("words", 0)))
        self.stat_values["commands"].setText(str(today.get("commands", 0)))
        self.stat_values["total"].setText(str(total.get("words", 0)))

        providers = self.orchestrator.provider_status()
        self.shortcut_hint.setText(format_hotkey(self.orchestrator.get_config("hotkey") or HOTKEY_DEFAULT))
        mode = self.orchestrator.get_config("enhancement_mode", "formal")
        enhancement = "on" if self.orchestrator.get_config("enable_ai_enhancement") else "off"
        self.mode_label.setText(f"mode: {mode} · enhancement: {enhancement}")
        self.set_stage(status.get("stage", "idle"))

        rows = [
            (
                "Speech-to-text provider",
                bool(providers["groq"]["configured"] or providers["openai"]["configured"]),
                "Configure in AI Providers",
                "Settings → AI Providers",
            ),
            ("Microphone", True, "Test in Microphone", ""),
            (
                "Global shortcut",
                bool(self.orchestrator.get_config("hotkey")),
                "Set in Shortcuts",
                "Settings → Shortcuts",
            ),
            ("Text insertion", True, "Clipboard, SendInput or typing", ""),
            ("History", True, "Stored locally in SQLite", ""),
        ]
        while self.readiness.count():
            item = self.readiness.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        for row_index, (label, ok, detail, _) in enumerate(rows):
            name = QLabel(label)
            status_label = QLabel("✓ ready" if ok else "• needs attention")
            status_label.setObjectName("BadgeOk" if ok else "BadgeWarn")
            detail_label = QLabel(detail)
            detail_label.setObjectName("Hint")
            self.readiness.addWidget(name, row_index, 0)
            self.readiness.addWidget(status_label, row_index, 1)
            self.readiness.addWidget(detail_label, row_index, 2)

        if self.orchestrator.last_error is not None and self.error_banner.isVisible():
            self.error_label.setText(
                f"{self.orchestrator.last_error.title} — "
                f"{self.orchestrator.last_error.action or self.orchestrator.last_error.summary}"
            )


# ── History ──────────────────────────────────────────────────────────────────


class HistoryPage(BasePage):
    title = "History"
    subtitle = "Every transcription is stored locally. Nothing is uploaded by the desktop app."

    def __init__(self, orchestrator, parent=None):
        super().__init__(orchestrator, parent)
        self._entries = []

        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search transcripts…")
        self.search.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self.search, 1)

        self.export_button = QPushButton("Export…")
        self.export_button.clicked.connect(self._export)
        toolbar.addWidget(self.export_button)

        self.clear_button = QPushButton("Clear all")
        self.clear_button.setObjectName("Danger")
        self.clear_button.clicked.connect(self._clear_all)
        toolbar.addWidget(self.clear_button)
        self.body.addLayout(toolbar)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["When", "Mode", "Words", "Text"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 110)
        self.table.setColumnWidth(2, 60)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemSelectionChanged.connect(self._on_select)
        self.body.addWidget(self.table, 1)

        preview_row = QHBoxLayout()
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("Select an entry to preview it…")
        self.preview.setMinimumHeight(120)
        preview_row.addWidget(self.preview, 1)
        self.body.addLayout(preview_row)

        actions = QHBoxLayout()
        self.copy_button = QPushButton("Copy")
        self.copy_button.clicked.connect(self._copy)
        self.inject_button = QPushButton("Insert again")
        self.inject_button.setObjectName("Primary")
        self.inject_button.clicked.connect(self._reinject)
        self.delete_button = QPushButton("Delete entry")
        self.delete_button.setObjectName("Danger")
        self.delete_button.clicked.connect(self._delete)
        actions.addWidget(self.copy_button)
        actions.addWidget(self.inject_button)
        actions.addWidget(self.delete_button)
        actions.addStretch()
        self.status_label = QLabel("")
        self.status_label.setObjectName("Hint")
        actions.addWidget(self.status_label)
        self.body.addLayout(actions)

        self.refresh()

    # -- data --------------------------------------------------------------

    def refresh(self) -> None:
        if self.orchestrator is None:
            return
        self._entries = self.orchestrator.history.get_all()
        if not self.orchestrator.history.enabled:
            self.status_label.setText("History is disabled in Privacy settings — new recordings are not stored.")
        else:
            self.status_label.setText(f"{len(self._entries)} entries stored locally")
        self._apply_filter()

    def _apply_filter(self) -> None:
        needle = self.search.text().strip().lower()
        rows = [
            entry
            for entry in self._entries
            if not needle
            or needle in (entry.get("enhanced") or "").lower()
            or needle in (entry.get("raw") or "").lower()
        ]
        self.table.setRowCount(len(rows))
        for row, entry in enumerate(rows):
            self.table.setItem(row, 0, QTableWidgetItem(entry.get("timestamp", "")))
            self.table.setItem(row, 1, QTableWidgetItem(entry.get("mode", "")))
            self.table.setItem(row, 2, QTableWidgetItem(str(entry.get("word_count", 0))))
            text = (entry.get("enhanced") or entry.get("raw") or "").replace("\n", " ")
            self.table.setItem(row, 3, QTableWidgetItem(text[:160]))
            self.table.item(row, 0).setData(Qt.UserRole, entry)
        self.table.resizeRowsToContents()

    def _current(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _on_select(self) -> None:
        entry = self._current()
        if not entry:
            self.preview.clear()
            return
        body = entry.get("enhanced") or entry.get("raw") or ""
        if entry.get("raw") and entry.get("raw") != entry.get("enhanced"):
            body = f"{body}\n\n── original ──\n{entry['raw']}"
        self.preview.setPlainText(body)

    # -- actions -----------------------------------------------------------

    def _copy(self) -> None:
        entry = self._current()
        if not entry:
            return
        from PyQt5.QtWidgets import QApplication

        QApplication.clipboard().setText(entry.get("enhanced") or entry.get("raw") or "")
        self.status_label.setText("Copied to clipboard")

    def _reinject(self) -> None:
        entry = self._current()
        if not entry or self.orchestrator is None:
            return
        outcome = self.orchestrator.injector.inject(entry.get("enhanced") or entry.get("raw") or "")
        self.status_label.setText(outcome.user_message())

    def _delete(self) -> None:
        entry = self._current()
        if not entry or self.orchestrator is None:
            return
        self.orchestrator.history.delete(entry["id"])
        self.refresh()

    def _clear_all(self) -> None:
        if self.orchestrator is None:
            return
        confirm = QMessageBox.question(
            self,
            "Clear history",
            "Delete every stored transcription? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self.orchestrator.history.clear()
            self.refresh()
            self.status_label.setText("History cleared")

    def _export(self) -> None:
        if self.orchestrator is None:
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export history",
            str(Path.home() / "voxylis-history.json"),
            "JSON (*.json);;CSV (*.csv)",
        )
        if not path:
            return
        fmt = "csv" if (path.lower().endswith(".csv") or "csv" in selected_filter.lower()) else "json"
        written = self.orchestrator.history.export(Path(path), fmt=fmt)
        self.status_label.setText(f"Exported to {written}" if written else "Export failed")


# ── Voice ────────────────────────────────────────────────────────────────────


class MicrophoneTestThread(QThread):
    finished_test = pyqtSignal(dict)

    def __init__(self, device_id=None, seconds: float = 3.0):
        super().__init__()
        self.device_id = device_id
        self.seconds = seconds

    def run(self) -> None:  # pragma: no cover - requires audio hardware
        result = {"ok": False, "detail": "", "peak": 0.0, "speech": False}
        try:
            import numpy as np
            import sounddevice as sd

            from audio.audio_utils import has_speech

            sample_rate = 16000
            frames = int(self.seconds * sample_rate)
            recording = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="int16", device=self.device_id)
            sd.wait()
            peak = float(np.max(np.abs(recording))) / 32767.0 if recording.size else 0.0
            result.update(
                {
                    "ok": True,
                    "peak": round(peak, 3),
                    "speech": bool(has_speech(recording)),
                    "detail": "Audio captured" if peak > 0.001 else "Silence captured — check the input device",
                }
            )
        except Exception as exc:
            result["detail"] = f"{type(exc).__name__}: {exc}"
        self.finished_test.emit(result)


class VoicePage(BasePage):
    title = "Microphone"
    subtitle = "Choose the input device and check that Voxylis can hear you."

    def __init__(self, orchestrator, parent=None):
        super().__init__(orchestrator, parent)

        device_box = QGroupBox("Input device")
        device_layout = QVBoxLayout(device_box)
        self.device_combo = QComboBox()
        device_layout.addWidget(self.device_combo)
        device_layout.addWidget(hint("Use the system default unless a specific microphone misbehaves."))

        test_row = QHBoxLayout()
        self.test_button = QPushButton("Test microphone (3s)")
        self.test_button.clicked.connect(self._test)
        test_row.addWidget(self.test_button)
        self.test_result = QLabel("Not tested yet")
        self.test_result.setObjectName("Hint")
        test_row.addWidget(self.test_result, 1)
        device_layout.addLayout(test_row)
        self.body.addWidget(device_box)

        voice_box = QGroupBox("Dictation")
        voice_layout = QVBoxLayout(voice_box)

        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel("Primary language"))
        self.language_combo = QComboBox()
        for label, code in LANGUAGES:
            self.language_combo.addItem(label, code)
        lang_row.addWidget(self.language_combo, 1)
        voice_layout.addLayout(lang_row)

        second_row = QHBoxLayout()
        second_row.addWidget(QLabel("Secondary language"))
        self.secondary_combo = QComboBox()
        for label, code in LANGUAGES:
            self.secondary_combo.addItem(label, code)
        second_row.addWidget(self.secondary_combo, 1)
        voice_layout.addLayout(second_row)
        voice_layout.addWidget(
            hint("Auto-detect lets Whisper identify the language. Pin one language only if detection is unreliable.")
        )

        self.auto_inject = QCheckBox("Insert the transcribed text automatically")
        voice_layout.addWidget(self.auto_inject)

        self.toggle_mode = QCheckBox("Toggle mode (press once to start, press again to stop)")
        voice_layout.addWidget(self.toggle_mode)
        self.body.addWidget(voice_box)

        sound_box = QGroupBox("Sound feedback")
        sound_layout = QVBoxLayout(sound_box)
        self.sound_enabled = QCheckBox("Play a tone when recording starts and stops")
        sound_layout.addWidget(self.sound_enabled)
        volume_row = QHBoxLayout()
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume_label = QLabel("70%")
        self.volume.valueChanged.connect(lambda v: self.volume_label.setText(f"{v}%"))
        volume_row.addWidget(self.volume, 1)
        volume_row.addWidget(self.volume_label)
        sound_layout.addLayout(volume_row)
        self.body.addWidget(sound_box)

        self.body.addStretch()

        self.language_combo.currentIndexChanged.connect(self._save)
        self.secondary_combo.currentIndexChanged.connect(self._save)
        self.device_combo.currentIndexChanged.connect(self._save)
        self.auto_inject.stateChanged.connect(self._save)
        self.toggle_mode.stateChanged.connect(self._save)
        self.sound_enabled.stateChanged.connect(self._save)
        self.volume.sliderReleased.connect(self._save)

        self.refresh()

    def refresh(self) -> None:
        if self.orchestrator is None:
            return
        config = self.orchestrator.get_config()
        self._load_devices()
        for combo, value in (
            (self.language_combo, config.get("language", "auto")),
            (self.secondary_combo, config.get("secondary_language", "auto")),
        ):
            index = combo.findData(value)
            combo.setCurrentIndex(index if index >= 0 else 0)
        self.auto_inject.setChecked(bool(config.get("auto_inject", True)))
        self.toggle_mode.setChecked(bool(config.get("toggle_mode", False)))
        self.sound_enabled.setChecked(bool(config.get("sound_feedback", True)))
        self.volume.setValue(int(float(config.get("sound_volume", 0.7)) * 100))
        self.volume_label.setText(f"{self.volume.value()}%")

    def _load_devices(self) -> None:
        if self.device_combo.count():
            return
        self.device_combo.addItem("System default", None)
        try:
            devices = self.orchestrator.recorder.list_devices()
            for index, device in enumerate(devices):
                name = device.get("name") if isinstance(device, dict) else getattr(device, "name", "")
                inputs = (
                    device.get("max_input_channels", 0)
                    if isinstance(device, dict)
                    else getattr(device, "max_input_channels", 0)
                )
                if name and inputs:
                    self.device_combo.addItem(str(name), index)
        except Exception:
            pass

    def _save(self) -> None:
        if self.orchestrator is None:
            return
        self.orchestrator.update_config("language", self.language_combo.currentData())
        self.orchestrator.update_config("secondary_language", self.secondary_combo.currentData())
        self.orchestrator.update_config("audio_device", self.device_combo.currentData())
        self.orchestrator.update_config("auto_inject", self.auto_inject.isChecked())
        self.orchestrator.update_config("toggle_mode", self.toggle_mode.isChecked())
        self.orchestrator.update_config("sound_feedback", self.sound_enabled.isChecked())
        self.orchestrator.update_config("sound_volume", self.volume.value() / 100.0)

    def _test(self) -> None:
        self.test_button.setEnabled(False)
        self.test_result.setText("Recording 3 seconds… speak now")
        self._thread = MicrophoneTestThread(self.device_combo.currentData())
        self._thread.finished_test.connect(self._test_done)
        self._thread.start()

    def _test_done(self, result: dict) -> None:
        self.test_button.setEnabled(True)
        if not result.get("ok"):
            self.test_result.setText(f"Could not open the microphone — {result.get('detail', '')}")
            self.test_result.setObjectName("BadgeBad")
        elif result.get("speech"):
            self.test_result.setText(f"Heard you clearly (peak {result.get('peak')})")
            self.test_result.setObjectName("BadgeOk")
        else:
            self.test_result.setText(f"Captured audio but no speech (peak {result.get('peak')})")
            self.test_result.setObjectName("BadgeWarn")
        self.test_result.style().unpolish(self.test_result)
        self.test_result.style().polish(self.test_result)


# ── AI providers ─────────────────────────────────────────────────────────────


class AIPage(BasePage):
    title = "AI Providers"
    subtitle = "Keys are stored in your operating system's credential store, never in a plaintext file."

    def __init__(self, orchestrator, parent=None):
        super().__init__(orchestrator, parent)

        storage_box = QGroupBox("Credential storage")
        storage_layout = QVBoxLayout(storage_box)
        self.storage_label = QLabel("")
        self.storage_label.setWordWrap(True)
        storage_layout.addWidget(self.storage_label)
        self.body.addWidget(storage_box)

        keys_box = QGroupBox("API keys")
        keys_layout = QVBoxLayout(keys_box)

        self.groq_status = QLabel("")
        self.groq_input = QLineEdit()
        self.groq_input.setEchoMode(QLineEdit.Password)
        self.groq_input.setPlaceholderText("gsk_…  (free at console.groq.com/keys)")
        keys_layout.addLayout(
            self._key_row("Groq (free, recommended)", self.groq_status, self.groq_input, "groq_api_key")
        )

        self.openai_status = QLabel("")
        self.openai_input = QLineEdit()
        self.openai_input.setEchoMode(QLineEdit.Password)
        self.openai_input.setPlaceholderText("sk-…  (paid fallback)")
        keys_layout.addLayout(self._key_row("OpenAI", self.openai_status, self.openai_input, "openai_api_key"))

        keys_layout.addWidget(
            hint(
                "Voxylis prefers Groq because the free tier is fast and generous. OpenAI is used only if Groq is absent."
            )
        )
        self.body.addWidget(keys_box)

        enhancement_box = QGroupBox("Enhancement")
        enhancement_layout = QVBoxLayout(enhancement_box)
        self.enable_enhancement = QCheckBox("Rewrite transcripts with AI before inserting them")
        enhancement_layout.addWidget(self.enable_enhancement)
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Default mode"))
        self.mode_combo = QComboBox()
        for mode in ENHANCEMENT_MODES:
            self.mode_combo.addItem(mode.capitalize(), mode)
        mode_row.addWidget(self.mode_combo, 1)
        enhancement_layout.addLayout(mode_row)
        self.custom_modes_label = QLabel("")
        self.custom_modes_label.setObjectName("Hint")
        enhancement_layout.addWidget(self.custom_modes_label)

        custom_row = QHBoxLayout()
        edit_modes = QPushButton("Edit custom modes…")
        edit_modes.clicked.connect(self._edit_custom_modes)
        custom_row.addWidget(edit_modes)
        custom_row.addStretch()
        enhancement_layout.addLayout(custom_row)
        self.body.addWidget(enhancement_box)

        self.body.addStretch()

        self.enable_enhancement.stateChanged.connect(
            lambda: self.orchestrator.update_config("enable_ai_enhancement", self.enable_enhancement.isChecked())
        )
        self.mode_combo.currentIndexChanged.connect(
            lambda: self.orchestrator.update_config("enhancement_mode", self.mode_combo.currentData())
        )
        self.refresh()

    def _key_row(self, label: str, status_label: QLabel, field: QLineEdit, config_key: str) -> QHBoxLayout:
        row = QHBoxLayout()
        name = QLabel(label)
        name.setMinimumWidth(190)
        row.addWidget(name)
        status_label.setObjectName("Hint")
        status_label.setMinimumWidth(120)
        row.addWidget(status_label)
        row.addWidget(field, 1)
        save = QPushButton("Save")
        save.clicked.connect(lambda: self._save_key(config_key, field))
        row.addWidget(save)
        clear = QPushButton("Remove")
        clear.setObjectName("Danger")
        clear.clicked.connect(lambda: self._remove_key(config_key))
        row.addWidget(clear)
        return row

    def refresh(self) -> None:
        if self.orchestrator is None:
            return
        providers = self.orchestrator.provider_status()
        for key, status_label in (("groq", self.groq_status), ("openai", self.openai_status)):
            configured = providers[key]["configured"]
            status_label.setText("✓ configured" if configured else "not configured")
            status_label.setObjectName("BadgeOk" if configured else "BadgeWarn")
            status_label.style().unpolish(status_label)
            status_label.style().polish(status_label)

        if providers["secure_storage"]:
            self.storage_label.setText(
                f"Secrets are protected by <b>{providers['backend']}</b> (OS-backed). "
                "Settings only record whether a provider is configured."
            )
        else:
            self.storage_label.setText(
                f"<b>Warning:</b> no OS credential store is available on this system, so secrets are only "
                f"obfuscated ({providers['backend']}) rather than encrypted. Install the <code>keyring</code> "
                "package, or run on Windows, to protect keys properly."
            )

        config = self.orchestrator.get_config()
        self.enable_enhancement.setChecked(bool(config.get("enable_ai_enhancement", False)))
        index = self.mode_combo.findData(config.get("enhancement_mode", "formal"))
        self.mode_combo.setCurrentIndex(index if index >= 0 else 0)
        custom = config.get("custom_modes", {}) or {}
        self.custom_modes_label.setText(f"{len(custom)} custom mode(s) defined" if custom else "No custom modes yet.")

    def _save_key(self, config_key: str, field: QLineEdit) -> None:
        value = field.text().strip()
        if not value:
            return
        if self.orchestrator.update_config(config_key, value):
            field.clear()
            field.setPlaceholderText("saved — paste a new key to replace it")
            self.refresh()
        else:
            QMessageBox.warning(self, "Could not save key", "The credential store rejected the write.")

    def _remove_key(self, config_key: str) -> None:
        self.orchestrator.update_config(config_key, "")
        self.refresh()

    def _edit_custom_modes(self) -> None:
        """Open the custom-mode editor and persist the result."""
        from ui.custom_modes_window import CustomModesWindow

        window = CustomModesWindow(self.orchestrator.get_config("custom_modes", {}) or {})
        window.setStyleSheet(theme.stylesheet(str(self.orchestrator.get_config("theme", "dark"))))
        window.modes_changed.connect(self._save_custom_modes)
        window.setAttribute(Qt.WA_DeleteOnClose, True)
        window.show()
        self._custom_modes_window = window

    def _save_custom_modes(self, modes: dict) -> None:
        self.orchestrator.update_config("custom_modes", modes)
        self.refresh()


# ── Shortcuts ────────────────────────────────────────────────────────────────


class ShortcutsPage(BasePage):
    title = "Shortcuts"
    subtitle = "Click a field and press the key combination you want."

    def __init__(self, orchestrator, parent=None):
        super().__init__(orchestrator, parent)

        main_box = QGroupBox("Main recording shortcut")
        main_layout = QVBoxLayout(main_box)
        row = QHBoxLayout()
        row.addWidget(QLabel("Record"))
        self.main_recorder = ShortcutRecorder(orchestrator.get_config("hotkey") or HOTKEY_DEFAULT)
        self.main_recorder.changed.connect(lambda value: self._set_main(value))
        self.main_recorder.invalid.connect(lambda reason: self.conflict_label.setText(reason))
        row.addWidget(self.main_recorder, 1)
        main_layout.addLayout(row)

        self.conflict_label = QLabel("")
        self.conflict_label.setObjectName("BadgeWarn")
        self.conflict_label.setWordWrap(True)
        main_layout.addWidget(self.conflict_label)
        self.body.addWidget(main_box)

        mode_box = QGroupBox("Mode shortcuts")
        mode_layout = QVBoxLayout(mode_box)
        mode_hotkeys = orchestrator.get_config("mode_hotkeys", {}) or {}
        self.casual_recorder = ShortcutRecorder(mode_hotkeys.get("casual", "win+alt"))
        self.technical_recorder = ShortcutRecorder(mode_hotkeys.get("technical", "win+ctrl"))
        for label, recorder in (("Casual mode", self.casual_recorder), ("Technical mode", self.technical_recorder)):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            row.addWidget(recorder, 1)
            mode_layout.addLayout(row)
        mode_layout.addWidget(hint("Mode shortcuts record directly in that mode. Leave one empty to remove it."))
        self.casual_recorder.changed.connect(self._save_mode_hotkeys)
        self.technical_recorder.changed.connect(self._save_mode_hotkeys)
        self.body.addWidget(mode_box)

        behaviour_box = QGroupBox("Behaviour")
        behaviour_layout = QVBoxLayout(behaviour_box)
        self.toggle_mode = QCheckBox("Toggle mode — press once to start, press again to stop")
        behaviour_layout.addWidget(self.toggle_mode)
        self.disable_global = QCheckBox("Disable global shortcuts (use the tray menu / this window instead)")
        behaviour_layout.addWidget(self.disable_global)
        self.listener_status = QLabel("")
        self.listener_status.setObjectName("Hint")
        behaviour_layout.addWidget(self.listener_status)

        reset_row = QHBoxLayout()
        reset = QPushButton("Reset to defaults")
        reset.clicked.connect(self._reset_defaults)
        reset_row.addWidget(reset)
        reset_row.addStretch()
        behaviour_layout.addLayout(reset_row)
        self.body.addWidget(behaviour_box)

        self.body.addStretch()

        self.toggle_mode.stateChanged.connect(
            lambda: self.orchestrator.update_config("toggle_mode", self.toggle_mode.isChecked())
        )
        self.disable_global.stateChanged.connect(self._toggle_global)
        self.refresh()

    def refresh(self) -> None:
        if self.orchestrator is None:
            return
        config = self.orchestrator.get_config()
        self.toggle_mode.setChecked(bool(config.get("toggle_mode", False)))
        self.disable_global.setChecked(bool(config.get("global_shortcuts_disabled", False)))
        listener = self.orchestrator.hotkey_listener
        if listener is None:
            self.listener_status.setText("Shortcut listener unavailable.")
        else:
            state = listener.describe()
            self.listener_status.setText(
                f"Listener: {'active' if state['alive'] else ('disabled' if not state['enabled'] else 'stopped')}"
            )

    def _set_main(self, value: str) -> None:
        if not value:
            self.conflict_label.setText("A shortcut is required — reset to defaults if unsure.")
            return
        if self.orchestrator.update_config("hotkey", value):
            self.conflict_label.setText("")
        else:
            self.conflict_label.setText(f"{format_hotkey(value)} could not be used. Try another combination.")

    def _save_mode_hotkeys(self) -> None:
        mapping = {}
        if self.casual_recorder.value():
            mapping[self.casual_recorder.value()] = "casual"
        if self.technical_recorder.value():
            mapping[self.technical_recorder.value()] = "technical"
        self.orchestrator.update_config("mode_hotkeys", mapping)

    def _toggle_global(self) -> None:
        disabled = self.disable_global.isChecked()
        self.orchestrator.update_config("global_shortcuts_disabled", disabled)
        self.refresh()

    def _reset_defaults(self) -> None:
        self.main_recorder.set_value(HOTKEY_DEFAULT)
        self.casual_recorder.set_value(MODE_HOTKEY_DEFAULTS["win+alt"])
        self.technical_recorder.set_value(MODE_HOTKEY_DEFAULTS["win+ctrl"])
        self.orchestrator.update_config("hotkey", HOTKEY_DEFAULT)
        self._save_mode_hotkeys()
        self.conflict_label.setText("")

    def on_show(self) -> None:
        self.refresh()


# ── Privacy / history storage ────────────────────────────────────────────────


class PrivacyPage(BasePage):
    title = "Privacy"
    subtitle = "What Voxylis stores on this machine, and how to get rid of it."

    def __init__(self, orchestrator, parent=None):
        super().__init__(orchestrator, parent)

        box = QGroupBox("Local storage")
        layout = QVBoxLayout(box)
        self.enabled = QCheckBox("Save transcription history on this device")
        layout.addWidget(self.enabled)

        retention_row = QHBoxLayout()
        retention_row.addWidget(QLabel("Delete entries older than"))
        self.retention = QSpinBox()
        self.retention.setRange(0, 365)
        self.retention.setSuffix(" days")
        self.retention.setSpecialValueText("keep forever")
        retention_row.addWidget(self.retention)
        retention_row.addStretch()
        layout.addLayout(retention_row)

        max_row = QHBoxLayout()
        max_row.addWidget(QLabel("Keep at most"))
        self.max_entries = QSpinBox()
        self.max_entries.setRange(10, 5000)
        self.max_entries.setSuffix(" entries")
        max_row.addWidget(self.max_entries)
        max_row.addStretch()
        layout.addLayout(max_row)

        buttons = QHBoxLayout()
        export = QPushButton("Export…")
        export.clicked.connect(self._export)
        buttons.addWidget(export)
        open_folder = QPushButton("Open data folder")
        open_folder.clicked.connect(self._open_folder)
        buttons.addWidget(open_folder)
        wipe = QPushButton("Delete all history")
        wipe.setObjectName("Danger")
        wipe.clicked.connect(self._wipe)
        buttons.addWidget(wipe)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.storage_info = QLabel("")
        self.storage_info.setObjectName("Mono")
        self.storage_info.setWordWrap(True)
        layout.addWidget(self.storage_info)
        self.body.addWidget(box)

        reports = QGroupBox("Crash reports")
        reports_layout = QVBoxLayout(reports)
        self.crash_reports = QCheckBox("Send a diagnostic report when Voxylis fails")
        reports_layout.addWidget(self.crash_reports)
        reports_note = QLabel(
            "Off by default. When it is on, a failure sends the error type, a stack trace, "
            "the app version, your OS and the provider name — never your transcripts, "
            "clipboard, API keys or account email. Turning it off stops reporting immediately."
        )
        reports_note.setWordWrap(True)
        reports_note.setObjectName("Muted")
        reports_layout.addWidget(reports_note)
        self.body.addWidget(reports)

        facts = QGroupBox("What Voxylis does with your data")
        facts_layout = QVBoxLayout(facts)
        for line in [
            "Audio is sent to your chosen speech provider (Groq or OpenAI) for transcription, then discarded.",
            "Transcripts are stored only in a local SQLite database on this machine.",
            "API keys live in the operating system credential store, not in a settings file.",
            "Diagnostics you copy never include transcripts, keys, tokens or email addresses.",
            "Disabling history stops new recordings from being stored at all.",
            "There is no analytics or usage tracking: the only outbound report is the crash "
            "report above, and only when you enable it.",
        ]:
            bullet = QLabel(f"•  {line}")
            bullet.setWordWrap(True)
            facts_layout.addWidget(bullet)
        self.body.addWidget(facts)

        self.body.addStretch()

        self.enabled.stateChanged.connect(self._save)
        self.retention.valueChanged.connect(self._save)
        self.max_entries.valueChanged.connect(self._save)
        self.crash_reports.stateChanged.connect(self._save_crash_reports)
        self.refresh()

    def refresh(self) -> None:
        if self.orchestrator is None:
            return
        config = self.orchestrator.get_config()
        blocked = self.enabled.blockSignals(True)
        self.enabled.setChecked(bool(config.get("history_enabled", True)))
        self.enabled.blockSignals(blocked)
        blocked = self.retention.blockSignals(True)
        self.retention.setValue(int(config.get("history_retention_days", 0)))
        self.retention.blockSignals(blocked)
        blocked = self.max_entries.blockSignals(True)
        self.max_entries.setValue(int(config.get("max_history", 500)))
        self.max_entries.blockSignals(blocked)
        blocked = self.crash_reports.blockSignals(True)
        self.crash_reports.setChecked(bool(config.get("share_crash_reports", False)))
        self.crash_reports.blockSignals(blocked)

        from utils import paths

        self.storage_info.setText(
            f"database: {self.orchestrator.history.db_path()}\n"
            f"entries:  {len(self.orchestrator.history)}\n"
            f"logs:     {paths.log_path()}"
        )

    def _save(self) -> None:
        self.orchestrator.update_config("history_enabled", self.enabled.isChecked())
        self.orchestrator.update_config("history_retention_days", self.retention.value())
        self.orchestrator.update_config("max_history", self.max_entries.value())
        self.storage_info.setText(self.storage_info.text())

    def _save_crash_reports(self) -> None:
        """Persist the opt-in and apply it to the running process immediately."""
        chosen = self.crash_reports.isChecked()
        self.orchestrator.update_config("share_crash_reports", chosen)
        from utils import observability

        started = observability.set_consent(chosen, self.orchestrator.get_config())
        status = observability.status()
        if chosen and not status["dsn_configured"]:
            QMessageBox.information(
                self,
                "Crash reports",
                "Your choice is saved. This build has no reporting endpoint baked in, so " "nothing will be sent.",
            )
        elif chosen and not started:
            QMessageBox.information(
                self,
                "Crash reports",
                "Your choice is saved, but reports could not start on this system. " f"Reason: {status['reason']}.",
            )

    def _export(self) -> None:
        path, selected = QFileDialog.getSaveFileName(
            self, "Export history", str(Path.home() / "voxylis-history.json"), "JSON (*.json);;CSV (*.csv)"
        )
        if not path:
            return
        fmt = "csv" if path.lower().endswith(".csv") or "csv" in selected.lower() else "json"
        self.orchestrator.history.export(Path(path), fmt=fmt)

    def _open_folder(self) -> None:
        from utils import paths

        _open_in_file_manager(str(paths.data_dir()))

    def _wipe(self) -> None:
        confirm = QMessageBox.question(
            self,
            "Delete all history",
            "Permanently delete every stored transcription?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self.orchestrator.history.clear()
            self.refresh()


def _open_in_file_manager(path: str) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


# ── Account ──────────────────────────────────────────────────────────────────


class AccountPage(BasePage):
    title = "Account"
    subtitle = "Optional. Voxylis works offline with your own provider keys."

    def __init__(self, orchestrator, parent=None):
        super().__init__(orchestrator, parent)

        box = QGroupBox("Voxylis account")
        layout = QVBoxLayout(box)
        self.state_label = QLabel("")
        self.state_label.setWordWrap(True)
        layout.addWidget(self.state_label)
        self.plan_label = QLabel("")
        self.plan_label.setObjectName("Hint")
        layout.addWidget(self.plan_label)

        buttons = QHBoxLayout()
        self.signin_button = QPushButton("Sign in")
        self.signin_button.setObjectName("Primary")
        self.signin_button.clicked.connect(self._sign_in)
        buttons.addWidget(self.signin_button)
        self.signout_button = QPushButton("Sign out")
        self.signout_button.clicked.connect(self._sign_out)
        buttons.addWidget(self.signout_button)
        self.refresh_button = QPushButton("Refresh plan")
        self.refresh_button.clicked.connect(self._refresh_plan)
        buttons.addWidget(self.refresh_button)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.body.addWidget(box)

        note = QGroupBox("How plans work")
        note_layout = QVBoxLayout(note)
        note_layout.addWidget(
            hint(
                "Your plan is decided by the Voxylis server. The desktop app only reads it, so it cannot be "
                "changed from this machine. Transcription with your own provider key is unaffected by plan."
            )
        )
        self.body.addWidget(note)
        self.body.addStretch()
        self.refresh()

    def refresh(self) -> None:
        if self.orchestrator is None:
            return
        config = self.orchestrator.get_config()
        email = (config.get("user_email") or "").strip()
        if email:
            self.state_label.setText(f"Signed in as <b>{email}</b>")
            tier = config.get("tier", "free")
            self.plan_label.setText(f"Plan: {tier} (reported by the server)")
            self.signin_button.setText("Switch account")
            self.signout_button.setEnabled(True)
        else:
            self.state_label.setText("Not signed in — you are using Voxylis locally.")
            self.plan_label.setText("No plan required for local dictation with your own API key.")
            self.signin_button.setText("Sign in")
            self.signout_button.setEnabled(False)

    def _api_base(self) -> str:
        config = self.orchestrator.get_config()
        base = (config.get("api_base") or "").strip()
        if base:
            return base.rstrip("/")
        return f"http://{config.get('web_ui_host', '127.0.0.1')}:{config.get('web_ui_port', 5000)}"

    def _sign_in(self) -> None:
        try:
            from ui.auth0_dialog import Auth0LoginDialog
        except Exception as exc:
            QMessageBox.warning(self, "Sign-in unavailable", f"The sign-in dialog could not load: {exc}")
            return
        dialog = Auth0LoginDialog(self, api_base=self._api_base())
        if not dialog.exec_() or not dialog.result_data:
            return
        data = dialog.result_data
        try:
            from core.user_manager import user_manager

            user_manager.save_auth0_login(
                data["email"],
                data.get("name", ""),
                data["session_id"],
                data.get("tier", "free"),
                data.get("role", "user"),
            )
        except Exception as exc:
            QMessageBox.warning(self, "Could not save session", str(exc))
            return
        try:
            from utils import credentials

            credentials.credential_store.set("session_id", data["session_id"])
        except Exception:
            pass
        self.orchestrator.update_config("session_id", data["session_id"])
        self.orchestrator.update_config("user_email", data["email"])
        self.orchestrator.update_config("tier", data.get("tier", "free"))
        self.orchestrator.update_config("user_role", data.get("role", "user"))
        self.refresh()

    def _sign_out(self) -> None:
        session_id = self.orchestrator.get_config("session_id", "")
        if not session_id:
            try:
                from utils import credentials

                session_id = credentials.credential_store.get("session_id") or ""
            except Exception:
                session_id = ""
        try:
            from core.user_manager import user_manager

            user_manager.logout(session_id)
        except Exception:
            pass
        for key in ("user_email", "tier", "user_role", "session_id"):
            self.orchestrator.update_config(key, "")
        try:
            from utils import credentials

            credentials.credential_store.set("session_id", None)
        except Exception:
            pass
        self.refresh()

    def _refresh_plan(self) -> None:
        import requests

        session_id = None
        try:
            from utils import credentials

            session_id = credentials.credential_store.get("session_id")
        except Exception:
            session_id = None
        if not session_id:
            session_id = self.orchestrator.get_config("session_id", "")
        if not session_id:
            QMessageBox.information(self, "Not signed in", "Sign in first to read your plan from the server.")
            return
        try:
            response = requests.get(
                f"{self._api_base()}/api/subscription",
                headers={"X-Session-Id": session_id},
                timeout=10,
            )
            payload = response.json()
            tier = (payload.get("subscription") or {}).get("tier", "free")
            self.orchestrator.update_config("tier", tier)
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Could not reach the server", str(exc))


# ── Diagnostics ──────────────────────────────────────────────────────────────


class DiagnosticsPage(BasePage):
    title = "Diagnostics"
    subtitle = "Redacted information you can paste into a bug report."

    def __init__(self, orchestrator, parent=None):
        super().__init__(orchestrator, parent)

        buttons = QHBoxLayout()
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh)
        buttons.addWidget(refresh_button)
        copy_button = QPushButton("Copy diagnostics")
        copy_button.clicked.connect(self._copy)
        buttons.addWidget(copy_button)
        logs_button = QPushButton("Open logs folder")
        logs_button.clicked.connect(self._open_logs)
        buttons.addWidget(logs_button)
        errors_button = QPushButton("Error catalogue")
        errors_button.clicked.connect(self._show_catalog)
        buttons.addWidget(errors_button)
        buttons.addStretch()
        self.body.addLayout(buttons)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setObjectName("Mono")
        self.output.setMinimumHeight(420)
        self.body.addWidget(self.output, 1)
        self.refresh()

    def refresh(self) -> None:
        self.output.setPlainText(diagnostics_mod.as_text(orchestrator=self.orchestrator))

    def _copy(self) -> None:
        from PyQt5.QtWidgets import QApplication

        QApplication.clipboard().setText(self.output.toPlainText())

    def _open_logs(self) -> None:
        from utils import paths

        _open_in_file_manager(str(paths.logs_dir()))

    def _show_catalog(self) -> None:
        entries = error_catalog.catalog()
        message = "\n\n".join(f"{key}\n  {value.summary}\n  → {value.action}" for key, value in sorted(entries.items()))
        dialog = QMessageBox(QMessageBox.Information, "Error catalogue", message, QMessageBox.Ok, self)
        dialog.exec_()


# ── About ────────────────────────────────────────────────────────────────────


class AboutPage(BasePage):
    title = "About"

    subtitle = "Voxylis desktop application."

    def __init__(self, orchestrator=None, parent=None):
        super().__init__(orchestrator, parent)

        card_widget = card()
        layout = QVBoxLayout(card_widget)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(6)

        name = QLabel(f"{version.APP_NAME}")
        name.setObjectName("PageTitle")
        layout.addWidget(name)

        tagline = QLabel(
            "System-wide AI dictation for Windows. Press a shortcut, speak, and the text lands in whatever you are working in."
        )
        tagline.setWordWrap(True)
        layout.addWidget(tagline)

        details = QLabel(
            f"<b>Version:</b> {version.__version__} ({version.UPDATE_CHANNEL})<br>"
            f"<b>Engine:</b> {version.ENGINE_NAME}<br>"
            f"<b>Publisher:</b> {version.PUBLISHER}<br>"
            f"<b>Project:</b> <a href='{version.REPO_URL}'>{version.REPO_URL}</a><br>"
            f"{version.COPYRIGHT}"
        )
        details.setOpenExternalLinks(True)
        details.setTextInteractionFlags(Qt.TextBrowserInteraction)
        layout.addWidget(details)

        update_row = QHBoxLayout()
        self.update_button = QPushButton("Check for updates")
        self.update_button.clicked.connect(self._check_updates)
        update_row.addWidget(self.update_button)
        self.update_status = QLabel(f"Current version {version.__version__}")
        self.update_status.setObjectName("Hint")
        self.update_status.setWordWrap(True)
        update_row.addWidget(self.update_status, 1)
        self.download_button = QPushButton("Open download page")
        self.download_button.setObjectName("Link")
        self.download_button.clicked.connect(lambda: __import__("webbrowser").open(version.RELEASES_URL))
        update_row.addWidget(self.download_button)
        layout.addLayout(update_row)
        self.body.addWidget(card_widget)

        license_card = card()
        license_layout = QVBoxLayout(license_card)
        license_layout.setContentsMargins(24, 18, 24, 18)
        license_layout.addLayout(section("Licences"))
        license_layout.addWidget(
            hint(
                "Voxylis is released under the MIT Licence. Speech recognition and language models are provided by "
                "your own Groq or OpenAI account and are subject to those providers' terms."
            )
        )
        self.body.addWidget(license_card)
        self.body.addStretch()

    # -- updates -----------------------------------------------------------

    def _check_updates(self) -> None:
        """Ask the release feed whether a newer build exists."""
        from core import updater as updater_module

        self.update_button.setEnabled(False)
        self.update_status.setText("Checking for updates…")

        def done(info) -> None:
            from PyQt5.QtCore import QTimer

            QTimer.singleShot(0, lambda: self._apply_update_result(info))

        updater_module.check_async(done)

    def _apply_update_result(self, info) -> None:
        self.update_button.setEnabled(True)
        if info.error and not info.available:
            self.update_status.setText(
                "No update feed is reachable right now. You can still download the latest build manually."
            )
            return
        if info.available:
            self.update_status.setText(
                f"Version {info.latest} is available (you have {info.current}). "
                "Voxylis downloads and verifies the installer before running it."
            )
            self.update_button.setText("Download and install")
            try:
                self.update_button.clicked.disconnect()
            except Exception:
                pass
            self.update_button.clicked.connect(lambda: self._download_update(info))
            return
        self.update_status.setText(f"You are up to date (version {info.current}).")

    def _download_update(self, info) -> None:
        from core import updater as updater_module

        self.update_button.setEnabled(False)
        self.update_status.setText("Downloading the installer…")
        updater = updater_module.Updater()

        def progress(done: int, total: int) -> None:
            if total:
                self.update_status.setText(f"Downloading… {done * 100 // total}%")

        result = updater.download(info, progress=progress)
        self.update_button.setEnabled(True)
        if not result.ok or result.path is None:
            self.update_status.setText(f"Update failed: {result.detail}. Try the download page instead.")
            return
        if not result.verified:
            self.update_status.setText(
                f"Downloaded to {result.path}, but it could not be verified ({result.detail}). "
                "The installer was not launched. Download it manually from the release page."
            )
            return
        self.update_status.setText("Verified. Voxylis will close so the installer can replace files.")
        if updater.launch_installer(result.path):
            from PyQt5.QtWidgets import QApplication

            QApplication.quit()
