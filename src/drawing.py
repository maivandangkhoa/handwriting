"""Stroke state: smoothing, stroke breaking, pen up/down, pause/clear. No Qt, no camera."""
import math
from typing import Protocol

Point = tuple[float, float]
Color = tuple[int, int, int]
DEFAULT_COLOR: Color = (90, 230, 255)


class Smoother(Protocol):
    def update(self, point: Point) -> Point: ...
    def reset(self) -> None: ...


class DrawingState:
    def __init__(self, smoother: Smoother | None = None):
        self._smoother = smoother  # None = no smoothing
        self.strokes: list[list[Point]] = []   # finished and in-progress strokes, canvas coordinates
        self.colors: list[Color] = []          # colour of each stroke (used where the canvas is lit ink on black)
        self.color: Color = DEFAULT_COLOR      # colour of the next stroke
        self.cursor: Point | None = None       # smoothed fingertip position, None when tracking is lost
        self._draw_enabled = True
        self._stroke_open = False

    @property
    def draw_enabled(self) -> bool:
        return self._draw_enabled

    def set_draw_enabled(self, enabled: bool) -> None:
        self._draw_enabled = enabled
        if not enabled:
            self.end_stroke()

    def end_stroke(self) -> None:
        self._stroke_open = False

    def clear(self) -> None:
        self.strokes.clear()
        self.colors.clear()
        self._stroke_open = False

    def update(self, point: Point | None, pen_down: bool = True) -> Point | None:
        """Feed the latest canvas-space pointer (None = lost/invalid). Returns the smoothed cursor.

        `pen_down=False` (e.g. fingers not pinched) moves the cursor without drawing and ends the stroke.
        """
        if point is None or not all(math.isfinite(v) for v in point):
            self.cursor = None
            if self._smoother:
                self._smoother.reset()
            self.end_stroke()  # never bridge a tracking gap
            return None
        self.cursor = self._smoother.update(point) if self._smoother else point
        if not pen_down:
            self.end_stroke()
        elif self._draw_enabled:
            if not self._stroke_open:
                self.strokes.append([])
                self.colors.append(self.color)
                self._stroke_open = True
            self.strokes[-1].append(self.cursor)
        return self.cursor
