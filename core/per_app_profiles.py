"""
Per-app profiles — automatically switch enhancement mode based on focused window.
Uses Win32 API (Windows only), gracefully skips on other platforms.
"""

import threading
from typing import Optional
from utils.logger import log_info, log_debug, log_error

try:
    import win32gui
    import win32process
    import psutil
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False


def get_active_window_info() -> dict:
    """Return {'title': ..., 'exe': ...} of the currently focused window."""
    if not WIN32_AVAILABLE:
        return {"title": "", "exe": ""}
    try:
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            exe = psutil.Process(pid).name().lower()
        except Exception:
            exe = ""
        return {"title": title.lower(), "exe": exe}
    except Exception as e:
        log_error(f"get_active_window_info error: {e}")
        return {"title": "", "exe": ""}


# Default profiles: exe/title keyword -> mode
DEFAULT_PROFILES = {
    "slack":    "casual",
    "teams":    "casual",
    "discord":  "casual",
    "winword":  "formal",
    "word":     "formal",
    "outlook":  "formal",
    "code":     "technical",
    "pycharm":  "technical",
    "notepad":  "concise",
}


class PerAppProfiles:
    def __init__(self, profiles: Optional[dict] = None):
        self.profiles = dict(DEFAULT_PROFILES)
        if profiles:
            self.profiles.update({k.lower(): v for k, v in profiles.items()})

    def update(self, profiles: dict):
        self.profiles = dict(DEFAULT_PROFILES)
        self.profiles.update({k.lower(): v for k, v in profiles.items()})

    def get_mode_for_active_window(self) -> Optional[str]:
        """Return the mode for the currently focused app, or None if no match."""
        info = get_active_window_info()
        combined = info["exe"] + " " + info["title"]
        for keyword, mode in self.profiles.items():
            if keyword in combined:
                log_debug(f"Per-app profile matched '{keyword}' -> {mode}")
                return mode
        return None

    def get_active_profile_name(self) -> str:
        """Return display name of matched profile, or empty string."""
        info = get_active_window_info()
        combined = info["exe"] + " " + info["title"]
        for keyword, mode in self.profiles.items():
            if keyword in combined:
                return f"{keyword.title()} ({mode})"
        return ""
