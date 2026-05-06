"""Configuration page \u2014 mirrors ``src/questions.py``.

Modern card-based layout with sectioned settings, ToggleSwitch controls for
booleans, and an inline search bar that filters rows live by label/description.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.constants import DEFAULT_CONFIG, WEAPONS
from src.gui.config_io import load_config, save_config
from src.gui.pages._common import page_header
from src.gui.widgets import ToggleSwitch
from src.questions import FLAGS_OPTS, TABLE_OPTS

# Short helper text to give context next to each toggle. Anything not listed
# here falls back to the value from FLAGS_OPTS / TABLE_OPTS only.
_FLAG_DESCRIPTIONS: Dict[str, str] = {
    "last_played": "Show last-match notes when re-meeting players you've seen recently.",
    "auto_hide_leaderboard": "Hide the Pos. column when nobody in the lobby is on the leaderboard.",
    "pre_cls": "Clear the console before each render in the CLI version.",
    "game_chat": "Forward in-match chat to the GUI panel and the console.",
    "peak_rank_act": "Append the act/episode tag (e10a3) to peak rank values.",
    "discord_rpc": "Push your current rank/RR to Discord Rich Presence.",
    "aggregate_rank_rr": "Render rank and RR as a single column (e.g. \u201cDiamond 1 (45)\u201d).",
    "server_id": "Show the matchmaker region (e.g. \u201cnyc-1\u201d) in the title bar.",
    "short_ranks": "Use compact rank labels (\u201cD1\u201d) instead of full names.",
    "truncate_skins": "Truncate long skin names when the window is narrow.",
    "truncate_names": "Truncate long player names when the window is narrow.",
}

_TABLE_DESCRIPTIONS: Dict[str, str] = {
    "skin": "Equipped skin name on the configured weapon.",
    "rr": "Current ranked rating.",
    "earned_rr": "Last-game RR delta and any AFK penalties.",
    "leaderboard": "Leaderboard position for Immortal+ players.",
    "peakrank": "Highest rank ever reached by the player.",
    "previousrank": "Rank from the previous competitive act.",
    "headshot_percent": "Lifetime headshot percentage.",
    "winrate": "Lifetime win rate with sample size.",
    "kd": "Kills/Deaths ratio (last completed match only).",
    "level": "Account level.",
}


class _SettingRow(QWidget):
    """A single labelled setting row.

    Left column: bold label + muted description. Right column: arbitrary
    control widget (combo box, spin box, toggle, ...). Stored references on
    the widget so the page-wide search box can show/hide rows in O(1).
    """

    def __init__(
        self,
        label: str,
        description: str,
        control: QWidget,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._search_haystack = f"{label} {description}".lower()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(12)

        # Text column.
        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(2)
        title = QLabel(label)
        title.setObjectName("settingTitle")
        title.setWordWrap(True)
        text_box.addWidget(title)
        if description:
            sub = QLabel(description)
            sub.setObjectName("settingDescription")
            sub.setProperty("muted", True)
            sub.setWordWrap(True)
            text_box.addWidget(sub)
        layout.addLayout(text_box, 1)

        # Right-aligned control.
        control.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout.addWidget(control, 0, Qt.AlignmentFlag.AlignRight)

    def matches(self, query: str) -> bool:
        return not query or query in self._search_haystack


class _SettingCard(QFrame):
    """A titled card containing one or more :class:`_SettingRow` widgets."""

    def __init__(
        self,
        title: str,
        description: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("settingCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(4)

        heading = QLabel(title)
        heading.setObjectName("settingCardTitle")
        layout.addWidget(heading)

        if description:
            sub = QLabel(description)
            sub.setObjectName("settingCardDescription")
            sub.setProperty("muted", True)
            sub.setWordWrap(True)
            layout.addWidget(sub)

        self._rows_layout = QVBoxLayout()
        self._rows_layout.setContentsMargins(0, 6, 0, 0)
        self._rows_layout.setSpacing(0)
        layout.addLayout(self._rows_layout)

        self._rows: List[_SettingRow] = []

    def add_row(self, row: _SettingRow) -> None:
        if self._rows:
            # Thin divider between rows so the card reads as a list, not a
            # blob.
            divider = QFrame()
            divider.setObjectName("settingDivider")
            divider.setFrameShape(QFrame.Shape.HLine)
            divider.setFixedHeight(1)
            self._rows_layout.addWidget(divider)
        self._rows_layout.addWidget(row)
        self._rows.append(row)

    def filter(self, query: str) -> bool:
        """Hide rows that don't match query; return True if any survive."""
        any_visible = False
        last_visible_index = -1
        # First, decide visibility per row.
        for idx, row in enumerate(self._rows):
            visible = row.matches(query)
            row.setVisible(visible)
            if visible:
                any_visible = True
                last_visible_index = idx
        # Hide dividers separating hidden rows. Dividers live at odd indices
        # in the layout (row, div, row, div, ...).
        for layout_idx in range(self._rows_layout.count()):
            item = self._rows_layout.itemAt(layout_idx)
            widget = item.widget() if item is not None else None
            if widget is None or widget.objectName() != "settingDivider":
                continue
            # A divider before row at logical position N visually separates
            # the previous visible row from row N. Hide if either neighbour
            # is hidden. Logical layout pattern: row0, div, row1, div, row2..
            row_index = (layout_idx + 1) // 2
            prev_visible = (
                row_index > 0 and self._rows[row_index - 1].isVisible()
            )
            curr_visible = (
                row_index < len(self._rows)
                and self._rows[row_index].isVisible()
            )
            widget.setVisible(prev_visible and curr_visible)
        self.setVisible(any_visible)
        # Avoid the dangling divider after the final visible row.
        if last_visible_index >= 0:
            for layout_idx in range(self._rows_layout.count() - 1, -1, -1):
                item = self._rows_layout.itemAt(layout_idx)
                widget = item.widget() if item is not None else None
                if widget is None or widget.objectName() != "settingDivider":
                    continue
                row_index = (layout_idx + 1) // 2
                if row_index > last_visible_index:
                    widget.hide()
        return any_visible


