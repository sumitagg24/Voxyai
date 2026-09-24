"""Backup and restore tooling for the SQLite database (web/backup.py).

These tests run entirely against scratch databases in temporary directories;
the developer's real ``web/data/voxylis.db`` is never touched.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from web import backup as backup_mod


@pytest.fixture
def scratch_db(tmp_path: Path) -> Path:
    """A small live database with one row of known content."""
    db = tmp_path / "live.db"
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE notes (body TEXT)")
    con.execute("INSERT INTO notes VALUES ('known content')")
    con.commit()
    con.close()
    return db


def _rows(db: Path) -> list[tuple]:
    con = sqlite3.connect(str(db))
    try:
        return con.execute("SELECT body FROM notes").fetchall()
    finally:
        con.close()


# ── backup ───────────────────────────────────────────────────────────────────


def test_backup_of_a_live_database_is_verified(scratch_db, tmp_path):
    backup_dir = tmp_path / "backups"
    result = backup_mod.backup(backup_dir=backup_dir, keep=3, db_path=scratch_db)

    assert result["ok"] is True, result
    saved = Path(result["file"])
    assert saved.exists() and saved.parent == backup_dir
    assert len(result["sha256"]) == 64
    # The copy is a real database holding the same rows.
    assert _rows(saved) == [("known content",)]
    # The checksum matches the file on disk.
    import hashlib

    assert hashlib.sha256(saved.read_bytes()).hexdigest() == result["sha256"]


def test_backup_captures_wal_content_a_raw_copy_would_lose(scratch_db, tmp_path):
    """The online backup API must see committed rows still sitting in -wal.

    Copying the main database file while the WAL holds un-checkpointed frames
    is the classic way to produce a stale or corrupt backup; this asserts the
    property that distinguishes the online API from ``shutil.copy``.
    """
    con = sqlite3.connect(str(scratch_db))
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("INSERT INTO notes VALUES ('wal-only content')")
    con.commit()
    # Deliberately no close/checkpoint: the newest row lives only in the WAL.
    assert scratch_db.with_name(scratch_db.name + "-wal").exists()
    try:
        result = backup_mod.backup(backup_dir=tmp_path / "b", keep=1, db_path=scratch_db)
        assert result["ok"] is True, result
        assert _rows(Path(result["file"])) == [
            ("known content",),
            ("wal-only content",),
        ]
    finally:
        con.close()


def test_backup_of_a_missing_database_fails_cleanly(tmp_path):
    result = backup_mod.backup(backup_dir=tmp_path / "b", db_path=tmp_path / "absent.db")
    assert result["ok"] is False
    assert "not found" in result["error"]


def test_retention_prunes_the_oldest_backups(scratch_db, tmp_path):
    backup_dir = tmp_path / "b"
    first = backup_mod.backup(backup_dir=backup_dir, keep=2, db_path=scratch_db)
    second = backup_mod.backup(backup_dir=backup_dir, keep=2, db_path=scratch_db)
    third = backup_mod.backup(backup_dir=backup_dir, keep=2, db_path=scratch_db)

    assert (first["ok"], second["ok"], third["ok"]) == (True, True, True)
    remaining = sorted(backup_dir.glob("voxylis-*.db"))
    assert len(remaining) == 2
    # The oldest file is the one that went away.
    assert Path(first["file"]).exists() is False
    assert Path(third["file"]).exists()
    assert third["pruned"] == 1


# ── restore ──────────────────────────────────────────────────────────────────


def test_restore_into_an_empty_location_needs_no_force(scratch_db, tmp_path):
    backup_dir = tmp_path / "b"
    saved = Path(backup_mod.backup(backup_dir=backup_dir, db_path=scratch_db)["file"])

    target = tmp_path / "fresh.db"
    result = backup_mod.restore(saved, db_path=target)
    assert result["ok"] is True, result
    assert result["verified_backup"] is True
    assert _rows(target) == [("known content",)]


def test_restore_refuses_to_overwrite_a_live_database_without_force(scratch_db, tmp_path):
    backup_dir = tmp_path / "b"
    saved = Path(backup_mod.backup(backup_dir=backup_dir, db_path=scratch_db)["file"])

    live = tmp_path / "live2.db"
    con = sqlite3.connect(str(live))
    con.execute("CREATE TABLE notes (body TEXT)")
    con.execute("INSERT INTO notes VALUES ('production data')")
    con.commit()
    con.close()

    result = backup_mod.restore(saved, db_path=live, force=False)
    assert result["ok"] is False
    assert "--force" in result["error"]
    # The live data survived the refused restore.
    assert _rows(live) == [("production data",)]


def test_restore_with_force_replaces_the_live_database(scratch_db, tmp_path):
    backup_dir = tmp_path / "b"
    saved = Path(backup_mod.backup(backup_dir=backup_dir, db_path=scratch_db)["file"])

    live = tmp_path / "live3.db"
    con = sqlite3.connect(str(live))
    con.execute("CREATE TABLE notes (body TEXT)")
    con.execute("INSERT INTO notes VALUES ('old state')")
    con.commit()
    con.close()

    result = backup_mod.restore(saved, db_path=live, force=True)
    assert result["ok"] is True, result
    assert _rows(live) == [("known content",)]
    # No temp file may survive a successful restore.
    assert not live.with_name(live.name + ".restore-tmp").exists()


def test_restore_refuses_a_corrupt_backup(scratch_db, tmp_path):
    saved = Path(backup_mod.backup(backup_dir=tmp_path / "b", db_path=scratch_db)["file"])
    # Corrupt the copy by truncating it to half its pages: the header then
    # promises pages that are not in the file.
    raw = saved.read_bytes()
    saved.write_bytes(raw[: len(raw) // 2])

    target = tmp_path / "fresh.db"
    result = backup_mod.restore(saved, db_path=target)
    assert result["ok"] is False
    assert "integrity" in result["error"]
    assert not target.exists()


def test_restore_removes_stale_wal_sidecars(scratch_db, tmp_path):
    """Old WAL frames must never be replayed into a restored database."""
    saved = Path(backup_mod.backup(backup_dir=tmp_path / "b", db_path=scratch_db)["file"])

    live = tmp_path / "live4.db"
    con = sqlite3.connect(str(live))
    con.execute("CREATE TABLE notes (body TEXT)")
    con.commit()
    con.close()
    # Plant sidecars as if the live DB had just been written.
    live.with_name(live.name + "-wal").write_bytes(b"stale frames")
    live.with_name(live.name + "-shm").write_bytes(b"stale index")

    assert backup_mod.restore(saved, db_path=live, force=True)["ok"] is True
    assert not live.with_name(live.name + "-wal").exists()
    assert not live.with_name(live.name + "-shm").exists()
    assert _rows(live) == [("known content",)]


def test_restore_of_a_missing_backup_fails_cleanly(tmp_path):
    result = backup_mod.restore(tmp_path / "absent.db", db_path=tmp_path / "x.db")
    assert result["ok"] is False
    assert "not found" in result["error"]


# ── CLI ──────────────────────────────────────────────────────────────────────


def test_cli_reports_failure_with_exit_code_one(tmp_path, capsys):
    exit_code = backup_mod.main(["--db", str(tmp_path / "absent.db")])
    captured = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert captured["ok"] is False


def test_cli_takes_a_backup_and_restores_it(tmp_path, capsys):
    db = tmp_path / "live.db"
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE notes (body TEXT)")
    con.commit()
    con.close()

    backup_dir = tmp_path / "b"
    assert backup_mod.main(["--backup-dir", str(backup_dir), "--keep", "1", "--db", str(db)]) == 0
    saved = json.loads(capsys.readouterr().out)["file"]

    db.unlink()
    assert backup_mod.main(["--restore", saved, "--db", str(db)]) == 0
    assert _rows(db) == []
