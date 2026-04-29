"""Standalone entry point for the vRY GUI launcher.

Run ``python gui.py`` (or use ``START_GUI.bat`` on Windows) to open the
graphical menu instead of the interactive console flow in ``main.py``.
"""

from src.gui import run

if __name__ == "__main__":
    run()
