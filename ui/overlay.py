"""
Voxylis — Listening Icon Widget (Waveform with Live Text)
Shows animated waveform when recording (listening) and displays live transcription text.
"""

import random
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import (
    QPainter,
    QColor,
    QFont,
    QFontMetrics,
)

# ── canvas & geometry constants ────────────────────────────────────────────
W, H = 60, 20  # widget size
CX = W // 2  # 30
CY = H // 2  # 10

BAR_COUNT = 5
BAR_WIDTH = 3
BAR_GAP = 2
MAX_BAR_HEIGHT = 8


class FloatingWidget(QWidget):
    status_changed = pyqtSignal(str)
    level_changed = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self.current_status = "ready"
        self.audio_level = 0.0
        self._bars = [0.0] * BAR_COUNT
        self.live_text = ""
        self._text_offset = 0

        self._setup_window()
        self._centre_screen()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)  # ~30 fps

        # Hidden by default — only shows while hotkey is held (recording)
        self.hide()

    # ── window ────────────────────────────────────────────────────────────
    def _setup_window(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(W, H)

    def _centre_screen(self):
        geo = QApplication.primaryScreen().availableGeometry()
        self.move(geo.center().x() - W // 2, geo.bottom() - H - 18)

    # ── animation tick ────────────────────────────────────────────────────
    def _tick(self):
        if self.current_status == "recording":
            base = self.audio_level / 100.0
            for i in range(BAR_COUNT):
                t = base * (0.25 + random.random() * 0.75)
                self._bars[i] += (t - self._bars[i]) * 0.4
        else:
            for i in range(BAR_COUNT):
                self._bars[i] *= 0.78  # decay when not recording

        # Animate live text ticker
        if self.live_text:
            self._text_offset = (self._text_offset + 1) % max(
                1, len(self.live_text) * 7
            )

        self.update()

    # ── paint dispatcher ──────────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self._draw_waveform(p)
        self._draw_live_text(p)

    # ── waveform ──────────────────────────────────────────────────────────
    def _draw_waveform(self, p: QPainter):
        total = BAR_COUNT * BAR_WIDTH + (BAR_COUNT - 1) * BAR_GAP
        x0 = CX - total // 2
        base_y = CY  # center vertically

        for i, lv in enumerate(self._bars):
            bh = max(2, int(lv * MAX_BAR_HEIGHT))
            x = x0 + i * (BAR_WIDTH + BAR_GAP)
            y = base_y + (MAX_BAR_HEIGHT - bh) // 2  # center the bar vertically

            if self.current_status == "recording":
                # Black color for listening indicator
                col = QColor(0, 0, 0, 200)  # Black with some transparency
            else:
                col = QColor(115, 115, 145, 100)  # dim gray when idle

            p.setPen(Qt.NoPen)
            p.setBrush(col)
            p.drawRoundedRect(x, y, BAR_WIDTH, bh, 1, 1)

    # ── live text ticker ──────────────────────────────────────────────────
    def _draw_live_text(self, p: QPainter):
        if not self.live_text:
            return
        p.setPen(QColor(255, 255, 255, 180))
        p.setFont(QFont("Arial", 7))
        fm = QFontMetrics(p.font())
        tw = fm.horizontalAdvance(self.live_text)
        # Limit text length to prevent extremely long strings from causing performance issues
        display_text = self.live_text[:100] + (
            "..." if len(self.live_text) > 100 else ""
        )
        tw = fm.horizontalAdvance(display_text)
        x = W - (self._text_offset % (tw + W))
        p.setClipRect(0, H - 12, W, 10)
        p.drawText(x, H - 2, display_text)
        p.setClipping(False)

    # ── public API ────────────────────────────────────────────────────────
    def set_recording(self, is_recording: bool):
        if is_recording:
            self.current_status = "recording"
            self.live_text = ""  # Clear live text when starting
            self._text_offset = 0
            self.show()  # Pop up when hotkey pressed
        else:
            self.current_status = "ready"
            self.hide()  # Disappear immediately on release
        self.update()

    def set_processing(self, is_processing: bool):
        # Never show during processing — user already released the key
        self.current_status = "ready"
        self.hide()
        self.update()

    def set_status(self, status: str, info: str = ""):
        s = status.lower()
        if "record" in s:
            self.current_status = "recording"
            self.show()
        else:
            # Everything else (processing, done, ready) — stay hidden
            self.current_status = "ready"
            self.hide()
        self.update()

    def set_audio_level(self, level: float):
        self.audio_level = level

    def set_live_text(self, text: str):
        self.live_text = text
        self._text_offset = 0
        self.update()

    # Unused methods for compatibility (keep empty)
    def set_profile(self, name: str):
        pass

    def set_language(self, language_name: str, language_code: str):
        pass

    def set_theme(self, theme: str = "dark"):
        pass

    def toggle_visibility(self):
        self.hide() if self.isVisible() else self.show()

    # ── drag ──────────────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
        event.accept()

    def mouseMoveEvent(self, event):
        if hasattr(self, "_drag_pos"):
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseDoubleClickEvent(self, event):
        self._centre_screen()
        event.accept()
