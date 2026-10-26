"""Rate and timing counters for the diagnostics panel."""
import threading
import time
from collections import deque


class RateCounter:
    """Events per second over a sliding time window. Thread-safe."""

    def __init__(self, window_seconds: float = 2.0, clock=time.monotonic):
        self._window = window_seconds
        self._clock = clock
        self._stamps: deque[float] = deque()
        self._lock = threading.Lock()

    def tick(self) -> None:
        now = self._clock()
        with self._lock:
            self._stamps.append(now)
            self._trim(now)

    def rate(self) -> float:
        now = self._clock()
        with self._lock:
            self._trim(now)
            if len(self._stamps) < 2:
                return 0.0
            span = self._stamps[-1] - self._stamps[0]
            return (len(self._stamps) - 1) / span if span > 0 else 0.0

    def reset(self) -> None:
        with self._lock:
            self._stamps.clear()

    def _trim(self, now: float) -> None:
        while self._stamps and now - self._stamps[0] > self._window:
            self._stamps.popleft()


class TimingStat:
    """Moving average of the last N durations in milliseconds. Thread-safe."""

    def __init__(self, size: int = 30):
        self._values: deque[float] = deque(maxlen=size)
        self._lock = threading.Lock()

    def add(self, ms: float) -> None:
        with self._lock:
            self._values.append(ms)

    def average(self) -> float:
        with self._lock:
            return sum(self._values) / len(self._values) if self._values else 0.0

    def reset(self) -> None:
        with self._lock:
            self._values.clear()
