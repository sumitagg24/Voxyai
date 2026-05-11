"""
Word count & usage stats tracker for Voxylis.
"""

import json
import os
from datetime import datetime, date
from utils.logger import log_error, log_debug

STATS_FILE = "logs/stats.json"


class StatsTracker:
    def __init__(self):
        self._data = self._load()

    def _load(self) -> dict:
        try:
            if os.path.exists(STATS_FILE):
                with open(STATS_FILE, "r") as f:
                    return json.load(f)
        except Exception as e:
            log_error(f"Stats load error: {e}")
        return {"daily": {}, "total": {"transcriptions": 0, "words": 0, "commands": 0}}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
            with open(STATS_FILE, "w") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            log_error(f"Stats save error: {e}")

    def _today(self) -> str:
        return date.today().isoformat()

    def _day(self) -> dict:
        d = self._today()
        if d not in self._data["daily"]:
            self._data["daily"][d] = {"transcriptions": 0, "words": 0, "commands": 0}
        return self._data["daily"][d]

    def record_transcription(self, text: str, language: str = ""):
        words = len(text.split())
        self._day()["transcriptions"] += 1
        self._day()["words"] += words
        self._data["total"]["transcriptions"] += 1
        self._data["total"]["words"] += words
        self._save()
        log_debug(f"Stats: +{words} words")

    def record_command(self):
        self._day()["commands"] += 1
        self._data["total"]["commands"] += 1
        self._save()

    def get_today(self) -> dict:
        return dict(self._day())

    def get_total(self) -> dict:
        return dict(self._data["total"])

    def get_summary(self) -> str:
        t = self.get_today()
        total = self.get_total()
        return (
            f"Today: {t['transcriptions']} transcriptions, {t['words']} words\n"
            f"All time: {total['transcriptions']} transcriptions, {total['words']} words"
        )
