from src.keyboard_layout import KEYS
from src.typing_session import TypingSession

DT = 1 / 30


def centre(char):
    k = next(k for k in KEYS if k.char == char)
    return (k.x + k.w / 2, k.y + k.h / 2)


class Typist:
    """Drives one fingertip through travel-then-stop presses at 30 fps."""

    def __init__(self, session, fid="Right-index", start=(7.0, 5.8)):
        self.s, self.fid, self.pos, self.t = session, fid, start, 0.0
        self.s.update({fid: start}, self.t)

    def step(self, pos):
        self.t += DT
        self.pos = pos
        return self.s.update({self.fid: pos}, self.t)

    def press(self, char, hold=14):
        tx, ty = centre(char)
        x0, y0 = self.pos
        for i in range(1, 7):
            self.step((x0 + (tx - x0) * i / 6, y0 + (ty - y0) * i / 6))
        for _ in range(hold):
            self.step((tx, ty))


def test_types_text_from_fingertip_trajectory():
    s = TypingSession()
    t = Typist(s)
    for ch in "hi k":
        t.press(ch)
    assert s.text == "hi k"


def test_backspace_and_enter():
    s = TypingSession()
    t = Typist(s)
    for ch in "ab\b\n":
        t.press(ch)
    assert s.text == "a\n"


def test_resting_hand_types_nothing():
    s = TypingSession()
    for i in range(120):
        s.update({"Left-index": centre("f"), "Right-index": centre("j")}, i * DT)
    assert s.text == ""


def test_thumb_only_types_space_and_modifiers_type_nothing():
    s = TypingSession()
    t = Typist(s, fid="Left-thumb")
    t.press("f")                          # thumb over a letter: ignored
    assert s.text == ""
    t.press(" ")
    assert s.text == " "
    t2 = Typist(s, fid="Right-index")
    t2.pos = (0.5, 4.5)                   # shift
    t2.press("\t")
    assert s.text == " \t"


def test_outside_keyboard_is_ignored_and_lost_finger_is_forgotten():
    s = TypingSession()
    t = Typist(s, start=(20.0, 9.0))
    t.pos = (20.0, 9.0)
    t.press("a")                          # travels from outside to a: fires
    n = len(s.text)
    s.update({}, t.t + DT)                # hand disappears
    assert s.fingertips == {} and n == 1


def test_real_keys_feed_ground_truth():
    s = TypingSession()
    s.real_key("a", 1.0); s.real_key("b", 1.1); s.real_key("\b", 1.2)
    assert s.actual_text == "a"
    assert s.evaluator.stats(10.0).truth == 3


def test_resting_hand_with_landmark_jitter_types_nothing_at_default_sensitivity():
    import random
    rng = random.Random(7)
    s = TypingSession()
    base = {"hand0-index": centre("f"), "hand1-index": centre("j")}
    for i in range(30 * 20):  # 20 s at 30 fps, +-0.04 key units of jitter
        s.update({k: (x + rng.gauss(0, 0.04), y + rng.gauss(0, 0.04)) for k, (x, y) in base.items()}, i * DT)
    assert s.text == ""


def test_higher_sensitivity_catches_a_tap_the_base_setting_misses():
    def type_tiny_tap(level):
        s = TypingSession()
        s.set_sensitivity(level)
        t = Typist(s, start=centre("f"))
        t.pos = centre("f")
        for _ in range(10):
            t.step(t.pos)
        x, y = t.pos
        for i in range(6):                                  # drift 0.22 key units away over 0.2 s
            t.step((x + 0.22 * (i + 1) / 6, y))
        for i in range(6):
            t.step((x + 0.22 * (1 - (i + 1) / 6), y))
        for _ in range(12):
            t.step((x, y))
        return s.text
    assert type_tiny_tap(5) == "" and type_tiny_tap(8) == "f"
