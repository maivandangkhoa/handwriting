from src.press_detector import PressDetector

DT = 1 / 30


def run(det, fid, path, t0=0.0):
    """Feed positions at 30 fps; return the times (relative index) at which a press fired."""
    return [i for i, p in enumerate(path) if det.update(fid, p, t0 + i * DT)]


def travel_then_stop(x0=0.0, x1=6.0, travel=6, stop=12):
    move = [(x0 + (x1 - x0) * (i + 1) / travel, 1.0) for i in range(travel)]
    return [(x0, 1.0)] + move + [(x1, 1.0)] * stop


def test_travel_then_stop_fires_once_after_dwell():
    fires = run(PressDetector(dwell=0.12), "R-index", travel_then_stop())
    assert len(fires) == 1


def test_resting_finger_never_fires():
    assert run(PressDetector(), "R-index", [(3.0, 1.0)] * 90) == []


def test_new_finger_must_travel_before_it_can_fire():
    det = PressDetector()
    assert run(det, "a", [(2.0, 1.0)] * 30) == []


def test_holding_still_does_not_repeat_but_moving_again_re_arms():
    det = PressDetector(dwell=0.12)
    path = travel_then_stop() + [(6.0, 1.0)] * 30 + [(6.0 + 0.8 * (i + 1), 1.0) for i in range(5)] + [(10.0, 1.0)] * 12
    assert len(run(det, "a", path)) == 2


def test_slow_drift_does_not_fire():
    drift = [(0.3 * i * DT * 3, 1.0) for i in range(120)]    # ~0.9 u/s: the anchor keeps up with it
    assert run(PressDetector(), "a", drift) == []


def test_fingers_are_independent_and_forget_resets():
    det = PressDetector(dwell=0.12)
    a, b = travel_then_stop(), travel_then_stop(10.0, 14.0)
    fires_a = fires_b = 0
    for i in range(len(a)):
        fires_a += det.update("a", a[i], i * DT)
        fires_b += det.update("b", b[i], i * DT)
    assert (fires_a, fires_b) == (1, 1)
    det.forget("a")
    assert run(det, "a", [(6.0, 1.0)] * 20, t0=10.0) == []   # fresh state: unarmed


def test_retain_only_drops_missing_fingers():
    det = PressDetector()
    det.update("a", (0, 0), 0.0)
    det.update("b", (0, 0), 0.0)
    det.retain_only({"b"})
    assert "a" not in det._fingers and "b" in det._fingers


def small_tap(x=5.0, out=0.4, steps=6):
    """Rest, move `out` units away, come back, rest."""
    path = [(x, 1.0)] * 10
    path += [(x + out * (i + 1) / steps, 1.0) for i in range(steps)]
    path += [(x + out * (1 - (i + 1) / steps), 1.0) for i in range(steps)]
    return path + [(x, 1.0)] * 12


def test_small_out_and_back_tap_fires():
    assert len(run(PressDetector(dwell=0.12), "a", small_tap())) == 1


def test_small_tap_is_ignored_when_it_does_not_leave_the_resting_spot():
    assert run(PressDetector(dwell=0.12, arm_dist=99.0), "a", small_tap()) == []   # arm distance out of reach


def test_repeated_same_key_taps_each_fire():
    path = small_tap() + small_tap()
    assert len(run(PressDetector(dwell=0.12), "a", path)) == 2


def test_scale_makes_smaller_movements_count():
    tiny = small_tap(out=0.2)                       # 0.2 u < arm_dist 0.35
    strict, sensitive = PressDetector(dwell=0.12), PressDetector(dwell=0.12)
    sensitive.scale = 0.5
    assert run(strict, "a", tiny) == [] and len(run(sensitive, "a", tiny)) == 1


def test_scale_for_sensitivity_mapping():
    from src.press_detector import scale_for_sensitivity
    assert scale_for_sensitivity(5) == 1.0
    assert scale_for_sensitivity(10) < scale_for_sensitivity(7) < 1.0 < scale_for_sensitivity(3) < scale_for_sensitivity(1)
    assert 0.25 < scale_for_sensitivity(10) < 0.35
