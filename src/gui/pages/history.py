"""Match history page \u2014 your past matches as recorded in ``stats.json``.

The local tracker writes one row per ingame heartbeat into
``%APPDATA%/vry/stats.json`` (see ``src/stats.py``). For the local user we
group those rows by ``match_id`` so each row in this table corresponds to a
single completed match: agent / map / rank / RR / RR change vs the previous
match / time ago.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.constants import NUMBERTORANKS
from src.gui.pages._common import page_header
from src.gui.stats_repo import StatsRepository

_COLUMNS: List[tuple[str, str]] = [
    ("when", "When"),
    ("map", "Map"),
    ("agent", "Agent"),
    ("rank", "Rank"),
    ("rr", "RR"),
    ("delta", "\u00b1RR"),
]


def _strip_ansi(value: str) -> str:
    import re

    return re.sub(
        r"(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]", "", str(value or "")
    )


def _rank_label(rank_idx: Any) -> str:
    if not isinstance(rank_idx, int):
        return "\u2014"
    if 0 <= rank_idx < len(NUMBERTORANKS):
        return _strip_ansi(NUMBERTORANKS[rank_idx])
    return str(rank_idx)


def _coerce_map_label(value: Any) -> str:
    """Map values were historically stored as a ``{'name': ..., 'splash': ...}``
    dict (and even as a stringified dict), so normalise to a clean display
    label here.
    """

    if isinstance(value, dict):
        name = value.get("name")
        return _strip_ansi(str(name or "\u2014"))
    if isinstance(value, str):
        stripped = value.strip()
        # Fallback for legacy entries serialised as a Python dict via repr().
        if stripped.startswith("{") and "'name'" in stripped:
            try:
                import ast

                parsed = ast.literal_eval(stripped)
                if isinstance(parsed, dict) and parsed.get("name"):
                    return _strip_ansi(str(parsed["name"]))
            except (ValueError, SyntaxError):
                pass
        return _strip_ansi(stripped or "\u2014")
    return "\u2014"


def _format_when(epoch: Any) -> str:
    try:
        ts = float(epoch)
    except (TypeError, ValueError):
        return "\u2014"
    if ts <= 0:
        return "\u2014"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


class HistoryPage(QWidget):
    """Render ``stats.json`` for the local player as a table of past matches."""

    def __init__(
        self,
        stats_repo: Optional[StatsRepository] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._stats_repo = stats_repo or StatsRepository()
        self._own_puuid: str = ""

        self._build_layout()
        self.refresh()

    # --------------------------------------------------------- public API
    def set_own_puuid(self, puuid: str) -> None:
        if puuid and puuid != self._own_puuid:
            self._own_puuid = puuid
            self.refresh()

    def refresh(self) -> None:
        self._stats_repo.reload()
        matches = self._collect_matches()
        self._populate(matches)

    # --------------------------------------------------------- layout
    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)

        layout.addWidget(
            page_header(
                "Match history",
                "Locally recorded competitive matches from %APPDATA%/vry/stats.json",
            )
        )

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self._summary_label = QLabel("\u2014")
        self._summary_label.setObjectName("pageSubtitle")
        toolbar.addWidget(self._summary_label)
        toolbar.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(refresh_btn)
        layout.addLayout(toolbar)

        self._model = QStandardItemModel(0, len(_COLUMNS), self)
        self._model.setHorizontalHeaderLabels([label for _, label in _COLUMNS])

        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in range(2, len(_COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._table, 1)

        self._empty_label = QLabel(
            "No history yet \u2014 finish a competitive match while the tracker is running."
        )
        self._empty_label.setObjectName("pageSubtitle")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setVisible(False)
        layout.addWidget(self._empty_label)

    # --------------------------------------------------------- data
    def _collect_matches(self) -> List[Dict[str, Any]]:
        if not self._own_puuid:
            return []

        entries = self._stats_repo.entries(self._own_puuid)
        # Group by match_id, keep the latest snapshot per match (the heartbeat
        # writes a row every tick during INGAME, so we want the final RR).
        per_match: Dict[str, Dict[str, Any]] = {}
        for e in entries:
            mid = str(e.get("match_id") or "")
            if not mid:
                continue
            existing = per_match.get(mid)
            try:
                e_ts = float(e.get("epoch") or 0)
            except (TypeError, ValueError):
                e_ts = 0.0
            if existing is None:
                per_match[mid] = e
                continue
            try:
                existing_ts = float(existing.get("epoch") or 0)
            except (TypeError, ValueError):
                existing_ts = 0.0
            if e_ts >= existing_ts:
                per_match[mid] = e

        # Sort by epoch desc and compute RR delta vs the previous match.
        ordered = sorted(
            per_match.values(),
            key=lambda e: float(e.get("epoch") or 0),
            reverse=True,
        )

        # Walk in chronological order to compute deltas, then reverse.
        chrono = list(reversed(ordered))
        prev_rank = None
        prev_rr = None
        for match in chrono:
            cur_rank = match.get("rank")
            cur_rr = match.get("rr")
            delta: Optional[int] = None
            try:
                if (
                    prev_rank is not None
                    and prev_rr is not None
                    and cur_rank == prev_rank
                ):
                    delta = int(cur_rr) - int(prev_rr)
            except (TypeError, ValueError):
                delta = None
            match["_delta"] = delta
            prev_rank = cur_rank
            prev_rr = cur_rr
        return list(reversed(chrono))

    def _populate(self, matches: List[Dict[str, Any]]) -> None:
        self._model.removeRows(0, self._model.rowCount())
        if not matches:
            self._summary_label.setText(
                "No matches recorded yet."
                if self._own_puuid
                else "Waiting for the local player puuid \u2014 start the tracker."
            )
            self._empty_label.setVisible(True)
            self._table.setVisible(False)
            return

        self._empty_label.setVisible(False)
        self._table.setVisible(True)
        wins = losses = draws = 0
        total_delta = 0

        for match in matches:
            row: List[QStandardItem] = []
            cells = {
                "when": _format_when(match.get("epoch")),
                "map": _coerce_map_label(match.get("map")),
                "agent": _strip_ansi(str(match.get("agent") or "\u2014")),
                "rank": _rank_label(match.get("rank")),
                "rr": str(match.get("rr") or "\u2014"),
                "delta": "\u2014",
            }
            delta = match.get("_delta")
            if isinstance(delta, int):
                cells["delta"] = f"+{delta}" if delta > 0 else str(delta)
                if delta > 0:
                    wins += 1
                    total_delta += delta
                elif delta < 0:
                    losses += 1
                    total_delta += delta
                else:
                    draws += 1
            for key, _ in _COLUMNS:
                item = QStandardItem(cells[key])
                item.setEditable(False)
                if key in ("rr", "delta"):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if key == "delta" and isinstance(delta, int):
                    if delta > 0:
                        item.setForeground(QColor("#5fcf80"))
                    elif delta < 0:
                        item.setForeground(QColor("#ff4655"))
                row.append(item)
            self._model.appendRow(row)

        played = len(matches)
        sign = "+" if total_delta > 0 else ""
        self._summary_label.setText(
            f"{played} match{'es' if played != 1 else ''} \u2022 "
            f"W:{wins} / L:{losses} / D:{draws} \u2022 \u0394RR {sign}{total_delta}"
        )
