"""Loadouts gallery \u2014 every player's full inventory in one place.

Mirrors the public ``vry.netlify.app/matchLoadouts`` view but inside the GUI.
The data comes from the ``matchLoadout`` payload broadcast by the tracker
(see :func:`src.Loadouts.Loadouts.convertLoadoutToJsonArray`). It contains
each player's full weapon inventory (per weapon: ``skinDisplayName``,
``skinDisplayIcon``, optional ``buddy_displayIcon``) plus their player card
and equipped sprays.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.gui.pages._common import card, page_header
from src.gui.workers.image_cache import ImageCache

_ANSI_RE = re.compile(r"(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]")


def _strip_ansi(value: str) -> str:
    return _ANSI_RE.sub("", value) if isinstance(value, str) else value


def _is_hidden_name(name: str) -> bool:
    """``names.py`` formats every player as ``f"{GameName}#{TagLine}"``; an
    incognito player ends up as just ``"#"``. We render the agent in that
    case to mirror what VALORANT itself shows."""

    if not isinstance(name, str):
        return True
    return name.strip() in ("", "#")


def _agent_display_name(loadout: Dict[str, Any]) -> str:
    """Best-effort extraction of the agent name from a loadout payload.

    The matchLoadout payload doesn't carry the bare agent name, but it does
    carry ``AgentArtworkName`` (e.g. ``"CypherArtwork"``) and the agent's
    ``displayIcon`` URL. Either is enough to recover the name without a
    second API call.
    """

    artwork = str(loadout.get("AgentArtworkName") or "").strip()
    if artwork.endswith("Artwork"):
        artwork = artwork[: -len("Artwork")]
    if artwork:
        return artwork
    icon_url = str(loadout.get("Agent") or "")
    # ``.../v1/agents/<uuid>/displayicon.png`` — no name in there, give up.
    if "/agents/" in icon_url:
        return ""
    return ""


class _SkinTile(QFrame):
    """Small card showing the icon and skin name for a single weapon."""

    ICON_SIZE = 96, 38

    def __init__(self, weapon: str, skin_name: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("skinTile")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(*self.ICON_SIZE)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setObjectName("skinTileIcon")
        layout.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignHCenter)

        self._weapon_label = QLabel(weapon)
        self._weapon_label.setObjectName("statLabel")
        layout.addWidget(self._weapon_label)

        self._skin_label = QLabel(skin_name)
        self._skin_label.setWordWrap(True)
        layout.addWidget(self._skin_label)

    def set_icon(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            return
        scaled = pixmap.scaled(
            self._icon_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._icon_label.setPixmap(scaled)


class _PlayerLoadoutCard(QFrame):
    """Per-player card with header (avatar + name + team) plus a weapons grid."""

    HEADER_AVATAR = 60, 60
    GRID_COLUMNS = 4

    def __init__(
        self,
        puuid: str,
        loadout: Dict[str, Any],
        image_cache: ImageCache,
        is_self: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("playerLoadoutCard")
        self.setProperty("team", loadout.get("Team") or "")
        self.setProperty("self", "true" if is_self else "false")
        self._is_self = is_self
        self._image_cache = image_cache
        self._tiles: List[tuple[str, _SkinTile]] = []
        self._avatar_url: str = ""
        self._avatar_label: QLabel = QLabel()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        layout.addLayout(self._build_header(loadout))
        layout.addWidget(self._build_grid(loadout))

    # ---------------------------------------------------------- header
    def _build_header(self, loadout: Dict[str, Any]) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        self._avatar_label = QLabel()
        self._avatar_label.setFixedSize(*self.HEADER_AVATAR)
        self._avatar_label.setObjectName("playerAvatar")
        self._avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._avatar_url = str(loadout.get("PlayerCard") or "")
        if self._avatar_url:
            cached = self._image_cache.request(self._avatar_url)
            if cached is not None:
                self._set_avatar(cached)
        row.addWidget(self._avatar_label, 0)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        agent_name = _agent_display_name(loadout)
        raw_name = _strip_ansi(str(loadout.get("Name") or "")).strip()
        hidden = _is_hidden_name(raw_name)
        if hidden:
            display_name = agent_name or "Hidden"
        else:
            display_name = raw_name

        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        name_row.setContentsMargins(0, 0, 0, 0)
        name_label = QLabel(display_name)
        name_label.setObjectName("playerName")
        if hidden:
            font = name_label.font()
            font.setItalic(True)
            name_label.setFont(font)
            name_label.setStyleSheet("color: #8b95a3;")
        if self._is_self:
            font = name_label.font()
            font.setBold(True)
            name_label.setFont(font)
            name_label.setStyleSheet("color: #ff4655;")
        name_row.addWidget(name_label)
        if self._is_self:
            you_pill = QLabel("YOU")
            you_pill.setObjectName("youPill")
            name_row.addWidget(you_pill, 0, Qt.AlignmentFlag.AlignVCenter)
        name_row.addStretch(1)
        text_col.addLayout(name_row)

        title = _strip_ansi(str(loadout.get("Title") or ""))
        meta_bits: List[str] = []
        if hidden:
            meta_bits.append("hidden")
        elif agent_name:
            # When the name IS visible, surface the agent next to the title so
            # the card still answers "who's playing what" at a glance.
            meta_bits.append(agent_name)
        if title:
            meta_bits.append(title)
        level = loadout.get("Level")
        if level:
            meta_bits.append(f"Lvl {level}")
        team = str(loadout.get("Team") or "")
        if team:
            meta_bits.append(f"Team {team}")
        meta_label = QLabel(" \u00b7 ".join(meta_bits) or "\u2014")
        meta_label.setProperty("muted", True)
        text_col.addWidget(meta_label)

        row.addLayout(text_col, 1)
        return row

    def _set_avatar(self, pixmap: QPixmap) -> None:
        scaled = pixmap.scaled(
            self._avatar_label.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._avatar_label.setPixmap(scaled)

    # ----------------------------------------------------------- grid
    def _build_grid(self, loadout: Dict[str, Any]) -> QWidget:
        weapons = loadout.get("Weapons") or {}
        if not isinstance(weapons, dict):
            weapons = {}

        # Order weapons sensibly: rifles / SMGs / pistols / etc.
        ordered = sorted(
            weapons.items(),
            key=lambda kv: str(kv[1].get("weapon") or "").lower()
            if isinstance(kv[1], dict)
            else "",
        )

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        index = 0
        for _uuid, entry in ordered:
            if not isinstance(entry, dict):
                continue
            weapon = str(entry.get("weapon") or "")
            if not weapon:
                continue
            skin_name = str(entry.get("skinDisplayName") or "\u2014")
            tile = _SkinTile(weapon, skin_name)
            icon_url = str(entry.get("skinDisplayIcon") or "")
            if icon_url:
                cached = self._image_cache.request(icon_url)
                if cached is not None:
                    tile.set_icon(cached)
            self._tiles.append((icon_url, tile))
            grid.addWidget(
                tile,
                index // self.GRID_COLUMNS,
                index % self.GRID_COLUMNS,
            )
            index += 1

        if index == 0:
            placeholder = QLabel("No weapons reported.")
            placeholder.setProperty("muted", True)
            grid.addWidget(placeholder, 0, 0)

        return grid_widget

    # ----------------------------------------------------- image updates
    def update_image(self, url: str, pixmap: QPixmap) -> None:
        if url == self._avatar_url and pixmap is not None and not pixmap.isNull():
            self._set_avatar(pixmap)
        for tile_url, tile in self._tiles:
            if tile_url == url:
                tile.set_icon(pixmap)


class LoadoutsPage(QWidget):
    """Scrollable gallery of every player's match loadout."""

    def __init__(
        self,
        image_cache: Optional[ImageCache] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._image_cache = image_cache or ImageCache(self)
        self._image_cache.image_ready.connect(self._on_image_ready)
        self._cards: List[_PlayerLoadoutCard] = []
        self._own_puuid: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        layout.addWidget(
            page_header(
                "Loadouts",
                "Every player's full inventory \u2014 same data as "
                "vry.netlify.app/matchLoadouts, but local.",
            )
        )

        self._meta_label = QLabel("Waiting for matchLoadout data\u2026")
        self._meta_label.setProperty("muted", True)
        layout.addWidget(self._meta_label)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(14)
        self._content_layout.addStretch(1)
        self._scroll.setWidget(self._content)
        layout.addWidget(self._scroll, 1)

    # --------------------------------------------------------- public
    def set_own_puuid(self, puuid: str) -> None:
        self._own_puuid = (puuid or "").strip()

    def apply_match_loadout(self, payload: Dict[str, Any]) -> None:
        players = payload.get("Players") or {}
        if not isinstance(players, dict):
            return

        # Tear down old cards.
        while self._content_layout.count() > 1:
            item = self._content_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        self._cards = []

        # Group by team — Blue / Red / other (DM, agent select). Keep the
        # alphabetical order inside each team for stability.
        from collections import OrderedDict

        groups: "OrderedDict[str, List[tuple[str, Dict[str, Any]]]]" = OrderedDict()
        groups["Blue"] = []
        groups["Red"] = []

        ordered_items = sorted(
            players.items(),
            key=lambda kv: (
                str(kv[1].get("Team") or ""),
                _strip_ansi(str(kv[1].get("Name") or "")).lower(),
            ),
        )
        for puuid, loadout in ordered_items:
            if not isinstance(loadout, dict):
                continue
            team_label = str(loadout.get("Team") or "Other").strip().capitalize()
            if team_label not in ("Blue", "Red"):
                team_label = "Other"
            groups.setdefault(team_label, []).append((str(puuid), loadout))

        for team_label, members in groups.items():
            if not members:
                continue
            section = self._build_team_section(team_label, members)
            self._content_layout.insertWidget(
                self._content_layout.count() - 1, section
            )

        map_name = str(payload.get("map") or "")
        meta = f"{len(self._cards)} player loadouts"
        if map_name:
            meta += f" \u00b7 map: {map_name}"
        self._meta_label.setText(meta)

    def _build_team_section(
        self,
        team_label: str,
        members: List[tuple[str, Dict[str, Any]]],
    ) -> QFrame:
        """Render a Blue/Red/Other team header followed by a 2-col card grid."""

        from PySide6.QtCore import Qt as _Qt

        section = QFrame()
        section.setObjectName("teamSection")
        outer = QVBoxLayout(section)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        header = QLabel(f"{team_label.upper()} \u00b7 {len(members)}")
        header.setObjectName("teamSectionTitle")
        header.setProperty("team", team_label)
        outer.addWidget(header)

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        grid.setContentsMargins(0, 0, 0, 0)

        for idx, (puuid, loadout) in enumerate(members):
            row, col = divmod(idx, 2)
            card = _PlayerLoadoutCard(
                puuid=puuid,
                loadout=loadout,
                image_cache=self._image_cache,
                is_self=bool(self._own_puuid) and puuid == self._own_puuid,
            )
            self._cards.append(card)
            grid.addWidget(card, row, col)

        # Make both columns share the available width.
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        outer.addWidget(grid_widget)
        return section

    # --------------------------------------------------------- internal
    def _on_image_ready(self, url: str, pixmap: QPixmap) -> None:
        for card in self._cards:
            card.update_image(url, pixmap)
