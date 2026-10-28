"""Infers key presses from fingertip motion alone (one RGB camera has no usable depth).

Purely spatial, so it does not depend on how noisy the landmarks are in speed terms. Per fingertip:
1. *Armed* when it leaves its resting spot by more than `arm_dist`. The resting spot, the "anchor", follows a finger
   only while it is nearly still or drifting slowly (below `FOLLOW_SPEED`), so jitter and slow repositioning cannot
   arm it, while travelling to a key or a small tap can.
2. Once armed it *fires* when it stays within `still_radius` for `dwell` seconds: one press on the key under it.
3. It cannot fire again until it is armed again, so fingers resting on the keys never type.
Positions are in key units, times in seconds. `scale` multiplies the distances and the follow speed (below 1 = more
sensitive).
"""
import math

from . import config

Point = tuple[float, float]
ANCHOR_TAU = 0.3    # s: how slowly the resting anchor follows the fingertip
FOLLOW_SPEED = 1.2  # key units/s: faster than this and the anchor stays put (the finger is really moving)
SPEED_EMA = 0.5


def scale_for_sensitivity(level: float) -> float:
    """Distance multiplier for a 1..10 sensitivity level: 5 -> 1.0, 10 -> ~0.3, 1 -> ~2.7."""
    return 3.0 ** ((5.0 - level) / 4.5)


class _Finger:
    __slots__ = ("anchor", "pos", "t", "speed", "armed", "still_pos", "still_since")

    def __init__(self, pos: Point, t: float):
        self.anchor, self.pos, self.t, self.speed = pos, pos, t, 0.0
        self.armed = False
        self.still_pos: Point = pos
        self.still_since = t


class PressDetector:
    def __init__(self, arm_dist: float = config.TYPING_ARM_DIST, still_radius: float = config.TYPING_STILL_RADIUS,
                 dwell: float = config.TYPING_DWELL_S):
        self.arm_dist, self.still_radius, self.dwell = arm_dist, still_radius, dwell
        self.scale = 1.0
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
        f.speed = SPEED_EMA * (math.dist(pos, f.pos) / dt) + (1 - SPEED_EMA) * f.speed
        f.pos, f.t = pos, t
        if not f.armed:
            if math.dist(pos, f.anchor) > self.arm_dist * self.scale:
                f.armed, f.still_pos, f.still_since = True, pos, t
            elif f.speed < FOLLOW_SPEED * self.scale:
                k = 1.0 - math.exp(-dt / ANCHOR_TAU)
                f.anchor = (f.anchor[0] + k * (pos[0] - f.anchor[0]), f.anchor[1] + k * (pos[1] - f.anchor[1]))
            return False
        if math.dist(pos, f.still_pos) > self.still_radius * self.scale:
            f.still_pos, f.still_since = pos, t     # still moving: restart the dwell clock here
            return False
        if t - f.still_since >= self.dwell:
            f.armed, f.anchor = False, pos
            return True
        return False
