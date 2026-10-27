import pytest

from src.filters import OneEuroFilter2D


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, dt=1 / 30):
        self.t += dt


def run(f, clk, points):
    out = []
    for p in points:
        out.append(f.update(p))
        clk.advance()
    return out


def test_first_sample_passes_through_and_reset_forgets():
    clk = Clock()
    f = OneEuroFilter2D(clock=clk)
    assert f.update((10, 20)) == (10, 20)
    run(f, clk, [(50, 50)] * 5)
    f.reset()
    assert f.update((300, 300)) == (300, 300)


def test_constant_input_converges():
    clk = Clock()
    f = OneEuroFilter2D(clock=clk)
    out = run(f, clk, [(0, 0)] + [(100, 100)] * 120)
    assert out[-1] == pytest.approx((100, 100), abs=0.5)


def test_jitter_at_rest_is_attenuated():
    clk = Clock()
    f = OneEuroFilter2D(min_cutoff=1.0, beta=0.0, clock=clk)
    noisy = [(100 + (3 if i % 2 else -3), 100) for i in range(60)]
    out = run(f, clk, noisy)
    assert max(abs(x - 100) for x, _ in out[30:]) < 1.5   # raw jitter is +-3


def test_fast_motion_has_less_lag_with_beta():
    def lag(beta):
        clk = Clock()
        f = OneEuroFilter2D(min_cutoff=1.0, beta=beta, clock=clk)
        pts = [(i * 30.0, 0) for i in range(60)]           # 900 px/s
        out = run(f, clk, pts)
        return pts[-1][0] - out[-1][0]
    assert lag(beta=0.05) < lag(beta=0.0) / 2


def test_zero_dt_does_not_crash():
    f = OneEuroFilter2D(clock=lambda: 5.0)
    f.update((0, 0))
    assert f.update((10, 10)) is not None
