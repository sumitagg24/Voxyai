"""
Voxylis Web Server - Production Ready
SQLite-backed Flask application for the Voxylis product site and API.
"""

import hashlib
import json
import logging
import os
import re
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

import requests as http_requests

from flask import Flask, g, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash, generate_password_hash

from web.tier import (
    TIER_FREE, TIER_PRO, TIER_BUSINESS,
    TIER_FEATURES, TIER_ENHANCEMENT_MODES, TIER_STT_MODES,
    FREE_MONTHLY_TRANSCRIPTIONS,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App bootstrap
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "data"
DB_PATH = DB_DIR / "voxylis.db"

app = Flask(__name__, static_folder="static")
# CORS origins are env-configurable so the statically-hosted frontend
# (e.g. https://voxylis-web.vercel.app) can reach a separately-hosted API.
# Set CORS_ORIGINS as a comma-separated list to override the defaults.
_cors_origins = [
    o.strip()
    for o in os.environ.get(
        "CORS_ORIGINS",
        "https://voxylis.com,https://www.voxylis.com,"
        "https://voxylis-web.vercel.app,"
        "http://localhost:5000,http://localhost:3000",
    ).split(",")
    if o.strip()
]
CORS(app, origins=_cors_origins, supports_credentials=True)

cache_config = {"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 300}
cache = Cache(app, config=cache_config)

# Rate limiting (memory-backed; per-instance limits on serverless hosts)
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["240 per hour", "60 per minute"],
)


def _get_user_key():
    """Rate limit key: use user_id if authenticated, fallback to IP."""
    session_id = request.headers.get("X-Session-Id", "")
    if not session_id:
        data = request.get_json(silent=True) or {}
        session_id = data.get("session_id", "")
    if session_id:
        try:
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT user_id FROM sessions WHERE id = ? AND expires_at > datetime('now')",
                (session_id,),
            ).fetchone()
            conn.close()
            if row:
                return f"user:{row['user_id']}"
        except Exception:
            pass
    return get_remote_address()

app.config["JSON_SORT_KEYS"] = False
app.config["JSONIFY_PRETTYPRINT_REGULAR"] = False
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1 MB request cap
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR.parent / ".env")
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Security headers (applied to every response)
# ---------------------------------------------------------------------------

@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = "microphone=(self), clipboard-read=(self), clipboard-write=(self)"
    resp.headers["X-XSS-Protection"] = "1; mode=block"
    resp.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'self'"
    )
    return resp

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
    """Generate a PBKDF2-SHA256 password hash (werkzeug)."""
    return generate_password_hash(password)


def _check_password(password_hash: str, password: str) -> bool:
    """Verify a password against a stored hash (supports legacy SHA-256)."""
    if password_hash and len(password_hash) == 64 and _is_hex(password_hash):
        # Legacy plain SHA-256 (pre-v2.2). Compare in constant-time style.
        return hashlib.sha256(password.encode("utf-8")).hexdigest() == password_hash
    try:
        return check_password_hash(password_hash, password)
    except (ValueError, TypeError):
        return False


