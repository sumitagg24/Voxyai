"""Content blueprint: blog/pricing/features/download/contact/newsletter/health (moved from web/app.py)."""

import logging
import os
import re
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_limiter.util import get_remote_address

from web import observability
from web.auth_helpers import _json_body, _text, normalize_email
from web.content.blog_posts import LEGACY_BLOG_SLUGS
from web.db import _get_db
from web.extensions import cache, limiter
from web.services import email_preferences, email_service, subscription_service
from config.version import APP_NAME, ENGINE_NAME, RELEASES_URL, REPO_URL as REPOSITORY_URL
from config.version import __version__ as APP_VERSION

import requests as http_requests

logger = logging.getLogger(__name__)

content_bp = Blueprint("content", __name__)


RELEASES_PAGE_URL = RELEASES_URL


_DOWNLOAD_CACHE: dict = {"at": 0.0, "payload": None}


def _github_latest_assets():
    """Return {asset_name: download_url} for the latest GitHub release.

    Cached 1h; any failure returns {} so the endpoint degrades to env
    overrides + releases-page fallback instead of 500ing.
    """
    import time as _time

    now = _time.time()
    cached = _DOWNLOAD_CACHE.get("payload")
    if cached is not None and now - float(_DOWNLOAD_CACHE.get("at", 0)) < 3600:
        return cached
    assets: dict = {}
    try:
        resp = http_requests.get(
            f"{REPOSITORY_URL}/releases/latest",
            headers={"Accept": "application/vnd.github+json"},
            timeout=10,
        )
        if resp.status_code == 200:
            try:
                data = resp.json()
            except ValueError:
                data = {}
            for asset in data.get("assets", []) or []:
                name = asset.get("name") or ""
                url = asset.get("browser_download_url") or ""
                if name and url:
                    assets[name] = url
    except Exception as exc:
        logger.warning("GitHub latest-release lookup failed: %s", exc)
    _DOWNLOAD_CACHE["at"] = now
    _DOWNLOAD_CACHE["payload"] = assets
    return assets


@content_bp.route("/api/download/urls", methods=["GET"])
def download_urls():
    """Resolve real download targets, and say plainly which ones exist.

    v3.0.0 IS published: the latest release assets are resolved via the
    GitHub API (cached 1h). DOWNLOAD_URL_* env vars override any platform
    when set. ``available`` lets the page tell the truth instead of guessing.
    """
    windows = (os.environ.get("DOWNLOAD_URL_WINDOWS") or "").strip()
    macos = (os.environ.get("DOWNLOAD_URL_MACOS") or "").strip()
    linux = (os.environ.get("DOWNLOAD_URL_LINUX") or "").strip()
    if not (windows and macos and linux):
        github_assets = _github_latest_assets()
        if not windows:
            for name, url in github_assets.items():
                lower = name.lower()
                if lower.endswith(".exe") and ("setup" in lower or "voxylis" in lower):
                    windows = url
                    break
        if not macos:
            for name, url in github_assets.items():
                lower = name.lower()
                if lower.endswith(".zip") or (lower.endswith(".dmg")):
                    macos = url
                    break
        if not linux:
            for name, url in github_assets.items():
                lower = name.lower()
                if lower.endswith(".tar.gz") or lower.endswith(".AppImage") or lower.endswith(".deb"):
                    linux = url
                    break
    return jsonify(
        {
            "windows": windows or RELEASES_PAGE_URL,
            "macos": macos or f"{REPOSITORY_URL}#macos-installation",
            "linux": linux or f"{REPOSITORY_URL}#linux-installation",
            "available": {
                "windows": bool(windows),
                "macos": bool(macos),
                "linux": bool(linux),
            },
            "releases_url": RELEASES_PAGE_URL,
        }
    )


@content_bp.route("/api/download/detect", methods=["GET"])
def download_detect():
    ua = request.headers.get("User-Agent", "").lower()
    if "windows" in ua or "win32" in ua or "win64" in ua:
        platform = "windows"
    elif "macintosh" in ua or "mac os" in ua or "darwin" in ua:
        platform = "macos"
    elif "linux" in ua or "x11" in ua:
        platform = "linux"
    else:
        platform = "unknown"

    return jsonify({"platform": platform})


