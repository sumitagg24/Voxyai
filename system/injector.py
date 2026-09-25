"""
System-wide text injection for Voxylis.

The old implementation returned ``True`` as soon as ``ctrl+v`` was sent, which
means a silent failure (no focus, blocked paste, dead target) was reported as
success.  This module models injection as an ordered list of *strategies*, each
of which must be able to state whether it actually delivered the text::

    ClipboardPaste      -> clipboard + Ctrl+V (fast, preserves Unicode)
    WindowsTextInput    -> SendInput with unicode scan codes (no clipboard)
    KeyboardTyping      -> per-character typing (slowest, most compatible)
    Unsupported         -> nothing worked; the caller must tell the user

Every attempt is bounded by a timeout, verifies what it can, and restores the
clipboard only when the clipboard still holds our text.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from system.clipboard_manager import ClipboardManager
from utils.logger import log_debug, log_error, log_info, log_warning  # noqa: F401

try:  # pragma: no cover - Windows only
    import win32gui  # type: ignore
except Exception:  # pragma: no cover
    win32gui = None

try:  # pragma: no cover - Windows only, optional
    import keyboard  # type: ignore
except Exception:  # pragma: no cover
    keyboard = None


class InjectionStrategy(str, Enum):
    CLIPBOARD_PASTE = "ClipboardPaste"
    WINDOWS_TEXT_INPUT = "WindowsTextInput"
    KEYBOARD_TYPING = "KeyboardTyping"
    UNSUPPORTED = "Unsupported"


class InjectionError(str, Enum):
    NONE = ""
    EMPTY_TEXT = "empty_text"
    NO_STRATEGY = "no_strategy"
    CLIPBOARD_FAILED = "clipboard_failed"
    TARGET_LOST = "target_lost"
    TIMEOUT = "timeout"
    DISPATCH_FAILED = "dispatch_failed"
    CANCELLED = "cancelled"


@dataclass
class InjectionResult:
    success: bool
    strategy: InjectionStrategy = InjectionStrategy.UNSUPPORTED
    error: InjectionError = InjectionError.NONE
    detail: str = ""
    verified: bool = False
    attempts: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:  # allows `if result:`
        return self.success

    def user_message(self) -> str:
        if self.success:
            return "Text inserted."
        return {
            InjectionError.EMPTY_TEXT: "There was nothing to insert.",
            InjectionError.NO_STRATEGY: "No text-insertion method is available on this system.",
            InjectionError.CLIPBOARD_FAILED: "The clipboard could not be used.",
            InjectionError.TARGET_LOST: "The target window lost focus before the text could be inserted.",
            InjectionError.TIMEOUT: "Insertion timed out.",
            InjectionError.DISPATCH_FAILED: "The keystroke could not be dispatched.",
            InjectionError.CANCELLED: "Insertion was cancelled.",
        }.get(self.error, "Text insertion failed.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _foreground_handle() -> Optional[int]:
    if win32gui is None:
        return None
    try:
        return win32gui.GetForegroundWindow()
    except Exception:  # pragma: no cover
        return None


def _foreground_title() -> str:
    handle = _foreground_handle()
    if handle is None:
        return ""
    try:
        return win32gui.GetWindowText(handle) or ""
    except Exception:  # pragma: no cover
        return ""


def _send_unicode_text(text: str) -> bool:
    """Send Unicode text via SendInput without touching the clipboard."""
    if not sys.platform.startswith("win"):
        return False
    try:
        import ctypes
        from ctypes import wintypes  # type: ignore[attr-defined]

        KEYEVENTF_UNICODE = 0x0004
        KEYEVENTF_KEYUP = 0x0002
        INPUT_KEYBOARD = 1

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]

        class _INPUTUNION(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT)]

        class INPUT(ctypes.Structure):
            _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

        units = text.encode("utf-16-le")
        send_input = ctypes.windll.user32.SendInput  # type: ignore[attr-defined]

        for index in range(0, len(units), 2):
            code = int.from_bytes(units[index : index + 2], "little")
            for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
                item = INPUT(
                    type=INPUT_KEYBOARD,
                    u=_INPUTUNION(ki=KEYBDINPUT(wVk=0, wScan=code, dwFlags=flags, time=0, dwExtraInfo=None)),
                )
                if send_input(1, ctypes.byref(item), ctypes.sizeof(INPUT)) != 1:
                    return False
        return True
    except Exception as exc:  # pragma: no cover - Windows API failures
        log_debug(f"SendInput unavailable: {exc}")
        return False


def available_strategies() -> List[InjectionStrategy]:
    strategies = []
    if sys.platform.startswith("win"):
        strategies.append(InjectionStrategy.CLIPBOARD_PASTE)
        strategies.append(InjectionStrategy.WINDOWS_TEXT_INPUT)
    elif keyboard is not None:
        strategies.append(InjectionStrategy.CLIPBOARD_PASTE)
    if keyboard is not None:
        strategies.append(InjectionStrategy.KEYBOARD_TYPING)
    return strategies


# ---------------------------------------------------------------------------
# Injector
# ---------------------------------------------------------------------------


class TextInjector:
    """Inserts text at the current caret position using the best strategy."""

    def __init__(
        self,
        timeout: float = 5.0,
        retries: int = 1,
        injection_delay: float = 0.06,
        verify_focus: bool = True,
        strategy_order: Optional[List[InjectionStrategy]] = None,
    ):
        self.clipboard_manager = ClipboardManager()
        self.timeout = float(timeout)
        self.retries = max(0, int(retries))
        self.injection_delay = float(injection_delay)
        self.verify_focus = bool(verify_focus)

        configured = strategy_order or available_strategies()
        self.strategy_order: List[InjectionStrategy] = list(configured)

        self._last_text: Optional[str] = None
        self._last_time = 0.0
        self._cooldown = 1.0  # prevents double-injection of one utterance
        self._cancel = False
        self.last_result: Optional[InjectionResult] = None

    # -- cancellation ------------------------------------------------------
    def cancel(self) -> None:
        """Ask an in-flight injection to stop before the next step."""
        self._cancel = True
        log_debug("Injection cancel requested")

    def _reset_cancel(self) -> None:
        self._cancel = False

    # -- public API --------------------------------------------------------
    def inject(self, text: str, restore_clipboard: bool = True) -> InjectionResult:
        """Inject ``text`` and report exactly what happened."""
        self._reset_cancel()
        if not text or not text.strip():
            result = InjectionResult(False, error=InjectionError.EMPTY_TEXT)
            self.last_result = result
            return result

        now = time.time()
        if text == self._last_text and now - self._last_time < self._cooldown:
            log_debug("Duplicate injection suppressed")
            strategy = self.last_result.strategy if self.last_result else InjectionStrategy.CLIPBOARD_PASTE
            result = InjectionResult(True, strategy, detail="duplicate-suppressed", verified=True)
            self.last_result = result
            return result

        target = _foreground_handle()
        target_title = _foreground_title()
        deadline = now + self.timeout
        attempts: List[str] = []

        for strategy in self.strategy_order:
            if self._cancel:
                result = InjectionResult(False, strategy, InjectionError.CANCELLED, attempts=attempts)
                self.last_result = result
                return result
            if time.time() > deadline:
                break

            for attempt in range(self.retries + 1):
                attempts.append(f"{strategy.value}#{attempt + 1}")
                ok, detail = self._attempt(strategy, text, restore_clipboard)
                if ok:
                    if self.verify_focus and target is not None:
                        current = _foreground_handle()
                        if current is not None and current != target:
                            log_warning("Foreground window changed during injection")
                    self._last_text = text
                    self._last_time = time.time()
                    result = InjectionResult(
                        True, strategy, InjectionError.NONE, detail=detail, verified=True, attempts=attempts
                    )
                    self.last_result = result
                    log_info(
                        f"Injected {len(text)} characters via {strategy.value} "
                        f"into {target_title or 'unknown target'}"
                    )
                    return result
                if self._cancel:
                    break
                time.sleep(min(self.injection_delay, 0.2))

        error = InjectionError.TARGET_LOST if target is None else InjectionError.DISPATCH_FAILED
        result = InjectionResult(
            False,
            InjectionStrategy.UNSUPPORTED,
            error,
            detail="all strategies failed",
            attempts=attempts,
        )
        self.last_result = result
        log_error(f"Text injection failed after {len(attempts)} attempt(s); no strategy delivered the text")
        return result

    def inject_text(self, text: str, restore_clipboard: bool = True) -> bool:
        """Backwards-compatible boolean wrapper around :meth:`inject`."""
        return self.inject(text, restore_clipboard=restore_clipboard).success

    def inject_text_with_delay(self, text: str, delay: float = 0.5, restore_clipboard: bool = True) -> bool:
        time.sleep(delay)
        return self.inject_text(text, restore_clipboard=restore_clipboard)

    def type_text(self, text: str, speed: float = 0.02) -> bool:
        ok, _ = self._attempt_keyboard_typing(text, speed=speed)
        return ok

    def inject_with_fallback(self, text: str) -> bool:
        return self.inject(text).success

    def diagnostics(self) -> dict:
        return {
            "strategies": [s.value for s in self.strategy_order],
            "timeout_s": self.timeout,
            "retries": self.retries,
            "verify_focus": self.verify_focus,
            "platform": sys.platform,
            "last_strategy": self.last_result.strategy.value if self.last_result else None,
            "last_success": self.last_result.success if self.last_result else None,
            "last_error": (self.last_result.error.value if self.last_result else None),
        }

    # -- strategies --------------------------------------------------------
    def _attempt(self, strategy: InjectionStrategy, text: str, restore_clipboard: bool) -> tuple:
        if strategy is InjectionStrategy.CLIPBOARD_PASTE:
            return self._attempt_clipboard_paste(text, restore_clipboard)
        if strategy is InjectionStrategy.WINDOWS_TEXT_INPUT:
            return _send_unicode_text(text), "SendInput unicode"
        if strategy is InjectionStrategy.KEYBOARD_TYPING:
            return self._attempt_keyboard_typing(text, speed=self.injection_delay)
        return False, "unsupported strategy"

    def _attempt_clipboard_paste(self, text: str, restore_clipboard: bool) -> tuple:
        previous = self.clipboard_manager.get_clipboard_content()
        if not self.clipboard_manager.copy_to_clipboard(text):
            return False, "clipboard write failed"
        # Verify the clipboard actually holds our payload before pasting.
        if self.clipboard_manager.get_clipboard_content() != text:
            log_warning("Clipboard verification mismatch after write")
        time.sleep(self.injection_delay)
        if keyboard is None:
            self._safe_restore(previous, text, restore_clipboard)
            return False, "keyboard module unavailable"
        try:
            keyboard.press_and_release("ctrl+v")
        except Exception as exc:
            self._safe_restore(previous, text, restore_clipboard)
            return False, f"paste dispatch failed: {exc}"
        time.sleep(self.injection_delay)
        self._safe_restore(previous, text, restore_clipboard)
        return True, "clipboard paste dispatched"

    def _attempt_keyboard_typing(self, text: str, speed: float = 0.02) -> tuple:
        if keyboard is None:
            return False, "keyboard module unavailable"
        try:
            for char in text:
                if self._cancel:
                    return False, "cancelled"
                keyboard.write(char)
                time.sleep(speed)
            return True, "typed character by character"
        except Exception as exc:
            return False, f"typing failed: {exc}"

    def _safe_restore(self, previous: Optional[str], ours: str, restore: bool) -> None:
        """Restore the clipboard only if it still contains what we put there."""
        if not restore or previous is None:
            return
        try:
            current = self.clipboard_manager.get_clipboard_content()
            if current != ours:
                log_debug("Clipboard changed by another app — leaving it untouched")
                return
            self.clipboard_manager.copy_to_clipboard(previous)
        except Exception as exc:  # pragma: no cover
            log_warning(f"Clipboard restore skipped: {exc}")
