"""
Voxylis — Compact Minion Mascot Widget  (80 × 120 px)
Custom-drawn, NOT a copy of the original character:
  • Chubby yellow pill body
  • Two round goggle eyes with coloured irises + blink
  • Dark headphone band arcing over the top
  • Red ear-cups that pulse when recording
  • Denim overalls with pocket + shoulder straps
  • Stubby arms + dark round hands
  • Expressive mouth (smile / open / thinking)
  • 5-bar animated waveform below body
  • Soft glow ring while recording / processing
  • Language & profile micro-badges
  • Draggable · double-click to re-centre · always-on-top
"""

import random
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtCore    import Qt, QTimer, QPoint, QRectF, pyqtSignal
from PyQt5.QtGui     import (
    QPainter, QColor, QBrush, QPen, QFont,
    QLinearGradient, QFontMetrics, QPainterPath
)

# ── canvas & geometry constants ────────────────────────────────────────────
W,  H   = 48, 64         # widget size  (micro!)
CX      = W // 2         # 24

# pill body
BY      = 9              # body top-y
BW      = 28             # body width
BH      = 38             # body height
BCX     = CX             # 24
BCY     = BY + BH // 2   # 28

# goggles
GB_Y    = BY + 9         # goggle-bar centre-y  (18)
EYE_R   = 5              # outer goggle radius
EYE_SEP = 6              # half-distance between eye centres
EL_CX   = BCX - EYE_SEP # 18
ER_CX   = BCX + EYE_SEP # 30

# headphone cups
CUP_Y   = BY + 5         # cup centre-y
CUP_RX  = 4              # cup x-radius
CUP_RY  = 5              # cup y-radius

BAR_COUNT = 5


