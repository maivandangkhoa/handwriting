"""Stroke state: smoothing, stroke breaking, pause/clear. No Qt, no camera."""
import math

Point = tuple[float, float]


class Smoother:
    """Exponential moving average of 2D points; `reset()` forgets history (use when tracking is lost)."""

    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha
        self.value: Point | None = None

    def reset(self) -> None:
        self.value = None

    def update(self, point: Point) -> Point:
        if self.value is None:
            self.value = point
        else:
            a = self.alpha
            self.value = (a * point[0] + (1 - a) * self.value[0], a * point[1] + (1 - a) * self.value[1])
        return self.value


class DrawingState:
    def __init__(self, smoothing_alpha: float = 1.0):
        self._smoother = Smoother(smoothing_alpha)
        self.strokes: list[list[Point]] = []   # finished and in-progress strokes, canvas coordinates
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
        self._stroke_open = False

    def update(self, point: Point | None) -> Point | None:
        """Feed the latest canvas-space fingertip (None = lost/invalid). Returns the smoothed cursor."""
        if point is None or not all(math.isfinite(v) for v in point):
            self.cursor = None
            self._smoother.reset()
            self.end_stroke()  # never bridge a tracking gap
            return None
        self.cursor = self._smoother.update(point)
        if self._draw_enabled:
            if not self._stroke_open:
                self.strokes.append([])
                self._stroke_open = True
            self.strokes[-1].append(self.cursor)
        return self.cursor
