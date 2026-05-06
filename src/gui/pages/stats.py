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


class _PlayHeatmap(QWidget):
    """7\u00d724 grid of match counts coloured by frequency.

    Rows = days of the week (Mon at top, Sun at bottom). Columns = hour of
    the day. Cell colour goes from a flat panel tone (no matches) to the
    accent red (most matches in the dataset). A small tooltip exposes the
    raw count on hover.
    """

    DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._counts: List[List[int]] = [[0] * 24 for _ in range(7)]
        self._max: int = 0
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMouseTracking(True)

    def set_data(self, counts: List[List[int]]) -> None:
        self._counts = counts
        self._max = max((max(row) for row in counts), default=0)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#181c24"))

        margin_left = 38
        margin_top = 18
        margin_bottom = 22
        rect = self.rect().adjusted(margin_left, margin_top, -8, -margin_bottom)
        cell_w = rect.width() / 24.0
        cell_h = rect.height() / 7.0

        # Day labels.
        painter.setPen(QColor("#8b95a3"))
        painter.setFont(QFont("Segoe UI", 8))
        for r, label in enumerate(self.DAY_LABELS):
            y = rect.top() + r * cell_h + cell_h / 2 - 6
            painter.drawText(0, int(y), margin_left - 6, 14,
                             int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                             label)

        # Hour labels (every 4h).
        for h in range(0, 24, 4):
            x = rect.left() + h * cell_w
            painter.drawText(int(x), int(rect.bottom() + 4), int(cell_w * 4), 14,
                             int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
                             f"{h:02d}")

        # Cells.
        for r in range(7):
            for h in range(24):
                count = self._counts[r][h]
                ratio = (count / self._max) if self._max > 0 else 0.0
                if ratio <= 0:
                    color = QColor("#1c2230")
                else:
                    # Lerp from #1c2230 -> #ff4655.
                    base = QColor("#1c2230")
                    accent = QColor("#ff4655")
                    color = QColor(
                        int(base.red() + (accent.red() - base.red()) * ratio),
                        int(base.green() + (accent.green() - base.green()) * ratio),
                        int(base.blue() + (accent.blue() - base.blue()) * ratio),
                    )
                cell_rect = (
                    rect.left() + h * cell_w + 1,
                    rect.top() + r * cell_h + 1,
                    cell_w - 2,
                    cell_h - 2,
                )
                painter.fillRect(
                    int(cell_rect[0]),
                    int(cell_rect[1]),
                    int(cell_rect[2]),
                    int(cell_rect[3]),
                    color,
                )

    def event(self, event):  # noqa: N802 (Qt API), provide tooltips per cell
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.ToolTip:
            pos = event.pos()
            margin_left = 38
            margin_top = 18
            margin_bottom = 22
            rect_w = self.width() - margin_left - 8
            rect_h = self.height() - margin_top - margin_bottom
            if rect_w > 0 and rect_h > 0:
                cell_w = rect_w / 24.0
                cell_h = rect_h / 7.0
                col = int((pos.x() - margin_left) // cell_w) if cell_w > 0 else -1
                row = int((pos.y() - margin_top) // cell_h) if cell_h > 0 else -1
                if 0 <= col < 24 and 0 <= row < 7:
                    self.setToolTip(
                        f"{self.DAY_LABELS[row]} {col:02d}:00 "
                        f"\u2014 {self._counts[row][col]} match(es)"
                    )
                else:
                    self.setToolTip("")
        return super().event(event)


class _BarBreakdown(QWidget):
    """Horizontal bar list of ``(label, played, win%)`` rows.

    Each row renders the agent/map name on the left, a horizontal track
    showing winrate (red \u2192 yellow \u2192 green gradient based on the actual
    win %) and the absolute counts (W-L \u2022 played) on the right. This is
    much more scannable than a 5-column table when the user only cares
    about \"which agent / map am I best on\".
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._rows: List[Tuple[str, int, int, int]] = []
        self._max_played = 0
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(80)

    def set_rows(self, rows: List[Tuple[str, int, int, int]]) -> None:
        self._rows = list(rows)
        self._max_played = max((r[1] for r in self._rows), default=0)
        # Resize so each row gets ~26px.
        target = max(80, len(self._rows) * 28 + 12)
        self.setMinimumHeight(target)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))

        if not self._rows:
            painter.setPen(QColor("#8b95a3"))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "No matches recorded yet",
            )
            return

        label_w = 130
        right_w = 110
        row_h = 26
        bar_pad_y = 6
        track_left = label_w + 8
        track_right = self.width() - right_w - 8
        track_w = max(40, track_right - track_left)

        font_label = QFont("Segoe UI", 10)
        font_label.setBold(True)
        font_meta = QFont("Segoe UI", 9)

        for idx, (label, played, wins, losses) in enumerate(self._rows):
            y = idx * row_h
            decisive = wins + losses
            wr = (wins / decisive * 100) if decisive else 0.0

            # Label.
            painter.setFont(font_label)
            painter.setPen(QColor("#dee5ee"))
            painter.drawText(
                0,
                y,
                label_w,
                row_h,
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                label,
            )

            # Bar track (background).
            track_rect_y = y + bar_pad_y
            track_rect_h = row_h - 2 * bar_pad_y
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#1c2230"))
            painter.drawRoundedRect(
                track_left,
                track_rect_y,
                track_w,
                track_rect_h,
                track_rect_h / 2,
                track_rect_h / 2,
            )

            # Filled portion. Width scaled by the *played* count relative
            # to the most-played agent/map - so a 100% winrate from a
            # single match doesn't look as dominant as 70% over 30 games.
            if self._max_played > 0:
                width_ratio = played / self._max_played
            else:
                width_ratio = 0
            filled_w = int(track_w * width_ratio)
            if filled_w > 0 and decisive > 0:
                color = self._wr_color(wr)
                painter.setBrush(color)
                painter.drawRoundedRect(
                    track_left,
                    track_rect_y,
                    filled_w,
                    track_rect_h,
                    track_rect_h / 2,
                    track_rect_h / 2,
                )

            # Right-side meta: W-L \u2022 played \u2022 win%.
            painter.setFont(font_meta)
            painter.setPen(QColor("#aab5c5"))
            wr_text = f"{wr:.0f}%" if decisive else "\u2014"
            meta_text = f"{wins}\u2013{losses}  \u2022  {played} matches  \u2022  {wr_text}"
            painter.drawText(
                track_right + 8,
                y,
                right_w - 8,
                row_h,
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                meta_text,
            )

    @staticmethod
    def _wr_color(wr: float) -> QColor:
        if wr >= 60:
            return QColor("#5fcf80")
        if wr >= 50:
            return QColor("#7fc7ff")
        if wr >= 40:
            return QColor("#f0b429")
        return QColor("#ff4655")


class _KpiCard(QFrame):
    """Compact frosted-glass tile used in the Stats hero metric strip."""

    def __init__(
        self,
        label: str,
        value: str = "\u2014",
        sublabel: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("kpiCard")
        self.setProperty("tone", "neutral")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        self._label = QLabel(label.upper())
        self._label.setObjectName("kpiLabel")
        layout.addWidget(self._label)

        self._value = QLabel(value)
        self._value.setObjectName("kpiValue")
        layout.addWidget(self._value)

        self._sub = QLabel(sublabel)
        self._sub.setObjectName("kpiSubLabel")
        layout.addWidget(self._sub)

        if not sublabel:
            self._sub.hide()

    def set_value(self, value: str, tone: str = "neutral", sublabel: str = "") -> None:
        self._value.setText(value)
        if sublabel:
            self._sub.setText(sublabel)
            self._sub.show()
        else:
            self._sub.hide()
        if self.property("tone") != tone:
            self.setProperty("tone", tone)
            self.style().unpolish(self)
            self.style().polish(self)


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
        self._update_streak(matches)
        self._update_kpis(matches)
        self._update_trend(matches)
        self._update_heatmap(matches)
        self._agent_bars.set_rows(self._aggregate(matches, "agent"))
        self._map_bars.set_rows(self._aggregate(matches, "map"))

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

        # Current win/loss streak pill - sits on the right of the toolbar
        # so it's the first thing the user sees when they open the page.
        self._streak_pill = QFrame()
        self._streak_pill.setObjectName("streakPill")
        self._streak_pill.setProperty("outcome", "neutral")
        streak_layout = QHBoxLayout(self._streak_pill)
        streak_layout.setContentsMargins(10, 4, 10, 4)
        streak_layout.setSpacing(8)
        self._streak_label = QLabel("Streak")
        self._streak_label.setObjectName("settingDescription")
        self._streak_label.setProperty("muted", True)
        streak_layout.addWidget(self._streak_label)
        self._streak_value = QLabel("\u2014")
        self._streak_value.setObjectName("streakValue")
        streak_layout.addWidget(self._streak_value)
        toolbar.addWidget(self._streak_pill)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(refresh_btn)
        root.addLayout(toolbar)

        # KPI strip - four pulse metrics the user wants to see at a glance.
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)
        self._kpi_played = _KpiCard("Matches", "0", "this season")
        self._kpi_winrate = _KpiCard("Win rate", "\u2014%", "0\u20130")
        self._kpi_delta = _KpiCard("Net RR", "+0", "all-time")
        self._kpi_streak = _KpiCard("Current streak", "\u2014", "")
        for kpi in (
            self._kpi_played,
            self._kpi_winrate,
            self._kpi_delta,
            self._kpi_streak,
        ):
            kpi.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
            kpi_row.addWidget(kpi, 1)
        root.addLayout(kpi_row)

        # Two-column grid: trend + heatmap on top, breakdowns below.
        upper = QGridLayout()
        upper.setHorizontalSpacing(16)
        upper.setVerticalSpacing(0)

        self._trend = _RRTrendChart()
        upper.addWidget(card(self._trend, title="RR over time"), 0, 0)

        self._heatmap = _PlayHeatmap()
        upper.addWidget(card(self._heatmap, title="When you play"), 0, 1)
        upper.setColumnStretch(0, 3)
        upper.setColumnStretch(1, 2)
        root.addLayout(upper)

        breakdowns = QGridLayout()
        breakdowns.setHorizontalSpacing(16)
        breakdowns.setVerticalSpacing(0)

        self._agent_bars = _BarBreakdown()
        breakdowns.addWidget(card(self._agent_bars, title="By agent"), 0, 0)

        self._map_bars = _BarBreakdown()
        breakdowns.addWidget(card(self._map_bars, title="By map"), 0, 1)

        root.addLayout(breakdowns, 1)

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

    def _update_kpis(self, matches: List[Dict[str, Any]]) -> None:
        """Top-of-page hero metrics: total played, winrate, net RR, streak."""

        total = len(matches)
        wins = sum(
            1 for m in matches if isinstance(m.get("_delta"), int) and m["_delta"] > 0
        )
        losses = sum(
            1 for m in matches if isinstance(m.get("_delta"), int) and m["_delta"] < 0
        )
        decisive = wins + losses
        net = sum(
            int(m["_delta"]) for m in matches if isinstance(m.get("_delta"), int)
        )

        self._kpi_played.set_value(
            str(total),
            tone="neutral",
            sublabel=("recorded locally" if total else "no data yet"),
        )

        if decisive:
            wr = wins / decisive * 100
            tone = "win" if wr >= 55 else "loss" if wr < 45 else "neutral"
            self._kpi_winrate.set_value(
                f"{wr:.0f}%",
                tone=tone,
                sublabel=f"{wins}\u2013{losses} decisive",
            )
        else:
            self._kpi_winrate.set_value("\u2014%", tone="neutral", sublabel="0\u20130")

        if net != 0:
            tone = "win" if net > 0 else "loss"
            sign = "+" if net > 0 else ""
            self._kpi_delta.set_value(
                f"{sign}{net}", tone=tone, sublabel="all-time"
            )
        else:
            self._kpi_delta.set_value("0", tone="neutral", sublabel="all-time")

    def _update_streak(self, matches: List[Dict[str, Any]]) -> None:
        """Walk back from the latest match counting consecutive same-sign deltas."""

        latest_first = list(reversed(matches))
        streak = 0
        outcome = "neutral"
        for m in latest_first:
            delta = m.get("_delta")
            if not isinstance(delta, int) or delta == 0:
                continue
            if streak == 0:
                outcome = "win" if delta > 0 else "loss"
                streak = 1
                continue
            same_sign = (outcome == "win" and delta > 0) or (
                outcome == "loss" and delta < 0
            )
            if same_sign:
                streak += 1
            else:
                break

        self._streak_pill.setProperty("outcome", outcome)
        # Re-polish so the property selector kicks in.
        self._streak_pill.style().unpolish(self._streak_pill)
        self._streak_pill.style().polish(self._streak_pill)

        if streak == 0:
            self._streak_label.setText("Streak")
            self._streak_value.setText("\u2014")
            self._streak_value.setStyleSheet("color: #aab5c5;")
            if hasattr(self, "_kpi_streak"):
                self._kpi_streak.set_value(
                    "\u2014", tone="neutral", sublabel="even"
                )
        else:
            prefix = "Win streak" if outcome == "win" else "Loss streak"
            color = "#5fcf80" if outcome == "win" else "#ff4655"
            arrow = "\u2191" if outcome == "win" else "\u2193"
            self._streak_label.setText(prefix)
            self._streak_value.setText(f"{arrow}{streak}")
            self._streak_value.setStyleSheet(f"color: {color};")
            if hasattr(self, "_kpi_streak"):
                self._kpi_streak.set_value(
                    f"{arrow}{streak}",
                    tone="win" if outcome == "win" else "loss",
                    sublabel="wins in a row" if outcome == "win" else "losses in a row",
                )

    def _update_heatmap(self, matches: List[Dict[str, Any]]) -> None:
        counts = [[0] * 24 for _ in range(7)]
        for m in matches:
            try:
                ts = float(m.get("epoch") or 0)
            except (TypeError, ValueError):
                continue
            if ts <= 0:
                continue
            dt = datetime.fromtimestamp(ts)
            counts[dt.weekday()][dt.hour] += 1
        self._heatmap.set_data(counts)

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
            raw = m.get(key)
            # Maps were historically stored as dicts ({'name', 'splash'})
            # so unwrap to a clean display name before bucketing.
            if isinstance(raw, dict):
                raw = raw.get("name") or "\u2014"
            elif isinstance(raw, str) and raw.startswith("{") and "'name'" in raw:
                try:
                    import ast
                    parsed = ast.literal_eval(raw)
                    if isinstance(parsed, dict) and parsed.get("name"):
                        raw = parsed["name"]
                except (ValueError, SyntaxError):
                    pass
            label = _strip_ansi(raw) or "\u2014"
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
