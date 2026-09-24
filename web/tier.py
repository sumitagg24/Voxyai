"""
Tier constants for Voxylis. DB-aware helpers live in web/app.py to avoid circular imports.
"""

from __future__ import annotations

import os

TIER_FREE = "free"
TIER_PRO = "pro"
TIER_BUSINESS = "business"
TIER_OWNER = "owner"

# Monthly transcription limits per tier (-1 means unlimited)
FREE_MONTHLY_TRANSCRIPTIONS = int(os.environ.get("FREE_MONTHLY_TRANSCRIPTIONS", 100))
PRO_MONTHLY_TRANSCRIPTIONS = int(os.environ.get("PRO_MONTHLY_TRANSCRIPTIONS", 1000))
BUSINESS_MONTHLY_TRANSCRIPTIONS = int(os.environ.get("BUSINESS_MONTHLY_TRANSCRIPTIONS", 5000))
OWNER_MONTHLY_TRANSCRIPTIONS = -1

TIER_QUOTAS = {
    TIER_FREE: FREE_MONTHLY_TRANSCRIPTIONS,
    TIER_PRO: PRO_MONTHLY_TRANSCRIPTIONS,
    TIER_BUSINESS: BUSINESS_MONTHLY_TRANSCRIPTIONS,
    TIER_OWNER: OWNER_MONTHLY_TRANSCRIPTIONS,
}

# Feature access map: tier -> set of allowed features
TIER_FEATURES = {
    TIER_FREE: {
        "transcription",  # basic (PUSH_TO_TALK only)
        "enhancement_basic",  # formal mode only
        "history",
        "settings",
        "hotkeys",
    },
    TIER_PRO: {
        "transcription",  # all modes (PUSH_TO_TALK, ENDPOINTING, DIARIZATION)
        "enhancement_basic",
        "enhancement_all",  # all 5 modes
        "qa",  # Q&A feature
        "advanced_stt",  # ENDPOINTING, DIARIZATION modes
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
    TIER_OWNER: {
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
        "diagnostics",
        "admin",
        "unlimited_usage",
    },
}

# Allowed enhancement modes per tier
TIER_ENHANCEMENT_MODES = {
    TIER_FREE: {"formal"},
    TIER_PRO: {"formal", "casual", "technical", "concise", "creative"},
    TIER_BUSINESS: {"formal", "casual", "technical", "concise", "creative"},
    TIER_OWNER: {"formal", "casual", "technical", "concise", "creative"},
}

# Allowed STT modes per tier
TIER_STT_MODES = {
    TIER_FREE: {"PUSH_TO_TALK"},
    TIER_PRO: {"PUSH_TO_TALK", "ENDPOINTING", "DIARIZATION"},
    TIER_BUSINESS: {"PUSH_TO_TALK", "ENDPOINTING", "DIARIZATION"},
    TIER_OWNER: {"PUSH_TO_TALK", "ENDPOINTING", "DIARIZATION"},
}
