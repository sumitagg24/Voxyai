"""
Global hotkey listener for Voxylis.
Supports:
  - Hold mode (default): hold to record, release to stop
  - Toggle mode: press once to start, press again to stop
  - Multiple hotkeys with per-mode overrides
  - Modifier-only combos (win+shift, win+alt, etc.)
  - Safe combos that don't clash with Windows defaults
"""

import threading
from typing import Callable, Optional, Set, Dict
from pynput import keyboard
from utils.logger import log_info, log_error, log_warning
from core.event_manager import event_manager, Events

# Friendly name -> pynput Key
KEY_MAP = {
    "win": keyboard.Key.cmd,
    "windows": keyboard.Key.cmd,
    "super": keyboard.Key.cmd,
    "cmd": keyboard.Key.cmd,
    "ctrl": keyboard.Key.ctrl,
    "shift": keyboard.Key.shift,
    "alt": keyboard.Key.alt,
}

# Combos known to conflict with Windows — warn if user picks these
UNSAFE_COMBOS = {
    "win",
    "win+d",
    "win+e",
    "win+l",
    "win+r",
    "win+s",
    "ctrl+c",
    "ctrl+v",
    "ctrl+x",
    "ctrl+z",
    "ctrl+shift+v",
    "alt+f4",
    "alt+tab",
}


def _parse_keys(hotkey: str) -> list:
    result = []
    for part in hotkey.lower().split("+"):
        part = part.strip()
        result.append(KEY_MAP.get(part, keyboard.KeyCode.from_char(part)))
    return result


def _canonical(key) -> object:
    mapping = {
        keyboard.Key.ctrl_l: keyboard.Key.ctrl,
        keyboard.Key.ctrl_r: keyboard.Key.ctrl,
        keyboard.Key.shift_l: keyboard.Key.shift,
        keyboard.Key.shift_r: keyboard.Key.shift,
        keyboard.Key.alt_l: keyboard.Key.alt,
        keyboard.Key.alt_r: keyboard.Key.alt,
        keyboard.Key.cmd_l: keyboard.Key.cmd,
        keyboard.Key.cmd_r: keyboard.Key.cmd,
    }
    return mapping.get(key, key)


def is_safe_combo(hotkey: str) -> bool:
    return hotkey.lower() not in UNSAFE_COMBOS


class _SingleHotkey:
    """Tracks one hotkey combo and fires callbacks."""

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
        self._target_keys = _parse_keys(hotkey)
        self._active = False
        self._toggle_recording = False  # for toggle mode

    def handle_press(self, held: Set):
        canon_held = held
        if all(
            _canonical(k) in canon_held or k in canon_held for k in self._target_keys
        ):
            if not self._active:
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

    def handle_release(self, canon_key):
        if self._active and canon_key in [_canonical(k) for k in self._target_keys]:
            self._active = False
            if not self.toggle_mode:
                threading.Thread(target=self.on_release, daemon=True).start()


