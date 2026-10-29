"""Synthetic projector scene: a projected checker board, a hand (skin-coloured finger), and its shadow.

The shadow of a point at height h lands at point + DIRECTION * h. The finger tilts, so points farther from the
tip are higher: fingertip contact (tip_height 0) puts the shadow tip exactly under the fingertip.
"""
import cv2
import numpy as np

W, H = 1280, 720
DIRECTION = np.array([0.8, 0.5])
SLOPE = 0.6          # extra height per pixel back from the tip
FINGER_WIDTH = 36
LANDMARKS = {0: (400, 640), 9: (400, 500), 5: (420, 470), 8: (420, 320)}   # wrist, middle MCP, index MCP, index tip


def board(seed: int = 0, cell: int = 80) -> np.ndarray:
    """Projected image as the camera sees it (BGR), with sensor noise."""
    yy, xx = np.mgrid[0:H, 0:W]
    light = ((xx // cell + yy // cell) % 2 == 0)
    gray = np.where(light, 205, 95).astype(np.uint8)
    img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    return add_noise(img, seed)


def add_noise(img: np.ndarray, seed: int) -> np.ndarray:
    noise = np.random.default_rng(seed).normal(0, 3, img.shape)
    return np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)


def hand_landmarks(shift=(0.0, 0.0)) -> np.ndarray:
    """21 landmarks of the pointing hand, moved by `shift` pixels (the index tip is at (420, 320) + shift)."""
    lm = np.zeros((21, 2), dtype=np.float32)
    lm[:] = LANDMARKS[0]
    for i, p in LANDMARKS.items():
        lm[i] = p
    for i in (1, 2, 3, 4, 6, 7, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20):   # park the rest on the palm / finger
        lm[i] = LANDMARKS[9] if i not in (6, 7) else LANDMARKS[5]
    lm[6], lm[7] = (420, 420), (420, 370)
    return lm + np.array(shift, dtype=np.float32)


def _finger_points(shifted: bool, tip_height: float, shift=(0.0, 0.0)) -> np.ndarray:
    pts = np.array([LANDMARKS[0], LANDMARKS[5], LANDMARKS[8]], dtype=np.float64)
    if shifted:
        back = np.linalg.norm(pts - np.array(LANDMARKS[8]), axis=1)
        pts = pts + DIRECTION * (tip_height + SLOPE * back)[:, None]
    return pts + np.array(shift)


def render(tip_height: float, seed: int = 1, shadow: bool = True, hand: bool = True, base=None,
           shift=(0.0, 0.0)) -> np.ndarray:
    """The camera frame: `base` (default: the checker board) plus the hand and, tip_height pixels up, its shadow."""
    img = (board(seed) if base is None else add_noise(base, seed)).astype(np.float32)
    if shadow:
        mask = np.zeros((H, W), np.float32)
        pts = _finger_points(True, tip_height, shift).astype(np.int32)
        cv2.polylines(mask, [pts], False, 1.0, FINGER_WIDTH, cv2.LINE_AA)
        img *= (1 - 0.55 * cv2.GaussianBlur(mask, (9, 9), 0))[..., None]
    img = img.astype(np.uint8)
    if hand:
        cv2.polylines(img, [_finger_points(False, 0, shift).astype(np.int32)], False, (120, 150, 205), FINGER_WIDTH,
                      cv2.LINE_AA)
    return img
