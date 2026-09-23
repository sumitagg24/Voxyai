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
    # Web (the desktop app can serve the dashboard locally)
    "flask",
    "flask_cors",
    "flask_caching",
    # Config / env
    "dotenv",
    "requests",
    # Optional secure credential storage (falls back to DPAPI)
    "keyring",
    "keyring.backends.Windows",
    "keyring.backends.SecretService",
    "keyring.backends.macOS",
    # AI lazy imports
    "ai.transcriber",
    "ai.enhancer",
    "ai.language_detector",
    "ai.prompt_templates",
    # Project modules (ensure collected)
    "config.version",
    "core.app_orchestrator",
    "core.errors",
    "core.event_manager",
    "core.voice_commands",
    "core.history_manager",
    "core.history_store",
    "core.sound_feedback",
    "core.stats_tracker",
    "core.per_app_profiles",
    "core.startup_manager",
    "core.command_processor",
    "core.user_manager",
    "core.updater",
    "audio.recorder",
    "audio.audio_utils",
    "audio.noise_canceller",
    "system.injector",
    "system.clipboard_manager",
    # Desktop shell
    "ui.main_window",
    "ui.pages",
    "ui.overlay",
    "ui.onboarding_window",
    "ui.custom_modes_window",
    "ui.auth0_dialog",
    "ui.shortcut_recorder",
    "ui.error_dialog",
    "ui.diagnostics",
    "ui.theme",
    "utils.paths",
    "utils.credentials",
    "utils.helpers",
    "utils.logger",
    "config.constants",
]

# ── Data files ──────────────────────────────────────────────────────────────
# (source, dest) tuples.
#
# IMPORTANT: settings.json is NOT bundled. The frozen app resolves all mutable
# state through utils.paths (%LOCALAPPDATA%\Voxylis), and shipping a settings
# file inside the bundle would recreate the "write into Program Files" bug.
# Only read-only defaults and web assets travel with the build.
datas = [
    (os.path.join(project_root, "config", "settings.example.json"), "config"),
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
    icon=os.path.join(project_root, "packaging", "voxylis.ico"),
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
