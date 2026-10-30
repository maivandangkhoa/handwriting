"""Paints the drawing-on-projector furniture on the logical canvas: the frame around the page and the colour palette."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from .projector_draw import FRAME_INSET


def paint_draw_furniture(p: QPainter, to_w, scale: float, projector, color) -> None:
    """Frame in the current pen colour, a swatch per colour (the current one outlined), and an arc filling around
    the swatch the pointer rests on."""
    w, h = projector.canvas_size
    pen_color = QColor(*color)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(pen_color, max(7 * scale, 3)))
    p.drawRect(QRectF(to_w((FRAME_INSET, FRAME_INSET)), to_w((w - FRAME_INSET, h - FRAME_INSET))))
    for i in range(projector.swatch_count):
        r = projector.swatch_rect(i)
        box = QRectF(to_w((r.x(), r.y())), to_w((r.right(), r.bottom())))
        rgb = projector.colors[i] if i < len(projector.colors) else None     # past the colours: a button
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(*rgb) if rgb else QColor(200, 200, 210))
        p.drawRoundedRect(box, 10 * scale, 10 * scale)
        if rgb is None:
            font = p.font()
            font.setPixelSize(int(34 * scale))
            p.setFont(font)
            p.setPen(QColor(60, 50, 40))
            p.drawText(box, Qt.AlignCenter, "→")
        if rgb == tuple(color):
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(*projector.ring_color), max(6 * scale, 3)))
            p.drawRoundedRect(box.adjusted(-6 * scale, -6 * scale, 6 * scale, 6 * scale), 12 * scale, 12 * scale)
    i = projector.resting_swatch
    if i is not None and projector.pick > 0:
        r = projector.swatch_rect(i).adjusted(-14, -14, 14, 14)
        box = QRectF(to_w((r.x(), r.y())), to_w((r.right(), r.bottom())))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(*projector.ring_color), max(9 * scale, 4)))
        p.drawArc(box, 90 * 16, int(-projector.pick * 360 * 16))
