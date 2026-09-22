# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Voxylis Desktop App
Build: pyinstaller voxylis.spec
"""

import os
import sys

block_cipher = None

project_root = os.path.abspath(SPECPATH)

# ── Hidden imports ──────────────────────────────────────────────────────────
hiddenimports = [
    # PyQt5
    "PyQt5.sip",
    "PyQt5.QtWidgets",
    "PyQt5.QtCore",
    "PyQt5.QtGui",
    # Audio
    "sounddevice",
    "numpy",
    "scipy",
    "scipy.io",
    "scipy.signal",
    # Speech APIs
    "groq",
    "openai",
    # Hotkey / system
    "pynput",
    "pynput.keyboard",
    "pynput.keyboard._win32",
    "pynput._util.win32",
    "keyboard",
    # Clipboard
    "pyperclip",
    "pyperclip.clipboards",
    "pyperclip.backends",
    # Win32 (per-app profiles)
    "win32gui",
    "win32process",
    "psutil",
    # Web
    "flask",
    "flask_cors",
    "flask_caching",
    # Config / env
    "dotenv",
    "requests",
    # AI lazy imports
    "ai.transcriber",
    "ai.enhancer",
    "ai.language_detector",
    "ai.prompt_templates",
    # Project modules (ensure collected)
    "core.app_orchestrator",
    "core.event_manager",
    "core.voice_commands",
    "core.history_manager",
    "core.sound_feedback",
    "core.stats_tracker",
    "core.per_app_profiles",
    "core.startup_manager",
    "core.command_processor",
    "core.user_manager",
    "audio.recorder",
    "audio.audio_utils",
    "audio.noise_canceller",
    "system.injector",
    "system.clipboard_manager",
    "ui.overlay",
    "ui.settings_window",
    "ui.history_window",
    "ui.custom_modes_window",
    "utils.helpers",
    "utils.logger",
    "config.constants",
]

# ── Data files ──────────────────────────────────────────────────────────────
# (source, dest) tuples
datas = [
    (os.path.join(project_root, "config", "settings.json"), "config"),
    (os.path.join(project_root, "web", "static"), "web/static"),
]

# ── Analysis ────────────────────────────────────────────────────────────────
a = Analysis(
    [os.path.join(project_root, "main.py")],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "pillow",
        "test",
        "unittest",
        "xmlrpc",
        "pydoc",
        "pdb",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Voxylis",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,           # no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,               # add .ico here if you have one, e.g. "packaging/voxylis.ico"
    version=os.path.join(project_root, "packaging", "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Voxylis",
)
