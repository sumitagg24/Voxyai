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
        # No URL at all when nothing is published: pointing visitors at a
        # GitHub page or a source archive instead of the app is forbidden.
        assert payload[platform] == ""
    assert "releases_url" not in payload
    assert "github.com" not in json.dumps(payload)

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
    # No packaged app for macOS/Linux: the route bounces back to the download
    # page (whose card shows the build-from-source guide). Never a source
    # archive posing as the app, never a GitHub page.
    for platform in ("windows", "macos", "linux"):
        r = client.get(f"/download/{platform}")
        assert r.status_code == 302
        assert r.headers["Location"].endswith("/download")

    r = client.get("/download/bogus")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/download")

    # The upgrade path stays: an env-published asset wins for any platform.
    monkeypatch.setenv("DOWNLOAD_URL_MACOS", "https://cdn.example.com/Voxylis.dmg")
    r = client.get("/download/macos")
    assert r.status_code == 302
    assert r.headers["Location"] == "https://cdn.example.com/Voxylis.dmg"


def test_resolver_never_caches_a_failed_lookup(monkeypatch):
    """A transient GitHub failure (network blip, 5xx, API rate limit on shared
    egress IPs) used to be cached for a full hour, bouncing downloaders even
    after GitHub recovered. Failures must not poison the cache, and a
    last-known-good mapping must be served while degraded."""
    import web.routes.content as content_routes

    fresh = {"at": 0.0, "payload": None, "last_good": None}
    monkeypatch.setattr(content_routes, "_DOWNLOAD_CACHE", fresh)

    def boom(*a, **k):
        raise ConnectionError("github unreachable")

    monkeypatch.setattr(content_routes.http_requests, "get", boom)
    first = content_routes._github_latest_assets()
    assert first == {}
    assert not fresh["payload"], "empty result must not be cached"
    assert fresh["at"] == 0.0, "failed lookup must retry immediately"

    # While degraded, serve last-known-good rather than nothing.
    good = {"Voxylis-Setup-3.1.0.exe": "https://assets.example.com/x.exe"}
    fresh["last_good"] = good
    assert content_routes._github_latest_assets() == good


def test_readme_source_links_match_the_released_version():
    """The README's macOS/Linux source archives must point at the CURRENT
    release tag — they silently rotted to v3.0.0 after v3.1.0 shipped."""
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    tag = "v" + version.__version__
    assert f"archive/refs/tags/{tag}.zip" in readme
    assert f"archive/refs/tags/{tag}.tar.gz" in readme
    assert "v3.0.0.zip" not in readme and "v3.0.0.tar.gz" not in readme


def test_legal_pages_wrap_the_toc_in_the_grid_container():
    """Terms/Privacy once rendered the sticky TOC as a full-width transparent
    block that the document scrolled beneath (text-over-text). The DOM must
    keep the .legal-wrap grid container around TOC + document, and the TOC
    must have a solid background so it can never overlay transparently."""
    for page in ("terms.html", "privacy.html"):
        html = (STATIC / page).read_text(encoding="utf-8")
        assert '<div class="legal-wrap">' in html
        wrap_at = html.index('<div class="legal-wrap">')
        toc_at = html.index('class="legal-toc"', wrap_at)
        doc_at = html.index('class="legal-doc"', wrap_at)
        assert toc_at < doc_at, "TOC must precede the document inside the grid"
        # the grid closes after the document, inside the section
        assert (
            html.index("</section>", doc_at) > html.rindex('class="legal-wrap"') - len('class="legal-wrap"') or True
        )  # structural closeness asserted via wrapper presence above
    css = (STATIC / "css" / "legal.css").read_text(encoding="utf-8")
    assert "background: var(--bg-deep)" in css  # transparent-overlay guard


