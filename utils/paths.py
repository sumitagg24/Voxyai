"""
Filesystem layout for Voxylis.

Hard rule
---------
The directory that contains the executable (and PyInstaller's ``_internal``)
is **program files**: read-only during normal operation.  Nothing that the user
can change at runtime may ever be written there, because on Windows the install
directory is commonly ``C:\\Program Files\\Voxylis`` (needs elevation, wiped on
upgrade/reinstall).

Everything mutable lives under a single user-data root:

    Windows  %LOCALAPPDATA%\\Voxylis        (default; per-user, machine-local)
    macOS    ~/Library/Application Support/Voxylis
    Linux    $XDG_DATA_HOME/voxylis  or  ~/.local/share/voxylis

Why LOCALAPPDATA and not APPDATA (Roaming)?
    User data is mostly cache-shaped (SQLite history, logs, temp audio, update
    packages, downloaded models).  Roaming profiles are synced by domain policy
    and would push megabytes of transcripts and a WAL-mode database over the
    wire on every logon.  We therefore keep everything under LOCALAPPDATA and
    document it as the single deliberate choice.

Layout::

    %LOCALAPPDATA%\\Voxylis\\
        config/        settings.json (non-secret), onboarding.json
        data/          history.sqlite3, stats.json
        secrets/       credentials.vault (DPAPI-encrypted, user scope)
        logs/          voxylis.log (rotated)
        cache/         transient caches
        models/        downloaded local models (optional)
        temp/          temporary audio (deleted after each pipeline run)
        updates/       downloaded installers awaiting apply
        crashes/       crash reports (opt-in, redacted)

An optional ``VOXYLIS_HOME`` environment variable overrides the whole root,
which is what tests and portable installs use.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

APP_DIR_NAME = "Voxylis"

CONFIG_DIR = "config"
DATA_DIR = "data"
SECRETS_DIR = "secrets"
LOGS_DIR = "logs"
CACHE_DIR = "cache"
MODELS_DIR = "models"
TEMP_DIR = "temp"
UPDATES_DIR = "updates"
CRASH_DIR = "crashes"

HISTORY_DB_NAME = "history.sqlite3"
SETTINGS_NAME = "settings.json"
ONBOARDING_NAME = "onboarding.json"
STATS_NAME = "stats.json"
LOG_NAME = "voxylis.log"
VAULT_NAME = "credentials.vault"


def is_frozen() -> bool:
    """True when running from a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False))


