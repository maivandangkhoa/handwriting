"""Paints the colouring book: the picture on the left, the palette and two big buttons on the right."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from .coloring_game import COLORS, KEYS, NEXT_CELL, PALETTE_COL, PICTURE_COLS, PICTURE_ROWS, RESET_CELL, ColoringGame

PAPER, LINE = QColor(245, 240, 225), QColor(70, 60, 50)
BUTTON = QColor(200, 200, 210)


def paint_coloring(p: QPainter, to_w, scale: float, g: ColoringGame, hint: str) -> None:
    def rect(cell, inset=0.0):
        x, y = g.square_origin(cell)
        pad = inset * g.square
        return QRectF(to_w((x + pad, y + pad)), to_w((x + g.square - pad, y + g.square - pad)))

    p.setPen(Qt.NoPen)
    p.setBrush(PAPER)
    p.drawRect(QRectF(to_w(g.origin), to_w((g.origin[0] + g.cells * g.square, g.origin[1] + g.cells * g.square))))
    for col in range(PICTURE_COLS):
        for row in range(PICTURE_ROWS):
            key = g.target((col, row))
            if key is None:
                continue
            painted = g.painted.get((col, row))
            p.setPen(QPen(LINE, max(2 * scale, 1.5)))
            p.setBrush(QColor(*COLORS[painted]) if painted else QColor(255, 255, 255))
            p.drawRect(rect((col, row)))
            if not painted:                         # the colour this cell is meant to be, as a small dot
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(*COLORS[key]))
                p.drawEllipse(rect((col, row), 0.38))
    for row, key in enumerate(KEYS):
        cell = (PALETTE_COL, row)
        p.setPen(QPen(QColor(255, 255, 255) if key == g.selected else LINE, max((7 if key == g.selected else 2) * scale, 2)))
        p.setBrush(QColor(*COLORS[key]))
        p.drawEllipse(rect(cell, 0.08))
    font = QFont()
    font.setPixelSize(int(g.square * 0.5 * scale))
    p.setFont(font)
    for cell, label in ((NEXT_CELL, "→"), (RESET_CELL, "↺")):
        p.setPen(Qt.NoPen)
        p.setBrush(BUTTON)
        p.drawRoundedRect(rect(cell, 0.08), 10, 10)
        p.setPen(LINE)
        p.drawText(rect(cell), Qt.AlignCenter, label)
    p.setPen(QColor(235, 235, 235))
    info = QFont()
    info.setPixelSize(int(26 * scale) + 4)
    p.setFont(info)
    p.drawText(to_w((16, 40)), g.status)
    p.setPen(QColor(255, 190, 120))
    p.drawText(to_w((16, 80)), hint or g.notice)
