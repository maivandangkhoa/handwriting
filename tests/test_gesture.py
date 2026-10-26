import numpy as np

from src.gesture import PinchDetector, pinch_point, pinch_ratio


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
