"""Pinch detection from hand landmarks (pixel coordinates). No Qt, no camera."""
import math

import numpy as np

from . import config

# MediaPipe hand landmarks: 0 = wrist, 4 = thumb tip, 8 = index fingertip, 9 = middle-finger MCP knuckle.
WRIST, THUMB_TIP, INDEX_MCP, INDEX_TIP, MIDDLE_MCP = 0, 4, 5, 8, 9


def pinch_ratio(landmarks: np.ndarray) -> float:
    """Thumb-tip to index-tip distance relative to palm length (wrist to middle knuckle): scale independent."""
    palm = math.dist(landmarks[WRIST], landmarks[MIDDLE_MCP])
    return math.dist(landmarks[THUMB_TIP], landmarks[INDEX_TIP]) / max(palm, 1e-6)


def pinch_point(landmarks: np.ndarray) -> tuple[float, float]:
    """Midpoint between thumb and index tips: steadier than the index tip alone while pinching."""
    x, y = (landmarks[THUMB_TIP] + landmarks[INDEX_TIP]) / 2
    return float(x), float(y)


def index_extension(landmarks: np.ndarray) -> float:
    """Wrist-to-index-tip over wrist-to-index-knuckle: large when the finger points out, small when it is curled."""
    return math.dist(landmarks[WRIST], landmarks[INDEX_TIP]) / max(math.dist(landmarks[WRIST], landmarks[INDEX_MCP]), 1e-6)


class PointDetector:
    """Index finger out (True) or curled (False), with hysteresis so a half-bent finger does not flicker."""

    def __init__(self, on_ratio: float = config.POINT_ON_RATIO, off_ratio: float = config.POINT_OFF_RATIO):
        self.on_ratio, self.off_ratio = on_ratio, off_ratio
        self.pointing = False

    def update(self, landmarks: np.ndarray | None) -> bool:
        if landmarks is None:
            self.pointing = False
            return False
        ratio = index_extension(landmarks)
        self.pointing = ratio > (self.off_ratio if self.pointing else self.on_ratio)
        return self.pointing


class PinchDetector:
    """Hysteresis around the pinch ratio so noise near the threshold does not flicker grab/release."""

    def __init__(self, on_ratio: float = config.PINCH_ON_RATIO, off_ratio: float = config.PINCH_OFF_RATIO):
        self.on_ratio, self.off_ratio = on_ratio, off_ratio
        self.pinching = False

    def update(self, landmarks: np.ndarray | None) -> bool:
        if landmarks is None:
            self.pinching = False
            return False
        ratio = pinch_ratio(landmarks)
        if self.pinching:
            self.pinching = ratio < self.off_ratio
        else:
            self.pinching = ratio < self.on_ratio
        return self.pinching
