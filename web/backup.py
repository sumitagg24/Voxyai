"""Safe backup and restore for the Voxylis SQLite database.

Why this module exists
----------------------
``docs/DEPLOYMENT.md`` § D keeps SQLite as the deliberate choice for a
single-instance deployment. The one thing a single-file database cannot
survive without help is operator error and disk loss, so backups must be both
safe to take on a live database and verified before anyone relies on them.

Safety properties
-----------------
* **Live-safe**: backups use SQLite's online backup API (``Connection.backup``),
  never a raw file copy. That produces a consistent snapshot of a database that
  is being written concurrently, unlike copying ``voxylis.db`` while ``-wal``
  sidecar files exist (which can yield a corrupt backup).
* **Verified**: every backup is checksummed (SHA-256) and opened for
  ``PRAGMA integrity_check`` before the run reports success. An unverified
  backup is not a backup.
* **Pruned**: retention keeps the newest ``--keep`` backups; older files are
  deleted so a backup directory cannot grow without bound.
* **Restorable**: restore verifies the backup's integrity first, refuses to
  overwrite a non-empty live database unless ``--force`` is passed, replaces
  the file via an atomic same-volume rename, and removes stale WAL sidecars.

CLI (from the project root or any host with the same tree):

    python -m web.backup --backup-dir D:/backups/voxylis --keep 14
    python -m web.backup --restore D:/backups/voxylis/voxylis-2026-09-24.db --force

Exit codes: 0 success, 1 the backup/restore failed, 2 usage error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


def _default_backup_dir() -> Path:
    return Path(os.environ.get("VOXYLIS_BACKUP_DIR") or "backups")


def _live_db_path() -> Path:
    """Resolve the live database path without importing web.app.

    Importing ``web.app`` runs ``_init_db()`` and would auto-create the very
    database a restore may be trying to replace, so the path logic from
    ``web/app.py`` is mirrored here: ``VOXYLIS_DB_PATH`` if set, else
    ``<this package>/data/voxylis.db``.
    """
    env = os.environ.get("VOXYLIS_DB_PATH")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent / "data" / "voxylis.db"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _integrity_ok(path: Path) -> bool:
    """Open a database file and confirm it is structurally consistent."""
    try:
        con = sqlite3.connect(str(path))
        try:
            row = con.execute("PRAGMA integrity_check").fetchone()
            return bool(row) and str(row[0]) == "ok"
        finally:
            con.close()
    except sqlite3.Error:
        return False


def backup(
    backup_dir: Path | None = None,
    keep: int = 14,
    db_path: Path | None = None,
) -> dict:
    """Take one verified backup of the live database and prune old ones.

    Returns ``{"ok", "file", "sha256", "pruned", "error"}``.
    """
    result: dict = {"ok": False, "file": None, "sha256": None, "pruned": 0, "error": None}

    if db_path is None:
        db_path = _live_db_path()
    db_path = Path(db_path)
    if not db_path.exists():
        result["error"] = f"database not found: {db_path}"
        return result

    backup_dir = Path(backup_dir) if backup_dir else _default_backup_dir()
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        result["error"] = f"cannot create backup directory {backup_dir}: {exc}"
        return result

    # Two runs inside the same second must not overwrite each other: every
    # backup stays individually restorable.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = backup_dir / f"voxylis-{stamp}.db"
    suffix = 0
    while target.exists():
        suffix += 1
        target = backup_dir / f"voxylis-{stamp}-{suffix}.db"

    try:
        source = sqlite3.connect(str(db_path))
        try:
            destination = sqlite3.connect(str(target))
            try:
                source.backup(destination)
            finally:
                destination.close()
        finally:
            source.close()
    except sqlite3.Error as exc:
        result["error"] = f"backup failed: {type(exc).__name__}: {exc}"
        target.unlink(missing_ok=True)
        return result

    # Verify before declaring success: checksum the file, then open the copy
    # and check its internal structure. A bad copy is deleted, not kept.
    try:
        checksum = _sha256(target)
    except OSError as exc:
        target.unlink(missing_ok=True)
        result["error"] = f"backup checksum failed: {exc}"
        return result
    if not _integrity_ok(target):
        target.unlink(missing_ok=True)
        result["error"] = "backup failed integrity_check; deleted"
        return result

    result["ok"] = True
    result["file"] = str(target)
    result["sha256"] = checksum
    result["pruned"] = _prune(backup_dir, keep)
    return result


def _prune(backup_dir: Path, keep: int) -> int:
    """Delete the oldest backups beyond the newest ``keep``; returns count."""
    if keep < 0:
        keep = 0
    # Sort by modification time, newest last: two runs can land in the same
    # second (the collision suffix in the name then breaks lexicographic
    # ordering), and a copied-in backup may carry a skewed mtime.
    backups = sorted(
        backup_dir.glob("voxylis-*.db"),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
    )
    removed = 0
    for stale in backups[: len(backups) - keep]:
        try:
            stale.unlink()
            removed += 1
        except OSError:
            continue  # a file held open elsewhere must not abort the run
    return removed


def restore(
    backup_file: Path,
    db_path: Path | None = None,
    force: bool = False,
) -> dict:
    """Restore a backup over the live database.

    Refuses to overwrite a non-empty live database unless ``force`` is given,
    verifies the backup's integrity first, replaces the file atomically, and
    removes stale WAL sidecars so a restarted app cannot resume frames that
    belonged to the discarded database.
    """
    result: dict = {"ok": False, "error": None, "verified_backup": False, "forced": bool(force)}

    if db_path is None:
        db_path = _live_db_path()
    db_path = Path(db_path)
    backup_file = Path(backup_file)

    if not backup_file.exists():
        result["error"] = f"backup not found: {backup_file}"
        return result
    if not _integrity_ok(backup_file):
        result["error"] = "backup failed integrity_check; refusing to restore a corrupt file"
        return result
    result["verified_backup"] = True

    live_is_empty = (not db_path.exists()) or db_path.stat().st_size == 0
    if not force and not live_is_empty:
        result["error"] = (
            f"live database {db_path} exists and is non-empty; " "pass --force to overwrite it (stop the app first)"
        )
        return result

    # Quiesce check: if another process holds a write lock, replacing the file
    # underneath it would corrupt that process's view. Only worth refusing
    # when the operator has not already accepted --force.
    if db_path.exists():
        try:
            probe = sqlite3.connect(str(db_path), timeout=0.5)
            try:
                probe.execute("BEGIN IMMEDIATE")
                probe.execute("ROLLBACK")
            finally:
                probe.close()
        except sqlite3.OperationalError as exc:
            if not force and "locked" in str(exc).lower():
                result["error"] = "live database is locked by another process; stop the app first"
                return result
        except sqlite3.Error:
            pass

    # Copy to a sibling temp file, confirm the copy matches byte for byte, then
    # rename over the live path (atomic on the same volume).
    tmp = db_path.with_name(db_path.name + ".restore-tmp")
    try:
        shutil.copyfile(backup_file, tmp)
        if _sha256(tmp) != _sha256(backup_file):
            raise RuntimeError("checksum mismatch between backup and temp copy")
        tmp.replace(db_path)
    except (OSError, RuntimeError) as exc:
        tmp.unlink(missing_ok=True)
        result["error"] = f"restore failed: {exc}"
        return result

    # The old database's WAL sidecars belong to the discarded file and must not
    # be replayed into the restored one.
    for sidecar in (db_path.with_name(db_path.name + "-wal"), db_path.with_name(db_path.name + "-shm")):
        try:
            sidecar.unlink()
        except OSError:
            pass

    try:
        con = sqlite3.connect(str(db_path))
        try:
            con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            con.close()
    except sqlite3.Error:
        pass  # a fresh database has nothing to checkpoint

    result["ok"] = True
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m web.backup",
        description="Safe backup / restore for the Voxylis SQLite database",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=None,
        help="directory for backups (default: $VOXYLIS_BACKUP_DIR or ./backups)",
    )
    parser.add_argument("--keep", type=int, default=14, help="retention count (default: 14)")
    parser.add_argument(
        "--restore",
        metavar="FILE",
        type=Path,
        default=None,
        help="restore this backup instead of taking one",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite a non-empty live database (stop the app first)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="explicit database path (default: $VOXYLIS_DB_PATH or web/data/voxylis.db)",
    )
    args = parser.parse_args(argv)

    if args.restore:
        outcome = restore(args.restore, db_path=args.db, force=args.force)
    else:
        outcome = backup(backup_dir=args.backup_dir, keep=args.keep, db_path=args.db)

    print(json.dumps(outcome, default=str))
    return 0 if outcome["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
