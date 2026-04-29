"""Live tracker page \u2014 receives heartbeats from the websocket server."""

from __future__ import annotations

import time
from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.constants import NUMBERTORANKS, version
from src.gui.config_io import load_config
from src.gui.pages._common import card, page_header

# Visual constants
GAME_STATES = ("MENUS", "PREGAME", "INGAME", "DISCONNECTED")
RANK_COLORS = {
    "UNRANKED": "#cccccc",
    "IRON": "#7d7575",
    "BRONZE": "#c08157",
    "SILVER": "#bcbcbc",
    "GOLD": "#f0b938",
    "PLATINUM": "#3aa6c2",
    "DIAMOND": "#c879ff",
    "ASCENDANT": "#3ad07a",
    "IMMORTAL": "#a32b3e",
    "RADIANT": "#fff291",
}

PLAYER_COLUMNS: List[tuple[str, str]] = [
    ("party", "Party"),
    ("agent", "Agent"),
    ("name", "Name"),
    ("rank", "Rank"),
    ("rr", "RR"),
    ("peakRank", "Peak"),
    ("winPercentage", "Win %"),
    ("headshotPercentage", "HS %"),
    ("kd", "K/D"),
    ("level", "Lvl"),
]


def _rank_color(rank_name: str) -> Optional[QColor]:
    if not isinstance(rank_name, str):
        return None
    for key, color in RANK_COLORS.items():
        if rank_name.upper().startswith(key):
            return QColor(color)
    return None


