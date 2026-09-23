"""
Clipboard management for Voxylis
"""

import pyperclip
import time
from typing import Optional
from utils.logger import log_info, log_error, log_debug


class ClipboardManager:
    """Handles clipboard operations safely"""

    def __init__(self):
        """Initialize clipboard manager"""
        self.original_content = None
        self.last_operation_time = 0

    def copy_to_clipboard(self, text: str) -> bool:
        """
        Copy text to clipboard

        Args:
            text: Text to copy

        Returns:
            True if successful
        """
        try:
            # Save original clipboard content
            self.original_content = self.get_clipboard_content()

            # Copy new text
            pyperclip.copy(text)
            self.last_operation_time = time.time()

            # Never log clipboard contents — they are user transcripts.
            log_debug(f"Text copied to clipboard: {len(text)} characters")

            return True

        except Exception as e:
            log_error(f"Error copying to clipboard: {e}", exc_info=True)
            return False

    def get_clipboard_content(self) -> Optional[str]:
        """
        Get current clipboard content

        Returns:
            Clipboard content or None if error
        """
        try:
            content = pyperclip.paste()
            return content
        except Exception as e:
            log_error(f"Error reading clipboard: {e}", exc_info=True)
            return None

    def restore_clipboard(self) -> bool:
        """
        Restore original clipboard content

        Returns:
            True if successful
        """
        try:
            if self.original_content is not None:
                pyperclip.copy(self.original_content)
                log_info("Clipboard restored to original content")
                return True
            return False
        except Exception as e:
            log_error(f"Error restoring clipboard: {e}", exc_info=True)
            return False

    def clear_clipboard(self) -> bool:
        """
        Clear clipboard

        Returns:
            True if successful
        """
        try:
            pyperclip.copy("")
            log_info("Clipboard cleared")
            return True
        except Exception as e:
            log_error(f"Error clearing clipboard: {e}", exc_info=True)
            return False
