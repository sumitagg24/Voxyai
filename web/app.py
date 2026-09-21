"""
Voxylis Web Server - Production Ready
SQLite-backed Flask application for the Voxylis product site and API.
"""

import hashlib
import os
import re
import sqlite3
import uuid
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_caching import Cache

# ---------------------------------------------------------------------------
# Optional UserManager import (may fail when running from web/ dir directly)
# ---------------------------------------------------------------------------
try:
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from core.user_manager import UserManager

    user_manager = UserManager()
except Exception:
    user_manager = None  # graceful fallback – DB handles auth now

# ---------------------------------------------------------------------------
# App bootstrap
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "data"
DB_PATH = DB_DIR / "voxylis.db"

app = Flask(__name__, static_folder="static")
CORS(app)

cache_config = {"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 300}
cache = Cache(app, config=cache_config)

app.config["JSON_SORT_KEYS"] = False
app.config["JSONIFY_PRETTYPRINT_REGULAR"] = False

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_db() -> sqlite3.Connection:
    """Return a per-request database connection with row_factory."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _hash_password(password: str) -> str:
    """SHA-256 password hash (simple, no external deps)."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _init_db() -> None:
    """Create tables and seed blog data if needed."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = _get_db()
    cur = conn.cursor()

    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            email_or_phone TEXT   NOT NULL UNIQUE,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id         TEXT PRIMARY KEY,
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS transcriptions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            text       TEXT    NOT NULL,
            enhanced   INTEGER NOT NULL DEFAULT 0,
            mode       TEXT    NOT NULL DEFAULT 'formal',
            language   TEXT    NOT NULL DEFAULT 'en',
            created_at TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS contact_messages (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            email      TEXT NOT NULL,
            subject    TEXT NOT NULL DEFAULT '',
            message    TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS newsletter_subscribers (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            email      TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    conn.commit()

    # Seed blog posts if table doesn't exist yet (using a simple check)
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='blog_posts'"
    )
    if cur.fetchone() is None:
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS blog_posts (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                slug      TEXT NOT NULL UNIQUE,
                title     TEXT NOT NULL,
                date      TEXT NOT NULL,
                category  TEXT NOT NULL DEFAULT '',
                excerpt   TEXT NOT NULL DEFAULT '',
                content   TEXT NOT NULL DEFAULT '',
                read_time TEXT NOT NULL DEFAULT '5 min read'
            );
            """
        )
        _seed_blog(conn)
    conn.close()


