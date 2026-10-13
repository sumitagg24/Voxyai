"""
Generate the Voxylis Windows app icon from code.

Run from the repository root with Qt available::

    python packaging/make_icons.py

Output (committed, so a release build needs no drawing tools):

    packaging/voxylis.ico            Windows EXE + installer + shortcuts

The mark is drawn from :mod:`config.brand` — the same 32-unit grid and
palette as the website's nav logo and favicon — so the installed app,
the window/tray icon and the website all show one identical logo. The
website's own binaries (web/static/favicon.ico, apple-touch-icon.png,
og-image.png) are canonical committed assets maintained with the site
and are deliberately NOT rewritten here.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import brand  # noqa: E402  (path set up above)

ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def paint_mark(painter, size: float) -> None:
    """Paint the Voxylis brand mark into the painter's coordinate system.

    Painting into an existing painter (rather than composing QImages) keeps
    the generator to one painter per output, which avoids a font-cache crash
    seen when a second QImage is drawn into an active painter on Windows.
    """
    from PyQt5.QtCore import QRectF, Qt
    from PyQt5.QtGui import QBrush, QColor

    k = size / brand.GRID
    painter.setPen(Qt.NoPen)

    painter.setBrush(QBrush(QColor(brand.TILE)))
    painter.drawRoundedRect(
        QRectF(brand.TILE_X * k, brand.TILE_Y * k, brand.TILE_SIZE * k, brand.TILE_SIZE * k),
        brand.TILE_RADIUS * k,
        brand.TILE_RADIUS * k,
    )
    for index, (x, top, width, height) in enumerate(brand.BARS):
        painter.setBrush(QBrush(QColor(brand.SIGNAL if index == brand.SIGNAL_BAR_INDEX else brand.BAR)))
        painter.drawRoundedRect(QRectF(x * k, top * k, width * k, height * k), k, k)


def _draw(size: int):
    """Render the mark at `size` via Qt, falling back to Pillow.

    Qt is the canonical renderer (the Windows build runner always has it).
    The Pillow fallback keeps the generator usable in headless environments
    where Qt cannot load (no libGL), drawing the same geometry 8x
    supersampled and downscaling for equivalent antialiasing.
    """
    try:
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QImage, QPainter
    except Exception:
        return _draw_pillow(size)

    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    paint_mark(painter, size)
    painter.end()
    return image


def _draw_pillow(size: int):
    from PIL import Image, ImageDraw

    ss = 8
    canvas = Image.new("RGBA", (size * ss, size * ss), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    k = size * ss / brand.GRID

    def box(x, top, w, h):
        return [x * k, top * k, (x + w) * k, (top + h) * k]

    draw.rounded_rectangle(
        box(brand.TILE_X, brand.TILE_Y, brand.TILE_SIZE, brand.TILE_SIZE),
        radius=brand.TILE_RADIUS * k,
        fill=brand.TILE,
    )
    for index, (x, top, width, height) in enumerate(brand.BARS):
        colour = brand.SIGNAL if index == brand.SIGNAL_BAR_INDEX else brand.BAR
        draw.rounded_rectangle(box(x, top, width, height), radius=k, fill=colour)
    return canvas.resize((size, size), Image.LANCZOS)


def _png_bytes(image) -> bytes:
    from io import BytesIO

    buffer = BytesIO()
    image.save(buffer, "PNG")
    return bytes(buffer.getvalue())


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


def _ensure_app() -> None:
    """QPainter needs a Qt application; a no-op when Qt is unavailable
    (the Pillow fallback in _draw needs no application object)."""
    try:
        from PyQt5.QtWidgets import QApplication
    except Exception:
        return

    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if QApplication.instance() is None:
        QApplication(["make_icons"])


def main(argv=None) -> int:
    _ensure_app()
    images = [(size, _draw(size)) for size in ICO_SIZES]
    write_ico(images, ROOT / "packaging" / "voxylis.ico")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
