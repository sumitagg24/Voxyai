"""Static pages blueprint (moved from web/app.py)."""

import os

from flask import Blueprint, current_app, jsonify, redirect, send_from_directory, url_for

from web.content.blog_posts import LEGACY_BLOG_SLUGS
from web.db import _get_db

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    return current_app.send_static_file("index.html")


@pages_bp.route("/pricing")
def pricing_page():
    return current_app.send_static_file("pricing.html")


@pages_bp.route("/blog")
def blog_page():
    return current_app.send_static_file("blog.html")


@pages_bp.route("/about")
def about_page():
    return current_app.send_static_file("about.html")


@pages_bp.route("/contact")
def contact_page():
    return current_app.send_static_file("contact.html")


@pages_bp.route("/privacy")
def privacy_page():
    return current_app.send_static_file("privacy.html")


@pages_bp.route("/terms")
def terms_page():
    return current_app.send_static_file("terms.html")


@pages_bp.route("/auth")
def auth_page():
    return current_app.send_static_file("auth.html")


@pages_bp.route("/download")
def download_page():
    return current_app.send_static_file("download.html")


@pages_bp.route("/dashboard")
def dashboard():
    return current_app.send_static_file("dashboard.html")


@pages_bp.route("/favicon.ico")
def favicon():
    """Browsers request /favicon.ico by convention; the file lives in static/."""
    return current_app.send_static_file("favicon.ico")


@pages_bp.route("/apple-touch-icon.png")
def apple_touch_icon():
    """Every page links /apple-touch-icon.png at the root (iOS home-screen
    icon); without this route every page load logs a 404 console error."""
    return current_app.send_static_file("apple-touch-icon.png")


@pages_bp.route("/og-image.png")
def og_image():
    """Open Graph images are referenced from the site root; serve it there."""
    return current_app.send_static_file("og-image.png")


@pages_bp.route("/docs/<page>")
def docs(page):
    valid_pages = [
        "installation",
        "configuration",
        "voice-commands",
        "qa-feature",
        "troubleshooting",
        "tips-tricks",
    ]
    if page in valid_pages:
        return send_from_directory(os.path.join(current_app.static_folder, "docs"), f"{page}.html")
    return jsonify({"error": "Page not found"}), 404


@pages_bp.route("/blog/<slug>")
def blog_post_page(slug):
    """Serve the single blog post page, or a real 404 for unknown slugs.

    The page used to render for any slug and let JS reveal a not-found state,
    which returned HTTP 200 for misspelled URLs (a soft 404 for crawlers).
    """
    replacement = LEGACY_BLOG_SLUGS.get(slug)
    if replacement:
        return redirect(url_for("pages.blog_post_page", slug=replacement), code=301)
    conn = _get_db()
    try:
        row = conn.execute("SELECT 1 FROM blog_posts WHERE slug = ?", (slug,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return current_app.send_static_file("404.html"), 404
    return current_app.send_static_file("blog-post.html")
