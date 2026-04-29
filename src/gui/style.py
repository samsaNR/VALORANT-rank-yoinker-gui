"""Qt stylesheet for the vRY GUI.

The palette is inspired by VALORANT's UI (deep navy + ``#ff4655`` accent) and
is applied as a global stylesheet so widgets get a consistent look without
per-widget styling.
"""

# Core palette
BG = "#0b0f15"
BG_ALT = "#11161f"
PANEL = "#161b25"
PANEL_ALT = "#1c2230"
PANEL_HIGHLIGHT = "#222a3a"
BORDER = "#2a3242"
BORDER_STRONG = "#384258"
TEXT = "#ece8e1"
MUTED = "#8b95a3"
MUTED_STRONG = "#aab5c5"
ACCENT = "#ff4655"
ACCENT_HOVER = "#ff6171"
ACCENT_PRESSED = "#e03b48"
SUCCESS = "#5fcf80"
WARNING = "#f0b429"
TEAM_BLUE = "#3a8bd1"
TEAM_RED = "#d14a4a"

QSS = f"""
* {{
    color: {TEXT};
    font-family: "Inter", "Segoe UI", "SF Pro Text", "Helvetica Neue", sans-serif;
    font-size: 13px;
}}

QMainWindow, QWidget#central {{
    background-color: {BG};
}}

QWidget#central {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {BG_ALT},
        stop:1 {BG}
    );
}}

QFrame#sidebar {{
    background-color: {PANEL};
    border-right: 1px solid {BORDER};
}}

QLabel#brandTitle {{
    color: {TEXT};
    font-size: 18px;
    font-weight: 800;
    letter-spacing: 2px;
}}

QLabel#brandSubtitle {{
    color: {MUTED};
    font-size: 11px;
    letter-spacing: 0.5px;
}}

QLabel#sidebarSection {{
    color: {MUTED};
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    font-weight: 700;
    padding: 8px 18px 4px 18px;
}}

QLabel#sidebarVersion {{
    color: {MUTED};
    font-size: 10px;
    letter-spacing: 0.5px;
}}

QLabel#pageTitle {{
    color: {TEXT};
    font-size: 24px;
    font-weight: 800;
    letter-spacing: 0.5px;
}}

QLabel#pageSubtitle {{
    color: {MUTED};
    font-size: 13px;
}}

QLabel#statValue {{
    color: {TEXT};
    font-size: 18px;
    font-weight: 700;
}}

QLabel#statLabel {{
    color: {MUTED};
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    font-weight: 600;
}}

QLabel.muted, QLabel[muted="true"] {{
    color: {MUTED};
}}

QPushButton#navButton {{
    background: transparent;
    border: none;
    color: {MUTED};
    text-align: left;
    padding: 9px 16px 9px 14px;
    border-left: 3px solid transparent;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.3px;
}}

QPushButton#navButton:hover {{
    background-color: {PANEL_ALT};
    color: {TEXT};
}}

QPushButton#navButton:checked {{
    background-color: {PANEL_ALT};
    color: {TEXT};
    border-left: 3px solid {ACCENT};
}}

QPushButton {{
    background-color: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 16px;
    color: {TEXT};
    font-weight: 600;
}}

QPushButton:hover {{
    background-color: {PANEL_HIGHLIGHT};
    border-color: {BORDER_STRONG};
}}

QPushButton:pressed {{
    background-color: #1c2230;
}}

QPushButton:disabled {{
    color: {MUTED};
    background-color: {PANEL};
}}

QPushButton#primary {{
    background-color: {ACCENT};
    border: none;
    color: white;
    font-weight: 800;
    padding: 11px 24px;
    border-radius: 6px;
    letter-spacing: 0.5px;
    font-size: 13px;
}}

QPushButton#primary:hover {{
    background-color: {ACCENT_HOVER};
}}

QPushButton#primary:pressed {{
    background-color: {ACCENT_PRESSED};
}}

QPushButton#primary:disabled {{
    background-color: {PANEL_ALT};
    color: {MUTED};
}}

QPushButton#danger {{
    background-color: transparent;
    border: 1px solid {ACCENT};
    color: {ACCENT};
    font-weight: 700;
    padding: 11px 24px;
    border-radius: 6px;
    letter-spacing: 0.5px;
}}

QPushButton#danger:hover {{
    background-color: {ACCENT};
    color: white;
}}

QFrame#card {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

QFrame#statusCard {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}

QFrame#teamSection {{
    background: transparent;
    border: none;
}}

QLabel#teamSectionTitle {{
    font-size: 13px;
    font-weight: 800;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    padding: 4px 0px 6px 8px;
    border-bottom: 2px solid {BORDER};
}}

QLabel#teamSectionTitle[team="Blue"] {{
    color: {TEAM_BLUE};
    border-bottom-color: {TEAM_BLUE};
}}

QLabel#teamSectionTitle[team="Red"] {{
    color: {TEAM_RED};
    border-bottom-color: {TEAM_RED};
}}

QLabel#teamSectionTitle[team="Yellow"] {{
    color: {WARNING};
    border-bottom-color: {WARNING};
}}

QFrame#statBadge {{
    background-color: {PANEL_ALT};
    border-radius: 6px;
}}

QLabel#statePill {{
    background-color: {PANEL_ALT};
    color: {TEXT};
    border-radius: 14px;
    padding: 6px 16px;
    font-weight: 800;
    font-size: 11px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}}

QLabel#statePill[gameState="MENUS"] {{ background-color: #2a3140; color: {MUTED_STRONG}; }}
QLabel#statePill[gameState="PREGAME"] {{ background-color: {WARNING}; color: #1a1a1a; }}
QLabel#statePill[gameState="INGAME"] {{ background-color: {SUCCESS}; color: #0d2a14; }}
QLabel#statePill[gameState="DISCONNECTED"] {{ background-color: {ACCENT}; color: white; }}

QLabel#connectionPill {{
    border-radius: 10px;
    padding: 4px 12px;
    font-weight: 700;
    font-size: 10px;
    letter-spacing: 1.2px;
    text-transform: uppercase;
}}

QLabel#connectionPill[connected="true"] {{
    background-color: rgba(95, 207, 128, 30);
    color: {SUCCESS};
}}

QLabel#connectionPill[connected="false"] {{
    background-color: rgba(255, 70, 85, 26);
    color: {ACCENT};
}}

QTableView, QListView, QListWidget, QTreeView, QAbstractItemView {{
    background-color: {PANEL};
    alternate-background-color: #1a1f29;
    gridline-color: {BORDER};
    border: 1px solid {BORDER};
    border-radius: 8px;
    selection-background-color: rgba(255, 70, 85, 70);
    selection-color: white;
    color: {TEXT};
    outline: 0;
}}

QTableView::item, QListView::item, QListWidget::item {{
    padding: 6px 8px;
}}

QTableView::item:selected, QListView::item:selected, QListWidget::item:selected {{
    background-color: rgba(255, 70, 85, 70);
    color: white;
}}

QHeaderView::section {{
    background-color: {PANEL_ALT};
    color: {MUTED};
    border: none;
    padding: 9px 10px;
    font-weight: 800;
    text-transform: uppercase;
    font-size: 10px;
    letter-spacing: 1.4px;
    border-bottom: 1px solid {BORDER};
}}

QTableView::item {{
    padding: 6px 10px;
    border: none;
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    background-color: {PANEL};
    border-radius: 8px;
    top: -1px;
}}

QTabBar::tab {{
    background-color: {PANEL_ALT};
    color: {MUTED};
    padding: 9px 20px;
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    font-weight: 700;
}}

QTabBar::tab:selected {{
    background-color: {PANEL};
    color: {TEXT};
    border-color: {BORDER};
}}

QLineEdit, QSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background-color: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 10px;
    color: {TEXT};
    selection-background-color: {ACCENT};
}}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus,
QPlainTextEdit:focus, QTextEdit:focus {{
    border-color: {ACCENT};
}}

QComboBox::drop-down {{
    border: none;
    width: 22px;
}}

QComboBox QAbstractItemView {{
    background-color: {PANEL};
    color: {TEXT};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
    selection-color: white;
}}

QCheckBox {{
    spacing: 8px;
    color: {TEXT};
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {BORDER};
    border-radius: 3px;
    background-color: {PANEL_ALT};
}}

QCheckBox::indicator:hover {{
    border-color: {ACCENT};
}}

QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    image: none;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 4px 2px;
}}

QScrollBar::handle:vertical {{
    background: {BORDER_STRONG};
    min-height: 32px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: #4a5570;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 2px 4px;
}}

QScrollBar::handle:horizontal {{
    background: {BORDER_STRONG};
    min-width: 32px;
    border-radius: 4px;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

QStatusBar {{
    background-color: {PANEL};
    color: {MUTED};
    border-top: 1px solid {BORDER};
}}

QToolTip {{
    background-color: {PANEL_ALT};
    color: {TEXT};
    border: 1px solid {BORDER_STRONG};
    border-radius: 4px;
    padding: 6px 10px;
}}

QFrame#playerLoadoutCard {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}

QFrame#playerLoadoutCard:hover {{
    border-color: {BORDER_STRONG};
}}

QFrame#playerLoadoutCard[team="Blue"] {{
    border-left: 3px solid {TEAM_BLUE};
}}

QFrame#playerLoadoutCard[team="Red"] {{
    border-left: 3px solid {TEAM_RED};
}}

QFrame#playerLoadoutCard[team="Yellow"] {{
    border-left: 3px solid {WARNING};
}}

QLabel#playerName {{
    color: {TEXT};
    font-size: 16px;
    font-weight: 800;
    letter-spacing: 0.3px;
}}

QLabel#playerAvatar {{
    background-color: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

QFrame#skinTile {{
    background-color: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 6px;
}}

QFrame#skinTile:hover {{
    border-color: {BORDER_STRONG};
    background-color: {PANEL_HIGHLIGHT};
}}

QLabel#skinTileIcon {{
    background-color: #0a0d12;
    border-radius: 4px;
}}

QLabel#emptyTitle {{
    color: {MUTED_STRONG};
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 0.5px;
}}

QLabel#emptySubtitle {{
    color: {MUTED};
    font-size: 12px;
}}

QFrame#chatBubble {{
    background-color: {PANEL_ALT};
    border-radius: 10px;
    padding: 8px 12px;
}}

QScrollArea, QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}

QLabel#chatChannel {{
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 1.3px;
    text-transform: uppercase;
    padding: 2px 8px;
    border-radius: 8px;
    background-color: {BORDER};
    color: {MUTED_STRONG};
}}

QLabel#chatChannel[channel="party"] {{
    background-color: rgba(95, 207, 128, 36);
    color: {SUCCESS};
}}

QLabel#chatChannel[channel="team"] {{
    background-color: rgba(58, 139, 209, 40);
    color: {TEAM_BLUE};
}}

QLabel#chatChannel[channel="all"] {{
    background-color: rgba(240, 180, 41, 40);
    color: {WARNING};
}}

QLabel#chatTimestamp {{
    color: {MUTED};
    font-size: 10px;
}}

QLabel#chatAuthor {{
    font-weight: 800;
    color: {TEXT};
}}

QLabel#chatBody {{
    color: {MUTED_STRONG};
}}
"""
