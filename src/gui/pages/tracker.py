"""Live tracker page \u2014 receives heartbeats from the websocket server."""

from __future__ import annotations

import re
import time
import urllib.parse
import webbrowser
from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional

from PySide6.QtCore import QModelIndex, QPoint, QSize, Qt
from PySide6.QtGui import (
    QBrush,
    QClipboard,
    QColor,
    QGuiApplication,
    QIcon,
    QPixmap,
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
    QMenu,
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
from src.gui.workers.image_cache import ImageCache

_ANSI_RE = re.compile(r"(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]")


def _strip_ansi(value: str) -> str:
    return _ANSI_RE.sub("", value) if isinstance(value, str) else value

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
    ("skin", "Skin"),
    ("winPercentage", "Win %"),
    ("headshotPercentage", "HS %"),
    ("kd", "K/D"),
    ("level", "Lvl"),
]

NAME_COLUMN = next(i for i, (k, _) in enumerate(PLAYER_COLUMNS) if k == "name")
SKIN_COLUMN = next(i for i, (k, _) in enumerate(PLAYER_COLUMNS) if k == "skin")

# Custom Qt item-data roles used to ferry domain values through the model.
PUUID_ROLE = Qt.ItemDataRole.UserRole + 1
NAME_ROLE = Qt.ItemDataRole.UserRole + 2
SKIN_ICON_URL_ROLE = Qt.ItemDataRole.UserRole + 3
PLAYER_CARD_URL_ROLE = Qt.ItemDataRole.UserRole + 4

# Team backgrounds (subtle tint applied to the row).
TEAM_ROW_COLORS: Dict[str, QColor] = {
    "Blue": QColor(58, 138, 232, 38),
    "Red": QColor(255, 70, 85, 44),
    "Yellow": QColor(240, 185, 56, 50),
}

