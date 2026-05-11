"""
Event management system for Voxylis
"""

from typing import Callable, Dict, List
from utils.logger import log_info, log_error, log_debug, log_warning


class EventManager:
    """Centralized event management system"""

    def __init__(self):
        """Initialize event manager"""
        self.listeners: Dict[str, List[Callable]] = {}

    def subscribe(self, event_name: str, callback: Callable) -> None:
        if event_name not in self.listeners:
            self.listeners[event_name] = []

        # Prevent duplicate subscriptions
        if callback not in self.listeners[event_name]:
            self.listeners[event_name].append(callback)
            log_debug(f"Subscribed to event: {event_name}")

    def unsubscribe(self, event_name: str, callback: Callable) -> None:
        """
        Unsubscribe from an event
        
        Args:
            event_name: Name of the event
            callback: Callback function to remove
        """
        if event_name in self.listeners:
            self.listeners[event_name].remove(callback)
            log_debug(f"Unsubscribed from event: {event_name}")

    def emit(self, event_name: str, *args, **kwargs) -> None:
        """
        Emit an event
        
        Args:
            event_name: Name of the event
            *args: Positional arguments to pass to callbacks
            **kwargs: Keyword arguments to pass to callbacks
        """
        if event_name in self.listeners:
            log_debug(f"Emitting event: {event_name}")
            for callback in self.listeners[event_name]:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    log_error(f"Error in event callback: {e}", exc_info=True)

    def clear_listeners(self, event_name: str = None) -> None:
        """
        Clear event listeners
        
        Args:
            event_name: Specific event to clear (None = clear all)
        """
        if event_name:
            if event_name in self.listeners:
                self.listeners[event_name] = []
                log_debug(f"Cleared listeners for event: {event_name}")
        else:
            self.listeners = {}
            log_debug("Cleared all event listeners")


# Global event manager instance
event_manager = EventManager()


# Event names
class Events:
    """Event name constants"""

    RECORDING_STARTED = "recording_started"
    RECORDING_STOPPED = "recording_stopped"
    RECORDING_FAILED = "recording_failed"
    RECORDING_CANCELLED = "recording_cancelled"
    AUDIO_LEVEL_CHANGED = "audio_level_changed"
    TRANSCRIPTION_STARTED = "transcription_started"
    TRANSCRIPTION_COMPLETED = "transcription_completed"
    TRANSCRIPTION_FAILED = "transcription_failed"
    ENHANCEMENT_STARTED = "enhancement_started"
    ENHANCEMENT_COMPLETED = "enhancement_completed"
    ENHANCEMENT_FAILED = "enhancement_failed"
    INJECTION_STARTED = "injection_started"
    INJECTION_COMPLETED = "injection_completed"
    INJECTION_FAILED = "injection_failed"
    HOTKEY_PRESSED = "hotkey_pressed"
    HOTKEY_RELEASED = "hotkey_released"
    SETTINGS_CHANGED = "settings_changed"
    ERROR_OCCURRED = "error_occurred"
    VOICE_COMMAND_EXECUTED = "voice_command_executed"
    HISTORY_UPDATED = "history_updated"
    MODE_HOTKEY_PRESSED = "mode_hotkey_pressed"
    MODE_HOTKEY_RELEASED = "mode_hotkey_released"
    LIVE_TEXT_UPDATED = "live_text_updated"
    STATS_UPDATED = "stats_updated"
    LANGUAGE_DETECTED = "language_detected"
