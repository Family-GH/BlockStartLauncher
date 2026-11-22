from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QLabel, QVBoxLayout

from ui.pixel_art import (
    PIXEL_ACCENT,
    PIXEL_BG,
    PIXEL_GREEN,
    PIXEL_RED,
    PIXEL_TEXT,
    PIXEL_YELLOW,
)


class Toast(QFrame):
    """Non-blocking status message shown above the bottom edge of the window."""

    COLORS = {
        "info": PIXEL_ACCENT,
        "success": PIXEL_GREEN,
        "warning": PIXEL_YELLOW,
        "error": PIXEL_RED,
    }

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setVisible(False)
        self._label = QLabel("")
        self._label.setWordWrap(True)
        self._label.setStyleSheet("background: transparent; color: %s;" % PIXEL_TEXT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 9, 14, 9)
        layout.addWidget(self._label)
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)
        self._fade = QPropertyAnimation(self._effect, b"opacity", self)
        self._fade.setDuration(160)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)
        self._fade.finished.connect(self._on_faded)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)
        self._token = 0
        self._fading_out = False
        self._hide_after_fade = False

    def show_message(self, text, kind="info", duration=2600):
        text = str(text or "").strip()
        if not text:
            return
        self._token += 1
        token = self._token
        color = self.COLORS.get(kind, PIXEL_ACCENT)
        self.setStyleSheet(
            "QFrame#Toast { background-color: %s; border: 2px solid %s;"
            " border-top-color: %s; border-left-color: %s; }"
            % (PIXEL_BG, color, color, color)
        )
        self._label.setText(text)
        width = min(540, max(220, self._label.fontMetrics().horizontalAdvance(text) + 34))
        self.setFixedWidth(width)
        self.adjustSize()
        self._fading_out = False
        self._hide_after_fade = False
        self._fade.stop()
        self._effect.setOpacity(0.0)
        self.reposition()
        self.show()
        self.raise_()
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()
        self._hide_timer.start(max(900, int(duration)))

    def reposition(self):
        parent = self.parentWidget()
        if parent is None:
            return
        self.adjustSize()
        x = max(8, (parent.width() - self.width()) // 2)
        y = max(8, parent.height() - self.height() - 48)
        self.move(x, y)

    def _fade_out(self):
        if self._fading_out:
            return
        self._fading_out = True
        self._hide_after_fade = True
        self._fade.stop()
        self._fade.setStartValue(self._effect.opacity())
        self._fade.setEndValue(0.0)
        self._fade.start()

    def _on_faded(self):
        if not self._hide_after_fade:
            return
        self._hide_after_fade = False
        self._fading_out = False
        self.hide()
