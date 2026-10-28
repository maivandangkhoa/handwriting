"""Typing state: fingertips -> key presses -> text. No Qt, no camera."""
from collections.abc import Callable

from . import config
from .filters import OneEuroFilter2D
from .keyboard_layout import Key, key_at
from .press_detector import PressDetector
from .typing_eval import TypingEvaluator

Point = tuple[float, float]

# MediaPipe fingertip landmarks: 4 thumb, 8 index, 12 middle, 16 ring, 20 pinky.
FINGERTIPS = {"thumb": 4, "index": 8, "middle": 12, "ring": 16, "pinky": 20}


class TypingSession:
    def __init__(self):
        self.text = ""             # what the camera "typed"
        self.actual_text = ""      # what the real keyboard typed (ground truth, for comparison)
        self.evaluator = TypingEvaluator()
        self.fingertips: dict[str, Point] = {}   # smoothed positions in key units
        self.last_fired: tuple[Key, float] | None = None
        self._now = 0.0
        self._clock: Callable[[], float] = lambda: self._now
        self._filters: dict[str, OneEuroFilter2D] = {}
        self._detector = PressDetector()

    def clear(self) -> None:
        self.text = self.actual_text = ""
        self.evaluator.clear()
        self.last_fired = None

    def update(self, points: dict[str, Point], now: float) -> list[Key]:
        """`points`: fingertip id ("Left-index", ...) -> position in key units. Returns the keys fired this frame."""
        self._now = now
        self._detector.retain_only(points)
        for fid in set(self._filters) - set(points):
            del self._filters[fid]
        fired: list[Key] = []
        self.fingertips = {}
        for fid, pt in points.items():
            flt = self._filters.setdefault(
                fid, OneEuroFilter2D(config.TYPING_FILTER_MIN_CUTOFF, config.TYPING_FILTER_BETA, clock=self._clock))
            smooth = flt.update(pt)
            self.fingertips[fid] = smooth
            if not self._detector.update(fid, smooth, now):
                continue
            key = key_at(*smooth)
            if key is None or key.char is None or (fid.endswith("thumb") and key.char != " "):
                continue  # outside the keyboard, a modifier, or a thumb away from the space bar
            self._apply(key.char)
            self.evaluator.add_pred(key.char, now)
            self.last_fired = (key, now)
            fired.append(key)
        return fired

    def real_key(self, char: str, now: float) -> None:
        """A keystroke reported by the OS (already reduced to its layout character)."""
        self.actual_text = self.actual_text[:-1] if char == "\b" else self.actual_text + char
        self.evaluator.add_truth(char, now)

    def active_keys(self) -> set[Key]:
        return {k for p in self.fingertips.values() if (k := key_at(*p)) is not None}

    def _apply(self, char: str) -> None:
        self.text = self.text[:-1] if char == "\b" else self.text + char