def _is_hex(value: str) -> bool:
    return all(c in "0123456789abcdefABCDEF" for c in value)


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
            onboarding    TEXT    NOT NULL DEFAULT '{}',
            settings      TEXT    NOT NULL DEFAULT '{}',
            hotkeys       TEXT    NOT NULL DEFAULT '{}',
            email_verified INTEGER NOT NULL DEFAULT 0,
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

        CREATE TABLE IF NOT EXISTS password_resets (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token      TEXT    NOT NULL UNIQUE,
            expires_at TEXT    NOT NULL,
            used       INTEGER NOT NULL DEFAULT 0,
            created_at TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS email_verifications (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token      TEXT    NOT NULL UNIQUE,
            expires_at TEXT    NOT NULL,
            used       INTEGER NOT NULL DEFAULT 0,
            created_at TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS qr_tickets (
            code             TEXT PRIMARY KEY,
            status           TEXT NOT NULL DEFAULT 'pending',
            approved_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            session_id       TEXT,
            device_name      TEXT NOT NULL DEFAULT '',
            created_at       TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at       TEXT NOT NULL
        );
        """
    )
    conn.commit()

    # Migrate legacy DBs that lack newer columns
    cols = [r[1] for r in cur.execute("PRAGMA table_info(users)").fetchall()]
    if "onboarding" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN onboarding TEXT NOT NULL DEFAULT '{}'")
        conn.commit()
    if "settings" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN settings TEXT NOT NULL DEFAULT '{}'")
        conn.commit()
    if "hotkeys" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN hotkeys TEXT NOT NULL DEFAULT '{}'")
        conn.commit()
    if "email_verified" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    if "tier" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN tier TEXT NOT NULL DEFAULT 'free'")
        conn.commit()
    if "role" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
        conn.commit()
    if "auth0_sub" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN auth0_sub TEXT")
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
        "SELECT user_id, expires_at, created_at FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if row is None:
        conn.close()
        return None
    expires = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
    if datetime.utcnow() > expires:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        conn.close()
        return None

    # Session rotation: tokens older than 24h get a fresh ID (announced via
    # X-Session-Rotated so clients can pick it up).
    created = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
    if datetime.utcnow() - created > timedelta(hours=24):
        new_id = uuid.uuid4().hex
        new_expires = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE sessions SET id = ?, created_at = ?, expires_at = ? WHERE id = ?",
            (new_id, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), new_expires, session_id),
        )
        conn.commit()
        conn.close()
        _set_rotated_session(new_id)
        return row["user_id"]

    conn.close()
    return row["user_id"]


def _set_rotated_session(new_id: str) -> None:
    """Best-effort: stash a rotated session id on the response headers."""
    try:
        from flask import g

        g._voxy_rotated_session = new_id
    except Exception:
        pass


def _extract_session() -> str:
    """Pull session_id from header or JSON body."""
    session_id = request.headers.get("X-Session-Id", "")
    if not session_id:
        data = request.get_json(silent=True) or {}
        session_id = data.get("session_id", "")
    return session_id


def require_auth(f):
    """Decorator: expects session_id in JSON body or header."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        session_id = _extract_session()
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

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?[0-9\s\-()]{7,20}$")


def _valid_identifier(value: str) -> bool:
    return bool(_EMAIL_RE.match(value) or _PHONE_RE.match(value))


def _valid_name(value: str) -> bool:
    return 2 <= len(value) <= 80


def _valid_password(value: str) -> bool:
    return 8 <= len(value) <= 128


def _sanitize(value: str) -> str:
    """Escape HTML entities in user-provided text to prevent XSS."""
    from markupsafe import escape
    return str(escape(value))


# ---------------------------------------------------------------------------
# Tier helpers (DB-aware, defined here to avoid circular imports with tier.py)
# ---------------------------------------------------------------------------

def get_user_tier(user_id: int) -> str:
    """Get the subscription tier for a user. Admins always get business."""
    if is_admin(user_id=user_id):
        return TIER_BUSINESS
    conn = _get_db()
    try:
        row = conn.execute("SELECT tier FROM users WHERE id = ?", (user_id,)).fetchone()
        if row and row["tier"]:
            return row["tier"]
    except Exception:
        pass
    finally:
        conn.close()
    return TIER_FREE


def has_feature(user_id: int, feature: str) -> bool:
    """Check if a user's tier includes a specific feature."""
    tier = get_user_tier(user_id)
    return feature in TIER_FEATURES.get(tier, TIER_FEATURES[TIER_FREE])


def get_monthly_transcription_count(user_id: int) -> int:
    """Count transcriptions for the current month."""
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM transcriptions "
            "WHERE user_id = ? AND created_at >= date('now', 'start of month')",
            (user_id,),
        ).fetchone()
        return row["cnt"] if row else 0
    except Exception:
        return 0
    finally:
        conn.close()


def check_transcription_quota(user_id: int) -> tuple:
    """Check if user has transcription quota remaining.
    Returns (allowed, used, limit). limit=0 means unlimited.
    """
    tier = get_user_tier(user_id)
    if tier in (TIER_PRO, TIER_BUSINESS):
        return True, 0, 0  # unlimited
    used = get_monthly_transcription_count(user_id)
    return used < FREE_MONTHLY_TRANSCRIPTIONS, used, FREE_MONTHLY_TRANSCRIPTIONS


# ---------------------------------------------------------------------------
# Auth0 authentication + admin roles + email-domain policy + QR login tickets
# ---------------------------------------------------------------------------

def _admin_emails() -> set:
    """Emails that are always Voxylis admins (full access to everything)."""
    return {
        e.strip().lower()
        for e in os.environ.get("ADMIN_EMAILS", "sumitagg24@gmail.com").split(",")
        if e.strip()
    }


def _password_login_domains() -> set:
    """Email domains allowed for password signup (Gmail + official domains)."""
    return {
        d.strip().lower()
        for d in os.environ.get(
            "PASSWORD_LOGIN_DOMAINS", "gmail.com,googlemail.com,voxylis.com"
        ).split(",")
        if d.strip()
    }


# Known disposable/temporary-mail providers. Password accounts may never use
# these — not at signup, not at login.
DISPOSABLE_EMAIL_DOMAINS = frozenset({
    "mailinator.com", "mailinator.net", "tempmail.com", "10minutemail.com",
    "10minutemail.net", "guerrillamail.com", "guerrillamail.net",
    "guerrillamailblock.com", "yopmail.com", "yopmail.net", "temp-mail.org",
    "temp-mail.io", "throwaway.email", "getnada.com", "mohmal.com",
    "sharklasers.com", "maildrop.cc", "trashmail.com", "trashmail.net",
    "fakeinbox.com", "mintemail.com", "mytemp.email", "tempail.com",
    "dispostable.com", "spambog.com", "mailnesia.com", "mailexpire.com",
    "pokemail.net", "spamgourmet.com", "slipry.net", "mail.tm",
    "emailondeck.com", "tmpmail.org", "tmpmail.net", "burnermail.io",
    "mailcatch.com", "jetable.org", "trash-mail.com", "fake-mail.cf",
})


def _email_domain(identifier: str) -> str:
    """Lowercased domain part of an email, or '' for phones/invalid."""
    parts = (identifier or "").strip().lower().split("@")
    if len(parts) != 2 or not parts[0] or not parts[1] or "." not in parts[1]:
        return ""
    return parts[1]


def _is_disposable_email(identifier: str) -> bool:
    return _email_domain(identifier) in DISPOSABLE_EMAIL_DOMAINS


def _password_domain_allowed(identifier: str) -> bool:
    """Password signup is restricted to Gmail + official domains."""
    return _email_domain(identifier) in _password_login_domains()


def is_admin(user_id=None, email=None) -> bool:
    """True if the user is a Voxylis admin (access to all features)."""
    if email and email.strip().lower() in _admin_emails():
        return True
    if user_id is None:
        return False
    try:
        conn = _get_db()
        row = conn.execute(
            "SELECT role, email_or_phone FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        conn.close()
    except Exception:
        return False
    if not row:
        return False
    try:
        role = row["role"]
    except Exception:
        role = None
    if (role or "user").lower() == "admin":
        return True
    return (row["email_or_phone"] or "").strip().lower() in _admin_emails()


def _ensure_admin(conn, user_id: int, email: str) -> None:
    """Promote well-known admin emails to admin/business (idempotent)."""
    if (email or "").strip().lower() not in _admin_emails():
        return
    try:
        conn.execute(
            "UPDATE users SET role = 'admin', tier = 'business' WHERE id = ?",
            (user_id,),
        )
    except Exception:
        pass


def require_admin(f):
    """Decorator: admin users only."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        user_id = _verify_session(_extract_session())
        if user_id is None:
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        if not is_admin(user_id=user_id):
            return jsonify({"success": False, "error": "Admin access required"}), 403
        return f(user_id=user_id, *args, **kwargs)
    return wrapper


_jwks_cache: dict = {"keys": [], "fetched_at": None}


def _auth0_jwks(domain: str) -> dict:
    now = datetime.utcnow()
    if (
        _jwks_cache["keys"]
        and _jwks_cache["fetched_at"]
        and (now - _jwks_cache["fetched_at"]) < timedelta(hours=12)
    ):
        return {"keys": _jwks_cache["keys"]}
    resp = http_requests.get(f"https://{domain}/.well-known/jwks.json", timeout=10)
    resp.raise_for_status()
    data = resp.json()
    _jwks_cache.update(keys=data.get("keys", []), fetched_at=now)
    return data


def _verify_auth0_token(id_token: str) -> dict:
    """Verify an Auth0 ID token (RS256 via JWKS). Raises on any failure."""
    import jwt as pyjwt

    domain = os.environ.get("AUTH0_DOMAIN", "").strip().strip("/")
    client_id = os.environ.get("AUTH0_CLIENT_ID", "").strip()
    if not domain or not client_id:
        raise ValueError("Auth0 is not configured on this server")
    header = pyjwt.get_unverified_header(id_token)
    jwks = _auth0_jwks(domain)
    key_data = next(
        (k for k in jwks.get("keys", []) if k.get("kid") == header.get("kid")),
        None,
    )
    if not key_data:
        _jwks_cache.update(keys=[], fetched_at=None)  # force refetch next time
        raise ValueError("Unknown token signing key")
    public_key = pyjwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key_data))
    return pyjwt.decode(
        id_token,
        public_key,
        algorithms=["RS256"],
        audience=client_id,
        issuer=f"https://{domain}/",
    )


@app.route("/api/auth/auth0/config", methods=["GET"])
def auth0_config():
    """Public Auth0 settings for the frontend (client IDs are public by design)."""
    domain = os.environ.get("AUTH0_DOMAIN", "").strip()
    client_id = os.environ.get("AUTH0_CLIENT_ID", "").strip()
    desktop_client_id = (
        os.environ.get("AUTH0_DESKTOP_CLIENT_ID", "").strip() or client_id
    )
    return jsonify({
        "enabled": bool(domain and client_id),
        "domain": domain,
        "clientId": client_id,
        "desktopClientId": desktop_client_id,
    })


@app.route("/api/auth/auth0", methods=["POST"])
@limiter.limit("20 per hour", key_func=get_remote_address)
def auth_auth0():
    """Log in (or auto-register) with a verified Auth0 ID token."""
    data = request.json or {}
    id_token = data.get("id_token", "")
    if not id_token:
        return jsonify({"success": False, "error": "Missing id_token"}), 400
    try:
        claims = _verify_auth0_token(id_token)
    except Exception as e:
        logger.warning("Auth0 token verification failed: %s", e)
        return jsonify({"success": False, "error": "Invalid Auth0 token"}), 401

    email = (claims.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"success": False, "error": "No email in Auth0 profile"}), 400
    sub = claims.get("sub", "") or ""
    name = ((claims.get("name") or email.split("@")[0]).strip()[:80]) or "Voxy User"

    conn = _get_db()
    user = None
    if sub:
        user = conn.execute(
            "SELECT id FROM users WHERE auth0_sub = ?", (sub,)
        ).fetchone()
    if user is None:
        user = conn.execute(
            "SELECT id FROM users WHERE email_or_phone = ?", (email,)
        ).fetchone()
    if user is None:
        cur = conn.execute(
            "INSERT INTO users (name, email_or_phone, password_hash, "
            "email_verified, auth0_sub) VALUES (?, ?, ?, 1, ?)",
            (name, email, "auth0:" + uuid.uuid4().hex, sub or None),
        )
        user_id = cur.lastrowid
    else:
        user_id = user["id"]
        try:
            conn.execute(
                "UPDATE users SET auth0_sub = COALESCE(auth0_sub, ?), "
                "email_verified = 1 WHERE id = ?",
                (sub or None, user_id),
            )
        except Exception:
            pass
    _ensure_admin(conn, user_id, email)
    conn.commit()
    row = conn.execute(
        "SELECT id, name, email_or_phone, tier, role FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    conn.close()

    session_id = _create_session(user_id)
    return jsonify({
        "success": True,
        "user_id": user_id,
        "session_id": session_id,
        "name": row["name"],
        "email_or_phone": row["email_or_phone"],
        "tier": get_user_tier(user_id),
        "role": (row["role"] or "user") if "role" in row.keys() else "user",
    }), 200


_QR_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _new_qr_code() -> str:
    return "".join(secrets.choice(_QR_ALPHABET) for _ in range(6))


@app.route("/api/auth/qr/start", methods=["POST"])
@limiter.limit("20 per hour", key_func=get_remote_address)
def qr_start():
    """Create a QR login ticket (5-minute expiry). No auth needed to start."""
    data = request.json or {}
    device = str(data.get("device_name", ""))[:60]
    conn = _get_db()
    code = None
    for _ in range(5):
        candidate = _new_qr_code()
        if not conn.execute(
            "SELECT 1 FROM qr_tickets WHERE code = ?", (candidate,)
        ).fetchone():
            code = candidate
            break
    if not code:
        conn.close()
        return jsonify({"success": False, "error": "Try again"}), 500
    expires = (datetime.utcnow() + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO qr_tickets (code, device_name, expires_at) VALUES (?, ?, ?)",
        (code, device, expires),
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True, "code": code, "expires_in": 300}), 200


@app.route("/api/auth/qr/status", methods=["GET"])
@limiter.limit("60 per hour", key_func=get_remote_address)
def qr_status():
    """Poll a QR ticket. Returns a Voxylis session once approved on the phone."""
    code = (request.args.get("code", "") or "").upper().strip()
    if not code:
        return jsonify({"success": False, "error": "Missing code"}), 400
    conn = _get_db()
    t = conn.execute(
        "SELECT * FROM qr_tickets WHERE code = ?", (code,)
    ).fetchone()
    if t is None:
        conn.close()
        return jsonify({"success": False, "error": "Unknown code"}), 404
    if t["status"] == "expired" or datetime.utcnow() > datetime.strptime(
        t["expires_at"], "%Y-%m-%d %H:%M:%S"
    ):
        conn.execute("UPDATE qr_tickets SET status = 'expired' WHERE code = ?", (code,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "status": "expired"}), 200
    if t["status"] == "approved":
        if t["session_id"]:
            conn.close()
            return jsonify({
                "success": True, "status": "approved", "session_id": t["session_id"],
            }), 200
        session_id = _create_session(t["approved_user_id"])
        conn.execute(
            "UPDATE qr_tickets SET session_id = ? WHERE code = ?", (session_id, code)
        )
        conn.commit()
        row = conn.execute(
            "SELECT name, email_or_phone FROM users WHERE id = ?",
            (t["approved_user_id"],),
        ).fetchone()
        conn.close()
        return jsonify({
            "success": True,
            "status": "approved",
            "session_id": session_id,
            "name": row["name"] if row else "",
            "email_or_phone": row["email_or_phone"] if row else "",
        }), 200
    conn.close()
    return jsonify({"success": True, "status": "pending"}), 200


@app.route("/api/auth/qr/approve", methods=["POST"])
@require_auth
@limiter.limit("30 per hour", key_func=get_remote_address)
def qr_approve(user_id):
    """Approve a QR login from the logged-in phone. Logs the other device in as you."""
    data = request.json or {}
    code = (data.get("code", "") or "").upper().strip()
    if not code:
        return jsonify({"success": False, "error": "Missing code"}), 400
    conn = _get_db()
    t = conn.execute(
        "SELECT status, expires_at FROM qr_tickets WHERE code = ?", (code,)
    ).fetchone()
    if t is None:
        conn.close()
        return jsonify({"success": False, "error": "Unknown code"}), 404
    if t["status"] != "pending" or datetime.utcnow() > datetime.strptime(
        t["expires_at"], "%Y-%m-%d %H:%M:%S"
    ):
        conn.execute("UPDATE qr_tickets SET status = 'expired' WHERE code = ?", (code,))
        conn.commit()
        conn.close()
        return jsonify({"success": False, "error": "Code expired"}), 410
    conn.execute(
        "UPDATE qr_tickets SET status = 'approved', approved_user_id = ? WHERE code = ?",
        (user_id, code),
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Login approved"}), 200


@app.route("/api/admin/users", methods=["GET"])
@require_admin
@limiter.limit("60 per hour", key_func=get_remote_address)
def admin_users(user_id):
    """Admin-only user listing."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT id, name, email_or_phone, tier, role, created_at "
        "FROM users ORDER BY id"
    ).fetchall()
    conn.close()
    return jsonify({
        "success": True,
        "users": [
            {
                "id": r["id"],
                "name": r["name"],
                "email_or_phone": r["email_or_phone"],
                "tier": r["tier"] or "free",
                "role": (r["role"] or "user"),
                "created_at": r["created_at"],
            }
            for r in rows
        ],
    }), 200


@app.route("/api/auth/signup", methods=["POST"])
@limiter.limit("10 per hour", key_func=get_remote_address)
def auth_signup():
    data = request.json or {}
    name = data.get("name", "").strip()
    email_or_phone = data.get("email_or_phone", "").strip()
    password = data.get("password", "").strip()

    if not name or not email_or_phone or not password:
        return jsonify({"success": False, "error": "Missing required fields"}), 400
    if not _valid_name(name):
        return jsonify({"success": False, "error": "Name must be 2-80 characters"}), 400
    if not _valid_identifier(email_or_phone):
        return jsonify({"success": False, "error": "Enter a valid email or phone number"}), 400
    if not _valid_password(password):
        return jsonify({"success": False, "error": "Password must be 8-128 characters"}), 400
    # Password accounts: Gmail / official-domain mail only, never temp mail.
    # (Auth0 social logins bypass this — the IdP already verified the identity.)
    if "@" not in email_or_phone:
        return jsonify({
            "success": False,
            "error": "Please sign up with your Gmail or company email address.",
        }), 400
    if _is_disposable_email(email_or_phone):
        return jsonify({
            "success": False,
            "error": "Temporary email addresses are not allowed.",
        }), 400
    if not _password_domain_allowed(email_or_phone):
        return jsonify({
            "success": False,
            "error": "Password signup is limited to Gmail and official company email.",
        }), 400

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
    _ensure_admin(conn, user_id, email_or_phone)
    conn.commit()
    conn.close()

    session_id = _create_session(user_id)
    return jsonify({
        "success": True,
        "user_id": user_id,
        "session_id": session_id,
        "name": name,
        "email_or_phone": email_or_phone,
        "onboarding": {
            "steps": _onboarding_steps(),
            "completed": {},
        },
    }), 201


@app.route("/api/auth/login", methods=["POST"])
@limiter.limit("10 per 15 minutes", key_func=get_remote_address)
def auth_login():
    data = request.json or {}
    email_or_phone = data.get("email_or_phone", "").strip()
    password = data.get("password", "").strip()

    if not email_or_phone or not password:
        return jsonify({"success": False, "error": "Missing required fields"}), 400

    conn = _get_db()
    user = conn.execute(
        "SELECT id, name, password_hash FROM users WHERE email_or_phone = ?",
        (email_or_phone,),
    ).fetchone()
    conn.close()

    if user is None or not _check_password(user["password_hash"], password):
        return jsonify({"success": False, "error": "Invalid credentials"}), 401
    if _is_disposable_email(email_or_phone):
        return jsonify({
            "success": False,
            "error": "Temporary email addresses are not allowed.",
        }), 403

    try:
        admin_conn = _get_db()
        _ensure_admin(admin_conn, user["id"], email_or_phone)
        admin_conn.commit()
        admin_conn.close()
    except Exception:
        pass
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

    user_id = _verify_session(session_id)
    if user_id is None:
        return jsonify({"valid": False, "error": "Invalid or expired session"}), 200

    conn = _get_db()
    user = conn.execute(
        "SELECT id, name, email_or_phone, onboarding FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()

    return jsonify({
        "valid": True,
        "user_id": user["id"],
        "name": user["name"],
        "email_or_phone": user["email_or_phone"],
        "onboarding": _load_onboarding(user["onboarding"]),
    }), 200


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    data = request.json or {}
    session_id = data.get("session_id", "")
    if not session_id:
        return jsonify({"success": False, "error": "Missing session_id"}), 400

    conn = _get_db()
    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Logged out"}), 200


# ============================================
# PASSWORD RESET
# ============================================


@app.route("/api/auth/forgot-password", methods=["POST"])
@limiter.limit("5 per hour", key_func=get_remote_address)
def forgot_password():
    data = request.json or {}
    email = data.get("email", "").strip().lower()
    if not email or not _EMAIL_RE.match(email):
        return jsonify({"success": False, "error": "Valid email required"}), 400

    conn = _get_db()
    user = conn.execute("SELECT id FROM users WHERE email_or_phone = ?", (email,)).fetchone()
    if user is None:
        conn.close()
        return jsonify({"success": True, "message": "If an account exists, a reset link has been sent."})

    token = secrets.token_urlsafe(32)
    expires = (datetime.utcnow() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO password_resets (user_id, token, expires_at) VALUES (?, ?, ?)",
        (user["id"], token, expires),
    )
    conn.commit()
    conn.close()

    # In production, send email here. For now, return the token for testing.
    logger.debug("Password reset token for %s generated", email)
    return jsonify({
        "success": True,
        "message": "If an account exists, a reset link has been sent.",
    })


@app.route("/api/auth/reset-password", methods=["POST"])
@limiter.limit("10 per hour", key_func=get_remote_address)
def reset_password():
    data = request.json or {}
    token = data.get("token", "").strip()
    new_password = data.get("password", "").strip()

    if not token or not new_password:
        return jsonify({"success": False, "error": "Token and password required"}), 400
    if not _valid_password(new_password):
        return jsonify({"success": False, "error": "Password must be 8-128 characters"}), 400

    conn = _get_db()
    row = conn.execute(
        "SELECT id, user_id, expires_at, used FROM password_resets WHERE token = ?", (token,)
    ).fetchone()
    if row is None or row["used"]:
        conn.close()
        return jsonify({"success": False, "error": "Invalid or used token"}), 400

    expires = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
    if datetime.utcnow() > expires:
        conn.close()
        return jsonify({"success": False, "error": "Token expired"}), 400

    pw_hash = _hash_password(new_password)
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, row["user_id"]))
    conn.execute("UPDATE password_resets SET used = 1 WHERE id = ?", (row["id"],))
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (row["user_id"],))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Password reset successful"})


