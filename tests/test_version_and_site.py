"""Version consistency, website routes and marketing-claim guardrails."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from web.routes import content as content_routes

from config import version

REPO = Path(__file__).resolve().parent.parent
STATIC = REPO / "web" / "static"


# ── one canonical version ────────────────────────────────────────────────────


def test_version_is_semantic():
    assert re.fullmatch(r"\d+\.\d+\.\d+", version.__version__)
    assert version.version_tag() == f"v{version.__version__}"


def test_generated_mirrors_match_the_canonical_version():
    version.sync()
    assert f"FileVersion', u'{version.__version__}'" in (REPO / "packaging" / "version_info.txt").read_text(
        encoding="utf-8"
    )
    payload = json.loads((STATIC / "version.json").read_text(encoding="utf-8"))
    assert payload["version"] == version.__version__
    # There is exactly one served mirror in the source tree. A second copy is
    # how two different release numbers end up on the same site. Build output and
    # virtualenvs are excluded: they are gitignored copies, not sources of truth.
    generated = {".git", "build", "dist", "venv", ".venv", "__pycache__", "node_modules"}
    others = [
        path
        for path in REPO.rglob("version.json")
        if path != STATIC / "version.json" and not (generated & set(path.relative_to(REPO).parts))
    ]
    assert others == [], f"duplicate version mirrors: {others}"


def test_constants_reexport_the_canonical_version():
    from config import constants

    assert constants.APP_VERSION == version.__version__
    assert constants.APP_NAME == version.APP_NAME


def test_health_reports_the_canonical_version(app_client):
    client, _ = app_client
    assert client.get("/api/health").get_json()["version"] == version.__version__


def test_no_stale_hard_coded_versions_remain():
    """A previous release left several different versions in the tree."""
    stale = {
        "config/constants.py": r'APP_VERSION\s*=\s*"',
    }
    for relative, pattern in stale.items():
        text = (REPO / relative).read_text(encoding="utf-8")
        assert not re.search(pattern, text), f"{relative} hard-codes a version again"

    for relative in ("web/app.py", "config/version.py"):
        text = (REPO / relative).read_text(encoding="utf-8")
        assert '"2.2.0"' not in text
        assert '"2.1.1"' not in text


def test_download_links_are_only_advertised_when_published(app_client, monkeypatch):
    """A visitor must never be sent to an installer that was never published.

    The previous build hard-coded a v3.0.0 artifact URL that returned 404 for
    every visitor while the page said an installer was available.
    """
    client, _ = app_client
    for name in ("DOWNLOAD_URL_WINDOWS", "DOWNLOAD_URL_MACOS", "DOWNLOAD_URL_LINUX"):
        monkeypatch.delenv(name, raising=False)
    # Isolate from the live GitHub feed: no published release in this test.
    monkeypatch.setattr(content_routes, "_github_latest_assets", lambda: {})
    monkeypatch.setattr(content_routes, "_DOWNLOAD_CACHE", {"at": 0.0, "payload": None})

    payload = client.get("/api/download/urls").get_json()
    assert payload["available"] == {"windows": False, "macos": False, "linux": False}
    for platform in ("windows", "macos", "linux"):
        assert "download/v3" not in payload[platform]
    assert payload["windows"] == payload["releases_url"]

    monkeypatch.setenv("DOWNLOAD_URL_WINDOWS", "https://cdn.example.com/Voxylis-Setup.exe")
    published = client.get("/api/download/urls").get_json()
    assert published["available"]["windows"] is True
    assert published["windows"] == "https://cdn.example.com/Voxylis-Setup.exe"


def test_download_routes_redirect_to_the_published_asset(app_client, monkeypatch):
    """Buttons hit the same-origin /download/<platform> routes; a published
    installer 302s straight to the asset, a missing one falls back to the
    honest /download page — never to a GitHub page."""
    client, _ = app_client
    import web.routes.content as content_routes

    monkeypatch.setattr(content_routes, "_DOWNLOAD_CACHE", {"at": 0.0, "payload": None})
    monkeypatch.setattr(
        content_routes,
        "_github_latest_assets",
        lambda: {"Voxylis-Setup-9.9.9.exe": "https://assets.example.com/Voxylis-Setup-9.9.9.exe"},
    )

    # Static buttons point at the same-origin routes (no GitHub hrefs).
    html = (STATIC / "download.html").read_text(encoding="utf-8")
    assert 'href="/download/windows"' in html
    assert "releases/download" not in html

    r = client.get("/download/windows")
    assert r.status_code == 302
    assert r.headers["Location"] == "https://assets.example.com/Voxylis-Setup-9.9.9.exe"

    monkeypatch.setattr(content_routes, "_github_latest_assets", lambda: {})
    r = client.get("/download/macos")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/download")

    r = client.get("/download/bogus")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/download")


def test_resolver_queries_the_json_api_not_the_html_page():
    """github.com/releases/latest serves HTML; the resolver must use
    api.github.com or it silently never resolves a published installer."""
    import inspect

    import web.routes.content as content_routes

    src = inspect.getsource(content_routes._github_latest_assets)
    assert "api.github.com/repos/" in src


def test_download_page_checks_availability_before_relinking():
    text = (STATIC / "download.html").read_text(encoding="utf-8")
    assert "dl-win-note" in text
    # The availability check lives in the external download.js bundle
    # (strict CSP forbids inline scripts).
    js = (STATIC / "js" / "download.js").read_text(encoding="utf-8")
    assert "available" in js


def test_download_page_reads_the_version_from_one_source():
    text = (STATIC / "download.html").read_text(encoding="utf-8")
    assert "data-voxylis-version" in text
    # The version fetch lives in the external download.js bundle
    # (strict CSP forbids inline scripts).
    js = (STATIC / "js" / "download.js").read_text(encoding="utf-8")
    assert "/version.json" in js
    # No hard-coded release asset: buttons start at the releases page and are
    # re-pointed only when /api/download/urls reports available=true. The
    # *displayed* version text is filled from version.json at runtime, so no
    # release number may be baked into visible markup (it would go stale).
    assert "releases/download/v" not in text
    visible = re.sub(r"<a\b[^>]*>", "", text)
    assert not re.search(r"v\d+\.\d+\.\d+", visible)


def test_social_login_requires_explicit_consent_before_session():
    """No Voxylis session may exist until the user presses Continue.

    The provider verifies the user first; then auth.html must show WHAT
    Voxylis receives (name, email, photo) with Continue/Cancel, and only the
    Continue handler may call finishAuth0Login. Cancel must discard the
    token and state plainly that nothing was stored.
    """
    text = (STATIC / "auth.html").read_text(encoding="utf-8")
    for marker in (
        "consent-overlay",
        "consent-continue",
        "consent-cancel",
        "nothing was created or stored",
    ):
        assert marker in text, f"auth.html missing consent gate: {marker}"
    # The consent logic lives in the external auth.js bundle (strict CSP
    # forbids inline scripts): the gate must exist there, wired to the same
    # overlay element ids.
    js = (STATIC / "js" / "auth.js").read_text(encoding="utf-8")
    for marker in ("showConsent(", "pendingIdToken"):
        assert marker in js, f"auth.js missing consent gate: {marker}"
    # The token-exchange success path must park at the consent dialog,
    # never create the session directly.
    assert "showConsent(tokens.id_token)" in js
    # Cancel path discards the token instead of proceeding.
    assert "pendingIdToken = ''" in js


def test_legal_pages_exist_for_oauth_consent_screen():
    """Google's OAuth consent screen links the app's privacy policy and
    terms. Both pages must exist, state the social-sign-in data (name,
    email, photo), and be linked from every footer."""
    privacy = (STATIC / "privacy.html").read_text(encoding="utf-8")
    terms = (STATIC / "terms.html").read_text(encoding="utf-8")
    for needle in ("profile photo", "never stored", "/contact"):
        assert needle in privacy, f"privacy.html missing: {needle}"
    assert "voxylis.com" not in privacy.lower(), "privacy.html must not claim an unowned domain"
    assert "as is" in terms
    for page in ("index", "download", "pricing", "about", "blog", "contact"):
        footer = (STATIC / f"{page}.html").read_text(encoding="utf-8")
        assert 'href="/privacy"' in footer, f"{page}.html footer missing Privacy"
        assert 'href="/terms"' in footer, f"{page}.html footer missing Terms"


def test_cookie_banner_is_honest_and_wired_everywhere():
    """The banner must match reality: no analytics/marketing cookies exist,
    so both stay OFF by default and optional loaders must gate on consent.
    Every page loads the script and links the cookie policy + re-opener."""
    js = (STATIC / "js" / "cookie-consent.js").read_text(encoding="utf-8")
    for marker in (
        "voxy_cookie_consent",
        "Reject non-essential",
        "Customize",
        "/privacy#cookies",
        "voxyCookieConsent",
        "voxyShowCookieBanner",
        "Not used today",
    ):
        assert marker in js, f"cookie-consent.js missing: {marker}"
    pages = [
        "index",
        "download",
        "pricing",
        "about",
        "blog",
        "contact",
        "auth",
        "dashboard",
        "privacy",
        "terms",
    ]
    for page in pages:
        text = (STATIC / f"{page}.html").read_text(encoding="utf-8")
        assert "js/cookie-consent.js" in text, f"{page}.html missing banner script"
    privacy = (STATIC / "privacy.html").read_text(encoding="utf-8")
    assert 'id="cookies"' in privacy


def test_version_json_is_served_by_the_backend_too(app_client):
    """The static host resolves the file; Flask needs its own route."""
    client, _ = app_client
    payload = client.get("/version.json").get_json()
    assert payload["version"] == version.__version__
    assert payload["releases_url"] == version.RELEASES_URL


# ── website routes ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/pricing",
        "/blog",
        "/about",
        "/contact",
        "/auth",
        "/download",
        "/dashboard",
        "/privacy",
        "/terms",
        "/docs/installation",
        "/docs/configuration",
        "/docs/troubleshooting",
        "/static/css/base.css",
        "/static/js/api.js",
        "/static/js/cookie-consent.js",
        "/api/features",
        "/api/pricing",
        "/api/stats/public",
        "/api/download/urls",
    ],
)
def test_public_routes_respond(app_client, path):
    client, _ = app_client
    assert client.get(path).status_code == 200, path


def test_unknown_docs_page_is_a_json_404(app_client):
    client, _ = app_client
    response = client.get("/docs/does-not-exist")
    assert response.status_code == 404
    assert response.get_json()["error"] == "Page not found"


def test_blog_exposes_the_current_post_set(app_client):
    client, _ = app_client
    slugs = {post["slug"] for post in client.get("/api/blog").get_json()["posts"]}
    assert "introducing-voxylis-3-0" in slugs
    # Withdrawn posts must not be served.
    assert "introducing-voxy-2-0" not in slugs
    assert "voice-input-vs-typing-numbers" not in slugs


def test_legacy_blog_urls_redirect(app_client):
    client, _ = app_client
    response = client.get("/blog/introducing-voxy-2-0")
    assert response.status_code == 301
    assert response.headers["Location"].endswith("/blog/introducing-voxylis-3-0")


def test_blog_post_bodies_match_the_titles(app_client):
    client, _ = app_client
    post = client.get("/api/blog/introducing-voxylis-3-0").get_json()["post"]
    assert post["title"] == "Introducing Voxylis 3.0"
    assert "3.0" in post["content"]


# ── marketing-claim guardrails ───────────────────────────────────────────────


FABRICATED_CLAIMS = [
    r"12k\+",
    r"4\.8/5",
    r"99\.2\s*%",
    r"50\s*000",
    r"142\s*WPM",
    r"NPS\s*:?\s*72",
    r"3\.2x",
    r"Anika Rao",
    r"Marcus Kim",
    r"Lena Petrova",
    r"Measured on [0-9,]+\s*sessions",
    r"10x\s+[Ff]aster",
    r"calibrated confidence",
    r"confidence score",
    r"Ctrl\+Shift\+P",
]


@pytest.mark.parametrize("pattern", FABRICATED_CLAIMS)
def test_no_fabricated_marketing_claims(pattern):
    offenders = []
    for path in list(STATIC.glob("*.html")) + list(STATIC.glob("js/*.js")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(pattern, text):
            offenders.append(path.name)
    assert not offenders, f"{pattern} reappeared in {offenders}"


def test_pricing_page_is_honest_about_payments():
    text = (STATIC / "pricing.html").read_text(encoding="utf-8")
    assert "not purchasable yet" in text
    for claim in ("PayPal", "credit cards", "14-day free trial", "annual plans"):
        assert claim.lower() not in text.lower(), claim


def test_wake_word_is_fully_removed():
    for relative in ("dashboard.html", "js/dashboard.js", "css/dashboard.css"):
        text = (STATIC / relative).read_text(encoding="utf-8", errors="ignore")
        assert "wakeword" not in text.lower(), f"wake word remnant in {relative}"
        assert "voxylis_wakeword" not in text
    import web.tier as tier

    assert "wake_word" not in tier.TIER_FEATURES.get("pro", set())
    assert "wake_word" not in tier.TIER_FEATURES.get("business", set())


def test_account_deletion_and_upgrade_claims_match_the_implementation():
    """The dashboard must not offer a self-service upgrade that cannot work."""
    for relative in ("dashboard.html", "js/dashboard.js"):
        text = (STATIC / relative).read_text(encoding="utf-8")
        assert "subscription/upgrade" not in text


def test_pricing_api_makes_no_unverifiable_language_claims(app_client):
    """Tier language copy must not assert counts the code does not enforce.

    The Whisper models behind /api/transcribe recognise their providers'
    language sets, and the app pins a fixed list from ui/pages.py — neither is
    a per-tier restriction, so advertising counts like "5 languages" (free) or
    "99+ languages" (pro) is unsupported either way.
    """
    client, _ = app_client
    payload = client.get("/api/pricing").get_json()
    for tier in payload["tiers"]:
        for feature in tier["features"]:
            assert not re.search(r"\d+\s*\+?\s*languages", feature, flags=re.IGNORECASE), f"{tier['id']}: {feature!r}"


def test_pricing_api_matches_enforced_quotas_and_features(app_client):
    """Advertised copy must agree with web/tier.py."""
    from web.tier import TIER_QUOTAS, TIER_ENHANCEMENT_MODES

    client, _ = app_client
    tiers = {t["id"]: t for t in client.get("/api/pricing").get_json()["tiers"]}
    assert f"{TIER_QUOTAS['free']:,} transcriptions/month" in tiers["free"]["features"]
    assert "Formal enhancement mode" in tiers["free"]["features"]
    assert len(TIER_ENHANCEMENT_MODES["pro"]) == 5
    pro_modes = ", ".join(sorted(TIER_ENHANCEMENT_MODES["pro"]))
    assert any(pro_modes in f for f in tiers["pro"]["features"]), tiers["pro"]["features"]
    assert f"{TIER_QUOTAS['pro']:,} transcriptions/month" in tiers["pro"]["features"]
    # Q&A is Pro+, never free.
    assert any("Q&A" in f for f in tiers["pro"]["features"])
    assert not any("Q&A" in f for f in tiers["free"]["features"])
    # No wake word anywhere.
    for tier in tiers.values():
        assert not any("wake" in f.lower() for f in tier["features"]), tier


def test_pricing_payload_equals_tier_policy(app_client):
    """GET /api/pricing must equal web.tier.pricing_payload() exactly."""
    from web import tier as tier_policy

    client, _ = app_client
    payload = client.get("/api/pricing").get_json()
    assert payload == tier_policy.pricing_payload()


def test_download_page_does_not_claim_a_language_count():
    text = (STATIC / "download.html").read_text(encoding="utf-8")
    assert not re.search(r"\d+\+?\s*languages", text, flags=re.IGNORECASE)
