"""
Voxylis - Main application entry point
"""

import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QMessageBox, QAction, QActionGroup
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon

from core.app_orchestrator import AppOrchestrator
from core.event_manager import event_manager, Events
from ui.overlay import FloatingWidget
from ui.settings_window import SettingsWindow
from ui.history_window import HistoryWindow
from ui.custom_modes_window import CustomModesWindow
from utils.logger import log_info, log_error, log_debug
from utils.helpers import ensure_directories

BUILTIN_MODES = ["formal", "casual", "technical", "concise", "creative"]


class VoxylisApp:
    def __init__(self):
        ensure_directories()
        self.app = QApplication(sys.argv)
        self.orchestrator = AppOrchestrator()
        self.floating_widget = None
        self.settings_window = None
        self.history_window = None
        self.custom_modes_window = None
        self.tray_icon = None
        self._mode_actions = {}   # mode_name -> QAction

        self._setup_floating_widget()
        self._setup_tray_icon()
        self._setup_event_handlers()

        log_info("Voxylis application initialized")

    # ── floating widget ───────────────────────────────────────────────────────

    def _setup_floating_widget(self):
        try:
            # Minion disabled
            self.floating_widget = None
            log_info("Floating widget disabled")
        except Exception as e:
            log_error(f"Error creating floating widget: {e}", exc_info=True)

    # ── tray icon ─────────────────────────────────────────────────────────────

    def _setup_tray_icon(self):
        try:
            self.tray_icon = QSystemTrayIcon(self.app)
            menu = QMenu()

            # Status (disabled label)
            self._status_action = menu.addAction("Status: Ready")
            self._status_action.setEnabled(False)
            menu.addSeparator()

            # Enhancement mode submenu
            mode_menu = menu.addMenu("Enhancement Mode")
            mode_group = QActionGroup(mode_menu)
            mode_group.setExclusive(True)

            current_mode = self.orchestrator.config.get("enhancement_mode", "formal")
            all_modes = BUILTIN_MODES + list(
                self.orchestrator.config.get("custom_modes", {}).keys()
            )
            for mode in all_modes:
                act = QAction(mode.title(), mode_menu, checkable=True)
                act.setChecked(mode == current_mode)
                act.triggered.connect(lambda checked, m=mode: self._set_mode(m))
                mode_group.addAction(act)
                mode_menu.addAction(act)
                self._mode_actions[mode] = act

            menu.addSeparator()

            # History
            history_action = menu.addAction("Transcription History")
            history_action.triggered.connect(self.show_history)

            # Custom modes editor
            custom_action = menu.addAction("Custom Modes Editor")
            custom_action.triggered.connect(self.show_custom_modes)

            menu.addSeparator()

            # Settings
            settings_action = menu.addAction("Settings")
            settings_action.triggered.connect(self.show_settings)

            # Toggle widget
            toggle_action = menu.addAction("Toggle Widget")
            toggle_action.triggered.connect(self.toggle_widget)

            menu.addSeparator()

            about_action = menu.addAction("About")
            about_action.triggered.connect(self.show_about)

            exit_action = menu.addAction("Exit")
            exit_action.triggered.connect(self.exit_app)

            self.tray_icon.setContextMenu(menu)
            self.tray_icon.show()
            log_info("System tray icon created")

        except Exception as e:
            log_error(f"Error creating tray icon: {e}", exc_info=True)

    def _set_mode(self, mode: str):
        """Switch enhancement mode from tray menu."""
        self.orchestrator.update_config("enhancement_mode", mode)
        log_info(f"Enhancement mode switched to: {mode}")
        if mode in self._mode_actions:
            self._mode_actions[mode].setChecked(True)

    # ── event handlers ────────────────────────────────────────────────────────

    def _setup_event_handlers(self):
        try:
            event_manager.subscribe(Events.RECORDING_STARTED,       self._on_recording_started)
            event_manager.subscribe(Events.RECORDING_STOPPED,       self._on_recording_stopped)
            event_manager.subscribe(Events.TRANSCRIPTION_COMPLETED, self._on_transcription_completed)
            event_manager.subscribe(Events.ENHANCEMENT_COMPLETED,   self._on_enhancement_completed)
            event_manager.subscribe(Events.INJECTION_COMPLETED,     self._on_injection_completed)
            event_manager.subscribe(Events.AUDIO_LEVEL_CHANGED,     self._on_audio_level_changed)
            event_manager.subscribe(Events.ERROR_OCCURRED,          self._on_error_occurred)
            event_manager.subscribe(Events.VOICE_COMMAND_EXECUTED,  self._on_voice_command)
            event_manager.subscribe(Events.HISTORY_UPDATED,         self._on_history_updated)
            event_manager.subscribe(Events.LIVE_TEXT_UPDATED,       self._on_live_text)
            event_manager.subscribe(Events.STATS_UPDATED,           self._on_stats_updated)
            event_manager.subscribe(Events.LANGUAGE_DETECTED,       self._on_language_detected)
            log_info("Event handlers registered")
        except Exception as e:
            log_error(f"Error setting up event handlers: {e}", exc_info=True)

    # All UI updates go through QTimer.singleShot to stay on the Qt main thread

    def _on_recording_started(self):
        QTimer.singleShot(0, lambda: (
            self.floating_widget.set_recording(True) if self.floating_widget else None,
            self._status_action.setText("Status: Recording...") if self._status_action else None
        ))

    def _on_recording_stopped(self):
        # Hide the minion the moment the hotkey is released
        QTimer.singleShot(0, lambda: (
            self.floating_widget.set_recording(False) if self.floating_widget else None,
            self._status_action.setText("Status: Processing...") if self._status_action else None
        ))

    def _on_transcription_completed(self, text: str):
        QTimer.singleShot(0, lambda: (
            self.floating_widget.set_status("Transcribed") if self.floating_widget else None
        ))

    def _on_enhancement_completed(self, text: str):
        QTimer.singleShot(0, lambda: (
            self.floating_widget.set_status("Enhanced") if self.floating_widget else None
        ))

    def _on_injection_completed(self, text: str):
        QTimer.singleShot(0, self._ui_injection_done)

    def _ui_injection_done(self):
        if self.floating_widget:
            self.floating_widget.set_processing(False)
            self.floating_widget.set_status("Done")
        if self._status_action:
            self._status_action.setText("Status: Ready")

    def _on_audio_level_changed(self, level: float):
        if self.floating_widget:
            self.floating_widget.set_audio_level(level)

    def _on_voice_command(self, action: str = ""):
        QTimer.singleShot(0, lambda: (
            self.floating_widget.set_processing(False) if self.floating_widget else None,
            self.floating_widget.set_status(f"Cmd: {action}") if self.floating_widget else None,
            self._status_action.setText("Status: Ready") if self._status_action else None
        ))

    def _on_history_updated(self):
        if self.history_window and self.history_window.isVisible():
            QTimer.singleShot(0, self.history_window.refresh)

    def _on_live_text(self, text: str = ""):
        """Show live transcription text on the floating widget."""
        if self.floating_widget:
            QTimer.singleShot(0, lambda: self.floating_widget.set_live_text(text))

    def _on_stats_updated(self, today: dict = None):
        """Update tray status with today's word count."""
        if today and self._status_action:
            words = today.get("words", 0)
            QTimer.singleShot(0, lambda: self._status_action.setText(
                f"Today: {words} words"
            ))

    def _on_language_detected(self, language_name: str = "", language_code: str = ""):
        """Update floating widget with detected language badge."""
        if self.floating_widget:
            QTimer.singleShot(0, lambda: self.floating_widget.set_language(
                language_name, language_code
            ))

    def _on_error_occurred(self, error_code: str = ""):
        QTimer.singleShot(0, lambda: self._ui_error(error_code))

    def _ui_error(self, error_code: str):
        if error_code == "no_api_key":
            QMessageBox.warning(
                None, "API Key Missing",
                "No API key is set.\n\n"
                "Option 1 — Groq (FREE, recommended):\n"
                "  1. Go to https://console.groq.com/keys\n"
                "  2. Sign up free, create a key\n"
                "  3. Add to config/settings.json:\n"
                '     "groq_api_key": "gsk_your_key_here"\n\n'
                "Option 2 — OpenAI (paid):\n"
                '     "openai_api_key": "sk-your_key_here"',
            )
        if self.floating_widget:
            self.floating_widget.set_recording(False)
            self.floating_widget.set_processing(False)
        if self._status_action:
            self._status_action.setText("Status: Ready")

    # ── windows ───────────────────────────────────────────────────────────────

    def show_settings(self):
        try:
            if self.settings_window is None:
                self.settings_window = SettingsWindow(self.orchestrator.config)
                self.settings_window.settings_changed.connect(self._on_settings_changed)
                self.settings_window.closed.connect(lambda: setattr(self, "settings_window", None))
            self.settings_window.show()
            self.settings_window.raise_()
            self.settings_window.activateWindow()
        except Exception as e:
            log_error(f"Error showing settings: {e}", exc_info=True)

    def show_history(self):
        try:
            if self.history_window is None:
                self.history_window = HistoryWindow(self.orchestrator.history)
                self.history_window.inject_requested.connect(self._on_history_inject)
                self.history_window.closed.connect(lambda: setattr(self, "history_window", None))
            self.history_window.show()
            self.history_window.raise_()
            self.history_window.activateWindow()
        except Exception as e:
            log_error(f"Error showing history: {e}", exc_info=True)

    def show_custom_modes(self):
        try:
            if self.custom_modes_window is None:
                self.custom_modes_window = CustomModesWindow(
                    self.orchestrator.config.get("custom_modes", {})
                )
                self.custom_modes_window.modes_changed.connect(self._on_custom_modes_changed)
                self.custom_modes_window.closed.connect(
                    lambda: setattr(self, "custom_modes_window", None)
                )
            self.custom_modes_window.show()
            self.custom_modes_window.raise_()
            self.custom_modes_window.activateWindow()
        except Exception as e:
            log_error(f"Error showing custom modes: {e}", exc_info=True)

    def _on_history_inject(self, text: str):
        """Re-inject a historical transcription."""
        self.orchestrator.injector.inject_text(text)

    def _on_custom_modes_changed(self, custom_modes: dict):
        """Save updated custom modes and refresh tray menu."""
        self.orchestrator.update_config("custom_modes", custom_modes)
        log_info(f"Custom modes updated: {list(custom_modes.keys())}")
        # Rebuild tray menu to include new modes
        self._rebuild_tray_menu()

    def _rebuild_tray_menu(self):
        """Rebuild tray context menu (called after custom modes change)."""
        self._setup_tray_icon()

    def _on_settings_changed(self, key: str, value):
        log_info(f"Settings changed: {key} = {value}")
        self.orchestrator.update_config(key, value)
        if key == "theme" and self.floating_widget:
            self.floating_widget.set_theme(value)

    def toggle_widget(self):
        if self.floating_widget:
            self.floating_widget.toggle_visibility()

    def show_about(self):
        stats = self.orchestrator.stats.get_summary()
        QMessageBox.information(
            None, "About Voxylis",
            "Voxylis v2.0\n\n"
            "Hotkeys:\n"
            "  Win+Shift       → Record (default mode)\n"
            "  Win+Alt         → Record (casual mode)\n"
            "  Win+Ctrl        → Record (technical mode)\n\n"
            "Voice commands while recording:\n"
            "  'clear that'  'new line'  'undo'\n\n"
            "Right-click tray for History, Custom Modes, Settings.\n\n"
            f"Usage Stats:\n{stats}\n\n"
            "© 2024 Voxylis Team",
        )

    def run(self) -> int:
        try:
            if not self.orchestrator.start():
                log_error("Failed to start orchestrator")
                QMessageBox.critical(None, "Error", "Failed to start Voxylis.")
                return 1

            log_info("Voxylis started successfully")
            log_info(f"Hotkey: {self.orchestrator.config.get('hotkey')}")
            log_info("Ready to record. Press hotkey to start.")

            if self.tray_icon:
                self.tray_icon.showMessage(
                    "Voxylis", "Ready! Press Win+Shift to record.",
                    QSystemTrayIcon.Information, 4000,
                )
            return self.app.exec_()
        except Exception as e:
            log_error(f"Error running application: {e}", exc_info=True)
            return 1

    def exit_app(self):
        try:
            log_info("Exiting Voxylis")
            self.orchestrator.stop()
            self.app.quit()
        except Exception as e:
            log_error(f"Error exiting: {e}", exc_info=True)


def main():
    try:
        app = VoxylisApp()
        sys.exit(app.run())
    except Exception as e:
        log_error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
