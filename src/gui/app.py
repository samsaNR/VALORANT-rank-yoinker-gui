"""Main launcher window for the vRY GUI.

The launcher does not replace the rich console UI of the tracker; instead it
provides a discoverable menu that ties together the existing entry points:

* "Start tracker" launches ``main.py`` in a fresh console window so the rich
  player table is rendered as before.
* "Configure" opens a tkinter form bound to ``config.json``.
* "Accounts" lists accounts saved under ``%APPDATA%\\vry\\accounts.json``.
* Convenience buttons open the log file, the project page and the docs.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk
from typing import Optional

from src.constants import version
from src.gui import theme
from src.gui.accounts_window import AccountsWindow
from src.gui.config_window import ConfigWindow

PROJECT_URL = "https://github.com/zayKenyon/VALORANT-rank-yoinker"
DISCORD_URL = "https://discord.gg/HeTKed64Ka"
LOG_FILE = "logs.log"


def _repo_root() -> str:
    """Return the directory that contains ``main.py``.

    When running from source ``__file__`` lives at ``<repo>/src/gui/app.py``.
    When packaged with cx_Freeze the modules sit next to the executable, so
    we fall back to the executable's directory in that case.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _main_entry() -> Optional[str]:
    """Locate the tracker entry point that ``Start tracker`` should launch."""
    root = _repo_root()
    candidates = ["main.py", "vry.exe", "VALORANT rank yoinker.exe"]
    for name in candidates:
        path = os.path.join(root, name)
        if os.path.exists(path):
            return path
    return None


def _open_path(path: str) -> bool:
    """Open ``path`` in the user's default file handler."""
    if not os.path.exists(path):
        return False
    try:
        if platform.system() == "Windows":
            os.startfile(path)  # type: ignore[attr-defined]
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except OSError:
        return False
    return True


class VryGuiApp(tk.Tk):
    """Top-level launcher window."""

    def __init__(self) -> None:
        super().__init__()
        self.title(f"vRY \u2014 VALORANT rank yoinker v{version}")
        self.geometry("520x460")
        self.minsize(480, 420)
        theme.apply_theme(self)

        self._tracker_proc: Optional[subprocess.Popen] = None
        self._build_layout()

    # ------------------------------------------------------------------ UI
    def _build_layout(self) -> None:
        container = ttk.Frame(self, padding=24)
        container.pack(fill="both", expand=True)

        ttk.Label(
            container,
            text="VALORANT rank yoinker",
            style="Title.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            container,
            text=f"Version {version}",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 18))

        ttk.Button(
            container,
            text="Start tracker",
            style="Accent.TButton",
            command=self._on_start_tracker,
        ).pack(fill="x")

        actions = ttk.Frame(container)
        actions.pack(fill="x", pady=(12, 0))
        actions.columnconfigure(0, weight=1, uniform="actions")
        actions.columnconfigure(1, weight=1, uniform="actions")

        ttk.Button(
            actions, text="Configure", command=self._on_configure
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=4)
        ttk.Button(
            actions, text="Accounts", command=self._on_accounts
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0), pady=4)
        ttk.Button(
            actions, text="Open logs", command=self._on_open_logs
        ).grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=4)
        ttk.Button(
            actions, text="Open config folder", command=self._on_open_folder
        ).grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=4)
        ttk.Button(
            actions, text="Project page", command=self._on_project_page
        ).grid(row=2, column=0, sticky="ew", padx=(0, 6), pady=4)
        ttk.Button(
            actions, text="Discord", command=self._on_discord
        ).grid(row=2, column=1, sticky="ew", padx=(6, 0), pady=4)

        spacer = ttk.Frame(container)
        spacer.pack(fill="both", expand=True)

        self._status_var = tk.StringVar(value="Idle")
        ttk.Label(
            container,
            textvariable=self._status_var,
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(12, 0))

        ttk.Button(container, text="Exit", command=self.destroy).pack(
            anchor="e", pady=(8, 0)
        )

    # -------------------------------------------------------------- actions
    def _set_status(self, message: str) -> None:
        self._status_var.set(message)

    def _on_start_tracker(self) -> None:
        if self._tracker_proc is not None and self._tracker_proc.poll() is None:
            messagebox.showinfo(
                "Tracker already running",
                "vRY is already running in another window.",
                parent=self,
            )
            return

        entry = _main_entry()
        if entry is None:
            messagebox.showerror(
                "Tracker not found",
                "Could not find main.py or vRY.exe next to the GUI.",
                parent=self,
            )
            return

        cwd = _repo_root()
        try:
            if entry.endswith(".py"):
                command = [sys.executable, entry]
            else:
                command = [entry]

            kwargs: dict = {"cwd": cwd}
            if platform.system() == "Windows":
                # Open in a new console so the rich output stays visible.
                kwargs["creationflags"] = (
                    subprocess.CREATE_NEW_CONSOLE  # type: ignore[attr-defined]
                )
            self._tracker_proc = subprocess.Popen(command, **kwargs)
        except (OSError, ValueError) as exc:
            messagebox.showerror(
                "Failed to launch",
                f"Could not start the tracker:\n{exc}",
                parent=self,
            )
            return

        self._set_status(f"Tracker started (pid {self._tracker_proc.pid})")

    def _on_configure(self) -> None:
        ConfigWindow(self)

    def _on_accounts(self) -> None:
        AccountsWindow(self)

    def _on_open_logs(self) -> None:
        log_path = os.path.join(_repo_root(), LOG_FILE)
        if not _open_path(log_path):
            messagebox.showinfo(
                "Log not available",
                "logs.log will appear here once the tracker has run at least once.",
                parent=self,
            )

    def _on_open_folder(self) -> None:
        if not _open_path(_repo_root()):
            messagebox.showerror(
                "Failed to open",
                "Could not open the project folder.",
                parent=self,
            )

    def _on_project_page(self) -> None:
        webbrowser.open(PROJECT_URL)

    def _on_discord(self) -> None:
        webbrowser.open(DISCORD_URL)


def run() -> None:
    """Entrypoint used by ``gui.py`` and ``python main.py --gui``."""
    app = VryGuiApp()
    app.mainloop()
