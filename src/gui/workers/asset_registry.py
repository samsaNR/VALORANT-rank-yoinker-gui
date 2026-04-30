"""Asynchronous registry for VALORANT static assets.

Keeps three lookups cached in memory:

* ``agent_icon_url(name)`` \u2192 URL of the agent's circular display icon.
* ``rank_icon_url(idx)`` \u2192 URL of the small rank icon for the given
  competitive-tier index used by the tracker.
* ``skin_tier_color(skin_display_name)`` \u2192 ``(r, g, b)`` content-tier
  colour for a skin, or ``None`` for default-tier skins.

The data comes from valorant-api.com and is fetched **once** on startup
through Qt's network stack. Until the responses arrive, the lookups
return ``None``; once :pyattr:`assets_ready` fires, callers can refresh
their UI to show icons.
"""

from __future__ import annotations

import json
import re
from typing import Dict, Optional, Tuple

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
)

from src.constants import tierDict


_AGENTS_URL = "https://valorant-api.com/v1/agents?isPlayableCharacter=true"
_TIERS_URL = "https://valorant-api.com/v1/competitivetiers"
_SKINS_URL = "https://valorant-api.com/v1/weapons/skins"


def _strip_weapon_suffix(name: str) -> str:
    """Strip the trailing weapon name from a skin display name.

    The API ships skins as ``"Reaver Vandal"`` while the tracker ends up
    showing just ``"Reaver"`` in the table. We normalise by indexing on
    the leading words so both forms match the same content tier.
    """

    return re.sub(r"\s+\S+$", "", name).strip().lower() if name else ""


class AssetRegistry(QObject):
    """Fetches and exposes agent / rank / skin metadata from valorant-api."""

    assets_ready = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._manager = QNetworkAccessManager(self)
        self._agents: Dict[str, str] = {}
        self._ranks: Dict[int, str] = {}
        self._skin_full: Dict[str, Tuple[int, int, int]] = {}
        self._skin_short: Dict[str, Tuple[int, int, int]] = {}
        self._pending = 0

    # ------------------------------------------------------------ public
    def start(self) -> None:
        """Kick off the three lookups in parallel."""

        for url, handler in (
            (_AGENTS_URL, self._on_agents),
            (_TIERS_URL, self._on_tiers),
            (_SKINS_URL, self._on_skins),
        ):
            self._pending += 1
            request = QNetworkRequest(QUrl(url))
            request.setRawHeader(b"User-Agent", b"vRY-GUI/1.0")
            reply = self._manager.get(request)
            reply.finished.connect(
                lambda r=reply, h=handler: self._dispatch(r, h)
            )

    def agent_icon_url(self, name: str) -> str:
        if not name:
            return ""
        return self._agents.get(name.strip().lower(), "")

    def rank_icon_url(self, rank_idx: int) -> str:
        if not isinstance(rank_idx, int):
            return ""
        return self._ranks.get(rank_idx, "")

    def skin_tier_color(self, display_name: str) -> Optional[Tuple[int, int, int]]:
        if not display_name:
            return None
        name = display_name.strip().lower()
        # First try the exact match (\u201cReaver Vandal\u201d), then the
        # weapon-stripped form (\u201cReaver\u201d) which is what the
        # tracker shows.
        tier = self._skin_full.get(name)
        if tier is not None:
            return tier
        return self._skin_short.get(_strip_weapon_suffix(display_name))

    # ------------------------------------------------------------ helpers
    def _dispatch(self, reply: QNetworkReply, handler) -> None:
        try:
            if reply.error() == QNetworkReply.NetworkError.NoError:
                try:
                    handler(json.loads(bytes(reply.readAll())))
                except (json.JSONDecodeError, ValueError):
                    pass
        finally:
            reply.deleteLater()
            self._pending -= 1
            if self._pending <= 0:
                self.assets_ready.emit()

    def _on_agents(self, payload: dict) -> None:
        for entry in payload.get("data") or []:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("displayName") or "").strip().lower()
            icon = str(entry.get("displayIcon") or "")
            if name and icon:
                self._agents[name] = icon

    def _on_tiers(self, payload: dict) -> None:
        # The endpoint returns a list of competitive-tier sets ordered by
        # episode/act. The last entry is the most recent one and matches
        # what ``NUMBERTORANKS`` indexes into.
        sets = payload.get("data") or []
        latest = sets[-1] if sets else {}
        for entry in latest.get("tiers") or []:
            if not isinstance(entry, dict):
                continue
            tier = entry.get("tier")
            icon = entry.get("smallIcon") or entry.get("largeIcon")
            if isinstance(tier, int) and icon:
                self._ranks[tier] = str(icon)

    def _on_skins(self, payload: dict) -> None:
        for entry in payload.get("data") or []:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("displayName") or "").strip().lower()
            tier_uuid = entry.get("contentTierUuid")
            color = tierDict.get(tier_uuid) if tier_uuid else None
            if not name or color is None:
                continue
            self._skin_full[name] = color
            short = _strip_weapon_suffix(name)
            if short:
                self._skin_short[short] = color
