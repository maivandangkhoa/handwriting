"""Finding the projected board in the camera image: show the canvas dark, then with four bright discs on the corner
squares, and diff the frames.
Differencing cancels ambient light, window glare and whatever else the camera sees. No Qt."""
import logging

import cv2
import numpy as np

log = logging.getLogger(__name__)
Point = tuple[float, float]


class MarkerError(ValueError):
    """The discs could not be found; the message tells the user what to change."""


def marker_centres(origin: Point, square: float) -> list[Point]:
    """Centres (canvas pixels) of the board's four corner squares, ordered top-left, top-right, bottom-right,
    bottom-left. The discs sit on the board, so the camera only has to see the board, not the whole canvas."""
    x0, y0 = origin[0] + 0.5 * square, origin[1] + 0.5 * square
    x1, y1 = origin[0] + 7.5 * square, origin[1] + 7.5 * square
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


LEVELS = (40, 20, 10, 6)   # brightness increase (0..255) a disc must show; tried high to low, so a faint projector still works
MIN_VISIBLE = 6


def _disc_like(mask: np.ndarray) -> list[tuple[int, Point]]:
    """(area, centre) of the round blobs in `mask`: filled, about as wide as tall. Hands and shadows that moved
    between the two frames are not round, so they drop out here."""
    count, _, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    found = []
    for i in range(1, count):
        area, w, h = stats[i, cv2.CC_STAT_AREA], stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        if area >= 40 and 0.7 <= w / h <= 1.4 and 0.6 <= area / (w * h) <= 0.95:
            found.append((int(area), (float(centroids[i][0]), float(centroids[i][1]))))
    return sorted(found, reverse=True)


def _touches_edge(mask: np.ndarray, disc_area: int) -> bool:
    """A blob on the image border, a quarter to a whole disc in size: probably a disc partly outside the picture."""
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    h, w = mask.shape
    for i in range(1, count):
        x, y, bw, bh, area = stats[i]
        on_border = x == 0 or y == 0 or x + bw >= w or y + bh >= h
        if on_border and 0.25 * disc_area <= area <= 1.2 * disc_area and 0.5 <= area / (bw * bh) <= 0.95:
            return True
    return False


def _four_alike(discs: list[tuple[int, Point]]) -> list[Point] | None:
    """Four discs of similar size with no other disc-sized blob around, else None."""
    for i in range(len(discs) - 3):
        group = discs[i:i + 4]
        big, small = group[0][0], group[3][0]
        if big > 2.0 * small:
            continue
        if any(0.5 * small <= a <= 2.0 * big for a, _ in discs[:i] + discs[i + 4:]):
            continue   # another blob that could just as well be a disc: ambiguous
        return [c for _, c in group]
    return None


def find_markers(dark: np.ndarray, lit: np.ndarray) -> list[Point]:
    """Raw-frame centres of the four discs (in no particular order) from a frame with the canvas black and one with
    the discs shown. Works with a dim projector in a bright room: the discs only need to be a little brighter."""
    gray = lambda f: cv2.GaussianBlur(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) if f.ndim == 3 else f, (9, 9), 0)
    diff = gray(lit).astype(np.int16) - gray(dark).astype(np.int16)
    diff -= int(np.median(diff))     # an auto-exposure change moves the whole frame, not just the discs
    peak = float(np.percentile(diff, 99.9))
    log.info("calibration diff: peak %.0f, mean brightness dark %.0f / lit %.0f", peak, gray(dark).mean(), gray(lit).mean())
    if peak < MIN_VISIBLE:
        raise MarkerError("The calibration discs are not visible: aim the camera at the projected canvas, "
                          "dim the room lights, or raise the projector brightness.")
    most, cut = 0, False
    for level in LEVELS:
        mask = cv2.morphologyEx((diff > level).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        discs = _disc_like(mask)
        log.info("calibration level %d: round blobs %s", level, [(a, (int(c[0]), int(c[1]))) for a, c in discs[:8]])
        if (four := _four_alike(discs)) is not None:
            return four
        most = max(most, len(discs))
        cut = cut or (0 < len(discs) < 4 and _touches_edge(mask, discs[0][0]))
    if cut:
        raise MarkerError("A calibration disc is cut off by the edge of the camera image: move or tilt the camera "
                          "(or zoom out) so the whole projected canvas is inside the picture, with some margin.")
    if most > 4:
        raise MarkerError("More than 4 similar bright spots changed between the two calibration frames: "
                          "keep the scene still (no hands, no moving light) and try again.")
    raise MarkerError(f"Found {most} of the 4 calibration discs: make the whole projected canvas visible "
                      "to the camera, dim the room lights, and keep your hands out of view.")


def order_corners(view_points: list[Point]) -> list[Point]:
    """Top-left, top-right, bottom-right, bottom-left of four points as seen in the (upright) camera view."""
    by_y = sorted(view_points, key=lambda p: p[1])
    top, bottom = sorted(by_y[:2]), sorted(by_y[2:])
    return [top[0], top[1], bottom[1], bottom[0]]
