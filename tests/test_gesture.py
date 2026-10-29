import numpy as np

from src.gesture import PinchDetector, PointDetector, index_extension, pinch_point, pinch_ratio


def hand(thumb_index_gap: float) -> np.ndarray:
    lm = np.zeros((21, 2), dtype=np.float32)
    lm[0] = (100, 200)            # wrist
    lm[9] = (100, 100)            # middle MCP -> palm length 100
    lm[4] = (100, 50)             # thumb tip
    lm[8] = (100 + thumb_index_gap, 50)
    return lm


def test_ratio_is_scale_independent():
    assert np.isclose(pinch_ratio(hand(20)), 0.2)
    assert np.isclose(pinch_ratio(hand(20) * 3), 0.2)


def test_pinch_point_is_midpoint():
    assert pinch_point(hand(20)) == (110.0, 50.0)


def test_hysteresis():
    d = PinchDetector(on_ratio=0.3, off_ratio=0.5)
    assert not d.update(hand(40))        # 0.4: above on-threshold
    assert d.update(hand(20))            # 0.2: pinch
    assert d.update(hand(40))            # 0.4: still pinching (between thresholds)
    assert not d.update(hand(60))        # 0.6: released
    assert not d.update(hand(40))        # 0.4: must go below on-threshold again


def test_lost_hand_releases():
    d = PinchDetector()
    d.update(hand(10))
    assert not d.update(None)


def index(tip_y: float) -> np.ndarray:
    """Index finger: knuckle 80 px above the wrist, fingertip at tip_y (smaller = further out)."""
    lm = np.zeros((21, 2), dtype=np.float32)
    lm[0], lm[5], lm[8] = (100, 200), (100, 120), (100, tip_y)
    return lm


def test_extension_is_large_when_straight_and_small_when_curled_and_scale_free():
    assert index_extension(index(20)) > 2 and index_extension(index(150)) < 1
    assert np.isclose(index_extension(index(20)), index_extension(index(20) * 3))


def test_point_hysteresis_lifts_early_and_needs_a_clear_straightening_to_draw_again():
    d = PointDetector(on_ratio=1.75, off_ratio=1.5)
    assert not d.update(index(70))        # 1.6: half bent, not drawing yet
    assert d.update(index(40))            # 2.0: straight
    assert d.update(index(60))            # 1.75: still drawing
    assert not d.update(index(85))        # 1.44: curled enough: pen up
    assert not d.update(index(70))        # 1.6: must straighten properly before drawing again


def test_lost_hand_lifts_the_pen():
    d = PointDetector()
    d.update(index(20))
    assert not d.update(None)
