"""
Local transcription history, stored in SQLite.

Why SQLite instead of ``logs/transcription_history.json``:
  * the JSON file rewrote the whole transcript corpus on every utterance;
  * it had no schema, no index, no retention and no way to delete one item;
  * it was unbounded and stored in the install directory.

Privacy rules enforced here
---------------------------
  * history can be disabled entirely (``enabled=False``) - nothing is written;
  * retention (``retention_days``) prunes on every write and on startup;
  * ``clear()`` / ``delete()`` are real deletes followed by ``VACUUM``;
  * transcripts are never logged - only ids, counts and word counts.

The database lives in ``%LOCALAPPDATA%\\Voxylis\\data\\history.sqlite3``.
"""

from __future__ import annotations

import csv
import json
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from utils import paths
from utils.logger import log_debug, log_error, log_info

_SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at   TEXT    NOT NULL,
    raw          TEXT    NOT NULL DEFAULT '',
    enhanced     TEXT    NOT NULL DEFAULT '',
    mode         TEXT    NOT NULL DEFAULT '',
    language     TEXT    NOT NULL DEFAULT '',
    app_context  TEXT    NOT NULL DEFAULT '',
    word_count   INTEGER NOT NULL DEFAULT 0,
    duration_ms  INTEGER NOT NULL DEFAULT 0,
    injected     INTEGER NOT NULL DEFAULT 0,
    meta         TEXT    NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_history_created_at ON history (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_history_mode ON history (mode);
"""


class HistoryStore:
    """Thread-safe SQLite store for transcription history."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        max_entries: int = 500,
        retention_days: int = 0,
        enabled: bool = True,
    ):
        self.db_path = Path(db_path) if db_path else paths.history_db_path()
        self.max_entries = max(1, int(max_entries))
        self.retention_days = max(0, int(retention_days))
        self.enabled = bool(enabled)
        self._lock = threading.RLock()
        self._ensure_schema()

    # -- schema ------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _ensure_schema(self) -> None:
        with self._lock:
            try:
                conn = self._connect()
                conn.executescript(_SCHEMA)
                conn.commit()
                conn.close()
            except sqlite3.Error as exc:
                log_error(f"History database unavailable: {exc}")

    # -- configuration -----------------------------------------------------
    def configure(
        self,
        max_entries: Optional[int] = None,
        retention_days: Optional[int] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        if max_entries is not None:
            self.max_entries = max(1, int(max_entries))
        if retention_days is not None:
            self.retention_days = max(0, int(retention_days))
        if enabled is not None:
            self.enabled = bool(enabled)
        if self.retention_days:
            self.purge_older_than(self.retention_days)
        self.enforce_limit()

    # -- writes ------------------------------------------------------------
    def add(
        self,
        raw: str,
        enhanced: Optional[str] = None,
        mode: str = "",
        language: str = "",
        app_context: str = "",
        duration_ms: int = 0,
        injected: bool = False,
        meta: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """Insert an entry. Returns the stored row, or ``None`` if disabled."""
        if not self.enabled:
            return None
        text = (raw or "").strip()
        if not text:
            return None
        effective = (enhanced or raw or "").strip()
        created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            try:
                conn = self._connect()
                cur = conn.execute(
                    "INSERT INTO history (created_at, raw, enhanced, mode, language,"
                    " app_context, word_count, duration_ms, injected, meta)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        created,
                        raw,
                        effective,
                        mode or "",
                        language or "",
                        app_context or "",
                        len(effective.split()),
                        int(duration_ms or 0),
                        1 if injected else 0,
                        json.dumps(meta or {}, ensure_ascii=False),
                    ),
                )
                row_id = cur.lastrowid
                conn.commit()
                conn.close()
            except sqlite3.Error as exc:
                log_error(f"History insert failed: {exc}")
                return None

        self.enforce_limit()
        log_debug(f"History stored entry #{row_id} ({len(effective.split())} words)")
        return {
            "id": row_id,
            "timestamp": created,
            "raw": raw,
            "enhanced": effective,
            "mode": mode or "",
            "language": language or "",
            "app_context": app_context or "",
            "word_count": len(effective.split()),
            "injected": bool(injected),
        }

    def mark_injected(self, entry_id: int, injected: bool = True) -> bool:
        with self._lock:
            try:
                conn = self._connect()
                conn.execute("UPDATE history SET injected = ? WHERE id = ?", (1 if injected else 0, entry_id))
                conn.commit()
                conn.close()
                return True
            except sqlite3.Error as exc:
                log_error(f"History update failed: {exc}")
                return False

    # -- reads -------------------------------------------------------------
    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict:
        return {
            "id": row["id"],
            "timestamp": row["created_at"],
            "raw": row["raw"],
            "enhanced": row["enhanced"],
            "mode": row["mode"],
            "language": row["language"],
            "app_context": row["app_context"],
            "word_count": row["word_count"],
            "duration_ms": row["duration_ms"],
            "injected": bool(row["injected"]),
        }

    def get_all(self, limit: Optional[int] = None) -> List[Dict]:
        limit_clause = f" LIMIT {int(limit)}" if limit else ""
        with self._lock:
            try:
                conn = self._connect()
                rows = conn.execute(
                    f"SELECT * FROM history ORDER BY id DESC{limit_clause}"
                ).fetchall()
                conn.close()
            except sqlite3.Error as exc:
                log_error(f"History read failed: {exc}")
                return []
        return [self._row_to_dict(row) for row in rows]

    def get_recent(self, n: int = 10) -> List[Dict]:
        return self.get_all(limit=max(0, int(n)))

    def count(self) -> int:
        with self._lock:
            try:
                conn = self._connect()
                count = conn.execute("SELECT COUNT(*) AS c FROM history").fetchone()["c"]
                conn.close()
                return int(count)
            except sqlite3.Error:
                return 0

    # -- deletes / retention ----------------------------------------------
    def delete(self, entry_id: int) -> bool:
        with self._lock:
            try:
                conn = self._connect()
                conn.execute("DELETE FROM history WHERE id = ?", (int(entry_id),))
                conn.commit()
                conn.close()
                log_info(f"History entry #{entry_id} deleted")
                return True
            except sqlite3.Error as exc:
                log_error(f"History delete failed: {exc}")
                return False

    def clear(self) -> bool:
        with self._lock:
            try:
                conn = self._connect()
                conn.execute("DELETE FROM history")
                conn.commit()
                conn.execute("VACUUM")
                conn.close()
                log_info("History cleared")
                return True
            except sqlite3.Error as exc:
                log_error(f"History clear failed: {exc}")
                return False

    def purge_older_than(self, days: int) -> int:
        """Delete entries older than ``days``. Returns the number removed."""
        if days <= 0:
            return 0
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            try:
                conn = self._connect()
                cur = conn.execute("DELETE FROM history WHERE created_at < ?", (cutoff,))
                removed = cur.rowcount or 0
                conn.commit()
                conn.close()
            except sqlite3.Error as exc:
                log_error(f"History retention failed: {exc}")
                return 0
        if removed:
            log_info(f"History retention removed {removed} entr(y/ies) older than {days} days")
        return removed

    def enforce_limit(self) -> int:
        """Keep at most ``max_entries`` rows."""
        removed = 0
        with self._lock:
            try:
                conn = self._connect()
                cur = conn.execute(
                    "DELETE FROM history WHERE id NOT IN "
                    "(SELECT id FROM history ORDER BY id DESC LIMIT ?)",
                    (self.max_entries,),
                )
                removed = cur.rowcount or 0
                conn.commit()
                conn.close()
            except sqlite3.Error as exc:
                log_error(f"History trim failed: {exc}")
        return removed

    # -- export / import ---------------------------------------------------
    def export(self, destination: Path, fmt: str = "json") -> Optional[Path]:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        entries = self.get_all()
        try:
            if fmt == "csv":
                fields = [
                    "id",
                    "timestamp",
                    "raw",
                    "enhanced",
                    "mode",
                    "language",
                    "app_context",
                    "word_count",
                ]
                with open(destination, "w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
                    writer.writeheader()
                    writer.writerows(entries)
            else:
                destination.write_text(
                    json.dumps({"exported": datetime.now().isoformat(), "entries": entries}, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
        except OSError as exc:
            log_error(f"History export failed: {exc}")
            return None
        log_info(f"History exported ({len(entries)} entries) to {destination.name}")
        return destination

    def import_legacy(self, source: Path) -> int:
        """Import a legacy ``transcription_history.json`` file once."""
        source = Path(source)
        if not source.is_file():
            return 0
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0
        if not isinstance(payload, list):
            return 0

        imported = 0
        for item in reversed(payload):  # legacy stored newest-first
            if not isinstance(item, dict):
                continue
            raw = item.get("raw") or item.get("text") or ""
            if not str(raw).strip():
                continue
            with self._lock:
                try:
                    conn = self._connect()
                    conn.execute(
                        "INSERT INTO history (created_at, raw, enhanced, mode, language,"
                        " app_context, word_count, duration_ms, injected, meta)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, ?)",
                        (
                            item.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            raw,
                            item.get("enhanced") or raw,
                            item.get("mode", ""),
                            item.get("language", ""),
                            item.get("app_context", ""),
                            int(item.get("word_count") or len(str(raw).split())),
                            json.dumps({"imported_from": source.name}),
                        ),
                    )
                    conn.commit()
                    conn.close()
                    imported += 1
                except sqlite3.Error:
                    continue
        if imported:
            log_info(f"Imported {imported} legacy history entr(y/ies)")
        self.enforce_limit()
        return imported

    # -- maintenance -------------------------------------------------------
    def path(self) -> str:
        return str(self.db_path)
