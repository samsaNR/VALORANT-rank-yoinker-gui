"""Read-only viewer for accounts saved by the CLI account manager."""

from __future__ import annotations

import json
import os
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.gui.pages._common import page_header
from src.gui.utils import accounts_path


class AccountsPage(QWidget):
    """Renders ``%APPDATA%/vry/accounts.json`` as a sortable table."""

    HEADERS = ["Account", "Rank", "Level", "Battlepass"]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._build_layout()
        self.refresh()

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        header_row = QHBoxLayout()
        header_row.addWidget(
            page_header(
                "Accounts",
                "Riot accounts vRY has previously authenticated with.",
            ),
            1,
        )

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self.refresh)
        header_row.addWidget(
            self._refresh_btn, 0, Qt.AlignmentFlag.AlignTop
        )
        layout.addLayout(header_row)

        path = accounts_path() or "(APPDATA not set)"
        self._path_label = QLabel(f"Source: {path}")
        self._path_label.setProperty("muted", True)
        self._path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self._path_label)

        self._model = QStandardItemModel(0, len(self.HEADERS), self)
        self._model.setHorizontalHeaderLabels(self.HEADERS)

        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(True)
        header = self._table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._table, 1)

        self._empty_label = QLabel(
            "No saved accounts yet. Use the CLI account manager to add one."
        )
        self._empty_label.setProperty("muted", True)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.hide()
        layout.addWidget(self._empty_label)

    # ------------------------------------------------------------ data
    def refresh(self) -> None:
        self._model.removeRows(0, self._model.rowCount())
        accounts = self._load_accounts()
        if not accounts:
            self._empty_label.show()
            self._table.hide()
            return

        self._empty_label.hide()
        self._table.show()

        for info in accounts.values():
            if not isinstance(info, dict):
                continue
            row = [
                QStandardItem(str(info.get("name", "?"))),
                QStandardItem(str(info.get("rank", "?"))),
                QStandardItem(str(info.get("level", "?"))),
                QStandardItem(f"{info.get('bp_level', '?')}/55"),
            ]
            for item in row:
                item.setEditable(False)
            self._model.appendRow(row)

    def _load_accounts(self) -> dict:
        path = accounts_path()
        if not path or not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}
