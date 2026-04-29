"""Shared styling helpers for the vRY GUI.

The GUI uses ttk so it picks up the native look-and-feel on Windows while
still allowing us to override colours for the dark accent theme that matches
the console app's branding.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# VALORANT-inspired palette. Kept conservative so widgets stay readable.
BG = "#1a1d24"
PANEL = "#22262f"
ACCENT = "#ff4655"
ACCENT_HOVER = "#e03b48"
TEXT = "#ece8e1"
MUTED = "#9aa0a6"

FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_HEADING = ("Segoe UI", 12, "bold")
FONT_BODY = ("Segoe UI", 10)


def apply_theme(root: tk.Misc) -> ttk.Style:
    """Install the vRY ttk theme on ``root`` and return the configured style."""
    style = ttk.Style(root)
    # ``clam`` is available on every Tk build and lets us recolour widgets.
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=BG, foreground=TEXT, font=FONT_BODY)
    style.configure("TFrame", background=BG)
    style.configure("Panel.TFrame", background=PANEL)
    style.configure("TLabel", background=BG, foreground=TEXT, font=FONT_BODY)
    style.configure("Title.TLabel", background=BG, foreground=TEXT, font=FONT_TITLE)
    style.configure(
        "Heading.TLabel", background=BG, foreground=TEXT, font=FONT_HEADING
    )
    style.configure("Muted.TLabel", background=BG, foreground=MUTED)

    style.configure(
        "TButton",
        background=PANEL,
        foreground=TEXT,
        padding=(14, 8),
        borderwidth=0,
        focusthickness=0,
    )
    style.map(
        "TButton",
        background=[("active", "#2c313c"), ("pressed", "#2c313c")],
        foreground=[("disabled", MUTED)],
    )

    style.configure(
        "Accent.TButton",
        background=ACCENT,
        foreground="#ffffff",
        padding=(14, 10),
        font=FONT_HEADING,
        borderwidth=0,
    )
    style.map(
        "Accent.TButton",
        background=[("active", ACCENT_HOVER), ("pressed", ACCENT_HOVER)],
    )

    style.configure(
        "TNotebook", background=BG, borderwidth=0, tabmargins=(4, 6, 4, 0)
    )
    style.configure(
        "TNotebook.Tab",
        background=PANEL,
        foreground=TEXT,
        padding=(14, 6),
        borderwidth=0,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", ACCENT)],
        foreground=[("selected", "#ffffff")],
    )

    style.configure(
        "TCheckbutton", background=BG, foreground=TEXT, focuscolor=BG
    )
    style.map("TCheckbutton", background=[("active", BG)])

    style.configure(
        "TCombobox",
        fieldbackground=PANEL,
        background=PANEL,
        foreground=TEXT,
        arrowcolor=TEXT,
    )
    style.configure(
        "TSpinbox",
        fieldbackground=PANEL,
        background=PANEL,
        foreground=TEXT,
        arrowcolor=TEXT,
    )
    style.configure(
        "Treeview",
        background=PANEL,
        fieldbackground=PANEL,
        foreground=TEXT,
        bordercolor=BG,
        borderwidth=0,
        rowheight=26,
    )
    style.configure(
        "Treeview.Heading",
        background=BG,
        foreground=MUTED,
        font=FONT_HEADING,
        relief="flat",
    )
    style.map(
        "Treeview",
        background=[("selected", ACCENT)],
        foreground=[("selected", "#ffffff")],
    )

    root.configure(background=BG)
    return style