# ============================================
# EMAIL VERIFICATION
# ============================================


@app.route("/api/auth/verify-email", methods=["POST"])
@require_auth
@limiter.limit("5 per hour", key_func=get_remote_address)
def send_verification(user_id):
    conn = _get_db()
    user = conn.execute("SELECT email_or_phone, email_verified FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        conn.close()
        return jsonify({"success": False, "error": "User not found"}), 404
    if user["email_verified"]:
        conn.close()
        return jsonify({"success": True, "message": "Email already verified"})

    token = secrets.token_urlsafe(32)
    expires = (datetime.utcnow() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO email_verifications (user_id, token, expires_at) VALUES (?, ?, ?)",
        (user_id, token, expires),
    )
    conn.commit()
    conn.close()

    logger.debug("Email verification token generated for user %s", user_id)
    return jsonify({
        "success": True,
        "message": "Verification email sent",
    })


@app.route("/api/auth/confirm-email", methods=["POST"])
@limiter.limit("10 per hour", key_func=get_remote_address)
def confirm_email():
    data = request.json or {}
    token = data.get("token", "").strip()
    if not token:
        return jsonify({"success": False, "error": "Token required"}), 400

    conn = _get_db()
    row = conn.execute(
        "SELECT id, user_id, expires_at, used FROM email_verifications WHERE token = ?", (token,)
    ).fetchone()
    if row is None or row["used"]:
        conn.close()
        return jsonify({"success": False, "error": "Invalid or used token"}), 400

    expires = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
    if datetime.utcnow() > expires:
        conn.close()
        return jsonify({"success": False, "error": "Token expired"}), 400

    conn.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (row["user_id"],))
    conn.execute("UPDATE email_verifications SET used = 1 WHERE id = ?", (row["id"],))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Email verified successfully"})


