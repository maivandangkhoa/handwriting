"""Stable per-hand ids across frames, assigned by wrist proximity.

MediaPipe's Left/Right label is unreliable when the camera looks down at the hands (both can get the same label),
so fingertip identities must not depend on it.
"""
import math

Point = tuple[float, float]


class HandSlots:
    def __init__(self, max_slots: int = 2, max_jump: float = 5.0):
        self.max_slots = max_slots
        self.max_jump = max_jump          # a wrist moving farther than this between frames is treated as another hand
        self._prev: dict[int, Point] = {}

    def reset(self) -> None:
        self._prev = {}

    def assign(self, wrists: list[Point]) -> list[int | None]:
        """Slot id for each wrist (None if more hands than slots). A hand keeps its slot while it stays close."""
        ids: list[int | None] = [None] * len(wrists)
        taken: set[int] = set()
        pairs = sorted((math.dist(w, p), i, slot) for i, w in enumerate(wrists) for slot, p in self._prev.items())
        for dist, i, slot in pairs:
            if dist <= self.max_jump and ids[i] is None and slot not in taken:
                ids[i] = slot
                taken.add(slot)
        free = [s for s in range(self.max_slots) if s not in taken]
        for i in range(len(wrists)):
            if ids[i] is None and free:
                ids[i] = free.pop(0)
        self._prev = {slot: wrists[i] for i, slot in enumerate(ids) if slot is not None}
        return ids
