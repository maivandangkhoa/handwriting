"""Paints the gomoku board on the logical canvas: lit wood, grid through the cell centres, stones, the winning line."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from .gomoku_game import GomokuGame

BOARD, GRID = QColor(222, 184, 120), QColor(70, 45, 20)
STONES = (QColor(15, 15, 15), QColor(250, 250, 250))
MARK = QColor(255, 80, 60)


def paint_gomoku(p: QPainter, to_w, scale: float, g: GomokuGame, hint: str) -> None:
    n, sq = g.cells, g.square * scale
    p.setPen(Qt.NoPen)
    p.setBrush(BOARD)
    p.drawRect(QRectF(to_w(g.origin), to_w((g.origin[0] + n * g.square, g.origin[1] + n * g.square))))
    centre = lambda cell: to_w((g.square_origin(cell)[0] + g.square / 2, g.square_origin(cell)[1] + g.square / 2))
    p.setPen(QPen(GRID, max(2 * scale, 1.5)))
    for i in range(n):
        p.drawLine(centre((0, i)), centre((n - 1, i)))
        p.drawLine(centre((i, 0)), centre((i, n - 1)))
    for cell, player in g.stones.items():
        p.setPen(QPen(STONES[1 - player], max(2 * scale, 1.5)))     # a thin rim of the other colour: visible on any wood
        p.setBrush(STONES[player])
        p.drawEllipse(centre(cell), sq * 0.42, sq * 0.42)
    if g.last is not None:
        p.setPen(QPen(MARK, max(3 * scale, 2)))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(centre(g.last), sq * 0.2, sq * 0.2)
    if g.line:
        p.setPen(QPen(MARK, max(8 * scale, 4), Qt.SolidLine, Qt.RoundCap))
        p.drawLine(centre(g.line[0]), centre(g.line[-1]))
    p.setPen(QColor(235, 235, 235))
    info = QFont()
    info.setPixelSize(int(26 * scale) + 4)
    p.setFont(info)
    p.drawText(to_w((16, 40)), g.status)
    p.setPen(QColor(255, 190, 120))
    p.drawText(to_w((16, 80)), hint or g.notice)
