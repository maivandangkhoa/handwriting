"""Chess interaction by touch: tap a piece, tap its destination (or touch a piece and slide to the destination).
Rules come from python-chess. No Qt."""
import chess

from . import config

Point = tuple[float, float]


class ChessGame:
    def __init__(self, origin: tuple[float, float] = config.CHESS_ORIGIN, square: float = config.CHESS_SQUARE):
        self.origin, self.square = origin, square
        self.pointer: Point | None = None
        self._was_touching = False
        self._slide_from: int | None = None   # square where the current touch picked the piece up (slide-to-move)
        self.new_game()

    def new_game(self) -> None:
        self.board = chess.Board()
        self.held: int | None = None
        self.targets: set[int] = set()
        self.last_move: chess.Move | None = None
        self.notice = ""
        self.revision = getattr(self, "revision", 0) + 1   # projected image changed: shadow background is stale

    # ---- geometry (white at the bottom) ----
    def square_at(self, pt: Point) -> int | None:
        col = int((pt[0] - self.origin[0]) // self.square)
        row = int((pt[1] - self.origin[1]) // self.square)
        if not (0 <= col < 8 and 0 <= row < 8):
            return None
        return chess.square(col, 7 - row)

    def square_origin(self, sq: int) -> Point:
        return (self.origin[0] + chess.square_file(sq) * self.square,
                self.origin[1] + (7 - chess.square_rank(sq)) * self.square)

    # ---- interaction ----
    def update(self, pointer: Point | None, touching: bool) -> None:
        """Feed the latest canvas-space fingertip (None = no hand) and whether it touches the surface.
        The selection survives the hand leaving, so tap-then-tap works."""
        self.pointer = pointer
        touching = touching and pointer is not None
        if touching and not self._was_touching:
            self._touch_down(pointer)
        elif not touching and self._was_touching:
            self._touch_up(pointer)
        self._was_touching = touching

    def _touch_down(self, pt: Point) -> None:
        sq = self.square_at(pt)
        self._slide_from = None
        if sq is None or self.board.is_game_over():
            return
        if self.held is not None:
            if sq == self.held:                       # touching the selected piece again deselects it
                self._deselect()
                return
            if sq in self.targets:
                self._move(self.held, sq)
                return
        piece = self.board.piece_at(sq)
        if piece is not None and piece.color == self.board.turn:
            self._select(sq)
            self._slide_from = sq
        else:
            self.notice = ("Illegal move." if self.held is not None else
                           "Pick a piece of the side to move." if piece else "")
            self._deselect()

    def _touch_up(self, pt: Point | None) -> None:
        """Lifting after a slide that started on the selected piece drops it on the square under the finger."""
        src, self._slide_from = self._slide_from, None
        dst = self.square_at(pt) if pt is not None else None
        if src is None or self.held != src or dst is None or dst == src:
            return
        if dst in self.targets:
            self._move(src, dst)
        else:
            self._deselect()
            self.notice = "Illegal move."

    def _select(self, sq: int) -> None:
        self.held = sq
        self.targets = {m.to_square for m in self.board.legal_moves if m.from_square == sq}
        self.notice = ""

    def _deselect(self) -> None:
        self.held, self.targets = None, set()

    def _move(self, src: int, dst: int) -> None:
        move = chess.Move(src, dst)
        if self.board.piece_at(src).piece_type == chess.PAWN and chess.square_rank(dst) in (0, 7):
            move.promotion = chess.QUEEN  # PoC: always promote to queen
        self._deselect()
        if move in self.board.legal_moves:
            self.board.push(move)
            self.last_move = move
            self.notice = ""
            self.revision += 1
        else:
            self.notice = "Illegal move."

    @property
    def status(self) -> str:
        b = self.board
        if b.is_checkmate():
            return f"Checkmate — {'Black' if b.turn == chess.WHITE else 'White'} wins"
        if b.is_game_over():
            return "Draw"
        side = "White" if b.turn == chess.WHITE else "Black"
        return f"{side} to move" + (" — CHECK" if b.is_check() else "")