@content_bp.route("/api/blog", methods=["GET"])
def blog_list():
    conn = _get_db()
    rows = conn.execute(
        "SELECT slug, title, date, category, excerpt, read_time " "FROM blog_posts ORDER BY date DESC"
    ).fetchall()
    conn.close()

    posts = [
        {
            "slug": r["slug"],
            "title": r["title"],
            "date": r["date"],
            "category": r["category"],
            "excerpt": r["excerpt"],
            "read_time": r["read_time"],
        }
        for r in rows
    ]
    return jsonify({"status": "success", "posts": posts})


@content_bp.route("/api/blog/<slug>", methods=["GET"])
def blog_post(slug):
    slug = LEGACY_BLOG_SLUGS.get(slug, slug)
    conn = _get_db()
    row = conn.execute(
        "SELECT slug, title, date, category, excerpt, content, read_time " "FROM blog_posts WHERE slug = ?",
        (slug,),
    ).fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "Post not found"}), 404

    return jsonify(
        {
            "status": "success",
            "post": {
                "slug": row["slug"],
                "title": row["title"],
                "date": row["date"],
                "category": row["category"],
                "excerpt": row["excerpt"],
                "content": row["content"],
                "read_time": row["read_time"],
            },
        }
    )


@content_bp.route("/api/download/track", methods=["POST", "GET"])
@limiter.limit("60 per minute", key_func=get_remote_address)
def download_track():
    """Track download clicks (lightweight counter)."""
    data = _json_body()
    raw_platform = str(data.get("platform", request.args.get("platform", "unknown")) or "unknown")
    platform = raw_platform.strip().lower()[:32]
    if not re.fullmatch(r"[a-z0-9_-]{0,32}", platform):
        platform = "unknown"
    if not platform:
        platform = "unknown"
    conn = _get_db()
    try:
        # download_events is created by schema migration 12 (web.db), not here.
        conn.execute("INSERT INTO download_events (platform) VALUES (?)", (platform,))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()
    return jsonify({"success": True})


@content_bp.route("/version.json", methods=["GET"])
def version_json():
    """Serve the canonical version to the website.

    Flask serves web/static itself, but the explicit route keeps
    /version.json working regardless of static-file handling.
    """
    return jsonify(
        {
            "version": APP_VERSION,
            "name": APP_NAME,
            "engine": ENGINE_NAME,
            "released": "stable",
            "releases_url": RELEASES_URL,
        }
    )


@content_bp.route("/api/public-config", methods=["GET"])
def public_config():
    """Non-secret runtime configuration for the browser bundle.

    Only values that are safe to publish are returned. The Sentry *browser* DSN
    is public by design; the server DSN and every credential stay server-side.
    """
    return jsonify(
        {
            "version": APP_VERSION,
            "environment": subscription_service.environment(),
            "sentry_dsn": observability.browser_dsn(),
            "sentry_release": observability.release_name(),
        }
    )


@content_bp.route("/api/health", methods=["GET"])
def health():
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": APP_VERSION,
            "subscription_policy": subscription_service.describe_policy(),
            "email": email_service.describe_configuration(),
            "monitoring": observability.status(),
        }
    )


