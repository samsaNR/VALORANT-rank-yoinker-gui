"""Modern iOS-style toggle switch.

Replaces the default Qt QCheckBox glyph with an animated pill: a wider track
that slides a circular knob between two positions. Emits ``toggled`` like a
QAbstractButton so existing checkbox-style call sites can swap it in cleanly.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QAbstractButton, QSizePolicy, QWidget


class ToggleSwitch(QAbstractButton):
    """Pill-shaped toggle that animates a knob between off/on states."""

    TRACK_OFF = QColor("#2a3242")
    TRACK_ON = QColor("#ff4655")
    KNOB = QColor("#ece8e1")

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._knob_position: float = 2.0
        self._anim = QPropertyAnimation(self, b"knobPosition", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate_knob)

    # -------------------------------------------------------------- size
    def sizeHint(self) -> QSize:  # noqa: D401
        return QSize(46, 26)

    # -------------------------------------------------------- knob anim
    def _knob_target(self) -> float:
        # 2px padding from the edges; track is 46 wide, knob is 22 wide,
        # so the on-position lives at 46 - 22 - 2 == 22.
        return float(self.width() - 24) if self.isChecked() else 2.0

    def _animate_knob(self, _checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._knob_position)
        self._anim.setEndValue(self._knob_target())
        self._anim.start()

    def get_knob_position(self) -> float:
        return self._knob_position

    def set_knob_position(self, value: float) -> None:
        self._knob_position = float(value)
        self.update()

    knobPosition = Property(float, get_knob_position, set_knob_position)

    # ---------------------------------------------------------- paint
    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Track: rounded rectangle, colour interpolated from off->on as
        # the knob travels.
        track_rect = QRectF(0, 4, self.width(), self.height() - 8)
        radius = track_rect.height() / 2

        progress = max(0.0, min(1.0, (self._knob_position - 2.0) / max(1.0, self.width() - 26)))
        track_color = QColor(
            int(self.TRACK_OFF.red() + (self.TRACK_ON.red() - self.TRACK_OFF.red()) * progress),
            int(self.TRACK_OFF.green() + (self.TRACK_ON.green() - self.TRACK_OFF.green()) * progress),
            int(self.TRACK_OFF.blue() + (self.TRACK_ON.blue() - self.TRACK_OFF.blue()) * progress),
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track_rect, radius, radius)

        # Knob: filled circle with a faint shadow band drawn under it.
        knob_size = self.height() - 12
        knob_rect = QRectF(
            self._knob_position,
            (self.height() - knob_size) / 2,
            knob_size,
            knob_size,
        )
        painter.setBrush(self.KNOB)
        painter.drawEllipse(knob_rect)

    # ---------------------------------------------------------- events
    def resizeEvent(self, event) -> None:  # noqa: D401
        # Keep the knob position aligned to whichever side the current state
        # implies, otherwise resizes during animation can leave it floating.
        if not self._anim.state():
            self._knob_position = self._knob_target()
        super().resizeEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        super().mouseReleaseEvent(event)
        # Force a paint so colour interpolation matches the new state even
        # if signals are blocked.
        self.update()
