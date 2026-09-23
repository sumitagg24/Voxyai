"""Version consistency, website routes and marketing-claim guardrails."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from config import version

REPO = Path(__file__).resolve().parent.parent
STATIC = REPO / "web" / "static"


# ── one canonical version ────────────────────────────────────────────────────


def test_version_is_semantic():
    assert re.fullmatch(r"\d+\.\d+\.\d+", version.__version__)
    assert version.version_tag() == f"v{version.__version__}"


def test_generated_mirrors_match_the_canonical_version():
    version.sync()
    assert f"FileVersion', u'{version.__version__}'" in (
        REPO / "packaging" / "version_info.txt"
    ).read_text(encoding="utf-8")
    for target in (STATIC / "version.json", REPO / "web" / "downloads" / "version.json"):
        payload = json.loads(target.read_text(encoding="utf-8"))
        assert payload["version"] == version.__version__


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


def test_download_page_reads_the_version_from_one_source():
    text = (STATIC / "download.html").read_text(encoding="utf-8")
    assert "data-voxylis-version" in text
    assert "/version.json" in text
    assert not re.search(r"v2\.\d\.\d", text)


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
        "/docs/installation",
        "/docs/configuration",
        "/docs/troubleshooting",
        "/static/css/base.css",
        "/static/js/api.js",
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


def test_wake_word_is_labelled_as_a_browser_preview():
    text = (STATIC / "dashboard.html").read_text(encoding="utf-8")
    assert "browser preview" in text
    assert "not implemented in the Windows build" in text


def test_account_deletion_and_upgrade_claims_match_the_implementation():
    """The dashboard must not offer a self-service upgrade that cannot work."""
    for relative in ("dashboard.html", "js/dashboard.js"):
        text = (STATIC / relative).read_text(encoding="utf-8")
        assert "subscription/upgrade" not in text
