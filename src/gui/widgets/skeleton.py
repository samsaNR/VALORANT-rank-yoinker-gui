"""Animated shimmer placeholder used while live data is loading.

Used in the player table header bar to communicate "we are connecting / we
are still pulling ranks" rather than showing dashes that look like errors.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPaintEvent,
)
from PySide6.QtWidgets import QSizePolicy, QWidget


class SkeletonRow(QWidget):
    """Single horizontal shimmering bar.

    The shimmer is achieved by painting a linear gradient whose middle stop
    moves left-to-right across the bar via a property animation. Cheap,
    GPU-friendly, no PNG asset required.
    """

    BG = QColor("#222a3a")
    HL = QColor("#39435a")

    def __init__(
        self,
        height: int = 14,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._progress: float = 0.0
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._anim = QPropertyAnimation(self, b"progress", self)
        self._anim.setDuration(1100)
        self._anim.setStartValue(-0.2)
        self._anim.setEndValue(1.2)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._anim.setLoopCount(-1)
        self._anim.start()

    # ------------------------------------------------------------ animation
    def get_progress(self) -> float:
        return self._progress

    def set_progress(self, value: float) -> None:
        self._progress = float(value)
        self.update()

    progress = Property(float, get_progress, set_progress)

    # ------------------------------------------------------------ paint
    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        radius = rect.height() / 2

        gradient = QLinearGradient(rect.left(), 0, rect.right(), 0)
        # Shimmer band centred on `progress`. Positions outside [0,1] are
        # clamped by Qt so the band can scroll in/out of frame.
        center = max(0.0, min(1.0, self._progress))
        left = max(0.0, center - 0.18)
        right = min(1.0, center + 0.18)
        gradient.setColorAt(0.0, self.BG)
        gradient.setColorAt(left, self.BG)
        gradient.setColorAt(center, self.HL)
        gradient.setColorAt(right, self.BG)
        gradient.setColorAt(1.0, self.BG)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawRoundedRect(rect, radius, radius)

    # ------------------------------------------------------------ control
    def stop(self) -> None:
        self._anim.stop()
        self.hide()
