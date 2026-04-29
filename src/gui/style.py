"""Qt stylesheet for the vRY GUI.

The palette is inspired by VALORANT's UI (deep navy + ``#ff4655`` accent) and
is applied as a global stylesheet so widgets get a consistent look without
per-widget styling.
"""

# Core palette
BG = "#0f1419"
PANEL = "#181c24"
PANEL_ALT = "#202632"
BORDER = "#2a3140"
TEXT = "#ece8e1"
MUTED = "#8b95a3"
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
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}}

QMainWindow, QWidget#central {{
    background-color: {BG};
}}

QFrame#sidebar {{
    background-color: {PANEL};
    border-right: 1px solid {BORDER};
}}

QLabel#brandTitle {{
    color: {TEXT};
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 1px;
}}

QLabel#brandSubtitle {{
    color: {MUTED};
    font-size: 11px;
}}

QLabel#pageTitle {{
    color: {TEXT};
    font-size: 22px;
    font-weight: 700;
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
    letter-spacing: 1px;
}}

QLabel.muted, QLabel[muted="true"] {{
    color: {MUTED};
}}

QPushButton#navButton {{
    background: transparent;
    border: none;
    color: {MUTED};
    text-align: left;
    padding: 10px 16px;
    border-left: 3px solid transparent;
    font-size: 13px;
    font-weight: 600;
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
    border-radius: 4px;
    padding: 8px 16px;
    color: {TEXT};
}}

QPushButton:hover {{
    background-color: #283040;
    border-color: #3a4356;
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
    font-weight: 700;
    padding: 10px 22px;
    border-radius: 4px;
}}

QPushButton#primary:hover {{
    background-color: {ACCENT_HOVER};
}}

QPushButton#primary:pressed {{
    background-color: {ACCENT_PRESSED};
}}

QPushButton#danger {{
    background-color: transparent;
    border: 1px solid {ACCENT};
    color: {ACCENT};
}}

QPushButton#danger:hover {{
    background-color: {ACCENT};
    color: white;
}}

QFrame#card {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 6px;
}}

QFrame#statBadge {{
    background-color: {PANEL_ALT};
    border-radius: 4px;
}}

QLabel#statePill {{
    background-color: {PANEL_ALT};
    color: {TEXT};
    border-radius: 12px;
    padding: 4px 12px;
    font-weight: 600;
    font-size: 11px;
    letter-spacing: 1px;
}}

QLabel#statePill[gameState="MENUS"] {{ background-color: #2a3140; color: {MUTED}; }}
QLabel#statePill[gameState="PREGAME"] {{ background-color: {WARNING}; color: #1a1a1a; }}
QLabel#statePill[gameState="INGAME"] {{ background-color: {SUCCESS}; color: #0d2a14; }}
QLabel#statePill[gameState="DISCONNECTED"] {{ background-color: {ACCENT}; color: white; }}

QTableView, QListView, QListWidget, QTreeView, QAbstractItemView {{
    background-color: {PANEL};
    alternate-background-color: #1d222b;
    gridline-color: {BORDER};
    border: 1px solid {BORDER};
    border-radius: 6px;
    selection-background-color: {ACCENT};
    selection-color: white;
    color: {TEXT};
    outline: 0;
}}

QTableView::item, QListView::item, QListWidget::item {{
    padding: 6px 8px;
}}

QTableView::item:selected, QListView::item:selected, QListWidget::item:selected {{
    background-color: {ACCENT};
    color: white;
}}

QHeaderView::section {{
    background-color: {PANEL_ALT};
    color: {MUTED};
    border: none;
    padding: 8px 10px;
    font-weight: 700;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 1px;
    border-bottom: 1px solid {BORDER};
}}

QTableView::item {{
    padding: 6px 10px;
    border: none;
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    background-color: {PANEL};
    border-radius: 6px;
    top: -1px;
}}

QTabBar::tab {{
    background-color: {PANEL_ALT};
    color: {MUTED};
    padding: 8px 18px;
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
    font-weight: 600;
}}

QTabBar::tab:selected {{
    background-color: {PANEL};
    color: {TEXT};
    border-color: {BORDER};
}}

QLineEdit, QSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background-color: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 8px;
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
    width: 10px;
    margin: 4px 2px;
}}

QScrollBar::handle:vertical {{
    background: {BORDER};
    min-height: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: #3a4356;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px 4px;
}}

QScrollBar::handle:horizontal {{
    background: {BORDER};
    min-width: 24px;
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
    border: 1px solid {BORDER};
    padding: 4px 8px;
}}

QFrame#playerLoadoutCard {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
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
    font-size: 15px;
    font-weight: 700;
}}

QLabel#playerAvatar {{
    background-color: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 6px;
}}

QFrame#skinTile {{
    background-color: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 4px;
}}

QLabel#skinTileIcon {{
    background-color: #11151c;
    border-radius: 3px;
}}
"""
