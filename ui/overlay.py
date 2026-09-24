"""
Voxylis recording overlay.

A small transient pill that appears while the hotkey is held and disappears
when the pipeline finishes.  It is deliberately *not* the application UI — the
main window owns configuration and history.

It shows:
  * recording / processing / success / error state with distinct colours;
  * microphone state (no input detected, quiet input, good input);
  * a live waveform driven by the real audio level;
  * elapsed time and the maximum-duration warning;
  * the detected language and current enhancement mode;
  * the live transcript when the provider returns it.

Positioning is DPI-aware and follows the screen that currently has the mouse
cursor, so it is correct on multi-monitor and mixed-DPI setups.
"""

from __future__ import annotations

import time
from typing import Optional

from PyQt5.QtCore import QPoint, QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt5.QtWidgets import QApplication, QWidget

from ui import theme

WIDTH = 320
HEIGHT = 64
MARGIN_BOTTOM = 56
RADIUS = 16
BAR_COUNT = 9

STATE_IDLE = "idle"
STATE_RECORDING = "recording"
STATE_PROCESSING = "processing"
STATE_SUCCESS = "success"
STATE_ERROR = "error"
STATE_CANCELLED = "cancelled"

_AUTOHIDE_MS = {STATE_SUCCESS: 1800, STATE_ERROR: 4200, STATE_CANCELLED: 1200}


