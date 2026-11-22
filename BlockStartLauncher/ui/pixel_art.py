"""Small, dependency-free Minecraft-flavoured widgets.

Everything here is painted with QPainter so the launcher does not ship any
extra image files.  Rounded corners are deliberately almost square and the
outlines use a light/dark bevel to feel like blocks rather than a web app.
"""

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QProgressBar, QWidget


PIXEL_BG = "#0A111C"
PIXEL_PANEL = "#111C2E"
PIXEL_PANEL_2 = "#17263C"
PIXEL_BORDER = "#2A405D"
PIXEL_LIGHT = "#3B587D"
PIXEL_DARK = "#070C14"
PIXEL_ACCENT = "#38BDF8"
PIXEL_ACCENT_2 = "#8B5CF6"
PIXEL_GREEN = "#4ADE80"
PIXEL_YELLOW = "#FACC15"
PIXEL_RED = "#FB7185"
PIXEL_BAD = PIXEL_RED
PIXEL_MUTED = "#8FA5C2"
PIXEL_TEXT = "#E6EDF7"


class PixelProgressBar(QProgressBar):
    """A segmented progress bar with an indeterminate "moving blocks" mode."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(False)
        self.setFixedHeight(14)
        self.setMinimumWidth(140)
        self._offset = 0
        self._timer = QTimer(self)
        self._timer.setInterval(90)
        self._timer.timeout.connect(self._tick)
        self._refresh_timer()

    def setRange(self, minimum, maximum):
        super().setRange(minimum, maximum)
        self._refresh_timer()
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_timer()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._refresh_timer()

    def _busy(self):
        return self.minimum() == 0 and self.maximum() == 0

    def _refresh_timer(self):
        if self._busy() and self.isVisible():
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()

    def _tick(self):
        self._offset = (self._offset + 1) % 24
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.fillRect(rect, QColor(PIXEL_BG))
        painter.setPen(QPen(QColor(PIXEL_BORDER), 1))
        painter.drawRect(rect)
        inner = rect.adjusted(3, 3, -3, -3)
        if inner.width() < 4 or inner.height() < 4:
            painter.end()
            return
        cell = 9
        count = max(1, inner.width() // cell)
        gap = max(1, (inner.width() - count * cell) // max(1, count - 1)) if count > 1 else 0
        filled = 0.0
        if self.maximum() > self.minimum():
            filled = (self.value() - self.minimum()) / float(self.maximum() - self.minimum())
            filled = max(0.0, min(1.0, filled))
        for index in range(count):
            x = inner.left() + index * (cell + gap)
            width = min(cell, inner.right() - x + 1)
            if width <= 0:
                break
            block = QRectF(x, inner.top(), width, inner.height())
            if self._busy():
                phase = (index + self._offset) % 24
                active = phase < 6
                color = QColor(PIXEL_ACCENT if active else PIXEL_PANEL_2)
            else:
                active = index / max(1, count - 1) < filled
                color = QColor(PIXEL_ACCENT if active else PIXEL_PANEL_2)
                if active and index % 4 == 3:
                    color = QColor(PIXEL_ACCENT_2)
            painter.fillRect(block, color)
        painter.end()


class StepIndicator(QWidget):
    """A tiny three-step launch flow readout, e.g. Java -> files -> launch."""

    COLORS = {
        "idle": PIXEL_PANEL_2,
        "active": PIXEL_ACCENT,
        "done": PIXEL_GREEN,
        "error": PIXEL_RED,
    }

    def __init__(self, steps=None, parent=None):
        super().__init__(parent)
        self._steps = list(steps or ["环境检查", "准备文件", "启动游戏"])
        self._states = ["idle"] * len(self._steps)
        self._pulse = False
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._tick)
        self.setMinimumHeight(48)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().verticalPolicy())

    def set_steps(self, steps):
        self._steps = list(steps or [])
        self._states = ["idle"] * len(self._steps)
        self.update()

    def set_step(self, index, state="active"):
        if 0 <= index < len(self._states):
            self._states[index] = str(state)
            if any(value == "active" for value in self._states):
                if not self._timer.isActive():
                    self._timer.start()
            else:
                self._timer.stop()
            self.update()

    def reset(self):
        self._states = ["idle"] * len(self._steps)
        self._timer.stop()
        self.update()

    def _tick(self):
        self._pulse = not self._pulse
        self.update()

    def paintEvent(self, _event):
        if not self._steps:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        width = max(1, self.width())
        gap = 8
        cell = max(1, (width - gap * (len(self._steps) - 1)) // len(self._steps))
        font = QFont("Microsoft YaHei", 8)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        for index, label in enumerate(self._steps):
            left = index * (cell + gap)
            rect = QRectF(left, 0, cell, 30)
            state = self._states[index] if index < len(self._states) else "idle"
            color = QColor(self.COLORS.get(state, PIXEL_PANEL_2))
            if state == "active" and self._pulse:
                color = color.lighter(125)
            painter.fillRect(rect, color)
            border = QColor(PIXEL_LIGHT if state != "idle" else PIXEL_BORDER)
            painter.setPen(QPen(border, 1))
            painter.drawRect(rect)
            marker = QRectF(left + 6, 9, 12, 12)
            painter.fillRect(marker, QColor(PIXEL_BG if state == "active" else PIXEL_DARK))
            painter.setPen(QPen(color, 1))
            painter.drawRect(marker)
            if state == "done":
                painter.drawLine(int(marker.left() + 3), int(marker.center().y()),
                                 int(marker.left() + 6), int(marker.bottom() - 3))
                painter.drawLine(int(marker.left() + 6), int(marker.bottom() - 3),
                                 int(marker.right() - 2), int(marker.top() + 3))
            elif state == "error":
                painter.drawLine(int(marker.left() + 3), int(marker.top() + 3),
                                 int(marker.right() - 3), int(marker.bottom() - 3))
                painter.drawLine(int(marker.right() - 3), int(marker.top() + 3),
                                 int(marker.left() + 3), int(marker.bottom() - 3))
            painter.setPen(QColor(PIXEL_TEXT if state in ("active", "done") else PIXEL_MUTED))
            text_rect = QRectF(left + 24, 0, max(1, cell - 28), 30)
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft,
                             metrics.elidedText(str(label), Qt.ElideRight, int(text_rect.width())))
            if index < len(self._steps) - 1:
                y = 15
                painter.setPen(QPen(QColor(PIXEL_BORDER), 2, Qt.DotLine))
                painter.drawLine(left + cell + 1, y, left + cell + gap - 1, y)
        painter.end()


class PixelBackdrop(QWidget):
    """A very quiet voxel horizon used behind the dashboard cards."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)

    def sizeHint(self):
        return QSize(800, 260)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        width = max(1, self.width())
        height = max(1, self.height())
        unit = 16
        # Sparse "stars" in the upper half, fixed positions to avoid repaint jitter.
        painter.setPen(Qt.NoPen)
        for x, y, size, alpha in (
            (38, 26, 2, 90), (124, 54, 2, 65), (210, 19, 3, 80),
            (318, 72, 2, 55), (406, 35, 2, 75), (512, 61, 3, 65),
            (620, 24, 2, 80), (730, 52, 2, 60), (842, 33, 2, 75),
            (948, 67, 3, 55), (1040, 22, 2, 70),
        ):
            if x < width:
                painter.fillRect(x, y, size, size, QColor(56, 189, 248, alpha))
        # A low, blocky horizon made from three muted terrain layers.
        horizon = int(height * 0.62)
        layers = (
            (0.00, QColor(20, 45, 65, 52)),
            (0.08, QColor(18, 62, 63, 55)),
            (0.16, QColor(36, 70, 49, 60)),
        )
        for offset, color in layers:
            base = horizon + int(height * offset)
            step = 0
            seed = int(base) * 7
            while step < width:
                block_w = unit * (2 + (seed + step) % 3)
                block_h = unit * (1 + (seed + step * 3) % 2)
                painter.fillRect(step, base, block_w, block_h, color)
                step += block_w
        # A couple of grass-edge pixels to make the horizon read as terrain.
        painter.fillRect(0, horizon, width, 2, QColor(74, 222, 128, 35))
        painter.end()