TRACKER_GG_TEMPLATE = (
    "https://tracker.gg/valorant/profile/riot/{name}/overview"
)
BLITZ_GG_TEMPLATE = (
    "https://blitz.gg/valorant/profile/{name}/overview"
)


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
    AVATAR_SIZE = QSize(28, 28)
    SKIN_TOOLTIP_SIZE = QSize(420, 160)

    def __init__(
        self,
        on_start,
        on_stop,
        image_cache: Optional[ImageCache] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._on_start = on_start
        self._on_stop = on_stop
        self._chat_history: Deque[Dict[str, Any]] = deque(maxlen=self.CHAT_LIMIT)
        self._connected = False
        self._tracker_running = False
        self._image_cache = image_cache or ImageCache(self)
        self._image_cache.image_ready.connect(self._on_image_ready)

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
        # Avatar / skin icon row needs a bit more breathing room.
        self._player_table.verticalHeader().setDefaultSectionSize(34)
        self._player_table.setIconSize(self.AVATAR_SIZE)
        self._player_table.setMouseTracking(True)
        self._player_table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self._player_table.customContextMenuRequested.connect(
            self._on_table_context_menu
        )
        self._player_table.doubleClicked.connect(self._on_table_double_click)
        header_view = self._player_table.horizontalHeader()
        header_view.setStretchLastSection(False)
        header_view.setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        # Stretch the name and skin columns so long values get more room.
        for index, (key, _) in enumerate(PLAYER_COLUMNS):
            if key in ("name", "skin"):
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

        def _rank_idx(p: Dict[str, Any]) -> int:
            r = p.get("rank")
            return int(r) if isinstance(r, int) else -1

        # Higher ranks first, then group by party.
        rows.sort(key=lambda p: int(p.get("partyNumber") or 0))
        rows.sort(key=_rank_idx, reverse=True)

        self._player_model.removeRows(0, self._player_model.rowCount())
        if not rows:
            self._players_empty.show()
            self._players_badge.set_value("0")
            return

        self._players_empty.hide()
        self._players_badge.set_value(str(len(rows)))

        weapon_choice = str(cfg.get("weapon") or "Vandal")
        for player in rows:
            row_items: List[QStandardItem] = []
            skin_url = self._skin_icon_url(player, weapon_choice)
            for key, _label in PLAYER_COLUMNS:
                value = self._cell_for(key, player, table_flags, weapon_choice)
                item = QStandardItem(value)
                item.setEditable(False)
                if key == "rank":
                    color = _rank_color(value)
                    if color is not None:
                        item.setForeground(color)
                if key == "peakRank":
                    color = _rank_color(value)
                    if color is not None:
                        item.setForeground(color)
                if key in ("rr", "level", "kd", "headshotPercentage"):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if key == "name":
                    item.setData(player.get("puuid"), PUUID_ROLE)
                    real_name = _strip_ansi(str(player.get("name") or ""))
                    if self._is_hidden_name(real_name):
                        # Italicise hidden names so it's obvious that the value
                        # in this cell is the agent and not the actual riot id.
                        font = item.font()
                        font.setItalic(True)
                        item.setFont(font)
                        item.setForeground(QColor("#8b95a3"))
                        item.setData("", NAME_ROLE)
                    else:
                        item.setData(real_name, NAME_ROLE)
                    card_url = str(player.get("playerCard") or "")
                    if card_url:
                        item.setData(card_url, PLAYER_CARD_URL_ROLE)
                        pix = self._image_cache.request(card_url)
                        if pix is not None:
                            item.setIcon(QIcon(self._scale_avatar(pix)))
                if key == "skin":
                    if skin_url:
                        item.setData(skin_url, SKIN_ICON_URL_ROLE)
                        item.setToolTip(self._skin_tooltip(value, skin_url))
                        # Trigger lazy download so the tooltip is ready next time.
                        self._image_cache.request(skin_url)
                row_items.append(item)
            self._apply_team_color(row_items, player.get("team"))
            self._player_model.appendRow(row_items)

    def _cell_for(
        self,
        key: str,
        player: Dict[str, Any],
        table_flags: Dict[str, Any],
        weapon_choice: str,
    ) -> str:
        if key == "party":
            number = player.get("partyNumber")
            return f"P{number}" if number else ""
        if key == "agent":
            return _strip_ansi(str(player.get("agent") or "?"))
        if key == "name":
            return self._format_name(player)
        if key == "skin":
            return self._skin_display_name(player, weapon_choice)
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

    # ------------------------------------------------------- name fallback
    @staticmethod
    def _is_hidden_name(name: str) -> bool:
        """Detect when Riot returns an empty riot-id for an incognito player.

        ``names.py`` formats every player as ``f"{GameName}#{TagLine}"``. When a
        player has streamer/incognito mode on, the name service returns empty
        strings on both sides, which means the heartbeat carries the literal
        string ``"#"`` (or whitespace around it). The console mirrors VALORANT
        and shows the agent name instead — the GUI should do the same.
        """

        if not isinstance(name, str):
            return True
        cleaned = name.strip()
        return cleaned in ("", "#")

    @classmethod
    def _format_name(cls, player: Dict[str, Any]) -> str:
        name = _strip_ansi(str(player.get("name") or "")).strip()
        if cls._is_hidden_name(name):
            agent = _strip_ansi(str(player.get("agent") or "")).strip()
            return agent or "Hidden"
        return name

    # --------------------------------------------------------- skins / images
    @staticmethod
    def _find_weapon_entry(
        player: Dict[str, Any], weapon_choice: str
    ) -> Optional[Dict[str, Any]]:
        weapons = player.get("weapons") or {}
        if not isinstance(weapons, dict):
            return None
        target = weapon_choice.strip().lower()
        for entry in weapons.values():
            if not isinstance(entry, dict):
                continue
            if str(entry.get("weapon") or "").strip().lower() == target:
                return entry
        return None

    @classmethod
    def _skin_display_name(
        cls, player: Dict[str, Any], weapon_choice: str
    ) -> str:
        entry = cls._find_weapon_entry(player, weapon_choice)
        if entry is None:
            return "\u2014"
        name = entry.get("skinDisplayName") or entry.get("skin_displayName") or ""
        name = _strip_ansi(str(name)).strip()
        if not name:
            return "\u2014"
        # The API ships skins as "Reaver Vandal"; trim the trailing weapon name.
        suffix = " " + weapon_choice
        if name.lower().endswith(suffix.lower()):
            name = name[: -len(suffix)].rstrip()
        return name or "\u2014"

    @classmethod
    def _skin_icon_url(
        cls, player: Dict[str, Any], weapon_choice: str
    ) -> str:
        entry = cls._find_weapon_entry(player, weapon_choice)
        if entry is None:
            return ""
        url = entry.get("skinDisplayIcon") or entry.get("skin_displayIcon") or ""
        return str(url) if url else ""

    def _scale_avatar(self, pixmap: QPixmap) -> QPixmap:
        return pixmap.scaled(
            self.AVATAR_SIZE,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )

    def _skin_tooltip(self, name: str, url: str) -> str:
        # Qt accepts <img> in rich text tooltips when given a local file path
        # (or a remote URL it can resolve synchronously). The image cache
        # downloads to disk, so once cached we can point the tooltip at the
        # file path. Until then, just render the name.
        cached_path = self._image_cache._disk_path(url)  # noqa: SLF001 - intentional
        import os as _os

        if _os.path.exists(cached_path):
            return (
                f'<div style="padding:4px"><b>{name}</b><br>'
                f'<img src="{cached_path}" width="{self.SKIN_TOOLTIP_SIZE.width()}"></div>'
            )
        return f"<b>{name}</b><br><i>loading skin preview\u2026</i>"

    def _apply_team_color(
        self, items: List[QStandardItem], team: Optional[str]
    ) -> None:
        if not team:
            return
        color = TEAM_ROW_COLORS.get(str(team).strip().capitalize())
        if color is None:
            return
        brush = QBrush(color)
        for item in items:
            item.setBackground(brush)

    # ---------------------------------------------------------- interactions
    def _on_image_ready(self, url: str, pixmap: QPixmap) -> None:
        """Refresh table cells whose deferred image just finished loading."""

        for row in range(self._player_model.rowCount()):
            name_item = self._player_model.item(row, NAME_COLUMN)
            if name_item is not None and name_item.data(PLAYER_CARD_URL_ROLE) == url:
                name_item.setIcon(QIcon(self._scale_avatar(pixmap)))
            skin_item = self._player_model.item(row, SKIN_COLUMN)
            if skin_item is not None and skin_item.data(SKIN_ICON_URL_ROLE) == url:
                skin_item.setToolTip(
                    self._skin_tooltip(skin_item.text(), url)
                )

    def _row_lookup(self, row: int) -> tuple[str, str]:
        name_item = self._player_model.item(row, NAME_COLUMN)
        if name_item is None:
            return "", ""
        name = str(name_item.data(NAME_ROLE) or name_item.text() or "")
        puuid = str(name_item.data(PUUID_ROLE) or "")
        return name, puuid

    def _on_table_double_click(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        name, _ = self._row_lookup(index.row())
        if not name or "#" not in name:
            return
        webbrowser.open(self._tracker_gg_url(name))

    def _on_table_context_menu(self, point: QPoint) -> None:
        index = self._player_table.indexAt(point)
        if not index.isValid():
            return
        name, puuid = self._row_lookup(index.row())
        if not name and not puuid:
            return

        menu = QMenu(self._player_table)
        clipboard = QGuiApplication.clipboard()

        copy_name = menu.addAction(f"Copy name: {name}" if name else "Copy name")
        copy_name.setEnabled(bool(name))
        copy_name.triggered.connect(
            lambda: clipboard.setText(name, QClipboard.Mode.Clipboard)
        )

        copy_puuid = menu.addAction("Copy puuid")
        copy_puuid.setEnabled(bool(puuid))
        copy_puuid.triggered.connect(
            lambda: clipboard.setText(puuid, QClipboard.Mode.Clipboard)
        )

        menu.addSeparator()

        open_tracker = menu.addAction("Open in tracker.gg")
        open_tracker.setEnabled(bool(name) and "#" in name)
        open_tracker.triggered.connect(
            lambda: webbrowser.open(self._tracker_gg_url(name))
        )

        open_blitz = menu.addAction("Open in blitz.gg")
        open_blitz.setEnabled(bool(name) and "#" in name)
        open_blitz.triggered.connect(
            lambda: webbrowser.open(self._blitz_gg_url(name))
        )

        menu.exec(self._player_table.viewport().mapToGlobal(point))

    @staticmethod
    def _tracker_gg_url(name: str) -> str:
        return TRACKER_GG_TEMPLATE.format(
            name=urllib.parse.quote(name, safe="")
        )

    @staticmethod
    def _blitz_gg_url(name: str) -> str:
        # blitz.gg accepts riot-id with a literal '#'.
        return BLITZ_GG_TEMPLATE.format(
            name=urllib.parse.quote(name, safe="#")
        )

    @staticmethod
    def _format_rank(rank: Any) -> str:
        """Resolve a numeric rank index to its human-readable name.

        ``main.py`` puts ``playerRank["rank"]`` (an int) into the heartbeat
        payload; the rich console looks up :data:`NUMBERTORANKS` (a list of
        ANSI-coloured strings) by index. We do the same here and strip the
        escape codes for plain text rendering.
        """

        if rank in (None, ""):
            return "\u2014"
        if isinstance(rank, bool):  # bool is a subclass of int; reject explicitly
            return str(rank)
        if isinstance(rank, int):
            if 0 <= rank < len(NUMBERTORANKS):
                return _strip_ansi(NUMBERTORANKS[rank])
            return str(rank)
        if isinstance(rank, str):
            return _strip_ansi(rank)
        return str(rank)

    # --------------------------------------------------------- diagnostics
    def banner_text(self) -> str:
        return f"vRY GUI v{version}"
