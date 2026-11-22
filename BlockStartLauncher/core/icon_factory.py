import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
)


def _point(size, x, y):
    return QPointF(size * x, size * y)


def create_pixmap(size=256):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

    margin = size * 0.035
    body_rect = QRectF(margin, margin, size - margin * 2, size - margin * 2)
    body = QPainterPath()
    body.addRoundedRect(body_rect, size * 0.215, size * 0.215)

    gradient = QLinearGradient(body_rect.topLeft(), body_rect.bottomRight())
    gradient.setColorAt(0.0, QColor("#0B1220"))
    gradient.setColorAt(0.55, QColor("#111C36"))
    gradient.setColorAt(1.0, QColor("#1E3A8A"))
    painter.fillPath(body, gradient)

    glow = QRadialGradient(_point(size, 0.32, 0.22), size * 0.55)
    glow.setColorAt(0.0, QColor(56, 189, 248, 70))
    glow.setColorAt(0.55, QColor(56, 189, 248, 18))
    glow.setColorAt(1.0, QColor(56, 189, 248, 0))
    painter.fillPath(body, glow)

    border = QPen(QColor("#38BDF8"))
    border.setWidthF(max(1.0, size * 0.012))
    painter.setPen(border)
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(body)

    top = QPolygonF([_point(size, 0.50, 0.245), _point(size, 0.745, 0.385),
                     _point(size, 0.50, 0.525), _point(size, 0.255, 0.385)])
    left = QPolygonF([_point(size, 0.255, 0.385), _point(size, 0.50, 0.525),
                      _point(size, 0.50, 0.795), _point(size, 0.255, 0.655)])
    right = QPolygonF([_point(size, 0.745, 0.385), _point(size, 0.50, 0.525),
                       _point(size, 0.50, 0.795), _point(size, 0.745, 0.655)])

    painter.setPen(Qt.NoPen)
    left_gradient = QLinearGradient(_point(size, 0.255, 0.385), _point(size, 0.50, 0.795))
    left_gradient.setColorAt(0.0, QColor("#22D3EE"))
    left_gradient.setColorAt(1.0, QColor("#0369A1"))
    painter.setBrush(left_gradient)
    painter.drawPolygon(left)

    right_gradient = QLinearGradient(_point(size, 0.50, 0.525), _point(size, 0.745, 0.795))
    right_gradient.setColorAt(0.0, QColor("#8B5CF6"))
    right_gradient.setColorAt(1.0, QColor("#4338CA"))
    painter.setBrush(right_gradient)
    painter.drawPolygon(right)

    painter.setBrush(QColor("#0F172A"))
    painter.drawPolygon(top)
    edge = QPen(QColor("#67E8F9"))
    edge.setWidthF(max(1.2, size * 0.016))
    edge.setJoinStyle(Qt.RoundJoin)
    painter.setPen(edge)
    painter.setBrush(Qt.NoBrush)
    painter.drawPolygon(top)

    play = QPolygonF([_point(size, 0.455, 0.325), _point(size, 0.455, 0.445),
                      _point(size, 0.565, 0.385)])
    play_gradient = QLinearGradient(_point(size, 0.455, 0.325), _point(size, 0.565, 0.445))
    play_gradient.setColorAt(0.0, QColor("#F8FAFC"))
    play_gradient.setColorAt(1.0, QColor("#22D3EE"))
    painter.setPen(Qt.NoPen)
    painter.setBrush(play_gradient)
    painter.drawPolygon(play)

    highlight = QPen(QColor(255, 255, 255, 90))
    highlight.setWidthF(max(1.0, size * 0.009))
    painter.setPen(highlight)
    painter.drawLine(_point(size, 0.265, 0.385), _point(size, 0.49, 0.515))
    painter.drawLine(_point(size, 0.51, 0.525), _point(size, 0.51, 0.785))
    painter.end()
    return pixmap


def create_app_icon():
    return QIcon(create_pixmap())


