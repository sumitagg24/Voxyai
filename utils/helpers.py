"""
Helper utilities for Voxylis
"""

import json
import os
import sys
from typing import Any, Dict
from config.constants import CONFIG_DIR


def get_base_dir() -> str:
    """Return the base directory for data files.

    When frozen by PyInstaller, sys.executable points to the exe and
    bundled source lives in a _internal/ subdir.  We want config/, logs/,
    temp/ to live next to the exe so they persist across runs, but for
    reading bundled assets we look inside _internal/.
    """
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        internal_dir = os.path.join(exe_dir, "_internal")
        if os.path.isdir(internal_dir):
            return internal_dir
        return exe_dir
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(filepath: str) -> Dict[str, Any]:
    """Load JSON file safely"""
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def save_json(filepath: str, data: Dict[str, Any]) -> bool:
    """Save JSON file safely"""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving JSON: {e}")
        return False


def ensure_directories():
    """Ensure all required directories exist next to the exe / project root."""
    base = get_base_dir()
    directories = [os.path.join(base, CONFIG_DIR), os.path.join(base, "temp"), os.path.join(base, "logs")]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)


def format_duration(seconds: float) -> str:
    """Format duration in seconds to readable format"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60
    return f"{minutes:.1f}m"


def sanitize_filename(filename: str) -> str:
    """Remove invalid characters from filename"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, "_")
    return filename


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to max length with ellipsis"""
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text
