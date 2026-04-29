"""Spawns and supervises the tracker subprocess.

The tracker is the existing ``main.py`` flow. We launch it without a console
window and pipe its stdout/stderr to the GUI so the Logs page can mirror what
the user used to see in the rich terminal output. Structured data (game
state, players, chat) is consumed through the websocket server that the
tracker exposes on the configured port.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from typing import List, Optional

from PySide6.QtCore import QObject, QProcess, Signal

from src.gui.utils import repo_root


class TrackerRunner(QObject):
    """Owns the tracker subprocess and forwards its output as Qt signals."""

    output_received = Signal(str)
    started = Signal()
    stopped = Signal(int)
    error = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._process: Optional[QProcess] = None

    # ------------------------------------------------------------ lifecycle
    def is_running(self) -> bool:
        return (
            self._process is not None
            and self._process.state() != QProcess.ProcessState.NotRunning
        )

    def start(self) -> bool:
        if self.is_running():
            return True

        program, arguments = self._build_command()
        if not program:
            self.error.emit(
                "Could not find main.py or vRY.exe next to the GUI."
            )
            return False

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.setWorkingDirectory(repo_root())
        env = process.processEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("PYTHONUNBUFFERED", "1")
        process.setProcessEnvironment(env)

        process.readyReadStandardOutput.connect(self._on_stdout)
        process.errorOccurred.connect(self._on_error)
        process.finished.connect(self._on_finished)

        if platform.system() == "Windows":
            # Hide the spawned console window — the GUI is the front-end.
            process.setCreateProcessArgumentsModifier(_hide_console_modifier)

        process.start(program, arguments)
        if not process.waitForStarted(3000):
            self.error.emit("Failed to launch the tracker process.")
            return False

        self._process = process
        self.started.emit()
        return True

    def stop(self) -> None:
        if not self.is_running() or self._process is None:
            return
        self._process.terminate()
        if not self._process.waitForFinished(3000):
            self._process.kill()
            self._process.waitForFinished(2000)

    # -------------------------------------------------------------- helpers
    def _build_command(self) -> tuple[Optional[str], List[str]]:
        root = repo_root()
        exe_candidates = ("vry.exe", "VALORANT rank yoinker.exe")
        for name in exe_candidates:
            path = os.path.join(root, name)
            if os.path.exists(path):
                return path, []

        main_py = os.path.join(root, "main.py")
        if os.path.exists(main_py):
            return sys.executable, [main_py]
        return None, []

    # ---------------------------------------------------------------- slots
    def _on_stdout(self) -> None:
        if self._process is None:
            return
        data = bytes(self._process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        if data:
            self.output_received.emit(data)

    def _on_error(self, _err: QProcess.ProcessError) -> None:
        if self._process is None:
            return
        self.error.emit(self._process.errorString())

    def _on_finished(self, code: int, _status: QProcess.ExitStatus) -> None:
        self.stopped.emit(int(code))
        self._process = None


def _hide_console_modifier(args):  # pragma: no cover - Windows only
    """QProcess hook to mark the child as a hidden window on Windows."""
    args["flags"] |= 0x08000000  # CREATE_NO_WINDOW
    return args
