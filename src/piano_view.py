"""Paints the piano on the logical canvas: keys that light up when struck, and where the fingertips are."""
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from .piano_layout import KEYS

WHITE, WHITE_LIT, WHITE_UNDER = QColor(240, 240, 234), QColor(90, 230, 255), QColor(200, 228, 238)
BLACK, BLACK_LIT, BLACK_UNDER = QColor(28, 28, 32), QColor(30, 165, 200), QColor(70, 90, 100)


def paint_piano(p: QPainter, to_w, scale: float, piano, now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    session = piano.session
    lit, under = session.lit(now), session.under_fingers()

    def box(k) -> QRectF:
        return QRectF(to_w((k.x, k.y)), to_w((k.x + k.w, k.y + k.h)))

    def font(px: int) -> QFont:
        f = QFont("Helvetica")
        f.setPixelSize(max(int(px * scale), 6))
        return f

    p.setPen(QColor(235, 235, 235))
    p.setFont(font(64))
    p.drawText(to_w((40, 110)), session.last.name if session.last else "")
    p.setFont(font(24))
    p.setPen(QColor(170, 170, 170))
    p.drawText(to_w((40, 190)), piano.hint)

    for k in KEYS:                         # white keys first, so the black ones are painted on top
        r = box(k)
        colors = (BLACK, BLACK_UNDER, BLACK_LIT) if k.black else (WHITE, WHITE_UNDER, WHITE_LIT)
        p.setPen(QPen(QColor(50, 50, 55), max(2 * scale, 1)))
        p.setBrush(colors[2] if k.midi in lit else colors[1] if k.midi in under else colors[0])
        p.drawRoundedRect(r, 6 * scale, 6 * scale)
        if not k.black:
            p.setPen(QColor(90, 90, 95))
            p.setFont(font(20))
            p.drawText(r.adjusted(0, 0, 0, -8 * scale), Qt.AlignBottom | Qt.AlignHCenter,
                       k.name if k.name.startswith("C") else k.name.rstrip("0123456789"))

    p.setBrush(QColor(255, 170, 40))
    p.setPen(QPen(QColor(255, 255, 255), max(2 * scale, 1)))
    for x, y in session.fingertips.values():
        p.drawEllipse(QPointF(to_w((x, y))), 7 * scale, 7 * scale)
