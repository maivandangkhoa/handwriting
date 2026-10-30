"""Mirror dance drawing: cute sticker-style animal characters that copy the body, and the wrist trails.
Canvas coordinates only."""
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF

BACKGROUND = QColor(40, 36, 80)
# name -> (fur, outline, belly/inner, accent)
LOOKS = {"Bunny": ((252, 248, 252), (176, 150, 190), (255, 180, 205), (255, 150, 185)),
         "Bear": ((184, 128, 84), (110, 70, 44), (232, 198, 160), (80, 50, 36)),
         "Cat": ((255, 170, 70), (170, 95, 30), (255, 226, 190), (255, 140, 170)),
         "Chick": ((255, 226, 70), (190, 150, 20), (255, 245, 170), (255, 140, 40))}
CHARACTERS = list(LOOKS)
ARMS = (("l_shoulder", "l_elbow", "l_wrist"), ("r_shoulder", "r_elbow", "r_wrist"))
LEGS = (("l_hip", "l_knee", "l_ankle"), ("r_hip", "r_knee", "r_ankle"))
DARK = QColor(45, 35, 50)


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _mid(a, b):
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def _qc(color) -> QColor:
    return QColor(*color)


def _blob(p: QPainter, c, rx: float, ry: float, fill, outline, line: float = 5.0) -> None:
    p.setPen(QPen(_qc(outline), line))
    p.setBrush(_qc(fill))
    p.drawEllipse(QPointF(*c), rx, ry)


