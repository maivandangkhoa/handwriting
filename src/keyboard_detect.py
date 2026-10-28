"""Finds the keyboard in a camera frame and returns the four layout corners (no clicking needed).

Chamfer matching: points sampled along every key outline of the layout are projected through a candidate
quadrilateral and scored by their mean distance to the nearest image edge (Canny). Several coarse guesses of the key
block (hull extremes, minimum-area rectangles, dense-edge region) x 8 corner assignments (4 rotations, with and
without reflection) are refined by pattern search; the best valid, low-cost quadrilateral wins. A high cost means
"no keyboard found": blurry frame, keyboard not in view, or something that is not a keyboard.
"""
from dataclasses import dataclass

import cv2
import numpy as np

from . import config
from .keyboard_layout import KEYS, LAYOUT_H, LAYOUT_W

Point = tuple[float, float]
MAX_COST_VS_CHANCE = 0.6   # accepted only if the outline cost is at most this fraction of the chance level
_CORNERS = np.float32([(0, 0), (LAYOUT_W, 0), (LAYOUT_W, LAYOUT_H), (0, LAYOUT_H)])


@dataclass(frozen=True)
class Detection:
    corners: list[Point]   # layout TL, TR, BR, BL (esc, power key, arrow cluster, fn) in input-frame pixels
    cost: float            # lower is better; <= KEYBOARD_DETECT_MAX_COST is accepted
    chance: float          # the same measure at key centres: what an unrelated, edge-rich image would score


def _template_points(step: float = 0.1) -> np.ndarray:
    pts = []
    for k in KEYS:
        for t in np.arange(0, k.w, step):
            pts += [(k.x + t, k.y), (k.x + t, k.y + k.h)]
        for t in np.arange(0, k.h, step):
            pts += [(k.x, k.y + t), (k.x + k.w, k.y + t)]
    return np.unique(np.round(np.array(pts, np.float32), 3), axis=0).reshape(1, -1, 2)


_TEMPLATE = _template_points()


def _edges(bgr: np.ndarray, width: int) -> tuple[np.ndarray, float]:
    scale = width / bgr.shape[1]
    gray = cv2.cvtColor(cv2.resize(bgr, (width, max(int(bgr.shape[0] * scale), 1))), cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(cv2.createCLAHE(2.0, (8, 8)).apply(gray), (5, 5), 0)
    median = float(np.median(gray))
    return cv2.Canny(gray, max(10, 0.5 * median), max(30, 1.2 * median)), scale


def _valid_quad(q: np.ndarray, w: int, h: int) -> bool:
    """Convex, big enough, keyboard-like aspect and corners (rejects the collapsed shapes chamfer matching favours)."""
    cross = [(q[(i + 1) % 4, 0] - q[i, 0]) * (q[(i + 2) % 4, 1] - q[(i + 1) % 4, 1])
             - (q[(i + 1) % 4, 1] - q[i, 1]) * (q[(i + 2) % 4, 0] - q[(i + 1) % 4, 0]) for i in range(4)]
    if not (all(c > 0 for c in cross) or all(c < 0 for c in cross)):
        return False
    area = 0.5 * abs(sum(q[i, 0] * q[(i + 1) % 4, 1] - q[(i + 1) % 4, 0] * q[i, 1] for i in range(4)))
    if area < 0.12 * w * h:
        return False
    top, bottom = np.linalg.norm(q[1] - q[0]), np.linalg.norm(q[2] - q[3])
    left, right = np.linalg.norm(q[3] - q[0]), np.linalg.norm(q[2] - q[1])
    if not 1.6 < (top + bottom) / max(left + right, 1e-6) < 3.6:
        return False
    if min(top, bottom, left, right) < 0.15 * np.sqrt(area):
        return False
    for i in range(4):
        a, b = q[i - 1] - q[i], q[(i + 1) % 4] - q[i]
        if abs(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))) > 0.8:
            return False
    return True


