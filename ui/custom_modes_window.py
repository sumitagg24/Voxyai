"""
Custom Enhancement Modes editor for Voxylis
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QLabel, QPushButton,
    QLineEdit, QTextEdit, QMessageBox, QSplitter
)
from PyQt5.QtCore import Qt, pyqtSignal
from utils.logger import log_info

# Built-in modes that cannot be deleted
BUILTIN_MODES = {"formal", "casual", "technical", "concise", "creative"}


class CustomModesWindow(QMainWindow):
    """Editor for custom AI enhancement modes."""

    modes_changed = pyqtSignal(dict)   # emits full custom_modes dict on save
    closed = pyqtSignal()

    def __init__(self, custom_modes: dict):
        super().__init__()
        self.custom_modes = dict(custom_modes)   # name -> prompt
        self._init_ui()
        self._refresh_list()

    def _init_ui(self):
        self.setWindowTitle("Voxylis — Custom Enhancement Modes")
        self.setGeometry(150, 150, 720, 520)
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #1e1e1e; color: #e0e0e0; }
            QListWidget { background: #252525; border: 1px solid #444;
                          border-radius: 4px; font-size: 12px; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #333; }
            QListWidget::item:selected { background: #3a3a5c; }
            QLineEdit, QTextEdit { background: #252525; border: 1px solid #444;
                                   border-radius: 4px; color: #e0e0e0;
                                   font-size: 13px; padding: 4px; }
            QPushButton { background: #3a3a5c; color: #e0e0e0; border: none;
                          border-radius: 4px; padding: 6px 14px; font-size: 12px; }
            QPushButton:hover { background: #4a4a7c; }
            QPushButton#danger { background: #5c2a2a; }
            QPushButton#danger:hover { background: #7c3a3a; }
            QPushButton#save { background: #2a5c2a; }
            QPushButton#save:hover { background: #3a7c3a; }
            QLabel#heading { font-size: 14px; font-weight: bold; color: #aaaaff; }
            QLabel#hint { font-size: 11px; color: #888; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        title = QLabel("Custom Enhancement Modes")
        title.setObjectName("heading")
        root.addWidget(title)

        hint = QLabel(
            "Write a prompt that tells the AI how to transform your speech. "
            "Use {text} as the placeholder for the transcribed text."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        splitter = QSplitter(Qt.Horizontal)

        # Left — mode list
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(4)
        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self._on_select)
        lv.addWidget(self.list_widget)

        add_btn = QPushButton("+ New Mode")
        add_btn.clicked.connect(self._on_new)
        lv.addWidget(add_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("danger")
        self.delete_btn.clicked.connect(self._on_delete)
        self.delete_btn.setEnabled(False)
        lv.addWidget(self.delete_btn)

        splitter.addWidget(left)

        # Right — editor
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(6)

        rv.addWidget(QLabel("Mode Name:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Email Reply")
        rv.addWidget(self.name_input)

        rv.addWidget(QLabel("Prompt (use {text} for the transcribed speech):"))
        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText(
            "e.g. Rewrite the following as a professional email reply.\n\n{text}\n\nReturn only the email."
        )
        rv.addWidget(self.prompt_input)

        # Example presets
        presets_label = QLabel("Quick presets:")
        presets_label.setObjectName("hint")
        rv.addWidget(presets_label)

        presets_row = QHBoxLayout()
        for label, prompt in [
            ("Email Reply",     "Rewrite the following as a professional email reply.\n\n{text}\n\nReturn only the email."),
            ("Bullet Points",   "Convert the following into a clear bullet point list.\n\n{text}\n\nReturn only the bullet points."),
            ("Fix Grammar",     "Fix only the grammar and punctuation of the following text. Do not change any words or style.\n\n{text}\n\nReturn only the corrected text."),
            ("Translate ES",    "Translate the following text to Spanish.\n\n{text}\n\nReturn only the translation."),
        ]:
            btn = QPushButton(label)
            btn.setProperty("preset_prompt", prompt)
            btn.setProperty("preset_name", label)
            btn.clicked.connect(self._on_preset)
            presets_row.addWidget(btn)
        rv.addLayout(presets_row)

        save_btn = QPushButton("Save Mode")
        save_btn.setObjectName("save")
        save_btn.clicked.connect(self._on_save_mode)
        rv.addWidget(save_btn)

        splitter.addWidget(right)
        splitter.setSizes([200, 500])
        root.addWidget(splitter)

        # Bottom
        bot = QHBoxLayout()
        bot.addStretch()
        done_btn = QPushButton("Done")
        done_btn.clicked.connect(self._on_done)
        bot.addWidget(done_btn)
        root.addLayout(bot)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _refresh_list(self):
        self.list_widget.clear()
        for name in self.custom_modes:
            item = QListWidgetItem(name)
            self.list_widget.addItem(item)
        self._clear_editor()

    def _clear_editor(self):
        self.name_input.clear()
        self.prompt_input.clear()
        self.delete_btn.setEnabled(False)

    # ── slots ─────────────────────────────────────────────────────────────────

    def _on_select(self, row: int):
        if row < 0:
            self._clear_editor()
            return
        item = self.list_widget.item(row)
        if not item:
            return
        name = item.text()
        self.name_input.setText(name)
        self.prompt_input.setPlainText(self.custom_modes.get(name, ""))
        self.delete_btn.setEnabled(True)

    def _on_new(self):
        self.list_widget.clearSelection()
        self._clear_editor()
        self.name_input.setFocus()

    def _on_preset(self):
        btn = self.sender()
        self.name_input.setText(btn.property("preset_name"))
        self.prompt_input.setPlainText(btn.property("preset_prompt"))

    def _on_save_mode(self):
        name = self.name_input.text().strip()
        prompt = self.prompt_input.toPlainText().strip()

        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter a mode name.")
            return
        if not prompt:
            QMessageBox.warning(self, "Missing Prompt", "Please enter a prompt.")
            return
        if "{text}" not in prompt:
            QMessageBox.warning(self, "Missing {text}",
                                "Your prompt must contain {text} as a placeholder.")
            return

        self.custom_modes[name] = prompt
        self._refresh_list()
        # Re-select the saved item
        for i in range(self.list_widget.count()):
            if self.list_widget.item(i).text() == name:
                self.list_widget.setCurrentRow(i)
                break
        log_info(f"Custom mode saved: {name}")

    def _on_delete(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        name = item.text()
        if QMessageBox.question(
            self, "Delete Mode", f"Delete mode '{name}'?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            self.custom_modes.pop(name, None)
            self._refresh_list()

    def _on_done(self):
        self.modes_changed.emit(self.custom_modes)
        self.close()

    def closeEvent(self, event):
        self.closed.emit()
        event.accept()