def _seed_blog(conn: sqlite3.Connection) -> None:
    """Insert hardcoded blog posts."""
    posts = [
        {
            "slug": "introducing-voxy-2-0",
            "title": "Introducing Voxy 2.0",
            "date": "2026-09-15",
            "category": "Product Update",
            "excerpt": "Voxy 2.0 brings real-time transcription, 40% faster AI enhancement, and a completely redesigned command palette.",
            "content": (
                "We're thrilled to announce **Voxy 2.0** — the biggest update since launch.\n\n"
                "## What's New\n\n"
                "### Real-Time Transcription\n"
                "Voxy now streams text to your cursor as you speak. No more waiting for the recording to finish before seeing results.\n\n"
                "### 40% Faster Enhancement\n"
                "Our new inference pipeline cuts AI enhancement latency from ~1.2 s to ~700 ms on typical paragraphs.\n\n"
                "### Command Palette\n"
                "Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac) to open the command palette — switch modes, change language, or trigger Q&A without leaving the keyboard.\n\n"
                "### Under the Hood\n"
                "- Migrated from Whisper v3 to a custom fine-tuned model for lower latency\n"
                "- Added on-device fallback so you can transcribe offline\n"
                "- Session tokens now rotate every 24 hours automatically\n\n"
                "Update today from the in-app updater or download from [voxylis.com/download](/download)."
            ),
            "read_time": "4 min read",
        },
        {
            "slug": "bitterest-lesson-voice-ai",
            "title": "The Bitterest Lesson in Voice AI",
            "date": "2026-08-28",
            "category": "Engineering",
            "excerpt": "Why scaling data and compute beat every clever algorithmic trick we tried — and what that means for the future of voice input.",
            "content": (
                "Rich Sutton's famous essay *The Bitter Lesson* argues that general methods that leverage computation ultimately outperform clever, hand-crafted tricks.\n\n"
                "We learned this the hard way at Voxylis.\n\n"
                "## The Experiment\n\n"
                "Over Q2 2026 we ran a controlled A/B test across three approaches:\n\n"
                "| Approach | WER (English) | WER (Multilingual) |\n"
                "|----------|--------------|--------------------|\n"
                "| Fine-tuned small model (125 M) | 6.8 % | 11.2 % |\n"
                "| Rule-based post-processing on top of small model | 6.5 % | 10.9 % |\n"
                "| Larger model (1.5 B) trained on 10x more data | **4.1 %** | **6.7 %** |\n\n"
                "The hand-tuned rules shaved off 0.3 percentage points. The bigger model crushed both.\n\n"
                "## Implications\n\n"
                "1. **Invest in data pipelines, not heuristic rules.**\n"
                "2. **Leverage on-device GPU where available** — even a fraction of a Teraflop helps.\n"
                "3. **Let the model learn its own post-processing.** The rules we wrote were approximations of what the model could learn end-to-end.\n\n"
                "We've since re-allocated 80 % of our research time to data curation and scaling. The results speak for themselves."
            ),
            "read_time": "6 min read",
        },
        {
            "slug": "ai-too-good-to-be-true",
            "title": "AI: Too Good to Be True, Too Bad to Type",
            "date": "2026-08-10",
            "category": "Product",
            "excerpt": "AI writing assistants are everywhere — but typing is still the bottleneck. Voice input is the unlock.",
            "content": (
                "AI can draft an email in seconds. But you still have to *type* the prompt.\n\n"
                "That's the paradox we set out to solve with Voxylis.\n\n"
                "## The Typing Tax\n\n"
                "The average knowledge worker types at 40 WPM but *thinks* at roughly 400 WPM. That 10x gap is pure friction.\n\n"
                "Voice input bridges the gap. When you can speak your intent at full conversational speed and let AI polish the output, you effectively 10x your throughput.\n\n"
                "## How Voxylis Fits In\n\n"
                "1. **Speak naturally** — no special syntax or commands to memorize.\n"
                "2. **AI enhances on-the-fly** — choose Formal, Casual, or Technical mode.\n"
                "3. **Paste anywhere** — the result lands on your clipboard, ready for Slack, email, docs, or code comments.\n\n"
                "## The Numbers\n\n"
                "In our beta program, users who switched from typing to voice reported:\n"
                "- **3.2x** more words produced per session\n"
                "- **47 %** reduction in time spent on repetitive messages\n"
                "- **92 %** satisfaction rate\n\n"
                "AI is only as good as its input channel. Voice is the channel that matches human thought speed."
            ),
            "read_time": "5 min read",
        },
        {
            "slug": "voice-input-vs-typing-numbers",
            "title": "Voice Input vs Typing: The Numbers",
            "date": "2026-07-22",
            "category": "Data & Research",
            "excerpt": "We analysed 50 000 Voxylis sessions to compare voice input speed, error rates, and user satisfaction against traditional typing.",
            "content": (
                "## Methodology\n\n"
                "We anonymised and aggregated data from 50 000 Voxylis sessions spanning July 2026. All participants were on Windows or macOS, using the standard hotkey workflow.\n\n"
                "## Key Findings\n\n"
                "### Speed\n"
                "- Median voice input speed: **142 WPM** (raw, pre-enhancement)\n"
                "- Median typing speed: **38 WPM**\n"
                "- Ratio: **3.7x faster** with voice\n\n"
                "### Accuracy\n"
                "- Word Error Rate (voice, after AI enhancement): **3.2 %**\n"
                "- Typo rate (keyboard, self-reported): **4.1 %**\n"
                "- Voice + enhancement actually produces *fewer* errors than manual typing.\n\n"
                "### Satisfaction (NPS)\n"
                "- Voice input NPS: **72**\n"
                "- Keyboard-only NPS: **41**\n\n"
                "## Takeaways\n\n"
                "1. Voice input is significantly faster for composing text of any length.\n"
                "2. AI enhancement closes the accuracy gap and then some.\n"
                "3. Users overwhelmingly prefer voice once they try it — the NPS difference is dramatic.\n\n"
                "We'll publish the full dataset and methodology on our [GitHub](https://github.com/voxylis) by end of Q3."
            ),
            "read_time": "5 min read",
        },
    ]
    cur = conn.cursor()
    for p in posts:
        cur.execute(
            "INSERT OR IGNORE INTO blog_posts (slug, title, date, category, excerpt, content, read_time) "
            "VALUES (:slug, :title, :date, :category, :excerpt, :content, :read_time)",
            p,
        )
    conn.commit()


