"""Path / environment helpers used by the GUI."""

from __future__ import annotations

import os
import sys

LOG_FILE = "logs.log"


def repo_root() -> str:
    """Return the directory that holds ``main.py`` and ``config.json``.

    When the GUI runs from source ``__file__`` lives at
    ``<repo>/src/gui/utils.py``. When packaged with cx_Freeze the modules sit
    next to the executable, so we fall back to the executable's directory.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def log_path() -> str:
    return os.path.join(repo_root(), LOG_FILE)


def accounts_path() -> str | None:
    base = os.getenv("APPDATA")
    if not base:
        return None
    return os.path.join(base, "vry", "accounts.json")
