"""
Persistent main window for Voxylis - the primary desktop surface.

The tray icon and the recording overlay are secondary surfaces.  This window is
where the user starts and stops recordings, reviews history, configures
providers, manages shortcuts, checks privacy settings, reads diagnostics and
signs in.  It is created once, hidden on close (never destroyed) and re-shown
from the tray, which is what makes Voxylis feel like an application rather than
a tray utility.
"""

from __future__ import annotations

from typing import Dict, Optional

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from config import version
from core.event_manager import Events, event_manager
from ui import theme
from ui.pages import (
    AboutPage,
    AccountPage,
    AIPage,
    DiagnosticsPage,
    HistoryPage,
    HomePage,
    PrivacyPage,
    ShortcutsPage,
    VoicePage,
)

PAGES = [
    ("home", "Home", HomePage),
    ("history", "History", HistoryPage),
    ("microphone", "Microphone", VoicePage),
    ("ai", "AI Providers", AIPage),
    ("shortcuts", "Shortcuts", ShortcutsPage),
    ("privacy", "Privacy", PrivacyPage),
    ("account", "Account", AccountPage),
    ("diagnostics", "Diagnostics", DiagnosticsPage),
    ("about", "About", AboutPage),
]

#: Map a page title to the nav key, used by "Open <section>" error actions.
SECTION_TO_PAGE = {
    "AI Providers": "ai",
    "Enhancement": "ai",
    "Microphone": "microphone",
    "Shortcuts": "shortcuts",
    "Privacy": "privacy",
    "Account": "account",
    "Diagnostics": "diagnostics",
}