class FloatingWidget(QWidget):
    status_changed = pyqtSignal(str)
    level_changed  = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self.current_status   = "ready"
        self.audio_level      = 0.0
        self.live_text        = ""
        self.profile_name     = ""
        self.current_language = ""
        self.language_code    = ""

        self._pulse      = 0.0
        self._pulse_dir  = 1
        self._bars       = [0.0] * BAR_COUNT
        self._tick_count = 0
        self._text_offset = 0
        self._blink_tick  = 0
        self._blink_open  = True

        self._setup_window()
        self._centre_screen()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)          # ~30 fps

        # Hidden by default — only shows while hotkey is held (recording)
        self.hide()

    # ── window ────────────────────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
            Qt.Tool | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(W, H)

    def _centre_screen(self):
        geo = QApplication.primaryScreen().availableGeometry()
        self.move(geo.center().x() - W // 2, geo.bottom() - H - 18)

    # ── animation tick ────────────────────────────────────────────────────

    def _tick(self):
        self._tick_count += 1

        if self.current_status == "recording":
            self._pulse += 0.06 * self._pulse_dir
            if self._pulse >= 1.0:  self._pulse_dir = -1
            elif self._pulse <= 0.0: self._pulse_dir = 1
            base = self.audio_level / 100.0
            for i in range(BAR_COUNT):
                t = base * (0.25 + random.random() * 0.75)
                self._bars[i] += (t - self._bars[i]) * 0.4
        else:
            self._pulse = max(0.0, self._pulse - 0.06)
            for i in range(BAR_COUNT):
                self._bars[i] *= 0.78

        # blink: open ~3 s, closed ~2 frames
        self._blink_tick += 1
        if self._blink_open and self._blink_tick > 95:
            self._blink_open = False
            self._blink_tick = 0
        elif not self._blink_open and self._blink_tick > 3:
            self._blink_open = True
            self._blink_tick = 0

        if self.live_text:
            self._text_offset = (self._text_offset + 1) % max(1, len(self.live_text) * 7)

        self.update()

    # ── paint dispatcher ──────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        self._draw_glow(p)
        self._draw_hp_band(p)
        self._draw_body(p)
        self._draw_overalls(p)
        self._draw_arms(p)
        self._draw_goggle_bar(p)
        self._draw_eyes(p)
        self._draw_mouth(p)
        self._draw_hp_cups(p)
        self._draw_waveform(p)
        self._draw_status(p)
        self._draw_live_text(p)
        self._draw_badges(p)

    # ── glow ──────────────────────────────────────────────────────────────

    def _draw_glow(self, p: QPainter):
        if self._pulse <= 0:
            return
        col = (QColor(255, 70, 70) if self.current_status == "recording"
               else QColor(255, 175, 0))
        r   = int(BW // 2 + 4 + 8 * self._pulse)
        col.setAlpha(int(100 * (1 - self._pulse)))
        p.setPen(QPen(col, 2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPoint(BCX, BCY), r, r)

    # ── headphone band ────────────────────────────────────────────────────

    def _draw_hp_band(self, p: QPainter):
        p.setPen(QPen(QColor(45, 45, 50), 2, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(BCX - 13, BY - 6, 26, 20), 0, 180 * 16)

    # ── pill body ─────────────────────────────────────────────────────────

    def _draw_body(self, p: QPainter):
        if self.current_status == "recording":
            top, bot = QColor(255, 212, 0), QColor(228, 158, 0)
        elif self.current_status == "processing":
            top, bot = QColor(255, 222, 50), QColor(218, 168, 0)
        else:
            top, bot = QColor(255, 218, 8), QColor(218, 162, 0)

        g = QLinearGradient(BCX - BW//2, BY, BCX + BW//2, BY + BH)
        g.setColorAt(0, top); g.setColorAt(1, bot)

        p.setPen(QPen(QColor(170, 115, 0), 1.2))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(BCX - BW//2, BY, BW, BH, BW//2, BW//2)

        # left-side highlight
        hi = QLinearGradient(BCX - BW//2, BY, BCX - BW//2 + 10, BY)
        hi.setColorAt(0, QColor(255, 255, 255, 55))
        hi.setColorAt(1, QColor(255, 255, 255, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(hi))
        p.drawRoundedRect(BCX - BW//2 + 2, BY + 5, 9, BH - 10, 4, 4)

    # ── overalls ──────────────────────────────────────────────────────────

    def _draw_overalls(self, p: QPainter):
        ov_top = BCY + 8
        ov_bot = BY + BH
        ol     = BCX - BW//2 + 2
        or_    = BCX + BW//2 - 2
        r      = BW//2 - 2

        # denim fill clipped to lower pill shape
        path = QPainterPath()
        path.moveTo(ol, ov_top)
        path.lineTo(or_, ov_top)
        path.arcTo(QRectF(or_ - r, ov_bot - r, r, r), 0, -90)
        path.lineTo(ol + r//2, ov_bot)
        path.arcTo(QRectF(ol, ov_bot - r, r, r), -90, -90)
        path.closeSubpath()

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(78, 98, 138))
        p.drawPath(path)

        # pocket
        pw, ph = 14, 9
        p.setPen(QPen(QColor(58, 78, 118), 1))
        p.setBrush(QColor(68, 88, 128))
        p.drawRoundedRect(BCX - pw//2, ov_top + 6, pw, ph, 2, 2)

        # shoulder straps
        p.setPen(QPen(QColor(68, 88, 128), 3, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(BCX - 10, ov_top, BCX - 13, ov_top - 10)
        p.drawLine(BCX + 10, ov_top, BCX + 13, ov_top - 10)

    # ── arms ──────────────────────────────────────────────────────────────

    def _draw_arms(self, p: QPainter):
        ay = BCY + 6
        p.setPen(QPen(QColor(205, 155, 0), 2, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(BCX - BW//2 + 1, ay, BCX - BW//2 - 3, ay + 4)
        p.drawLine(BCX + BW//2 - 1, ay, BCX + BW//2 + 3, ay + 4)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(55, 30, 8))
        p.drawEllipse(QPoint(BCX - BW//2 - 3, ay + 4), 2, 2)
        p.drawEllipse(QPoint(BCX + BW//2 + 3, ay + 4), 2, 2)

    # ── goggle bar ────────────────────────────────────────────────────────

    def _draw_goggle_bar(self, p: QPainter):
        # connecting bridge
        p.setPen(QPen(QColor(130, 130, 140), 2, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(EL_CX + EYE_R - 1, GB_Y, ER_CX - EYE_R + 1, GB_Y)

        # goggle rings
        for cx in (EL_CX, ER_CX):
            p.setPen(QPen(QColor(45, 45, 50), 2))
            p.setBrush(QColor(238, 244, 255))
            p.drawEllipse(QPoint(cx, GB_Y), EYE_R, EYE_R)

    # ── eyes ──────────────────────────────────────────────────────────────

    def _draw_eyes(self, p: QPainter):
        iris = (QColor(195, 35, 35) if self.current_status == "recording"
                else QColor(195, 125, 0) if self.current_status == "processing"
                else QColor(35, 85, 210))

        for cx in (EL_CX, ER_CX):
            if self._blink_open:
                p.setPen(Qt.NoPen)
                p.setBrush(iris)
                p.drawEllipse(QPoint(cx, GB_Y), 5, 5)
                p.setBrush(QColor(8, 8, 8))
                p.drawEllipse(QPoint(cx, GB_Y), 2, 2)
                p.setBrush(QColor(255, 255, 255, 210))
                p.drawEllipse(QPoint(cx + 2, GB_Y - 2), 1, 1)
            else:
                p.setPen(QPen(QColor(45, 45, 50), 1.5,
                              Qt.SolidLine, Qt.RoundCap))
                p.drawLine(cx - 5, GB_Y, cx + 5, GB_Y)

    # ── mouth ─────────────────────────────────────────────────────────────

    def _draw_mouth(self, p: QPainter):
        my = GB_Y + EYE_R + 8
        p.setPen(QPen(QColor(75, 35, 0), 1.2, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)

        if self.current_status == "recording":
            p.setBrush(QColor(55, 15, 0))
            p.drawEllipse(QPoint(BCX, my), 5, 4)
        elif self.current_status == "processing":
            # flat line with slight upturn
            p.drawArc(QRectF(BCX - 6, my - 2, 12, 6), 0, -180 * 16)
        else:
            # wide smile
            p.drawArc(QRectF(BCX - 7, my - 3, 14, 8), 0, -180 * 16)

    # ── headphone ear cups ────────────────────────────────────────────────

    def _draw_hp_cups(self, p: QPainter):
        if self.current_status == "recording":
            outer, inner = QColor(215, 45, 45), QColor(255, 95, 95)
        elif self.current_status == "processing":
            outer, inner = QColor(195, 115, 0), QColor(255, 175, 45)
        else:
            outer, inner = QColor(175, 35, 35), QColor(215, 75, 75)

        for cx in (BCX - BW//2 - 3, BCX + BW//2 + 3):
            p.setPen(QPen(QColor(38, 38, 42), 1))
            p.setBrush(outer)
            p.drawEllipse(QPoint(cx, CUP_Y), CUP_RX, CUP_RY)
            p.setPen(Qt.NoPen)
            p.setBrush(inner)
            p.drawEllipse(QPoint(cx, CUP_Y), CUP_RX - 3, CUP_RY - 3)

    # ── waveform ──────────────────────────────────────────────────────────

    def _draw_waveform(self, p: QPainter):
        bw, gap = 3, 2
        total   = BAR_COUNT * bw + (BAR_COUNT - 1) * gap
        x0      = BCX - total // 2
        base_y  = BY + BH + 3   # tight under body
        max_h   = 8

        for i, lv in enumerate(self._bars):
            bh = max(2, int(lv * max_h))
            x  = x0 + i * (bw + gap)
            y  = base_y + (max_h - bh)

            if self.current_status == "recording":
                col = QColor(255, 75 + int(85 * lv), 55,
                             195 + int(60 * lv))
            elif self.current_status == "processing":
                col = QColor(255, 168, 0, 175)
            else:
                col = QColor(115, 115, 145, 125)

            p.setPen(Qt.NoPen)
            p.setBrush(col)
            p.drawRoundedRect(x, y, bw, bh, 1, 1)

    # ── status label — removed (no text below body) ──────────────────────

    def _draw_status(self, p: QPainter):
        pass   # intentionally empty — no text label shown

    # ── live text ticker ──────────────────────────────────────────────────

    def _draw_live_text(self, p: QPainter):
        if not self.live_text:
            return
        p.setPen(QColor(215, 215, 250, 185))
        p.setFont(QFont("Arial", 4))
        fm = QFontMetrics(p.font())
        tw = fm.horizontalAdvance(self.live_text)
        x  = W - (self._text_offset % (tw + W))
        p.setClipRect(0, H - 10, W, 9)
        p.drawText(x, H - 2, self.live_text)
        p.setClipping(False)

    # ── micro badges ──────────────────────────────────────────────────────

    def _draw_badges(self, p: QPainter):
        p.setFont(QFont("Arial", 4, QFont.Bold))
        p.setPen(Qt.NoPen)

        if self.language_code:
            p.setBrush(QColor(155, 55, 55, 205))
            p.drawRoundedRect(1, 1, 18, 8, 2, 2)
            p.setPen(QColor(255, 205, 205))
            p.drawText(1, 1, 18, 8, Qt.AlignCenter,
                       self.language_code.upper()[:3])

        if self.profile_name:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(55, 55, 155, 205))
            p.drawRoundedRect(W - 19, 1, 18, 8, 2, 2)
            p.setPen(QColor(205, 205, 255))
            p.drawText(W - 19, 1, 18, 8, Qt.AlignCenter,
                       self.profile_name[:4])

    # ── public API ────────────────────────────────────────────────────────

    def set_recording(self, is_recording: bool):
        if is_recording:
            self.current_status = "recording"
            self.show()          # Pop up when hotkey pressed
        else:
            self.current_status = "ready"
            self.live_text = ""
            self.hide()          # Disappear immediately on release
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
            self.live_text = ""
            self.hide()
        self.update()

    def set_audio_level(self, level: float):
        self.audio_level = level

    def set_live_text(self, text: str):
        self.live_text    = text
        self._text_offset = 0

    def set_profile(self, name: str):
        self.profile_name = name
        self.update()

    def set_language(self, language_name: str, language_code: str):
        self.current_language = language_name
        self.language_code    = language_code
        self.update()

    def set_theme(self, theme: str = "dark"):
        pass   # colours driven by status

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
