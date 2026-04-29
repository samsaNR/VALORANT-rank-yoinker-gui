"""Read-only viewer for accounts saved by ``AccountManager``.

The CLI account manager relies on InquirerPy prompts which do not lend
themselves to embedding inside tkinter, so the GUI exposes the saved
accounts as an informational list. Adding/removing/switching accounts is
still done through the existing console flow.
"""

from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import ttk
from typing import Optional

from src.gui import theme

ACCOUNTS_PATH_ENV = "APPDATA"
ACCOUNTS_REL_PATH = os.path.join("vry", "accounts.json")


def accounts_file_path() -> Optional[str]:
    """Return the absolute path to ``accounts.json`` if it can be resolved."""
    base = os.getenv(ACCOUNTS_PATH_ENV)
    if not base:
        return None
    return os.path.join(base, ACCOUNTS_REL_PATH)


def load_accounts() -> dict:
    path = accounts_file_path()
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


class AccountsWindow(tk.Toplevel):
    """Show a table of every account vRY has previously authenticated with."""

    COLUMNS = ("name", "rank", "level", "battlepass")
    HEADINGS = {
        "name": "Account",
        "rank": "Rank",
        "level": "Level",
        "battlepass": "Battlepass",
    }

    def __init__(self, master: Optional[tk.Misc] = None) -> None:
        super().__init__(master)
        self.title("vRY \u2014 Accounts")
        self.geometry("600x420")
        self.minsize(520, 360)
        theme.apply_theme(self)

        self._build_layout()
        self.refresh()
        self.transient(master)
        self.grab_set()

    def _build_layout(self) -> None:
        container = ttk.Frame(self, padding=16)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="Accounts", style="Title.TLabel").pack(
            anchor="w"
        )
        path = accounts_file_path() or "(APPDATA not set)"
        ttk.Label(
            container,
            text=f"Source: {path}",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 8))

        table_frame = ttk.Frame(container)
        table_frame.pack(fill="both", expand=True)

        self._tree = ttk.Treeview(
            table_frame, columns=self.COLUMNS, show="headings", height=10
        )
        for col in self.COLUMNS:
            self._tree.heading(col, text=self.HEADINGS[col])
            anchor = "w" if col == "name" else "center"
            width = 220 if col == "name" else 110
            self._tree.column(col, anchor=anchor, width=width, stretch=True)
        self._tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(
            table_frame, orient="vertical", command=self._tree.yview
        )
        self._tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        self._empty_label = ttk.Label(
            container,
            text="No saved accounts yet. Use the CLI account manager to add one.",
            style="Muted.TLabel",
        )

        button_row = ttk.Frame(container)
        button_row.pack(fill="x", pady=(12, 0))
        ttk.Button(button_row, text="Close", command=self.destroy).pack(
            side="right"
        )
        ttk.Button(
            button_row,
            text="Refresh",
            command=self.refresh,
        ).pack(side="right", padx=(0, 8))

    def refresh(self) -> None:
        for row in self._tree.get_children():
            self._tree.delete(row)

        accounts = load_accounts()
        if not accounts:
            self._empty_label.pack(anchor="w", pady=(8, 0))
            return

        self._empty_label.pack_forget()
        for puuid, info in accounts.items():
            if not isinstance(info, dict):
                continue
            self._tree.insert(
                "",
                "end",
                iid=puuid,
                values=(
                    info.get("name", "?"),
                    info.get("rank", "?"),
                    info.get("level", "?"),
                    f"{info.get('bp_level', '?')}/55",
                ),
            )
