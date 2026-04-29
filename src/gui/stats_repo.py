"""Read-only helpers around ``%APPDATA%/vry/stats.json``.

``src/stats.py`` writes one JSON file mapping each puuid we've ever seen in a
match to a list of per-match snapshots ``{name, agent, map, rank, rr,
match_id, epoch}``. The GUI uses that to enrich the live tracker (last-match
tooltip, played-with-you counter, RR delta) and to back the Match history
and Stats / Charts pages.

The file may be opened concurrently by the running tracker (which writes new
entries when matches finish), so we always read it fresh and tolerate I/O
errors gracefully.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

from src.gui.utils import stats_path


class StatsRepository:
    """Load + index ``stats.json`` and expose convenience lookups."""

    def __init__(self) -> None:
        self._raw: Dict[str, List[Dict[str, Any]]] = {}
        self._loaded_at: float = 0.0

    # ----------------------------------------------------------- loading
    def reload(self) -> None:
        path = stats_path()
        if not path or not os.path.exists(path):
            self._raw = {}
            self._loaded_at = time.time()
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        # Normalise: every value must be a list of dicts in chronological order.
        self._raw = {
            str(puuid): [e for e in entries if isinstance(e, dict)]
            for puuid, entries in data.items()
            if isinstance(entries, list)
        }
        self._loaded_at = time.time()

    @property
    def loaded_at(self) -> float:
        return self._loaded_at

    @property
    def empty(self) -> bool:
        return not self._raw

    # ----------------------------------------------------------- lookups
    def entries(self, puuid: str) -> List[Dict[str, Any]]:
        return list(self._raw.get(puuid, []))

    def last_match(self, puuid: str) -> Optional[Dict[str, Any]]:
        entries = self._raw.get(puuid)
        return entries[-1] if entries else None

    def times_played_with(self, puuid: str) -> int:
        """Return the number of distinct prior matches we logged for ``puuid``."""

        entries = self._raw.get(puuid)
        if not entries:
            return 0
        seen: set[str] = set()
        for e in entries:
            mid = str(e.get("match_id") or "")
            if mid:
                seen.add(mid)
        return len(seen)

    def last_rr_delta(self, puuid: str) -> Optional[int]:
        """Difference between the two most recent RR snapshots, if any.

        A positive number means the player gained RR in their last completed
        match; negative means lost. ``None`` means we don't have enough data
        to compute a delta.
        """

        entries = self._raw.get(puuid)
        if not entries or len(entries) < 2:
            return None
        try:
            current = int(entries[-1].get("rr"))
            previous = int(entries[-2].get("rr"))
        except (TypeError, ValueError):
            return None
        if entries[-1].get("rank") != entries[-2].get("rank"):
            # Promotions/demotions reset RR \u2014 the diff isn't meaningful.
            return None
        return current - previous

    # ---------------------------------------------------------- aggregates
    def own_history(self, own_puuid: str) -> List[Dict[str, Any]]:
        """Chronological match history for the local player (newest first)."""

        entries = list(self._raw.get(own_puuid, []))
        entries.sort(key=lambda e: float(e.get("epoch") or 0), reverse=True)
        return entries

    def all_puuids(self) -> List[str]:
        return list(self._raw.keys())
