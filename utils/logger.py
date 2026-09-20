"""
Logging utility for Voxylis
"""

import logging
import os
from config.constants import LOG_LEVEL, LOG_FILE, LOGS_DIR


def _get_logs_dir() -> str:
    """Return the logs directory, resolving relative to the exe when frozen."""
    try:
        from utils.helpers import get_base_dir
        return os.path.join(get_base_dir(), LOGS_DIR)
    except Exception:
        return LOGS_DIR


class VoxylisLogger:
    """Centralized logging system"""

    _instance = None
    _logger = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize_logger()
        return cls._instance

    def _initialize_logger(self):
        """Initialize the logger with file and console handlers"""
        logs_dir = _get_logs_dir()
        os.makedirs(logs_dir, exist_ok=True)

        self._logger = logging.getLogger("voxylis")
        self._logger.setLevel(getattr(logging, LOG_LEVEL))

        # File handler
        log_path = os.path.join(logs_dir, LOG_FILE)
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(getattr(logging, LOG_LEVEL))

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, LOG_LEVEL))

        # Formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        self._logger.addHandler(file_handler)
        self._logger.addHandler(console_handler)

    def get_logger(self):
        """Get the logger instance"""
        return self._logger


# Global logger instance
logger = VoxylisLogger().get_logger()


def log_info(message):
    """Log info level message"""
    logger.info(message)


def log_error(message, exc_info=False):
    """Log error level message"""
    logger.error(message, exc_info=exc_info)


def log_warning(message):
    """Log warning level message"""
    logger.warning(message)


# Alias for compatibility
def log_warn(message):
    """Log warning level message (alias)"""
    logger.warning(message)


def log_debug(message):
    """Log debug level message"""
    logger.debug(message)
