"""
Transcription history manager for Voxylis
Saves every transcription to a JSON file and provides retrieval.
"""

import json
import os
from datetime import datetime
from typing import List, Optional
from utils.logger import log_info, log_error, log_debug

HISTORY_FILE = "logs/transcription_history.json"
MAX_DEFAULT = 100


class HistoryManager:
    def __init__(self, max_entries: int = MAX_DEFAULT):
        self.max_entries = max_entries
        self._entries: List[dict] = []
        self._load()

    # ── persistence ───────────────────────────────────────────────────────────

    def _load(self):
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    self._entries = json.load(f)
                log_debug(f"History loaded: {len(self._entries)} entries")
        except Exception as e:
            log_error(f"Failed to load history: {e}")
            self._entries = []

    def _save(self):
        try:
            os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log_error(f"Failed to save history: {e}")

    # ── public API ────────────────────────────────────────────────────────────

    def add(self, raw: str, enhanced: Optional[str] = None, mode: str = "", language: str = ""):
        """Add a new transcription entry."""
        entry = {
            "id": len(self._entries) + 1,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "raw": raw,
            "enhanced": enhanced or raw,
            "mode": mode,
            "language": language,
            "word_count": len((enhanced or raw).split()),
        }
        self._entries.insert(0, entry)          # newest first
        if len(self._entries) > self.max_entries:
            self._entries = self._entries[:self.max_entries]
        self._save()
        log_info(f"History: saved entry #{entry['id']} ({entry['word_count']} words)")
        return entry

    def get_all(self) -> List[dict]:
        return list(self._entries)

    def get_recent(self, n: int = 10) -> List[dict]:
        return self._entries[:n]

    def delete(self, entry_id: int):
        self._entries = [e for e in self._entries if e.get("id") != entry_id]
        self._save()

    def clear(self):
        self._entries = []
        self._save()
        log_info("History cleared")

    def __len__(self):
        return len(self._entries)
