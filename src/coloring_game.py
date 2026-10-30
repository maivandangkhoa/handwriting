"""Colouring book for small children, on the same cell grid as gomoku: touch a colour, then touch the picture.
The picture is pixel art; each of its cells shows a dot of the colour it is meant to be. No Qt."""
from . import config

Point = tuple[float, float]
Cell = tuple[int, int]
PICTURE_COLS, PICTURE_ROWS = 8, 10
COLORS = {"R": (230, 50, 50), "O": (250, 150, 30), "Y": (250, 220, 40), "G": (60, 180, 75), "L": (90, 190, 250),
          "N": (40, 80, 200), "P": (150, 80, 200), "K": (250, 120, 190), "W": (140, 90, 50), "S": (150, 150, 155)}
KEYS = list(COLORS)                  # the palette, top to bottom of its column
PALETTE_COL, TOOL_COL = PICTURE_COLS, PICTURE_COLS + 1
NEXT_CELL, RESET_CELL = (TOOL_COL, 0), (TOOL_COL, 1)
PICTURES = {
    "Heart": ("........", ".RR..RR.", "RRRRRRRR", "RRRRRRRR", "RRRRRRRR", ".RRRRRR.", "..RRRR..", "...RR...",
              "........", "........"),
    "House": ("...RR...", "..RRRR..", ".RRRRRR.", "RRRRRRRR", ".YYYYYY.", ".YLYYLY.", ".YLYYLY.", ".YYYYYY.",
              ".YYWWYY.", ".YYWWYY."),
    "Flower": ("...KK...", ".KKKKKK.", "KKKYYKKK", "KKKYYKKK", ".KKKKKK.", "...KK...", "...GG...", ".GGGGGG.",
               "...GG...", "...GG..."),
}


class ColoringGame:
    def __init__(self, origin: Point = config.GOMOKU_ORIGIN, square: float = config.GOMOKU_SQUARE,
                 cells: int = config.GOMOKU_CELLS):
        assert cells >= max(PICTURE_ROWS, TOOL_COL + 1)
        self.origin, self.square, self.cells = origin, square, cells
        self.pointer: Point | None = None
        self._was_touching = False
        self.picture = 0
        self.selected = "R"
        self.new_game()

    def new_game(self) -> None:
        """Wipes the colouring of the current picture."""
        self.painted: dict[Cell, str] = {}
        self.notice = ""
        self.revision = getattr(self, "revision", 0) + 1   # projected image changed: shadow background is stale

    @property
    def name(self) -> str:
        return list(PICTURES)[self.picture]

    def target(self, cell: Cell) -> str | None:
        """The colour key this picture cell should be, None outside the picture."""
        col, row = cell
        if not (0 <= col < PICTURE_COLS and 0 <= row < PICTURE_ROWS):
            return None
        key = PICTURES[self.name][row][col]
        return None if key == "." else key

    @property
    def done(self) -> bool:
        return all(self.painted.get((c, r)) == self.target((c, r)) for c in range(PICTURE_COLS)
                   for r in range(PICTURE_ROWS) if self.target((c, r)))

    # ---- geometry ----
    def square_at(self, pt: Point) -> Cell | None:
        col = int((pt[0] - self.origin[0]) // self.square)
        row = int((pt[1] - self.origin[1]) // self.square)
        return (col, row) if 0 <= col < self.cells and 0 <= row < self.cells else None

    def square_origin(self, cell: Cell) -> Point:
        return (self.origin[0] + cell[0] * self.square, self.origin[1] + cell[1] * self.square)

    # ---- interaction ----
    def update(self, pointer: Point | None, touching: bool) -> None:
        self.pointer = pointer
        touching = touching and pointer is not None
        if touching and not self._was_touching:
            self._touch_down(pointer)
        self._was_touching = touching

    def _touch_down(self, pt: Point) -> None:
        cell = self.square_at(pt)
        if cell is None:
            return
        self.notice = ""
        if cell[0] == PALETTE_COL and cell[1] < len(KEYS):
            self.selected = KEYS[cell[1]]
        elif cell == NEXT_CELL:
            self.picture = (self.picture + 1) % len(PICTURES)
            self.new_game()
        elif cell == RESET_CELL:
            self.new_game()
        elif self.target(cell):
            self.painted[cell] = self.selected
            self.revision += 1
            if self.done:
                self.notice = "Well done! Touch the arrow for the next picture."

    @property
    def status(self) -> str:
        return f"Colouring: {self.name}"
