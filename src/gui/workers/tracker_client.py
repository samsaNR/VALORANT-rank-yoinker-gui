"""Websocket client that subscribes to the tracker's structured payloads.

The tracker exposes a ``websocket-server`` socket on the port from
``config.json`` (default ``1100``). It broadcasts JSON messages tagged with
``type`` — ``heartbeat`` carries the live player table, ``chat`` carries
in-game chat, ``matchLoadout`` carries skin loadouts, etc. The GUI uses
``QtWebSockets`` so the network IO stays on Qt's event loop.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QAbstractSocket
from PySide6.QtWebSockets import QWebSocket


class TrackerClient(QObject):
    """Reconnect-friendly client for the tracker websocket server."""

    connected = Signal()
    disconnected = Signal()
    heartbeat = Signal(dict)
    chat_message = Signal(dict)
    match_loadout = Signal(dict)
    server_version = Signal(str)
    error = Signal(str)

    RECONNECT_INTERVAL_MS = 2000

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._socket = QWebSocket()
        self._socket.connected.connect(self._on_connected)
        self._socket.disconnected.connect(self._on_disconnected)
        self._socket.textMessageReceived.connect(self._on_message)
        self._socket.errorOccurred.connect(self._on_error)

        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setInterval(self.RECONNECT_INTERVAL_MS)
        self._reconnect_timer.timeout.connect(self._attempt_connect)

        self._url: Optional[QUrl] = None
        self._wanted = False

    # ---------------------------------------------------------- lifecycle
    def start(self, host: str, port: int) -> None:
        self._wanted = True
        self._url = QUrl(f"ws://{host}:{port}")
        self._attempt_connect()
        if not self._reconnect_timer.isActive():
            self._reconnect_timer.start()

    def stop(self) -> None:
        self._wanted = False
        self._reconnect_timer.stop()
        if self._socket.state() != QAbstractSocket.SocketState.UnconnectedState:
            self._socket.close()

    # ------------------------------------------------------------- helpers
    def _attempt_connect(self) -> None:
        if not self._wanted or self._url is None:
            return
        if self._socket.state() != QAbstractSocket.SocketState.UnconnectedState:
            return
        self._socket.open(self._url)

    # --------------------------------------------------------------- slots
    def _on_connected(self) -> None:
        self.connected.emit()

    def _on_disconnected(self) -> None:
        self.disconnected.emit()
        if self._wanted and not self._reconnect_timer.isActive():
            self._reconnect_timer.start()

    def _on_error(self, _err) -> None:
        # Errors typically resolve on reconnect; surface them so the UI can
        # display the last reason if needed.
        message = self._socket.errorString()
        if message:
            self.error.emit(message)

    def _on_message(self, raw: str) -> None:
        try:
            payload: Any = json.loads(raw)
        except json.JSONDecodeError:
            return
        if not isinstance(payload, dict):
            return

        msg_type = payload.get("type")
        if msg_type == "heartbeat":
            self.heartbeat.emit(payload)
        elif msg_type == "chat":
            self.chat_message.emit(payload)
        elif msg_type == "matchLoadout":
            self.match_loadout.emit(payload)
        elif msg_type == "version":
            self.server_version.emit(str(payload.get("core", "")))
