"""
Word count & usage stats tracker for Voxylis.

Stored at ``%LOCALAPPDATA%\\Voxylis\\data\\stats.json``.  Counts only - no
transcript text is ever persisted here.
"""

import json
import os
from datetime import date

from utils import paths
from utils.logger import log_debug, log_error

_EMPTY = {"daily": {}, "total": {"transcriptions": 0, "words": 0, "commands": 0}}


def _resolve_stats_path() -> str:
    return str(paths.stats_path())


class StatsTracker:
    def __init__(self, stats_path: str = None):
        self._stats_file = stats_path or _resolve_stats_path()
        self._data = self._load()

    def _load(self) -> dict:
        try:
            if os.path.exists(self._stats_file):
                with open(self._stats_file, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                if isinstance(data, dict):
                    data.setdefault("daily", {})
                    data.setdefault("total", dict(_EMPTY["total"]))
                    return data
        except (OSError, json.JSONDecodeError) as exc:
            log_error(f"Stats load error: {exc}")
        return {"daily": {}, "total": dict(_EMPTY["total"])}

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._stats_file), exist_ok=True)
            with open(self._stats_file, "w", encoding="utf-8") as handle:
                json.dump(self._data, handle, indent=2)
        except OSError as exc:
            log_error(f"Stats save error: {exc}")

    def _today(self) -> str:
        return date.today().isoformat()

    def _day(self) -> dict:
        today = self._today()
        if today not in self._data["daily"]:
            self._data["daily"][today] = {"transcriptions": 0, "words": 0, "commands": 0}
        return self._data["daily"][today]

    def record_transcription(self, text: str, language: str = "") -> None:
        words = len((text or "").split())
        self._day()["transcriptions"] += 1
        self._day()["words"] += words
        self._data["total"]["transcriptions"] += 1
        self._data["total"]["words"] += words
        self._save()
        log_debug(f"Stats: +{words} words")

    def record_command(self) -> None:
        self._day()["commands"] += 1
        self._data["total"]["commands"] += 1
        self._save()

    def get_today(self) -> dict:
        return dict(self._day())

    def get_total(self) -> dict:
        return dict(self._data["total"])

    def get_summary(self) -> str:
        today = self.get_today()
        total = self.get_total()
        return (
            f"Today: {today['transcriptions']} transcriptions, {today['words']} words\n"
            f"All time: {total['transcriptions']} transcriptions, {total['words']} words"
        )
