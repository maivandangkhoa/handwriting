import math

import pytest

from src.calibration import CalibrationError, CoordinateMapper, validate_points

FRAME = (1000, 500)
CANVAS = (1280, 720)
# A fingertip quad as seen in the *view* (screen-like orientation): TL, TR, BR, BL
GOOD = [(200, 100), (800, 120), (780, 400), (220, 380)]


def mapper(mirror=False):
    return CoordinateMapper(FRAME, CANVAS, mirror=mirror)


def test_linear_fallback_center_and_corners():
    m = mapper()
    assert not m.calibrated
    assert m.map((500, 250)) == pytest.approx((640, 360))
    assert m.map((0, 0)) == pytest.approx((0, 0))
    assert m.map((1000, 500)) == pytest.approx((1280, 720))


def test_moving_finger_left_moves_cursor_left_mirrored():
    # Mirrored preview behaves like a mirror: the user's left is the image's left.
    # Raw camera x grows towards the user's left, so raw x increasing => view x decreasing.
    m = mapper(mirror=True)
    a, b = m.map((400, 250)), m.map((600, 250))
    assert b[0] < a[0]


def test_moving_finger_right_moves_cursor_right_unmirrored():
    m = mapper(mirror=False)
    a, b = m.map((400, 250)), m.map((600, 250))
    assert b[0] > a[0]


def test_mirror_maps_symmetrically():
    x_m = mapper(mirror=True).map((100, 250))[0]
    x_u = mapper(mirror=False).map((900, 250))[0]
    assert x_m == pytest.approx(x_u)


def test_calibration_maps_quad_corners_to_canvas_corners():
    m = mapper()
    m.calibrate(GOOD)
    assert m.calibrated
    for raw, expect in zip(GOOD, [(0, 0), (1280, 0), (1280, 720), (0, 720)]):
        assert m.map(raw) == pytest.approx(expect, abs=1e-2)


def test_calibration_with_mirror_uses_view_coordinates():
    m = mapper(mirror=True)
    raw_quad = [m.to_view(p) for p in GOOD]  # to_view is its own inverse
    m.calibrate(GOOD)
    assert m.map(raw_quad[0]) == pytest.approx((0, 0), abs=1e-2)
    assert m.map(raw_quad[2]) == pytest.approx((1280, 720), abs=1e-2)


def test_points_outside_quad_are_clamped():
    m = mapper()
    m.calibrate(GOOD)
    x, y = m.map((0, 0))
    assert 0 <= x <= 1280 and 0 <= y <= 720


def test_changing_mirror_or_frame_size_resets_calibration():
    m = mapper()
    m.calibrate(GOOD)
    m.set_mirror(True)
    assert not m.calibrated
    m.set_mirror(False)
    m.calibrate(GOOD)
    m.set_frame_size((640, 480))
    assert not m.calibrated


def test_reset_returns_to_fallback():
    m = mapper()
    m.calibrate(GOOD)
    m.reset()
    assert not m.calibrated


def test_rejects_near_duplicate_points():
    pts = [GOOD[0], GOOD[0], GOOD[2], GOOD[3]]
    with pytest.raises(CalibrationError, match="too close"):
        validate_points(pts, FRAME)


def test_rejects_bad_ordering():
    pts = [GOOD[0], GOOD[2], GOOD[1], GOOD[3]]  # bow-tie
    with pytest.raises(CalibrationError, match="order"):
        validate_points(pts, FRAME)


def test_rejects_collinear_degenerate_quad():
    pts = [(100, 100), (300, 100), (600, 100), (900, 100)]
    with pytest.raises(CalibrationError):
        validate_points(pts, FRAME)


def test_rejects_tiny_area():
    pts = [(500, 250), (540, 250), (540, 290), (500, 290)]
    with pytest.raises(CalibrationError):
        validate_points(pts, FRAME)


def test_rejects_wrong_point_count():
    with pytest.raises(CalibrationError):
        validate_points(GOOD[:3], FRAME)


def test_non_finite_input_returns_none():
    assert mapper().map((math.nan, 10)) is None


def test_flip_vertical_moves_cursor_down_when_raw_y_decreases():
    m = CoordinateMapper(FRAME, CANVAS, mirror=False, flip_vertical=True)
    a, b = m.map((500, 200)), m.map((500, 100))
    assert b[1] > a[1]
    assert m.map((500, 0))[1] == pytest.approx(720)


def test_changing_flip_vertical_resets_calibration():
    m = mapper()
    m.calibrate(GOOD)
    m.set_flip_vertical(True)
    assert not m.calibrated
