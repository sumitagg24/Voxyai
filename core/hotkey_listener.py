"""
Global hotkey listener for Voxylis.

Supports:
  * hold mode (default) — hold to record, release to stop;
  * toggle mode — press once to start, press again to stop;
  * per-mode hotkeys (e.g. Win+Alt = casual);
  * modifier-only combos (``win+shift``), which is why we cannot use a simple
    string-equality hotkey library.

Production hardening added here:
  * every shortcut string is parsed and validated *before* it is trusted, so a
    malformed config cannot crash the listener;
  * reserved Windows shortcuts and duplicate assignments are detected and
    reported instead of silently swallowed;
  * the listener can be disabled without tearing down the app;
  * :meth:`HotkeyListener.recover` restarts a dead hook once, and
    ``on_listener_lost`` lets the app tell the user if that fails;
  * events are only fired from a single canonical key (``ctrl`` not both
    ``ctrl_l``/``ctrl_r``), so a combo cannot fire twice for one press.
"""

from __future__ import annotations

import threading
from typing import Callable, Dict, List, Optional, Set, Tuple

try:
    from pynput import keyboard
except Exception as _pynput_import_error:  # headless CI without DISPLAY
    keyboard = None  # type: ignore[assignment]
    _pynput_import_error = _pynput_import_error  # keep for diagnostics

from core.event_manager import Events, event_manager
from utils.logger import log_error, log_info, log_warning

#: Friendly name -> pynput key.
KEY_MAP = {
    "win": keyboard.Key.cmd,
    "windows": keyboard.Key.cmd,
    "super": keyboard.Key.cmd,
    "cmd": keyboard.Key.cmd,
    "meta": keyboard.Key.cmd,
    "ctrl": keyboard.Key.ctrl,
    "control": keyboard.Key.ctrl,
    "shift": keyboard.Key.shift,
    "alt": keyboard.Key.alt,
}

MODIFIER_NAMES = {"win", "windows", "super", "cmd", "meta", "ctrl", "control", "shift", "alt"}

#: Combos that collide with Windows itself.  Warn, never silently accept.
RESERVED_COMBOS = {
    "win": "opens the Start menu",
    "win+d": "shows the desktop",
    "win+e": "opens File Explorer",
    "win+l": "locks Windows",
    "win+r": "opens the Run dialog",
    "win+s": "opens Search",
    "win+i": "opens Settings",
    "win+tab": "opens Task View",
    "alt+tab": "switches windows",
    "alt+f4": "closes the active window",
    "ctrl+c": "copies",
    "ctrl+v": "pastes",
    "ctrl+x": "cuts",
    "ctrl+z": "undoes",
    "ctrl+shift+v": "pastes as plain text",
    "ctrl+shift+esc": "opens Task Manager",
    "ctrl+alt+del": "opens the security screen",
}

# Backwards-compatible alias (older code imported UNSAFE_COMBOS).
UNSAFE_COMBOS = set(RESERVED_COMBOS)


class HotkeyValidationError(ValueError):
    """Raised for a shortcut string that cannot be used."""


def _canonical(key) -> object:
    mapping = {
        keyboard.Key.ctrl_l: keyboard.Key.ctrl,
        keyboard.Key.ctrl_r: keyboard.Key.ctrl,
        keyboard.Key.shift_l: keyboard.Key.shift,
        keyboard.Key.shift_r: keyboard.Key.shift,
        keyboard.Key.alt_l: keyboard.Key.alt,
        keyboard.Key.alt_r: keyboard.Key.alt,
        keyboard.Key.alt_gr: keyboard.Key.alt,
        keyboard.Key.cmd_l: keyboard.Key.cmd,
        keyboard.Key.cmd_r: keyboard.Key.cmd,
    }
    return mapping.get(key, key)


