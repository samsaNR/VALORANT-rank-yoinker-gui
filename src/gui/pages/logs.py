"""Logs page \u2014 mirrors raw tracker output and the on-disk log file."""

from __future__ import annotations

import os
import re
from typing import Optional

from PySide6.QtCore import QFileSystemWatcher, Qt
from PySide6.QtGui import QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.pages._common import page_header
from src.gui.utils import log_path

# Strip ANSI control sequences before showing them in the log view. The
# tracker uses them for colour-coded console output which is meaningless
# inside a plain QPlainTextEdit.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_TITLE_RE = re.compile(r"\x1b\][^\x07]*\x07")
_CURSOR_RE = re.compile(r"\x1b\[[0-9]*[ABCDEFGHJKST]")


def strip_ansi(text: str) -> str:
    cleaned = _TITLE_RE.sub("", text)
    cleaned = _ANSI_RE.sub("", cleaned)
    cleaned = _CURSOR_RE.sub("", cleaned)
    return cleaned


class LogsPage(QWidget):
    """Streams output from the tracker subprocess and tails ``logs.log``."""

    MAX_LINES = 4000

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._build_layout()

        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._on_log_file_changed)
        self._log_offset = 0
        self._watch_log_file()

    # ------------------------------------------------------------ layout
    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        header_row.addWidget(
            page_header(
                "Logs",
                "Live output from the tracker plus contents of logs.log.",
            ),
            1,
        )
        self._clear_btn = QPushButton("Clear view")
        self._clear_btn.clicked.connect(self._on_clear)
        header_row.addWidget(self._clear_btn, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header_row)

        path_label = QLabel(f"Log file: {log_path()}")
        path_label.setProperty("muted", True)
        path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(path_label)

        self._view = QPlainTextEdit()
        self._view.setReadOnly(True)
        self._view.setMaximumBlockCount(self.MAX_LINES)
        self._view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = self._view.font()
        font.setFamily("Cascadia Mono")
        font.setStyleHint(font.StyleHint.Monospace)
        font.setPointSize(10)
        self._view.setFont(font)
        layout.addWidget(self._view, 1)

    # ----------------------------------------------------------- helpers
    def _watch_log_file(self) -> None:
        path = log_path()
        if os.path.exists(path):
            try:
                self._log_offset = os.path.getsize(path)
            except OSError:
                self._log_offset = 0
            self._watcher.addPath(path)

    def append_line(self, text: str) -> None:
        cleaned = strip_ansi(text).rstrip("\r\n")
        if not cleaned:
            return
        cursor = self._view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(cleaned + "\n", QTextCharFormat())
        self._view.moveCursor(QTextCursor.MoveOperation.End)

    def append_chunk(self, text: str) -> None:
        for line in text.splitlines():
            self.append_line(line)

    # ------------------------------------------------------------ slots
    def _on_clear(self) -> None:
        self._view.clear()

    def _on_log_file_changed(self, path: str) -> None:
        if not os.path.exists(path):
            self._log_offset = 0
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self._log_offset)
                new_data = f.read()
                self._log_offset = f.tell()
        except OSError:
            return
        if new_data:
            self.append_chunk(new_data)
        # Some editors swap files atomically, which removes the watch entry.
        if path not in self._watcher.files():
            self._watcher.addPath(path)
