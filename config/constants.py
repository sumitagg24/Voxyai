"""
Global constants and configuration for Voxylis
"""

# Application metadata
#
# APP_VERSION comes from config/version.py - the single canonical source.
# Never hard-code a version string in another module.
from config.version import (  # noqa: F401  (re-exported for compatibility)
    APP_DISPLAY_NAME,
    APP_NAME,
    COPYRIGHT as APP_COPYRIGHT,
    PUBLISHER as APP_PUBLISHER,
    REPO_URL as APP_REPO_URL,
    __version__ as APP_VERSION,
)

__all__ = [
    "APP_DISPLAY_NAME",
    "APP_NAME",
    "APP_COPYRIGHT",
    "APP_PUBLISHER",
    "APP_REPO_URL",
    "APP_VERSION",
]

APP_AUTHOR = APP_PUBLISHER

# Audio settings
SAMPLE_RATE = 16000
CHUNK_SIZE = 1024
AUDIO_FORMAT = "int16"
CHANNELS = 1
AUDIO_DEVICE = None  # None = default device

# Recording settings
MAX_RECORDING_DURATION = 600  # 10 minutes in seconds
MIN_RECORDING_DURATION = 1.0  # 1 second minimum

# API settings
OPENAI_API_TIMEOUT = 30
WHISPER_MODEL = "whisper-1"
GPT_MODEL = "gpt-4-turbo-preview"

# UI settings
# Default hotkey must be a combo that does not collide with a Windows
# shortcut (see core/hotkey_listener.UNSAFE_COMBOS).
HOTKEY_DEFAULT = "win+shift"
MODE_HOTKEY_DEFAULTS = {"win+alt": "casual", "win+ctrl": "technical"}
FLOATING_WIDGET_WIDTH = 260
FLOATING_WIDGET_HEIGHT = 56
WINDOW_OPACITY = 0.95

# Enhancement modes
ENHANCEMENT_MODES = {
    "formal": "Make this text formal and professional",
    "casual": "Keep this text casual and friendly",
    "technical": "Make this text technical and precise",
    "concise": "Make this text concise and brief",
    "creative": "Make this text creative and engaging",
}

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = "voxylis.log"

# Paths (names only - the writable root is resolved by utils.paths)
CONFIG_DIR = "config"
TEMP_DIR = "temp"
LOGS_DIR = "logs"
DATA_DIR = "data"
SECRETS_DIR = "secrets"
CACHE_DIR = "cache"
MODELS_DIR = "models"
UPDATES_DIR = "updates"

# Timeouts
TRANSCRIPTION_TIMEOUT = 120  # 2 minutes for long audio
ENHANCEMENT_TIMEOUT = 60  # 1 minute for long text
INJECTION_TIMEOUT = 5

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

# Subscription tiers
TIER_FREE = "free"
TIER_PRO = "pro"
TIER_BUSINESS = "business"

TIER_FEATURES = {
    TIER_FREE: {"transcription", "enhancement_basic", "history", "settings"},
    TIER_PRO: {
        "transcription",
        "enhancement_basic",
        "enhancement_all",
        "qa",
        "advanced_stt",
        "wake_word",
        "history",
        "settings",
    },
    TIER_BUSINESS: {
        "transcription",
        "enhancement_basic",
        "enhancement_all",
        "qa",
        "advanced_stt",
        "wake_word",
        "api_access",
        "team_features",
        "history",
        "settings",
    },
}

FREE_MONTHLY_TRANSCRIPTIONS = 100

TIER_ENHANCEMENT_MODES = {
    TIER_FREE: {"formal"},
    TIER_PRO: {"formal", "casual", "technical", "concise", "creative"},
    TIER_BUSINESS: {"formal", "casual", "technical", "concise", "creative"},
}

TIER_STT_MODES = {
    TIER_FREE: {"PUSH_TO_TALK"},
    TIER_PRO: {"PUSH_TO_TALK", "ENDPOINTING", "DIARIZATION"},
    TIER_BUSINESS: {"PUSH_TO_TALK", "ENDPOINTING", "DIARIZATION"},
}


def get_user_tier(settings: dict) -> str:
    """Get tier from user settings. Defaults to free."""
    return settings.get("tier", TIER_FREE)


def has_tier_feature(settings: dict, feature: str) -> bool:
    """Check if user's tier has a feature."""
    tier = get_user_tier(settings)
    return feature in TIER_FEATURES.get(tier, TIER_FEATURES[TIER_FREE])
