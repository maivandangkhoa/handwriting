"""Gomoku (cờ caro) by touch: two players take turns touching an empty cell; five in a row wins. No Qt."""
from . import config

Point = tuple[float, float]
Cell = tuple[int, int]    # (column, row), row 0 at the top
DIRECTIONS = ((1, 0), (0, 1), (1, 1), (1, -1))
WIN_LENGTH = 5
NAMES = ("X", "O")        # X moves first


class GomokuGame:
    def __init__(self, origin: Point = config.GOMOKU_ORIGIN, square: float = config.GOMOKU_SQUARE,
                 cells: int = config.GOMOKU_CELLS):
        self.origin, self.square, self.cells = origin, square, cells
        self.pointer: Point | None = None
        self._was_touching = False
        self.new_game()

    def new_game(self) -> None:
        self.stones: dict[Cell, int] = {}
        self.turn = 0
        self.last: Cell | None = None
        self.winner: int | None = None
        self.line: list[Cell] = []
        self.notice = ""
        self.revision = getattr(self, "revision", 0) + 1   # projected image changed: shadow background is stale

    # ---- geometry ----
    def square_at(self, pt: Point) -> Cell | None:
        col = int((pt[0] - self.origin[0]) // self.square)
        row = int((pt[1] - self.origin[1]) // self.square)
        return (col, row) if 0 <= col < self.cells and 0 <= row < self.cells else None

    def square_origin(self, cell: Cell) -> Point:
        return (self.origin[0] + cell[0] * self.square, self.origin[1] + cell[1] * self.square)

    # ---- interaction ----
    def update(self, pointer: Point | None, touching: bool) -> None:
        """Feed the latest canvas-space fingertip (None = no hand) and whether it touches the surface."""
        self.pointer = pointer
        touching = touching and pointer is not None
        if touching and not self._was_touching:
            self._touch_down(pointer)
        self._was_touching = touching

    def _touch_down(self, pt: Point) -> None:
        cell = self.square_at(pt)
        if cell is None or self.over:
            return
        if cell in self.stones:
            self.notice = "That cell is taken."
            return
        self.stones[cell] = self.turn
        self.last, self.notice = cell, ""
        self.line = self._line_through(cell)
        if self.line:
            self.winner = self.turn
        self.turn = 1 - self.turn
        self.revision += 1

    def _line_through(self, cell: Cell) -> list[Cell]:
        """The run of WIN_LENGTH or more same-player stones through `cell`, or []."""
        player = self.stones[cell]
        for dx, dy in DIRECTIONS:
            run = [cell]
            for sign in (1, -1):
                c = (cell[0] + sign * dx, cell[1] + sign * dy)
                while self.stones.get(c) == player:
                    run.append(c)
                    c = (c[0] + sign * dx, c[1] + sign * dy)
            if len(run) >= WIN_LENGTH:
                return sorted(run)
        return []

    @property
    def over(self) -> bool:
        return self.winner is not None or len(self.stones) == self.cells ** 2

    @property
    def status(self) -> str:
        if self.winner is not None:
            return f"{NAMES[self.winner]} wins with five in a row"
        if self.over:
            return "Draw"
        return f"{NAMES[self.turn]} to move"
