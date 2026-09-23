"""
Logging for Voxylis.

Logs live under ``%LOCALAPPDATA%\\Voxylis\\logs`` (never in the install
directory) and rotate, so a long-running desktop app cannot fill the disk.
Secrets are never logged: use :func:`utils.credentials.redact` for anything
that may contain a credential.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from config.constants import LOG_LEVEL, LOG_FILE
from utils import paths

_CONFIGURED = False
_MAX_BYTES = 5 * 1024 * 1024
_BACKUPS = 3


class VoxylisLogger:
    """Centralized logging system (process-wide singleton)."""

    _instance = None
    _logger = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize_logger()
        return cls._instance

    def _initialize_logger(self):
        self._logger = logging.getLogger("voxylis")
        self._logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
        # Never double-attach handlers when the app is reloaded (e.g. tests).
        if self._logger.handlers:
            return

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        try:
            logs_dir = paths.logs_dir()
            os.makedirs(logs_dir, exist_ok=True)
            file_handler = RotatingFileHandler(
                str(logs_dir / LOG_FILE),
                maxBytes=_MAX_BYTES,
                backupCount=_BACKUPS,
                encoding="utf-8",
            )
            file_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
            file_handler.setFormatter(formatter)
            self._logger.addHandler(file_handler)
        except OSError as exc:  # pragma: no cover - read-only environments
            print(f"Voxylis: file logging disabled ({exc})", file=sys.stderr)

        # Console output is only useful in a terminal; the frozen windowed
        # build has no console and would otherwise crash on a broken stdout.
        if sys.stderr is not None and not getattr(sys, "frozen", False):
            console_handler = logging.StreamHandler()
            console_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
            console_handler.setFormatter(formatter)
            self._logger.addHandler(console_handler)

        self._logger.propagate = False

    def get_logger(self):
        return self._logger


def configure_root_logger():
    """Route third-party (werkzeug/flask/urllib3) warnings into our log file."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


logger = VoxylisLogger().get_logger()


def log_info(message):
    logger.info(message)


def log_error(message, exc_info=False):
    logger.error(message, exc_info=exc_info)


def log_warning(message):
    logger.warning(message)


def log_warn(message):
    """Alias kept for backwards compatibility."""
    logger.warning(message)


def log_debug(message):
    logger.debug(message)
