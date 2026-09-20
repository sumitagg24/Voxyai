"""
Settings window for Voxylis — all features in one place.
"""

from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QCheckBox,
    QTabWidget,
    QSpinBox,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSlider,
)
from PyQt5.QtCore import Qt, pyqtSignal
from utils.logger import log_info

LANGUAGES = [
    ("Auto-detect", "auto"),
    ("English", "en"),
    ("Spanish", "es"),
    ("French", "fr"),
    ("German", "de"),
    ("Italian", "it"),
    ("Portuguese", "pt"),
    ("Japanese", "ja"),
    ("Chinese", "zh"),
    ("Hindi", "hi"),
    ("Bengali", "bn"),
    ("Punjabi", "pa"),
    ("Gujarati", "gu"),
    ("Tamil", "ta"),
    ("Telugu", "te"),
    ("Malayalam", "ml"),
    ("Marathi", "mr"),
    ("Urdu", "ur"),
    ("Hinglish", "hi-en"),
    ("Arabic", "ar"),
    ("Russian", "ru"),
    ("Turkish", "tr"),
    ("Dutch", "nl"),
    ("Polish", "pl"),
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
    ("Thai", "th"),
    ("Vietnamese", "vi"),
    ("Indonesian", "id"),
    ("Malay", "ms"),
    ("Tagalog", "tl"),
]
BUILTIN_MODES = ["formal", "casual", "technical", "concise", "creative"]


