"""Paints the typing app on the logical canvas: camera-read text, real text, and a keyboard with live highlights."""
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from .keyboard_layout import KEYS, LAYOUT_H, LAYOUT_W, key_at

KB_X, KB_Y, KB_UNIT, KB_ROW_H = 40, 252, 80, 72
FLASH_S = 0.35


def paint_typing(p: QPainter, to_w, scale: float, typing) -> None:
    session = typing.session

    def rect(x, y, w, h) -> QRectF:
        return QRectF(to_w((x, y)), to_w((x + w, y + h)))

    def font(px: int, family: str = "Menlo") -> QFont:
        f = QFont(family)
        f.setPixelSize(max(int(px * scale), 6))
        return f

    p.setPen(QColor(170, 170, 170))
    p.setFont(font(15, "Helvetica"))
    p.drawText(to_w((40, 30)), "Read by camera:")
    p.fillRect(rect(40, 38, 1200, 124), QColor(30, 30, 34))
    p.setPen(QColor(240, 240, 240))
    p.setFont(font(30))
    p.drawText(rect(52, 44, 1176, 112), Qt.TextWordWrap, session.text.replace("\t", "    ") + "▌")
    p.setPen(QColor(170, 170, 170))
    p.setFont(font(15, "Helvetica"))
    p.drawText(to_w((40, 182)), "Actually typed (real keyboard, for comparison):")
    p.fillRect(rect(40, 190, 1200, 50), QColor(30, 30, 34))
    p.setPen(QColor(150, 200, 150))
    p.setFont(font(18))
    p.drawText(rect(52, 192, 1176, 46), Qt.TextWordWrap, session.actual_text.replace("\t", "    "))

    active = session.active_keys()
    fired = session.last_fired[0] if session.last_fired and time.monotonic() - session.last_fired[1] < FLASH_S else None
    corner = typing.calib_corner()
    target = key_at(min(max(corner[0], 0.01), LAYOUT_W - 0.01), min(max(corner[1], 0.01), LAYOUT_H - 0.01)) if corner else None
    p.setFont(font(16, "Helvetica"))
    for key in KEYS:
        cell = rect(KB_X + key.x * KB_UNIT + 2, KB_Y + key.y * KB_ROW_H + 2, key.w * KB_UNIT - 4, KB_ROW_H - 4)
        p.setPen(QPen(QColor(90, 90, 96), 1))
        p.setBrush(QColor(200, 60, 60) if key == target else QColor(60, 170, 90) if key == fired else QColor(70, 110, 190) if key in active else QColor(55, 55, 60))
        p.drawRoundedRect(cell, 6 * scale, 6 * scale)
        p.setPen(QColor(235, 235, 235))
        p.drawText(cell, Qt.AlignCenter, key.name)
    p.setPen(QPen(QColor(255, 255, 255), 1.5))
    p.setBrush(QColor(255, 210, 0, 220))
    for x, y in session.fingertips.values():
        if 0 <= x <= LAYOUT_W and 0 <= y <= LAYOUT_H:
            p.drawEllipse(to_w((KB_X + x * KB_UNIT, KB_Y + y * KB_ROW_H)), 6, 6)
    if corner:
        p.setPen(QPen(QColor(255, 255, 255), 3))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(to_w((KB_X + corner[0] * KB_UNIT, KB_Y + corner[1] * KB_ROW_H)), 14, 14)
    if not typing.ready:
        p.setPen(QColor(255, 190, 120))
        p.setFont(font(20, "Helvetica"))
        p.drawText(rect(KB_X, KB_Y + LAYOUT_H * KB_ROW_H + 6, 1200, 30), Qt.AlignLeft,
                   "Not calibrated: press Calibrate Keyboard, then click the 4 keyboard corners on the preview.")