def _limb(p: QPainter, pts, fill, outline, width: float) -> None:
    """A fat round limb along `pts`, outlined (outline pass first, then the fur on top)."""
    for color, w in ((outline, width + 10), (fill, width)):
        p.setPen(QPen(_qc(color), w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        for a, b in zip(pts, pts[1:]):
            p.drawLine(QPointF(*a), QPointF(*b))


def paint_trails(p: QPainter, trails: dict[str, list]) -> None:
    """Sparkling dots behind the wrists, oldest smallest."""
    for hue, points in zip((190, 330), (trails.get("l_wrist", []), trails.get("r_wrist", []))):
        for i, pt in enumerate(points):
            f = (i + 1) / max(len(points), 1)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor.fromHsv(hue, 120, 255, int(40 + 190 * f)))
            r = 5 + 18 * f
            p.drawEllipse(QPointF(*pt), r, r)


def paint_figure(p: QPainter, joints: dict, character: str, t: float) -> None:
    """Draw `character` over the joints (name -> canvas point). Missing joints are skipped."""
    need = ("l_shoulder", "r_shoulder", "l_hip", "r_hip", "nose")
    if any(k not in joints for k in need):
        return
    ls, rs, lh, rh, nose = (joints[k] for k in need)
    fur, outline, belly, accent = LOOKS[character]
    sw = _dist(ls, rs)
    width = max(22.0, min(56.0, 0.3 * sw))
    r = max(46.0, min(120.0, 0.8 * sw))
    hip = _mid(lh, rh)
    if character in ("Cat", "Bunny"):      # tail behind everything
        sway = math.sin(t * 5) * 0.5
        tip = (hip[0] + math.sin(sway) * 110, hip[1] + 40 - 30 * math.cos(sway))
        if character == "Cat":
            _limb(p, [hip, tip], fur, outline, width * 0.6)
        else:
            _blob(p, tip, 26, 26, fur, outline)
    for chain in LEGS + ARMS:
        pts = [joints[k] for k in chain if k in joints]
        if len(pts) > 1:
            _limb(p, pts, fur, outline, width)
            end = pts[-1]
            if chain in LEGS:      # a foot pointing outwards
                side = -1 if chain[0].startswith("l") else 1
                _blob(p, (end[0] + side * width * 0.3, end[1] + width * 0.3), width * 0.95, width * 0.6,
                      accent if character == "Chick" else fur, outline)
            else:                  # a mitten
                _blob(p, end, width * 0.75, width * 0.75, fur, outline)
    body = [QPointF(*q) for q in (ls, rs, rh, lh)]
    for color, w in ((outline, 0.55 * sw + 10), (fur, 0.55 * sw)):         # chubby rounded torso
        p.setPen(QPen(_qc(color), w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(_qc(color))
        p.drawPolygon(QPolygonF(body))
    centre = _mid(_mid(ls, rs), hip)
    _blob(p, centre, 0.34 * sw, 0.5 * _dist(_mid(ls, rs), hip), belly, belly, 1)
    _head(p, nose, r, character, t)


def _head(p: QPainter, c, r: float, character: str, t: float) -> None:
    fur, outline, inner, accent = LOOKS[character]
    cx, cy = c
    if character == "Bunny":
        for sign in (-1, 1):
            tilt = sign * 0.25 * r + math.sin(t * 3 + sign) * 0.12 * r
            _blob(p, (cx + sign * 0.45 * r + tilt * 0.3, cy - 1.45 * r), 0.3 * r, 0.85 * r, fur, outline)
            _blob(p, (cx + sign * 0.45 * r + tilt * 0.3, cy - 1.4 * r), 0.15 * r, 0.6 * r, inner, inner, 1)
    elif character == "Bear":
        for sign in (-1, 1):
            _blob(p, (cx + sign * 0.8 * r, cy - 0.8 * r), 0.35 * r, 0.35 * r, fur, outline)
            _blob(p, (cx + sign * 0.8 * r, cy - 0.8 * r), 0.18 * r, 0.18 * r, inner, inner, 1)
    elif character == "Cat":
        for sign in (-1, 1):
            for color, grow in ((outline, 1.0), (fur, 0.86)):
                p.setPen(QPen(_qc(color), 5))
                p.setBrush(_qc(color))
                p.drawPolygon(QPolygonF([QPointF(cx + sign * 0.95 * r, cy - 0.1 * r),
                                         QPointF(cx + sign * 0.3 * r * grow, cy - 1.0 * r),
                                         QPointF(cx + sign * 0.98 * r * grow, cy - 1.35 * r * grow)]))
    elif character == "Chick":
        for dx in (-0.2, 0, 0.2):
            _blob(p, (cx + dx * r, cy - 1.05 * r), 0.1 * r, 0.22 * r, fur, outline, 3)
    _blob(p, c, r, 0.92 * r, fur, outline)
    for sign in (-1, 1):                    # big shiny eyes
        ex, ey = cx + sign * 0.42 * r, cy - 0.08 * r
        p.setPen(Qt.NoPen)
        p.setBrush(DARK)
        p.drawEllipse(QPointF(ex, ey), 0.17 * r, 0.21 * r)
        p.setBrush(QColor(255, 255, 255))
        p.drawEllipse(QPointF(ex - 0.05 * r, ey - 0.08 * r), 0.07 * r, 0.07 * r)
        p.drawEllipse(QPointF(ex + 0.05 * r, ey + 0.07 * r), 0.035 * r, 0.035 * r)
        p.setBrush(QColor(255, 130, 150, 150))       # rosy cheeks
        p.drawEllipse(QPointF(cx + sign * 0.68 * r, cy + 0.3 * r), 0.17 * r, 0.11 * r)
    if character == "Bear":
        _blob(p, (cx, cy + 0.3 * r), 0.32 * r, 0.24 * r, inner, outline, 3)
    if character == "Chick":                # beak
        p.setPen(QPen(_qc(outline), 3))
        p.setBrush(_qc(accent))
        p.drawPolygon(QPolygonF([QPointF(cx - 0.17 * r, cy + 0.14 * r), QPointF(cx + 0.17 * r, cy + 0.14 * r),
                                 QPointF(cx, cy + 0.42 * r)]))
        return
    p.setPen(Qt.NoPen)
    p.setBrush(DARK if character == "Bear" else _qc(accent))
    p.drawEllipse(QPointF(cx, cy + 0.2 * r), 0.1 * r, 0.07 * r)       # little nose
    p.setPen(QPen(DARK, max(3.0, 0.045 * r), Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(cx - 0.2 * r, cy + 0.22 * r, 0.2 * r, 0.18 * r), 180 * 16, 180 * 16)
    p.drawArc(QRectF(cx, cy + 0.22 * r, 0.2 * r, 0.18 * r), 180 * 16, 180 * 16)
    if character == "Cat":
        for sign in (-1, 1):
            for dy in (-0.05, 0.1):
                p.drawLine(QPointF(cx + sign * 0.55 * r, cy + (0.28 + dy) * r), QPointF(cx + sign * 1.15 * r, cy + (0.2 + 2 * dy) * r))
