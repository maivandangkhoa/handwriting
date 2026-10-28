"""Scores the camera's key predictions against the keys really typed (reported by the OS to this window)."""
from dataclasses import dataclass

from . import config

MAX_EVENTS = 500


@dataclass
class EvalStats:
    truth: int = 0
    predicted: int = 0
    correct: int = 0
    wrong: int = 0       # a real keystroke was matched by a prediction of a different key
    missed: int = 0      # a real keystroke with no prediction near it in time
    false_pos: int = 0   # a prediction with no real keystroke near it in time

    @property
    def accuracy(self) -> float | None:
        settled = self.correct + self.wrong + self.missed
        return self.correct / settled if settled else None


class TypingEvaluator:
    def __init__(self, window: float = config.TYPING_EVAL_WINDOW_S):
        self.window = window
        self.clear()

    def clear(self) -> None:
        self._truth: list[tuple[str, float]] = []
        self._pred: list[tuple[str, float]] = []

    def add_truth(self, char: str, t: float) -> None:
        self._truth = (self._truth + [(char, t)])[-MAX_EVENTS:]

    def add_pred(self, char: str, t: float) -> None:
        self._pred = (self._pred + [(char, t)])[-MAX_EVENTS:]

    def stats(self, now: float) -> EvalStats:
        """Greedy match in time order; events younger than the window are still pending and not scored."""
        s = EvalStats(truth=len(self._truth), predicted=len(self._pred))
        used: set[int] = set()
        for char, t in self._truth:
            near = [i for i, (_, pt) in enumerate(self._pred) if i not in used and abs(pt - t) <= self.window]
            same = [i for i in near if self._pred[i][0] == char]
            pick = min(same or near, key=lambda i: abs(self._pred[i][1] - t), default=None)
            if pick is None:
                s.missed += now - t > self.window
                continue
            used.add(pick)
            if self._pred[pick][0] == char:
                s.correct += 1
            else:
                s.wrong += 1
        s.false_pos = sum(1 for i, (_, pt) in enumerate(self._pred) if i not in used and now - pt > self.window)
        return s