class SettingsWindow(QMainWindow):
    settings_changed = pyqtSignal(str, object)
    closed = pyqtSignal()

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("Voxylis — Settings")
        self.setGeometry(180, 180, 660, 560)
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #1e1e1e; color: #e0e0e0; font-size: 13px; }
            QTabWidget::pane { border: 1px solid #444; }
            QTabBar::tab { background: #2a2a2a; color: #aaa; padding: 8px 16px; }
            QTabBar::tab:selected { background: #3a3a5c; color: #fff; }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit {
                background: #252525; border: 1px solid #555; border-radius: 4px;
                color: #e0e0e0; padding: 4px; }
            QPushButton { background: #3a3a5c; color: #e0e0e0; border: none;
                          border-radius: 4px; padding: 7px 18px; }
            QPushButton:hover { background: #4a4a7c; }
            QPushButton#save { background: #2a5c2a; }
            QPushButton#save:hover { background: #3a7c3a; }
            QCheckBox { spacing: 8px; }
            QGroupBox { border: 1px solid #444; border-radius: 4px;
                        margin-top: 8px; padding-top: 8px; color: #aaaaff; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; }
            QSlider::groove:horizontal { height: 4px; background: #444; border-radius: 2px; }
            QSlider::handle:horizontal { width: 14px; height: 14px; background: #7070cc;
                                         border-radius: 7px; margin: -5px 0; }
            QTableWidget { background: #252525; gridline-color: #444; }
            QHeaderView::section { background: #2a2a2a; color: #aaa; padding: 4px; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)

        tabs = QTabWidget()
        tabs.addTab(self._tab_general(), "General")
        tabs.addTab(self._tab_hotkeys(), "Hotkeys")
        tabs.addTab(self._tab_ai(), "AI & Language")
        tabs.addTab(self._tab_sound(), "Sound")
        tabs.addTab(self._tab_profiles(), "App Profiles")
        tabs.addTab(self._tab_advanced(), "Advanced")
        root.addWidget(tabs)

        btns = QHBoxLayout()
        btns.addStretch()
        save = QPushButton("Save Settings")
        save.setObjectName("save")
        save.clicked.connect(self._save)
        btns.addWidget(save)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.close)
        btns.addWidget(cancel)
        root.addLayout(btns)

    # ── General ───────────────────────────────────────────────────────────────

    def _tab_general(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        f.setSpacing(10)

        self.auto_inject = QCheckBox()
        self.auto_inject.setChecked(self.config.get("auto_inject", True))
        self.show_widget = QCheckBox()
        self.show_widget.setChecked(self.config.get("show_floating_widget", True))
        self.startup_boot = QCheckBox()
        self.startup_boot.setChecked(self.config.get("startup_on_boot", False))
        self.toggle_mode = QCheckBox()
        self.toggle_mode.setChecked(self.config.get("toggle_mode", False))

        f.addRow("Auto-inject text after recording:", self.auto_inject)
        f.addRow("Show floating widget:", self.show_widget)
        f.addRow("Start with Windows:", self.startup_boot)

        grp = QGroupBox("Recording Mode")
        gl = QVBoxLayout(grp)
        self.toggle_mode.setText(
            "Toggle mode  (press once = start, press again = stop)"
        )
        hint = QLabel("Default: hold hotkey to record, release to stop.")
        hint.setStyleSheet("color:#888; font-size:11px;")
        gl.addWidget(hint)
        gl.addWidget(self.toggle_mode)
        f.addRow(grp)
        return w

    # ── Hotkeys ───────────────────────────────────────────────────────────────

    def _tab_hotkeys(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(10)

        grp1 = QGroupBox("Main Recording Hotkey")
        f1 = QFormLayout(grp1)
        self.hotkey_input = QLineEdit(self.config.get("hotkey", "win+shift"))
        hint1 = QLabel(
            "Safe combos: win+shift, win+alt, win+ctrl, ctrl+alt+r\n"
            "Avoid: ctrl+c, ctrl+v, alt+tab, win+d"
        )
        hint1.setStyleSheet("color:#888; font-size:11px;")
        f1.addRow("Hotkey:", self.hotkey_input)
        f1.addRow(hint1)
        layout.addWidget(grp1)

        grp2 = QGroupBox("Per-Mode Hotkeys  (optional)")
        f2 = QFormLayout(grp2)
        mode_hotkeys = self.config.get("mode_hotkeys", {})
        self.casual_hk = QLineEdit(mode_hotkeys.get("casual", "win+alt"))
        self.technical_hk = QLineEdit(mode_hotkeys.get("technical", "win+ctrl"))
        hint2 = QLabel(
            "These hotkeys record and force a specific mode, ignoring the default."
        )
        hint2.setStyleSheet("color:#888; font-size:11px;")
        f2.addRow("Casual mode hotkey:", self.casual_hk)
        f2.addRow("Technical mode hotkey:", self.technical_hk)
        f2.addRow(hint2)
        layout.addWidget(grp2)
        layout.addStretch()
        return w

    # ── AI & Language ─────────────────────────────────────────────────────────

    def _tab_ai(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        f.setSpacing(10)

        self.groq_key = QLineEdit(self.config.get("groq_api_key", ""))
        self.groq_key.setEchoMode(QLineEdit.Password)
        self.groq_key.setPlaceholderText("gsk_...  (free at console.groq.com/keys)")

        self.openai_key = QLineEdit(self.config.get("openai_api_key", ""))
        self.openai_key.setEchoMode(QLineEdit.Password)
        self.openai_key.setPlaceholderText("sk-...  (paid, fallback)")

        self.lang_combo = QComboBox()
        for label, code in LANGUAGES:
            self.lang_combo.addItem(label, code)
        cur_lang = self.config.get("language", "auto")
        idx = next((i for i, (_, c) in enumerate(LANGUAGES) if c == cur_lang), 0)
        self.lang_combo.setCurrentIndex(idx)

        # Secondary language (fallback)
        self.secondary_lang_combo = QComboBox()
        for label, code in LANGUAGES:
            self.secondary_lang_combo.addItem(label, code)
        cur_secondary = self.config.get("secondary_language", "auto")
        idx = next((i for i, (_, c) in enumerate(LANGUAGES) if c == cur_secondary), 0)
        self.secondary_lang_combo.setCurrentIndex(idx)

        all_modes = BUILTIN_MODES + list(self.config.get("custom_modes", {}).keys())
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(all_modes)
        self.mode_combo.setCurrentText(self.config.get("enhancement_mode", "formal"))

        self.enable_enhance = QCheckBox()
        self.enable_enhance.setChecked(self.config.get("enable_ai_enhancement", False))

        f.addRow("Primary Language:", self.lang_combo)
        f.addRow("Secondary Language (fallback):", self.secondary_lang_combo)
        f.addRow("Enhancement Mode:", self.mode_combo)
        f.addRow("Enable AI Enhancement:", self.enable_enhance)

        note = QLabel(
            "Primary Language: Whisper detects your language automatically.\n"
            "Secondary Language: Used as fallback when primary is not detected.\n"
            "Enhancement uses Groq LLaMA (free) or OpenAI GPT."
        )
        note.setStyleSheet("color:#888; font-size:11px;")
        note.setWordWrap(True)
        f.addRow(note)
        return w

    # ── Sound ─────────────────────────────────────────────────────────────────

    def _tab_sound(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        f.setSpacing(10)

        self.sound_enabled = QCheckBox()
        self.sound_enabled.setChecked(self.config.get("sound_feedback", True))

        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(int(self.config.get("sound_volume", 0.7) * 100))
        self.vol_label = QLabel(f"{self.vol_slider.value()}%")
        self.vol_slider.valueChanged.connect(lambda v: self.vol_label.setText(f"{v}%"))

        vol_row = QHBoxLayout()
        vol_row.addWidget(self.vol_slider)
        vol_row.addWidget(self.vol_label)
        vol_w = QWidget()
        vol_w.setLayout(vol_row)

        f.addRow("Sound feedback:", self.sound_enabled)
        f.addRow("Volume:", vol_w)

        legend = QLabel(
            "High beep  →  recording started\n"
            "Low beep   →  recording stopped\n"
            "Two chimes →  text injected\n"
            "Low buzz   →  error"
        )
        legend.setStyleSheet("color:#888; font-size:11px;")
        f.addRow(legend)
        return w

    # ── App Profiles ──────────────────────────────────────────────────────────

    def _tab_profiles(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(8)

        note = QLabel(
            "Automatically switch enhancement mode based on the focused app.\n"
            "Keyword is matched against the app's window title or exe name."
        )
        note.setStyleSheet("color:#888; font-size:11px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        self.profiles_table = QTableWidget(0, 2)
        self.profiles_table.setHorizontalHeaderLabels(["App keyword", "Mode"])
        self.profiles_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.profiles_table.setMinimumHeight(200)

        profiles = self.config.get("app_profiles", {})
        for kw, mode in profiles.items():
            self._add_profile_row(kw, mode)

        layout.addWidget(self.profiles_table)

        btns = QHBoxLayout()
        add_btn = QPushButton("+ Add Row")
        add_btn.clicked.connect(lambda: self._add_profile_row("", "formal"))
        del_btn = QPushButton("Remove Selected")
        del_btn.clicked.connect(self._del_profile_row)
        btns.addWidget(add_btn)
        btns.addWidget(del_btn)
        btns.addStretch()
        layout.addLayout(btns)

        example = QLabel(
            "Examples: slack → casual,  winword → formal,  code → technical"
        )
        example.setStyleSheet("color:#666; font-size:11px;")
        layout.addWidget(example)
        return w

    def _add_profile_row(self, kw: str, mode: str):
        r = self.profiles_table.rowCount()
        self.profiles_table.insertRow(r)
        self.profiles_table.setItem(r, 0, QTableWidgetItem(kw))
        combo = QComboBox()
        all_modes = BUILTIN_MODES + list(self.config.get("custom_modes", {}).keys())
        combo.addItems(all_modes)
        if mode in all_modes:
            combo.setCurrentText(mode)
        self.profiles_table.setCellWidget(r, 1, combo)

    def _del_profile_row(self):
        row = self.profiles_table.currentRow()
        if row >= 0:
            self.profiles_table.removeRow(row)

    # ── Advanced ──────────────────────────────────────────────────────────────

    def _tab_advanced(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        f.setSpacing(10)

        self.log_level = QComboBox()
        self.log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level.setCurrentText(self.config.get("log_level", "INFO"))

        self.max_history = QSpinBox()
        self.max_history.setRange(10, 1000)
        self.max_history.setValue(self.config.get("max_history", 100))

        self.sample_rate = QSpinBox()
        self.sample_rate.setRange(8000, 48000)
        self.sample_rate.setSingleStep(1000)
        self.sample_rate.setValue(self.config.get("sample_rate", 16000))

        f.addRow("Log Level:", self.log_level)
        f.addRow("Max History Entries:", self.max_history)
        f.addRow("Audio Sample Rate (Hz):", self.sample_rate)
        return w

    # ── save ──────────────────────────────────────────────────────────────────

    def _save(self):
        # Build mode_hotkeys dict
        mode_hotkeys = {}
        if self.casual_hk.text().strip():
            mode_hotkeys[self.casual_hk.text().strip()] = "casual"
        if self.technical_hk.text().strip():
            mode_hotkeys[self.technical_hk.text().strip()] = "technical"

        # Build app_profiles dict
        profiles = {}
        for r in range(self.profiles_table.rowCount()):
            kw_item = self.profiles_table.item(r, 0)
            combo = self.profiles_table.cellWidget(r, 1)
            if kw_item and combo:
                kw = kw_item.text().strip().lower()
                if kw:
                    profiles[kw] = combo.currentText()

        settings = {
            "auto_inject": self.auto_inject.isChecked(),
            "show_floating_widget": self.show_widget.isChecked(),
            "startup_on_boot": self.startup_boot.isChecked(),
            "toggle_mode": self.toggle_mode.isChecked(),
            "hotkey": self.hotkey_input.text().strip(),
            "mode_hotkeys": mode_hotkeys,
            "groq_api_key": self.groq_key.text().strip(),
            "openai_api_key": self.openai_key.text().strip(),
            "language": self.lang_combo.currentData(),
            "secondary_language": self.secondary_lang_combo.currentData(),
            "enhancement_mode": self.mode_combo.currentText(),
            "enable_ai_enhancement": self.enable_enhance.isChecked(),
            "sound_feedback": self.sound_enabled.isChecked(),
            "sound_volume": self.vol_slider.value() / 100.0,
            "app_profiles": profiles,
            "log_level": self.log_level.currentText(),
            "max_history": self.max_history.value(),
            "sample_rate": self.sample_rate.value(),
        }

        for k, v in settings.items():
            self.settings_changed.emit(k, v)

        log_info("Settings saved")
        self.close()

    def closeEvent(self, event):
        self.closed.emit()
        event.accept()