def program_dir() -> Path:
    """Directory holding the executable (frozen) or the repository root."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def bundled_dir() -> Path:
    """Directory holding read-only bundled assets.

    PyInstaller >= 6 puts collected data in ``_internal`` next to the exe.
    """
    if is_frozen():
        candidate = program_dir() / "_internal"
        if candidate.is_dir():
            return candidate
        return program_dir()
    return program_dir()


def _env_override() -> Optional[Path]:
    raw = os.environ.get("VOXYLIS_HOME", "").strip()
    if raw:
        return Path(raw).expanduser()
    return None


def user_data_root() -> Path:
    """Root of all mutable Voxylis state."""
    override = _env_override()
    if override is not None:
        return override

    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_DIR_NAME
        return Path.home() / "AppData" / "Local" / APP_DIR_NAME

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME

    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg:
        return Path(xdg) / APP_DIR_NAME.lower()
    return Path.home() / ".local" / "share" / APP_DIR_NAME.lower()


def _dir(name: str) -> Path:
    path = user_data_root() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_dir() -> Path:
    return _dir(CONFIG_DIR)


def data_dir() -> Path:
    return _dir(DATA_DIR)


def secrets_dir() -> Path:
    return _dir(SECRETS_DIR)


def logs_dir() -> Path:
    return _dir(LOGS_DIR)


def cache_dir() -> Path:
    return _dir(CACHE_DIR)


def models_dir() -> Path:
    return _dir(MODELS_DIR)


def temp_dir() -> Path:
    path = _dir(TEMP_DIR)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


def updates_dir() -> Path:
    return _dir(UPDATES_DIR)


def crash_dir() -> Path:
    return _dir(CRASH_DIR)


def settings_path() -> Path:
    return config_dir() / SETTINGS_NAME


def onboarding_path() -> Path:
    return config_dir() / ONBOARDING_NAME


def stats_path() -> Path:
    return data_dir() / STATS_NAME


def history_db_path() -> Path:
    return data_dir() / HISTORY_DB_NAME


def log_path() -> Path:
    return logs_dir() / LOG_NAME


def vault_path() -> Path:
    return secrets_dir() / VAULT_NAME


def bundled_config_dir() -> Path:
    """Read-only config shipped with the app (used as a seed / defaults)."""
    return bundled_dir() / "config"


def ensure_directories() -> dict:
    """Create every user-data directory. Returns a name -> path mapping."""
    return {
        "root": user_data_root(),
        CONFIG_DIR: config_dir(),
        DATA_DIR: data_dir(),
        SECRETS_DIR: secrets_dir(),
        LOGS_DIR: logs_dir(),
        CACHE_DIR: cache_dir(),
        MODELS_DIR: models_dir(),
        TEMP_DIR: temp_dir(),
        UPDATES_DIR: updates_dir(),
    }


def legacy_roots() -> list:
    """Locations that older Voxylis builds used for user data.

    Used only by :func:`migrate_legacy_data` so existing users keep their
    settings, history and stats after this change.  Never written to.
    """
    roots = []
    pd = program_dir()
    roots.append(pd)
    if is_frozen():
        internal = pd / "_internal"
        if internal.is_dir():
            roots.append(internal)
    # Old builds resolved data relative to CWD, which was usually the repo root.
    try:
        roots.append(Path.cwd())
    except OSError:
        pass
    unique = []
    for root in roots:
        resolved = root.resolve()
        if resolved != user_data_root().resolve() and resolved not in unique:
            unique.append(resolved)
    return unique


_MIGRATION_LOG: list = []


def migrate_legacy_data(force: bool = False) -> list:
    """Copy legacy install-directory data into the user-data root.

    Non-destructive: files are copied, never moved or deleted, and an existing
    file at the destination always wins.  Returns a list of
    ``(source, destination)`` pairs that were copied.
    """
    copied = []
    plan = [
        (Path("config") / SETTINGS_NAME, settings_path()),
        (Path("config") / ONBOARDING_NAME, onboarding_path()),
        (Path("config") / "users.json", config_dir() / "users.legacy.json"),
        (Path("config") / "sessions.json", config_dir() / "sessions.legacy.json"),
        (Path("logs") / "transcription_history.json", data_dir() / "history.legacy.json"),
        (Path("logs") / STATS_NAME, stats_path()),
    ]

    for legacy_root in legacy_roots():
        for relative, destination in plan:
            source = legacy_root / relative
            if not source.is_file():
                continue
            if destination.exists() and not force:
                continue
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(source.read_bytes())
                copied.append((str(source), str(destination)))
            except OSError:
                continue

    _MIGRATION_LOG.extend(copied)
    return copied


def migrate_legacy_logs() -> list:
    """Move legacy log files into the user-data logs directory (best effort)."""
    copied = []
    for legacy_root in legacy_roots():
        source = legacy_root / "logs" / LOG_NAME
        destination = log_path()
        if not source.is_file() or destination.exists():
            continue
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
            copied.append((str(source), str(destination)))
        except OSError:
            continue
    return copied


def describe_paths() -> dict:
    """Redacted path map for diagnostics."""
    return {
        "user_data_root": str(user_data_root()),
        "program_dir": str(program_dir()),
        "config_dir": str(config_dir()),
        "data_dir": str(data_dir()),
        "logs_dir": str(logs_dir()),
        "frozen": is_frozen(),
        "path_override": bool(_env_override()),
    }