def parse_hotkey(hotkey: str) -> List[object]:
    """Parse a shortcut string into pynput keys.

    Accepts modifier-only combos (``win+shift``) and combos with a normal key
    (``ctrl+alt+r``).  Raises :class:`HotkeyValidationError` for anything else.
    """
    if not hotkey or not hotkey.strip():
        raise HotkeyValidationError("Shortcut is empty")

    parts = [p.strip().lower() for p in hotkey.split("+") if p.strip()]
    if not parts:
        raise HotkeyValidationError("Shortcut is empty")
    if len(parts) > 3:
        raise HotkeyValidationError("Use at most three keys (for example ctrl+alt+r)")

    deduped: List[str] = []
    for part in parts:
        if part in deduped:
            raise HotkeyValidationError(f"'{part}' is listed twice")
        deduped.append(part)

    keys: List[object] = []
    for part in deduped:
        if part in KEY_MAP:
            keys.append(KEY_MAP[part])
        elif len(part) == 1:
            keys.append(keyboard.KeyCode.from_char(part))
        else:
            raise HotkeyValidationError(f"'{part}' is not a recognised key")

    if all(isinstance(k, keyboard.Key) and k in set(KEY_MAP.values()) for k in keys) and not keys:
        raise HotkeyValidationError("Shortcut is empty")
    return keys


def normalize_hotkey(hotkey: str) -> str:
    """Return the canonical lowercase form used for comparison/storage."""
    return "+".join(sorted(p.strip().lower() for p in (hotkey or "").split("+") if p.strip()))


def is_reserved(hotkey: str) -> Optional[str]:
    """Return the reason a combo is reserved by Windows, else ``None``."""
    canonical = normalize_hotkey(hotkey)
    if canonical in RESERVED_COMBOS:
        return RESERVED_COMBOS[canonical]
    # "win" alone, or win + a single letter, is almost always a system shortcut.
    parts = canonical.split("+")
    if len(parts) == 1 and parts[0] in ("win", "windows", "super", "cmd", "meta"):
        return RESERVED_COMBOS["win"]
    return None


def is_safe_combo(hotkey: str) -> bool:
    """Backwards-compatible helper used by older callers."""
    return is_reserved(hotkey) is None


def validate_hotkey(hotkey: str) -> Tuple[bool, str, Optional[str]]:
    """Validate a shortcut string.

    Returns ``(ok, canonical, error)``.  ``error`` is a user-facing sentence.
    """
    try:
        parse_hotkey(hotkey)
    except HotkeyValidationError as exc:
        return False, "", str(exc)

    canonical = normalize_hotkey(hotkey)
    reason = is_reserved(canonical)
    if reason:
        return False, canonical, f"{canonical.replace('+', ' + ')} is reserved by Windows ({reason})."
    return True, canonical, None


def find_conflicts(hotkeys: Dict[str, str]) -> List[str]:
    """Return human-readable conflicts for a ``{shortcut: mode}`` mapping."""
    conflicts: List[str] = []
    seen: Dict[str, str] = {}
    for hotkey, mode in (hotkeys or {}).items():
        canonical = normalize_hotkey(hotkey)
        if not canonical:
            continue
        if canonical in seen:
            conflicts.append(f"{canonical.replace('+', ' + ')} is assigned to both {seen[canonical]} and {mode}")
        else:
            seen[canonical] = mode
        reason = is_reserved(canonical)
        if reason:
            conflicts.append(f"{canonical.replace('+', ' + ')} is reserved by Windows ({reason})")
    return conflicts


class _SingleHotkey:
    """Tracks one combo and fires callbacks on press/release."""

    def __init__(
        self,
        hotkey: str,
        on_press: Callable,
        on_release: Callable,
        toggle_mode: bool = False,
        mode_override: Optional[str] = None,
    ):
        self.hotkey = hotkey
        self.on_press = on_press
        self.on_release = on_release
        self.toggle_mode = toggle_mode
        self.mode_override = mode_override
        self._target_keys = parse_hotkey(hotkey)
        self._canonical_targets = {id(k): _canonical(k) for k in self._target_keys}
        self._active = False
        self._toggle_recording = False

    def _matches(self, held: Set) -> bool:
        for key in self._target_keys:
            if key not in held and _canonical(key) not in held:
                return False
        return True

    def handle_press(self, held: Set) -> None:
        if not self._matches(held):
            return
        if self._active:
            return
        self._active = True
        if self.toggle_mode:
            if not self._toggle_recording:
                self._toggle_recording = True
                threading.Thread(target=self.on_press, daemon=True).start()
            else:
                self._toggle_recording = False
                threading.Thread(target=self.on_release, daemon=True).start()
        else:
            threading.Thread(target=self.on_press, daemon=True).start()

    def handle_release(self, canon_key) -> None:
        if not self._active:
            return
        if any(_canonical(k) == canon_key for k in self._target_keys):
            self._active = False
            if not self.toggle_mode:
                threading.Thread(target=self.on_release, daemon=True).start()

    def reset(self) -> None:
        self._active = False