@content_bp.route("/api/contact", methods=["POST"])
@limiter.limit("10 per hour", key_func=get_remote_address)
def contact_submit():
    data = _json_body()
    name = _text(data.get("name"))
    email = _text(data.get("email"))
    subject = _text(data.get("subject"))
    message = _text(data.get("message"))

    if not name or not email or not message:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Name, email, and message are required",
                }
            ),
            400,
        )

    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return jsonify({"success": False, "error": "Invalid email address"}), 400

    conn = _get_db()
    # Store raw strings (no HTML-escaping at rest): contact_notification email
    # templates escape at render time via html.escape, so persisting escaped
    # entities would double-escape and corrupt the stored message.
    conn.execute(
        "INSERT INTO contact_messages (name, email, subject, message) VALUES (?, ?, ?, ?)",
        (name, email, subject, message),
    )
    conn.commit()
    conn.close()

    # The database is the source of truth; the email is a convenience copy so a
    # message is not missed when nobody opens the admin console.
    # Templates escape at render time, so pass raw values here.
    email_service.send_transactional(
        "contact_notification",
        email_service.support_address(),
        {
            "name": name,
            "from_email": email,
            "subject": subject,
            "message": message,
        },
    )

    return jsonify({"success": True, "message": "Message received. We'll get back to you shortly."})


@content_bp.route("/api/newsletter", methods=["POST"])
@limiter.limit("10 per hour", key_func=get_remote_address)
def newsletter_subscribe():
    data = _json_body()
    email = normalize_email(_text(data.get("email")))

    if not email:
        return jsonify({"success": False, "error": "Email is required"}), 400

    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return jsonify({"success": False, "error": "Invalid email address"}), 400

    conn = _get_db()
    existing = conn.execute("SELECT id FROM newsletter_subscribers WHERE LOWER(email) = LOWER(?)", (email,)).fetchone()
    if existing:
        conn.close()
        return jsonify({"success": True, "message": "You are already subscribed."})

    conn.execute("INSERT INTO newsletter_subscribers (email) VALUES (?)", (email,))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Subscribed successfully!"})


@content_bp.route("/unsubscribe", methods=["GET", "POST"])
def unsubscribe():
    """One-click opt-out of product news from a link in an email.

    Signed, so it works without a session; invalid or edited links are refused
    rather than silently opting somebody out.
    """
    token = (request.args.get("token") or "").strip()
    if not token and request.is_json:
        token = (_json_body().get("token") or "").strip()

    masked = None
    conn = _get_db()
    try:
        masked = email_preferences.opt_out_by_token(conn, token)
        if masked is not None:
            conn.commit()
    finally:
        conn.close()

    if request.args.get("format") == "json" or request.is_json:
        if masked is None:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "This unsubscribe link is invalid or has expired.",
                    }
                ),
                400,
            )
        return jsonify({"success": True, "message": "You will no longer receive product news."})

    if masked is None:
        body = (
            "<h1>Link not valid</h1><p>This unsubscribe link is invalid or has expired. "
            "Reply to any Voxylis email and we will remove you manually.</p>"
        )
        return body, 400
    return (
        "<h1>Unsubscribed</h1>"
        f"<p>{masked} will no longer receive Voxylis product news. "
        "Account and security messages are unaffected.</p>"
    ), 200


@content_bp.route("/api/features", methods=["GET"])
@cache.cached(timeout=3600)
def get_features():
    return jsonify(
        {
            "status": "success",
            "features": [
                {"id": 1, "name": "Voice-to-Text", "description": "Accurate speech recognition", "icon": "\U0001f3a4"},
                {"id": 2, "name": "AI Enhancement", "description": "Smart text improvement", "icon": "\u2728"},
                {"id": 3, "name": "Q&A Feature", "description": "Instant answers", "icon": "\U0001f916"},
                {"id": 4, "name": "Custom Hotkeys", "description": "Personalized shortcuts", "icon": "\u2328\ufe0f"},
                {
                    "id": 5,
                    "name": "Multi-Language",
                    "description": "Recognises the languages your speech provider supports",
                    "icon": "\U0001f30d",
                },
                {
                    "id": 6,
                    "name": "Local History",
                    "description": "Export and delete your transcripts anytime",
                    "icon": "\U0001f4c4",
                },
                {"id": 7, "name": "Privacy First", "description": "Your data, your control", "icon": "\U0001f512"},
            ],
        }
    )


@content_bp.route("/api/pricing", methods=["GET"])
@cache.cached(timeout=3600)
def get_pricing():
    from web.tier import pricing_payload

    return jsonify(pricing_payload())
