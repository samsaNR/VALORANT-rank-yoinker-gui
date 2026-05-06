"""Tiny SVG icon library used by the sidebar and headers.

Inline SVG keeps the assets self-contained (no extra files to ship through
cx_Freeze) while still benefiting from vector scaling at any DPI. Each icon
is a 24\u00d724 viewBox using ``currentColor`` semantics so we can recolor it
per state by passing a hex via ``svg_icon(name, color)``.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# 24x24 stroked icons, lucide-style.
_ICONS: dict[str, str] = {
    "tracker": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{stroke}" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="9"/>'
        '<circle cx="12" cy="12" r="5"/>'
        '<circle cx="12" cy="12" r="1.5" fill="{stroke}"/>'
        "</svg>"
    ),
    "loadouts": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{stroke}" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M3 7h13l3 3v7H3z"/>'
        '<path d="M3 11h16"/>'
        '<circle cx="7" cy="14" r="1.4"/>'
        "</svg>"
    ),
    "history": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{stroke}" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M3 12a9 9 0 1 0 3-6.7"/>'
        '<polyline points="3 4 3 9 8 9"/>'
        '<polyline points="12 7 12 12 15 14"/>'
        "</svg>"
    ),
    "stats": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{stroke}" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M3 3v18h18"/>'
        '<rect x="7" y="11" width="3" height="7"/>'
        '<rect x="12" y="7" width="3" height="11"/>'
        '<rect x="17" y="13" width="3" height="5"/>'
        "</svg>"
    ),
    "config": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{stroke}" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="3"/>'
        '<path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 0 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 0 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 0 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 0 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>'
        "</svg>"
    ),
    "accounts": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{stroke}" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>'
        '<circle cx="9" cy="7" r="4"/>'
        '<path d="M22 21v-2a4 4 0 0 0-3-3.9"/>'
        '<path d="M16 3.1a4 4 0 0 1 0 7.8"/>'
        "</svg>"
    ),
    "logs": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{stroke}" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
        '<polyline points="14 2 14 8 20 8"/>'
        '<line x1="9" y1="13" x2="15" y2="13"/>'
        '<line x1="9" y1="17" x2="13" y2="17"/>'
        "</svg>"
    ),
    "about": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{stroke}" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="9"/>'
        '<line x1="12" y1="8" x2="12" y2="8.01"/>'
        '<polyline points="11 12 12 12 12 16 13 16"/>'
        "</svg>"
    ),
    "play": (
        '<svg viewBox="0 0 24 24" fill="{stroke}" stroke="none">'
        '<path d="M7 5v14l12-7z"/>'
        "</svg>"
    ),
    "stop": (
        '<svg viewBox="0 0 24 24" fill="{stroke}" stroke="none">'
        '<rect x="6" y="6" width="12" height="12" rx="1"/>'
        "</svg>"
    ),
    "chevron_left": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{stroke}" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="15 6 9 12 15 18"/>'
        "</svg>"
    ),
    "chevron_right": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{stroke}" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="9 6 15 12 9 18"/>'
        "</svg>"
    ),
    "message": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{stroke}" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>'
        "</svg>"
    ),
    "refresh": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{stroke}" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="1 4 1 10 7 10"/>'
        '<polyline points="23 20 23 14 17 14"/>'
        '<path d="M20.5 9A9 9 0 0 0 5 5.7L1 10"/>'
        '<path d="M3.5 15A9 9 0 0 0 19 18.3L23 14"/>'
        "</svg>"
    ),
}


def svg_icon(name: str, color: str = "#ece8e1", size: int = 24) -> QIcon:
    """Return a QIcon rendered from the named inline SVG with ``color``."""

    template = _ICONS.get(name)
    if template is None:
        return QIcon()
    svg = template.format(stroke=color)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)
