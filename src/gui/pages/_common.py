"""Reusable building blocks for vRY GUI pages."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


def page_header(title: str, subtitle: str = "") -> QWidget:
    """Return a page header with title + muted subtitle."""
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)

    title_label = QLabel(title)
    title_label.setObjectName("pageTitle")
    layout.addWidget(title_label)

    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("pageSubtitle")
        layout.addWidget(subtitle_label)

    return container


def card(content: QWidget, title: Optional[str] = None) -> QFrame:
    """Wrap ``content`` in a styled card with optional heading."""
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(10)

    if title:
        heading = QLabel(title)
        heading.setObjectName("statLabel")
        heading.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(heading)

    layout.addWidget(content)
    return frame
