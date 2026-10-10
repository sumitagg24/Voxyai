"""Blueprint registration guard (prevents route loss during refactors)."""

import importlib


def test_all_route_modules_importable():
    for name in (
        "web.auth_helpers",
        "web.content.blog_posts",
        "web.db",
        "web.extensions",
        "web.routes.pages",
        "web.routes.auth",
        "web.routes.account",
        "web.routes.usage",
        "web.routes.content",
        "web.routes.webhooks",
    ):
        importlib.import_module(name)


def test_blueprints_registered_and_routes_present(app_client):
    client, web_app = app_client
    for bp in ("pages", "auth", "account", "usage", "content", "webhooks"):
        assert bp in web_app.app.blueprints, f"blueprint {bp} not registered"
    rules = {r.rule for r in web_app.app.url_map.iter_rules()}
    expected = {
        "/",
        "/pricing",
        "/blog",
        "/about",
        "/contact",
        "/privacy",
        "/terms",
        "/auth",
        "/download",
        "/dashboard",
        "/favicon.ico",
        "/og-image.png",
        "/docs/<page>",
        "/blog/<slug>",
        "/api/auth/auth0/config",
        "/api/auth/auth0",
        "/api/auth/qr/start",
        "/api/auth/qr/status",
        "/api/auth/qr/approve",
        "/api/admin/users",
        "/api/auth/signup",
        "/api/auth/login",
        "/api/auth/verify",
        "/api/auth/logout",
        "/api/auth/forgot-password",
        "/api/auth/reset-password",
        "/api/auth/verify-email",
        "/api/auth/confirm-email",
        "/api/me",
        "/api/onboarding",
        "/api/features",
        "/api/pricing",
        "/api/settings",
        "/api/hotkeys",
        "/api/qa",
        "/api/enhance",
        "/api/transcribe",
        "/api/history",
        "/api/history/<int:item_id>",
        "/api/stats",
        "/api/stats/public",
        "/api/subscription",
        "/api/subscription/upgrade",
        "/api/auth/update-profile",
        "/api/account/delete",
        "/api/contact",
        "/api/newsletter",
        "/api/download/urls",
        "/api/download/detect",
        "/api/blog",
        "/api/blog/<slug>",
        "/api/download/track",
        "/version.json",
        "/api/public-config",
        "/api/health",
        "/unsubscribe",
        "/api/webhooks/dodo",
    }
    missing = expected - rules
    assert not missing, f"missing routes: {sorted(missing)}"


def test_legacy_reexports_present(app_client):
    _, web_app = app_client
    for name in (
        "app",
        "_get_db",
        "_create_session",
        "_verify_session",
        "_extract_session",
        "_call_llm_for_qa",
        "_call_llm_for_enhancement",
        "_any_llm_key_configured",
        "get_user_tier",
        "get_user_entitlements",
        "http_requests",
        "check_transcription_quota",
        "limiter",
        "cache",
        "subscription_service",
        "FREE_MONTHLY_TRANSCRIPTIONS",
        "TIER_QUOTAS",
    ):
        assert hasattr(web_app, name), f"web.app missing legacy name: {name}"
