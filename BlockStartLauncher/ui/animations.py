from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

try:
    import shiboken6

    def _valid(obj):
        return obj is not None and shiboken6.isValid(obj)
except Exception:  # pragma: no cover - extremely old PySide builds
    def _valid(obj):
        return obj is not None


class Spinner(QWidget):
    """An eight-block loading spinner drawn without image assets."""

    def __init__(self, parent=None, size=22):
        super().__init__(parent)
        self._step = 0
        self._running = False
        self._timer = QTimer(self)
        self._timer.setInterval(70)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(size, size)
        self.hide()

    def set_running(self, running):
        running = bool(running)
        if running == self._running and running == self.isVisible():
            return
        self._running = running
        self.setVisible(running)
        if running:
            self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def _tick(self):
        self._step = (self._step + 1) % 8
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setPen(Qt.NoPen)
        side = min(self.width(), self.height())
        cell = max(3.0, side / 6.0)
        center = side / 2.0
        radius = side * 0.31
        for index in range(8):
            import math

            angle = math.radians(index * 45 - 90)
            x = center + math.cos(angle) * radius - cell / 2.0
            y = center + math.sin(angle) * radius - cell / 2.0
            distance = (index - self._step) % 8
            if distance == 0:
                color = QColor("#F8FAFC")
            elif distance == 1:
                color = QColor("#38BDF8")
            elif distance == 2:
                color = QColor("#22D3EE")
            else:
                color = QColor(42, 64, 93, 120)
            painter.fillRect(QRectF(x, y, cell, cell), color)
        painter.end()


def fade_in(widget, duration=160):
    """Fade a page in, safely ignoring a widget destroyed mid-animation."""
    if widget is None or not _valid(widget):
        return None
    try:
        if not widget.isVisible():
            return None
        old = getattr(widget, "_bsl_fade", None)
        if old is not None:
            try:
                old.stop()
                old.deleteLater()
            except Exception:
                pass
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.0)
        widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", widget)
        animation.setDuration(max(60, int(duration)))
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.OutCubic)

        def cleanup():
            if not _valid(widget):
                return
            if getattr(widget, "_bsl_fade", None) is not animation:
                return
            try:
                if _valid(effect):
                    widget.setGraphicsEffect(None)
            except Exception:
                pass
            widget._bsl_fade = None
            animation.deleteLater()

        animation.finished.connect(cleanup)
        widget._bsl_fade = animation
        animation.start()
        return animation
    except Exception:
        return None