def _cost(q: np.ndarray, dist: np.ndarray, cap: float, template: np.ndarray = _TEMPLATE) -> float:
    h, w = dist.shape
    if not _valid_quad(q, w, h):
        return cap
    pts = cv2.perspectiveTransform(template, cv2.getPerspectiveTransform(_CORNERS, q.astype(np.float32)))[0]
    x = np.clip(np.round(pts[:, 0]).astype(int), 0, w - 1)
    y = np.clip(np.round(pts[:, 1]).astype(int), 0, h - 1)
    d = np.minimum(dist[y, x], cap)
    d[(pts[:, 0] < 0) | (pts[:, 0] >= w) | (pts[:, 1] < 0) | (pts[:, 1] >= h)] = cap
    return float(d.mean())


def _refine(q: np.ndarray, dist: np.ndarray, cap: float = 8.0, step0: float = 24.0, step_min: float = 0.5):
    """Pattern search on the 8 corner coordinates with a shrinking step."""
    q, best, step = q.copy(), _cost(q, dist, cap), step0
    while step >= step_min:
        improved = True
        while improved:
            improved = False
            for i in range(4):
                for axis in (0, 1):
                    for sign in (-1, 1):
                        trial = q.copy()
                        trial[i, axis] += sign * step
                        c = _cost(trial, dist, cap)
                        if c < best - 1e-4:
                            q, best, improved = trial, c, True
        step /= 2
    return q, best


def _initial_quads(edges: np.ndarray) -> list[np.ndarray]:
    """Complementary coarse guesses of the key block, each as 4 corners in any order."""
    quads: list[np.ndarray] = []
    n, labels, stats, _ = cv2.connectedComponentsWithStats(cv2.dilate(edges, np.ones((9, 9), np.uint8)), 8)
    for i in (1 + np.argsort(-stats[1:, cv2.CC_STAT_AREA])[:2] if n > 1 else []):
        ys, xs = np.nonzero((labels == i) & (edges > 0))
        hull = cv2.convexHull(np.stack([xs, ys], 1).astype(np.float32))
        pts = hull.reshape(-1, 2)
        s, d = pts.sum(1), pts[:, 0] - pts[:, 1]
        quads.append(np.float32([pts[np.argmin(s)], pts[np.argmax(d)], pts[np.argmax(s)], pts[np.argmin(d)]]))
        box = cv2.boxPoints(cv2.minAreaRect(hull)).astype(np.float32)
        quads += [box, (box.mean(0) + 0.85 * (box - box.mean(0))).astype(np.float32)]
    density = cv2.boxFilter((edges > 0).astype(np.float32), -1, (25, 25))
    if density.max() > 0:
        mask = (density > 0.4 * density.max()).astype(np.uint8) * 255
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            quads.append(cv2.boxPoints(cv2.minAreaRect(cv2.convexHull(max(contours, key=cv2.contourArea)))).astype(np.float32))
    return quads


def detect_keyboard(bgr: np.ndarray, max_cost: float = config.KEYBOARD_DETECT_MAX_COST) -> Detection | None:
    """The keyboard's four layout corners in `bgr` pixel coordinates, or None if no convincing match was found."""
    edges, scale = _edges(bgr, config.KEYBOARD_DETECT_WIDTH)
    if (edges > 0).mean() < 0.01:
        return None
    dist = cv2.distanceTransform(255 - edges, cv2.DIST_L2, 3)
    h, w = dist.shape
    best_q, best_cost = None, float("inf")
    for q0 in _initial_quads(edges):
        for base in (q0, q0[::-1]):             # with and without reflection
            for shift in range(4):              # 4 rotations
                q = np.roll(base, shift, axis=0)
                if not _valid_quad(q, w, h):
                    continue
                q, cost = _refine(q, dist)
                if cost < best_cost:
                    best_q, best_cost = q, cost
    if best_q is None or best_cost > max_cost:
        return None
    # Edge-rich noise puts an edge near every point, so also demand that key outlines match much better than the
    # same points shifted half a key (key centres, which have no outline).
    chance = _cost(best_q, dist, 8.0, _TEMPLATE + np.float32((0.5, 0.5)))
    if best_cost > MAX_COST_VS_CHANCE * chance:
        return None
    return Detection([(float(x / scale), float(y / scale)) for x, y in best_q], best_cost, chance)
