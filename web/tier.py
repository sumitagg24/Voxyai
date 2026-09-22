"""
Tier constants for Voxylis. DB-aware helpers live in web/app.py to avoid circular imports.
"""
from functools import wraps
from flask import jsonify


TIER_FREE = "free"
TIER_PRO = "pro"
TIER_BUSINESS = "business"

# Feature access map: tier -> set of allowed features
TIER_FEATURES = {
    TIER_FREE: {
        "transcription",       # basic (PUSH_TO_TALK only)
        "enhancement_basic",   # formal mode only
        "history",
        "settings",
        "hotkeys",
    },
    TIER_PRO: {
        "transcription",       # all modes (PUSH_TO_TALK, ENDPOINTING, DIARIZATION)
        "enhancement_basic",
        "enhancement_all",     # all 5 modes
        "qa",                  # Q&A feature
        "advanced_stt",        # ENDPOINTING, DIARIZATION modes
        "wake_word",
        "history",
        "settings",
        "hotkeys",
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
        "custom_integrations",
        "history",
        "settings",
        "hotkeys",
    },
}

# Free tier limits
FREE_MONTHLY_TRANSCRIPTIONS = 100

# Allowed enhancement modes per tier
TIER_ENHANCEMENT_MODES = {
    TIER_FREE: {"formal"},
    TIER_PRO: {"formal", "casual", "technical", "concise", "creative"},
    TIER_BUSINESS: {"formal", "casual", "technical", "concise", "creative"},
}

# Allowed STT modes per tier
TIER_STT_MODES = {
    TIER_FREE: {"PUSH_TO_TALK"},
    TIER_PRO: {"PUSH_TO_TALK", "ENDPOINTING", "DIARIZATION"},
    TIER_BUSINESS: {"PUSH_TO_TALK", "ENDPOINTING", "DIARIZATION"},
}
