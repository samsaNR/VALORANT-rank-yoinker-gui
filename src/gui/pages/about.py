"""About page with quick links and credits."""

from __future__ import annotations

import webbrowser
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.constants import version
from src.gui.pages._common import card, page_header

GUI_FORK_URL = "https://github.com/samsaNR/VALORANT-rank-yoinker-gui"
TELEGRAM_URL = "https://t.me/rinonrc"


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
                f"vRY GUI \u2014 VALORANT match insights overlay (v{version}).",
            )
        )

        info = QLabel(
            "A modern Qt front-end for tracking your VALORANT lobby in real "
            "time \u2014 ranks, peak ranks, headshot %, win rates, K/D, "
            "skins, party groupings and in-match chat are pulled directly "
            "from the Riot client and shown in a clean dark UI. Stats and "
            "match history are stored locally on your machine."
        )
        info.setWordWrap(True)
        info.setProperty("muted", True)
        layout.addWidget(card(info, title="Project"))

        credits = QLabel(
            "Built by <a href=\"" + TELEGRAM_URL + "\" "
            "style=\"color:#ff4655;text-decoration:none;\">@rinonrc</a> "
            "(Telegram). Source on "
            "<a href=\"" + GUI_FORK_URL + "\" "
            "style=\"color:#ff4655;text-decoration:none;\">GitHub</a>."
        )
        credits.setOpenExternalLinks(True)
        credits.setWordWrap(True)
        credits.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(card(credits, title="Credits"))

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
            ("GitHub", GUI_FORK_URL),
            ("Telegram @rinonrc", TELEGRAM_URL),
        ):
            btn = QPushButton(label)
            btn.clicked.connect(lambda _checked=False, u=url: webbrowser.open(u))
            button_row.addWidget(btn)

        button_row.addStretch(1)
        layout.addLayout(button_row)
        layout.addStretch(1)