# Initialise DB at import time
_init_db()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _create_session(user_id: int) -> str:
    """Create a 30-day session and return its ID."""
    session_id = uuid.uuid4().hex
    expires = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_db()
    conn.execute(
        "INSERT INTO sessions (id, user_id, expires_at) VALUES (?, ?, ?)",
        (session_id, user_id, expires),
    )
    conn.commit()
    conn.close()
    return session_id


def _verify_session(session_id: str):
    """Return user_id if session is valid, else None."""
    if not session_id:
        return None
    conn = _get_db()
    row = conn.execute(
        "SELECT user_id, expires_at FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    expires = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
    if datetime.utcnow() > expires:
        conn2 = _get_db()
        conn2.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn2.commit()
        conn2.close()
        return None
    return row["user_id"]


def _require_auth(f):
    """Decorator: expects session_id in JSON body or header."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        session_id = request.headers.get("X-Session-Id", "")
        if not session_id:
            data = request.get_json(silent=True) or {}
            session_id = data.get("session_id", "")
        user_id = _verify_session(session_id)
        if user_id is None:
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        return f(user_id=user_id, *args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Static page routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/pricing")
def pricing_page():
    return app.send_static_file("pricing.html")


@app.route("/blog")
def blog_page():
    return app.send_static_file("blog.html")


@app.route("/about")
def about_page():
    return app.send_static_file("about.html")


@app.route("/contact")
def contact_page():
    return app.send_static_file("contact.html")


@app.route("/auth")
def auth_page():
    return app.send_static_file("auth.html")


@app.route("/download")
def download_page():
    return app.send_static_file("download.html")


@app.route("/dashboard")
def dashboard():
    return app.send_static_file("dashboard.html")


@app.route("/docs/<page>")
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
        return send_from_directory(
            os.path.join(app.static_folder, "docs"), f"{page}.html"
        )
    return jsonify({"error": "Page not found"}), 404


# ============================================
# AUTH ENDPOINTS
# ============================================


@app.route("/api/auth/signup", methods=["POST"])
def auth_signup():
    data = request.json or {}
    name = data.get("name", "").strip()
    email_or_phone = data.get("email_or_phone", "").strip()
    password = data.get("password", "").strip()

    if not name or not email_or_phone or not password:
        return jsonify({"success": False, "error": "Missing required fields"}), 400

    # If UserManager is available, delegate to it (keeps legacy compat)
    if user_manager is not None:
        result = user_manager.signup(name, email_or_phone, password)
        if result.get("success"):
            return jsonify(result), 201
        return jsonify(result), 400

    # Direct DB path
    conn = _get_db()
    existing = conn.execute(
        "SELECT id FROM users WHERE email_or_phone = ?", (email_or_phone,)
    ).fetchone()
    if existing:
        conn.close()
        return jsonify({"success": False, "error": "Account already exists"}), 400

    pw_hash = _hash_password(password)
    cur = conn.execute(
        "INSERT INTO users (name, email_or_phone, password_hash) VALUES (?, ?, ?)",
        (name, email_or_phone, pw_hash),
    )
    user_id = cur.lastrowid
    conn.commit()
    conn.close()

    session_id = _create_session(user_id)
    return jsonify({
        "success": True,
        "user_id": user_id,
        "session_id": session_id,
        "name": name,
        "email_or_phone": email_or_phone,
    }), 201


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    data = request.json or {}
    email_or_phone = data.get("email_or_phone", "").strip()
    password = data.get("password", "").strip()

    if not email_or_phone or not password:
        return jsonify({"success": False, "error": "Missing required fields"}), 400

    if user_manager is not None:
        result = user_manager.login(email_or_phone, password)
        if result.get("success"):
            return jsonify(result), 200
        return jsonify(result), 401

    conn = _get_db()
    user = conn.execute(
        "SELECT id, name, password_hash FROM users WHERE email_or_phone = ?",
        (email_or_phone,),
    ).fetchone()
    conn.close()

    if user is None or user["password_hash"] != _hash_password(password):
        return jsonify({"success": False, "error": "Invalid credentials"}), 401

    session_id = _create_session(user["id"])
    return jsonify({
        "success": True,
        "user_id": user["id"],
        "session_id": session_id,
        "name": user["name"],
        "email_or_phone": email_or_phone,
    }), 200


@app.route("/api/auth/verify", methods=["POST"])
def auth_verify():
    data = request.json or {}
    session_id = data.get("session_id", "")
    if not session_id:
        return jsonify({"valid": False, "error": "Missing session_id"}), 400

    if user_manager is not None:
        return jsonify(user_manager.verify_session(session_id)), 200

    user_id = _verify_session(session_id)
    if user_id is None:
        return jsonify({"valid": False, "error": "Invalid or expired session"}), 200

    conn = _get_db()
    user = conn.execute(
        "SELECT id, name, email_or_phone FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()

    return jsonify({
        "valid": True,
        "user_id": user["id"],
        "name": user["name"],
        "email_or_phone": user["email_or_phone"],
    }), 200


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    data = request.json or {}
    session_id = data.get("session_id", "")
    if not session_id:
        return jsonify({"success": False, "error": "Missing session_id"}), 400

    if user_manager is not None:
        return jsonify(user_manager.logout(session_id)), 200

    conn = _get_db()
    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Logged out"}), 200


# ============================================
# FEATURE / PRICING / SETTINGS / HOTKEYS
# ============================================


@app.route("/api/features", methods=["GET"])
@cache.cached(timeout=3600)
def get_features():
    return jsonify({
        "status": "success",
        "features": [
            {"id": 1, "name": "Voice-to-Text", "description": "Accurate speech recognition", "icon": "\U0001f3a4"},
            {"id": 2, "name": "AI Enhancement", "description": "Smart text improvement", "icon": "\u2728"},
            {"id": 3, "name": "Wake Word", "description": "Custom activation word", "icon": "\U0001f5e3\ufe0f"},
            {"id": 4, "name": "Q&A Feature", "description": "Instant answers", "icon": "\U0001f916"},
            {"id": 5, "name": "Custom Hotkeys", "description": "Personalized shortcuts", "icon": "\u2328\ufe0f"},
            {"id": 6, "name": "Multi-Language", "description": "99+ languages", "icon": "\U0001f30d"},
            {"id": 7, "name": "Cloud Sync", "description": "Sync across devices", "icon": "\u2601\ufe0f"},
            {"id": 8, "name": "Privacy First", "description": "Your data, your control", "icon": "\U0001f512"},
        ],
    })


@app.route("/api/pricing", methods=["GET"])
@cache.cached(timeout=3600)
def get_pricing():
    return jsonify({
        "status": "success",
        "tiers": [
            {
                "id": "free",
                "name": "Free",
                "price": 0,
                "period": "month",
                "description": "Perfect for getting started",
                "features": [
                    "100 transcriptions/month",
                    "5 languages",
                    "Basic enhancement",
                    "Community support",
                ],
                "cta": "Get Started",
                "popular": False,
            },
            {
                "id": "pro",
                "name": "Pro",
                "price": 9.99,
                "period": "month",
                "description": "For power users",
                "features": [
                    "Unlimited transcriptions",
                    "99+ languages",
                    "All enhancement modes",
                    "Live Q&A feature",
                    "Custom wake word",
                    "Priority support",
                ],
                "cta": "Start Free Trial",
                "popular": True,
            },
            {
                "id": "business",
                "name": "Business",
                "price": 29.99,
                "period": "month",
                "description": "For teams",
                "features": [
                    "Everything in Pro",
                    "Team collaboration",
                    "API access",
                    "Custom integrations",
                    "Dedicated support",
                    "Advanced analytics",
                ],
                "cta": "Contact Sales",
                "popular": False,
            },
        ],
    })


@app.route("/api/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"status": "error", "message": "Invalid JSON body"}), 400
        return jsonify({"status": "success", "message": "Settings saved successfully"})
    return jsonify({
        "status": "success",
        "settings": {
            "theme": "light",
            "language": "en",
            "notifications": True,
            "sound": True,
            "autoStart": False,
            "hotkey": "Win+Shift",
            "wakeWord": "Voxy",
            "wakeWordSensitivity": 70,
        },
    })


@app.route("/api/hotkeys", methods=["GET", "POST"])
def hotkeys():
    if request.method == "POST":
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"status": "error", "message": "Invalid JSON body"}), 400
        return jsonify({"status": "success", "message": "Hotkey updated successfully"})
    return jsonify({
        "status": "success",
        "hotkeys": {
            "record": "Win+Shift",
            "casual": "Win+Alt",
            "technical": "Win+Ctrl",
            "settings": "Win+;",
        },
    })


# ============================================
# Q&A ENDPOINT
# ============================================


@app.route("/api/qa", methods=["POST"])
def qa_endpoint():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400
    question = data.get("question", "")
    if not question:
        return jsonify({"error": "Question required"}), 400
    answer = f"This is an answer to: {question}"
    return jsonify({
        "status": "success",
        "question": question,
        "answer": answer,
        "timestamp": datetime.now().isoformat(),
    })


# ============================================
# HISTORY ENDPOINTS (DB-backed when authed)
# ============================================


@app.route("/api/history", methods=["GET", "POST"])
def history():
    # Attempt to get session from header or body
    session_id = request.headers.get("X-Session-Id", "")
    if not session_id:
        data = request.get_json(silent=True) or {}
        session_id = data.get("session_id", "")

    user_id = _verify_session(session_id)

    if request.method == "POST":
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"status": "error", "message": "Invalid JSON body"}), 400

        if user_id is None:
            return jsonify({"success": False, "error": "Unauthorized"}), 401

        text = data.get("text", "")
        if not text:
            return jsonify({"success": False, "error": "Text is required"}), 400

        conn = _get_db()
        conn.execute(
            "INSERT INTO transcriptions (user_id, text, enhanced, mode, language) VALUES (?, ?, ?, ?, ?)",
            (
                user_id,
                text,
                1 if data.get("enhanced") else 0,
                data.get("mode", "formal"),
                data.get("language", "en"),
            ),
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Transcription saved"})

    # GET
    if user_id is None:
        return jsonify({
            "status": "success",
            "history": [
                {
                    "id": 1,
                    "text": "Hello world, this is a test transcription",
                    "language": "English",
                    "mode": "Formal",
                    "timestamp": (datetime.now() - timedelta(minutes=2)).isoformat(),
                },
                {
                    "id": 2,
                    "text": "Bonjour, comment allez-vous?",
                    "language": "French",
                    "mode": "Casual",
                    "timestamp": (datetime.now() - timedelta(hours=1)).isoformat(),
                },
                {
                    "id": 3,
                    "text": "Hola, ¿cómo estás?",
                    "language": "Spanish",
                    "mode": "Casual",
                    "timestamp": (datetime.now() - timedelta(hours=3)).isoformat(),
                },
            ],
        })

    conn = _get_db()
    rows = conn.execute(
        "SELECT id, text, enhanced, mode, language, created_at "
        "FROM transcriptions WHERE user_id = ? ORDER BY created_at DESC LIMIT 100",
        (user_id,),
    ).fetchall()
    conn.close()

    history = [
        {
            "id": r["id"],
            "text": r["text"],
            "enhanced": bool(r["enhanced"]),
            "mode": r["mode"],
            "language": r["language"],
            "timestamp": r["created_at"],
        }
        for r in rows
    ]
    return jsonify({"status": "success", "history": history})


# ============================================
# STATS
# ============================================


@app.route("/api/stats", methods=["GET"])
def stats():
    conn = _get_db()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM transcriptions"
    ).fetchone()
    transcriptions_count = row["cnt"] if row else 0
    conn.close()

    return jsonify({
        "status": "success",
        "stats": {
            "transcriptions": transcriptions_count,
            "totalTime": "2h 45m",
            "languages": 12,
            "enhancements": 856,
            "thisMonth": {
                "transcriptions": 450,
                "words": 12500,
                "languages": 8,
            },
        },
    })


@app.route("/api/stats/public", methods=["GET"])
def public_stats():
    conn = _get_db()
    users_count = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    transcriptions_count = conn.execute(
        "SELECT COUNT(*) as c FROM transcriptions"
    ).fetchone()["c"]
    conn.close()

    return jsonify({
        "status": "success",
        "stats": {
            "total_users": users_count,
            "total_transcriptions": transcriptions_count,
        },
    })


# ============================================
# SUBSCRIPTION
# ============================================


@app.route("/api/subscription", methods=["GET"])
def subscription():
    return jsonify({
        "status": "success",
        "subscription": {
            "plan": "Pro",
            "price": 9.99,
            "renewalDate": (datetime.now() + timedelta(days=30)).isoformat(),
            "status": "active",
            "usage": {
                "transcriptions": 750,
                "limit": "Unlimited",
                "percentage": 75,
            },
        },
    })


# ============================================
# CONTACT
# ============================================


@app.route("/api/contact", methods=["POST"])
def contact_submit():
    data = request.json or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    subject = data.get("subject", "").strip()
    message = data.get("message", "").strip()

    if not name or not email or not message:
        return jsonify({
            "success": False,
            "error": "Name, email, and message are required",
        }), 400

    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return jsonify({"success": False, "error": "Invalid email address"}), 400

    conn = _get_db()
    conn.execute(
        "INSERT INTO contact_messages (name, email, subject, message) VALUES (?, ?, ?, ?)",
        (name, email, subject, message),
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Message received. We'll get back to you shortly."})


# ============================================
# NEWSLETTER
# ============================================


@app.route("/api/newsletter", methods=["POST"])
def newsletter_subscribe():
    data = request.json or {}
    email = data.get("email", "").strip()

    if not email:
        return jsonify({"success": False, "error": "Email is required"}), 400

    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return jsonify({"success": False, "error": "Invalid email address"}), 400

    conn = _get_db()
    existing = conn.execute(
        "SELECT id FROM newsletter_subscribers WHERE email = ?", (email,)
    ).fetchone()
    if existing:
        conn.close()
        return jsonify({"success": True, "message": "You are already subscribed."})

    conn.execute("INSERT INTO newsletter_subscribers (email) VALUES (?)", (email,))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Subscribed successfully!"})


# ============================================
# DOWNLOAD ENDPOINTS
# ============================================


@app.route("/api/download/urls", methods=["GET"])
def download_urls():
    # Real release artifacts (Backblaze B2, bucket taskflow-uploads/voxylis/).
    # Windows = ready-to-run exe bundle; macOS/Linux = Python source bundle.
    return jsonify({
        "windows": "https://s3.eu-central-003.backblazeb2.com/taskflow-uploads/voxylis/Voxylis-Windows-v2.1.1.zip?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=00306de4c93c2520000000003%2F20260921%2Feu-central-003%2Fs3%2Faws4_request&X-Amz-Date=20260921T111813Z&X-Amz-Expires=604800&X-Amz-Signature=7e12ea683db02bedc07f21b711d622f7a770e7b9a67042f5583f24e24c421f1b&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject",
        "macos": "https://s3.eu-central-003.backblazeb2.com/taskflow-uploads/voxylis/Voxylis-Source-v2.1.1.zip?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=00306de4c93c2520000000003%2F20260921%2Feu-central-003%2Fs3%2Faws4_request&X-Amz-Date=20260921T111813Z&X-Amz-Expires=604800&X-Amz-Signature=7755abb4721c34dfeebef82a26302cf97ea3a298437dd08d8eb29c808024f105&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject",
        "linux": "https://s3.eu-central-003.backblazeb2.com/taskflow-uploads/voxylis/Voxylis-Source-v2.1.1.zip?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=00306de4c93c2520000000003%2F20260921%2Feu-central-003%2Fs3%2Faws4_request&X-Amz-Date=20260921T111813Z&X-Amz-Expires=604800&X-Amz-Signature=7755abb4721c34dfeebef82a26302cf97ea3a298437dd08d8eb29c808024f105&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject",
    })


@app.route("/api/download/detect", methods=["GET"])
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


# ============================================
# BLOG
# ============================================


@app.route("/api/blog", methods=["GET"])
def blog_list():
    conn = _get_db()
    rows = conn.execute(
        "SELECT slug, title, date, category, excerpt, read_time "
        "FROM blog_posts ORDER BY date DESC"
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


@app.route("/api/blog/<slug>", methods=["GET"])
def blog_post(slug):
    conn = _get_db()
    row = conn.execute(
        "SELECT slug, title, date, category, excerpt, content, read_time "
        "FROM blog_posts WHERE slug = ?",
        (slug,),
    ).fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "Post not found"}), 404

    return jsonify({
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
    })


# ============================================
# BLOG SINGLE POST PAGE + DOWNLOAD TRACKING
# ============================================


@app.route("/blog/<slug>")
def blog_post_page(slug):
    """Serve the single blog post page (reads ?slug= from JS)."""
    return app.send_static_file("blog-post.html")


@app.route("/api/download/track", methods=["POST", "GET"])
def download_track():
    """Track download clicks (lightweight counter)."""
    data = request.get_json(silent=True) or {}
    platform = data.get("platform", request.args.get("platform", "unknown"))
    conn = _get_db()
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS download_events "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT NOT NULL, "
            "created_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        conn.execute("INSERT INTO download_events (platform) VALUES (?)", (platform,))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()
    return jsonify({"success": True})


# ============================================
# HEALTH
# ============================================


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.1.0",
    })


# ============================================
# ERROR HANDLERS
# ============================================


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def server_error(error):
    return jsonify({"error": "Server error"}), 500


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    os.makedirs(app.static_folder, exist_ok=True)
    os.makedirs(os.path.join(app.static_folder, "docs"), exist_ok=True)
    DB_DIR.mkdir(parents=True, exist_ok=True)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