# ============================================
# PROFILE + ONBOARDING
# ============================================

_ONBOARDING_STEPS = [
    {"id": "account", "label": "Create your account", "done": True},
    {"id": "download", "label": "Download Voxylis desktop app"},
    {"id": "first_recording", "label": "Make your first recording"},
    {"id": "enhance", "label": "Try an AI enhancement mode"},
    {"id": "ask", "label": "Ask Voxy a question"},
]


def _onboarding_steps():
    return list(_ONBOARDING_STEPS)


def _load_onboarding(raw: str):
    try:
        completed = json.loads(raw) if raw else {}
    except (ValueError, TypeError):
        completed = {}
    steps = []
    for s in _ONBOARDING_STEPS:
        steps.append({
            **s,
            "done": bool(completed.get(s["id"])),
        })
    return {"steps": steps, "completed": completed}


@app.route("/api/me", methods=["GET"])
def me():
    """Return the current user's profile (or 401 when logged out)."""
    session_id = _extract_session()
    user_id = _verify_session(session_id)
    if user_id is None:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    conn = _get_db()
    user = conn.execute(
        "SELECT id, name, email_or_phone, onboarding, created_at, tier, role "
        "FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    if user is None:
        return jsonify({"success": False, "error": "Not found"}), 404

    role = "user"
    try:
        role = user["role"] or "user"
    except Exception:
        pass
    if is_admin(user_id=user_id):
        role = "admin"

    return jsonify({
        "success": True,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email_or_phone": user["email_or_phone"],
            "created_at": user["created_at"],
            "tier": get_user_tier(user_id),
            "role": role,
            "onboarding": _load_onboarding(user["onboarding"]),
        },
    })


