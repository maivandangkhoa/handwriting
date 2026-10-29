"""Finding a projected canvas in the camera image, shared by the apps that run on a projector.

Geometry calibration is a small state machine fed by camera frames:
  dark -> markers      the canvas is shown black, then with four bright discs; differencing the frames finds them
  manual               fallback when the discs were not found: the user clicks them on the camera preview
By default the discs sit near the canvas corners; a subclass can move them (`markers`, `marker_radius`) and says what
happens once the canvas is found (`_geometry_found`).
"""
import logging
import os
import time

import cv2
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QPolygonF

from . import config
from .calibration import CalibrationError, CoordinateMapper
from .preview import preview_to_view
from .projector_calib import MarkerError, find_markers, order_corners

log = logging.getLogger(__name__)
Point = tuple[float, float]
DISC_FRACTIONS = [(0.08, 0.10), (0.92, 0.10), (0.92, 0.90), (0.08, 0.90)]   # TL, TR, BR, BL of the canvas
DISC_RADIUS = 0.03    # of the canvas width


class ProjectorSurface:
    ready_phase = "play"     # the phase in which the app is up and running; a finished calibration survives a camera stop

    def __init__(self, frame_size: tuple[int, int], canvas_size: tuple[int, int], mirror: bool, flip_vertical: bool):
        self.canvas_size = canvas_size
        self.mapper = CoordinateMapper(frame_size, canvas_size, mirror=mirror, flip_vertical=flip_vertical)
        self.phase = "idle"
        self.message = "Open the canvas on the projector screen, then press Calibrate Projector."
        self._phase_start = 0.0
        self._dark = None
        self._pending: list[Point] = []

    # ---- what the canvas should show ----
    @property
    def pattern(self) -> str | None:
        return {"dark": "dark", "markers": "markers", "manual": "markers"}.get(self.phase)

    @property
    def markers(self) -> list[Point]:
        w, h = self.canvas_size
        return [(fx * w, fy * h) for fx, fy in DISC_FRACTIONS]

    @property
    def marker_radius(self) -> float:
        return DISC_RADIUS * self.canvas_size[0]

    # Extras the canvas may draw; apps that have them override.
    paints_canvas = False    # True: the app draws the whole canvas itself via `paint`
    target = None            # canvas point of a ring to touch while recording references
    progress = 0.0           # 0..1 hold progress shown on that ring
    dwell_square = None      # canvas centre of the square a point-and-hold is filling
    hint = ""                # instruction drawn on the projected canvas

    # ---- calibration ----
    def start_calibration(self, now: float | None = None) -> None:
        self.mapper.reset()
        self._pending, self._dark = [], None
        self._enter("dark", "Calibrating: keep your hands away from the projected canvas.", now)

    def camera_stopped(self) -> None:
        """The camera went away: an unfinished calibration cannot continue (a finished one is kept)."""
        if self.mapper.calibrated and self.phase == self.ready_phase:
            self._camera_lost()
        elif self.phase != "idle":
            self.phase, self.message = "idle", "Calibration interrupted: press Calibrate Projector."

    def _camera_lost(self) -> None:
        pass

    def _enter(self, phase: str, message: str, now: float | None = None) -> None:
        log.info("projector phase %s -> %s: %s", self.phase, phase, message)
        self.phase, self.message = phase, message
        self._phase_start = time.monotonic() if now is None else now

    def click(self, x: float, y: float, label) -> None:
        """Manual fallback: the user clicks the four discs (any order) on the camera preview."""
        point = preview_to_view(x, y, label, self.mapper.frame_size[0]) if self.phase == "manual" else None
        if point is None:
            return
        self._pending.append(point)
        if len(self._pending) < 4:
            self.message = f"Clicked {len(self._pending)}/4 discs. Click the next one."
        else:
            self._set_geometry(self._pending)

    def _set_geometry(self, view_points: list[Point]) -> None:
        try:
            self.mapper.calibrate(order_corners(view_points), self.markers)
        except CalibrationError as exc:
            self._pending = []
            self._enter("manual", f"Calibration rejected ({exc}). Click the 4 discs on the preview.")
            return
        self._geometry_found()

    def _geometry_found(self) -> None:
        raise NotImplementedError

    def _geometry_step(self, frame, now: float) -> None:
        if now - self._phase_start < config.PROJECTOR_PHASE_S:
            return
        if self.phase == "dark":
            self._dark = frame.copy()
            self._enter("markers", "Calibrating: finding the four corner discs…", now)
            return
        try:
            found = find_markers(self._dark, frame)
        except MarkerError as exc:
            log.warning("projector calibration: %s", exc)
            self._dump_debug(frame)
            self._pending = []
            self._enter("manual", f"{exc} Or click the 4 discs on the camera preview.", now)
            return
        self._set_geometry([self.mapper.to_view(p) for p in found])

    def _dump_debug(self, lit) -> None:
        """With FINGERTRACE_DEBUG_DIR set, keep the two calibration frames of a failed attempt for inspection."""
        folder = os.environ.get("FINGERTRACE_DEBUG_DIR")
        if folder and self._dark is not None:
            cv2.imwrite(os.path.join(folder, "calib_dark.png"), self._dark)
            cv2.imwrite(os.path.join(folder, "calib_lit.png"), lit)
            log.info("calibration frames saved to %s", folder)

    def canvas_in_view(self) -> list[Point] | None:
        """The four canvas corners as seen in the camera view, once calibrated."""
        corners = [(0, 0), (self.canvas_size[0], 0), self.canvas_size, (0, self.canvas_size[1])]
        return self.mapper.canvas_to_view_many(corners)

    # ---- preview overlay ----
    def overlay(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            return
        scale = config.PREVIEW_WIDTH / self.mapper.frame_size[0]
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)
        if self.phase == "manual":
            p.setPen(QPen(QColor(255, 60, 60), 2))
            for x, y in self._pending:
                p.drawEllipse(QPointF(x * scale, y * scale), 5, 5)
        elif self.mapper.calibrated:
            view = self.canvas_in_view()
            if view is not None:
                p.setPen(QPen(QColor(0, 255, 255, 170), 2))
                p.drawPolygon(QPolygonF([QPointF(x * scale, y * scale) for x, y in view]))
            if (pointer := self.pointer_ring()) is not None:
                v = self.mapper.canvas_to_view(pointer[0])
                if v is not None:
                    p.setPen(QPen(pointer[1], 3))
                    p.drawEllipse(QPointF(v[0] * scale, v[1] * scale), 7, 7)
        p.end()

    def pointer_ring(self) -> tuple[Point, QColor] | None:
        """Canvas point and colour of the marker the preview draws for the pointer, or None."""
        return None
