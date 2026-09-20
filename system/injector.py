"""
System-wide text injection engine for Voxylis
"""

import time
import keyboard
from system.clipboard_manager import ClipboardManager
from utils.logger import log_info, log_error, log_debug, log_warning


class TextInjector:
    """Handles system-wide text injection at cursor position"""

    def __init__(self):
        self.clipboard_manager = ClipboardManager()
        self.injection_delay = 0.1
        self._last_injected_text = None
        self._last_inject_time = 0.0
        self._inject_cooldown = 1.0  # 1 second cooldown to prevent duplicate injection

    def inject_text(self, text: str, restore_clipboard: bool = True) -> bool:
        try:
            import time as _time

            now = _time.time()

            # Guard: skip if same text injected within cooldown window
            if (
                text == self._last_injected_text
                and now - self._last_inject_time < self._inject_cooldown
            ):
                log_warning(f"Duplicate injection blocked: {repr(text[:40])}")
                return True

            self._last_injected_text = text
            self._last_inject_time = now

            log_info(f"Injecting text: {len(text)} characters")

            if not self.clipboard_manager.copy_to_clipboard(text):
                log_error("Failed to copy text to clipboard")
                return False

            time.sleep(self.injection_delay)
            keyboard.press_and_release("ctrl+v")
            log_debug("Paste command sent")
            time.sleep(self.injection_delay)

            if restore_clipboard:
                self.clipboard_manager.restore_clipboard()

            log_info("Text injection successful")
            return True

        except Exception as e:
            log_error(f"Text injection error: {e}", exc_info=True)
            return False

    def inject_text_with_delay(
        self, text: str, delay: float = 0.5, restore_clipboard: bool = True
    ) -> bool:
        """
        Inject text with initial delay

        Args:
            text: Text to inject
            delay: Delay before injection in seconds
            restore_clipboard: Whether to restore original clipboard content

        Returns:
            True if successful
        """
        try:
            log_info(f"Scheduling text injection with {delay}s delay")
            time.sleep(delay)
            return self.inject_text(text, restore_clipboard)

        except Exception as e:
            log_error(f"Delayed injection error: {e}", exc_info=True)
            return False

    def type_text(self, text: str, speed: float = 0.05) -> bool:
        """
        Type text character by character (slower but more compatible)

        Args:
            text: Text to type
            speed: Delay between characters in seconds

        Returns:
            True if successful
        """
        try:
            log_info(f"Typing text: {len(text)} characters")

            for char in text:
                keyboard.write(char)
                time.sleep(speed)

            log_info("Text typing successful")
            return True

        except Exception as e:
            log_error(f"Text typing error: {e}", exc_info=True)
            return False

    def inject_with_fallback(self, text: str) -> bool:
        """
        Inject text with fallback to character-by-character typing

        Args:
            text: Text to inject

        Returns:
            True if successful
        """
        try:
            # Try clipboard + paste first
            if self.inject_text(text):
                return True

            log_warning("Clipboard injection failed, falling back to typing")

            # Fallback to typing
            return self.type_text(text)

        except Exception as e:
            log_error(f"Injection with fallback error: {e}", exc_info=True)
            return False
