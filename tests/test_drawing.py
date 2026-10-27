import math

from src.drawing import DrawingState


def test_points_extend_one_stroke():
    s = DrawingState()
    for x in range(3):
        s.update((x, 0))
    assert s.strokes == [[(0, 0), (1, 0), (2, 0)]]


def test_losing_hand_breaks_stroke_without_bridge():
    s = DrawingState()
    s.update((0, 0)); s.update((1, 0))
    assert s.update(None) is None and s.cursor is None
    s.update((900, 700)); s.update((901, 700))
    assert len(s.strokes) == 2
    assert s.strokes[0] == [(0, 0), (1, 0)]
    assert s.strokes[1][0] == (900, 700)  # smoothing must not drag the new start towards the old point


def test_disabled_draws_nothing_but_tracks_cursor():
    s = DrawingState()
    s.set_draw_enabled(False)
    assert s.update((5, 5)) == (5, 5)
    assert s.strokes == []


def test_pause_breaks_stroke_and_resume_starts_new_one():
    s = DrawingState()
    s.update((0, 0)); s.update((1, 1))
    s.set_draw_enabled(False)
    s.update((500, 500))
    s.set_draw_enabled(True)
    s.update((501, 501))
    assert len(s.strokes) == 2
    assert s.strokes[1] == [(501, 501)] or s.strokes[1][0] != (1, 1)
    assert all(math.dist(a, b) < 5 for st in s.strokes for a, b in zip(st, st[1:]))


def test_clear_removes_everything_and_next_point_starts_fresh():
    s = DrawingState()
    s.update((0, 0)); s.update((1, 1))
    s.clear()
    assert s.strokes == []
    s.update((2, 2))
    assert s.strokes == [[(2, 2)]]


class HalfStep:
    """Deterministic smoother: moves halfway to each new point."""

    def __init__(self):
        self.value = None

    def reset(self):
        self.value = None

    def update(self, point):
        self.value = point if self.value is None else tuple((a + b) / 2 for a, b in zip(point, self.value))
        return self.value


def test_smoother_is_used_and_reset_when_tracking_is_lost():
    s = DrawingState(HalfStep())
    s.update((0, 0))
    assert s.update((10, 0)) == (5, 0)
    s.update(None)
    assert s.update((100, 0)) == (100, 0)   # history forgotten: no drag from the old position


def test_pen_up_moves_cursor_without_drawing_and_ends_stroke():
    s = DrawingState()
    s.update((0, 0)); s.update((1, 0))
    assert s.update((50, 50), pen_down=False) == (50, 50)
    assert s.strokes == [[(0, 0), (1, 0)]]
    s.update((51, 50)); s.update((52, 50))
    assert len(s.strokes) == 2 and s.strokes[1] == [(51, 50), (52, 50)]


def test_non_finite_point_treated_as_lost():
    s = DrawingState()
    s.update((0, 0))
    assert s.update((math.nan, 1)) is None
    s.update((3, 3))
    assert len(s.strokes) == 2
