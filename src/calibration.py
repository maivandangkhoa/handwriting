"""Camera-to-canvas coordinate mapping.

Isolated from UI/tracking so it can later be reused for camera-to-floor mapping.

Coordinate conventions
- "raw" points: pixel coordinates in the unmirrored camera frame (what the tracker returns).
- "view" points: raw points after the optional horizontal mirror / vertical flip (what the user sees in the preview).
- Calibration points are stored in view coordinates, so changing the mirror setting invalidates them.
"""
import math

import cv2
import numpy as np

from . import config

Point = tuple[float, float]

CORNER_NAMES = ("top-left", "top-right", "bottom-right", "bottom-left")


class CalibrationError(ValueError):
    """Calibration points are unusable; the message is shown to the user."""


def _cross(o: Point, a: Point, b: Point) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def validate_points(points: list[Point], frame_size: tuple[int, int]) -> None:
    """Raise CalibrationError unless `points` form a usable convex quadrilateral in TL,TR,BR,BL order."""
    if len(points) != 4:
        raise CalibrationError("Calibration needs exactly 4 points.")
    w, h = frame_size
    min_dist = config.CALIB_MIN_POINT_DISTANCE * math.hypot(w, h)
    for i in range(4):
        for j in range(i + 1, 4):
            if math.dist(points[i], points[j]) < min_dist:
                raise CalibrationError(
                    f"Points {i + 1} ({CORNER_NAMES[i]}) and {j + 1} ({CORNER_NAMES[j]}) are too close. "
                    "Move your fingertip clearly to each target."
                )
    crosses = [_cross(points[i], points[(i + 1) % 4], points[(i + 2) % 4]) for i in range(4)]
    if not (all(c > 0 for c in crosses) or all(c < 0 for c in crosses)):
        raise CalibrationError(
            "Points are in the wrong order or form a bent shape. "
            "Go top-left, top-right, bottom-right, bottom-left."
        )
    area = 0.5 * abs(sum(
        points[i][0] * points[(i + 1) % 4][1] - points[(i + 1) % 4][0] * points[i][1] for i in range(4)
    ))
    if area < config.CALIB_MIN_AREA * w * h:
        raise CalibrationError("The calibrated area is too small. Spread the four points further apart.")


class CoordinateMapper:
    """Maps raw camera pixels to canvas coordinates (calibrated homography or linear fallback)."""

    def __init__(self, frame_size: tuple[int, int], canvas_size: tuple[int, int], mirror: bool = True,
                 flip_vertical: bool = False):
        self.frame_size = frame_size
        self.canvas_size = canvas_size
        self._mirror = mirror
        self._flip_vertical = flip_vertical
        self._homography: np.ndarray | None = None

    @property
    def mirror(self) -> bool:
        return self._mirror

    @property
    def flip_vertical(self) -> bool:
        return self._flip_vertical

    @property
    def calibrated(self) -> bool:
        return self._homography is not None

    def set_mirror(self, mirror: bool) -> None:
        if mirror != self._mirror:
            self._mirror = mirror
            self.reset()  # stored calibration points are in view coordinates

    def set_flip_vertical(self, flip: bool) -> None:
        if flip != self._flip_vertical:
            self._flip_vertical = flip
            self.reset()

    def set_frame_size(self, frame_size: tuple[int, int]) -> None:
        if frame_size != self.frame_size:
            self.frame_size = frame_size
            self.reset()

    def to_view(self, raw: Point) -> Point:
        x = self.frame_size[0] - raw[0] if self._mirror else raw[0]
        y = self.frame_size[1] - raw[1] if self._flip_vertical else raw[1]
        return (x, y)

    def reset(self) -> None:
        self._homography = None

    def calibrate(self, view_points: list[Point]) -> None:
        validate_points(view_points, self.frame_size)
        cw, ch = self.canvas_size
        src = np.array(view_points, dtype=np.float32)
        dst = np.array([(0, 0), (cw, 0), (cw, ch), (0, ch)], dtype=np.float32)
        matrix = cv2.getPerspectiveTransform(src, dst)
        if not np.all(np.isfinite(matrix)):
            raise CalibrationError("Could not compute a valid transform from these points.")
        self._homography = matrix

    def map(self, raw: Point) -> Point | None:
        """Canvas coordinates (clamped to the canvas) for a raw fingertip, or None if the transform is invalid."""
        vx, vy = self.to_view(raw)
        cw, ch = self.canvas_size
        if self._homography is None:
            fw, fh = self.frame_size
            x, y = vx / fw * cw, vy / fh * ch
        else:
            src = np.array([[[vx, vy]]], dtype=np.float32)
            x, y = cv2.perspectiveTransform(src, self._homography)[0, 0]
        if not (math.isfinite(x) and math.isfinite(y)):
            return None
        return (min(max(float(x), 0.0), cw), min(max(float(y), 0.0), ch))
