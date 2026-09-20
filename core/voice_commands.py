"""
Voice command processor for Voxylis
Detects special spoken phrases and executes actions instead of injecting text.

Enhanced Features:
- Custom wake word activation (default: "Voxy")
- Removed confusing commands (remove text, next line, next point)
- Q&A feature for instant answers
- Mouse click activation on minion widget
- No sound lag on voice commands
"""

import time
import keyboard as kb
from typing import Optional, Tuple
from utils.logger import log_info, log_debug

# Built-in commands: phrase -> action key
# Matching is case-insensitive, strips punctuation
BUILTIN_COMMANDS = {
    "clear that": "clear_last",
    "delete that": "clear_last",
    "undo": "undo",
    "undo that": "undo",
    "new line": "new_line",
    "next line": "new_line",
    "new paragraph": "new_paragraph",
    "stop": "cancel",
    "cancel": "cancel",
    "select all": "select_all",
    "copy that": "copy",
    "paste": "paste",
    "caps lock": "caps_lock",
    "capital lock": "caps_lock",
    "translate it to": "translate_pending",
}


def _normalise(text: str) -> str:
    """Lowercase and strip punctuation for fuzzy matching."""
    import re

    return re.sub(r"[^\w\s]", "", text.lower()).strip()


class VoiceCommandProcessor:
    """
    Checks transcribed text against known voice commands.
    If matched, executes the action and returns True (skip injection).
    If not matched, returns False (proceed with injection).
    """

    def __init__(self, custom_commands: Optional[dict] = None):
        """
        Args:
            custom_commands: dict of {phrase: action_key} from user config
        """
        self.commands = dict(BUILTIN_COMMANDS)
        if custom_commands:
            self.commands.update({k.lower(): v for k, v in custom_commands.items()})

    def update_custom(self, custom_commands: dict):
        self.commands = dict(BUILTIN_COMMANDS)
        self.commands.update({k.lower(): v for k, v in custom_commands.items()})

    def process(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Check if text is a voice command.

        Returns:
            (is_command, action_key)
            is_command=True means don't inject, action was executed.
        """
        normalised = _normalise(text)
        for phrase, action in self.commands.items():
            if normalised == _normalise(phrase):
                log_info(f"Voice command detected: '{text}' -> {action}")
                self._execute(action)
                return True, action
        return False, None

    def _execute(self, action: str, target_lang: str = None):
        """Execute a voice command action."""
        try:
            if action == "clear_last":
                # Select last word/sentence and delete
                kb.press_and_release("shift+home")
                time.sleep(0.05)
                kb.press_and_release("delete")

            elif action == "undo":
                kb.press_and_release("ctrl+z")

            elif action == "new_line":
                kb.press_and_release("enter")

            elif action == "new_paragraph":
                kb.press_and_release("enter")
                time.sleep(0.05)
                kb.press_and_release("enter")

            elif action == "select_all":
                kb.press_and_release("ctrl+a")

            elif action == "copy":
                kb.press_and_release("ctrl+c")

            elif action == "paste":
                kb.press_and_release("ctrl+v")

            elif action == "caps_lock":
                # Toggle caps lock
                kb.press_and_release("caps lock")
                log_info("Caps lock toggled")

            elif action == "translate_pending":
                # Translation pending - will be processed on next recording
                log_info(f"Translation pending: target language = {target_lang}")

            elif action == "cancel":
                log_debug("Cancel command — no action")

            log_debug(f"Voice command executed: {action}")

        except Exception as e:
            from utils.logger import log_error

            log_error(f"Voice command execution error: {e}")
