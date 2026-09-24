"""
Voxylis desktop application entry point.

Responsibilities:
  * single-instance enforcement (a second launch focuses the running window);
  * application lifecycle (tray + persistent main window + recording overlay);
  * wiring orchestrator events to the UI on the Qt main thread;
  * friendly error reporting and crash logging;
  * clean shutdown that stops the hotkey hook and the recorder.

The recording overlay is a transient surface; the main window is the product.
"""

from __future__ import annotations

import os
import sys
import traceback
from typing import Optional

from PyQt5.QtCore import QTimer
from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from PyQt5.QtWidgets import (
    QAction,
    QActionGroup,
    QApplication,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
)

from config import version
from config.constants import HOTKEY_DEFAULT
from config.constants import ENHANCEMENT_MODES, MAX_RECORDING_DURATION
from core.app_orchestrator import AppOrchestrator
from core.event_manager import Events, event_manager
from ui import theme
from ui.error_dialog import build_diagnostics_text, show_error
from ui.main_window import MainWindow, app_icon
from ui.overlay import FloatingWidget
from ui.shortcut_recorder import format_hotkey
from utils import observability, paths
from utils.helpers import ensure_directories
from utils.logger import configure_root_logger, log_error, log_info

BUILTIN_MODES = list(ENHANCEMENT_MODES.keys())
SERVER_NAME = "voxylis-single-instance"


class SingleInstance:
    """Named local socket guard so only one Voxylis runs per user session."""

    def __init__(self, name: str = SERVER_NAME):
        self.name = name
        self.server: Optional[QLocalServer] = None
        self.is_primary = False

    def acquire(self, on_activate=None) -> bool:
        socket = QLocalSocket()
        socket.connectToServer(self.name)
        if socket.waitForConnected(300):
            socket.write(b"activate")
            socket.flush()
            socket.waitForBytesWritten(300)
            socket.disconnectFromServer()
            return False

        # Stale server file from a previous crash.
        QLocalServer.removeServer(self.name)
        self.server = QLocalServer()
        self.server.removeServer(self.name)
        self.is_primary = self.server.listen(self.name)
        if self.is_primary and on_activate is not None:
            self.server.newConnection.connect(on_activate)
        return self.is_primary


