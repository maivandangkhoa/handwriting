"""Air Drawing on a projector: the hand moves over the projected canvas and the strokes appear under it.

Only the geometry has to be found (ProjectorSurface); pinching and stroke handling stay in DrawingState, fed by the
main window with points mapped through this object's mapper.
"""
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor

from .drawing import DrawingState
from .hand_tracker import Detection
from .projector_surface import ProjectorSurface

COLORS = [(90, 230, 255), (255, 255, 255), (255, 80, 80), (255, 165, 40), (255, 235, 60), (90, 235, 120), (255, 100, 225)]
SWATCH, GAP, PALETTE_X, PALETTE_Y = 64, 12, 26, 110     # palette: a column of squares down the left edge (canvas px)
REACH = 10            # the pointer counts as on a swatch this far outside it (and in the gaps between swatches)
PICK_S = 0.5          # resting on a swatch this long selects its colour
FRAME_INSET = 10      # the drawing frame, canvas px from the edge


class ProjectorDraw(ProjectorSurface):
    ready_phase = "draw"
    colors = COLORS
    ring_color = (255, 255, 255)     # selection ring and pick arc: must stand out from the canvas

    @property
    def swatch_count(self) -> int:
        return len(self.colors)

    def __init__(self, state: DrawingState, frame_size: tuple[int, int], canvas_size: tuple[int, int],
                 mirror: bool, flip_vertical: bool):
        super().__init__(frame_size, canvas_size, mirror, flip_vertical)
        self.state = state
        self._swatch: int | None = None     # swatch the pointer rests on, and since when
        self._swatch_since = 0.0
        self.pick = 0.0                     # 0..1 of PICK_S completed, drawn as an arc around that swatch
        self.message = "Open the canvas on the projector screen, then press Calibrate Projector."

    @property
    def drawing(self) -> bool:
        """Calibrated and running: the main window may feed the hand into the strokes."""
        return self.phase == "draw" and self.mapper.calibrated

    def swatch_rect(self, i: int) -> QRectF:
        return QRectF(PALETTE_X, PALETTE_Y + i * (SWATCH + GAP), SWATCH, SWATCH)

    @property
    def resting_swatch(self) -> int | None:
        return self._swatch

    def on_palette(self, point, now: float) -> bool:
        """Feed the pointer (canvas px, None = lost). True while it is over the palette, which blocks drawing; resting
        on a swatch for PICK_S selects its colour."""
        i = None
        if point is not None:
            for k in range(self.swatch_count):
                if self.swatch_rect(k).adjusted(-REACH, -REACH, REACH, REACH).contains(*point):
                    i = k
                    break
        if i != self._swatch:
            self._swatch, self._swatch_since, self.pick = i, now, 0.0
        if i is None:
            return False
        self.pick = min((now - self._swatch_since) / PICK_S, 1.0)
        if self.pick >= 1.0:
            self._select(i)
        return True

    def _select(self, i: int) -> None:
        if self.state.color != self.colors[i]:
            self.state.color = self.colors[i]
            self.state.end_stroke()      # the next stroke starts in the new colour

    def _geometry_found(self) -> None:
        self._enter("draw", "")

    def on_detection(self, det: Detection, now: float) -> None:
        if self.phase == "draw" and not self.mapper.calibrated:
            self.phase, self.message = "idle", "Camera orientation changed: calibrate the projector again."
        if det.frame is not None and self.phase in ("dark", "markers"):
            self._geometry_step(det.frame, now)

    def pointer_ring(self):
        return None if self.state.cursor is None else (self.state.cursor, QColor(255, 200, 0))
