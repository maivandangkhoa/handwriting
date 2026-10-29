"""Touch detection on a projected surface from the hand's shadow. No Qt.

The projector lights the surface from one side, the camera sees the hand and its shadow from another. A hovering
finger casts a shadow displaced from it, so a crescent of shadow shows beside the fingertip; as the finger lands
the shadow slides under the finger and the crescent shrinks. The score is the visible shadow area around the
fingertip (palm lengths squared), measured against a model of the empty scene so dark squares are not shadow.
Two reference scores (touching, hovering), taken from the user, set the thresholds.

A projector that is weak against the room light only adds a little to each pixel, so a shadow darkens the wall by a
few percent, not tens. When the black-canvas frame (pure ambient light) is known, a pixel's shadow is therefore
measured as the share of the *projected* light that has disappeared, not as a plain brightness ratio.
"""
import math
from dataclasses import dataclass

import cv2
import numpy as np

from . import config
from .hand_tracker import INDEX_FINGER_TIP

WRIST, MIDDLE_MCP = 0, 9   # palm length (wrist to middle-finger knuckle) is the unit that makes the score scale-free


@dataclass
class TouchSample:
    ready: bool            # the empty-scene model exists, so shadows can be measured
    score: float | None    # visible shadow area near the fingertip, palm lengths squared; None until ready
    near: float | None     # distance from the fingertip to the nearest visible shadow, palm lengths; None = no shadow
    touching: bool