class VoxylisApp:
    """Owns the tray icon, main window and recording overlay."""

    def __init__(self, argv=None):
        ensure_directories()
        configure_root_logger()

        # Reuse the QApplication created by main() (Qt allows exactly one).
        self.app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
        self.app.setApplicationName(version.APP_NAME)
        self.app.setApplicationVersion(version.__version__)
        self.app.setOrganizationName(version.PUBLISHER)
        self.app.setQuitOnLastWindowClosed(False)
        self.app.setStyleSheet(theme.stylesheet("dark"))
        self.app.setWindowIcon(app_icon())

        self.orchestrator = AppOrchestrator()
        self.overlay: Optional[FloatingWidget] = None
        self.main_window: Optional[MainWindow] = None
        self.tray_icon: Optional[QSystemTrayIcon] = None
        self._tray_menu: Optional[QMenu] = None
        self._mode_actions = {}
        self._status_action: Optional[QAction] = None
        self._record_action: Optional[QAction] = None
        self._pause_action: Optional[QAction] = None
        self._mic_action: Optional[QAction] = None
        self._provider_action: Optional[QAction] = None
        self._quitting = False

        self._setup_overlay()
        self._setup_main_window()
        self._setup_tray_icon()
        self._setup_event_handlers()

        log_info(f"{version.APP_NAME} {version.__version__} initialised")

    # ── surfaces ─────────────────────────────────────────────────────────

    def _setup_overlay(self) -> None:
        try:
            self.overlay = FloatingWidget(max_recording_seconds=MAX_RECORDING_DURATION)
            self.overlay.cancel_requested.connect(self._cancel_recording)
            if not self.orchestrator.get_config("show_floating_widget", True):
                self.overlay.hide()
            log_info("Recording overlay created")
        except Exception as exc:
            log_error(f"Error creating recording overlay: {exc}", exc_info=True)
            self.overlay = None

    def _setup_main_window(self) -> None:
        try:
            self.main_window = MainWindow(self.orchestrator)
            self.main_window.closed.connect(self._on_main_window_closed)
        except Exception as exc:
            log_error(f"Error creating main window: {exc}", exc_info=True)
            self.main_window = None

    # ── tray ─────────────────────────────────────────────────────────────

    def _setup_tray_icon(self) -> None:
        """Build or rebuild the tray menu, disposing the previous one."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            log_error("No system tray available")
            return
        try:
            if self.tray_icon is None:
                self.tray_icon = QSystemTrayIcon(app_icon(), self.app)
                self.tray_icon.setToolTip(f"{version.APP_NAME} {version.__version__}")
                self.tray_icon.activated.connect(self._on_tray_activated)

            old_menu = self._tray_menu
            menu = QMenu()
            self._mode_actions = {}

            self._status_action = menu.addAction("Ready")
            self._status_action.setEnabled(False)
            menu.addSeparator()

            self._record_action = menu.addAction("Start recording")
            self._record_action.triggered.connect(self._toggle_recording)
            cancel_action = menu.addAction("Cancel")
            cancel_action.triggered.connect(self._cancel_recording)
            menu.addSeparator()

            mode_menu = menu.addMenu("Enhancement mode")
            mode_group = QActionGroup(mode_menu)
            mode_group.setExclusive(True)
            current_mode = self.orchestrator.get_config("enhancement_mode", "formal")
            all_modes = BUILTIN_MODES + list((self.orchestrator.get_config("custom_modes") or {}).keys())
            for mode in all_modes:
                action = QAction(mode.title(), mode_menu, checkable=True)
                action.setChecked(mode == current_mode)
                action.triggered.connect(lambda _checked, m=mode: self._set_mode(m))
                mode_group.addAction(action)
                mode_menu.addAction(action)
                self._mode_actions[mode] = action

            menu.addSeparator()
            open_action = menu.addAction("Open Voxylis")
            open_action.triggered.connect(lambda: self.show_page("home"))
            history_action = menu.addAction("History")
            history_action.triggered.connect(lambda: self.show_page("history"))
            settings_action = menu.addAction("Settings")
            settings_action.triggered.connect(lambda: self.show_page("ai"))
            shortcuts_action = menu.addAction("Shortcuts")
            shortcuts_action.triggered.connect(lambda: self.show_page("shortcuts"))
            diagnostics_action = menu.addAction("Diagnostics")
            diagnostics_action.triggered.connect(lambda: self.show_page("diagnostics"))
            copy_diag_action = menu.addAction("Copy diagnostics")
            copy_diag_action.triggered.connect(self._copy_diagnostics)
            menu.addSeparator()

            self._pause_action = menu.addAction("Pause global shortcuts")
            self._pause_action.setCheckable(True)
            self._pause_action.setChecked(bool(self.orchestrator.get_config("global_shortcuts_disabled", False)))
            self._pause_action.triggered.connect(self._toggle_pause)

            self._mic_action = menu.addAction("Microphone: checking…")
            self._mic_action.setEnabled(False)
            providers = self.orchestrator.provider_status()
            groq_ok = providers["groq"]["configured"]
            openai_ok = providers["openai"]["configured"]
            self._provider_action = menu.addAction(
                f"Provider: {'Groq' if groq_ok else ('OpenAI' if openai_ok else 'not configured')}"
            )
            self._provider_action.setEnabled(False)
            menu.addSeparator()

            about_action = menu.addAction("About")
            about_action.triggered.connect(lambda: self.show_page("about"))
            quit_action = menu.addAction("Quit")
            quit_action.triggered.connect(self.exit_app)

            self._tray_menu = menu
            self.tray_icon.setContextMenu(menu)
            self.tray_icon.show()

            # Dispose of the replaced menu so repeated rebuilds cannot leak.
            if old_menu is not None:
                old_menu.deleteLater()

            log_info("System tray icon ready")
        except Exception as exc:
            log_error(f"Error creating tray icon: {exc}", exc_info=True)

    def _rebuild_tray_menu(self) -> None:
        self._setup_tray_icon()

    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_page("home")

    def _set_mode(self, mode: str) -> None:
        self.orchestrator.update_config("enhancement_mode", mode)
        if mode in self._mode_actions:
            self._mode_actions[mode].setChecked(True)
        if self.overlay:
            self.overlay.set_mode(mode)

    def _toggle_pause(self) -> None:
        paused = bool(self._pause_action and self._pause_action.isChecked())
        self.orchestrator.update_config("global_shortcuts_disabled", paused)
        log_info(f"Global shortcuts {'paused' if paused else 'resumed'}")
        self._refresh_status_text()

    # ── window helpers ───────────────────────────────────────────────────

    def show_page(self, key: str = "home") -> None:
        if self.main_window is None:
            return
        if key == "settings":
            key = "ai"
        self.main_window.show_page(key)

    def _on_main_window_closed(self) -> None:
        log_info("Main window hidden (still running in the tray)")

    def _copy_diagnostics(self) -> None:
        QApplication.clipboard().setText(build_diagnostics_text(self.orchestrator))

    # ── event wiring ─────────────────────────────────────────────────────

    def _setup_event_handlers(self) -> None:
        mapping = {
            Events.AUDIO_LEVEL_CHANGED: self._on_audio_level,
            Events.PIPELINE_STAGE: self._on_stage,
            Events.LANGUAGE_DETECTED: self._on_language,
            Events.LIVE_TEXT_UPDATED: self._on_live_text,
            Events.INJECTION_COMPLETED: self._on_injection_completed,
            Events.INJECTION_FAILED: self._on_injection_failed,
            Events.ERROR_OCCURRED: self._on_error_occurred,
            Events.STATS_UPDATED: self._on_stats_updated,
            Events.RECORDING_CANCELLED: self._on_recording_cancelled,
        }
        for event, handler in mapping.items():
            event_manager.subscribe(event, handler)
        log_info("Event handlers registered")

    # Overlay updates arrive from worker threads; QTimer.singleShot moves them
    # onto the Qt main thread.

    def _on_audio_level(self, level: float = 0.0) -> None:
        if self.overlay:
            QTimer.singleShot(0, lambda: self.overlay.set_audio_level(level))

    def _on_stage(self, stage: str = "idle") -> None:
        def apply() -> None:
            if self.overlay:
                self.overlay.set_stage(stage)
            self._refresh_status_text(stage)

        QTimer.singleShot(0, apply)

    def _refresh_status_text(self, stage: Optional[str] = None) -> None:
        if self._status_action is None:
            return
        if stage is None:
            stage = self.orchestrator.get_status().get("stage", "idle")
        labels = {
            "idle": "Ready",
            "recording": "Recording…",
            "transcribing": "Transcribing…",
            "enhancing": "Enhancing…",
            "injecting": "Inserting…",
        }
        text = labels.get(stage, "Ready")
        hotkey = format_hotkey(self.orchestrator.get_config("hotkey", HOTKEY_DEFAULT))
        paused = bool(self.orchestrator.get_config("global_shortcuts_disabled", False))
        suffix = " · shortcuts paused" if paused else f" · {hotkey}"
        self._status_action.setText(f"Status: {text}{suffix}")
        if self._record_action is not None:
            self._record_action.setText("Stop recording" if stage == "recording" else "Start recording")
        mode = self.orchestrator.get_config("enhancement_mode", "formal")
        if mode in self._mode_actions:
            self._mode_actions[mode].setChecked(True)
        if self._mic_action is not None and self.overlay is not None:
            self._mic_action.setText("Microphone: input detected" if self.overlay.mic_healthy else "Microphone: idle")

    def _on_language(self, language_name: str = "", language_code: str = "") -> None:
        if self.overlay:
            QTimer.singleShot(0, lambda: self.overlay.set_language(language_name, language_code))

    def _on_live_text(self, text: str = "") -> None:
        if self.overlay:
            QTimer.singleShot(0, lambda: self.overlay.set_live_text(text))

    def _on_injection_completed(self, text: str = "") -> None:
        def apply() -> None:
            if self.overlay:
                self.overlay.show_success("Text inserted")
            self._refresh_status_text("idle")

        QTimer.singleShot(0, apply)

    def _on_injection_failed(self) -> None:
        def apply() -> None:
            if self.overlay:
                self.overlay.show_error("Insertion failed — see the error dialog")
            self._refresh_status_text("idle")

        QTimer.singleShot(0, apply)

    def _on_recording_cancelled(self) -> None:
        def apply() -> None:
            if self.overlay:
                self.overlay.show_cancelled()
            self._refresh_status_text("idle")

        QTimer.singleShot(0, apply)

    def _on_stats_updated(self, today: Optional[dict] = None) -> None:
        words = (today or {}).get("words", 0)
        log_info(f"Stats updated for today ({words} words)")

    def _on_error_occurred(self, error) -> None:
        def apply() -> None:
            if self.overlay:
                message = getattr(error, "summary", None) or str(error)
                self.overlay.show_error(message)
            if self.main_window is not None and self.main_window.isVisible():
                section = show_error(
                    error,
                    parent=self.main_window,
                    diagnostics=lambda: build_diagnostics_text(self.orchestrator),
                )
                if section and section != "retry":
                    self.show_page(section)
            self._refresh_status_text("idle")

        # Errors are shown only when the main window is open; otherwise the
        # overlay conveys the failure without stealing focus mid-dictation.
        QTimer.singleShot(0, apply)

    # ── actions ──────────────────────────────────────────────────────────

    def _toggle_recording(self) -> None:
        self.orchestrator.toggle_recording()

    def _cancel_recording(self) -> None:
        self.orchestrator.cancel_recording()

    # ── lifecycle ────────────────────────────────────────────────────────

    def run(self) -> int:
        try:
            if not self.orchestrator.start():
                log_error("Failed to start the orchestrator")
                show_error(
                    "pipeline_error",
                    parent=self.main_window,
                    diagnostics=lambda: build_diagnostics_text(self.orchestrator),
                )
                return 1

            log_info(f"Hotkey: {self.orchestrator.get_config('hotkey', HOTKEY_DEFAULT)}")
            log_info("Ready. Press the shortcut or open the window from the tray.")

            if self.tray_icon:
                hotkey = format_hotkey(self.orchestrator.get_config("hotkey", HOTKEY_DEFAULT))
                self.tray_icon.showMessage(
                    version.APP_NAME,
                    f"Ready — press {hotkey} to dictate.",
                    QSystemTrayIcon.Information,
                    4000,
                )

            self._maybe_run_onboarding()
            if self.main_window is not None:
                self.main_window.refresh()
            self._refresh_status_text()
            self._check_for_updates()

            return self.app.exec_()
        except Exception as exc:
            log_error(f"Error running application: {exc}", exc_info=True)
            self._write_crash_report(exc)
            return 1

    def _check_for_updates(self) -> None:
        """Non-blocking update check; the user is informed, never interrupted."""
        if self.orchestrator.get_config("check_for_updates") is False:
            return

        def done(info) -> None:
            if not info.available or self.tray_icon is None:
                return
            log_info(f"Update available: {info.latest} (running {info.current})")
            self.tray_icon.showMessage(
                f"{version.APP_NAME} {info.latest} is available",
                "Open Voxylis → About to download and install it.",
                QSystemTrayIcon.Information,
                6000,
            )

        try:
            from core import updater

            updater.check_async(done)
        except Exception as exc:  # pragma: no cover - optional feature
            log_error(f"Update check could not start: {exc}")

    def _maybe_run_onboarding(self) -> None:
        """Run the first-run wizard once, applying its answers live."""
        from ui.onboarding_window import OnboardingWindow, has_completed_onboarding

        if has_completed_onboarding():
            return
        log_info("First run detected — opening the setup wizard")
        wizard = OnboardingWindow(
            self.orchestrator.get_config(),
            orchestrator=self.orchestrator,
            parent=self.main_window,
        )
        wizard.settings_ready.connect(self._apply_onboarding)
        wizard.credential_ready.connect(self._apply_onboarding_credential)
        wizard.exec_()
        if self.main_window is not None:
            self.main_window.refresh()

    def _apply_onboarding(self, payload: dict) -> None:
        mapping = {
            "hotkey": "hotkey",
            "toggle_mode": "toggle_mode",
            "audio_device": "audio_device",
            "language": "language",
            "mode": "enhancement_mode",
            "enable_enhancement": "enable_ai_enhancement",
        }
        for source, target in mapping.items():
            if source in payload and payload[source] is not None:
                self.orchestrator.update_config(target, payload[source])
        log_info("Onboarding settings applied")

    def _apply_onboarding_credential(self, name: str, value: str) -> None:
        if self.orchestrator.update_config(name, value):
            log_info(f"Onboarding stored credential '{name}' in the secure vault")
            if self._provider_action is not None:
                providers = self.orchestrator.provider_status()
                self._provider_action.setText(
                    "Provider: "
                    + (
                        "Groq"
                        if providers["groq"]["configured"]
                        else ("OpenAI" if providers["openai"]["configured"] else "not configured")
                    )
                )

    def _write_crash_report(self, exc: BaseException) -> None:
        """Persist a redacted crash report; never includes transcripts or keys.

        The local file is the primary artefact — it works offline and the user
        can read it. Remote reporting (opt-in, Settings → Privacy) is a second,
        clearly separate channel handled by ``utils.observability``.
        """
        try:
            report = paths.crash_dir() / f"crash-{os.getpid()}.log"
            report.write_text(
                f"{version.APP_NAME} {version.__version__}\n"
                f"{type(exc).__name__}: {exc}\n\n"
                + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
                encoding="utf-8",
            )
            log_error(f"Crash report written to {report}")
        except Exception:
            pass
        observability.capture_startup_failure(exc)

    def exit_app(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        try:
            log_info("Exiting Voxylis")
            self.orchestrator.stop()
            if self.tray_icon:
                self.tray_icon.hide()
            self.app.quit()
        except Exception as exc:
            log_error(f"Error exiting: {exc}", exc_info=True)
            self.app.quit()


def main() -> int:
    QApplication.setAttribute(0x00000004)  # Qt.AA_EnableHighDpiScaling
    QApplication.setAttribute(0x00000001)  # Qt.AA_UseHighDpiPixmaps
    application = QApplication(sys.argv)

    instance = SingleInstance()
    if not instance.acquire(on_activate=_activate_existing):
        print("Voxylis is already running — focusing the existing window.")
        return 0

    app = None
    try:
        app = VoxylisApp(sys.argv)
        return app.run()
    except Exception as exc:
        log_error(f"Fatal error: {exc}", exc_info=True)
        # A startup failure happens before any window exists, so this is the
        # only place the user can be told and the only place it can be reported.
        observability.capture_startup_failure(exc)
        QMessageBox.critical(None, "Voxylis", f"Voxylis could not start.\n\n{exc}")
        return 1
    finally:
        if app is not None:
            app.orchestrator.stop()
        application.quit()


def _activate_existing() -> None:
    """A second launch reached us: surface the running window."""
    from PyQt5.QtCore import QCoreApplication

    for widget in QCoreApplication.topLevelWidgets():
        if isinstance(widget, MainWindow):
            widget.show_page("home")
            return


if __name__ == "__main__":
    sys.exit(main())
