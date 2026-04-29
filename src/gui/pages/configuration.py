"""Configuration page \u2014 mirrors ``src/questions.py``."""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.constants import DEFAULT_CONFIG, WEAPONS
from src.gui.config_io import load_config, save_config
from src.gui.pages._common import page_header
from src.questions import FLAGS_OPTS, TABLE_OPTS


class ConfigurationPage(QWidget):
    """Editor for ``config.json`` exposed in the main window."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config: Dict[str, Any] = load_config()
        self._table_checks: Dict[str, QCheckBox] = {}
        self._flag_checks: Dict[str, QCheckBox] = {}

        self._build_layout()
        self._populate_from_config()

    # ------------------------------------------------------------ layout
    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        layout.addWidget(
            page_header(
                "Configuration",
                "Tweak the same options the CLI configurator exposes \u2014 changes are written to config.json.",
            )
        )

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._build_table_tab(), "Table columns")
        tabs.addTab(self._build_flags_tab(), "Feature flags")
        layout.addWidget(tabs, 1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)

        self._reset_btn = QPushButton("Reset")
        self._reset_btn.setToolTip("Reload config.json and discard unsaved edits.")
        self._reset_btn.clicked.connect(self._on_reset)
        button_row.addWidget(self._reset_btn)

        self._save_btn = QPushButton("Save")
        self._save_btn.setObjectName("primary")
        self._save_btn.clicked.connect(self._on_save)
        button_row.addWidget(self._save_btn)

        layout.addLayout(button_row)

    def _build_general_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setHorizontalSpacing(20)
        form.setVerticalSpacing(12)

        self._weapon_box = QComboBox()
        self._weapon_box.addItems(WEAPONS)
        form.addRow("Weapon", self._weapon_box)

        self._port_spin = QSpinBox()
        self._port_spin.setRange(1, 65535)
        form.addRow("Server port", self._port_spin)

        self._cooldown_spin = QSpinBox()
        self._cooldown_spin.setRange(1, 600)
        self._cooldown_spin.setSuffix(" s")
        form.addRow("Cooldown", self._cooldown_spin)

        self._chat_spin = QSpinBox()
        self._chat_spin.setRange(0, 100)
        form.addRow("Chat history length", self._chat_spin)

        return widget

    def _build_table_tab(self) -> QWidget:
        widget = QWidget()
        grid = QGridLayout(widget)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(8)

        intro = QLabel("Pick which columns appear in the live tracker table.")
        intro.setProperty("muted", True)
        grid.addWidget(intro, 0, 0, 1, 2)

        for index, (key, label) in enumerate(TABLE_OPTS.items()):
            checkbox = QCheckBox(label)
            self._table_checks[key] = checkbox
            grid.addWidget(checkbox, 1 + index // 2, index % 2)

        grid.setRowStretch(grid.rowCount(), 1)
        return widget

    def _build_flags_tab(self) -> QWidget:
        widget = QWidget()
        grid = QGridLayout(widget)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(8)

        intro = QLabel("Toggle optional behaviour.")
        intro.setProperty("muted", True)
        grid.addWidget(intro, 0, 0, 1, 2)

        for index, (key, label) in enumerate(FLAGS_OPTS.items()):
            checkbox = QCheckBox(label)
            self._flag_checks[key] = checkbox
            grid.addWidget(checkbox, 1 + index // 2, index % 2)

        grid.setRowStretch(grid.rowCount(), 1)
        return widget

    # ----------------------------------------------------------- helpers
    def _populate_from_config(self) -> None:
        weapon = self._config.get("weapon", DEFAULT_CONFIG["weapon"])
        if weapon in WEAPONS:
            self._weapon_box.setCurrentText(weapon)
        else:
            self._weapon_box.setCurrentText(DEFAULT_CONFIG["weapon"])

        self._port_spin.setValue(int(self._config.get("port", DEFAULT_CONFIG["port"])))
        self._cooldown_spin.setValue(
            int(self._config.get("cooldown", DEFAULT_CONFIG["cooldown"]))
        )
        self._chat_spin.setValue(
            int(self._config.get("chat_limit", DEFAULT_CONFIG["chat_limit"]))
        )

        table_cfg = self._config.get("table", DEFAULT_CONFIG["table"])
        for key, checkbox in self._table_checks.items():
            checkbox.setChecked(
                bool(table_cfg.get(key, DEFAULT_CONFIG["table"][key]))
            )

        flag_cfg = self._config.get("flags", DEFAULT_CONFIG["flags"])
        for key, checkbox in self._flag_checks.items():
            checkbox.setChecked(
                bool(flag_cfg.get(key, DEFAULT_CONFIG["flags"][key]))
            )

    def _collect(self) -> Dict[str, Any]:
        return {
            "cooldown": int(self._cooldown_spin.value()),
            "port": int(self._port_spin.value()),
            "weapon": self._weapon_box.currentText() or DEFAULT_CONFIG["weapon"],
            "chat_limit": int(self._chat_spin.value()),
            "table": {key: cb.isChecked() for key, cb in self._table_checks.items()},
            "flags": {key: cb.isChecked() for key, cb in self._flag_checks.items()},
        }

    # ------------------------------------------------------------ slots
    def _on_save(self) -> None:
        try:
            new_config = self._collect()
            save_config(new_config)
        except OSError as exc:
            QMessageBox.critical(
                self, "Failed to save", f"Could not write config.json:\n{exc}"
            )
            return

        self._config = new_config
        QMessageBox.information(
            self, "Saved", "Configuration saved to config.json."
        )

    def _on_reset(self) -> None:
        self._config = load_config()
        self._populate_from_config()