class HotkeyListener:
    def __init__(self, hotkey: str = "win+shift", toggle_mode: bool = False):
        self.hotkey = hotkey
        self.toggle_mode = toggle_mode
        self.listener = None
        self.is_listening = False
        self._held: Set = set()
        self._hotkeys: list = []

        self.on_hotkey_pressed: Optional[Callable] = None
        self.on_hotkey_released: Optional[Callable] = None

        # Extra per-mode hotkeys: {hotkey_str: mode_name}
        self._mode_hotkeys: Dict[str, str] = {}
        # Callback for mode-override hotkeys: fn(mode_name)
        self.on_mode_hotkey: Optional[Callable] = None

        self._build_hotkeys()

    def _build_hotkeys(self):
        self._hotkeys = []
        if not is_safe_combo(self.hotkey):
            log_warning(f"Hotkey '{self.hotkey}' may conflict with Windows shortcuts")

        self._hotkeys.append(
            _SingleHotkey(
                self.hotkey,
                on_press=self._fire_pressed,
                on_release=self._fire_released,
                toggle_mode=self.toggle_mode,
            )
        )

        for hk, mode in self._mode_hotkeys.items():
            m = mode  # capture
            self._hotkeys.append(
                _SingleHotkey(
                    hk,
                    on_press=lambda m=m: self._fire_mode_pressed(m),
                    on_release=lambda m=m: self._fire_mode_released(m),
                    toggle_mode=self.toggle_mode,
                    mode_override=mode,
                )
            )

    def set_mode_hotkeys(self, mode_hotkeys: Dict[str, str]):
        """Set extra hotkeys: {'win+alt': 'casual', 'win+ctrl': 'technical'}"""
        self._mode_hotkeys = {k.lower(): v for k, v in mode_hotkeys.items()}
        was = self.is_listening
        if was:
            self.stop_listening()
        self._build_hotkeys()
        if was:
            self.start_listening()

    def set_toggle_mode(self, enabled: bool):
        self.toggle_mode = enabled
        was = self.is_listening
        if was:
            self.stop_listening()
        self._build_hotkeys()
        if was:
            self.start_listening()

    def _fire_pressed(self):
        event_manager.emit(Events.HOTKEY_PRESSED)
        if self.on_hotkey_pressed:
            try:
                self.on_hotkey_pressed()
            except Exception as e:
                log_error(f"on_hotkey_pressed: {e}", exc_info=True)

    def _fire_released(self):
        event_manager.emit(Events.HOTKEY_RELEASED)
        if self.on_hotkey_released:
            try:
                self.on_hotkey_released()
            except Exception as e:
                log_error(f"on_hotkey_released: {e}", exc_info=True)

    def _fire_mode_pressed(self, mode: str):
        event_manager.emit(Events.MODE_HOTKEY_PRESSED, mode)
        if self.on_mode_hotkey:
            try:
                self.on_mode_hotkey(mode, "press")
            except Exception as e:
                log_error(f"on_mode_hotkey: {e}", exc_info=True)

    def _fire_mode_released(self, mode: str):
        event_manager.emit(Events.MODE_HOTKEY_RELEASED, mode)
        if self.on_mode_hotkey:
            try:
                self.on_mode_hotkey(mode, "release")
            except Exception as e:
                log_error(f"on_mode_hotkey: {e}", exc_info=True)

    def _on_press(self, key):
        try:
            self._held.add(_canonical(key))
            for hk in self._hotkeys:
                hk.handle_press(self._held)
        except Exception as e:
            log_error(f"Press handler: {e}")

    def _on_release(self, key):
        try:
            canon = _canonical(key)
            for hk in self._hotkeys:
                hk.handle_release(canon)
            self._held.discard(canon)
        except Exception as e:
            log_error(f"Release handler: {e}")

    def start_listening(self) -> bool:
        try:
            if self.is_listening:
                return False
            self.listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
            )
            self.listener.start()
            self.is_listening = True
            log_info(
                f"Hotkey listener started: {self.hotkey} (toggle={self.toggle_mode})"
            )
            return True
        except Exception as e:
            log_error(f"Error starting listener: {e}", exc_info=True)
            return False

    def stop_listening(self) -> bool:
        try:
            if not self.is_listening:
                return False
            if self.listener:
                self.listener.stop()
                self.listener = None
            self.is_listening = False
            self._held.clear()
            log_info("Hotkey listener stopped")
            return True
        except Exception as e:
            log_error(f"Error stopping listener: {e}", exc_info=True)
            return False

    def set_hotkey(self, new_hotkey: str) -> bool:
        try:
            was = self.is_listening
            if was:
                self.stop_listening()
            self.hotkey = new_hotkey
            self._build_hotkeys()
            if was:
                self.start_listening()
            log_info(f"Hotkey changed to: {new_hotkey}")
            return True
        except Exception as e:
            log_error(f"Error changing hotkey: {e}", exc_info=True)
            return False
