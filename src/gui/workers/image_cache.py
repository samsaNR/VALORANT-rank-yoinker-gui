"""Asynchronous image cache for player cards, agent art and weapon skins.

The tracker emits URLs (e.g. ``skinDisplayIcon``, ``PlayerCard``) coming from
``valorant-api.com``. The GUI fetches them lazily through Qt's network stack
so the UI never blocks. Pixmaps are cached both in memory and on disk under
the per-user app data directory, keyed by a hash of the URL.
"""

from __future__ import annotations

import hashlib
import os
from typing import Dict, Optional

from PySide6.QtCore import QObject, QStandardPaths, QUrl, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
)


class ImageCache(QObject):
    """In-memory + on-disk QPixmap cache keyed by URL.

    Use :meth:`request` to start (or reuse) a download; the
    :pyattr:`image_ready` signal fires with the original URL and the loaded
    pixmap as soon as it is available.
    """

    image_ready = Signal(str, QPixmap)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._memory: Dict[str, QPixmap] = {}
        self._inflight: Dict[str, QNetworkReply] = {}
        self._manager = QNetworkAccessManager(self)
        self._cache_dir = self._resolve_cache_dir()

    # ------------------------------------------------------------ public
    def get(self, url: str) -> Optional[QPixmap]:
        """Return the cached pixmap for ``url`` or ``None`` if not loaded."""

        if not url:
            return None
        pix = self._memory.get(url)
        if pix is not None:
            return pix
        path = self._disk_path(url)
        if os.path.exists(path):
            pix = QPixmap(path)
            if not pix.isNull():
                self._memory[url] = pix
                return pix
        return None

    def request(self, url: str) -> Optional[QPixmap]:
        """Start downloading ``url`` if needed, returning a cached pixmap."""

        if not url:
            return None
        cached = self.get(url)
        if cached is not None:
            return cached
        if url in self._inflight:
            return None
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", b"vRY-GUI/1.0")
        reply = self._manager.get(request)
        self._inflight[url] = reply
        reply.finished.connect(lambda r=reply, u=url: self._on_finished(u, r))
        return None

    # ----------------------------------------------------------- internals
    def _on_finished(self, url: str, reply: QNetworkReply) -> None:
        try:
            self._inflight.pop(url, None)
            if reply.error() != QNetworkReply.NetworkError.NoError:
                return
            data = bytes(reply.readAll())
            pix = QPixmap()
            if not pix.loadFromData(data):
                return
            self._memory[url] = pix
            try:
                with open(self._disk_path(url), "wb") as fh:
                    fh.write(data)
            except OSError:
                # Disk caching is best-effort.
                pass
            self.image_ready.emit(url, pix)
        finally:
            reply.deleteLater()

    def _disk_path(self, url: str) -> str:
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
        ext = os.path.splitext(url.split("?", 1)[0])[1].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".webp"):
            ext = ".bin"
        return os.path.join(self._cache_dir, digest + ext)

    @staticmethod
    def _resolve_cache_dir() -> str:
        base = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        )
        if not base:
            base = os.path.join(os.path.expanduser("~"), ".vry")
        cache = os.path.join(base, "img-cache")
        os.makedirs(cache, exist_ok=True)
        return cache
