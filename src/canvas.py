"""Canvas widget: draws strokes (Air Drawing) or the chess board (Chess) in logical canvas coordinates."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

import chess

from . import config
from .chess_game import ChessGame
from .draw_view import paint_draw_furniture
from .drawing import DrawingState
from .gomoku_game import GomokuGame
from .gomoku_view import paint_gomoku
from .typing_view import paint_typing

CANVAS_SIZE = (config.CANVAS_WIDTH, config.CANVAS_HEIGHT)
TARGETS = [(0.06, 0.08), (0.94, 0.08), (0.94, 0.92), (0.06, 0.92)]  # TL, TR, BR, BL as canvas fractions
LIGHT, DARK = QColor(240, 217, 181), QColor(181, 136, 99)
HIGHLIGHT = QColor(255, 235, 120)


class CanvasWidget(QWidget):
    """Letterboxed logical canvas. Shows the chess board when `game` is set, otherwise the drawn strokes."""

    def __init__(self, state: DrawingState):
        super().__init__()
        self.state = state
        self.game: ChessGame | GomokuGame | None = None
        self.typing = None   # TypingMode when the typing app is active
        self.projector = None   # ProjectorSurface while an app runs on a projector (calibration patterns, ring)
        self.show_cursor = True   # off on the projector itself: the real finger is the cursor, a dot would light it
        self.pinching = False
        self.target_index: int | None = None  # calibration target to highlight
        self.setMinimumSize(480, 270)

    @property
    def lit_ink(self) -> bool:
        """Drawing on a projector: black canvas, bright strokes (dark ink would be just the unlit wall)."""
        return self.projector is not None and self.game is None and self.typing is None

    def _viewport(self) -> tuple[QRectF, float]:
        s = min(self.width() / CANVAS_SIZE[0], self.height() / CANVAS_SIZE[1])
        w, h = CANVAS_SIZE[0] * s, CANVAS_SIZE[1] * s
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h), s

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(40, 40, 40))
        rect, s = self._viewport()
        pattern = self.projector.pattern if self.projector is not None else None
        p.fillRect(rect, QColor(0, 0, 0) if pattern or self.lit_ink else
                   QColor(255, 255, 255) if self.game is None and self.typing is None else
                   QColor(110, 106, 100) if self.game is not None else QColor(52, 49, 46))

        def to_w(pt):
            return QPointF(rect.x() + pt[0] * s, rect.y() + pt[1] * s)

        if pattern == "markers":
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255))
            for c in self.projector.markers:
                p.drawEllipse(to_w(c), self.projector.marker_radius * s, self.projector.marker_radius * s)
        if pattern:
            return
        if self.projector is not None and self.projector.paints_canvas:
            self.projector.paint(p, to_w, s)
            cursor = None
        elif self.typing is not None:
            paint_typing(p, to_w, s, self.typing)
            cursor = None
        elif self.game is None:
            if self.lit_ink:
                paint_draw_furniture(p, to_w, s, self.projector, self.state.color)
            self._paint_strokes(p, to_w)
            cursor = self.state.cursor
        else:
            hint = self.projector.hint if self.projector is not None else ""
            if isinstance(self.game, GomokuGame):
                paint_gomoku(p, to_w, s, self.game, hint)
            else:
                self._paint_chess(p, to_w, s)
            cursor = self.game.pointer
        if self.projector is not None and self.projector.target is not None:
            c = to_w(self.projector.target)
            p.setPen(QPen(QColor(255, 235, 120), 6))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(c, 26 * s, 26 * s)
            if self.projector.progress > 0:     # hold progress: a green arc fills the ring
                p.setPen(QPen(QColor(60, 230, 90), 10))
                p.drawArc(QRectF(c.x() - 26 * s, c.y() - 26 * s, 52 * s, 52 * s), 90 * 16,
                          int(-self.projector.progress * 360 * 16))
        if self.projector is not None and self.projector.dwell_square is not None:    # point-and-hold filling
            c = to_w(self.projector.dwell_square)
            r = 0.36 * self.game.square * s
            p.setPen(QPen(QColor(60, 230, 90), 8))
            p.setBrush(Qt.NoBrush)
            p.drawArc(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), 90 * 16, int(-self.projector.dwell * 360 * 16))
        if self.target_index is not None:
            fx, fy = TARGETS[self.target_index]
            c = to_w((fx * CANVAS_SIZE[0], fy * CANVAS_SIZE[1]))
            p.setPen(QPen(QColor(220, 0, 0), 3))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(c, 22, 22)
            p.drawLine(c + QPointF(-30, 0), c + QPointF(30, 0))
            p.drawLine(c + QPointF(0, -30), c + QPointF(0, 30))
        if cursor is not None and self.show_cursor:
            p.setPen(QPen(QColor(255, 255, 255), 2))
            p.setBrush(QColor(40, 200, 70, 220) if self.pinching else QColor(230, 40, 40, 200))
            p.drawEllipse(to_w(cursor), 9 if not self.pinching else 6, 9 if not self.pinching else 6)

    def _paint_strokes(self, p: QPainter, to_w) -> None:
        for stroke, color in zip(self.state.strokes, self.state.colors):
            ink = QPen(QColor(*color), 9) if self.lit_ink else QPen(QColor(20, 20, 120), 4)
            ink.setCapStyle(Qt.RoundCap)
            ink.setJoinStyle(Qt.RoundJoin)
            p.setPen(ink)
            if len(stroke) == 1:
                p.drawPoint(to_w(stroke[0]))
            for a, b in zip(stroke, stroke[1:]):
                p.drawLine(to_w(a), to_w(b))

    def _paint_chess(self, p: QPainter, to_w, scale: float) -> None:
        g = self.game
        sq = g.square * scale
        p.setPen(Qt.NoPen)
        for square in range(64):
            ox, oy = g.square_origin(square)
            cell = QRectF(to_w((ox, oy)), QPointF(to_w((ox + g.square, oy + g.square))))
            col, row = square % 8, square // 8
            p.setBrush(DARK if (col + row) % 2 == 0 else LIGHT)
            p.drawRect(cell)
            if g.last_move and square in (g.last_move.from_square, g.last_move.to_square):
                p.setBrush(QColor(255, 235, 59, 110))
                p.drawRect(cell)
            if square == g.held:   # outline only, and brighter than the square: a darker patch would pass for shadow
                p.setPen(QPen(HIGHLIGHT, max(4 * scale, 3)))
                p.setBrush(Qt.NoBrush)
                p.drawRect(cell.adjusted(3, 3, -3, -3))
                p.setPen(Qt.NoPen)
            elif square in g.targets:
                p.setBrush(HIGHLIGHT)
                p.drawEllipse(cell.center(), sq * 0.12, sq * 0.12)
        font = QFont("Apple Symbols")
        font.setPixelSize(int(sq * 0.8))
        p.setFont(font)
        for square, piece in g.board.piece_map().items():
            ox, oy = g.square_origin(square)
            self._draw_piece(p, to_w((ox, oy)), sq, piece)
        p.setPen(QColor(235, 235, 235))
        info = QFont()
        info.setPixelSize(int(26 * scale) + 4)
        p.setFont(info)
        p.drawText(to_w((16, 40)), g.status)
        p.setPen(QColor(255, 190, 120))
        hint = self.projector.hint if self.projector is not None else ""
        p.drawText(to_w((16, 80)), hint or g.notice)

    @staticmethod
    def _draw_piece(p: QPainter, top_left: QPointF, size: float, piece: chess.Piece) -> None:
        # Always the solid glyph, recoloured; outlined so both colours stay visible on any square.
        # U+FE0E forces text (not emoji) presentation of the pawn.
        glyph = chess.Piece(piece.piece_type, chess.BLACK).unicode_symbol() + "\ufe0e"
        white = piece.color == chess.WHITE
        rect = QRectF(top_left, QPointF(top_left.x() + size, top_left.y() + size))
        p.setPen(QColor(20, 20, 20))
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            p.drawText(rect.translated(dx * 1.5, dy * 1.5), Qt.AlignCenter, glyph)
        p.setPen(QColor(255, 255, 255) if white else QColor(10, 10, 10))
        p.drawText(rect, Qt.AlignCenter, glyph)