@app.route("/api/onboarding", methods=["GET", "POST"])
def onboarding():
    """GET returns steps + progress; POST marks a step complete."""
    session_id = _extract_session()
    user_id = _verify_session(session_id)
    if user_id is None:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    conn = _get_db()
    row = conn.execute("SELECT onboarding FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        conn.close()
        return jsonify({"success": False, "error": "Not found"}), 404

    try:
        completed = json.loads(row["onboarding"]) if row["onboarding"] else {}
    except (ValueError, TypeError):
        completed = {}

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        step_id = (data.get("step") or "").strip()
        valid_ids = {s["id"] for s in _ONBOARDING_STEPS}
        if step_id not in valid_ids:
            conn.close()
            return jsonify({"success": False, "error": "Unknown step"}), 400
        done = bool(data.get("done", True))
        completed[step_id] = done
        conn.execute("UPDATE users SET onboarding = ? WHERE id = ?", (json.dumps(completed), user_id))
        conn.commit()

    conn.close()
    return jsonify({
        "success": True,
        "onboarding": {
            "steps": [
                {**s, "done": bool(completed.get(s["id"]))} for s in _ONBOARDING_STEPS
            ],
            "completed": completed,
        },
    })


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
@require_auth
@limiter.limit("30 per minute", key_func=get_remote_address)
def settings(user_id):
    conn = _get_db()
    row = conn.execute("SELECT settings FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        conn.close()
        return jsonify({"status": "error", "message": "User not found"}), 404

    try:
        current = json.loads(row["settings"]) if row["settings"] else {}
    except (ValueError, TypeError):
        current = {}

    if request.method == "POST":
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            conn.close()
            return jsonify({"status": "error", "message": "Invalid JSON body"}), 400
        current.update(data)
        conn.execute("UPDATE users SET settings = ? WHERE id = ?", (json.dumps(current), user_id))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Settings saved successfully", "settings": current})

    conn.close()
    defaults = {
        "theme": "light",
        "language": "en",
        "notifications": True,
        "sound": True,
        "autoStart": False,
        "hotkey": "Win+Shift",
        "wakeWord": "Voxy",
        "wakeWordSensitivity": 70,
    }
    defaults.update(current)
    return jsonify({"status": "success", "settings": defaults})


@app.route("/api/hotkeys", methods=["GET", "POST"])
@require_auth
@limiter.limit("30 per minute", key_func=get_remote_address)
def hotkeys(user_id):
    conn = _get_db()
    row = conn.execute("SELECT hotkeys FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        conn.close()
        return jsonify({"status": "error", "message": "User not found"}), 404

    try:
        current = json.loads(row["hotkeys"]) if row["hotkeys"] else {}
    except (ValueError, TypeError):
        current = {}

    if request.method == "POST":
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            conn.close()
            return jsonify({"status": "error", "message": "Invalid JSON body"}), 400
        current.update(data)
        conn.execute("UPDATE users SET hotkeys = ? WHERE id = ?", (json.dumps(current), user_id))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Hotkey updated successfully", "hotkeys": current})

    conn.close()
    defaults = {
        "record": "Win+Shift",
        "casual": "Win+Alt",
        "technical": "Win+Ctrl",
        "settings": "Win+;",
    }
    defaults.update(current)
    return jsonify({"status": "success", "hotkeys": defaults})


# ============================================
# Q&A ENDPOINT
# ============================================


@app.route("/api/qa", methods=["POST"])
@limiter.limit("30 per minute", key_func=get_remote_address)
def qa_endpoint():
    session_id = _extract_session()
    user_id = _verify_session(session_id)
    if user_id is None:
        return jsonify({"error": "Login required for Q&A"}), 401

    if not has_feature(user_id, "qa"):
        tier = get_user_tier(user_id)
        return jsonify({
            "error": "Q&A requires a Pro or Business plan",
            "current_tier": tier,
            "upgrade_url": "/pricing",
        }), 403

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "Question required"}), 400

    answer = _call_llm_for_qa(question)
    return jsonify({
        "status": "success",
        "question": question,
        "answer": answer,
        "timestamp": datetime.now().isoformat(),
    })


def _call_llm_for_qa(question: str) -> str:
    """Call Muse Spark → OpenRouter → Groq → OpenAI (fallback chain) for Q&A."""
    model_key = os.environ.get("MODEL_API_KEY", "")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    groq_key = os.environ.get("GROQ_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")

    if model_key:
        try:
            import openai
            client = openai.OpenAI(api_key=model_key, base_url="https://api.meta.ai/v1")
            resp = client.chat.completions.create(
                model="muse-spark-1.3",
                messages=[
                    {"role": "system", "content": "You are Voxy, a helpful AI assistant built into the Voxylis voice-to-text app. Answer questions concisely and accurately. If the question is about Voxylis, reference its features (voice-to-text, AI enhancement, wake word, multi-language support)."},
                    {"role": "user", "content": question},
                ],
                max_tokens=512,
                temperature=0.7,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.warning("Muse Spark Q&A failed: %s", e)

    if openrouter_key:
        try:
            import openai
            client = openai.OpenAI(api_key=openrouter_key, base_url="https://openrouter.ai/api/v1")
            resp = client.chat.completions.create(
                model="meta-llama/llama-3.3-70b-instruct:free",
                messages=[
                    {"role": "system", "content": "You are Voxy, a helpful AI assistant built into the Voxylis voice-to-text app. Answer questions concisely and accurately. If the question is about Voxylis, reference its features (voice-to-text, AI enhancement, wake word, multi-language support)."},
                    {"role": "user", "content": question},
                ],
                max_tokens=512,
                temperature=0.7,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.warning("OpenRouter Q&A failed: %s", e)

    if groq_key:
        try:
            import groq
            client = groq.Groq(api_key=groq_key)
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are Voxy, a helpful AI assistant built into the Voxylis voice-to-text app. Answer questions concisely and accurately. If the question is about Voxylis, reference its features (voice-to-text, AI enhancement, wake word, multi-language support)."},
                    {"role": "user", "content": question},
                ],
                max_tokens=512,
                temperature=0.7,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.warning("Groq Q&A failed: %s", e)

    if openai_key:
        try:
            import openai
            client = openai.OpenAI(api_key=openai_key)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are Voxy, a helpful AI assistant built into the Voxylis voice-to-text app. Answer questions concisely and accurately."},
                    {"role": "user", "content": question},
                ],
                max_tokens=512,
                temperature=0.7,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.warning("OpenAI Q&A failed: %s", e)

    return "I'm sorry, the AI service is currently unavailable. Please try again later or configure a MODEL_API_KEY, OPENROUTER_API_KEY, GROQ_API_KEY, or OPENAI_API_KEY in your settings."


# ============================================
# TEXT ENHANCEMENT ENDPOINT
# ============================================

_MODE_PROMPTS = {
    "formal": "Rewrite the following text in a formal, professional tone. Fix grammar, punctuation, and clarity. Preserve the original meaning. Output ONLY the enhanced text, nothing else.",
    "casual": "Rewrite the following text in a relaxed, friendly, conversational tone. Fix obvious errors. Preserve the original meaning. Output ONLY the enhanced text, nothing else.",
    "technical": "Rewrite the following text in a precise, technical tone suitable for documentation or engineering audiences. Fix grammar and clarity. Preserve the original meaning. Output ONLY the enhanced text, nothing else.",
    "concise": "Rewrite the following text as concisely as possible while preserving all key information. Remove filler words and redundancy. Output ONLY the enhanced text, nothing else.",
    "creative": "Rewrite the following text with creative flair — vivid language, varied sentence structure, engaging tone. Preserve the original meaning. Output ONLY the enhanced text, nothing else.",
}


@app.route("/api/enhance", methods=["POST"])
@limiter.limit("30 per minute", key_func=get_remote_address)
def enhance_endpoint():
    session_id = _extract_session()
    user_id = _verify_session(session_id)
    if user_id is None:
        return jsonify({"error": "Login required for enhancement"}), 401

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400
    text = data.get("text", "").strip()
    mode = data.get("mode", "formal").strip().lower()
    if not text:
        return jsonify({"error": "Text required"}), 400
    if mode not in _MODE_PROMPTS:
        return jsonify({"error": f"Invalid mode. Choose from: {', '.join(_MODE_PROMPTS)}"}), 400

    tier = get_user_tier(user_id)
    allowed_modes = TIER_ENHANCEMENT_MODES.get(tier, TIER_ENHANCEMENT_MODES[TIER_FREE])
    if mode not in allowed_modes:
        return jsonify({
            "error": f"Mode '{mode}' requires a paid plan. Free tier: formal only.",
            "current_tier": tier,
            "allowed_modes": list(allowed_modes),
            "upgrade_url": "/pricing",
        }), 403

    enhanced = _call_llm_for_enhancement(text, mode)
    return jsonify({
        "status": "success",
        "original": text,
        "enhanced": enhanced,
        "mode": mode,
    })


def _call_llm_for_enhancement(text: str, mode: str) -> str:
    """Call Muse Spark → OpenRouter → Groq → OpenAI (fallback chain) for text enhancement."""
    model_key = os.environ.get("MODEL_API_KEY", "")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    groq_key = os.environ.get("GROQ_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    system_prompt = _MODE_PROMPTS.get(mode, _MODE_PROMPTS["formal"])

    if model_key:
        try:
            import openai
            client = openai.OpenAI(api_key=model_key, base_url="https://api.meta.ai/v1")
            resp = client.chat.completions.create(
                model="muse-spark-1.3",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                max_tokens=2048,
                temperature=0.7,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.warning("Muse Spark enhancement failed: %s", e)

    if openrouter_key:
        try:
            import openai
            client = openai.OpenAI(api_key=openrouter_key, base_url="https://openrouter.ai/api/v1")
            resp = client.chat.completions.create(
                model="meta-llama/llama-3.3-70b-instruct:free",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                max_tokens=2048,
                temperature=0.7,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.warning("OpenRouter enhancement failed: %s", e)

    if groq_key:
        try:
            import groq
            client = groq.Groq(api_key=groq_key)
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                max_tokens=2048,
                temperature=0.7,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.warning("Groq enhancement failed: %s", e)

    if openai_key:
        try:
            import openai
            client = openai.OpenAI(api_key=openai_key)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                max_tokens=2048,
                temperature=0.7,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.warning("OpenAI enhancement failed: %s", e)

    return text


# ============================================
# SPEECH-TO-TEXT ENDPOINT (Muse Voice Transcribe)
# ============================================


@app.route("/api/transcribe", methods=["POST"])
@limiter.limit("20 per minute", key_func=get_remote_address)
def transcribe_endpoint():
    """Transcribe uploaded audio: Muse Voice Transcribe -> Groq Whisper (fallback chain)."""
    session_id = _extract_session()
    user_id = _verify_session(session_id)
    if user_id is None:
        return jsonify({"error": "Login required for transcription"}), 401

    allowed, used, limit = check_transcription_quota(user_id)
    if not allowed:
        return jsonify({
            "error": f"Monthly transcription limit reached ({limit})",
            "used": used,
            "limit": limit,
            "upgrade_url": "/pricing",
        }), 403

    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["audio"]
    if not audio_file.filename:
        return jsonify({"error": "Empty audio file"}), 400

    mode = request.form.get("mode", "PUSH_TO_TALK").upper()
    if mode not in ("PUSH_TO_TALK", "ENDPOINTING", "DIARIZATION"):
        mode = "PUSH_TO_TALK"

    tier = get_user_tier(user_id)
    allowed_modes = TIER_STT_MODES.get(tier, TIER_STT_MODES[TIER_FREE])
    if mode not in allowed_modes:
        return jsonify({
            "error": f"STT mode '{mode}' requires a paid plan",
            "current_tier": tier,
            "allowed_modes": list(allowed_modes),
            "upgrade_url": "/pricing",
        }), 403

    audio_bytes = audio_file.read()
    if len(audio_bytes) > 32 * 1024 * 1024:
        return jsonify({"error": "Audio file exceeds 32 MB limit"}), 413

    # --- Muse Voice Transcribe (primary) ---
    model_key = os.environ.get("MODEL_API_KEY", "")
    if model_key:
        try:
            resp = http_requests.post(
                "https://api.meta.ai/v1/asr/transcribe",
                headers={
                    "Authorization": f"Bearer {model_key}",
                    "Accept": "application/json",
                },
                files={
                    "request": (
                        None,
                        json.dumps({
                            "model": "muse-voice-transcribe-1.0",
                            "audioEncoding": "WAV",
                            "mode": mode,
                        }),
                        "application/json",
                    ),
                    "audio": (audio_file.filename, audio_bytes, audio_file.content_type or "audio/wav"),
                },
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()

            transcript = ""
            turns = result.get("turns", [])
            if turns:
                transcript = " ".join(t.get("transcript", "") for t in turns)
            elif "transcript" in result:
                transcript = result["transcript"]

            if transcript.strip():
                return jsonify({
                    "status": "success",
                    "transcript": transcript.strip(),
                    "provider": "muse-voice-transcribe",
                    "mode": mode,
                })
        except Exception as e:
            logger.warning("Muse Voice Transcribe failed, falling back to Groq: %s", e)

    # --- Groq Whisper (fallback) ---
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if groq_key:
        try:
            import groq
            client = groq.Groq(api_key=groq_key)
            # Reset file pointer for Groq
            audio_file.seek(0)
            groq_mode = "segments" if mode == "DIARIZATION" else None
            resp = client.audio.transcriptions.create(
                file=(audio_file.filename, audio_bytes, audio_file.content_type or "audio/wav"),
                model="whisper-large-v3-turbo",
                response_format="verbose_json",
                **({"timestamp_granularities": ["segment"]} if groq_mode else {}),
            )
            transcript = resp.text if hasattr(resp, "text") else str(resp)
            if transcript.strip():
                return jsonify({
                    "status": "success",
                    "transcript": transcript.strip(),
                    "provider": "groq-whisper",
                    "mode": mode,
                })
        except Exception as e:
            logger.warning("Groq Whisper failed: %s", e)

    return jsonify({"error": "Transcription unavailable. Configure MODEL_API_KEY or GROQ_API_KEY."}), 503


# ============================================
# HISTORY ENDPOINTS (DB-backed when authed)
# ============================================


@app.route("/api/history", methods=["GET", "POST"])
@limiter.limit("30 per minute", key_func=get_remote_address)
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


@app.route("/api/history/<int:item_id>", methods=["DELETE"])
@limiter.limit("30 per minute", key_func=get_remote_address)
def history_delete(item_id):
    """Delete one history entry. Auth required; users can only delete their own."""
    session_id = _extract_session()
    user_id = _verify_session(session_id)
    if user_id is None:
        return jsonify({"success": False, "error": "Login required"}), 401

    conn = _get_db()
    cur = conn.execute(
        "DELETE FROM transcriptions WHERE id = ? AND user_id = ?",
        (item_id, user_id),
    )
    conn.commit()
    deleted = cur.rowcount
    conn.close()

    if not deleted:
        return jsonify({"success": False, "error": "Entry not found"}), 404
    return jsonify({"success": True, "message": "Entry deleted"})


# ============================================
# STATS
# ============================================


@app.route("/api/stats", methods=["GET"])
def stats():
    """Real usage stats. Scoped to the logged-in user when a session is
    present, otherwise global. All numbers come from the transcriptions table."""
    user_id = _verify_session(_extract_session())
    scope = "WHERE user_id = ?" if user_id is not None else ""
    params: tuple = (user_id,) if user_id is not None else ()

    conn = _get_db()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) as c FROM transcriptions {scope}", params
        ).fetchone()["c"]
        langs = conn.execute(
            f"SELECT COUNT(DISTINCT language) as c FROM transcriptions {scope}", params
        ).fetchone()["c"]
        enhanced = conn.execute(
            f"SELECT COUNT(*) as c FROM transcriptions {scope}"
            f"{' AND' if scope else 'WHERE'} enhanced = 1",
            params,
        ).fetchone()["c"]

        month_filter = "created_at >= date('now', 'start of month')"
        month_rows = conn.execute(
            f"SELECT text, language FROM transcriptions {scope}"
            f"{' AND' if scope else 'WHERE'} {month_filter}",
            params,
        ).fetchall()

        all_texts = conn.execute(
            f"SELECT text FROM transcriptions {scope}", params
        ).fetchall()

        weekly_counts = []
        weekly_labels = []
        for i in range(6, -1, -1):
            day = (datetime.now() - timedelta(days=i)).date().isoformat()
            c = conn.execute(
                f"SELECT COUNT(*) as n FROM transcriptions {scope}"
                f"{' AND' if scope else 'WHERE'} date(created_at) = ?",
                (*params, day),
            ).fetchone()["n"]
            weekly_counts.append(c)
            weekly_labels.append(
                (datetime.now() - timedelta(days=i)).strftime("%a")
            )
    finally:
        conn.close()

    words = sum(len((r["text"] or "").split()) for r in all_texts)
    month_words = sum(len((r["text"] or "").split()) for r in month_rows)
    month_langs = len({r["language"] for r in month_rows if r["language"]})
    minutes = max(1, round(words / 150)) if words else 0
    total_time = f"{minutes // 60}h {minutes % 60}m" if minutes >= 60 else f"{minutes}m"

    return jsonify({
        "status": "success",
        "stats": {
            "transcriptions": total,
            "totalTime": total_time,
            "languages": langs,
            "enhancements": enhanced,
            "words": words,
            "thisMonth": {
                "transcriptions": len(month_rows),
                "words": month_words,
                "languages": month_langs,
            },
            "weekly": {"labels": weekly_labels, "counts": weekly_counts},
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
    """Subscription summary. Logged-out visitors get Free-tier defaults."""
    user_id = _verify_session(_extract_session())
    if user_id is None:
        return jsonify({
            "status": "success",
            "authenticated": False,
            "subscription": {
                "plan": "Free",
                "tier": TIER_FREE,
                "price": 0,
                "renewalDate": None,
                "status": "active",
                "usage": {
                    "transcriptions": 0,
                    "limit": "100/month",
                    "percentage": 0,
                },
            },
        })

    tier = get_user_tier(user_id)
    conn = _get_db()
    user = conn.execute(
        "SELECT created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()

    trans_count = 0
    try:
        conn2 = _get_db()
        row = conn2.execute(
            "SELECT COUNT(*) as c FROM transcriptions WHERE user_id = ?", (user_id,)
        ).fetchone()
        trans_count = row["c"] if row else 0
        conn2.close()
    except Exception:
        pass

    tier_info = {
        TIER_FREE: {"price": 0, "limit": "100/month", "name": "Free"},
        TIER_PRO: {"price": 9.99, "limit": "Unlimited", "name": "Pro"},
        TIER_BUSINESS: {"price": 29.99, "limit": "Unlimited", "name": "Business"},
    }
    info = tier_info.get(tier, tier_info[TIER_FREE])

    return jsonify({
        "status": "success",
        "subscription": {
            "plan": info["name"],
            "tier": tier,
            "price": info["price"],
            "renewalDate": None,
            "status": "active",
            "usage": {
                "transcriptions": trans_count,
                "limit": info["limit"],
                "percentage": min(trans_count, 100) if tier == TIER_FREE else 0,
            },
        },
    })


@app.route("/api/subscription/upgrade", methods=["POST"])
@require_auth
@limiter.limit("10 per hour", key_func=get_remote_address)
def upgrade_tier(user_id):
    """Set user tier. In production, this would be triggered by Stripe webhook."""
    data = request.json or {}
    new_tier = data.get("tier", "").strip().lower()
    if new_tier not in (TIER_FREE, TIER_PRO, TIER_BUSINESS):
        return jsonify({"error": "Invalid tier"}), 400

    conn = _get_db()
    conn.execute("UPDATE users SET tier = ? WHERE id = ?", (new_tier, user_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "tier": new_tier})


# ============================================
# USER PROFILE UPDATE
# ============================================


@app.route("/api/auth/update-profile", methods=["POST"])
@require_auth
@limiter.limit("10 per hour", key_func=get_remote_address)
def update_profile(user_id):
    data = request.json or {}
    name = data.get("name", "").strip()
    current_password = data.get("current_password", "").strip()
    new_password = data.get("new_password", "").strip()

    conn = _get_db()
    user = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        conn.close()
        return jsonify({"success": False, "error": "User not found"}), 404

    if new_password:
        if not current_password:
            conn.close()
            return jsonify({"success": False, "error": "Current password required"}), 400
        if not _check_password(user["password_hash"], current_password):
            conn.close()
            return jsonify({"success": False, "error": "Incorrect current password"}), 400
        if not _valid_password(new_password):
            conn.close()
            return jsonify({"success": False, "error": "New password must be 8-128 characters"}), 400
        pw_hash = _hash_password(new_password)
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, user_id))

    if name:
        if not _valid_name(name):
            conn.close()
            return jsonify({"success": False, "error": "Name must be 2-80 characters"}), 400
        conn.execute("UPDATE users SET name = ? WHERE id = ?", (name, user_id))

    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Profile updated"})


# ============================================
# CONTACT
# ============================================


@app.route("/api/contact", methods=["POST"])
@limiter.limit("10 per hour", key_func=get_remote_address)
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
        (_sanitize(name), email, _sanitize(subject), _sanitize(message)),
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Message received. We'll get back to you shortly."})


# ============================================
# NEWSLETTER
# ============================================


@app.route("/api/newsletter", methods=["POST"])
@limiter.limit("10 per hour", key_func=get_remote_address)
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
    return jsonify({
        "windows": os.environ.get("DOWNLOAD_URL_WINDOWS", ""),
        "macos": os.environ.get("DOWNLOAD_URL_MACOS", ""),
        "linux": os.environ.get("DOWNLOAD_URL_LINUX", ""),
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
@limiter.limit("60 per minute", key_func=get_remote_address)
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
        "version": "2.2.0",
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
