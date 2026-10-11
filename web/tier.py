"""
Tier policy for Voxylis — the SINGLE authoritative source.

Server (web/tier.py) owns tiers, quotas, features, modes and prices.
The desktop never enforces tiers locally; it reads entitlements from
GET /api/me and degrades offline to "local mode".
/api/pricing is generated from this module so copy cannot drift.
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
        "qa",  # Q&A feature (Pro+)
        "advanced_stt",  # ENDPOINTING, DIARIZATION modes
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

# Allowed enhancement modes per tier (exact mode ids)
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

# Display metadata for /api/pricing (generated from this module only).
TIER_META = {
    TIER_FREE: {
        "name": "Free",
        "price": 0,
        "period": "month",
        "description": "Perfect for getting started",
        "cta": "Get Started",
        "popular": False,
    },
    TIER_PRO: {
        "name": "Pro",
        "price": 9.99,
        "period": "month",
        "description": "For power users",
        "cta": "Upgrade to Pro",
        "popular": True,
    },
    TIER_BUSINESS: {
        "name": "Business",
        "price": 29.99,
        "period": "month",
        "description": "For teams",
        "cta": "Contact Sales",
        "popular": False,
    },
}

TIER_ORDER = (TIER_FREE, TIER_PRO, TIER_BUSINESS)


def _quota_label(tier: str) -> str:
    quota = TIER_QUOTAS.get(tier, 0)
    if quota is not None and quota < 0:
        return "Unlimited transcriptions"
    if quota >= 1000:
        return f"{quota:,} transcriptions/month"
    return f"{quota} transcriptions/month"


def _mode_label(tier: str) -> str:
    modes = sorted(TIER_ENHANCEMENT_MODES.get(tier, set()))
    if tier == TIER_FREE:
        return "Formal enhancement mode"
    return f"All {len(modes)} enhancement modes ({', '.join(modes)})"


def pricing_features(tier: str) -> list:
    """Honest feature bullets derived from the policy above."""
    quota = _quota_label(tier)
    base = [quota, "Languages your speech provider supports"]
    if tier == TIER_FREE:
        return base + [_mode_label(tier), "Community support"]
    if tier == TIER_PRO:
        return base + [_mode_label(tier), "Q&A (Pro+)", "Priority support"]
    if tier == TIER_BUSINESS:
        return base + [
            "Everything in Pro",
            "Q&A (Pro+)",
            "Team collaboration",
            "API access",
            "Custom integrations",
            "Dedicated support",
        ]
    return base


def pricing_payload() -> dict:
    """Build the /api/pricing response from the single policy source."""
    tiers = []
    for tier in TIER_ORDER:
        meta = TIER_META[tier]
        tiers.append(
            {
                "id": tier,
                "name": meta["name"],
                "price": meta["price"],
                "period": meta["period"],
                "description": meta["description"],
                "features": pricing_features(tier),
                "cta": meta["cta"],
                "popular": meta["popular"],
            }
        )
    return {"status": "success", "tiers": tiers}