class HotkeyListener:
    def __init__(self, hotkey: str = "win+shift", toggle_mode: bool = False):
        self.toggle_mode = toggle_mode
        self.listener = None
        self.is_listening = False
        self.enabled = True
        self._held: Set = set()
        self._hotkeys: List[_SingleHotkey] = []
        self._mode_hotkeys: Dict[str, str] = {}
        self._restart_attempts = 0
        self._lock = threading.RLock()

        self.on_hotkey_pressed: Optional[Callable] = None
        self.on_hotkey_released: Optional[Callable] = None
        self.on_mode_hotkey: Optional[Callable] = None
        self.on_listener_lost: Optional[Callable] = None

        ok, canonical, error = validate_hotkey(hotkey)
        if ok:
            self.hotkey = canonical
        else:
            log_warning(f"Invalid hotkey '{hotkey}' ({error}) — falling back to win+shift")
            self.hotkey = "shift+win"
        self._build_hotkeys()

    # ── construction ──────────────────────────────────────────────────────

    def _build_hotkeys(self) -> None:
        self._hotkeys = []
        reason = is_reserved(self.hotkey)
        if reason:
            log_warning(f"Hotkey '{self.hotkey}' conflicts with Windows ({reason})")

        self._hotkeys.append(
            _SingleHotkey(
                self.hotkey,
                on_press=self._fire_pressed,
                on_release=self._fire_released,
                toggle_mode=self.toggle_mode,
            )
        )

        for hotkey, mode in self._mode_hotkeys.items():
            ok, canonical, error = validate_hotkey(hotkey)
            if not ok:
                log_warning(f"Mode hotkey '{hotkey}' rejected: {error}")
                continue
            if canonical == normalize_hotkey(self.hotkey):
                log_warning(f"Mode hotkey '{canonical}' duplicates the main hotkey — skipped")
                continue
            self._hotkeys.append(
                _SingleHotkey(
                    canonical,
                    on_press=lambda m=mode: self._fire_mode_pressed(m),
                    on_release=lambda m=mode: self._fire_mode_released(m),
                    toggle_mode=self.toggle_mode,
                    mode_override=mode,
                )
            )

    def set_mode_hotkeys(self, mode_hotkeys: Dict[str, str]) -> None:
        """Set extra hotkeys, e.g. ``{'win+alt': 'casual'}``."""
        self._mode_hotkeys = {str(k).lower(): str(v) for k, v in (mode_hotkeys or {}).items()}
        self._restart(self._build_hotkeys)

    def set_toggle_mode(self, enabled: bool) -> None:
        self.toggle_mode = bool(enabled)

        def rebuild() -> None:
            self._build_hotkeys()

        self._restart(rebuild)

    def set_enabled(self, enabled: bool) -> bool:
        """Enable/disable global shortcuts without destroying the app."""
        self.enabled = bool(enabled)
        if not self.enabled:
            self.stop_listening()
            log_info("Global shortcuts disabled")
        else:
            self.start_listening()
        return True

    def _restart(self, mutation: Callable) -> None:
        was = self.is_listening
        if was:
            self.stop_listening()
        mutation()
        if was and self.enabled:
            self.start_listening()

    # ── callbacks ─────────────────────────────────────────────────────────

    def _safe(self, label: str, fn: Callable) -> None:
        try:
            fn()
        except Exception as exc:
            log_error(f"{label}: {exc}", exc_info=True)

    def _fire_pressed(self) -> None:
        event_manager.emit(Events.HOTKEY_PRESSED)
        if self.on_hotkey_pressed:
            self._safe("on_hotkey_pressed", self.on_hotkey_pressed)

    def _fire_released(self) -> None:
        event_manager.emit(Events.HOTKEY_RELEASED)
        if self.on_hotkey_released:
            self._safe("on_hotkey_released", self.on_hotkey_released)

    def _fire_mode_pressed(self, mode: str) -> None:
        event_manager.emit(Events.MODE_HOTKEY_PRESSED, mode)
        if self.on_mode_hotkey:
            self._safe("on_mode_hotkey", lambda: self.on_mode_hotkey(mode, "press"))

    def _fire_mode_released(self, mode: str) -> None:
        event_manager.emit(Events.MODE_HOTKEY_RELEASED, mode)
        if self.on_mode_hotkey:
            self._safe("on_mode_hotkey", lambda: self.on_mode_hotkey(mode, "release"))

    # ── pynput callbacks ──────────────────────────────────────────────────

    def _on_press(self, key) -> None:
        try:
            self._held.add(_canonical(key))
            for hotkey in list(self._hotkeys):
                hotkey.handle_press(self._held)
        except Exception as exc:  # pragma: no cover - must never kill the hook
            log_error(f"Press handler: {exc}")

    def _on_release(self, key) -> None:
        try:
            canon = _canonical(key)
            for hotkey in list(self._hotkeys):
                hotkey.handle_release(canon)
            self._held.discard(canon)
            self._sync_modifiers()
        except Exception as exc:  # pragma: no cover
            log_error(f"Release handler: {exc}")

    def _sync_modifiers(self) -> None:
        """Drop modifiers we no longer believe are held.

        Windows can swallow a key-up (e.g. Win+L), which otherwise leaves the
        combo stuck "held" and recording forever.
        """
        try:
            import ctypes

            user32 = ctypes.windll.user32
            pressed = {
                keyboard.Key.ctrl: user32.GetAsyncKeyState(0x11) & 0x8000,
                keyboard.Key.shift: user32.GetAsyncKeyState(0x10) & 0x8000,
                keyboard.Key.alt: user32.GetAsyncKeyState(0x12) & 0x8000,
                keyboard.Key.cmd: (user32.GetAsyncKeyState(0x5B) | user32.GetAsyncKeyState(0x5C)) & 0x8000,
            }
            for key, is_down in pressed.items():
                if not is_down:
                    self._held.discard(key)
                else:
                    self._held.add(key)
        except Exception:
            pass

    # ── lifecycle ─────────────────────────────────────────────────────────

    def start_listening(self) -> bool:
        with self._lock:
            if self.is_listening:
                return False
            if not self.enabled:
                return False
            try:
                self._held.clear()
                for hotkey in self._hotkeys:
                    hotkey.reset()
                self.listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
                self.listener.start()
                self.is_listening = True
                self._restart_attempts = 0
                log_info(f"Hotkey listener started: {self.hotkey} (toggle={self.toggle_mode})")
                return True
            except Exception as exc:
                log_error(f"Error starting listener: {exc}", exc_info=True)
                return False

    def stop_listening(self) -> bool:
        with self._lock:
            if not self.is_listening:
                return False
            try:
                if self.listener:
                    self.listener.stop()
                    self.listener = None
                self.is_listening = False
                self._held.clear()
                log_info("Hotkey listener stopped")
                return True
            except Exception as exc:
                log_error(f"Error stopping listener: {exc}", exc_info=True)
                return False

    def is_alive(self) -> bool:
        return bool(self.listener and self.listener.is_alive())

    def recover(self) -> bool:
        """Restart a dead hook. Returns True if shortcuts are usable again."""
        with self._lock:
            if not self.enabled:
                return False
            if self.is_alive():
                return True
            if self._restart_attempts >= 1:
                log_warning("Hotkey listener already recovered once — not retrying again")
                return False
            self._restart_attempts += 1
            self.is_listening = False
            log_warning("Attempting to recover the hotkey listener")
            return self.start_listening()

    def set_hotkey(self, new_hotkey: str) -> bool:
        """Validate and apply a new main shortcut. Returns False if invalid."""
        ok, canonical, error = validate_hotkey(new_hotkey)
        if not ok:
            log_warning(f"Rejected hotkey '{new_hotkey}': {error}")
            return False

        def rebuild() -> None:
            self.hotkey = canonical
            self._build_hotkeys()

        self._restart(rebuild)
        log_info(f"Hotkey changed to: {self.hotkey}")
        return True

    def describe(self) -> dict:
        return {
            "hotkey": self.hotkey,
            "toggle_mode": self.toggle_mode,
            "enabled": self.enabled,
            "listening": self.is_listening,
            "alive": self.is_alive(),
            "mode_hotkeys": dict(self._mode_hotkeys),
        }
