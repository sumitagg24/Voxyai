"""
Friendly error dialog.

Replaces raw ``QMessageBox.warning(..., "Error: HTTP 401")`` popups with a
dialog that answers: what happened, why, and what to do.  Technical detail is
hidden behind "Show diagnostics" and is copyable for bug reports.
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from core.errors import VoxylisError, friendly_error
from ui import theme


class ErrorDialog(QDialog):
    """Modal, plain-language error report."""

    def __init__(self, error: VoxylisError, parent=None, diagnostics_text: str = ""):
        super().__init__(parent)
        self.error = error
        self.diagnostics_text = diagnostics_text
        self.open_settings_section: Optional[str] = None
        self.retry_requested = False

        self.setWindowTitle(error.title)
        self.setStyleSheet(theme.stylesheet())
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(12)

        title = QLabel(error.title)
        title.setObjectName("PageTitle")
        root.addWidget(title)

        summary = QLabel(error.summary)
        summary.setWordWrap(True)
        summary.setStyleSheet("font-size: 14px;")
        root.addWidget(summary)

        if error.cause:
            cause = QLabel(f"<b>Why:</b> {error.cause}")
            cause.setWordWrap(True)
            cause.setObjectName("Hint")
            root.addWidget(cause)

        if error.action:
            action = QLabel(f"<b>What to do:</b> {error.action}")
            action.setWordWrap(True)
            root.addWidget(action)

        self.detail_box = QPlainTextEdit()
        self.detail_box.setReadOnly(True)
        self.detail_box.setObjectName("Mono")
        self.detail_box.setPlainText(self._build_detail())
        self.detail_box.setVisible(False)
        self.detail_box.setMinimumHeight(140)
        root.addWidget(self.detail_box)

        self.toggle_button = QPushButton("Show diagnostics")
        self.toggle_button.setObjectName("Link")
        self.toggle_button.clicked.connect(self._toggle_detail)
        root.addWidget(self.toggle_button, alignment=Qt.AlignLeft)

        buttons = QHBoxLayout()
        buttons.addStretch()

        if error.settings_section:
            settings_button = QPushButton(f"Open {error.settings_section}")
            settings_button.clicked.connect(self._open_settings)
            buttons.addWidget(settings_button)

        if error.retryable:
            retry_button = QPushButton("Retry")
            retry_button.clicked.connect(self._retry)
            buttons.addWidget(retry_button)

        copy_button = QPushButton("Copy diagnostics")
        copy_button.clicked.connect(self._copy)
        buttons.addWidget(copy_button)

        close_button = QPushButton("Close")
        close_button.setObjectName("Primary")
        close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button)
        root.addLayout(buttons)

    # ── internals ─────────────────────────────────────────────────────────

    def _build_detail(self) -> str:
        parts = [
            f"code: {self.error.code}",
            f"summary: {self.error.summary}",
            f"detail: {self.error.detail or 'n/a'}",
        ]
        if self.diagnostics_text:
            parts.append("")
            parts.append(self.diagnostics_text)
        return "\n".join(parts)

    def _toggle_detail(self) -> None:
        visible = not self.detail_box.isVisible()
        self.detail_box.setVisible(visible)
        self.toggle_button.setText("Hide diagnostics" if visible else "Show diagnostics")
        self.adjustSize()

    def _open_settings(self) -> None:
        self.open_settings_section = self.error.settings_section
        self.accept()

    def _retry(self) -> None:
        self.retry_requested = True
        self.accept()

    def _copy(self) -> None:
        from PyQt5.QtWidgets import QApplication

        QApplication.clipboard().setText(self.detail_box.toPlainText())


def show_error(error, parent=None, diagnostics: Optional[Callable[[], str]] = None) -> Optional[str]:
    """Show an error dialog.

    Accepts either a :class:`VoxylisError` or a legacy string error code.
    Returns the settings section the user asked to open, ``"retry"`` when the
    user chose retry, or ``None``.
    """
    if not isinstance(error, VoxylisError):
        error = friendly_error(str(error) or "pipeline_error")

    diag_text = ""
    if diagnostics is not None:
        try:
            diag_text = diagnostics()
        except Exception:
            diag_text = ""

    dialog = ErrorDialog(error, parent=parent, diagnostics_text=diag_text)
    dialog.exec_()
    if dialog.retry_requested:
        return "retry"
    return dialog.open_settings_section


def build_diagnostics_text(orchestrator=None) -> str:
    """Best-effort redacted diagnostics string; never raises."""
    try:
        from ui import diagnostics

        return diagnostics.as_text(orchestrator=orchestrator)
    except Exception:
        return "diagnostics unavailable"
