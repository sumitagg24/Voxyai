"""
Transcription history facade.

``HistoryManager`` keeps the small public API the rest of the app already used
(``add`` / ``get_all`` / ``get_recent`` / ``delete`` / ``clear`` / ``len()``)
but now delegates to :class:`core.history_store.HistoryStore`, which persists to
SQLite inside the user-data directory instead of a plaintext JSON file in the
install directory.

Additions over the old implementation: per-item delete, retention, export,
import of the legacy JSON history, and a global enable/disable switch.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from utils import paths
from utils.logger import log_debug, log_info

from core.history_store import HistoryStore

MAX_DEFAULT = 500
RETENTION_DEFAULT_DAYS = 0  # 0 = keep until the max_entries cap is hit


class HistoryManager:
    def __init__(
        self,
        max_entries: int = MAX_DEFAULT,
        db_path: Optional[Path] = None,
        enabled: bool = True,
        retention_days: int = RETENTION_DEFAULT_DAYS,
    ):
        self.store = HistoryStore(
            db_path=db_path,
            max_entries=max_entries,
            retention_days=retention_days,
            enabled=enabled,
        )
        self._imported_legacy = False
        self._import_legacy_once()

    # ── legacy migration ─────────────────────────────────────────────────────

    def _import_legacy_once(self) -> None:
        if self._imported_legacy or self.store.count() > 0:
            return
        self._imported_legacy = True
        candidates = [
            paths.data_dir() / "history.legacy.json",
            paths.user_data_root() / "logs" / "transcription_history.json",
        ]
        for candidate in candidates:
            if candidate.is_file():
                self.store.import_legacy(candidate)
                break

    # ── public API ───────────────────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        return self.store.enabled

    @property
    def max_entries(self) -> int:
        return self.store.max_entries

    @max_entries.setter
    def max_entries(self, value: int) -> None:
        self.store.max_entries = max(1, int(value))
        self.store.enforce_limit()

    def configure(
        self,
        max_entries: Optional[int] = None,
        retention_days: Optional[int] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        self.store.configure(max_entries=max_entries, retention_days=retention_days, enabled=enabled)

    def add(
        self,
        raw: str,
        enhanced: Optional[str] = None,
        mode: str = "",
        language: str = "",
        app_context: str = "",
        duration_ms: int = 0,
        injected: bool = False,
        meta: Optional[dict] = None,
    ) -> Optional[dict]:
        """Add a transcription. Returns the stored entry or ``None``."""
        if not self.store.enabled:
            log_debug("History disabled — entry not stored")
            return None
        return self.store.add(
            raw=raw,
            enhanced=enhanced,
            mode=mode,
            language=language,
            app_context=app_context,
            duration_ms=duration_ms,
            injected=injected,
            meta=meta,
        )

    def get_all(self) -> List[dict]:
        return self.store.get_all()

    def get_recent(self, n: int = 10) -> List[dict]:
        return self.store.get_recent(n)

    def delete(self, entry_id: int) -> bool:
        return self.store.delete(entry_id)

    def clear(self) -> bool:
        return self.store.clear()

    def export(self, destination: Path, fmt: str = "json") -> Optional[Path]:
        return self.store.export(destination, fmt=fmt)

    def purge_older_than(self, days: int) -> int:
        return self.store.purge_older_than(days)

    def db_path(self) -> str:
        return self.store.path()

    def __len__(self) -> int:
        return self.store.count()


def default_history() -> HistoryManager:
    """Build a HistoryManager from settings, if a settings dict is available."""
    from utils.helpers import load_json

    config = load_json(str(paths.settings_path()))
    enabled = bool(config.get("history_enabled", True))
    if not enabled:
        log_info("History is disabled in settings")
    return HistoryManager(
        max_entries=int(config.get("max_history", MAX_DEFAULT)),
        enabled=enabled,
        retention_days=int(config.get("history_retention_days", RETENTION_DEFAULT_DAYS)),
    )
