"""Colouring animals on a projector by sweeping the hand like a brush.

It is Air Drawing on a projector (same calibration, pen styles and palette selection by resting on a swatch) with a
different canvas: an animal outline, and every stroke is clipped to the part of the animal it started on, so paint
stays inside the lines. The last palette cell is a "next animal" button.
"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF

from .animal_pictures import ANIMALS
from .draw_view import paint_draw_furniture
from .projector_draw import ProjectorDraw

PAPER, LINE = QColor(250, 246, 232), QColor(60, 50, 40)
KIDS_COLORS = [(230, 50, 50), (250, 150, 30), (250, 220, 40), (60, 180, 75), (90, 190, 250), (250, 120, 190),
               (140, 90, 50)]
SHEET, BRUSH = 560.0, 34      # canvas px per side of the 100 x 100 sheet; brush width in canvas px


def smooth_path(points) -> QPainterPath:
    """A stroke as a curve: quadratic segments through the midpoints of the samples, so the camera's ~30 samples a second
    do not show as a polyline."""
    path = QPainterPath(QPointF(*points[0]))
    if len(points) == 1:
        path.lineTo(QPointF(points[0][0] + 0.01, points[0][1]))      # a dot
        return path
    for a, b in zip(points[1:], points[2:]):
        path.quadTo(QPointF(*a), QPointF((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
    path.lineTo(QPointF(*points[-1]))
    return path


class ProjectorAnimals(ProjectorDraw):
    paints_canvas = True
    colors = KIDS_COLORS
    ring_color = (60, 50, 40)         # the paper is light: a white ring would vanish

    def __init__(self, *args):
        super().__init__(*args)
        self.animal = 0
        self._next_done = False
        self._shapes = self._build()

    @property
    def name(self) -> str:
        return list(ANIMALS)[self.animal]

    @property
    def swatch_count(self) -> int:
        return len(self.colors) + 1            # the colours and the "next animal" button

    def _build(self) -> list[QPainterPath]:
        w, h = self.canvas_size
        x0, y0, k = (w + 120 - SHEET) / 2, (h - SHEET) / 2, SHEET / 100
        shapes = []
        for kind, *args in ANIMALS[self.name]:
            path = QPainterPath()
            if kind == "ellipse":
                cx, cy, rx, ry = args
                path.addEllipse(QRectF(x0 + (cx - rx) * k, y0 + (cy - ry) * k, 2 * rx * k, 2 * ry * k))
            else:
                path.addPolygon(QPolygonF([QPointF(x0 + x * k, y0 + y * k) for x, y in args[0]]))
                path.closeSubpath()
            shapes.append(path)
        return shapes

    def next_animal(self) -> None:
        self.animal = (self.animal + 1) % len(ANIMALS)
        self._shapes = self._build()
        self.state.clear()

    def _select(self, i: int) -> None:
        if i < len(self.colors):
            super()._select(i)
        elif not self._next_done:
            self._next_done = True
            self.next_animal()

    def on_palette(self, point, now: float) -> bool:
        over = super().on_palette(point, now)
        if self.resting_swatch != len(self.colors):
            self._next_done = False             # the button fires once per visit
        return over

    def _shape_at(self, point) -> int | None:
        """The topmost shape under `point`, or None."""
        pt = QPointF(*point)
        return next((i for i in reversed(range(len(self._shapes))) if self._shapes[i].contains(pt)), None)

    def _runs(self, stroke) -> list[tuple[int, list]]:
        """Split a stroke into stretches over one shape each (a stroke may cross shapes; paint stays inside the shape
        the brush is over). A stretch keeps the neighbouring points so it reaches the shape edge without a gap."""
        runs: list[tuple[int, list]] = []
        owners = [self._shape_at(pt) for pt in stroke]
        start = 0
        for k in range(1, len(stroke) + 1):
            if k == len(stroke) or owners[k] != owners[start]:
                if owners[start] is not None:
                    runs.append((owners[start], stroke[max(start - 1, 0):k + 1]))
                start = k
        return runs

    def paint(self, p: QPainter, to_w, scale: float) -> None:
        w, h = self.canvas_size
        p.fillRect(QRectF(to_w((0, 0)), to_w((w, h))), PAPER)
        owner: dict[int, list] = {}
        for stroke, color in zip(self.state.strokes, self.state.colors):
            for i, run in self._runs(stroke):
                owner.setdefault(i, []).append((run, color))
        p.save()
        p.translate(to_w((0, 0)))
        p.scale(scale, scale)
        for i, path in enumerate(self._shapes):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255))
            p.drawPath(path)
            p.save()
            p.setClipPath(path)
            for stroke, color in owner.get(i, []):
                brush = QPen(QColor(*color), BRUSH, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                p.setPen(brush)
                p.drawPath(smooth_path(stroke))
            p.restore()
            p.setPen(QPen(LINE, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
        p.restore()
        paint_draw_furniture(p, to_w, scale, self, self.state.color)
        p.setPen(LINE)
        font = p.font()
        font.setPixelSize(int(26 * scale) + 4)
        p.setFont(font)
        p.drawText(to_w((130, 70)), f"{self.name}: pick a colour on the left, then sweep your finger over the animal")
