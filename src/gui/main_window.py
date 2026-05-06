"""Top-level window for the vRY GUI."""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from src.constants import version
from src.gui.config_io import load_config
from src.gui.icons import svg_icon
from src.gui.pages.about import AboutPage
from src.gui.pages.accounts import AccountsPage
from src.gui.pages.configuration import ConfigurationPage
from src.gui.pages.history import HistoryPage
from src.gui.pages.loadouts import LoadoutsPage
from src.gui.pages.logs import LogsPage
from src.gui.pages.stats import StatsPage
from src.gui.pages.tracker import TrackerPage
from src.gui.stats_repo import StatsRepository
from src.gui.workers.asset_registry import AssetRegistry
from src.gui.workers.global_hotkey import GlobalHotkey
from src.gui.workers.image_cache import ImageCache
from src.gui.workers.notifier import SoundNotifier
from src.gui.workers.tracker_client import TrackerClient
from src.gui.workers.tracker_runner import TrackerRunner


class MainWindow(QMainWindow):
    """Sidebar + stacked pages, plus the websocket / subprocess plumbing."""

    NAV_ITEMS = (
        ("Tracker", "tracker", "tracker"),
        ("Loadouts", "loadouts", "loadouts"),
        ("History", "history", "history"),
        ("Stats", "stats", "stats"),
        ("Configuration", "config", "config"),
        ("Accounts", "accounts", "accounts"),
        ("Logs", "logs", "logs"),
        ("About", "about", "about"),
    )

    # Where the sidebar inserts a thin divider/section header.
    SIDEBAR_SECTIONS = (
        (0, "Live"),
        (4, "Settings"),
    )

    def __init__(self, icon_path: Optional[str] = None) -> None:
        super().__init__()
        self.setWindowTitle(f"vRY \u2014 VALORANT rank yoinker v{version}")
        self.resize(1180, 760)
        self.setMinimumSize(960, 600)
        self._icon = QIcon(icon_path) if icon_path else QIcon()
        if icon_path:
            self.setWindowIcon(self._icon)

        self._tracker_runner = TrackerRunner(self)
        self._tracker_client = TrackerClient(self)
        self._image_cache = ImageCache(self)
        self._asset_registry = AssetRegistry(self)
        self._sound_notifier = SoundNotifier(self)
        self._stats_repo = StatsRepository()
        self._tray: Optional[QSystemTrayIcon] = None
        self._hotkey: Optional[GlobalHotkey] = None
        self._force_quit = False
        self._sidebar_collapsed = False

        self._tracker_page = TrackerPage(
            on_start=self._on_start_tracker,
            on_stop=self._on_stop_tracker,
            image_cache=self._image_cache,
            stats_repo=self._stats_repo,
            asset_registry=self._asset_registry,
        )
        self._loadouts_page = LoadoutsPage(
            image_cache=self._image_cache,
            asset_registry=self._asset_registry,
        )
        self._history_page = HistoryPage(stats_repo=self._stats_repo)
        self._stats_page = StatsPage(stats_repo=self._stats_repo)
        self._config_page = ConfigurationPage()
        self._accounts_page = AccountsPage()
        self._logs_page = LogsPage()
        self._about_page = AboutPage()

        self._page_widgets = {
            "tracker": self._tracker_page,
            "loadouts": self._loadouts_page,
            "history": self._history_page,
            "stats": self._stats_page,
            "config": self._config_page,
            "accounts": self._accounts_page,
            "logs": self._logs_page,
            "about": self._about_page,
        }

        self._build_layout()
        self._wire_workers()
        self._setup_tray()
        self._setup_hotkey()
        # Pull agent / rank / skin metadata from valorant-api in the background.
        self._asset_registry.start()

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
        for _label, key, _icon in self.NAV_ITEMS:
            self._stack.addWidget(self._page_widgets[key])
        body_layout.addWidget(self._stack, 1)

        layout.addWidget(body, 1)
        self.setCentralWidget(central)

        status = self.statusBar()
        status.setSizeGripEnabled(False)
        self._status_label = QLabel("Tracker idle")
        status.addWidget(self._status_label, 1)
        self._connection_label = QLabel("Offline")
        self._connection_label.setObjectName("connectionPill")
        self._connection_label.setProperty("connected", "false")
        status.addPermanentWidget(self._connection_label)

    SIDEBAR_WIDTH_FULL = 232
    SIDEBAR_WIDTH_COLLAPSED = 64

    def _build_sidebar(self) -> QFrame:
        from PySide6.QtCore import QSize

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(self.SIDEBAR_WIDTH_FULL)
        self._sidebar = sidebar

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 16, 0, 18)
        layout.setSpacing(2)

        # Brand block + collapse toggle on the right.
        header_row = QHBoxLayout()
        header_row.setContentsMargins(20, 0, 12, 14)
        header_row.setSpacing(8)
        brand_box = QVBoxLayout()
        brand_box.setContentsMargins(0, 0, 0, 0)
        brand_box.setSpacing(2)
        title = QLabel("vRY")
        title.setObjectName("brandTitle")
        brand_box.addWidget(title)
        subtitle = QLabel("VALORANT rank yoinker")
        subtitle.setObjectName("brandSubtitle")
        brand_box.addWidget(subtitle)
        self._sidebar_brand_widgets: List[QLabel] = [title, subtitle]
        header_row.addLayout(brand_box, 1)

        toggle = QPushButton()
        toggle.setObjectName("sidebarToggle")
        toggle.setIcon(svg_icon("chevron_left", color="#aab5c5"))
        toggle.setIconSize(QSize(18, 18))
        toggle.setFixedSize(28, 28)
        toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle.setToolTip("Collapse sidebar")
        toggle.clicked.connect(self._toggle_sidebar)
        self._sidebar_toggle = toggle
        header_row.addWidget(toggle, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header_row)

        self._nav_buttons: List[QPushButton] = []
        self._nav_button_labels: List[str] = []
        self._sidebar_section_labels: List[QLabel] = []
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)

        section_starts = dict(self.SIDEBAR_SECTIONS)

        for index, (label, key, icon_name) in enumerate(self.NAV_ITEMS):
            if index in section_starts:
                if index > 0:
                    layout.addSpacing(10)
                section_label = QLabel(section_starts[index])
                section_label.setObjectName("sidebarSection")
                self._sidebar_section_labels.append(section_label)
                layout.addWidget(section_label)
            button = QPushButton(" " + label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setIcon(svg_icon(icon_name, color="#aab5c5"))
            button.setIconSize(QSize(18, 18))
            button.setToolTip(label)
            button.clicked.connect(
                lambda _checked=False, idx=index: self._show_page(idx)
            )
            self._nav_buttons.append(button)
            self._nav_button_labels.append(label)
            self._nav_group.addButton(button, index)
            layout.addWidget(button)

        self._nav_buttons[0].setChecked(True)
        layout.addStretch(1)

        # Author credit + version footer (collapses with the sidebar).
        credit_label = QLabel(
            "made by <a href=\"https://t.me/rinonrc\" "
            "style=\"color:#ff4655;text-decoration:none;\">@rinonrc</a>"
        )
        credit_label.setObjectName("sidebarCredit")
        credit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credit_label.setOpenExternalLinks(True)
        credit_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(credit_label)
        self._sidebar_credit = credit_label

        version_label = QLabel(f"v{version}")
        version_label.setObjectName("sidebarVersion")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)
        self._sidebar_version = version_label
        return sidebar

    def _toggle_sidebar(self) -> None:
        self._sidebar_collapsed = not self._sidebar_collapsed
        self._sidebar.setFixedWidth(
            self.SIDEBAR_WIDTH_COLLAPSED
            if self._sidebar_collapsed
            else self.SIDEBAR_WIDTH_FULL
        )
        # Hide the text labels but keep the icons.
        for label in self._sidebar_brand_widgets:
            label.setVisible(not self._sidebar_collapsed)
        for label in self._sidebar_section_labels:
            label.setVisible(not self._sidebar_collapsed)
        self._sidebar_credit.setVisible(not self._sidebar_collapsed)
        self._sidebar_version.setVisible(not self._sidebar_collapsed)
        for button, label in zip(self._nav_buttons, self._nav_button_labels):
            button.setText("" if self._sidebar_collapsed else " " + label)
        self._sidebar_toggle.setIcon(
            svg_icon(
                "chevron_right" if self._sidebar_collapsed else "chevron_left",
                color="#aab5c5",
            )
        )
        self._sidebar_toggle.setToolTip(
            "Expand sidebar" if self._sidebar_collapsed else "Collapse sidebar"
        )

    # ----------------------------------------------------------- wiring
    def _wire_workers(self) -> None:
        self._tracker_runner.started.connect(self._on_runner_started)
        self._tracker_runner.stopped.connect(self._on_runner_stopped)
        self._tracker_runner.error.connect(self._on_runner_error)
        self._tracker_runner.output_received.connect(self._on_runner_output)

        self._tracker_client.connected.connect(self._on_client_connected)
        self._tracker_client.disconnected.connect(self._on_client_disconnected)
        self._tracker_client.heartbeat.connect(self._tracker_page.apply_heartbeat)
        self._tracker_client.heartbeat.connect(self._on_heartbeat)
        self._tracker_client.chat_message.connect(self._tracker_page.append_chat)
        self._tracker_client.match_loadout.connect(
            self._loadouts_page.apply_match_loadout
        )
        self._tracker_client.error.connect(self._on_client_error)

        # Right-click → "View loadout" on a player row jumps to the
        # Loadouts page and highlights that player's card.
        self._tracker_page.view_loadout_requested.connect(
            self._on_view_loadout_requested
        )

    # ------------------------------------------------------------ slots
    def _show_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        # Refresh stats-backed pages whenever the user lands on them so the
        # latest finished match shows up without restarting the GUI.
        widget = self._stack.widget(index)
        if widget is self._history_page:
            self._history_page.refresh()
        elif widget is self._stats_page:
            self._stats_page.refresh()

    def _on_view_loadout_requested(self, puuid: str) -> None:
        """Switch to the Loadouts page and pulse the requested card."""

        # Find the index of the loadouts page in NAV_ITEMS so we don't
        # hard-code it.
        for index, (_label, key, _icon) in enumerate(self.NAV_ITEMS):
            if key == "loadouts":
                self._show_page(index)
                # Sync the sidebar selection too.
                if 0 <= index < len(self._nav_buttons):
                    self._nav_buttons[index].setChecked(True)
                break
        self._loadouts_page.focus_player(puuid)

    def _on_heartbeat(self, payload: dict) -> None:
        own = str(payload.get("puuid") or "").strip()
        # Always run through the sound notifier so match start / end chimes
        # fire even if the heartbeat carries no own-puuid yet (e.g. early
        # MENUS payload).
        state = str(payload.get("state") or "").strip()
        if state:
            self._sound_notifier.update_state(state)
        if not own:
            return
        self._history_page.set_own_puuid(own)
        self._stats_page.set_own_puuid(own)
        self._loadouts_page.set_own_puuid(own)

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
        self._connection_label.setText("Live")
        self._connection_label.setProperty("connected", "true")
        self._connection_label.style().unpolish(self._connection_label)
        self._connection_label.style().polish(self._connection_label)
        self._tracker_page.set_connected(True)

    def _on_client_disconnected(self) -> None:
        self._connection_label.setText("Offline")
        self._connection_label.setProperty("connected", "false")
        self._connection_label.style().unpolish(self._connection_label)
        self._connection_label.style().polish(self._connection_label)
        self._tracker_page.set_connected(False)

    def _on_client_error(self, message: str) -> None:
        # Keep noisy reconnect errors in the status bar only.
        self._connection_label.setText(f"WS: {message[:48]}")
        self._connection_label.setProperty("connected", "false")
        self._connection_label.style().unpolish(self._connection_label)
        self._connection_label.style().polish(self._connection_label)

    # -------------------------------------------------------- tray / hotkey
    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self._tray = QSystemTrayIcon(self._icon, self)
        self._tray.setToolTip("vRY — VALORANT rank yoinker")
        menu = QMenu(self)
        show_action = QAction("Show vRY", self)
        show_action.triggered.connect(self._show_from_tray)
        menu.addAction(show_action)
        hide_action = QAction("Hide window", self)
        hide_action.triggered.connect(self.hide)
        menu.addAction(hide_action)
        menu.addSeparator()
        quit_action = QAction("Quit vRY", self)
        quit_action.triggered.connect(self._quit_from_tray)
        menu.addAction(quit_action)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _setup_hotkey(self) -> None:
        # Global, system-wide hotkey to toggle the window. Only activates on
        # Windows where ``RegisterHotKey`` is available; on Linux/macOS the
        # GlobalHotkey class no-ops and we fall back to a window-local
        # ``QShortcut`` so the same chord still works when vRY has focus.
        self._hotkey = GlobalHotkey(self)
        self._hotkey.toggle_requested.connect(self._toggle_window)
        ok = self._hotkey.start("ctrl+shift+v")
        if not ok:
            shortcut = QShortcut(QKeySequence("Ctrl+Shift+V"), self)
            shortcut.activated.connect(self._toggle_window)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._show_from_tray()

    def _show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit_from_tray(self) -> None:
        self._force_quit = True
        self.close()

    def _toggle_window(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self._show_from_tray()

    # ------------------------------------------------------------ window
    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        # The X button fully quits the app; users that want to keep it
        # running in the background can use the tray icon's "Hide window"
        # entry or the Ctrl+Shift+V hotkey instead. Without this, the
        # program looked closed but kept living in the system tray and in
        # the process list.
        if self._hotkey is not None:
            try:
                self._hotkey.stop()
            except Exception:  # noqa: BLE001
                pass
        try:
            self._tracker_client.stop()
        except Exception:  # noqa: BLE001
            pass
        if self._tracker_runner.is_running():
            try:
                self._tracker_runner.stop()
            except Exception:  # noqa: BLE001
                pass
        if self._tray is not None:
            try:
                self._tray.hide()
            except Exception:  # noqa: BLE001
                pass
            self._tray = None
        super().closeEvent(event)
        # Force the Qt event loop to quit even if some lingering object
        # (e.g. a hidden tray icon on platforms where it counts as a
        # top-level window) keeps the application alive.
        from PySide6.QtWidgets import QApplication

        QApplication.quit()
