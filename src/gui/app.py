"""Entry point used by ``gui.py`` and ``START_GUI.bat``.

Builds the QApplication, applies the dark VALORANT-style stylesheet and
shows the main window.
"""

from __future__ import annotations

import os
import sys

from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from src.gui.main_window import MainWindow
from src.gui.style import BG, MUTED, PANEL, PANEL_ALT, QSS, TEXT
from src.gui.utils import repo_root


def _build_dark_palette() -> QPalette:
    """Return a Fusion-friendly dark palette that matches the QSS theme."""
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(PANEL))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(PANEL_ALT))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(PANEL_ALT))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(MUTED))
    palette.setColor(QPalette.ColorRole.Button, QColor(PANEL_ALT))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#ff4655"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Text,
        QColor(MUTED),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor(MUTED),
    )
    return palette


def _icon_path() -> str:
    candidate = os.path.join(repo_root(), "assets", "Logo.ico")
    return candidate if os.path.exists(candidate) else ""


def run() -> int:
    """Launch the GUI and return Qt's exit code."""
    QGuiApplication.setApplicationDisplayName("VALORANT rank yoinker")
    QGuiApplication.setApplicationName("vRY")
    QGuiApplication.setOrganizationName("vRY")

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(_build_dark_palette())
    app.setStyleSheet(QSS)

    icon = _icon_path()
    window = MainWindow(icon_path=icon or None)
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(run())
