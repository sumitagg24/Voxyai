"""
Subscription tier policy.

The desktop client and the website are **untrusted**.  A tier may only change
through one of these paths:

    payment_webhook   a verified webhook from the payment provider.  Not
                      configured yet, so this path refuses rather than
                      pretending a payment happened.
    admin             an admin acting on a user (audited).
    dev               an explicit local-development override.  Refused whenever
                      the app is running in production.

Previously ``POST /api/subscription/upgrade`` let any authenticated user set
their own tier to ``pro`` or ``business`` — a complete subscription bypass.
Every attempt is now recorded in ``tier_audit`` so the log of who granted what
survives, and the HTTP route is a thin wrapper over :func:`apply_tier_change`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from web.tier import (
    TIER_BUSINESS,
    TIER_FREE,
    TIER_PRO,
    TIER_OWNER,
    FREE_MONTHLY_TRANSCRIPTIONS,
    PRO_MONTHLY_TRANSCRIPTIONS,
    BUSINESS_MONTHLY_TRANSCRIPTIONS,
    OWNER_MONTHLY_TRANSCRIPTIONS,
)

VALID_TIERS = (TIER_FREE, TIER_PRO, TIER_BUSINESS, TIER_OWNER)

SOURCE_PAYMENT_WEBHOOK = "payment_webhook"
SOURCE_ADMIN = "admin"
SOURCE_DEV = "dev"
VALID_SOURCES = (SOURCE_PAYMENT_WEBHOOK, SOURCE_ADMIN, SOURCE_DEV)

_TRUTHY = {"1", "true", "yes", "on"}


@dataclass
class TierChangeResult:
    applied: bool
    tier: str
    source: str
    reason: str = ""

    def as_dict(self) -> dict:
        return {"applied": self.applied, "tier": self.tier, "source": self.source, "reason": self.reason}


class TierChangeDenied(Exception):
    """Raised when a tier change is not permitted."""

    def __init__(self, message: str, status: int = 403, code: str = "tier_change_denied"):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code

    def as_dict(self) -> dict:
        return {"success": False, "error": self.message, "code": self.code}


def environment() -> str:
    """Resolved deployment environment: ``production`` or ``development``."""
    import os

    for name in ("VOXYLIS_ENV", "APP_ENV", "FLASK_ENV", "ENVIRONMENT"):
        value = (os.environ.get(name) or "").strip().lower()
        if value:
            return "production" if value in ("production", "prod", "live") else "development"
    # Render/Fly all set these; treat a hosted runtime as production.
    for name in ("VERCEL", "RENDER", "FLY_APP_NAME", "DYNO", "WEBSITE_SITE_NAME"):
        if os.environ.get(name):
            return "production"
    return "development"


def is_production() -> bool:
    return environment() == "production"


def dev_tier_change_enabled() -> bool:
    """True only for an explicit, non-production development override."""
    import os

    if is_production():
        return False
    return (os.environ.get("ALLOW_DEV_TIER_CHANGE") or "").strip().lower() in _TRUTHY


def payments_configured() -> bool:
    """True when a payment provider is wired up (webhook + checkout).

    Backwards-compatible alias for :func:`dodo_configured`: Dodo Payments is
    the only supported provider, so this is true exactly when Dodo is.
    """
    return dodo_configured()


def dodo_api_key() -> str:
    """Optional Dodo Payments API key (server-side use only, never exposed)."""
    import os

    return (os.environ.get("DODO_PAYMENTS_API_KEY") or "").strip()


def dodo_webhook_secret() -> str:
    """Shared secret used to verify Dodo webhook signatures (``whsec_...``)."""
    import os

    return (os.environ.get("DODO_WEBHOOK_SECRET") or "").strip()


def dodo_checkout_urls() -> dict:
    """Public hosted-checkout links per paid tier (empty string when unset)."""
    import os

    return {
        TIER_PRO: (os.environ.get("DODO_CHECKOUT_URL_PRO") or "").strip(),
        TIER_BUSINESS: (os.environ.get("DODO_CHECKOUT_URL_BUSINESS") or "").strip(),
    }


def dodo_configured() -> bool:
    """True when Dodo Payments is wired up: webhook secret plus at least one
    hosted-checkout URL.

    A secret alone cannot collect money (nothing to buy through) and a
    checkout link alone cannot be trusted (no way to verify payment), so both
    halves are required before the site offers checkout or the webhook path
    applies tier changes.
    """
    if not dodo_webhook_secret():
        return False
    return any(url for url in dodo_checkout_urls().values())


def _record(conn, user_id: int, old_tier: str, new_tier: str, source: str, actor: str, note: str) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS tier_audit ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " user_id INTEGER NOT NULL,"
        " old_tier TEXT NOT NULL,"
        " new_tier TEXT NOT NULL,"
        " source TEXT NOT NULL,"
        " actor TEXT NOT NULL DEFAULT '',"
        " note TEXT NOT NULL DEFAULT '',"
        " created_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    conn.execute(
        "INSERT INTO tier_audit (user_id, old_tier, new_tier, source, actor, note)" " VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, old_tier, new_tier, source, actor or "", note or ""),
    )


def apply_tier_change(
    conn,
    user_id: int,
    new_tier: str,
    source: str,
    actor: str = "",
    actor_is_admin: bool = False,
    webhook_verified: bool = False,
    note: str = "",
) -> TierChangeResult:
    """Apply a tier change if (and only if) the source is authorised.

    ``conn`` is an open sqlite3 connection; the caller owns commit/close so a
    tier change and its audit row are written atomically.
    """
    new_tier = (new_tier or "").strip().lower()
    if new_tier not in VALID_TIERS:
        raise TierChangeDenied("Unknown subscription tier.", status=400, code="invalid_tier")
    if source not in VALID_SOURCES:
        raise TierChangeDenied("Unknown tier-change source.", status=400, code="invalid_source")

    if source == SOURCE_PAYMENT_WEBHOOK:
        if not payments_configured():
            raise TierChangeDenied(
                "Paid plans are not available yet. No payment provider is configured on this deployment, "
                "so no tier change was applied.",
                status=503,
                code="payments_not_configured",
            )
        if not webhook_verified:
            raise TierChangeDenied(
                "Unverified webhook.",
                status=401,
                code="webhook_unverified",
            )
    elif source == SOURCE_ADMIN:
        if not actor_is_admin:
            raise TierChangeDenied(
                "Only an administrator can change a plan manually.",
                status=403,
                code="admin_required",
            )
    elif source == SOURCE_DEV:
        if new_tier == TIER_OWNER and not actor_is_admin:
            raise TierChangeDenied(
                "The owner tier can only be granted to the designated owner account.",
                status=403,
                code="owner_restricted",
            )
        if not dev_tier_change_enabled():
            raise TierChangeDenied(
                "Changing your own plan is not allowed. Paid plans must be purchased through the " "payment provider.",
                status=403,
                code="self_service_tier_change_disabled",
            )

    row = conn.execute("SELECT tier FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise TierChangeDenied("User not found.", status=404, code="user_not_found")
    old_tier = (row["tier"] if not hasattr(row, "keys") else row["tier"]) or TIER_FREE

    conn.execute("UPDATE users SET tier = ? WHERE id = ?", (new_tier, user_id))
    _record(conn, user_id, old_tier, new_tier, source, actor, note)
    return TierChangeResult(applied=True, tier=new_tier, source=source, reason=note)


def tier_summary(user_id: int, get_tier, count_transcriptions) -> dict:
    """Server-authoritative plan summary. The client only reads this."""
    tier = get_tier(user_id)
    tier_info = {
        TIER_FREE: {
            "price": 0,
            "limit": f"{FREE_MONTHLY_TRANSCRIPTIONS}/month",
            "name": "Free",
            "max": FREE_MONTHLY_TRANSCRIPTIONS,
        },
        TIER_PRO: {
            "price": 9.99,
            "limit": f"{PRO_MONTHLY_TRANSCRIPTIONS}/month",
            "name": "Pro",
            "max": PRO_MONTHLY_TRANSCRIPTIONS,
        },
        TIER_BUSINESS: {
            "price": 29.99,
            "limit": f"{BUSINESS_MONTHLY_TRANSCRIPTIONS}/month",
            "name": "Business",
            "max": BUSINESS_MONTHLY_TRANSCRIPTIONS,
        },
        TIER_OWNER: {"price": 0, "limit": "Unlimited", "name": "Owner", "max": OWNER_MONTHLY_TRANSCRIPTIONS},
    }
    info = tier_info.get(tier, tier_info[TIER_FREE])
    usage = count_transcriptions(user_id)
    max_limit = info["max"]
    if max_limit == -1:
        percentage = 0
        limit_display = "Unlimited"
    else:
        percentage = min(100, max(0, round((usage / max_limit) * 100))) if max_limit > 0 else 0
        limit_display = f"{max_limit}/month"

    return {
        "plan": info["name"],
        "tier": tier,
        "price": info["price"],
        "renewalDate": None,
        "status": "active",
        "usage": {
            "transcriptions": usage,
            "limit": limit_display,
            "max": max_limit,
            "percentage": percentage,
        },
        # The client must not offer a self-service upgrade that cannot work.
        # When configured, checkout_urls hands the browser the hosted Dodo
        # checkout links (public URLs, safe to expose); otherwise they are
        # empty and the frontend shows honest "unavailable" copy instead.
        "can_self_upgrade": payments_configured(),
        "checkout_available": payments_configured(),
        "checkout_urls": public_checkout_urls(),
    }


def self_service_upgrade_available() -> bool:
    return payments_configured()


def public_checkout_urls() -> dict:
    """Checkout links safe for any client, logged out or not.

    Real hosted URLs only when Dodo is fully configured; empty strings
    otherwise, so the frontend shows honest "unavailable" copy instead of a
    dead link. Same shape as the ``checkout_urls`` in :func:`tier_summary`.
    """
    if not payments_configured():
        return {TIER_PRO: "", TIER_BUSINESS: ""}
    return dodo_checkout_urls()


def describe_policy() -> dict:
    """Non-secret policy description for /api/health and diagnostics."""
    urls = dodo_checkout_urls()
    return {
        "environment": environment(),
        "payments_configured": payments_configured(),
        "dev_tier_change_enabled": dev_tier_change_enabled(),
        "self_service_upgrade_available": self_service_upgrade_available(),
        "provider": "dodo",
        "dodo_configured": dodo_configured(),
        "dodo_checkout_configured": {tier: bool(url) for tier, url in urls.items()},
    }


def dodo_plan_to_tier(plan_ref: str) -> str:
    """Map a Dodo product/plan reference to a Voxylis tier.

    The reference is whatever the merchant configured on the Dodo product
    (product id, name, or metadata); matching is case-insensitive substring so
    ``"Voxylis Business Monthly"`` and ``"business"`` both resolve. Unknown or
    empty references default to Pro — a successful payment must grant *some*
    paid tier, and Pro is the lower one. Expired/cancelled subscriptions never
    reach this helper: the webhook downgrades those to free directly.
    """
    ref = (plan_ref or "").strip().lower()
    if "business" in ref:
        return TIER_BUSINESS
    return TIER_PRO


def resolve_actor_source(actor_is_admin: bool) -> Optional[str]:
    """Pick the source used by the HTTP route: admin, explicit dev, or None."""
    if actor_is_admin:
        return SOURCE_ADMIN
    if dev_tier_change_enabled():
        return SOURCE_DEV
    return None
