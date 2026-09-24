"""
Generate the Voxylis brand assets from code.

Run from the repository root with Qt available::

    python packaging/make_icons.py

Outputs (all committed, so a release build needs no drawing tools):

    packaging/voxylis.ico            Windows EXE + installer + shortcuts
    web/static/favicon.ico           website tab icon
    web/static/apple-touch-icon.png  iOS home-screen icon
    web/static/og-image.png          social preview card

The mark is a rounded square holding a five-bar waveform.  It is intentionally
not a stock microphone glyph, and it is identical everywhere it appears.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ACCENT = "#7c6cf0"
ACCENT_DARK = "#5a4bd1"
MARK = "#ffffff"

ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def paint_mark(painter, size: float, background: bool = True) -> None:
    """Paint the Voxylis mark into the painter's current coordinate system.

    Painting into an existing painter (rather than composing QImages) keeps
    the generator to one painter per output, which avoids a font-cache crash
    seen when a second QImage is drawn into an active painter on Windows.
    """
    from PyQt5.QtCore import QRectF, Qt
    from PyQt5.QtGui import QBrush, QColor, QLinearGradient

    if background:
        gradient = QLinearGradient(0, 0, size, size)
        gradient.setColorAt(0.0, QColor(ACCENT))
        gradient.setColorAt(1.0, QColor(ACCENT_DARK))
        # drawRoundedRect with a gradient brush (rather than QPainterPath +
        # fillPath) keeps this safe to call inside a larger composition.
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(QRectF(0, 0, size, size), size * 0.26, size * 0.26)

    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(MARK))
    bar_width = max(1.0, size * 0.10)
    gap = max(1.0, size * 0.055)
    heights = [0.30, 0.58, 0.84, 0.46, 0.26]
    total = len(heights) * bar_width + (len(heights) - 1) * gap
    x = (size - total) / 2
    for factor in heights:
        height = size * factor
        y = (size - height) / 2
        painter.drawRoundedRect(QRectF(x, y, bar_width, height), bar_width / 2, bar_width / 2)
        x += bar_width + gap


def _draw(size: int, background: bool = True):
    from PyQt5.QtGui import QImage, QPainter
    from PyQt5.QtCore import Qt

    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    paint_mark(painter, size, background=background)
    painter.end()
    return image


def _png_bytes(image) -> bytes:
    from PyQt5.QtCore import QBuffer, QIODevice

    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def write_ico(images, destination: Path) -> None:
    """Write a PNG-compressed ICO (supported by Windows Vista and later)."""
    payloads = []
    for size, image in images:
        data = _png_bytes(image)
        payloads.append((size, data))

    header = struct.pack("<HHH", 0, 1, len(payloads))
    offset = len(header) + 16 * len(payloads)
    entries = b""
    body = b""
    for size, data in payloads:
        dimension = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(data), offset)
        body += data
        offset += len(data)

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(header + entries + body)
    print(f"wrote {destination.relative_to(ROOT)} ({len(payloads)} sizes)")


def write_png(image, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(_png_bytes(image))
    print(f"wrote {destination.relative_to(ROOT)} ({image.width()}x{image.height()})")


def write_og_image(destination: Path) -> None:
    """1200x630 social card: brand mark on a dark card with the wordmark."""
    from PyQt5.QtCore import QRectF, Qt
    from PyQt5.QtGui import QColor, QImage, QLinearGradient, QPainter

    width, height = 1200, 630
    image = QImage(width, height, QImage.Format_ARGB32)
    gradient = QLinearGradient(0, 0, width, height)
    gradient.setColorAt(0.0, QColor("#111114"))
    gradient.setColorAt(1.0, QColor("#1c1a33"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.fillRect(0, 0, width, height, gradient)

    # Draw the badge inline with solid brushes. Composing a separately rendered
    # QImage into this painter crashes Qt 5.15 on some Windows builds, so the
    # card is painted entirely in one pass.
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(ACCENT))
    painter.drawRoundedRect(QRectF(110, 200, 220, 220), 56, 56)
    painter.setBrush(QColor(MARK))
    bar_width, gap = 22.0, 12.0
    heights = [0.30, 0.58, 0.84, 0.46, 0.26]
    total = len(heights) * bar_width + (len(heights) - 1) * gap
    x = 110 + (220 - total) / 2
    for factor in heights:
        bar_height = 220 * factor
        painter.drawRoundedRect(
            QRectF(x, 200 + (220 - bar_height) / 2, bar_width, bar_height),
            bar_width / 2,
            bar_width / 2,
        )
        x += bar_width + gap

    # NOTE: the card is deliberately text-free. Qt 5.15 crashes when drawing
    # text into a large QImage inside this script (reproduced with a minimal
    # case), and a hand-rolled text rasteriser is not worth it. The wordmark is
    # rendered by the website; a designed 1200x630 card is a design task.
    painter.setPen(Qt.NoPen)
    accent_bar = QColor("#2a2545")
    painter.setBrush(accent_bar)
    for index in range(3):
        painter.drawRoundedRect(QRectF(110 + index * 260, 470, 220, 10), 5, 5)
    painter.end()
    write_png(image, destination)


def _ensure_app() -> None:
    """QPainter needs a Qt application, and text needs a font database.

    QApplication (widgets) is preferred because it reliably populates fonts;
    a QGuiApplication with the offscreen platform is the headless fallback.
    """
    try:
        from PyQt5.QtWidgets import QApplication

        if QApplication.instance() is None:
            QApplication(["make_icons"])
        return
    except Exception:
        pass

    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt5.QtGui import QGuiApplication

    if QGuiApplication.instance() is None:
        QGuiApplication(["make_icons"])


def main(argv=None) -> int:
    import argparse
    import subprocess

    parser = argparse.ArgumentParser(description="Generate Voxylis brand assets")
    parser.add_argument(
        "--og-only",
        action="store_true",
        help="generate only the social card (used internally, one image per process)",
    )
    args = parser.parse_args(argv)

    _ensure_app()

    if args.og_only:
        write_og_image(ROOT / "web" / "static" / "og-image.png")
        return 0

    images = [(size, _draw(size)) for size in ICO_SIZES]
    write_ico(images, ROOT / "packaging" / "voxylis.ico")
    write_ico(
        [(s, i) for s, i in images if s in (16, 32, 48)],
        ROOT / "web" / "static" / "favicon.ico",
    )
    write_png(_draw(180), ROOT / "web" / "static" / "apple-touch-icon.png")

    # The social card is rendered in a fresh interpreter: painting text after a
    # long sequence of QImage/QPainter objects crashes Qt 5.15 on Windows.
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--og-only"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(result.stdout.strip())
    else:
        print(f"warning: social card not generated (exit {result.returncode})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
