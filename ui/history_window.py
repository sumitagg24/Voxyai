"""
Transcription History Panel for Voxylis
"""

from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QPushButton,
    QTextEdit,
    QSplitter,
    QMessageBox,
)
from PyQt5.QtCore import Qt, pyqtSignal


class HistoryWindow(QMainWindow):
    """Floating history panel showing past transcriptions."""

    inject_requested = pyqtSignal(str)  # emitted when user clicks Re-inject
    closed = pyqtSignal()

    def __init__(self, history_manager):
        super().__init__()
        self.history_manager = history_manager
        self._init_ui()
        self.refresh()

    def _init_ui(self):
        self.setWindowTitle("Voxylis — Transcription History")
        self.setGeometry(100, 100, 680, 500)
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #1e1e1e; color: #e0e0e0; }
            QListWidget { background: #252525; border: 1px solid #444;
                          border-radius: 4px; font-size: 12px; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #333; }
            QListWidget::item:selected { background: #3a3a5c; }
            QTextEdit { background: #252525; border: 1px solid #444;
                        border-radius: 4px; font-size: 13px; }
            QPushButton { background: #3a3a5c; color: #e0e0e0; border: none;
                          border-radius: 4px; padding: 6px 14px; font-size: 12px; }
            QPushButton:hover { background: #4a4a7c; }
            QPushButton#danger { background: #5c2a2a; }
            QPushButton#danger:hover { background: #7c3a3a; }
            QLabel#heading { font-size: 14px; font-weight: bold; color: #aaaaff; }
            QLabel#meta { font-size: 11px; color: #888; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Transcription History")
        title.setObjectName("heading")
        hdr.addWidget(title)
        hdr.addStretch()
        self.count_label = QLabel("")
        self.count_label.setObjectName("meta")
        hdr.addWidget(self.count_label)
        root.addLayout(hdr)

        # Splitter: list on left, preview on right
        splitter = QSplitter(Qt.Horizontal)

        # Left — list
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self._on_select)
        lv.addWidget(self.list_widget)
        splitter.addWidget(left)

        # Right — preview + actions
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(6)

        self.meta_label = QLabel("Select an entry to preview")
        self.meta_label.setObjectName("meta")
        rv.addWidget(self.meta_label)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("Select an entry to preview...")
        rv.addWidget(self.preview)

        btn_row = QHBoxLayout()
        self.inject_btn = QPushButton("Re-inject")
        self.inject_btn.clicked.connect(self._on_inject)
        self.inject_btn.setEnabled(False)
        btn_row.addWidget(self.inject_btn)

        self.copy_btn = QPushButton("Copy")
        self.copy_btn.clicked.connect(self._on_copy)
        self.copy_btn.setEnabled(False)
        btn_row.addWidget(self.copy_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("danger")
        self.delete_btn.clicked.connect(self._on_delete)
        self.delete_btn.setEnabled(False)
        btn_row.addWidget(self.delete_btn)
        rv.addLayout(btn_row)

        splitter.addWidget(right)
        splitter.setSizes([260, 400])
        root.addWidget(splitter)

        # Bottom bar
        bot = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        bot.addWidget(refresh_btn)
        bot.addStretch()
        clear_btn = QPushButton("Clear All")
        clear_btn.setObjectName("danger")
        clear_btn.clicked.connect(self._on_clear_all)
        bot.addWidget(clear_btn)
        root.addLayout(bot)

    # ── data ──────────────────────────────────────────────────────────────────

    def refresh(self):
        """Reload entries from history manager."""
        self.list_widget.clear()
        entries = self.history_manager.get_all()
        self.count_label.setText(f"{len(entries)} entries")

        for entry in entries:
            preview = entry["enhanced"][:60].replace("\n", " ")
            if len(entry["enhanced"]) > 60:
                preview += "..."
            item = QListWidgetItem(f"[{entry['timestamp']}]\n{preview}")
            item.setData(Qt.UserRole, entry)
            self.list_widget.addItem(item)

        self._clear_preview()

    def _clear_preview(self):
        self.preview.clear()
        self.meta_label.setText("Select an entry to preview")
        self.inject_btn.setEnabled(False)
        self.copy_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)

    # ── slots ─────────────────────────────────────────────────────────────────

    def _on_select(self, row: int):
        if row < 0:
            self._clear_preview()
            return
        item = self.list_widget.item(row)
        if not item:
            return
        entry = item.data(Qt.UserRole)
        self.preview.setPlainText(entry["enhanced"])
        self.meta_label.setText(
            f"Mode: {entry.get('mode', '-')}  |  "
            f"Words: {entry.get('word_count', '-')}  |  "
            f"{entry['timestamp']}"
        )
        self.inject_btn.setEnabled(True)
        self.copy_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)

    def _current_entry(self):
        item = self.list_widget.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _on_inject(self):
        entry = self._current_entry()
        if entry:
            self.inject_requested.emit(entry["enhanced"])
            self.hide()

    def _on_copy(self):
        entry = self._current_entry()
        if entry:
            from PyQt5.QtWidgets import QApplication

            QApplication.clipboard().setText(entry["enhanced"])

    def _on_delete(self):
        entry = self._current_entry()
        if entry:
            self.history_manager.delete(entry["id"])
            self.refresh()

    def _on_clear_all(self):
        if (
            QMessageBox.question(
                self,
                "Clear History",
                "Delete all transcription history?",
                QMessageBox.Yes | QMessageBox.No,
            )
            == QMessageBox.Yes
        ):
            self.history_manager.clear()
            self.refresh()

    def closeEvent(self, event):
        self.closed.emit()
        event.accept()
