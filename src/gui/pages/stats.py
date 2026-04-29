"""Stats / charts page \u2014 aggregate insights from ``stats.json``.

We don't depend on matplotlib or pyqtgraph: a tiny QtCharts-free implementation
based on a custom QWidget is enough for the visualisations we need (RR
trend, winrate per agent, winrate per map).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.gui.pages._common import card, page_header
from src.gui.stats_repo import StatsRepository

_ANSI_RE = re.compile(r"(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]")


def _strip_ansi(value: Any) -> str:
    return _ANSI_RE.sub("", str(value or ""))


class _RRTrendChart(QWidget):
    """Tiny line chart of ``(epoch, rr)`` points."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._points: List[Tuple[float, float]] = []
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(180)

    def set_points(self, points: List[Tuple[float, float]]) -> None:
        self._points = list(points)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt API)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(40, 12, -12, -28)
        painter.fillRect(self.rect(), QColor("#181c24"))

        # Axes
        axis_pen = QPen(QColor("#2a3140"))
        axis_pen.setWidth(1)
        painter.setPen(axis_pen)
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        painter.drawLine(rect.topLeft(), rect.bottomLeft())

        if not self._points:
            painter.setPen(QColor("#8b95a3"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No data yet")
            return

        xs = [p[0] for p in self._points]
        ys = [p[1] for p in self._points]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        if x_max == x_min:
            x_max = x_min + 1
        # pad y slightly
        y_pad = max(5, (y_max - y_min) * 0.1)
        y_min -= y_pad
        y_max += y_pad

        def to_xy(x: float, y: float) -> QPointF:
            xn = (x - x_min) / (x_max - x_min)
            yn = (y - y_min) / (y_max - y_min) if y_max != y_min else 0.5
            return QPointF(
                rect.left() + xn * rect.width(),
                rect.bottom() - yn * rect.height(),
            )

        # Y axis labels (min/max)
        painter.setPen(QColor("#8b95a3"))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(
            0,
            int(rect.top()),
            int(rect.left() - 4),
            14,
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
            f"{int(y_max)}",
        )
        painter.drawText(
            0,
            int(rect.bottom() - 14),
            int(rect.left() - 4),
            14,
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
            f"{int(y_min)}",
        )
        # X axis labels (first / last date)
        first = datetime.fromtimestamp(x_min).strftime("%b %d")
        last = datetime.fromtimestamp(x_max).strftime("%b %d")
        painter.drawText(
            int(rect.left()),
            int(rect.bottom() + 4),
            int(rect.width() // 2),
            16,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
            first,
        )
        painter.drawText(
            int(rect.left() + rect.width() // 2),
            int(rect.bottom() + 4),
            int(rect.width() // 2),
            16,
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop),
            last,
        )

        # Filled area under the line
        path = QPainterPath()
        path.moveTo(to_xy(self._points[0][0], y_min))
        for x, y in self._points:
            path.lineTo(to_xy(x, y))
        path.lineTo(to_xy(self._points[-1][0], y_min))
        path.closeSubpath()
        painter.fillPath(path, QBrush(QColor(255, 70, 85, 50)))

        # Line
        line_pen = QPen(QColor("#ff4655"))
        line_pen.setWidth(2)
        painter.setPen(line_pen)
        last_pt = None
        for x, y in self._points:
            pt = to_xy(x, y)
            if last_pt is not None:
                painter.drawLine(last_pt, pt)
            last_pt = pt

        # Dots
        painter.setBrush(QColor("#ff4655"))
        painter.setPen(QColor("#0f1419"))
        for x, y in self._points:
            pt = to_xy(x, y)
            painter.drawEllipse(pt, 3.0, 3.0)


class StatsPage(QWidget):
    """RR trend + winrate breakdowns by agent and by map."""

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

    def set_own_puuid(self, puuid: str) -> None:
        if puuid and puuid != self._own_puuid:
            self._own_puuid = puuid
            self.refresh()

    def refresh(self) -> None:
        self._stats_repo.reload()
        matches = self._collect_matches()
        self._update_summary(matches)
        self._update_trend(matches)
        self._update_breakdown(self._agent_model, self._aggregate(matches, "agent"))
        self._update_breakdown(self._map_model, self._aggregate(matches, "map"))

    # ------------------------------------------------------- layout
    def _build_layout(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(16)

        root.addWidget(
            page_header(
                "Stats",
                "Trends and winrates derived from %APPDATA%/vry/stats.json",
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
        root.addLayout(toolbar)

        self._trend = _RRTrendChart()
        root.addWidget(card(self._trend, title="RR over time"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(0)

        self._agent_model = QStandardItemModel(0, 5, self)
        self._agent_model.setHorizontalHeaderLabels(
            ["Agent", "Played", "W", "L", "Win %"]
        )
        agent_view = self._build_table(self._agent_model)
        grid.addWidget(card(agent_view, title="By agent"), 0, 0)

        self._map_model = QStandardItemModel(0, 5, self)
        self._map_model.setHorizontalHeaderLabels(
            ["Map", "Played", "W", "L", "Win %"]
        )
        map_view = self._build_table(self._map_model)
        grid.addWidget(card(map_view, title="By map"), 0, 1)

        root.addLayout(grid, 1)

    @staticmethod
    def _build_table(model: QStandardItemModel) -> QTableView:
        table = QTableView()
        table.setModel(model)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, model.columnCount()):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        return table

    # ------------------------------------------------------- data
    def _collect_matches(self) -> List[Dict[str, Any]]:
        if not self._own_puuid:
            return []
        entries = self._stats_repo.entries(self._own_puuid)
        per_match: Dict[str, Dict[str, Any]] = {}
        for e in entries:
            mid = str(e.get("match_id") or "")
            if not mid:
                continue
            try:
                ts = float(e.get("epoch") or 0)
            except (TypeError, ValueError):
                ts = 0.0
            existing = per_match.get(mid)
            if existing is None:
                per_match[mid] = e
                continue
            try:
                existing_ts = float(existing.get("epoch") or 0)
            except (TypeError, ValueError):
                existing_ts = 0.0
            if ts >= existing_ts:
                per_match[mid] = e
        ordered = sorted(
            per_match.values(),
            key=lambda e: float(e.get("epoch") or 0),
        )
        # Compute deltas vs prior match
        prev_rank = None
        prev_rr = None
        for match in ordered:
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
        return ordered

    def _update_summary(self, matches: List[Dict[str, Any]]) -> None:
        if not matches:
            self._summary_label.setText(
                "No matches recorded yet."
                if self._own_puuid
                else "Waiting for the local player puuid \u2014 start the tracker."
            )
            return
        wins = sum(
            1 for m in matches if isinstance(m.get("_delta"), int) and m["_delta"] > 0
        )
        losses = sum(
            1 for m in matches if isinstance(m.get("_delta"), int) and m["_delta"] < 0
        )
        total_delta = sum(
            int(m["_delta"]) for m in matches if isinstance(m.get("_delta"), int)
        )
        sign = "+" if total_delta > 0 else ""
        self._summary_label.setText(
            f"{len(matches)} matches \u2022 W:{wins} / L:{losses} \u2022 \u0394RR {sign}{total_delta}"
        )

    def _update_trend(self, matches: List[Dict[str, Any]]) -> None:
        # Approximate "MMR" by ``rank * 100 + rr`` so promotions show as jumps.
        points: List[Tuple[float, float]] = []
        for m in matches:
            try:
                ts = float(m.get("epoch") or 0)
                rank = int(m.get("rank") or 0)
                rr = int(m.get("rr") or 0)
            except (TypeError, ValueError):
                continue
            if ts <= 0:
                continue
            points.append((ts, rank * 100 + rr))
        self._trend.set_points(points)

    def _aggregate(
        self, matches: List[Dict[str, Any]], key: str
    ) -> List[Tuple[str, int, int, int]]:
        buckets: Dict[str, Dict[str, int]] = {}
        for m in matches:
            label = _strip_ansi(m.get(key)) or "\u2014"
            bucket = buckets.setdefault(
                label, {"played": 0, "wins": 0, "losses": 0}
            )
            bucket["played"] += 1
            delta = m.get("_delta")
            if isinstance(delta, int):
                if delta > 0:
                    bucket["wins"] += 1
                elif delta < 0:
                    bucket["losses"] += 1
        rows = [
            (label, b["played"], b["wins"], b["losses"])
            for label, b in buckets.items()
        ]
        rows.sort(key=lambda r: r[1], reverse=True)
        return rows

    def _update_breakdown(
        self,
        model: QStandardItemModel,
        rows: List[Tuple[str, int, int, int]],
    ) -> None:
        model.removeRows(0, model.rowCount())
        for label, played, wins, losses in rows:
            decisive = wins + losses
            wr = (wins / decisive * 100) if decisive else 0
            cells = [
                QStandardItem(label),
                QStandardItem(str(played)),
                QStandardItem(str(wins)),
                QStandardItem(str(losses)),
                QStandardItem(f"{wr:.0f}%" if decisive else "\u2014"),
            ]
            for idx, item in enumerate(cells):
                item.setEditable(False)
                if idx > 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if decisive:
                if wr >= 60:
                    cells[4].setForeground(QColor("#5fcf80"))
                elif wr <= 40:
                    cells[4].setForeground(QColor("#ff4655"))
            model.appendRow(cells)
