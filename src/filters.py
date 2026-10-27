"""One Euro filter (Casiez et al., CHI 2012) for 2D points: heavy smoothing when slow, little lag when fast."""
import math
import time
from collections.abc import Callable

from . import config

Point = tuple[float, float]
FALLBACK_DT = 1 / 30


def _alpha(cutoff: float, dt: float) -> float:
    tau = 1.0 / (2 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


class OneEuroFilter2D:
    """`update(point)` returns the filtered point; `reset()` forgets history (call when tracking is lost).

    min_cutoff: jitter control at rest (Hz, lower = smoother). beta: how fast the cutoff opens with speed
    (higher = less lag when moving). Units follow the input (canvas pixels per second here).
    """

    def __init__(self, min_cutoff: float = config.ONE_EURO_MIN_CUTOFF, beta: float = config.ONE_EURO_BETA,
                 d_cutoff: float = 1.0, clock: Callable[[], float] = time.monotonic):
        self.min_cutoff, self.beta, self.d_cutoff = min_cutoff, beta, d_cutoff
        self._clock = clock
        self.reset()

    def reset(self) -> None:
        self._x: Point | None = None        # last filtered position
        self._raw: Point | None = None      # last raw position
        self._dx: Point = (0.0, 0.0)        # filtered velocity
        self._t: float | None = None

    def update(self, point: Point) -> Point:
        now = self._clock()
        if self._x is None:
            self._x, self._raw, self._t = point, point, now
            return point
        dt = now - self._t
        if dt <= 0:
            dt = FALLBACK_DT
        self._t = now
        a_d = _alpha(self.d_cutoff, dt)
        raw_v = ((point[0] - self._raw[0]) / dt, (point[1] - self._raw[1]) / dt)
        self._dx = (a_d * raw_v[0] + (1 - a_d) * self._dx[0], a_d * raw_v[1] + (1 - a_d) * self._dx[1])
        a = _alpha(self.min_cutoff + self.beta * math.hypot(*self._dx), dt)
        self._x = (a * point[0] + (1 - a) * self._x[0], a * point[1] + (1 - a) * self._x[1])
        self._raw = point
        return self._x