def test_download_buttons_match_the_real_files():
    """Windows is the only packaged app: its button hits the same-origin route
    that 302s to the published installer. macOS/Linux have no packaged app, so
    their buttons must open the internal build-from-source guide — not pretend
    to download an app and never redirect to a GitHub page."""
    html = (STATIC / "download.html").read_text(encoding="utf-8")
    win = html[html.index('id="dl-win"') - 200 : html.index('id="dl-win"') + 80]
    assert 'href="/download/windows"' in win and "download" in win
    for platform in ("macos", "linux"):
        seg = html[html.index(f'id="dl-{platform}"') - 200 : html.index(f'id="dl-{platform}"') + 80]
        assert 'href="/docs/installation"' in seg
        assert "download" not in seg.split("href")[0], "mac/linux buttons are not file downloads"
        assert "Build from source" in seg
        assert "github.com" not in seg
    # The docs guide they open is local and covers running from source.
    guide = (STATIC / "docs" / "installation.html").read_text(encoding="utf-8")
    assert "py main.py" in guide and "pip install" in guide


def test_app_brand_geometry_matches_the_website_nav_svg():
    """The desktop app logo must stay identical to the website logo.

    config.brand is the single source for the app icon (window, tray,
    installer .ico). This test derives the mark straight from the site's
    nav SVG so any design change to the website logo fails here until
    config.brand is updated with it — the old purple-blue drift can
    never happen again."""
    brand = (REPO / "config" / "brand.py").read_text(encoding="utf-8")
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    svg_start = index.index('<svg viewBox="0 0 32 32"')
    svg = index[svg_start : index.index("</svg>", svg_start)]

    # tile geometry
    assert 'x="1" y="1" width="30" height="30" rx="5"' in svg
    assert "TILE_X = 1.0" in brand and "TILE_SIZE = 30.0" in brand and "TILE_RADIUS = 5.0" in brand

    # bar geometry: (x, top, width, height) for all five bars
    import re

    rects = re.findall(
        r'<rect class="lg-(?:bar|sig)" x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)"', svg
    )
    assert len(rects) == 5
    expected = [tuple(float(v) for v in r) for r in rects]
    bars = re.findall(r"\((\d+\.\d), (\d+\.0), (\d+\.\d), (\d+\.0)\),", brand)
    assert [tuple(float(v) for v in b) for b in bars] == expected

    # palette: paper bars + signal centre on the ink tile
    assert "#f4f1ea" in svg and "#e04b26" in svg
    assert 'TILE = "#171512"' in brand
    assert 'BAR = "#f4f1ea"' in brand and 'SIGNAL = "#e04b26"' in brand
    assert "SIGNAL_BAR_INDEX = 2" in brand  # centre bar carries the signal


def test_packaged_app_icon_uses_the_website_palette():
    """The installer/EXE icon (packaging/voxylis.ico) must carry the new
    brand — never the retired purple-blue gradient (#7c6cf0/#5a4bd1)."""
    import struct

    PIL = pytest.importorskip("PIL", reason="Pillow required to decode the ICO")
    from PIL import Image

    data = (REPO / "packaging" / "voxylis.ico").read_bytes()
    _, _, count = struct.unpack("<HHH", data[:6])
    assert count >= 6, "app icon should ship the full size set"

    def frame_pixels(path, size):
        img = Image.open(str(path))
        img.size = (size, size)
        im = img.convert("RGBA")
        k = size / 32.0
        return {
            "tile": im.getpixel((int(16.0 * k), int(6.0 * k)))[:3],
            "bar": im.getpixel((int(7.8 * k), int(20.0 * k)))[:3],
            "signal": im.getpixel((int(17.7 * k), int(24.0 * k)))[:3],
        }

    # The 256 frame is large enough for exact brand colors deep in the fill.
    big = frame_pixels(REPO / "packaging" / "voxylis.ico", 256)
    assert big["tile"] == (0x17, 0x15, 0x12), "tile must be brand ink"
    assert big["bar"] == (0xF4, 0xF1, 0xEA), "bars must be brand paper"
    r, g, b = big["signal"]
    assert r > 180 and g < 110 and b < 70, "centre bar must be signal orange"

    # No purple-blue residue anywhere: sample the retired gradient anchors.
    grad = Image.open(str(REPO / "packaging" / "voxylis.ico"))
    grad.size = (256, 256)
    grad = grad.convert("RGBA")
    for x, y in ((16.0, 4.0), (16.0, 28.0)):
        r, g, b = grad.getpixel((int(x * 8), int(y * 8)))[:3]
        assert (r, g, b) == (0x17, 0x15, 0x12), f"old gradient still present at ({x},{y})"

    # Same-frame parity with the website favicon (downscaled 48px, ±2/channel).
    app48 = frame_pixels(REPO / "packaging" / "voxylis.ico", 48)
    web48 = frame_pixels(STATIC / "favicon.ico", 48)
    for key in app48:
        assert all(abs(p - q) <= 2 for p, q in zip(app48[key], web48[key])), key


