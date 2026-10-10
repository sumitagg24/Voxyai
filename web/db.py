"""Database helpers (moved from web/app.py without behavior changes)."""

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from web.content.blog_posts import BLOG_POSTS
from web.services import email_preferences

BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "data"


def get_db_path() -> Path:
    """Return the active DB path, re-reading VOXYLIS_DB_PATH on every call.

    Tests set VOXYLIS_DB_PATH then reload web.app; web.db itself is not reloaded,
    so _get_db() must not close over a stale global.
    """

    return Path(os.environ.get("VOXYLIS_DB_PATH") or (DB_DIR / "voxylis.db"))


#: Overridable so tests and containers can point at a scratch database.
#: Note: web/data is gitignored — the production database is created on the
#: host (Docker volume), never committed.
DB_PATH = get_db_path()


def utcnow() -> datetime:
    """Naive UTC now, matching SQLite's ``datetime('now')``.

    ``datetime.utcnow()`` is deprecated from Python 3.12. Sessions, tokens and
    email codes are stored as naive UTC strings so they can be compared against
    ``datetime('now')`` inside SQL, so the tzinfo is stripped deliberately.
    """

    return datetime.now(timezone.utc).replace(tzinfo=None)


def _owner_emails() -> set:
    """Emails that are designated owners (unlimited server-enforced usage)."""

    return {e.strip().lower() for e in os.environ.get("OWNER_EMAILS", "sumitagg24@gmail.com").split(",") if e.strip()}


def _get_db() -> sqlite3.Connection:
    """Return a per-request database connection with row_factory."""

    conn = sqlite3.connect(str(get_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _init_db() -> None:
    """Create tables and seed blog data if needed."""

    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = _get_db()
    cur = conn.cursor()

    cur.executescript("""
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

        CREATE TABLE IF NOT EXISTS subscriptions (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id              INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            tier                 TEXT NOT NULL DEFAULT 'free',
            status               TEXT NOT NULL DEFAULT 'active',
            current_period_start TEXT NOT NULL DEFAULT (datetime('now')),
            current_period_end   TEXT NOT NULL DEFAULT (datetime('now', '+30 days')),
            cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
            created_at           TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS usage_records (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            feature    TEXT NOT NULL,
            tokens     INTEGER NOT NULL DEFAULT 0,
            count      INTEGER NOT NULL DEFAULT 1,
            metadata   TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS notification_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            kind       TEXT    NOT NULL,
            period     TEXT    NOT NULL,
            created_at TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE(user_id, kind, period)
        );

        CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_transcriptions_user_id ON transcriptions(user_id);
        CREATE INDEX IF NOT EXISTS idx_transcriptions_created ON transcriptions(created_at);
        CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
        CREATE INDEX IF NOT EXISTS idx_usage_records_user_id_feature ON usage_records(user_id, feature, created_at);
        CREATE INDEX IF NOT EXISTS idx_users_email ON users(email_or_phone);
        """)
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
    if "is_owner" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN is_owner INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    if "auth0_sub" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN auth0_sub TEXT")
        conn.commit()

    for owner_email in _owner_emails():
        # Same verified-address rule as _ensure_owner(): the startup sweep must
        # not promote an unverified claim on the owner address either.
        cur.execute(
            "UPDATE users SET is_owner = 1, role = 'owner', tier = 'owner' "
            "WHERE LOWER(email_or_phone) = ? AND email_verified = 1",
            (owner_email.lower(),),
        )
    # Marketing consent lives in its own table: absence of a row means "no".
    email_preferences.ensure_schema(conn)
    conn.commit()

    # Blog content is seeded/updated on every start so corrections to copy are
    # actually published (the upsert in _seed_blog also prunes withdrawn posts).
    cur.executescript("""
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
        """)
    _seed_blog(conn)
    conn.close()


def _seed_blog(conn: sqlite3.Connection) -> None:
    """Insert hardcoded blog posts."""

    posts = BLOG_POSTS
    cur = conn.cursor()
    keep = []
    for post in posts:
        # Upsert, so corrections to published copy reach existing databases
        # instead of being frozen at first seed.
        cur.execute(
            "INSERT INTO blog_posts (slug, title, date, category, excerpt, content, read_time) "
            "VALUES (:slug, :title, :date, :category, :excerpt, :content, :read_time) "
            "ON CONFLICT(slug) DO UPDATE SET title=excluded.title, date=excluded.date, "
            "category=excluded.category, excerpt=excluded.excerpt, content=excluded.content, "
            "read_time=excluded.read_time",
            post,
        )
        keep.append(post["slug"])

    # Earlier releases shipped posts containing fabricated research figures.
    # Remove anything we no longer publish rather than leaving it served.
    placeholders = ",".join("?" for _ in keep)
    cur.execute(f"DELETE FROM blog_posts WHERE slug NOT IN ({placeholders})", keep)
    conn.commit()
