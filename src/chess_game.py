"""Chess interaction: pinch to pick up a piece, release to drop it. Rules come from python-chess. No Qt."""
import chess

from . import config

Point = tuple[float, float]


class ChessGame:
    def __init__(self, origin: tuple[float, float] = config.CHESS_ORIGIN, square: float = config.CHESS_SQUARE):
        self.origin, self.square = origin, square
        self.pointer: Point | None = None
        self._was_pinching = False
        self._wait_release = False   # after a cancel, ignore the pinch until the fingers open once
        self.new_game()

    def new_game(self) -> None:
        self.board = chess.Board()
        self.held: int | None = None
        self.targets: set[int] = set()
        self.last_move: chess.Move | None = None
        self.notice = ""

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
    def update(self, pointer: Point | None, pinching: bool) -> None:
        """Feed the latest canvas-space pointer (None = hand lost) and pinch state."""
        self.pointer = pointer
        if pointer is None:
            self._cancel()
            self._was_pinching = False
            self._wait_release = self._wait_release and pinching
            return
        if not pinching:
            self._wait_release = False
        if pinching and not self._was_pinching and not self._wait_release:
            self._pick(pointer)
        elif not pinching and self._was_pinching and self.held is not None:
            self._drop(pointer)
        self._was_pinching = pinching

    def _pick(self, pt: Point) -> None:
        sq = self.square_at(pt)
        if sq is None or self.board.is_game_over():
            return
        piece = self.board.piece_at(sq)
        if piece is None or piece.color != self.board.turn:
            self.notice = "Pick a piece of the side to move." if piece else ""
            return
        self.held = sq
        self.targets = {m.to_square for m in self.board.legal_moves if m.from_square == sq}
        self.notice = ""

    def _drop(self, pt: Point) -> None:
        src, dst = self.held, self.square_at(pt)
        self.held, self.targets = None, set()
        if dst is None or dst == src:
            return
        move = chess.Move(src, dst)
        if self.board.piece_at(src).piece_type == chess.PAWN and chess.square_rank(dst) in (0, 7):
            move.promotion = chess.QUEEN  # PoC: always promote to queen
        if move in self.board.legal_moves:
            self.board.push(move)
            self.last_move = move
            self.notice = ""
        else:
            self.notice = "Illegal move."

    def _cancel(self) -> None:
        if self.held is not None:
            self.notice = "Hand lost: move cancelled."
            self._wait_release = True
        self.held, self.targets = None, set()

    @property
    def status(self) -> str:
        b = self.board
        if b.is_checkmate():
            return f"Checkmate — {'Black' if b.turn == chess.WHITE else 'White'} wins"
        if b.is_game_over():
            return "Draw"
        side = "White" if b.turn == chess.WHITE else "Black"
        return f"{side} to move" + (" — CHECK" if b.is_check() else "")
