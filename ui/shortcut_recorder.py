"""
Shortcut capture widget.

Users must never have to type ``win+shift`` by hand.  This widget captures the
actual key combination that is pressed, normalises it, and validates it against
the same rules the listener enforces (reserved Windows combos, modifier-only
rules, malformed input, duplicates).
"""

from __future__ import annotations

from typing import List, Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from core.hotkey_listener import normalize_hotkey, validate_hotkey

#: Qt modifier flag -> friendly token.
_MODIFIERS = [
    (Qt.ControlModifier, "ctrl"),
    (Qt.AltModifier, "alt"),
    (Qt.ShiftModifier, "shift"),
    (Qt.MetaModifier, "win"),
]

#: Qt key -> friendly token for non-modifier keys.
_KEY_NAMES = {
    Qt.Key_Space: "space",
    Qt.Key_Return: "enter",
    Qt.Key_Enter: "enter",
    Qt.Key_Escape: None,  # cancels capture
    Qt.Key_Tab: "tab",
    Qt.Key_Backspace: "backspace",
    Qt.Key_Delete: "delete",
    Qt.Key_Insert: "insert",
    Qt.Key_Home: "home",
    Qt.Key_End: "end",
    Qt.Key_PageUp: "pageup",
    Qt.Key_PageDown: "pagedown",
    Qt.Key_Up: "up",
    Qt.Key_Down: "down",
    Qt.Key_Left: "left",
    Qt.Key_Right: "right",
}

MODIFIER_TOKENS = {"ctrl", "alt", "shift", "win"}
_DISPLAY_ORDER = ["ctrl", "alt", "shift", "win"]
_DISPLAY_LABEL = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Win"}


def format_hotkey(hotkey: str) -> str:
    """Render a stored shortcut in a human order: ``Win + Shift``."""
    if not hotkey:
        return "Not set"
    tokens = [t for t in hotkey.split("+") if t]
    ordered = [t for t in _DISPLAY_ORDER if t in tokens]
    ordered += [t for t in tokens if t not in MODIFIER_TOKENS and t not in _DISPLAY_ORDER]
    labels = (_DISPLAY_LABEL.get(t, t.upper() if len(t) == 1 else t.capitalize()) for t in ordered)
    return " + ".join(labels)


def event_to_hotkey(event: QKeyEvent) -> Optional[str]:
    """Convert a Qt key event into a shortcut string (``None`` if unusable)."""
    tokens: List[str] = []
    for flag, name in _MODIFIERS:
        if event.modifiers() & flag:
            tokens.append(name)

    key = event.key()
    if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
        # Modifier-only combo: valid (this is how win+shift works).
        return "+".join(tokens) if tokens else None
    if key in _KEY_NAMES:
        name = _KEY_NAMES[key]
        if name is None:
            return None
        tokens.append(name)
    elif 0x20 <= key <= 0x7E or Qt.Key_F1 <= key <= Qt.Key_F35:
        text = event.text().strip()
        if text:
            tokens.append(text.lower())
        else:
            tokens.append(f"f{key - Qt.Key_F1 + 1}" if Qt.Key_F1 <= key <= Qt.Key_F35 else "")
    else:
        return None

    tokens = [t for t in tokens if t]
    if not tokens:
        return None
    return "+".join(tokens)


class ShortcutRecorder(QWidget):
    """A click-to-record shortcut field.

    Emits :attr:`changed` with the normalised shortcut when a valid combination
    is captured, and :attr:`invalid` with a user-facing reason otherwise.
    """

    changed = pyqtSignal(str)
    invalid = pyqtSignal(str)

    def __init__(self, value: str = "", parent=None):
        super().__init__(parent)
        self._value = normalize_hotkey(value) if value else ""
        self._capturing = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.field = QPushButton()
        self.field.setObjectName("ShortcutField")
        self.field.setMinimumWidth(180)
        self.field.setFocusPolicy(Qt.StrongFocus)
        self.field.setToolTip("Click, then press the key combination you want")
        self.field.clicked.connect(self._start_capture)
        self.field.installEventFilter(self)
        self.field.setStyleSheet("QPushButton#ShortcutField { text-align: left; padding: 8px 12px; }")
        layout.addWidget(self.field)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self._clear)
        layout.addWidget(self.clear_button)

        self.hint = QLabel("")
        self.hint.setObjectName("Hint")
        layout.addWidget(self.hint)
        layout.addStretch()

        self._refresh()

    # ── public API ────────────────────────────────────────────────────────

    def value(self) -> str:
        return self._value

    def set_value(self, value: str, silent: bool = True) -> None:
        self._value = normalize_hotkey(value) if value else ""
        self._refresh()
        if not silent and self._value:
            self.changed.emit(self._value)

    # ── capture ───────────────────────────────────────────────────────────

    def _start_capture(self) -> None:
        self._capturing = True
        self.field.setText("Press shortcut…")
        self.hint.setText("Esc cancels")

    def _stop_capture(self) -> None:
        self._capturing = False

    def _clear(self) -> None:
        self._stop_capture()
        self._value = ""
        self.hint.setText("")
        self._refresh()
        self.changed.emit("")

    def _refresh(self) -> None:
        self.field.setText(format_hotkey(self._value) if self._value else "Not set")
        self.field.setFocusPolicy(Qt.StrongFocus)

    def eventFilter(self, obj, event):  # noqa: N802 - Qt naming
        if obj is self.field and self._capturing:
            if event.type() == QKeyEvent.KeyPress:
                if event.key() == Qt.Key_Escape:
                    self._capturing = False
                    self._refresh()
                    self.hint.setText("Cancelled")
                    return True
                candidate = event_to_hotkey(event)
                if candidate is None:
                    self.hint.setText("Add a modifier, e.g. Ctrl / Alt / Shift / Win")
                    return True
                ok, canonical, error = validate_hotkey(candidate)
                if not ok:
                    self.hint.setText(error or "That combination cannot be used")
                    self.invalid.emit(error or "invalid shortcut")
                    return True
                self._capturing = False
                self._value = canonical
                self.hint.setText("")
                self._refresh()
                self.changed.emit(canonical)
                return True
            if event.type() == QKeyEvent.KeyRelease:
                return True
        return super().eventFilter(obj, event)

    def focusOutEvent(self, event):  # noqa: N802
        if self._capturing:
            self._capturing = False
            self._refresh()
        super().focusOutEvent(event)
