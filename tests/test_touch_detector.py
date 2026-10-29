import numpy as np
import pytest

from src import config
from src.touch_detector import ShadowTouchDetector
from tests import scene

LM = scene.hand_landmarks()
TOUCH_H, HOVER_H = 0, 35     # fingertip height (scene pixels) for the two reference poses


def learned(frames=40):
    d = ShadowTouchDetector()
    t = 0.0
    for i in range(frames):
        d.observe_empty(scene.board(i), t)
        t += 1 / 30
    return d


def score(d, height, seed=100):
    return d.measure(scene.render(height, seed=seed), LM)


def calibrated():
    d = learned()
    assert d.set_references(score(d, TOUCH_H).score, score(d, HOVER_H).score)
    return d


def test_background_needs_the_hand_away_first():
    d = ShadowTouchDetector()
    d.observe_empty(scene.board(0), 0.0)
    d.observe_empty(scene.board(1), config.BACKGROUND_EMPTY_S - 0.05)
    assert not d.ready
    t = config.BACKGROUND_EMPTY_S
    for i in range(config.BACKGROUND_FRAMES):
        d.observe_empty(scene.board(i), t + i / 30)
    assert d.ready


def test_not_ready_without_background():
    s = ShadowTouchDetector().measure(scene.render(0), LM)
    assert not s.ready and not s.touching and s.score is None


def test_score_grows_as_the_finger_lifts():
    d = learned()
    scores = [score(d, h).score for h in (0, 8, 16, 24, 35)]
    assert scores == sorted(scores) and scores[-1] > scores[0] + config.TOUCH_MIN_CONTRAST


def test_dark_squares_alone_are_not_shadow():
    d = learned()
    s = d.measure(scene.render(0, shadow=False, hand=False), LM)
    assert s.score < 0.01 and s.near is None


def test_touch_and_hover_classification():
    d = calibrated()
    for k in range(3):
        s = score(d, TOUCH_H, seed=200 + k)
    assert s.touching
    for h in (20, 30, 35):
        assert not score(d, h).touching, h


def test_hysteresis_keeps_touch_through_small_changes_then_releases():
    d = calibrated()
    for k in range(3):
        score(d, 0, seed=300 + k)
    assert score(d, 4).touching          # slightly higher than the on-threshold: still down
    assert not score(d, 30).touching


def test_high_hover_is_not_a_touch_even_though_the_local_score_falls_again():
    d = calibrated()
    for h in (90, 130, 200):
        s = score(d, h)
        assert not s.touching and (s.near is None or s.near > config.TOUCH_NEAR_MAX), h


def test_no_hand_shadow_visible_means_no_touch():
    d = calibrated()
    for k in range(4):
        s = d.measure(scene.render(0, shadow=False, seed=400 + k), LM)
    assert not s.touching


def test_touch_needs_a_confirmed_streak():
    d = calibrated()
    assert not score(d, 0).touching       # first frame only
    assert score(d, 0, seed=101).touching


def test_global_exposure_change_is_not_shadow():
    d = calibrated()
    dim = (scene.render(HOVER_H, seed=7) * 0.7).astype(np.uint8)    # auto-exposure darkens the whole frame
    s = d.measure(dim, LM)
    ref = score(d, HOVER_H, seed=7)
    assert abs(s.score - ref.score) < 0.03


def test_references_too_alike_are_rejected():
    d = learned()
    assert not d.set_references(0.10, 0.10 + config.TOUCH_MIN_CONTRAST / 2)
    assert not d.calibrated


def test_invalidate_forgets_the_scene_but_keeps_thresholds():
    d = calibrated()
    d.invalidate()
    assert not d.ready and d.calibrated
    assert not d.measure(scene.render(0), LM).ready


def test_region_limits_the_search():
    d = learned()
    d.set_region([(0, 0), (100, 0), (100, 100), (0, 100)])     # nowhere near the hand
    s = score(d, HOVER_H)
    assert s.score == pytest.approx(0.0, abs=1e-6)


# ---- a projector that is weak against the room light: it adds 12..30 levels to a wall already at 150 ----
AMBIENT = 150


def weak(height, seed=100, **kw):
    projected = (scene.render(height, seed=seed, hand=False, **kw).astype(np.float32) - 95) * (30 / 110) + 12
    return np.clip(projected + AMBIENT, 0, 255).astype(np.uint8)


def weak_learned(ambient=True):
    d = ShadowTouchDetector()
    if ambient:
        d.set_ambient(np.full((scene.H, scene.W, 3), AMBIENT, np.uint8))
    for i in range(40):
        d.observe_empty(weak(0, seed=i, shadow=False), i / 30)
    return d


def test_weak_projector_shadow_is_invisible_without_the_room_light_frame():
    d = weak_learned(ambient=False)
    assert d.measure(weak(35), LM).score < 0.01


def test_weak_projector_shadow_is_seen_with_the_room_light_frame():
    d = weak_learned()
    near, far = d.measure(weak(0), LM).score, d.measure(weak(35), LM).score
    assert far > near + config.TOUCH_MIN_CONTRAST
    assert d.set_references(near, far)


def test_weak_projector_no_shadow_means_no_score():
    d = weak_learned()
    assert d.measure(weak(0, seed=9, shadow=False), LM).score < 0.01
