"""A small, palette-aware wave without changing QProgressBar value semantics."""
from __future__ import annotations

import ctypes
import math
import os

from PyQt6.QtCore import QEvent, QRectF, Qt, QTimer
from PyQt6.QtGui import QPainter, QPainterPath, QPalette, QPen
from PyQt6.QtWidgets import QProgressBar


def _system_animations_enabled() -> bool:
    if os.name != "nt":
        return True
    enabled = ctypes.c_int()
    try:
        # SPI_GETCLIENTAREAANIMATION reads the Windows accessibility preference.
        if ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0):
            return bool(enabled.value)
    except (AttributeError, OSError):
        pass
    return False


class WaveProgressBar(QProgressBar):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setRange(0, 100)
        self.setValue(0)
        self.setMinimumHeight(24)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._advance)
        self.valueChanged.connect(self._sync_animation)
        self.window().installEventFilter(self)

    def _sync_animation(self) -> None:
        active = (self.isVisible() and not self.window().isMinimized()
                  and 0 <= self.value() < self.maximum() and _system_animations_enabled())
        if active:
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()

    def _advance(self) -> None:
        self._phase = (self._phase + 0.18) % math.tau
        self.update()

    def eventFilter(self, watched, event) -> bool:
        if event.type() in (QEvent.Type.WindowStateChange, QEvent.Type.StyleChange):
            self._sync_animation()
        return super().eventFilter(watched, event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_animation()

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self.font())
        label_width = self.fontMetrics().horizontalAdvance("100%") + 12
        end = max(3.0, self.width() - label_width - 3.0)
        center = self.height() / 2.0
        path = QPainterPath()
        for x in range(3, int(end) + 1):
            y = center + 2.5 * math.sin((x - 3) * math.tau / 22.0 - self._phase)
            if x == 3:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        track = self.palette().color(QPalette.ColorRole.Text)
        track.setAlphaF(0.30)
        pen = QPen(track, 2.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawPath(path)
        fraction = max(0.0, min(1.0, self.value() / 100.0))
        if fraction:
            painter.save()
            fill_end = self.width() if fraction == 1.0 else 3 + (end - 3) * fraction
            painter.setClipRect(QRectF(0, 0, fill_end, self.height()))
            pen.setColor(self.palette().color(QPalette.ColorRole.Highlight))
            painter.setPen(pen)
            painter.drawPath(path)
            painter.restore()
        painter.setPen(self.palette().color(QPalette.ColorRole.Text))
        painter.drawText(QRectF(end + 8, 0, label_width - 5, self.height()),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self.text())