def app_icon(size: int = 64) -> QIcon:
    """Draw the Voxylis mark in code so no binary asset is required.

    A rounded square with a waveform: distinct from a stock microphone glyph,
    and identical to the icon used by the installer/tray at their own sizes.
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QBrush(QColor(theme.palette()["accent"])))
    painter.setPen(Qt.NoPen)
    radius = size * 0.28
    painter.drawRoundedRect(0, 0, size, size, radius, radius)

    painter.setBrush(QBrush(QColor("#ffffff")))
    bar_width = max(2, int(size * 0.09))
    gap = max(2, int(size * 0.06))
    heights = [0.34, 0.62, 0.86, 0.5, 0.28]
    total = len(heights) * bar_width + (len(heights) - 1) * gap
    x = (size - total) / 2
    for factor in heights:
        bar_height = size * factor
        y = (size - bar_height) / 2
        painter.drawRoundedRect(int(x), int(y), bar_width, int(bar_height), bar_width / 2, bar_width / 2)
        x += bar_width + gap
    painter.end()
    return QIcon(pixmap)


class MainWindow(QMainWindow):
    """The persistent Voxylis application window."""

    closed = pyqtSignal()

    def __init__(self, orchestrator, parent=None):
        super().__init__(parent)
        self.orchestrator = orchestrator
        self.pages: Dict[str, QWidget] = {}

        self.setWindowTitle(f"{version.APP_NAME} {version.__version__}")
        self.setWindowIcon(app_icon())
        self.resize(1040, 700)
        self.setMinimumSize(860, 560)
        self.setStyleSheet(theme.stylesheet(self._theme()))

        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        for key, _label, page_class in PAGES:
            page = page_class(orchestrator)
            self.pages[key] = page
            self.stack.addWidget(page)
        layout.addWidget(self.stack, 1)

        self.setStatusBar(QStatusBar())
        self._status_stage = QLabel("Ready")
        self._status_providers = QLabel("")
        self._status_providers.setObjectName("Mono")
        self.statusBar().addWidget(self._status_stage, 1)
        self.statusBar().addPermanentWidget(self._status_providers)

        self._subscribe()
        self._select("home")
        QTimer.singleShot(0, self._refresh_status)

    # ── construction ─────────────────────────────────────────────────────

    def _theme(self) -> str:
        try:
            return self.orchestrator.get_config("theme", "dark") or "dark"
        except Exception:
            return "dark"

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(216)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.setSpacing(0)

        brand = QLabel(version.APP_NAME)
        brand.setObjectName("SidebarBrand")
        layout.addWidget(brand)

        version_label = QLabel(f"v{version.__version__} · {version.ENGINE_NAME}")
        version_label.setObjectName("SidebarVersion")
        layout.addWidget(version_label)

        self.nav = QListWidget()
        self.nav.setObjectName("NavList")
        self.nav.setFocusPolicy(Qt.NoFocus)
        for key, label, _ in PAGES:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, key)
            self.nav.addItem(item)
        self.nav.currentRowChanged.connect(self._on_nav)
        layout.addWidget(self.nav, 1)

        self.footer = QLabel("")
        self.footer.setObjectName("SidebarVersion")
        self.footer.setWordWrap(True)
        layout.addWidget(self.footer)
        return sidebar

    # ── navigation ───────────────────────────────────────────────────────

    def _on_nav(self, row: int) -> None:
        if 0 <= row < len(PAGES):
            self._select(PAGES[row][0])

    def _select(self, key: str) -> None:
        if key not in self.pages:
            return
        page = self.pages[key]
        self.stack.setCurrentWidget(page)
        for row, (page_key, _label, _cls) in enumerate(PAGES):
            if page_key == key:
                self.nav.blockSignals(True)
                self.nav.setCurrentRow(row)
                self.nav.blockSignals(False)
                break
        try:
            page.on_show()
        except Exception:
            pass

    def show_page(self, key: str) -> None:
        """Public entry point used by the tray and error dialogs."""
        mapped = SECTION_TO_PAGE.get(key, key)
        self.show()
        self.raise_()
        self.activateWindow()
        self._select(mapped)

    # ── events ───────────────────────────────────────────────────────────

    def _subscribe(self) -> None:
        event_manager.subscribe(Events.AUDIO_LEVEL_CHANGED, self._on_level)
        event_manager.subscribe(Events.PIPELINE_STAGE, self._on_stage)
        event_manager.subscribe(Events.LANGUAGE_DETECTED, self._on_language)
        event_manager.subscribe(Events.HISTORY_UPDATED, self._on_history)
        event_manager.subscribe(Events.STATS_UPDATED, self._on_stats)
        event_manager.subscribe(Events.ERROR_OCCURRED, self._on_error)
        event_manager.subscribe(Events.SETTINGS_CHANGED, self._on_settings_changed)

    def _on_level(self, level: float) -> None:
        page = self.pages.get("home")
        if isinstance(page, HomePage):
            page.set_level(float(level or 0))

    def _on_stage(self, stage: str) -> None:
        QTimer.singleShot(0, lambda: self._apply_stage(stage))

    def _apply_stage(self, stage: str) -> None:
        page = self.pages.get("home")
        if isinstance(page, HomePage):
            page.set_stage(stage)
        labels = {
            "idle": "Ready",
            "recording": "Listening…",
            "transcribing": "Transcribing…",
            "enhancing": "Enhancing…",
            "injecting": "Inserting…",
        }
        self._status_stage.setText(labels.get(stage, stage))

    def _on_language(self, language_name: str = "", language_code: str = "") -> None:
        self._status_providers.setText(f"{language_name or language_code}")

    def _on_history(self) -> None:
        page = self.pages.get("history")
        if isinstance(page, HistoryPage) and self.stack.currentWidget() is page:
            QTimer.singleShot(0, page.refresh)

    def _on_stats(self, today: Optional[dict] = None) -> None:
        page = self.pages.get("home")
        if isinstance(page, HomePage):
            QTimer.singleShot(0, page.refresh)

    def _on_error(self, error) -> None:
        QTimer.singleShot(0, lambda: self._apply_error(error))

    def _apply_error(self, error) -> None:
        page = self.pages.get("home")
        if isinstance(page, HomePage):
            page.show_error(error)
        self._status_stage.setText("Ready")

    def _on_settings_changed(self, key: str = "", value=None) -> None:
        if key == "theme":
            self.setStyleSheet(theme.stylesheet(str(value)))

    # ── status ───────────────────────────────────────────────────────────

    def _refresh_status(self) -> None:
        try:
            providers = self.orchestrator.provider_status()
        except Exception:
            return
        parts = []
        parts.append("groq" if providers.get("groq", {}).get("configured") else "no groq")
        parts.append("openai" if providers.get("openai", {}).get("configured") else "no openai")
        parts.append("keys:" + ("secure" if providers.get("secure_storage") else "unprotected"))
        self._status_providers.setText(" · ".join(parts))

        history_enabled = bool(self.orchestrator.get_config("history_enabled", True))
        self.footer.setText("history: on" if history_enabled else "history: off")

    def refresh(self) -> None:
        self._refresh_status()
        current = self.stack.currentWidget()
        if hasattr(current, "refresh"):
            try:
                current.refresh()
            except Exception:
                pass

    # ── window behaviour ─────────────────────────────────────────────────

    def closeEvent(self, event):  # noqa: N802 - Qt naming
        """Hide instead of quitting: the tray keeps the app alive."""
        event.ignore()
        self.hide()
        self.closed.emit()

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self.refresh()
