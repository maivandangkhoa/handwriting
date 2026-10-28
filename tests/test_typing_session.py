from src.keyboard_layout import KEYS
from src.typing_session import TypingSession

DT = 1 / 30


def centre(char):
    k = next(k for k in KEYS if k.char == char)
    return (k.x + k.w / 2, k.y + k.h / 2)


class Typist:
    """Drives one fingertip through travel-then-stop presses at 30 fps."""

    def __init__(self, session, fid="Right-index", start=(7.0, 4.8)):
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
    t2.pos = (0.5, 3.5)                   # shift
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
