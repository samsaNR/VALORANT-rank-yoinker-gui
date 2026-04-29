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
from src.gui.icons import svg_icon
from src.gui.pages._common import card, page_header
from src.gui.stats_repo import StatsRepository
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
    ("rrDelta", "±RR"),
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
    # Glow ranks: Immortal 1+ and Radiant. NUMBERTORANKS index >= 24.
    GLOW_RANK_THRESHOLD = 24

    def __init__(
        self,
        on_start,
        on_stop,
        image_cache: Optional[ImageCache] = None,
        stats_repo: Optional[StatsRepository] = None,
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
        self._stats_repo = stats_repo or StatsRepository()
        self._own_puuid: str = ""
        # Track row indices of synthetic 'BLUE TEAM' / 'RED TEAM' banner rows
        # so we can apply column spans after the model is rebuilt.
        self._banner_rows: List[int] = []

        self._build_layout()
        self._update_buttons()
        self._update_state_pill("MENUS")
        self._update_connection_pill(False)

    # ----------------------------------------------------------- layout
    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        layout.addWidget(self._build_status_card())
        layout.addWidget(self._build_body(), 1)

    def _build_status_card(self) -> QFrame:
        """Single hero card combining state pill, key stats and Start/Stop CTA.

        Replaces the old two-row header (page title + separate stats row) with
        a denser card so the player table gets more vertical space.
        """

        wrapper = QFrame()
        wrapper.setObjectName("statusCard")
        outer = QVBoxLayout(wrapper)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(14)

        top = QHBoxLayout()
        top.setSpacing(14)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_label = QLabel("Live tracker")
        title_label.setObjectName("pageTitle")
        title_box.addWidget(title_label)
        subtitle_label = QLabel(
            "Real-time match data \u2014 ranks, skins, chat and more."
        )
        subtitle_label.setObjectName("pageSubtitle")
        title_box.addWidget(subtitle_label)
        top.addLayout(title_box, 1)

        self._state_pill = QLabel("MENUS")
        self._state_pill.setObjectName("statePill")
        self._state_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._state_pill.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed
        )
        top.addWidget(self._state_pill, 0, Qt.AlignmentFlag.AlignVCenter)

        self._connection_pill = QLabel("OFFLINE")
        self._connection_pill.setObjectName("connectionPill")
        self._connection_pill.setProperty("connected", "false")
        top.addWidget(
            self._connection_pill, 0, Qt.AlignmentFlag.AlignVCenter
        )

        self._start_btn = QPushButton(" Start tracker")
        self._start_btn.setObjectName("primary")
        self._start_btn.setIcon(svg_icon("play", color="#ffffff"))
        self._start_btn.setIconSize(QSize(16, 16))
        self._start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_btn.clicked.connect(self._on_start)
        top.addWidget(self._start_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self._stop_btn = QPushButton(" Stop")
        self._stop_btn.setObjectName("danger")
        self._stop_btn.setIcon(svg_icon("stop", color="#ff4655"))
        self._stop_btn.setIconSize(QSize(14, 14))
        self._stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop_btn.clicked.connect(self._on_stop)
        top.addWidget(self._stop_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        outer.addLayout(top)

        bottom = QHBoxLayout()
        bottom.setSpacing(10)
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
            bottom.addWidget(badge, 1)
        outer.addLayout(bottom)

        return wrapper

    def _build_body(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)

        splitter.addWidget(self._build_player_table())
        splitter.addWidget(self._build_chat_panel())
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([900, 260])
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
        self._player_table.setAlternatingRowColors(False)
        # Sorting is disabled because we group rows by team and emit
        # synthetic 'BLUE TEAM' / 'RED TEAM' header rows; user sorting would
        # mix the headers in with normal rows.
        self._player_table.setSortingEnabled(False)
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
        # Stretch the name column so it absorbs leftover width; explicitly
        # size the rank/peak columns wide enough to fit the longest tier
        # label ("Ascendant 2") because ResizeToContents underestimates with
        # our stylesheet padding and chops to "Asc...".
        for index, (key, _) in enumerate(PLAYER_COLUMNS):
            if key == "name":
                header_view.setSectionResizeMode(
                    index, QHeaderView.ResizeMode.Stretch
                )
            elif key in ("rank", "peakRank"):
                header_view.setSectionResizeMode(
                    index, QHeaderView.ResizeMode.Interactive
                )
                self._player_table.setColumnWidth(index, 120)
            elif key == "skin":
                header_view.setSectionResizeMode(
                    index, QHeaderView.ResizeMode.Interactive
                )
                self._player_table.setColumnWidth(index, 110)
        header_view.setMinimumSectionSize(40)
        layout.addWidget(self._player_table, 1)

        self._players_empty = self._build_empty_state(
            "Waiting for game data",
            "Start the tracker and join a match \u2014 player rows will appear here.",
        )
        layout.addWidget(self._players_empty)
        return container

    @staticmethod
    def _build_empty_state(title: str, subtitle: str) -> QWidget:
        wrapper = QFrame()
        wrapper.setObjectName("card")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(20, 28, 20, 28)
        layout.setSpacing(8)

        glyph = QLabel("\u25c8")  # diamond glyph as a visual anchor
        font = glyph.font()
        font.setPointSize(28)
        font.setBold(True)
        glyph.setFont(font)
        glyph.setStyleSheet("color: #ff4655;")
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(glyph)

        title_label = QLabel(title)
        title_label.setObjectName("emptyTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("emptySubtitle")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setWordWrap(True)
        layout.addWidget(subtitle_label)
        return wrapper

    def _build_chat_panel(self) -> QWidget:
        from PySide6.QtWidgets import QScrollArea

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QLabel("Game chat")
        header.setObjectName("statLabel")
        layout.addWidget(header)

        # Custom scrollable column of chat bubbles, instead of a plain
        # QListWidget with one-line items, so multiline messages, channel
        # pills and timestamps all read more like a modern chat UI.
        self._chat_scroll = QScrollArea()
        self._chat_scroll.setWidgetResizable(True)
        self._chat_scroll.setFrameShape(QFrame.Shape.NoFrame)

        chat_body = QWidget()
        chat_body.setObjectName("chatBody")
        self._chat_layout = QVBoxLayout(chat_body)
        self._chat_layout.setContentsMargins(8, 8, 8, 8)
        self._chat_layout.setSpacing(6)
        self._chat_layout.addStretch(1)
        self._chat_scroll.setWidget(chat_body)

        layout.addWidget(self._chat_scroll, 1)

        self._chat_empty = self._build_empty_state(
            "Quiet lobby",
            "In-match chat will appear here once the tracker connects.",
        )
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
        # Refresh stats.json once per heartbeat: the running tracker writes a
        # new row to it whenever a match finishes.
        self._stats_repo.reload()
        own = str(payload.get("puuid") or "").strip()
        if own:
            self._own_puuid = own
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
        self._chat_history.append(payload)
        if not self._chat_history:
            return

        self._chat_empty.hide()
        timestamp = payload.get("time")
        if isinstance(timestamp, (int, float)) and timestamp > 0:
            stamp = datetime.fromtimestamp(timestamp).strftime("%H:%M")
        else:
            stamp = datetime.now().strftime("%H:%M")
        group_raw = (payload.get("group") or "").strip()
        group = group_raw or "All"
        speaker = payload.get("player") or payload.get("agent") or "?"
        text = payload.get("text") or ""

        bubble = self._build_chat_bubble(stamp, group, speaker, text)
        # Insert before the trailing stretch so messages keep stacking.
        self._chat_layout.insertWidget(
            self._chat_layout.count() - 1, bubble
        )

        # Bound the visible list (we still keep the deque history above).
        # Walk over the layout (which has one trailing stretch) and remove
        # the oldest bubble while we're over the limit.
        while self._chat_layout.count() - 1 > self.CHAT_LIMIT:
            old_item = self._chat_layout.takeAt(0)
            old_widget = old_item.widget() if old_item is not None else None
            if old_widget is not None:
                old_widget.deleteLater()

        bar = self._chat_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _build_chat_bubble(
        self, stamp: str, group: str, speaker: str, text: str
    ) -> QWidget:
        """Render one chat message as a coloured pill bubble."""

        bubble = QFrame()
        bubble.setObjectName("chatBubble")
        body = QVBoxLayout(bubble)
        body.setContentsMargins(10, 6, 10, 6)
        body.setSpacing(2)

        meta = QHBoxLayout()
        meta.setSpacing(6)
        channel_pill = QLabel(group.upper())
        channel_pill.setObjectName("chatChannel")
        # Map the freeform group string to a known channel for styling.
        normalised = group.lower()
        if normalised.startswith("team"):
            channel = "team"
        elif normalised.startswith("party") or normalised.startswith("lobby"):
            channel = "party"
        else:
            channel = "all"
        channel_pill.setProperty("channel", channel)
        meta.addWidget(channel_pill)

        author_label = QLabel(_strip_ansi(str(speaker)))
        author_label.setObjectName("chatAuthor")
        meta.addWidget(author_label)

        meta.addStretch(1)

        timestamp_label = QLabel(stamp)
        timestamp_label.setObjectName("chatTimestamp")
        meta.addWidget(timestamp_label)

        body.addLayout(meta)

        text_label = QLabel(_strip_ansi(str(text)))
        text_label.setObjectName("chatBody")
        text_label.setWordWrap(True)
        body.addWidget(text_label)
        return bubble

    # ---------------------------------------------------------- internals
    def _update_state_pill(self, state: str) -> None:
        normalised = state if state in GAME_STATES else "MENUS"
        self._state_pill.setText(normalised)
        self._state_pill.setProperty("gameState", normalised)
        self._state_pill.style().unpolish(self._state_pill)
        self._state_pill.style().polish(self._state_pill)

    def _update_connection_pill(self, connected: bool) -> None:
        self._connection_pill.setText("LIVE" if connected else "OFFLINE")
        self._connection_pill.setProperty(
            "connected", "true" if connected else "false"
        )
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

        # Group by team (Blue, Red, then anything else such as DM/agent
        # select), and within each team sort by rank descending.
        from collections import OrderedDict

        groups: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()
        for label in ("Blue", "Red"):
            groups[label] = []
        for player in rows:
            team_label = (
                str(player.get("team") or "Other").strip().capitalize()
                or "Other"
            )
            if team_label not in ("Blue", "Red"):
                team_label = "Other"
            groups.setdefault(team_label, []).append(player)
        for label, members in groups.items():
            members.sort(key=_rank_idx, reverse=True)

        self._player_model.removeRows(0, self._player_model.rowCount())
        self._banner_rows = []
        if not rows:
            self._players_empty.show()
            self._players_badge.set_value("0")
            return

        self._players_empty.hide()
        self._players_badge.set_value(str(len(rows)))

        weapon_choice = str(cfg.get("weapon") or "Vandal")

        # Render team-by-team with a banner row above each non-empty group.
        for team_label, members in groups.items():
            if not members:
                continue
            self._append_team_banner(team_label, len(members))
            for player in members:
                self._append_player_row(
                    player, weapon_choice, table_flags
                )
        # Make the banner rows span the full width of the table.
        self._refresh_banner_spans()
        return

    def _append_player_row(
        self,
        player: Dict[str, Any],
        weapon_choice: str,
        table_flags: Dict[str, Any],
    ) -> None:
        puuid = str(player.get("puuid") or "")
        is_self = bool(puuid) and puuid == self._own_puuid
        last_match = self._stats_repo.last_match(puuid) if puuid else None
        played_with = (
            self._stats_repo.times_played_with(puuid) if puuid else 0
        )
        rr_delta = (
            self._stats_repo.last_rr_delta(puuid) if puuid else None
        )
        tooltip = self._build_player_tooltip(
            player, last_match, played_with, rr_delta
        )
        row_items: List[QStandardItem] = []
        skin_url = self._skin_icon_url(player, weapon_choice)
        for key, _label in PLAYER_COLUMNS:
            value = self._cell_for(
                key, player, table_flags, weapon_choice, rr_delta
            )
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
            if key == "rrDelta":
                if rr_delta is not None and rr_delta > 0:
                    item.setForeground(QColor("#5fcf80"))
                elif rr_delta is not None and rr_delta < 0:
                    item.setForeground(QColor("#ff4655"))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
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
                if played_with > 0:
                    item.setText(item.text() + f"  ×{played_with}")
                if is_self:
                    # Mark the local player so the row stands out in lobbies
                    # with 10+ players.
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setForeground(QColor("#ff4655"))
                if tooltip:
                    item.setToolTip(tooltip)
            if key == "skin":
                if skin_url:
                    item.setData(skin_url, SKIN_ICON_URL_ROLE)
                    item.setToolTip(self._skin_tooltip(value, skin_url))
                    # Trigger lazy download so the tooltip is ready next time.
                    self._image_cache.request(skin_url)
            row_items.append(item)
        self._apply_team_color(row_items, player.get("team"))
        self._apply_glow(row_items, player.get("rank"))
        if is_self:
            self._apply_self_highlight(row_items)
        self._player_model.appendRow(row_items)

    def _append_team_banner(self, team_label: str, count: int) -> None:
        """Append a single 'BLUE TEAM' / 'RED TEAM' banner row to the model."""

        text = f"{team_label.upper()} TEAM \u00b7 {count}"
        item = QStandardItem(text)
        item.setEditable(False)
        item.setSelectable(False)
        font = item.font()
        font.setBold(True)
        font.setLetterSpacing(font.SpacingType.AbsoluteSpacing, 1)
        item.setFont(font)
        if team_label == "Blue":
            item.setForeground(QColor("#74a2d6"))
            item.setBackground(QBrush(QColor(58, 138, 232, 28)))
        elif team_label == "Red":
            item.setForeground(QColor("#ff7782"))
            item.setBackground(QBrush(QColor(255, 70, 85, 32)))
        else:
            item.setForeground(QColor("#aab5c5"))
            item.setBackground(QBrush(QColor(170, 181, 197, 22)))
        # Padding via leading whitespace so the banner reads more like a chip.
        item.setText("  " + text)
        # Track the banner row so we can call setSpan once the model is fully
        # populated. We only need the row index; spans are applied later.
        self._banner_rows.append(self._player_model.rowCount())
        # Empty placeholder cells for the remaining columns. setSpan can only
        # hide them visually — we still need them in the model.
        empties = [QStandardItem() for _ in range(len(PLAYER_COLUMNS) - 1)]
        for empty in empties:
            empty.setEditable(False)
            empty.setSelectable(False)
        self._player_model.appendRow([item, *empties])

    def _refresh_banner_spans(self) -> None:
        """Span each banner row across the entire table width."""

        for row in self._banner_rows:
            self._player_table.setSpan(row, 0, 1, len(PLAYER_COLUMNS))

    def _apply_self_highlight(self, items: List[QStandardItem]) -> None:
        """Tint the local player's row in red so it pops in the table."""

        brush = QBrush(QColor(255, 70, 85, 56))
        for item in items:
            item.setBackground(brush)

    def _cell_for(
        self,
        key: str,
        player: Dict[str, Any],
        table_flags: Dict[str, Any],
        weapon_choice: str,
        rr_delta: Optional[int],
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
        if key == "rrDelta":
            if rr_delta is None:
                return "—"
            return f"+{rr_delta}" if rr_delta > 0 else str(rr_delta)
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

    # ----------------------------------------------------- tooltip / glow
    def _build_player_tooltip(
        self,
        player: Dict[str, Any],
        last_match: Optional[Dict[str, Any]],
        played_with: int,
        rr_delta: Optional[int],
    ) -> str:
        bits: List[str] = []
        name = self._format_name(player)
        bits.append(f"<b>{name}</b>")

        if played_with > 0:
            bits.append(
                f"<span style='color:#8b95a3'>Played with you "
                f"{played_with} time{'s' if played_with != 1 else ''}</span>"
            )

        if last_match:
            ago = self._format_ago(last_match.get("epoch"))
            agent = _strip_ansi(str(last_match.get("agent") or ""))
            map_name = _strip_ansi(str(last_match.get("map") or ""))
            chunks: List[str] = []
            if agent:
                chunks.append(f"as <b>{agent}</b>")
            if map_name:
                chunks.append(f"on {map_name}")
            if ago:
                chunks.append(ago)
            if chunks:
                bits.append("Last seen: " + " ".join(chunks))

        if rr_delta is not None:
            sign = "+" if rr_delta > 0 else ""
            color = (
                "#5fcf80" if rr_delta > 0
                else "#ff4655" if rr_delta < 0
                else "#8b95a3"
            )
            bits.append(
                f"Last RR change: <span style='color:{color}'>{sign}{rr_delta}</span>"
            )

        if len(bits) <= 1:
            return ""
        return "<br>".join(bits)

    @staticmethod
    def _format_ago(epoch: Any) -> str:
        try:
            then = float(epoch)
        except (TypeError, ValueError):
            return ""
        if then <= 0:
            return ""
        seconds = max(0, int(time.time() - then))
        if seconds < 60:
            return f"{seconds}s ago"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        return f"{days}d ago"

    def _apply_glow(
        self, items: List[QStandardItem], rank: Any
    ) -> None:
        if not isinstance(rank, int) or rank < self.GLOW_RANK_THRESHOLD:
            return
        # Subtle highlight + bold name to mark Immortal/Radiant rows. We can't
        # do a real CSS box-shadow on a model item, but a brighter background
        # + bold weight on the name column reads as "premium" without being
        # noisy.
        glow = QBrush(QColor(255, 242, 145, 26))  # radiant yellow tint
        for item in items:
            existing = item.background()
            if existing.style() == Qt.BrushStyle.NoBrush:
                item.setBackground(glow)
        if items:
            font = items[NAME_COLUMN].font()
            font.setBold(True)
            items[NAME_COLUMN].setFont(font)

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