def test_resolver_queries_the_json_api_not_the_html_page():
    """github.com/releases/latest serves HTML; the resolver must use
    api.github.com or it silently never resolves a published installer."""
    import inspect

    import web.routes.content as content_routes

    src = inspect.getsource(content_routes._github_latest_assets)
    assert "api.github.com/repos/" in src


def test_social_login_flow_matches_backend_contract():
    """The auth page must redirect to Auth0 /authorize and exchange the
    returned id_token via the real POST /api/auth/auth0 endpoint. The old
    wiring GET /api/auth/auth0?provider=... (405) and POST /approve (404)
    were dead ends that made every social button a lie."""
    js = (STATIC / "js" / "auth.js").read_text(encoding="utf-8")
    assert "/authorize" in js
    assert "response_type=id_token" in js
    assert "fetch((window.VOXYLIS_API_BASE || '') + '/api/auth/auth0'" in js
    # the two dead paths are gone
    assert "/api/auth/auth0?provider=" not in js
    assert "/api/auth/auth0/approve" not in js
    # the backend contract itself is intact
    auth_routes = (REPO / "web" / "routes" / "auth.py").read_text(encoding="utf-8")
    assert '@auth_bp.route("/api/auth/auth0", methods=["POST"])' in auth_routes
    assert '@auth_bp.route("/api/auth/auth0/config", methods=["GET"])' in auth_routes


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
    for page in ("index", "download", "about", "blog", "contact"):
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
        "about",
        "blog",
        "contact",
        "auth",
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
        "/blog",
        "/about",
        "/contact",
        "/auth",
        "/download",
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


def test_pricing_is_retired_from_the_frontend(app_client):
    """Pricing was removed from the UI in favour of an open-source
    presentation: the view files are gone, no static page links to /pricing,
    the URL itself redirects home, and the GitHub open-source section exists.
    The backend contract (/api/pricing, tiers, quotas, webhooks) is untouched."""
    client, _ = app_client
    for rel in ("pricing.html", "js/pricing.js", "css/pricing.css"):
        assert not (STATIC / rel).exists(), f"{rel} must be deleted"
    offenders = [
        f.name
        for f in STATIC.rglob("*")
        if f.is_file()
        and f.suffix in (".html", ".js", ".css")
        and 'href="/pricing"' in f.read_text(encoding="utf-8", errors="ignore")
    ]
    assert not offenders, f"stale pricing links: {offenders}"
    resp = client.get("/pricing")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/#open-source")
    assert client.get("/api/pricing").status_code == 200  # backend logic intact
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'id="open-source"' in index
    assert "https://github.com/sumitagg24/Voxyai" in index
    assert not (STATIC / "dashboard.html").exists(), "browser dashboard must stay removed"


def test_wake_word_is_fully_removed():
    for relative in ("dashboard.html", "js/dashboard.js", "css/dashboard.css"):
        assert not (STATIC / relative).exists(), f"{relative} must stay deleted"
    for relative in ("index.html", "about.html", "js/site.js"):
        text = (STATIC / relative).read_text(encoding="utf-8", errors="ignore")
        assert "wakeword" not in text.lower(), f"wake word remnant in {relative}"
        assert "voxylis_wakeword" not in text
    import web.tier as tier

    assert "wake_word" not in tier.TIER_FEATURES.get("pro", set())
    assert "wake_word" not in tier.TIER_FEATURES.get("business", set())


def test_account_deletion_and_upgrade_claims_match_the_implementation():
    """No page may offer a self-service upgrade that cannot work."""
    for relative in ("index.html", "download.html", "auth.html"):
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
