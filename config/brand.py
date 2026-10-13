"""Voxylis brand mark — single source of truth for the app icon.

The mark is identical everywhere it appears (website nav, favicon,
Windows installer/EXE, window title bar, tray): a rounded ink tile
holding five vertical bars whose outer edges align on one baseline — a
voice signal coming to rest — with the centre bar in signal orange.

Geometry lives on the same 32-unit grid as the website's SVG mark
(``viewBox="0 0 32 32"``), so every surface is a direct scaling of one
design.  Colors are fixed brand constants, NOT theme tokens: the mark
looks the same in the light and dark themes, exactly like the favicon.

Pure data on purpose — importable from the server (no Qt dependency).
"""

from __future__ import annotations

# Palette (hex RGB).
TILE = "#171512"  # ink tile
BAR = "#f4f1ea"  # paper bars
SIGNAL = "#e04b26"  # centre bar

# 32-unit grid: tile rect + corner radius (matches the website SVG).
GRID = 32
TILE_X = 1.0
TILE_Y = 1.0
TILE_SIZE = 30.0
TILE_RADIUS = 5.0

# Bars as (x, top, width, height) on the 32-unit grid.
BARS = (
    (6.2, 13.0, 3.4, 13.0),
    (11.1, 18.0, 3.4, 8.0),
    (16.0, 22.0, 3.4, 4.0),
    (20.9, 18.0, 3.4, 8.0),
    (25.8, 13.0, 3.4, 13.0),
)
#: Index into BARS painted in SIGNAL.
SIGNAL_BAR_INDEX = 2
