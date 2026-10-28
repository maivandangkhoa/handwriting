import numpy as np

from src.hand_tracker import Detection
from src.keyboard_layout import KEYS
from src.typing_mode import TypingMode

DT = 1 / 30
PX = 100.0  # frame pixels per key unit in this synthetic setup


def make_mode():
    tm = TypingMode((1450, 600), mirror=False, flip_vertical=False)
    tm.mapper.calibrate([(0, 0), (1450, 0), (1450, 600), (0, 600)])   # view px = layout units * 100
    return tm


def centre(char):
    k = next(k for k in KEYS if k.char == char)
    return ((k.x + k.w / 2) * PX, (k.y + k.h / 2) * PX)


def hand(index_tip, wrist):
    lm = np.full((21, 2), -500.0, dtype=np.float32)   # all other landmarks parked off the keyboard
    lm[0], lm[8] = wrist, index_tip
    return lm


def test_two_hands_with_the_same_handedness_label_both_type():
    tm = make_mode()
    pos = [centre(" "), centre(" ")]
    wrist = [(300.0, 560.0), (1000.0, 560.0)]
    t = 0.0

    def frame(p0, p1):
        nonlocal t
        det = Detection(None, 2, 5.0, [hand(p0, wrist[0]), hand(p1, wrist[1])], ["Right", "Right"])  # label clash
        tm.on_detection(det, t)
        t += DT

    for _ in range(3):
        frame(*pos)
    targets = [centre("a"), centre("l")]
    for i in range(1, 7):
        frame(*[(p[0] + (q[0] - p[0]) * i / 6, p[1] + (q[1] - p[1]) * i / 6) for p, q in zip(pos, targets)])
    for _ in range(14):
        frame(*targets)
    assert sorted(tm.session.text) == ["a", "l"]


def test_not_ready_types_nothing_and_clears_fingertips():
    tm = TypingMode((1450, 600), mirror=False, flip_vertical=False)   # never calibrated
    det = Detection(None, 1, 5.0, [hand(centre("a"), (300.0, 560.0))], ["Left"])
    tm.on_detection(det, 0.0)
    assert tm.session.text == "" and tm.session.fingertips == {}
