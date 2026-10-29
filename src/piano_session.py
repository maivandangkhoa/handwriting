"""Fingertips -> piano notes. No Qt, no camera.

Same idea as typing: one RGB camera cannot see depth, so a press is a fingertip that travels a little and then stays
still for a moment (PressDetector); resting fingers never sound. Positions are canvas pixels, turned into key units
(one white key = 1) for the detector.
"""
from . import config
from .filters import OneEuroFilter2D
from .piano_layout import WHITE_W, Key, key_at
from .press_detector import PressDetector, scale_for_sensitivity

Point = tuple[float, float]
GLOW_S = 0.3    # how long a struck key stays lit


class PianoSession:
    def __init__(self):
        self.fingertips: dict[str, Point] = {}     # smoothed, canvas px
        self.struck: dict[int, float] = {}         # midi -> time of its last note
        self.last: Key | None = None
        self.count = 0
        self._now = 0.0
        self._filters: dict[str, OneEuroFilter2D] = {}
        self._detector = PressDetector()
        self._detector.scale = scale_for_sensitivity(config.PIANO_SENSITIVITY)

    def reset(self) -> None:
        self.fingertips, self._filters = {}, {}
        self._detector.retain_only(())

    def update(self, points: dict[str, Point], now: float) -> list[Key]:
        """`points`: fingertip id -> canvas px. Returns the keys struck this frame."""
        self._now = now
        self._detector.retain_only(points)
        for fid in set(self._filters) - set(points):
            del self._filters[fid]
        fired: list[Key] = []
        self.fingertips = {}
        for fid, (x, y) in points.items():
            flt = self._filters.setdefault(
                fid, OneEuroFilter2D(config.TYPING_FILTER_MIN_CUTOFF, config.TYPING_FILTER_BETA, clock=lambda: self._now))
            unit = flt.update((x / WHITE_W, y / WHITE_W))
            self.fingertips[fid] = (unit[0] * WHITE_W, unit[1] * WHITE_W)
            if not self._detector.update(fid, unit, now):
                continue
            key = key_at(*self.fingertips[fid])
            if key is not None:
                self.struck[key.midi] = now
                self.last, self.count = key, self.count + 1
                fired.append(key)
        return fired

    def lit(self, now: float) -> set[int]:
        """Keys still glowing from a recent note."""
        return {m for m, t in self.struck.items() if now - t < GLOW_S}

    def under_fingers(self) -> set[int]:
        return {k.midi for p in self.fingertips.values() if (k := key_at(*p)) is not None}
