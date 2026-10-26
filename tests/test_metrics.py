import pytest

from src.metrics import RateCounter, TimingStat


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_rate_counter_steady_30hz():
    clk = FakeClock()
    r = RateCounter(2.0, clock=clk)
    for _ in range(61):
        r.tick()
        clk.t += 1 / 30
    assert r.rate() == pytest.approx(30, rel=0.05)


def test_rate_counter_decays_to_zero_when_idle():
    clk = FakeClock()
    r = RateCounter(2.0, clock=clk)
    for _ in range(10):
        r.tick(); clk.t += 0.1
    clk.t += 10
    assert r.rate() == 0.0


def test_rate_counter_needs_two_samples():
    r = RateCounter(clock=FakeClock())
    r.tick()
    assert r.rate() == 0.0


def test_timing_stat_moving_average():
    t = TimingStat(size=3)
    assert t.average() == 0.0
    for v in (10, 20, 30, 40):
        t.add(v)
    assert t.average() == pytest.approx(30)
