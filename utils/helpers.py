"""
Helper utilities for Voxylis.

Writable state resolution lives in :mod:`utils.paths`.  ``get_base_dir()`` is
kept as the legacy entry point but now returns the **user-data root** rather
than the install directory, so every module that used to write next to the exe
automatically stops doing so.
"""

import json
import os
import tempfile
from typing import Any, Dict

from utils import paths


def get_base_dir() -> str:
    """Return the writable user-data root (``%LOCALAPPDATA%\\Voxylis``).

    Historically this returned the program/install directory, which meant the
    app wrote settings and history into ``C:\\Program Files``.  Program files
    must stay immutable, so the contract is now "the one writable root".
    """
    return str(paths.user_data_root())


def get_program_dir() -> str:
    """Return the read-only program directory (install dir when frozen)."""
    return str(paths.program_dir())


def get_bundled_dir() -> str:
    """Return the directory holding bundled, read-only assets."""
    return str(paths.bundled_dir())


def load_json(filepath: str) -> Dict[str, Any]:
    """Load a JSON file, returning ``{}`` for missing or malformed input."""
    try:
        with open(filepath, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}


def save_json(filepath: str, data: Dict[str, Any]) -> bool:
    """Atomically save a JSON file with restrictive permissions."""
    try:
        directory = os.path.dirname(os.path.abspath(filepath))
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
            os.replace(tmp, filepath)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return True
    except OSError as exc:
        from utils.logger import log_error

        log_error(f"Error saving JSON to {filepath}: {exc}")
        return False


def ensure_directories() -> Dict[str, str]:
    """Create the user-data tree and migrate legacy install-dir data once."""
    created = paths.ensure_directories()
    marker = paths.user_data_root() / ".migrated"
    if not marker.exists():
        copied = paths.migrate_legacy_data()
        paths.migrate_legacy_logs()
        try:
            marker.write_text("1\n", encoding="utf-8")
        except OSError:
            pass
        if copied:
            from utils.logger import log_info

            log_info(f"Migrated {len(copied)} legacy data file(s) into {paths.user_data_root()}")
    return {key: str(value) for key, value in created.items()}


def format_duration(seconds: float) -> str:
    """Format duration in seconds to a readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{seconds / 60:.1f}m"


def sanitize_filename(filename: str) -> str:
    """Remove characters that are invalid in Windows filenames."""
    for char in '<>:"/\\|?*':
        filename = filename.replace(char, "_")
    return filename


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to max_length with an ellipsis."""
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text
