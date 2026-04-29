"""GUI replacement for ``src.configurator``.

Mirrors the choices exposed by ``src/questions.py`` so power users can edit
``config.json`` from a tkinter window instead of stepping through the
InquirerPy prompts.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, Optional

from src.constants import DEFAULT_CONFIG, WEAPONS
from src.gui import theme
from src.gui.config_io import load_config, save_config
from src.questions import FLAGS_OPTS, TABLE_OPTS


class ConfigWindow(tk.Toplevel):
    """Modal window that edits ``config.json`` in place."""

    def __init__(self, master: Optional[tk.Misc] = None) -> None:
        super().__init__(master)
        self.title("vRY \u2014 Configuration")
        self.geometry("560x520")
        self.minsize(520, 480)
        theme.apply_theme(self)

        self.config_data: Dict[str, Any] = load_config()
        self._table_vars: Dict[str, tk.BooleanVar] = {}
        self._flag_vars: Dict[str, tk.BooleanVar] = {}
        self._weapon_var = tk.StringVar(
            value=self.config_data.get("weapon", DEFAULT_CONFIG["weapon"])
        )
        self._port_var = tk.StringVar(
            value=str(self.config_data.get("port", DEFAULT_CONFIG["port"]))
        )
        self._cooldown_var = tk.StringVar(
            value=str(self.config_data.get("cooldown", DEFAULT_CONFIG["cooldown"]))
        )
        self._chat_limit_var = tk.StringVar(
            value=str(
                self.config_data.get("chat_limit", DEFAULT_CONFIG["chat_limit"])
            )
        )

        self._build_layout()
        self.transient(master)
        self.grab_set()

    # ------------------------------------------------------------------ UI
    def _build_layout(self) -> None:
        container = ttk.Frame(self, padding=16)
        container.pack(fill="both", expand=True)

        ttk.Label(
            container, text="Configuration", style="Title.TLabel"
        ).pack(anchor="w")
        ttk.Label(
            container,
            text="Edit config.json without leaving the GUI.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 12))

        notebook = ttk.Notebook(container)
        notebook.pack(fill="both", expand=True)
        notebook.add(self._build_general_tab(notebook), text="General")
        notebook.add(self._build_table_tab(notebook), text="Table columns")
        notebook.add(self._build_flags_tab(notebook), text="Feature flags")

        button_row = ttk.Frame(container)
        button_row.pack(fill="x", pady=(14, 0))
        ttk.Button(button_row, text="Cancel", command=self.destroy).pack(
            side="right"
        )
        ttk.Button(
            button_row,
            text="Save",
            style="Accent.TButton",
            command=self._on_save,
        ).pack(side="right", padx=(0, 8))

    def _build_general_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=16)

        ttk.Label(frame, text="Weapon for skin column", style="Heading.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        weapon_box = ttk.Combobox(
            frame,
            textvariable=self._weapon_var,
            values=WEAPONS,
            state="readonly",
            width=24,
        )
        weapon_box.grid(row=1, column=0, sticky="w", pady=(0, 12))

        ttk.Label(
            frame, text="Server port", style="Heading.TLabel"
        ).grid(row=2, column=0, sticky="w", pady=(0, 4))
        ttk.Spinbox(
            frame,
            from_=1,
            to=65535,
            textvariable=self._port_var,
            width=10,
        ).grid(row=3, column=0, sticky="w", pady=(0, 12))

        ttk.Label(
            frame, text="Cooldown (seconds)", style="Heading.TLabel"
        ).grid(row=4, column=0, sticky="w", pady=(0, 4))
        ttk.Spinbox(
            frame,
            from_=1,
            to=600,
            textvariable=self._cooldown_var,
            width=10,
        ).grid(row=5, column=0, sticky="w", pady=(0, 12))

        ttk.Label(
            frame, text="Chat history length", style="Heading.TLabel"
        ).grid(row=6, column=0, sticky="w", pady=(0, 4))
        ttk.Spinbox(
            frame,
            from_=0,
            to=100,
            textvariable=self._chat_limit_var,
            width=10,
        ).grid(row=7, column=0, sticky="w")

        return frame

    def _build_table_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=16)
        ttk.Label(
            frame,
            text="Pick which columns appear in the live table.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 8))

        table_cfg = self.config_data.get("table", DEFAULT_CONFIG["table"])
        for key, label in TABLE_OPTS.items():
            var = tk.BooleanVar(
                value=bool(table_cfg.get(key, DEFAULT_CONFIG["table"][key]))
            )
            self._table_vars[key] = var
            ttk.Checkbutton(frame, text=label, variable=var).pack(
                anchor="w", pady=2
            )
        return frame

    def _build_flags_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=16)
        ttk.Label(
            frame,
            text="Toggle optional features.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 8))

        flag_cfg = self.config_data.get("flags", DEFAULT_CONFIG["flags"])
        for key, label in FLAGS_OPTS.items():
            var = tk.BooleanVar(
                value=bool(flag_cfg.get(key, DEFAULT_CONFIG["flags"][key]))
            )
            self._flag_vars[key] = var
            ttk.Checkbutton(frame, text=label, variable=var).pack(
                anchor="w", pady=2
            )
        return frame

    # -------------------------------------------------------------- actions
    def _collect(self) -> Optional[Dict[str, Any]]:
        try:
            port = int(self._port_var.get())
            cooldown = int(self._cooldown_var.get())
            chat_limit = int(self._chat_limit_var.get())
        except ValueError:
            messagebox.showerror(
                "Invalid value",
                "Port, cooldown and chat limit must be whole numbers.",
                parent=self,
            )
            return None

        if not (0 < port <= 65535):
            messagebox.showerror(
                "Invalid port",
                "Port must be between 1 and 65535.",
                parent=self,
            )
            return None

        if cooldown < 1:
            messagebox.showerror(
                "Invalid cooldown",
                "Cooldown must be at least 1 second.",
                parent=self,
            )
            return None

        if not (0 <= chat_limit <= 100):
            messagebox.showerror(
                "Invalid chat limit",
                "Chat limit must be between 0 and 100.",
                parent=self,
            )
            return None

        return {
            "cooldown": cooldown,
            "port": port,
            "weapon": self._weapon_var.get() or DEFAULT_CONFIG["weapon"],
            "chat_limit": chat_limit,
            "table": {key: var.get() for key, var in self._table_vars.items()},
            "flags": {key: var.get() for key, var in self._flag_vars.items()},
        }

    def _on_save(self) -> None:
        new_config = self._collect()
        if new_config is None:
            return

        try:
            save_config(new_config)
        except OSError as exc:
            messagebox.showerror(
                "Failed to save",
                f"Could not write config.json:\n{exc}",
                parent=self,
            )
            return

        messagebox.showinfo(
            "Saved",
            "Configuration saved to config.json.",
            parent=self,
        )
        self.destroy()
