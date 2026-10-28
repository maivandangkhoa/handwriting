"""Infers key presses from fingertip motion alone (one RGB camera has no usable depth).

Heuristic per fingertip: it must first *travel* (speed above `v_move`, which arms it), then *stop* (speed below
`v_stop`) for `dwell` seconds; that fires one press. It cannot fire again until it moves fast enough to re-arm,
so fingers resting on the keys never type. Positions are in key units, times in seconds.
"""
import math

from . import config

Point = tuple[float, float]
SPEED_EMA = 0.5


class _Finger:
    __slots__ = ("pos", "t", "speed", "armed", "still_since")

    def __init__(self, pos: Point, t: float):
        self.pos, self.t, self.speed = pos, t, 0.0
        self.armed = False
        self.still_since: float | None = None


class PressDetector:
    def __init__(self, v_move: float = config.TYPING_V_MOVE, v_stop: float = config.TYPING_V_STOP,
                 dwell: float = config.TYPING_DWELL_S):
        self.v_move, self.v_stop, self.dwell = v_move, v_stop, dwell
        self._fingers: dict[str, _Finger] = {}

    def forget(self, finger_id: str) -> None:
        self._fingers.pop(finger_id, None)

    def retain_only(self, finger_ids) -> None:
        for fid in set(self._fingers) - set(finger_ids):
            del self._fingers[fid]

    def update(self, finger_id: str, pos: Point, t: float) -> bool:
        """Feed one fingertip sample; True exactly when a press is detected."""
        f = self._fingers.get(finger_id)
        if f is None:
            self._fingers[finger_id] = _Finger(pos, t)
            return False
        dt = t - f.t
        if dt <= 0:
            return False
        inst = math.dist(pos, f.pos) / dt
        f.speed = SPEED_EMA * inst + (1 - SPEED_EMA) * f.speed
        f.pos, f.t = pos, t
        if f.speed > self.v_move:
            f.armed, f.still_since = True, None
        elif f.speed < self.v_stop and f.armed:
            if f.still_since is None:
                f.still_since = t
            if t - f.still_since >= self.dwell:
                f.armed, f.still_since = False, None
                return True
        else:
            f.still_since = None
        return False