class ShadowTouchDetector:
    def __init__(self):
        self._bg: np.ndarray | None = None
        self._acc: np.ndarray | None = None
        self._n = 0
        self._empty_since: float | None = None
        self._touching = False
        self._streak = 0
        self._on: float | None = None    # thresholds, set from the touching / hovering references
        self._off: float | None = None
        self._region: np.ndarray | None = None   # the projected canvas as a polygon in raw frame pixels
        self._region_mask: tuple | None = None   # (work shape, mask) cache
        self._ambient_raw: np.ndarray | None = None   # frame of the black canvas: the room light alone
        self._ambient: np.ndarray | None = None       # the same at work size, in the exposure of the learned scene

    @property
    def ready(self) -> bool:
        return self._bg is not None

    @property
    def calibrated(self) -> bool:
        return self._on is not None

    def set_region(self, polygon: list[tuple[float, float]] | None) -> None:
        """Only look for shadow inside this polygon (raw frame pixels): the projected surface."""
        self._region = None if polygon is None else np.array(polygon, dtype=np.float32)
        self._region_mask = None

    def set_ambient(self, dark_frame: np.ndarray | None) -> None:
        """A raw frame taken while the projector showed black: what each pixel looks like without projected light."""
        self._ambient_raw, self._ambient = dark_frame, None

    def _in_region(self, shape: tuple[int, int], scale: float) -> np.ndarray | None:
        if self._region is None:
            return None
        if self._region_mask is None or self._region_mask[0] != shape:
            mask = np.zeros(shape, np.uint8)
            cv2.fillConvexPoly(mask, (self._region * scale).astype(np.int32), 1)
            self._region_mask = (shape, mask > 0)
        return self._region_mask[1]

    def _valid(self, shape: tuple[int, int], scale: float) -> np.ndarray:
        """Pixels where the projector adds enough light to show a shadow and that lie on the projected canvas."""
        if self._ambient is not None:
            valid = (self._bg - self._ambient) > config.TOUCH_MIN_PROJECTED
        else:
            valid = self._bg > config.TOUCH_MIN_BACKGROUND
        region = self._in_region(shape, scale)
        return valid if region is None else valid & region

    def _fit_ambient(self, scale: float) -> None:
        """Bring the black-canvas frame to the exposure of the learned scene, judged by the pixels off the canvas."""
        if self._ambient_raw is None:
            return
        amb, _ = self._gray(self._ambient_raw)
        region = self._in_region(amb.shape, scale)
        if region is not None:
            outside = ~region & (amb > config.TOUCH_MIN_BACKGROUND)
            if outside.mean() > 0.05:
                amb = amb * float(np.median(self._bg[outside] / amb[outside]))
        self._ambient = amb

    def set_references(self, touching: float, hovering: float) -> bool:
        """Set thresholds from scores measured while touching and while hovering; False if they are too alike."""
        if hovering - touching < config.TOUCH_MIN_CONTRAST:
            return False
        self._on = touching + config.TOUCH_ON_FRACTION * (hovering - touching)
        self._off = touching + config.TOUCH_OFF_FRACTION * (hovering - touching)
        self._reset_touch()
        return True

    def invalidate(self) -> None:
        """The projected image changed: forget the empty scene and relearn it once the hand is away."""
        self._bg, self._acc, self._n, self._ambient = None, None, 0, None
        self._reset_touch()

    def _reset_touch(self) -> None:
        self._touching, self._streak = False, 0

    @staticmethod
    def _gray(frame: np.ndarray) -> tuple[np.ndarray, float]:
        scale = config.TOUCH_WORK_WIDTH / frame.shape[1]
        small = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY) if small.ndim == 3 else small
        return cv2.GaussianBlur(gray, (5, 5), 0).astype(np.float32), scale

    # ---- empty scene ----
    def observe_empty(self, frame: np.ndarray, now: float) -> None:
        """Call for every frame without a hand: learns (and slowly tracks) the empty projected scene."""
        self._reset_touch()
        if self._empty_since is None:
            self._empty_since = now
        if now - self._empty_since < config.BACKGROUND_EMPTY_S:
            return   # the hand may only just have left; wait for its shadow to go too
        gray, scale = self._gray(frame)
        if self._bg is not None:
            self._bg = 0.97 * self._bg + 0.03 * gray   # follow ambient light / auto-exposure drift
            return
        self._acc = gray if self._acc is None else self._acc + gray
        self._n += 1
        if self._n >= config.BACKGROUND_FRAMES:
            self._bg, self._acc, self._n = self._acc / self._n, None, 0
            self._fit_ambient(scale)

    def hand_seen(self) -> None:
        self._empty_since = None

    # ---- touch ----
    def measure(self, frame: np.ndarray, landmarks: np.ndarray) -> TouchSample:
        self.hand_seen()
        if self._bg is None:
            return TouchSample(False, None, None, False)
        gray, scale = self._gray(frame)
        lm = landmarks * scale
        palm = max(math.dist(lm[WRIST], lm[MIDDLE_MCP]), 8.0)
        score, near = self._score(gray, lm, palm, scale)
        if self._on is not None:
            # No shadow close to the fingertip (a high hover, or a shadow that is not visible) is never a touch.
            low = score is not None and near is not None and near <= config.TOUCH_NEAR_MAX
            if self._touching:
                if not low or score > self._off:
                    self._reset_touch()
            else:
                self._streak = self._streak + 1 if low and score < self._on else 0
                self._touching = self._streak >= config.TOUCH_CONFIRM_FRAMES
        return TouchSample(True, score, near, self._touching)

    def _score(self, gray: np.ndarray, lm: np.ndarray, palm: float, scale: float) -> tuple[float | None, float | None]:
        h, w = gray.shape
        valid = self._valid(gray.shape, scale)
        ratio = gray / (self._bg + 1.0)
        sample = ratio[::4, ::4][valid[::4, ::4]]
        if sample.size == 0:
            return None, None
        gray = gray / max(float(np.median(sample)), 0.3)   # a global exposure change is not a shadow
        ambient = 0.0 if self._ambient is None else self._ambient
        lost = (self._bg - gray) / (self._bg - ambient + 1.0)    # share of the projected light that is gone
        threshold = 1.0 - config.TOUCH_SHADOW_RATIO if self._ambient is None else config.TOUCH_SHADOW_FRACTION
        shadow = ((lost > threshold) & valid).astype(np.uint8)

        margin = max(int(config.TOUCH_HAND_MARGIN * palm), 2)
        hand = np.zeros_like(shadow)
        cv2.fillConvexPoly(hand, cv2.convexHull(lm.astype(np.int32)), 1)
        hand = cv2.dilate(hand, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * margin + 1, 2 * margin + 1)))
        shadow[hand > 0] = 0
        shadow = cv2.morphologyEx(shadow, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        shadow = self._drop_specks(shadow, palm)

        tip = lm[INDEX_FINGER_TIP]
        tx, ty = min(max(int(round(tip[0])), 0), w - 1), min(max(int(round(tip[1])), 0), h - 1)
        disc = np.zeros_like(shadow)
        cv2.circle(disc, (tx, ty), int(config.TOUCH_DISC_RADIUS * palm), 1, -1)
        score = float(np.count_nonzero(shadow & disc)) / (palm * palm)
        if not shadow.any():
            return score, None
        nearest = cv2.distanceTransform(np.where(shadow > 0, 0, 255).astype(np.uint8), cv2.DIST_L2, 3)[ty, tx]
        return score, float(nearest) / palm

    @staticmethod
    def _drop_specks(shadow: np.ndarray, palm: float) -> np.ndarray:
        """Keep only shadow blobs of at least a fingertip's size, so sensor noise does not count."""
        count, labels, stats, _ = cv2.connectedComponentsWithStats(shadow, connectivity=8)
        keep = np.zeros(count, dtype=np.uint8)
        keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= 0.02 * palm * palm
        return keep[labels]
