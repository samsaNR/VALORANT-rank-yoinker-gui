"""Top-level window for the vRY GUI."""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.constants import version
from src.gui.config_io import load_config
from src.gui.pages.about import AboutPage
from src.gui.pages.accounts import AccountsPage
from src.gui.pages.configuration import ConfigurationPage
from src.gui.pages.logs import LogsPage
from src.gui.pages.tracker import TrackerPage
from src.gui.workers.tracker_client import TrackerClient
from src.gui.workers.tracker_runner import TrackerRunner


class MainWindow(QMainWindow):
    """Sidebar + stacked pages, plus the websocket / subprocess plumbing."""

    NAV_ITEMS = (
        ("Tracker", "tracker"),
        ("Configuration", "config"),
        ("Accounts", "accounts"),
        ("Logs", "logs"),
        ("About", "about"),
    )

    def __init__(self, icon_path: Optional[str] = None) -> None:
        super().__init__()
        self.setWindowTitle(f"vRY \u2014 VALORANT rank yoinker v{version}")
        self.resize(1180, 760)
        self.setMinimumSize(960, 600)
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        self._tracker_runner = TrackerRunner(self)
        self._tracker_client = TrackerClient(self)

        self._tracker_page = TrackerPage(
            on_start=self._on_start_tracker,
            on_stop=self._on_stop_tracker,
        )
        self._config_page = ConfigurationPage()
        self._accounts_page = AccountsPage()
        self._logs_page = LogsPage()
        self._about_page = AboutPage()

        self._page_widgets = {
            "tracker": self._tracker_page,
            "config": self._config_page,
            "accounts": self._accounts_page,
            "logs": self._logs_page,
            "about": self._about_page,
        }

        self._build_layout()
        self._wire_workers()

    # ----------------------------------------------------------- layout
    def _build_layout(self) -> None:
        central = QWidget()
        central.setObjectName("central")
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_sidebar())

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(28, 24, 28, 24)
        body_layout.setSpacing(16)

        self._stack = QStackedWidget()
        for _, key in self.NAV_ITEMS:
            self._stack.addWidget(self._page_widgets[key])
        body_layout.addWidget(self._stack, 1)

        layout.addWidget(body, 1)
        self.setCentralWidget(central)

        status = self.statusBar()
        status.setSizeGripEnabled(False)
        self._status_label = QLabel("Tracker idle")
        status.addWidget(self._status_label, 1)
        self._connection_label = QLabel("Disconnected")
        status.addPermanentWidget(self._connection_label)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 24, 20, 20)
        layout.setSpacing(4)

        title = QLabel("vRY")
        title.setObjectName("brandTitle")
        layout.addWidget(title)

        subtitle = QLabel(f"VALORANT rank yoinker\nv{version}")
        subtitle.setObjectName("brandSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(subtitle)
        layout.addSpacing(20)

        self._nav_buttons: List[QPushButton] = []
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)

        for index, (label, key) in enumerate(self.NAV_ITEMS):
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(
                lambda _checked=False, idx=index: self._show_page(idx)
            )
            self._nav_buttons.append(button)
            self._nav_group.addButton(button, index)
            layout.addWidget(button)

        self._nav_buttons[0].setChecked(True)
        layout.addStretch(1)

        footer = QLabel("Made for vRY by the community")
        footer.setObjectName("brandSubtitle")
        footer.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(footer)
        return sidebar

    # ----------------------------------------------------------- wiring
    def _wire_workers(self) -> None:
        self._tracker_runner.started.connect(self._on_runner_started)
        self._tracker_runner.stopped.connect(self._on_runner_stopped)
        self._tracker_runner.error.connect(self._on_runner_error)
        self._tracker_runner.output_received.connect(self._on_runner_output)

        self._tracker_client.connected.connect(self._on_client_connected)
        self._tracker_client.disconnected.connect(self._on_client_disconnected)
        self._tracker_client.heartbeat.connect(self._tracker_page.apply_heartbeat)
        self._tracker_client.chat_message.connect(self._tracker_page.append_chat)
        self._tracker_client.error.connect(self._on_client_error)

    # ------------------------------------------------------------ slots
    def _show_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)

    def _on_start_tracker(self) -> None:
        if self._tracker_runner.is_running():
            return
        if self._tracker_runner.start():
            self._tracker_page.set_tracker_running(True)
            self._status_label.setText("Tracker starting\u2026")

    def _on_stop_tracker(self) -> None:
        self._tracker_runner.stop()

    def _on_runner_started(self) -> None:
        self._status_label.setText("Tracker running")
        self._tracker_page.set_tracker_running(True)
        # Give the tracker a moment to bind its websocket port before we connect.
        port = int(load_config().get("port") or 1100)
        QTimer.singleShot(
            500,
            lambda: self._tracker_client.start("127.0.0.1", port),
        )

    def _on_runner_stopped(self, code: int) -> None:
        self._status_label.setText(
            f"Tracker stopped (exit code {code})"
        )
        self._tracker_page.set_tracker_running(False)
        self._tracker_client.stop()

    def _on_runner_error(self, message: str) -> None:
        QMessageBox.critical(self, "Tracker error", message)
        self._tracker_page.set_tracker_running(False)
        self._status_label.setText("Tracker error")

    def _on_runner_output(self, chunk: str) -> None:
        self._logs_page.append_chunk(chunk)

    def _on_client_connected(self) -> None:
        self._connection_label.setText("Connected")
        self._tracker_page.set_connected(True)

    def _on_client_disconnected(self) -> None:
        self._connection_label.setText("Disconnected")
        self._tracker_page.set_connected(False)

    def _on_client_error(self, message: str) -> None:
        # Keep noisy reconnect errors in the status bar only.
        self._connection_label.setText(f"WS: {message[:60]}")

    # ------------------------------------------------------------ window
    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._tracker_client.stop()
        if self._tracker_runner.is_running():
            self._tracker_runner.stop()
        super().closeEvent(event)
