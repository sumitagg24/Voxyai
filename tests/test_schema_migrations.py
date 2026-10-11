"""P6.4: numbered schema migrations — fresh DBs, legacy upgrades, run-once."""

from __future__ import annotations

import sqlite3

import web.db as db


def _expected_versions() -> list:
    return [version for version, _, _ in db._migrations()]


def test_fresh_database_records_every_migration(app_client):
    client, web_app = app_client
    conn = web_app._get_db()
    rows = conn.execute("SELECT version, name, applied_at FROM schema_migrations ORDER BY version").fetchall()
    assert [r["version"] for r in rows] == _expected_versions()
    assert all(r["applied_at"] for r in rows)
    assert all(r["name"] for r in rows)

    cols = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
    assert {"onboarding", "settings", "hotkeys", "email_verified", "tier", "role", "is_owner", "auth0_sub"} <= cols

    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_users_email_lower'"
    ).fetchone(), "email-lower unique index must exist"
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='processed_events'"
    ).fetchone(), "processed_events must be created by a migration, not ad hoc"
    conn.close()


def test_legacy_database_is_upgraded_and_steps_run_only_once(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy.db"
    con = sqlite3.connect(str(legacy))
    con.executescript("""
        CREATE TABLE users (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL,
            email_or_phone TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at   TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE newsletter_subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """)
    con.execute("INSERT INTO users (name, email_or_phone, password_hash) VALUES ('Legacy', 'Legacy@Gmail.com', 'x')")
    con.commit()
    con.close()

    monkeypatch.setenv("VOXYLIS_DB_PATH", str(legacy))
    db._init_db()

    conn = sqlite3.connect(str(legacy))
    conn.row_factory = sqlite3.Row
    cols = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
    assert {"onboarding", "settings", "hotkeys", "email_verified", "tier", "role", "is_owner", "auth0_sub"} <= cols
    assert conn.execute("SELECT email_or_phone FROM users").fetchone()["email_or_phone"] == "legacy@gmail.com"
    assert conn.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_users_email_lower'").fetchone()
    first_applied = {
        r["version"]: r["applied_at"]
        for r in conn.execute("SELECT version, applied_at FROM schema_migrations").fetchall()
    }
    conn.close()
    assert sorted(first_applied) == _expected_versions()

    # Second boot: every step is already recorded and must be skipped.
    db._init_db()

    conn = sqlite3.connect(str(legacy))
    conn.row_factory = sqlite3.Row
    second_applied = {
        r["version"]: r["applied_at"]
        for r in conn.execute("SELECT version, applied_at FROM schema_migrations").fetchall()
    }
    total = conn.execute("SELECT COUNT(*) AS c FROM schema_migrations").fetchone()["c"]
    conn.close()

    assert second_applied == first_applied, "re-running _init_db must not re-apply migrations"
    assert total == len(_expected_versions())


def test_migration_versions_are_unique_and_ordered():
    versions = _expected_versions()
    assert versions == sorted(versions)
    assert len(versions) == len(set(versions)), "migration versions must be unique"