class FloatingWidget(QWidget):
    """Transient status pill shown during and right after a recording."""

    status_changed = pyqtSignal(str)
    level_changed = pyqtSignal(float)
    cancel_requested = pyqtSignal()

    def __init__(self, max_recording_seconds: int = 600):
        super().__init__()
        self.state = STATE_IDLE
        self.audio_level = 0.0
        self.peak_level = 0.0
        self.live_text = ""
        self.language_name = ""
        self.language_code = ""
        self.mode = ""
        self._detail = ""
        self._bars = [0.0] * BAR_COUNT
        self._started_at: Optional[float] = None
        self._elapsed = 0.0
        self.max_recording_seconds = max_recording_seconds
        self._theme = "dark"

        self._setup_window()
        self._move_to_active_screen()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)  # ~30 fps

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._auto_hide)

        self.setAccessibleName("Voxylis recording status")
        self.setAccessibleDescription("Shows whether Voxylis is listening, processing or finished.")
        self.hide()

    # ── window setup ─────────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(WIDTH, HEIGHT)
        self.setCursor(Qt.ArrowCursor)
        self.setToolTip("Voxylis — click to cancel the current recording")

    def _move_to_active_screen(self) -> None:
        """Centre on the screen that currently has the cursor (multi-monitor)."""
        screen = None
        try:
            cursor_pos = QApplication.instance().desktop().cursor().pos() if QApplication.instance() else None
            if cursor_pos is not None:
                screen = QApplication.screenAt(cursor_pos)
        except Exception:
            screen = None
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        x = geometry.center().x() - WIDTH // 2
        y = geometry.bottom() - HEIGHT - MARGIN_BOTTOM
        # Clamp so the pill can never be pushed off-screen by a small panel.
        x = max(geometry.left() + 8, min(x, geometry.right() - WIDTH - 8))
        y = max(geometry.top() + 8, min(y, geometry.bottom() - HEIGHT - 8))
        self.move(QPoint(int(x), int(y)))

    # ── animation ────────────────────────────────────────────────────────

    def _tick(self) -> None:
        if self.state == STATE_RECORDING:
            self._elapsed = (time.time() - self._started_at) if self._started_at else 0.0
            base = min(1.0, self.audio_level / 100.0)
            for index in range(BAR_COUNT):
                # Shape the bars so the middle of the waveform is tallest.
                shape = 1.0 - abs(index - (BAR_COUNT - 1) / 2) / (BAR_COUNT / 2)
                target = base * (0.25 + 0.75 * shape)
                self._bars[index] += (target - self._bars[index]) * 0.35
        else:
            for index in range(BAR_COUNT):
                self._bars[index] *= 0.8

        self.update()

    # ── painting ─────────────────────────────────────────────────────────

    def _colors(self) -> dict:
        return theme.palette(self._theme)

    def paintEvent(self, event):  # noqa: N802 - Qt naming
        colors = self._colors()
        accent = {
            STATE_RECORDING: colors["recording"],
            STATE_PROCESSING: colors["accent"],
            STATE_SUCCESS: colors["success"],
            STATE_ERROR: colors["danger"],
            STATE_CANCELLED: colors["warning"],
        }.get(self.state, colors["accent"])

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # pill background
        painter.setPen(QPen(QColor(accent), 1.4))
        painter.setBrush(QColor(colors["bg_elevated"]))
        painter.drawRoundedRect(QRectF(0.7, 0.7, WIDTH - 1.4, HEIGHT - 1.4), RADIUS, RADIUS)

        self._draw_glyph(painter, accent, colors)
        self._draw_waveform(painter, accent)
        self._draw_meta(painter, colors)
        self._draw_live_text(painter, colors)
        painter.end()

    def _draw_glyph(self, painter: QPainter, accent, colors: dict) -> None:
        """Small state dot; pulses while listening."""
        rect = QRectF(16, 22, 16, 16)
        painter.setPen(Qt.NoPen)
        if self.state == STATE_RECORDING:
            pulse = 1.0 + 0.12 * (self.audio_level / 100.0)
            size = 14 * pulse
            rect = QRectF(16 + (16 - size) / 2, 22 + (16 - size) / 2, size, size)
        painter.setBrush(QColor(accent))
        painter.drawEllipse(rect)

        if self.state == STATE_RECORDING and self.audio_level < 1.0:
            # Mic is open but silent: warn with a hollow ring.
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(colors["warning"]), 1.5))
            painter.drawEllipse(QRectF(13, 19, 22, 22))

    def _draw_waveform(self, painter: QPainter, accent) -> None:
        left = 44
        right = WIDTH - 96
        available = right - left
        bar_width = 3
        gap = (available - BAR_COUNT * bar_width) / max(1, BAR_COUNT - 1)
        center_y = HEIGHT / 2
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(accent))

        for index, level in enumerate(self._bars):
            max_height = 20
            height = max(2.0, min(max_height, 2.0 + level * max_height))
            x = left + index * (bar_width + gap)
            painter.drawRoundedRect(QRectF(x, center_y - height / 2, bar_width, height), 1.5, 1.5)

    def _draw_meta(self, painter: QPainter, colors: dict) -> None:
        painter.setPen(QColor(colors["text"]))
        font = QFont("Segoe UI", 9)
        font.setBold(True)
        painter.setFont(font)

        if self.state == STATE_RECORDING:
            text = self._format_elapsed()
        else:
            text = {
                STATE_PROCESSING: "Working…",
                STATE_SUCCESS: "Inserted",
                STATE_ERROR: "Failed",
                STATE_CANCELLED: "Cancelled",
            }.get(self.state, "")
        painter.drawText(QRectF(WIDTH - 92, 12, 78, 16), Qt.AlignRight | Qt.AlignVCenter, text)

        badges = []
        if self.language_name or self.language_code:
            badges.append(self.language_name or self.language_code.upper())
        if self.mode:
            badges.append(self.mode.capitalize())
        painter.setPen(QColor(colors["text_muted"]))
        small = QFont("Segoe UI", 8)
        painter.setFont(small)
        painter.drawText(
            QRectF(WIDTH - 132, 30, 118, 14),
            Qt.AlignRight | Qt.AlignVCenter,
            " · ".join(badges),
        )

        # Max-duration warning
        if self.state == STATE_RECORDING and self._elapsed > self.max_recording_seconds - 30:
            painter.setPen(QColor(colors["warning"]))
            painter.drawText(
                QRectF(WIDTH - 132, 46, 118, 14),
                Qt.AlignRight | Qt.AlignVCenter,
                f"max {self.max_recording_seconds // 60}m",
            )

    def _draw_live_text(self, painter: QPainter, colors: dict) -> None:
        if not self.live_text:
            return
        painter.setPen(QColor(colors["text_muted"]))
        painter.setFont(QFont("Segoe UI", 8))
        metrics = QFontMetrics(painter.font())
        available = WIDTH - 32
        text = metrics.elidedText(self.live_text.replace("\n", " "), Qt.ElideRight, available)
        painter.drawText(QRectF(16, HEIGHT - 18, available, 14), Qt.AlignLeft | Qt.AlignVCenter, text)

    def _format_elapsed(self) -> str:
        seconds = int(self._elapsed)
        return f"{seconds // 60}:{seconds % 60:02d}"

    # ── state API ────────────────────────────────────────────────────────

    def set_stage(self, stage: str, detail: str = "") -> None:
        """Drive the overlay from pipeline stages."""
        self._hide_timer.stop()
        if stage == "recording":
            self._enter_recording()
            return
        mapping = {
            "transcribing": (STATE_PROCESSING, "Transcribing…"),
            "enhancing": (STATE_PROCESSING, "Enhancing…"),
            "injecting": (STATE_PROCESSING, "Inserting…"),
        }
        if stage in mapping:
            state, label = mapping[stage]
            self.state = state
            self._detail = detail or label
            self._show()
            self.setAccessibleDescription(label)
            self.update()
            return
        if stage == "idle":
            self._exit_recording()

    def _enter_recording(self) -> None:
        self.state = STATE_RECORDING
        self.live_text = ""
        self.peak_level = 0.0
        self._elapsed = 0.0
        self._started_at = time.time()
        self._move_to_active_screen()
        self._show()
        self.setAccessibleDescription("Listening. Speak now.")
        self.update()

    def _exit_recording(self) -> None:
        self._started_at = None
        if self.state == STATE_RECORDING:
            self.state = STATE_PROCESSING
            self.setAccessibleDescription("Processing your recording.")
            self.update()

    def show_success(self, detail: str = "Text inserted", auto_hide_ms: Optional[int] = None) -> None:
        self.state = STATE_SUCCESS
        self._detail = detail
        self.live_text = ""
        self._started_at = None
        self._show()
        self.setAccessibleDescription(detail)
        self._schedule_hide(auto_hide_ms or _AUTOHIDE_MS[STATE_SUCCESS], force=True)
        self.update()

    def show_error(self, detail: str = "Something went wrong") -> None:
        self.state = STATE_ERROR
        self._detail = detail
        self._started_at = None
        self._show()
        self.setAccessibleDescription(detail)
        self._schedule_hide(_AUTOHIDE_MS[STATE_ERROR], force=True)
        self.update()

    def show_cancelled(self, detail: str = "Cancelled") -> None:
        self.state = STATE_CANCELLED
        self._detail = detail
        self._started_at = None
        self._show()
        self._schedule_hide(_AUTOHIDE_MS[STATE_CANCELLED], force=True)
        self.update()

    def _schedule_hide(self, milliseconds: int, force: bool = False) -> None:
        # Errors/success must always auto-hide, even if a stray "hidden" state
        # was set by an older signal path.
        if force or self.state not in (STATE_RECORDING, STATE_PROCESSING):
            self._hide_timer.start(max(200, int(milliseconds)))

    def _auto_hide(self) -> None:
        if self.state in (STATE_RECORDING, STATE_PROCESSING):
            return
        self.hide()

    def _show(self) -> None:
        self._move_to_active_screen() if self.state == STATE_RECORDING else None
        if not self.isVisible():
            self.show()
        self.raise_()

    # ── legacy / compatibility API ───────────────────────────────────────

    def set_recording(self, is_recording: bool) -> None:
        if is_recording:
            self._enter_recording()
        else:
            self._exit_recording()

    def set_processing(self, is_processing: bool) -> None:
        if is_processing:
            self.set_stage("transcribing")
        elif self.state == STATE_PROCESSING:
            self.set_stage("idle")

    def set_status(self, status: str, info: str = "") -> None:
        lowered = (status or "").lower()
        if "record" in lowered:
            self._enter_recording()
        elif "done" in lowered or "success" in lowered:
            self.show_success(info or "Text inserted")
        elif "error" in lowered or "fail" in lowered:
            self.show_error(info or self._detail or "Something went wrong")
        elif "cancel" in lowered:
            self.show_cancelled(info or "Cancelled")
        elif "process" in lowered or "transcrib" in lowered or "enhanc" in lowered:
            self.set_stage("transcribing", info)
        else:
            self.set_stage("idle")
        self.status_changed.emit(self.state)

    def set_audio_level(self, level: float) -> None:
        self.audio_level = float(level or 0.0)
        self.peak_level = max(self.peak_level, self.audio_level)
        self.level_changed.emit(self.audio_level)

    def set_live_text(self, text: str) -> None:
        self.live_text = (text or "")[:400]
        self.update()

    def set_language(self, language_name: str, language_code: str = "") -> None:
        self.language_name = language_name or ""
        self.language_code = language_code or ""
        self.update()

    def set_mode(self, mode: str) -> None:
        self.mode = mode or ""
        self.update()

    def set_profile(self, name: str) -> None:
        self.mode = name or self.mode
        self.update()

    def set_theme(self, theme_name: str = "dark") -> None:
        self._theme = "light" if str(theme_name).lower() == "light" else "dark"
        self.update()

    @property
    def mic_healthy(self) -> bool:
        return self.peak_level > 2.0

    def toggle_visibility(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self._enter_recording()

    # ── input ────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):  # noqa: N802
        self.cancel_requested.emit()
        if self.state == STATE_RECORDING:
            self.show_cancelled()
        event.accept()

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        self._move_to_active_screen()
        event.accept()

    def keyPressEvent(self, event):  # noqa: N802 - accessibility: Esc cancels
        if event.key() == Qt.Key_Escape:
            self.cancel_requested.emit()
            self.show_cancelled()
        else:
            super().keyPressEvent(event)