def _glyph_pixmap(kind, size, color):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.save()
    painter.scale(size / 24.0, size / 24.0)
    pen = QPen(QColor(color))
    pen.setWidthF(1.9)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    if kind == "home":
        painter.drawPolyline(QPolygonF([QPointF(3.5, 11), QPointF(12, 4), QPointF(20.5, 11)]))
        painter.drawRoundedRect(QRectF(6, 10, 12, 10), 2, 2)
        painter.drawRoundedRect(QRectF(10, 14, 4, 6), 1.2, 1.2)
    elif kind == "instance":
        painter.drawPolygon(
            QPolygonF([QPointF(12, 3.5), QPointF(20.5, 8), QPointF(12, 12.5), QPointF(3.5, 8)])
        )
        painter.drawPolyline(
            QPolygonF([QPointF(3.5, 8), QPointF(3.5, 16), QPointF(12, 20.5), QPointF(20.5, 16), QPointF(20.5, 8)])
        )
        painter.drawLine(QPointF(12, 12.5), QPointF(12, 20.5))
    elif kind == "account":
        painter.drawEllipse(QRectF(8.2, 3.5, 7.6, 7.6))
        path = QPainterPath()
        path.moveTo(4.5, 20.5)
        path.cubicTo(4.5, 15.2, 8.2, 13.2, 12, 13.2)
        path.cubicTo(15.8, 13.2, 19.5, 15.2, 19.5, 20.5)
        painter.drawPath(path)
    elif kind == "mod":
        painter.drawRoundedRect(QRectF(4, 6, 16, 14), 2, 2)
        painter.drawEllipse(QRectF(9.8, 2.6, 4.4, 4.4))
        painter.drawLine(QPointF(4, 12.5), QPointF(20, 12.5))
        painter.drawLine(QPointF(12, 12.5), QPointF(12, 20))
    elif kind == "modpack":
        painter.drawRoundedRect(QRectF(3, 8, 18, 12.5), 2, 2)
        painter.drawLine(QPointF(3, 12), QPointF(21, 12))
        painter.drawLine(QPointF(12, 12), QPointF(12, 20.5))
        painter.drawPolyline(
            QPolygonF([QPointF(8, 8), QPointF(8, 5), QPointF(16, 5), QPointF(16, 8)])
        )
    elif kind == "resource":
        painter.drawRoundedRect(QRectF(3, 5, 18, 14), 2, 2)
        painter.drawEllipse(QRectF(7, 8, 3.2, 3.2))
        painter.drawPolyline(
            QPolygonF([QPointF(4.5, 17), QPointF(10, 11.5), QPointF(14, 15.5), QPointF(16.5, 12.5), QPointF(20, 16.5)])
        )
    elif kind == "repair":
        painter.drawLine(QPointF(5, 19), QPointF(15.5, 8.5))
        painter.drawEllipse(QRectF(13.5, 3.5, 7, 7))
        path = QPainterPath()
        path.moveTo(7.4, 20.6)
        path.lineTo(3.4, 16.6)
        path.lineTo(6.2, 13.8)
        path.lineTo(10.2, 17.8)
        path.closeSubpath()
        painter.drawPath(path)
    elif kind == "settings":
        painter.drawEllipse(QRectF(8.5, 8.5, 7, 7))
        painter.drawEllipse(QRectF(11, 11, 2, 2))
        for angle in range(0, 360, 45):
            radians = math.radians(angle)
            inner = QPointF(12 + 5.2 * math.cos(radians), 12 + 5.2 * math.sin(radians))
            outer = QPointF(12 + 8.2 * math.cos(radians), 12 + 8.2 * math.sin(radians))
            painter.drawLine(inner, outer)
    else:
        painter.drawEllipse(QRectF(4, 4, 16, 16))
    painter.restore()
    painter.end()
    return pixmap


_PIXEL_GLYPHS = {
    "home": (
        "............",
        ".....#......",
        "....###.....",
        "...#####....",
        "..#######...",
        ".....#......",
        "...#####....",
        "...##.##....",
        "...##.##....",
        "............",
    ),
    "instance": (
        "............",
        "..########..",
        ".##########.",
        ".#++####++#.",
        ".##########.",
        ".##########.",
        ".##.####.##.",
        ".##########.",
        "..########..",
        "............",
    ),
    "account": (
        "....####....",
        "..########..",
        ".##..##..##.",
        ".##..##..##.",
        ".##########.",
        "..########..",
        "...######...",
        "..########..",
        ".##..##..##.",
        "............",
    ),
    "mod": (
        ".....##.....",
        "...####.....",
        "..##..##....",
        ".##....##...",
        "###.##.###..",
        "....##......",
        "...####.....",
        "..##..##....",
        ".##....##...",
        "............",
    ),
    "modpack": (
        "............",
        "..########..",
        ".##......##.",
        ".##########.",
        ".##..##..##.",
        ".##########.",
        ".##......##.",
        "..########..",
        "............",
    ),
    "resource": (
        "............",
        ".##########.",
        ".#++++++++#.",
        ".#+######+#.",
        ".#+######+#.",
        ".#+######+#.",
        ".#++++++++#.",
        ".##########.",
        "............",
    ),
    "repair": (
        "............",
        "........##..",
        ".......####.",
        "......##.##.",
        ".....##.....",
        "....##......",
        "...##.......",
        "..##........",
        ".#..........",
        "............",
    ),
    "settings": (
        ".....##.....",
        "...####.....",
        ".#..##..#...",
        "###.##.###..",
        "..######....",
        "..######....",
        "###.##.###..",
        ".#..##..#...",
        "...####.....",
        ".....##.....",
    ),
}


def _pixel_nav_pixmap(kind, size, primary, accent):
    grid = _PIXEL_GLYPHS.get(kind)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    if not grid:
        return pixmap
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, False)
    grid_size = max(len(grid), max((len(line) for line in grid), default=0), 1)
    cell = size / grid_size
    offset_x = (size - max((len(line) for line in grid), default=0) * cell) / 2.0
    offset_y = (size - len(grid) * cell) / 2.0
    for row, line in enumerate(grid):
        for column, char in enumerate(line):
            if char == ".":
                continue
            color = QColor(accent if char == "+" else primary)
            painter.fillRect(
                QRectF(offset_x + column * cell, offset_y + row * cell, cell + 0.2, cell + 0.2),
                color,
            )
    painter.end()
    return pixmap


def create_nav_icon(kind, size=24):
    """Crisp 12x12 pixel icons; no icon font or image assets required."""
    icon = QIcon()
    for scale in (1, 2):
        icon.addPixmap(
            _pixel_nav_pixmap(kind, size * scale, "#8FA5C2", "#C7D8EE"),
            QIcon.Normal,
            QIcon.Off,
        )
        icon.addPixmap(
            _pixel_nav_pixmap(kind, size * scale, "#38BDF8", "#F8FAFC"),
            QIcon.Normal,
            QIcon.On,
        )
        icon.addPixmap(
            _pixel_nav_pixmap(kind, size * scale, "#38BDF8", "#F8FAFC"),
            QIcon.Selected,
            QIcon.On,
        )
    return icon