class StatBadge(QFrame):
    """Small panel that shows a label + bold value (used in the status row)."""

    def __init__(self, label: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("statBadge")
        self.setFrameShape(QFrame.Shape.NoFrame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)

        self._label = QLabel(label.upper())
        self._label.setObjectName("statLabel")
        layout.addWidget(self._label)

        self._value = QLabel("\u2014")
        self._value.setObjectName("statValue")
        layout.addWidget(self._value)

    def set_value(self, value: str) -> None:
        self._value.setText(value if value else "\u2014")


class TrackerPage(QWidget):
    """Live page that mirrors the rich console table inside the GUI."""

    CHAT_LIMIT = 50

    def __init__(
        self,
        on_start,
        on_stop,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._on_start = on_start
        self._on_stop = on_stop
        self._chat_history: Deque[Dict[str, Any]] = deque(maxlen=self.CHAT_LIMIT)
        self._connected = False
        self._tracker_running = False

        self._build_layout()
        self._update_buttons()
        self._update_state_pill("MENUS")
        self._update_connection_pill(False)

    # ----------------------------------------------------------- layout
    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        layout.addLayout(self._build_header())
        layout.addLayout(self._build_status_row())
        layout.addWidget(self._build_body(), 1)

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(
            page_header(
                "Live tracker",
                "All the data the console used to print \u2014 now in a Qt window.",
            ),
            1,
        )

        self._connection_pill = QLabel("OFFLINE")
        self._connection_pill.setObjectName("statePill")
        self._connection_pill.setProperty("gameState", "DISCONNECTED")
        row.addWidget(
            self._connection_pill, 0, Qt.AlignmentFlag.AlignTop
        )

        self._start_btn = QPushButton("Start tracker")
        self._start_btn.setObjectName("primary")
        self._start_btn.clicked.connect(self._on_start)
        row.addWidget(self._start_btn, 0, Qt.AlignmentFlag.AlignTop)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName("danger")
        self._stop_btn.clicked.connect(self._on_stop)
        row.addWidget(self._stop_btn, 0, Qt.AlignmentFlag.AlignTop)

        return row

    def _build_status_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        self._state_pill = QLabel("MENUS")
        self._state_pill.setObjectName("statePill")
        self._state_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._state_pill.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed
        )
        row.addWidget(self._state_pill, 0, Qt.AlignmentFlag.AlignVCenter)

        self._mode_badge = StatBadge("Mode")
        self._map_badge = StatBadge("Map")
        self._players_badge = StatBadge("Players")
        self._heartbeat_badge = StatBadge("Last update")

        for badge in (
            self._mode_badge,
            self._map_badge,
            self._players_badge,
            self._heartbeat_badge,
        ):
            row.addWidget(badge, 1)

        return row

    def _build_body(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)

        splitter.addWidget(self._build_player_table())
        splitter.addWidget(self._build_chat_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([700, 280])
        return splitter

    def _build_player_table(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QLabel("Players")
        header.setObjectName("statLabel")
        layout.addWidget(header)

        self._player_model = QStandardItemModel(0, len(PLAYER_COLUMNS), self)
        self._player_model.setHorizontalHeaderLabels(
            [label for _, label in PLAYER_COLUMNS]
        )

        self._player_table = QTableView()
        self._player_table.setModel(self._player_model)
        self._player_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._player_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._player_table.setAlternatingRowColors(True)
        self._player_table.setSortingEnabled(True)
        self._player_table.verticalHeader().setVisible(False)
        header_view = self._player_table.horizontalHeader()
        header_view.setStretchLastSection(False)
        header_view.setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        # Stretch the name column so long names get more breathing room.
        for index, (key, _) in enumerate(PLAYER_COLUMNS):
            if key == "name":
                header_view.setSectionResizeMode(
                    index, QHeaderView.ResizeMode.Stretch
                )
        layout.addWidget(self._player_table, 1)

        self._players_empty = QLabel(
            "Waiting for game data\u2026 start the tracker and join a match."
        )
        self._players_empty.setProperty("muted", True)
        self._players_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._players_empty)
        return container

    def _build_chat_panel(self) -> QWidget:
        from PySide6.QtWidgets import QListWidget  # local import keeps top tidy

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QLabel("Game chat")
        header.setObjectName("statLabel")
        layout.addWidget(header)

        self._chat_list = QListWidget()
        self._chat_list.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self._chat_list.setWordWrap(True)
        layout.addWidget(self._chat_list, 1)

        self._chat_empty = QLabel("No messages yet.")
        self._chat_empty.setProperty("muted", True)
        self._chat_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._chat_empty)
        return card(container, title=None)

    # ------------------------------------------------------------ public
    def set_tracker_running(self, running: bool) -> None:
        self._tracker_running = running
        self._update_buttons()
        if not running:
            self._update_connection_pill(False)

    def set_connected(self, connected: bool) -> None:
        self._connected = connected
        self._update_connection_pill(connected)

    def apply_heartbeat(self, payload: Dict[str, Any]) -> None:
        state = str(payload.get("state") or "MENUS").upper()
        self._update_state_pill(state)

        mode = payload.get("mode") or "\u2014"
        self._mode_badge.set_value(str(mode))

        map_value = payload.get("map")
        if isinstance(map_value, (list, tuple)) and map_value:
            map_value = map_value[0]
        if isinstance(map_value, str):
            map_name = map_value.rsplit("/", 1)[-1].split(".", 1)[0] or "\u2014"
        else:
            map_name = "\u2014"
        self._map_badge.set_value(map_name)

        timestamp = payload.get("time")
        if isinstance(timestamp, (int, float)) and timestamp > 0:
            stamp = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")
        else:
            stamp = datetime.fromtimestamp(time.time()).strftime("%H:%M:%S")
        self._heartbeat_badge.set_value(stamp)

        players = payload.get("players") or {}
        if isinstance(players, dict):
            self._update_players(players)

    def append_chat(self, payload: Dict[str, Any]) -> None:
        from PySide6.QtWidgets import QListWidgetItem

        self._chat_history.append(payload)
        if not self._chat_history:
            return

        self._chat_empty.hide()
        timestamp = payload.get("time")
        if isinstance(timestamp, (int, float)) and timestamp > 0:
            stamp = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")
        else:
            stamp = datetime.now().strftime("%H:%M:%S")
        group = (payload.get("group") or "").strip() or "All"
        speaker = payload.get("player") or payload.get("agent") or "?"
        text = payload.get("text") or ""
        line = f"[{stamp}] [{group}] {speaker}: {text}"

        item = QListWidgetItem(line)
        if group.lower().startswith("team"):
            item.setForeground(QColor("#74a2d6"))
        else:
            item.setForeground(QColor("#ece8e1"))
        self._chat_list.addItem(item)
        # Keep the visual list bounded as well.
        while self._chat_list.count() > self.CHAT_LIMIT:
            self._chat_list.takeItem(0)
        self._chat_list.scrollToBottom()

    # ---------------------------------------------------------- internals
    def _update_state_pill(self, state: str) -> None:
        normalised = state if state in GAME_STATES else "MENUS"
        self._state_pill.setText(normalised)
        self._state_pill.setProperty("gameState", normalised)
        self._state_pill.style().unpolish(self._state_pill)
        self._state_pill.style().polish(self._state_pill)

    def _update_connection_pill(self, connected: bool) -> None:
        text = "LIVE" if connected else "OFFLINE"
        state = "INGAME" if connected else "DISCONNECTED"
        self._connection_pill.setText(text)
        self._connection_pill.setProperty("gameState", state)
        self._connection_pill.style().unpolish(self._connection_pill)
        self._connection_pill.style().polish(self._connection_pill)

    def _update_buttons(self) -> None:
        self._start_btn.setEnabled(not self._tracker_running)
        self._stop_btn.setEnabled(self._tracker_running)

    def _update_players(self, players: Dict[str, Any]) -> None:
        cfg = load_config()
        table_flags = cfg.get("table") or {}

        rows = list(players.values())
        rows.sort(key=lambda p: int(p.get("partyNumber") or 0))
        rows.sort(key=lambda p: str(p.get("rank") or ""), reverse=True)

        self._player_model.removeRows(0, self._player_model.rowCount())
        if not rows:
            self._players_empty.show()
            self._players_badge.set_value("0")
            return

        self._players_empty.hide()
        self._players_badge.set_value(str(len(rows)))

        for player in rows:
            row_items: List[QStandardItem] = []
            for key, _label in PLAYER_COLUMNS:
                value = self._cell_for(key, player, table_flags)
                item = QStandardItem(value)
                item.setEditable(False)
                if key == "rank":
                    color = _rank_color(str(player.get("rank") or ""))
                    if color is not None:
                        item.setForeground(color)
                if key in ("rr", "level", "kd", "headshotPercentage"):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                row_items.append(item)
            self._player_model.appendRow(row_items)

    def _cell_for(
        self,
        key: str,
        player: Dict[str, Any],
        table_flags: Dict[str, Any],
    ) -> str:
        if key == "party":
            number = player.get("partyNumber")
            return f"P{number}" if number else ""
        if key == "agent":
            return str(player.get("agent") or "?")
        if key == "name":
            return str(player.get("name") or "?")
        if key == "rank":
            rank = player.get("rank")
            return self._format_rank(rank)
        if key == "rr":
            if not table_flags.get("rr", True):
                return ""
            rr = player.get("rr")
            return str(rr) if rr not in (None, "") else "\u2014"
        if key == "peakRank":
            if not table_flags.get("peakrank", True):
                return ""
            return self._format_rank(player.get("peakRank"))
        if key == "winPercentage":
            if not table_flags.get("winrate", True):
                return ""
            return str(player.get("winPercentage") or "\u2014")
        if key == "headshotPercentage":
            if not table_flags.get("headshot_percent", True):
                return ""
            value = player.get("headshotPercentage")
            return str(value) if value not in (None, "") else "\u2014"
        if key == "kd":
            if not table_flags.get("kd", False):
                return ""
            value = player.get("kd")
            return str(value) if value not in (None, "") else "\u2014"
        if key == "level":
            if not table_flags.get("level", True):
                return ""
            value = player.get("level")
            return str(value) if value not in (None, "") else "\u2014"
        return ""

    @staticmethod
    def _format_rank(rank: Any) -> str:
        if rank in (None, ""):
            return "\u2014"
        if isinstance(rank, int):
            return NUMBERTORANKS.get(rank, str(rank))
        return str(rank)

    # --------------------------------------------------------- diagnostics
    def banner_text(self) -> str:
        return f"vRY GUI v{version}"
