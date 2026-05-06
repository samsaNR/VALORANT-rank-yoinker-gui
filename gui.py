"""Standalone entry point for the vRY GUI.

Run ``python gui.py`` (or use ``START_GUI.bat`` on Windows) to launch the
PySide6 menu instead of stepping through the console flow in ``main.py``.
"""

from __future__ import annotations

import sys

from src.gui import run

if __name__ == "__main__":
    sys.exit(run())
