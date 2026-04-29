"""System-wide hotkey listener.

On Windows we register a hotkey via the ``RegisterHotKey`` Win32 API and pump
``WM_HOTKEY`` messages on a background thread. The thread emits a Qt signal
on each press, which Qt automatically marshals back onto the GUI thread.

On other platforms we don't try to register a global hotkey \u2014 the caller
should fall back to a per-window :class:`~PySide6.QtGui.QShortcut`.
"""

from __future__ import annotations

import platform
import sys
import threading
from typing import Optional

from PySide6.QtCore import QObject, Signal


# Win32 modifier flags
_MOD_ALT = 0x0001
_MOD_CONTROL = 0x0002
_MOD_SHIFT = 0x0004
_MOD_WIN = 0x0008
_WM_HOTKEY = 0x0312
_WM_QUIT = 0x0012
_HOTKEY_ID = 1

_MOD_LOOKUP = {
    "ctrl": _MOD_CONTROL,
    "control": _MOD_CONTROL,
    "shift": _MOD_SHIFT,
    "alt": _MOD_ALT,
    "win": _MOD_WIN,
    "super": _MOD_WIN,
}


def _parse_chord(chord: str) -> tuple[int, int]:
    """Convert e.g. ``"ctrl+shift+v"`` to ``(modifiers, virtual_key)``."""

    parts = [p.strip().lower() for p in chord.split("+") if p.strip()]
    if not parts:
        raise ValueError(f"Empty hotkey chord: {chord!r}")
    modifiers = 0
    key_part: Optional[str] = None
    for part in parts:
        if part in _MOD_LOOKUP:
            modifiers |= _MOD_LOOKUP[part]
        else:
            key_part = part
    if key_part is None:
        raise ValueError(f"Hotkey chord missing trigger key: {chord!r}")
    if len(key_part) == 1:
        vk = ord(key_part.upper())
    elif key_part.startswith("f") and key_part[1:].isdigit():
        # F1..F24 → VK_F1 (0x70) ..
        n = int(key_part[1:])
        vk = 0x70 + (n - 1)
    else:
        raise ValueError(f"Unsupported hotkey trigger: {key_part!r}")
    return modifiers, vk


class GlobalHotkey(QObject):
    """Cross-platform wrapper that registers a global hotkey when possible."""

    toggle_requested = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._thread: Optional[threading.Thread] = None
        self._thread_id: Optional[int] = None
        self._stopping = False

    def start(self, chord: str) -> bool:
        if platform.system() != "Windows":
            return False
        try:
            modifiers, vk = _parse_chord(chord)
        except ValueError:
            return False

        ready = threading.Event()
        success = {"ok": False}

        def runner() -> None:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            self._thread_id = kernel32.GetCurrentThreadId()
            registered = user32.RegisterHotKey(
                None, _HOTKEY_ID, modifiers, vk
            )
            success["ok"] = bool(registered)
            ready.set()
            if not registered:
                return

            try:
                msg = wintypes.MSG()
                while not self._stopping:
                    ret = user32.GetMessageW(
                        ctypes.byref(msg), None, 0, 0
                    )
                    if ret in (0, -1):
                        break
                    if msg.message == _WM_HOTKEY and msg.wParam == _HOTKEY_ID:
                        # Marshalled to GUI thread automatically because the
                        # signal is connected via Qt::AutoConnection.
                        self.toggle_requested.emit()
            finally:
                user32.UnregisterHotKey(None, _HOTKEY_ID)

        self._thread = threading.Thread(
            target=runner,
            name="GlobalHotkey",
            daemon=True,
        )
        self._thread.start()
        ready.wait(timeout=2.0)
        return bool(success["ok"])

    def stop(self) -> None:
        if self._thread is None or platform.system() != "Windows":
            return
        self._stopping = True
        try:
            import ctypes

            if self._thread_id is not None:
                ctypes.windll.user32.PostThreadMessageW(
                    self._thread_id, _WM_QUIT, 0, 0
                )
        except OSError:
            pass
        self._thread.join(timeout=1.0)
        self._thread = None
