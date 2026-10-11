"""Database helpers (moved from web/app.py without behavior changes)."""

import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from web.content.blog_posts import BLOG_POSTS
from web.services import email_preferences

logger = logging.getLogger(__name__)

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


#: Every schema change ships as a numbered, recorded step here (P6.4). Rules:
#: append only — never edit or renumber a released step — and keep each step
#: idempotent, because a database that predates the ``schema_migrations``
#: table already contains the effects of older steps and will run them once
#: for the record.
def _add_user_column_if_missing(conn: sqlite3.Connection, column: str, ddl: str) -> None:
    """ALTER TABLE users, but only when the column is actually absent."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
    if column not in cols:
        conn.execute(f"ALTER TABLE users ADD COLUMN {ddl}")
        conn.commit()


def _create_processed_events(conn: sqlite3.Connection) -> None:
    """Webhook replay-dedup table (was created ad-hoc in the route)."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS processed_events ("
        " event_id TEXT PRIMARY KEY,"
        " source TEXT NOT NULL DEFAULT '',"
        " created_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    conn.commit()


def _create_download_events(conn: sqlite3.Connection) -> None:
    """Download-click counter table (was created ad-hoc in the route)."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS download_events "
        "(id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT NOT NULL, "
        "created_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    conn.commit()


def _add_qr_device_token(conn: sqlite3.Connection) -> None:
    """P6.7: per-ticket client secret so only the ticket creator can claim
    the session that an approval mints (blocks QR-observation session theft)."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(qr_tickets)").fetchall()]
    if "device_token" not in cols:
        conn.execute("ALTER TABLE qr_tickets ADD COLUMN device_token TEXT")
        conn.commit()


def _migrations() -> list:
    """The ordered migration ledger (resolved lazily so step functions defined
    later in this module are available)."""
    return [
        (
            1,
            "users: add onboarding",
            lambda c: _add_user_column_if_missing(c, "onboarding", "onboarding TEXT NOT NULL DEFAULT '{}'"),
        ),
        (
            2,
            "users: add settings",
            lambda c: _add_user_column_if_missing(c, "settings", "settings TEXT NOT NULL DEFAULT '{}'"),
        ),
        (
            3,
            "users: add hotkeys",
            lambda c: _add_user_column_if_missing(c, "hotkeys", "hotkeys TEXT NOT NULL DEFAULT '{}'"),
        ),
        (
            4,
            "users: add email_verified",
            lambda c: _add_user_column_if_missing(c, "email_verified", "email_verified INTEGER NOT NULL DEFAULT 0"),
        ),
        (5, "users: add tier", lambda c: _add_user_column_if_missing(c, "tier", "tier TEXT NOT NULL DEFAULT 'free'")),
        (6, "users: add role", lambda c: _add_user_column_if_missing(c, "role", "role TEXT NOT NULL DEFAULT 'user'")),
        (
            7,
            "users: add is_owner",
            lambda c: _add_user_column_if_missing(c, "is_owner", "is_owner INTEGER NOT NULL DEFAULT 0"),
        ),
        (8, "users: add auth0_sub", lambda c: _add_user_column_if_missing(c, "auth0_sub", "auth0_sub TEXT")),
        (9, "email case-normalization + lower() unique indexes", _dedupe_case_variant_emails),
        (10, "processed_events table", _create_processed_events),
        (11, "qr_tickets: add device_token", _add_qr_device_token),
        (12, "download_events table", _create_download_events),
    ]


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Run every migration that has not been recorded yet (exactly once).

    The ``schema_migrations`` row is written only after the step function
    returns, so a crashed step is retried on the next boot rather than being
    silently marked as applied.
    """
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " version INTEGER PRIMARY KEY,"
        " name TEXT NOT NULL DEFAULT '',"
        " applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    conn.commit()
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}
    for version, name, step in _migrations():
        if version in applied:
            continue
        step(conn)
        conn.execute(
            "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
            (version, name),
        )
        conn.commit()
        logger.info("schema migration %d applied: %s", version, name)


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

    # Numbered, recorded schema steps (column adds, email normalization,
    # unique indexes, processed_events). Each runs exactly once per database.
    _apply_migrations(conn)

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


def _dedupe_case_variant_emails(conn: sqlite3.Connection) -> None:
    """Merge case-variant duplicate addresses (P1.2, idempotent).

    Keeps the oldest verified row per ``LOWER(address)`` group and deletes the
    rest, logging each merge. Afterwards all stored emails are lowercased and
    a ``LOWER()`` unique index prevents future case-variant duplicates.
    """
    cur = conn.cursor()
    # ── users ──────────────────────────────────────────────────────────────
    try:
        dupes = cur.execute(
            "SELECT LOWER(email_or_phone) AS norm, COUNT(*) AS c FROM users " "GROUP BY norm HAVING c > 1"
        ).fetchall()
        for dupe in dupes:
            norm = dupe["norm"] if hasattr(dupe, "keys") else dupe[0]
            rows = cur.execute(
                "SELECT id, email_or_phone, email_verified, created_at FROM users "
                "WHERE LOWER(email_or_phone) = ? ORDER BY email_verified DESC, id ASC",
                (norm,),
            ).fetchall()
            if len(rows) <= 1:
                continue
            keep = rows[0]["id"] if hasattr(rows[0], "keys") else rows[0][0]
            drop_ids = [(r["id"] if hasattr(r, "keys") else r[0]) for r in rows[1:]]
            placeholders = ",".join("?" for _ in drop_ids)
            cur.execute(f"DELETE FROM users WHERE id IN ({placeholders})", drop_ids)
            logger.info(
                "email-dedupe: merged %d case-variant users for %s into id=%s",
                len(drop_ids),
                norm,
                keep,
            )
        # Normalize stored addresses to lowercase (emails only, not phones).
        cur.execute(
            "UPDATE users SET email_or_phone = LOWER(email_or_phone) "
            "WHERE email_or_phone LIKE '%@%' AND email_or_phone != LOWER(email_or_phone)"
        )
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_lower ON users(LOWER(email_or_phone))")
    except sqlite3.Error as exc:
        logger.warning("email-dedupe users skipped: %s", type(exc).__name__)
    # ── newsletter ─────────────────────────────────────────────────────────
    try:
        dupes = cur.execute(
            "SELECT LOWER(email) AS norm, COUNT(*) AS c FROM newsletter_subscribers " "GROUP BY norm HAVING c > 1"
        ).fetchall()
        for dupe in dupes:
            norm = dupe["norm"] if hasattr(dupe, "keys") else dupe[0]
            rows = cur.execute(
                "SELECT id FROM newsletter_subscribers WHERE LOWER(email) = ? ORDER BY id ASC",
                (norm,),
            ).fetchall()
            if len(rows) <= 1:
                continue
            keep = rows[0]["id"] if hasattr(rows[0], "keys") else rows[0][0]
            drop_ids = [(r["id"] if hasattr(r, "keys") else r[0]) for r in rows[1:]]
            placeholders = ",".join("?" for _ in drop_ids)
            cur.execute(f"DELETE FROM newsletter_subscribers WHERE id IN ({placeholders})", drop_ids)
            logger.info(
                "email-dedupe: merged %d case-variant newsletter rows for %s into id=%s",
                len(drop_ids),
                norm,
                keep,
            )
        cur.execute("UPDATE newsletter_subscribers SET email = LOWER(email) WHERE email != LOWER(email)")
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_newsletter_email_lower " "ON newsletter_subscribers(LOWER(email))"
        )
    except sqlite3.Error as exc:
        logger.warning("email-dedupe newsletter skipped: %s", type(exc).__name__)
    conn.commit()


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
