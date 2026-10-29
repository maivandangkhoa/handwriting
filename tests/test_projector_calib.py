import cv2
import numpy as np
import pytest

from src.calibration import CoordinateMapper
from src.projector_calib import MarkerError, find_markers, marker_centres, order_corners

CANVAS = (1280, 720)
CAM = (1280, 720)
ORIGIN, SQUARE = (336, 56), 76
RADIUS = 24
# canvas corners as the camera sees them (perspective, slightly rotated)
SEEN = np.float32([(200, 100), (1090, 70), (1150, 650), (130, 620)])


def disc_in_camera(index: int) -> tuple[int, int]:
    h = cv2.getPerspectiveTransform(np.float32([(0, 0), (CANVAS[0], 0), CANVAS, (0, CANVAS[1])]), SEEN)
    x, y = cv2.perspectiveTransform(np.float32([[marker_centres(ORIGIN, SQUARE)[index]]]), h)[0, 0]
    return int(x), int(y)


def camera(pattern: str, ambient: float = 40.0, seed: int = 0) -> np.ndarray:
    canvas = np.zeros((CANVAS[1], CANVAS[0], 3), np.uint8)
    if pattern == "markers":
        for x, y in marker_centres(ORIGIN, SQUARE):
            cv2.circle(canvas, (int(x), int(y)), RADIUS, (255, 255, 255), -1, cv2.LINE_AA)
    h = cv2.getPerspectiveTransform(np.float32([(0, 0), (CANVAS[0], 0), CANVAS, (0, CANVAS[1])]), SEEN)
    img = cv2.warpPerspective(canvas, h, CAM).astype(np.float32) * 0.8 + ambient
    img += np.random.default_rng(seed).normal(0, 2, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def test_marker_centres_are_the_corner_squares_in_corner_order():
    tl, tr, br, bl = marker_centres(ORIGIN, SQUARE)
    assert tl[0] < tr[0] and tl[1] < bl[1] and br[0] > bl[0] and br[1] > tr[1]
    assert tl == (ORIGIN[0] + SQUARE / 2, ORIGIN[1] + SQUARE / 2)
    assert br == (ORIGIN[0] + 7.5 * SQUARE, ORIGIN[1] + 7.5 * SQUARE)


def test_finds_the_four_discs_to_subpixel_accuracy():
    found = find_markers(camera("dark"), camera("markers", seed=1))
    h = cv2.getPerspectiveTransform(np.float32([(0, 0), (CANVAS[0], 0), CANVAS, (0, CANVAS[1])]), SEEN)
    expected = cv2.perspectiveTransform(np.float32([marker_centres(ORIGIN, SQUARE)]), h)[0]
    for e in expected:
        assert min(np.hypot(*(np.array(f) - e)) for f in found) < 1.5


def test_calibrated_mapping_recovers_canvas_coordinates():
    found = find_markers(camera("dark"), camera("markers", seed=1))
    m = CoordinateMapper(CAM, CANVAS, mirror=False)
    m.calibrate(order_corners(found), marker_centres(ORIGIN, SQUARE))
    h = cv2.getPerspectiveTransform(np.float32([(0, 0), (CANVAS[0], 0), CANVAS, (0, CANVAS[1])]), SEEN)
    for cx, cy in [(100, 100), (640, 360), (1200, 650)]:
        px = cv2.perspectiveTransform(np.float32([[[cx, cy]]]), h)[0, 0]
        assert np.hypot(*(np.array(m.map(tuple(px), clamp=False)) - (cx, cy))) < 3


def test_order_corners_handles_any_input_order():
    pts = [(900, 600), (100, 90), (110, 580), (880, 80)]
    assert order_corners(pts) == [(100, 90), (880, 80), (900, 600), (110, 580)]


def test_no_discs_when_nothing_changed():
    with pytest.raises(MarkerError, match="not visible"):
        find_markers(camera("dark"), camera("dark", seed=3))


def test_faint_discs_in_a_bright_room_with_a_big_moving_object():
    """The real failure: discs only ~12 levels brighter on a bright wall, and a big blob changed elsewhere."""
    dark = camera("dark", ambient=150)
    lit = (camera("markers", ambient=150, seed=1).astype(np.float32) - 150) * 0.15 + 150
    lit = np.clip(lit, 0, 255).astype(np.uint8)
    dark[300:500, 0:90] = 20                    # someone dark was standing there in the first frame only
    found = find_markers(dark, lit)
    h = cv2.getPerspectiveTransform(np.float32([(0, 0), (CANVAS[0], 0), CANVAS, (0, CANVAS[1])]), SEEN)
    expected = cv2.perspectiveTransform(np.float32([marker_centres(ORIGIN, SQUARE)]), h)[0]
    for e in expected:
        assert min(np.hypot(*(np.array(f) - e)) for f in found) < 2.5


def test_too_few_discs_when_one_is_hidden():
    lit = camera("markers", seed=2)
    x, y = disc_in_camera(0)
    lit[y - 60:y + 60, x - 60:x + 60] = camera("dark", seed=2)[y - 60:y + 60, x - 60:x + 60]   # a hand over the top-left disc
    with pytest.raises(MarkerError, match="of the 4"):
        find_markers(camera("dark"), lit)


def test_extra_bright_spot_is_rejected():
    lit = camera("markers", seed=2)
    cv2.circle(lit, (640, 360), 24, (255, 255, 255), -1)
    with pytest.raises(MarkerError, match="More than 4"):
        find_markers(camera("dark"), lit)


def test_disc_cut_by_the_image_edge_gets_a_specific_message():
    lit = camera("markers", seed=2)
    dark = camera("dark")
    rows = (disc_in_camera(0)[1] + disc_in_camera(1)[1]) // 2
    up = lambda f: np.vstack([f[rows:], np.zeros_like(f[:rows])])    # the camera sees the board too high: top discs half cut
    lit, dark = up(lit), up(dark)
    with pytest.raises(MarkerError, match="cut off"):
        find_markers(dark, lit)
