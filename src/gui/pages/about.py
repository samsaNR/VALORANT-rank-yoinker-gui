"""About page with quick links and credits."""

from __future__ import annotations

import webbrowser
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.constants import version
from src.gui.pages._common import card, page_header

PROJECT_URL = "https://github.com/zayKenyon/VALORANT-rank-yoinker"
DISCORD_URL = "https://discord.gg/HeTKed64Ka"
DOCS_URL = "https://vry.netlify.app/matchLoadouts"


class AboutPage(QWidget):
    """Shows version, links and a short disclaimer."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        layout.addWidget(
            page_header(
                "About",
                f"VALORANT rank yoinker \u2014 GUI front-end (v{version}).",
            )
        )

        info = QLabel(
            "vRY is an open-source tracker that pulls rank, peak rank, "
            "headshot %, win rate, and skin info for everyone in your "
            "lobby straight from the Riot client. The GUI wraps the "
            "existing tracker so all of the same data is rendered in a "
            "modern Qt window instead of the console."
        )
        info.setWordWrap(True)
        info.setProperty("muted", True)
        layout.addWidget(card(info, title="Project"))

        disclaimer = QLabel(
            "This project is not associated or endorsed by Riot Games. "
            "Riot Games and all associated properties are trademarks or "
            "registered trademarks of Riot Games, Inc. Use at your own risk."
        )
        disclaimer.setWordWrap(True)
        disclaimer.setProperty("muted", True)
        layout.addWidget(card(disclaimer, title="Disclaimer"))

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        for label, url in (
            ("GitHub", PROJECT_URL),
            ("Discord", DISCORD_URL),
            ("Match Loadouts", DOCS_URL),
        ):
            btn = QPushButton(label)
            btn.clicked.connect(lambda _checked=False, u=url: webbrowser.open(u))
            button_row.addWidget(btn)

        button_row.addStretch(1)
        layout.addLayout(button_row)
        layout.addStretch(1)
