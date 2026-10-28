import cv2
import numpy as np
import pytest

from src.keyboard_detect import detect_keyboard
from src.keyboard_layout import KEYS, LAYOUT_H, LAYOUT_W

PX, PAD = 100, 100
W, H = 960, 540
# where the layout corners (TL, TR, BR, BL) land in the picture: a mildly perspective trapezoid
QUAD = np.float32([(90, 100), (870, 70), (930, 430), (30, 470)])


def synthetic_keyboard(seed=0) -> np.ndarray:
    """Dark keycaps with light gaps and light 'legends', like a photographed laptop keyboard."""
    rng = np.random.default_rng(seed)
    sheet = np.full((int(LAYOUT_H * PX) + 2 * PAD, int(LAYOUT_W * PX) + 2 * PAD), 70, np.uint8)
    cv2.rectangle(sheet, (PAD - 12, PAD - 12), (PAD + int(LAYOUT_W * PX) + 12, PAD + int(LAYOUT_H * PX) + 12), 120, -1)
    for k in KEYS:
        x0, y0 = PAD + int(k.x * PX) + 5, PAD + int(k.y * PX) + 5
        x1, y1 = PAD + int((k.x + k.w) * PX) - 5, PAD + int((k.y + k.h) * PX) - 5
        cv2.rectangle(sheet, (x0, y0), (x1, y1), 28, -1)
        for _ in range(3):   # legends
            lx, ly = int(rng.integers(x0 + 6, max(x0 + 7, x1 - 20))), int(rng.integers(y0 + 6, max(y0 + 7, y1 - 20)))
            cv2.rectangle(sheet, (lx, ly), (lx + 10, ly + 12), 170, -1)
    return sheet


def render(quad: np.ndarray, seed=0) -> np.ndarray:
    sheet = synthetic_keyboard(seed)
    src = np.float32([(PAD, PAD), (PAD + LAYOUT_W * PX, PAD), (PAD + LAYOUT_W * PX, PAD + LAYOUT_H * PX),
                      (PAD, PAD + LAYOUT_H * PX)])
    M = cv2.getPerspectiveTransform(src, quad)
    img = cv2.warpPerspective(sheet, M, (W, H), borderValue=60)
    img = cv2.GaussianBlur(img, (0, 0), 1.3)
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)


def mean_error(found, expected) -> float:
    return float(np.mean(np.linalg.norm(np.array(found) - np.array(expected), axis=1)))


def check(quad_in_layout_order):
    det = detect_keyboard(render(np.float32(quad_in_layout_order)))
    assert det is not None, "keyboard not found"
    assert mean_error(det.corners, quad_in_layout_order) < 10
    return det


def test_upright_keyboard_is_found():
    det = check(QUAD)
    assert det.cost < 1.2


def test_rotated_180_degrees_is_found_with_corners_in_layout_order():
    check(QUAD[[2, 3, 0, 1]])           # esc corner now at the bottom right, like a camera facing the user


def test_mirrored_keyboard_is_found():
    check(QUAD[[1, 0, 3, 2]])           # reflected assignment (horizontal mirror)


def test_slightly_rotated_keyboard_is_found():
    c = QUAD.mean(0)
    r = np.deg2rad(4)
    R = np.array([[np.cos(r), -np.sin(r)], [np.sin(r), np.cos(r)]])
    check(((QUAD - c) @ R.T + c).astype(np.float32))


def test_noise_blank_and_unrelated_images_are_rejected():
    rng = np.random.default_rng(1)
    assert detect_keyboard(np.full((H, W, 3), 80, np.uint8)) is None                      # blank
    assert detect_keyboard(rng.integers(0, 255, (H, W, 3), dtype=np.uint8)) is None        # noise
    circles = np.full((H, W, 3), 90, np.uint8)
    for _ in range(40):
        cv2.circle(circles, (int(rng.integers(0, W)), int(rng.integers(0, H))), int(rng.integers(10, 60)),
                   (int(rng.integers(0, 255)),) * 3, 2)
    assert detect_keyboard(circles) is None


def test_very_blurry_frame_is_rejected_rather_than_misplaced():
    blurry = cv2.GaussianBlur(render(QUAD), (0, 0), 9)
    assert detect_keyboard(blurry) is None
