"""Spawns and supervises the tracker subprocess.

The tracker is the existing ``main.py`` flow. We launch it without a console
window and pipe its stdout/stderr to the GUI so the Logs page can mirror what
the user used to see in the rich terminal output. Structured data (game
state, players, chat) is consumed through the websocket server that the
tracker exposes on the configured port.

We use :mod:`subprocess` (rather than ``QProcess``) because PySide6 does not
expose ``QProcess.setCreateProcessArgumentsModifier`` — that method only
exists in PyQt — and we still need ``CREATE_NO_WINDOW`` on Windows to avoid
a stray console window popping up next to the GUI.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import threading
from typing import List, Optional

from PySide6.QtCore import QObject, Signal


# Windows constant; harmless to define on other platforms.
CREATE_NO_WINDOW = 0x08000000


from src.gui.utils import repo_root


class TrackerRunner(QObject):
    """Owns the tracker subprocess and forwards its output as Qt signals."""

    output_received = Signal(str)
    started = Signal()
    stopped = Signal(int)
    error = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._process: Optional[subprocess.Popen[str]] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------ lifecycle
    def is_running(self) -> bool:
        proc = self._process
        return proc is not None and proc.poll() is None

    def start(self) -> bool:
        if self.is_running():
            return True

        program, arguments = self._build_command()
        if not program:
            self.error.emit(
                "Could not find main.py or vRY.exe next to the GUI."
            )
            return False

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"

        creationflags = 0
        startupinfo = None
        if platform.system() == "Windows":
            creationflags = CREATE_NO_WINDOW
            # Belt-and-suspenders: also hide the window via STARTUPINFO in
            # case the executable was built without the console subsystem
            # being suppressed.
            startupinfo = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]
            startupinfo.wShowWindow = 0  # SW_HIDE

        try:
            process = subprocess.Popen(
                [program, *arguments],
                cwd=repo_root(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                env=env,
                creationflags=creationflags,
                startupinfo=startupinfo,
                bufsize=1,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            self.error.emit(f"Failed to launch the tracker process: {exc}")
            return False

        self._process = process
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name="TrackerRunner-reader",
            daemon=True,
        )
        self._reader_thread.start()
        self.started.emit()
        return True

    def stop(self) -> None:
        proc = self._process
        if proc is None or proc.poll() is not None:
            return
        try:
            if platform.system() == "Windows":
                # ``proc.terminate()`` on Windows only kills the immediate
                # child. The tracker spawns its own helpers (riot client
                # callbacks, etc.) that would otherwise leak. Use taskkill
                # with /T to wipe out the whole tree.
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        creationflags=CREATE_NO_WINDOW,
                        capture_output=True,
                        timeout=3,
                    )
                except (OSError, subprocess.SubprocessError):
                    proc.terminate()
            else:
                proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
        except OSError as exc:
            self.error.emit(f"Failed to stop the tracker process: {exc}")
        finally:
            # Drop our handle so the next start() can spawn a fresh process
            # without reusing a zombie.
            self._process = None

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
    def _reader_loop(self) -> None:
        proc = self._process
        if proc is None or proc.stdout is None:
            return
        try:
            for line in iter(proc.stdout.readline, ""):
                if not line:
                    break
                # Qt queues signal delivery across threads automatically.
                self.output_received.emit(line)
        except Exception as exc:  # pragma: no cover - defensive
            self.error.emit(f"Tracker output stream failed: {exc}")
        finally:
            try:
                if proc.stdout is not None:
                    proc.stdout.close()
            except OSError:
                pass
            rc = proc.wait()
            with self._lock:
                if self._process is proc:
                    self._process = None
            self.stopped.emit(int(rc))
