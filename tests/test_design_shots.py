"""
Smoke test for the hidden ``--design-shots`` dev flag (main.py).

Runs the flag end-to-end in an offscreen Qt session and asserts that every
surface produced a PNG. Skips gracefully when PyQt5 is unavailable (CI).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt5.QtWidgets", reason="PyQt5 is required for the desktop app")

EXPECTED_SHOTS = [
    "page_home.png",
    "page_history.png",
    "page_microphone.png",
    "page_ai.png",
    "page_shortcuts.png",
    "page_privacy.png",
    "page_account.png",
    "page_diagnostics.png",
    "page_about.png",
    "onboarding.png",
    "overlay_idle.png",
    "overlay_recording.png",
]


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def test_design_shots_produces_pngs(tmp_path):
    """Running `main.py --design-shots <dir>` renders every surface to PNG."""
    root = _project_root()
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONDONTWRITEBYTECODE": "1"}
    if sys.platform == "win32":
        # Offscreen on Windows rasterises text only with a font directory hint.
        env.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
    result = subprocess.run(
        [sys.executable, str(root / "main.py"), "--design-shots", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )
    assert result.returncode == 0, f"design-shots failed:\n{result.stdout}\n{result.stderr}"

    saved = sorted(p.name for p in tmp_path.glob("*.png"))
    missing = [name for name in EXPECTED_SHOTS if name not in saved]
    assert not missing, f"missing design shots: {missing}"
    for name in EXPECTED_SHOTS:
        assert (tmp_path / name).stat().st_size > 0, f"{name} is empty"