class ConfigurationPage(QWidget):
    """Editor for ``config.json`` exposed in the main window."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config: Dict[str, Any] = load_config()
        self._cards: List[_SettingCard] = []
        self._table_toggles: Dict[str, ToggleSwitch] = {}
        self._flag_toggles: Dict[str, ToggleSwitch] = {}

        self._build_layout()
        self._populate_from_config()

    # ------------------------------------------------------------ layout
    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        layout.addWidget(
            page_header(
                "Configuration",
                "Live tracker preferences. Search, toggle, save \u2014 changes are written back to config.json.",
            )
        )

        # Search bar in a thin pill above the cards.
        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(8)

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText(
            "\U0001f50d  Search settings (e.g. 'discord', 'k/d', 'short')"
        )
        self._search_box.setClearButtonEnabled(True)
        self._search_box.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self._search_box, 1)
        layout.addLayout(search_row)

        # Scrollable cards column.
        scroll = QScrollArea()
        scroll.setObjectName("configScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_body = QWidget()
        scroll_body.setObjectName("configScrollBody")
        body_layout = QVBoxLayout(scroll_body)
        body_layout.setContentsMargins(2, 2, 2, 2)
        body_layout.setSpacing(16)

        body_layout.addWidget(self._build_general_card())
        body_layout.addWidget(self._build_table_card())
        body_layout.addWidget(self._build_flags_card())
        body_layout.addStretch(1)

        scroll.setWidget(scroll_body)
        layout.addWidget(scroll, 1)

        # Action footer.
        footer = QHBoxLayout()
        self._status_label = QLabel("")
        self._status_label.setObjectName("settingStatus")
        self._status_label.setProperty("muted", True)
        footer.addWidget(self._status_label, 1)

        self._reset_btn = QPushButton("Reset")
        self._reset_btn.setObjectName("ghost")
        self._reset_btn.setToolTip("Reload config.json and discard unsaved edits.")
        self._reset_btn.clicked.connect(self._on_reset)
        footer.addWidget(self._reset_btn)

        self._save_btn = QPushButton("Save changes")
        self._save_btn.setObjectName("primary")
        self._save_btn.clicked.connect(self._on_save)
        footer.addWidget(self._save_btn)
        layout.addLayout(footer)

    def _build_general_card(self) -> _SettingCard:
        card = _SettingCard(
            "General",
            "Core tracker behaviour: which weapon is shown for skins, on which port the GUI bridge listens, and how often the table refreshes.",
        )

        self._weapon_box = QComboBox()
        self._weapon_box.addItems(WEAPONS)
        card.add_row(
            _SettingRow(
                "Weapon",
                "Skin shown for each player in the live table.",
                self._weapon_box,
            )
        )

        self._port_spin = QSpinBox()
        self._port_spin.setRange(1, 65535)
        self._port_spin.setMinimumWidth(120)
        card.add_row(
            _SettingRow(
                "Server port",
                "Local websocket bridge between the tracker and the GUI.",
                self._port_spin,
            )
        )

        self._cooldown_spin = QSpinBox()
        self._cooldown_spin.setRange(1, 600)
        self._cooldown_spin.setSuffix(" s")
        self._cooldown_spin.setMinimumWidth(120)
        card.add_row(
            _SettingRow(
                "Refresh cooldown",
                "Seconds between heartbeats sent to the GUI / printed to the CLI.",
                self._cooldown_spin,
            )
        )

        self._chat_spin = QSpinBox()
        self._chat_spin.setRange(0, 100)
        self._chat_spin.setMinimumWidth(120)
        card.add_row(
            _SettingRow(
                "CLI chat history",
                "Number of latest game-chat messages kept in the CLI scrollback (0 disables).",
                self._chat_spin,
            )
        )

        self._cards.append(card)
        return card

    def _build_table_card(self) -> _SettingCard:
        card = _SettingCard(
            "Player table columns",
            "Pick which columns appear in the live tracker table.",
        )

        for key, label in TABLE_OPTS.items():
            toggle = ToggleSwitch()
            self._table_toggles[key] = toggle
            description = _TABLE_DESCRIPTIONS.get(key, "")
            card.add_row(_SettingRow(label, description, toggle))

        self._cards.append(card)
        return card

    def _build_flags_card(self) -> _SettingCard:
        card = _SettingCard(
            "Feature flags",
            "Optional behaviours for the tracker and CLI.",
        )

        for key, label in FLAGS_OPTS.items():
            toggle = ToggleSwitch()
            self._flag_toggles[key] = toggle
            description = _FLAG_DESCRIPTIONS.get(key, "")
            card.add_row(_SettingRow(label, description, toggle))

        self._cards.append(card)
        return card

    # ------------------------------------------------------------ search
    def _on_search_changed(self, text: str) -> None:
        query = text.strip().lower()
        for card in self._cards:
            card.filter(query)

    # ------------------------------------------------------------ helpers
    def _populate_from_config(self) -> None:
        weapon = self._config.get("weapon", DEFAULT_CONFIG["weapon"])
        if weapon in WEAPONS:
            self._weapon_box.setCurrentText(weapon)
        else:
            self._weapon_box.setCurrentText(DEFAULT_CONFIG["weapon"])

        self._port_spin.setValue(int(self._config.get("port", DEFAULT_CONFIG["port"])))
        self._cooldown_spin.setValue(
            int(self._config.get("cooldown", DEFAULT_CONFIG["cooldown"]))
        )
        self._chat_spin.setValue(
            int(self._config.get("chat_limit", DEFAULT_CONFIG["chat_limit"]))
        )

        table_cfg = self._config.get("table", DEFAULT_CONFIG["table"])
        for key, toggle in self._table_toggles.items():
            toggle.setChecked(
                bool(table_cfg.get(key, DEFAULT_CONFIG["table"][key]))
            )

        flag_cfg = self._config.get("flags", DEFAULT_CONFIG["flags"])
        for key, toggle in self._flag_toggles.items():
            toggle.setChecked(
                bool(flag_cfg.get(key, DEFAULT_CONFIG["flags"][key]))
            )

    def _collect(self) -> Dict[str, Any]:
        return {
            "cooldown": int(self._cooldown_spin.value()),
            "port": int(self._port_spin.value()),
            "weapon": self._weapon_box.currentText() or DEFAULT_CONFIG["weapon"],
            "chat_limit": int(self._chat_spin.value()),
            "table": {key: t.isChecked() for key, t in self._table_toggles.items()},
            "flags": {key: t.isChecked() for key, t in self._flag_toggles.items()},
        }

    # ------------------------------------------------------------ slots
    def _on_save(self) -> None:
        try:
            new_config = self._collect()
            save_config(new_config)
        except OSError as exc:
            QMessageBox.critical(
                self, "Failed to save", f"Could not write config.json:\n{exc}"
            )
            return

        self._config = new_config
        self._status_label.setText("Saved \u2713")
        self._status_label.setStyleSheet("color: #5fcf80;")

    def _on_reset(self) -> None:
        self._config = load_config()
        self._populate_from_config()
        self._status_label.setText("Reset to last saved values")
        self._status_label.setStyleSheet("")
