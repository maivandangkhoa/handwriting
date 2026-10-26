"""PySide6 main window: canvas, preview, controls, diagnostics, calibration flow."""
import logging

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from . import config
from .calibration import CORNER_NAMES, CalibrationError, CoordinateMapper
from .camera import Camera, list_cameras
from .drawing import DrawingState
from .worker import CameraOpener, TrackingWorker

log = logging.getLogger(__name__)

CANVAS_SIZE = (config.CANVAS_WIDTH, config.CANVAS_HEIGHT)
TARGETS = [(0.06, 0.08), (0.94, 0.08), (0.94, 0.92), (0.06, 0.92)]  # TL, TR, BR, BL as canvas fractions


class CanvasWidget(QWidget):
    """Draws strokes stored in logical canvas coordinates, letterboxed to keep the aspect ratio."""

    def __init__(self, state: DrawingState):
        super().__init__()
        self.state = state
        self.target_index: int | None = None  # calibration target to highlight
        self.setMinimumSize(480, 270)

    def _viewport(self) -> tuple[QRectF, float]:
        s = min(self.width() / CANVAS_SIZE[0], self.height() / CANVAS_SIZE[1])
        w, h = CANVAS_SIZE[0] * s, CANVAS_SIZE[1] * s
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h), s

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(40, 40, 40))
        rect, s = self._viewport()
        p.fillRect(rect, QColor(255, 255, 255))

        def to_w(pt):
            return QPointF(rect.x() + pt[0] * s, rect.y() + pt[1] * s)

        p.setPen(QPen(QColor(20, 20, 120), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        for stroke in self.state.strokes:
            if len(stroke) == 1:
                p.drawPoint(to_w(stroke[0]))
            for a, b in zip(stroke, stroke[1:]):
                p.drawLine(to_w(a), to_w(b))
        if self.target_index is not None:
            fx, fy = TARGETS[self.target_index]
            c = to_w((fx * CANVAS_SIZE[0], fy * CANVAS_SIZE[1]))
            p.setPen(QPen(QColor(220, 0, 0), 3))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(c, 22, 22)
            p.drawLine(c + QPointF(-30, 0), c + QPointF(30, 0))
            p.drawLine(c + QPointF(0, -30), c + QPointF(0, 30))
        if self.state.cursor is not None:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(230, 40, 40, 200))
            p.drawEllipse(to_w(self.state.cursor), 9, 9)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FingerTrace PoC — air-drawing (not touchscreen)")
        self.resize(1400, 800)
        self.camera = Camera()
        self.worker: TrackingWorker | None = None
        self.state = DrawingState(config.SMOOTHING_ALPHA)
        self.mapper = CoordinateMapper((config.CAMERA_REQUEST_WIDTH, config.CAMERA_REQUEST_HEIGHT), CANVAS_SIZE)
        self.last_tip_raw: tuple[float, float] | None = None
        self.calib_points: list[tuple[float, float]] = []
        self.calibrating = False
        self.message = ""
        self.camera_unavailable = False
        self.opener: CameraOpener | None = None
        self._build_ui()
        self._refresh_cameras()
        self.timer = QTimer(self, interval=250, timeout=self._update_diagnostics)
        self.timer.start()
        self._update_diagnostics()

    # ---- layout -------------------------------------------------------------------------
    def _build_ui(self):
        self.canvas = CanvasWidget(self.state)
        self.preview = QLabel("Camera stopped")
        self.preview.setFixedSize(config.PREVIEW_WIDTH, config.PREVIEW_WIDTH * 9 // 16)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setFrameShape(QFrame.Box)
        self.status = QLabel()
        self.status.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.mapping_label = QLabel()
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.diag = QLabel()
        self.diag.setStyleSheet("font-family: Menlo, monospace;")

        self.camera_box = QComboBox()
        self.camera_box.activated.connect(self._on_camera_selected)  # user-driven only, not programmatic changes
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._refresh_cameras)
        self.start_btn = QPushButton("Start Camera")
        self.start_btn.clicked.connect(self._toggle_camera)
        self.draw_chk = QCheckBox("Draw Enabled")
        self.draw_chk.setChecked(True)
        self.draw_chk.toggled.connect(self.state.set_draw_enabled)
        self.mirror_chk = QCheckBox("Mirror Camera")
        self.mirror_chk.setChecked(True)
        self.mirror_chk.toggled.connect(self._on_mirror)
        clear = QPushButton("Clear Canvas")
        clear.clicked.connect(self.state.clear)
        clear.clicked.connect(self.canvas.update)
        self.calib_btn = QPushButton("Calibrate")
        self.calib_btn.clicked.connect(self._start_calibration)
        self.confirm_btn = QPushButton("Confirm Point (Space)")
        self.confirm_btn.clicked.connect(self._confirm_point)
        self.confirm_btn.setEnabled(False)
        reset = QPushButton("Reset Calibration")
        reset.clicked.connect(self._reset_calibration)
        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self._confirm_point)
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self._cancel_calibration)

        cam_row = QHBoxLayout()
        cam_row.addWidget(self.camera_box, 1)
        cam_row.addWidget(refresh)
        side = QVBoxLayout()
        for w in (self.status, self.preview):
            side.addWidget(w)
        side.addLayout(cam_row)
        for w in (self.start_btn, self.draw_chk, self.mirror_chk, clear, self.calib_btn,
                  self.confirm_btn, reset, self.mapping_label, self.hint, self.diag):
            side.addWidget(w)
        side.addStretch(1)
        panel = QWidget()
        panel.setLayout(side)
        panel.setFixedWidth(config.PREVIEW_WIDTH + 20)
        root = QHBoxLayout(self)
        root.addWidget(self.canvas, 1)
        root.addWidget(panel)

    # ---- camera -------------------------------------------------------------------------
    def _refresh_cameras(self):
        self.camera_box.clear()
        found = list_cameras() if self.worker is None else []
        for i, w, h in found:
            self.camera_box.addItem(f"Camera {i} ({w}x{h})", i)
        if not found and self.worker is None:
            self.camera_unavailable = True
            self.message = "No camera found. Connect the USB camera and grant camera permission, then Refresh."

    def _on_camera_selected(self, _row: int):
        """Switch to the newly selected camera immediately if one is already running."""
        if self.worker is not None and self.opener is None:
            self._stop_worker()  # the opener closes the old camera in the background
            self._start_camera()

    def _toggle_camera(self):
        if self.opener is not None:
            return
        if self.worker is not None:
            self._stop_camera()
        else:
            self._start_camera()

    def _start_camera(self):
        index = self.camera_box.currentData()
        if index is None:
            self.message = "No camera selected. Connect the USB camera and press Refresh."
            return
        self.camera_unavailable = False
        self.message = f"Opening camera {index}…"
        self._set_busy(True)
        self.preview.setPixmap(QPixmap())
        self.preview.setText("Opening camera…")
        self.opener = CameraOpener(self.camera, index)
        self.opener.opened.connect(self._on_opened)
        self.opener.failed.connect(self._on_open_failed)
        self.opener.start()

    def _set_busy(self, busy: bool):
        self.start_btn.setEnabled(not busy)
        self.camera_box.setEnabled(not busy)
        self.status.setText("Opening camera…" if busy else self.status.text())

    def _finish_open(self):
        self.opener.wait()
        self.opener = None
        self._set_busy(False)

    def _on_open_failed(self, msg: str):
        log.error("%s", msg)
        self._finish_open()
        self.camera_unavailable = True
        self.message = msg
        self.start_btn.setText("Start Camera")

    def _on_opened(self, info):
        self._finish_open()
        self.mapper.set_frame_size((info.width, info.height))
        self.worker = TrackingWorker(self.camera)
        self.worker.mirror = self.mirror_chk.isChecked()
        self.worker.result.connect(self._on_result)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()
        self.start_btn.setText("Stop Camera")
        self.message = ""

    def _stop_camera(self):
        self._stop_worker()
        self.camera.close()

    def _stop_worker(self):
        if self.worker is not None:
            self.worker.stop()
            self.worker = None
        self.state.update(None)
        self.last_tip_raw = None
        self._cancel_calibration()
        self.start_btn.setText("Start Camera")
        self.preview.setPixmap(QPixmap())
        self.preview.setText("Camera stopped")
        self.canvas.update()

    def _on_failed(self, msg: str):
        log.error("Worker failed: %s", msg)
        self._stop_camera()
        self.camera_unavailable = True
        self.message = msg

    # ---- per-frame ----------------------------------------------------------------------
    def _on_result(self, image, det):
        self.preview.setPixmap(QPixmap.fromImage(image))
        raw = det.tip_px
        self.last_tip_raw = raw
        if self.calibrating:
            self.state.update(None)
        else:
            self.state.update(self.mapper.map(raw) if raw is not None else None)
        self.canvas.update()

    def _on_mirror(self, on: bool):
        self.mapper.set_mirror(on)  # also invalidates calibration (stored in view coordinates)
        if self.worker is not None:
            self.worker.mirror = on
        self.state.end_stroke()
        if self.calibrating:
            self._start_calibration()
        else:
            self.message = "Mirror changed: calibration reset (linear fallback in use)."

    # ---- calibration --------------------------------------------------------------------
    def _start_calibration(self):
        if self.worker is None:
            self.message = "Start the camera before calibrating."
            return
        self.calibrating = True
        self.calib_points = []
        self.state.end_stroke()
        self.confirm_btn.setEnabled(True)
        self._show_target()

    def _show_target(self):
        i = len(self.calib_points)
        self.canvas.target_index = i
        self.message = f"Calibration {i + 1}/4: point your fingertip at the {CORNER_NAMES[i].upper()} target, then press Space."
        self.canvas.update()

    def _confirm_point(self):
        if not self.calibrating:
            return
        if self.last_tip_raw is None:
            self.message = "No hand detected — show your hand, then confirm again."
            return
        self.calib_points.append(self.mapper.to_view(self.last_tip_raw))
        if len(self.calib_points) < 4:
            self._show_target()
            return
        try:
            self.mapper.calibrate(self.calib_points)
        except CalibrationError as exc:
            self.message = f"Calibration rejected: {exc}"
            self.calib_points = []
            self.canvas.target_index = 0
            self.canvas.update()
            return
        self._end_calibration()
        self.message = "Calibration complete."

    def _cancel_calibration(self):
        if self.calibrating:
            self._end_calibration()
            self.message = "Calibration cancelled."

    def _end_calibration(self):
        self.calibrating = False
        self.calib_points = []
        self.canvas.target_index = None
        self.confirm_btn.setEnabled(False)
        self.canvas.update()

    def _reset_calibration(self):
        self.mapper.reset()
        self._end_calibration()
        self.message = "Calibration reset: using linear fallback mapping."

    # ---- diagnostics --------------------------------------------------------------------
    def _update_diagnostics(self):
        w = self.worker
        if self.camera.error and w is not None:
            self._stop_camera()
            self.camera_unavailable = True
            self.message = self.camera.error
        if self.opener is not None:
            status = "Opening camera…"
        elif w is None:
            status = "Camera unavailable" if self.camera_unavailable else "Camera stopped"
        elif not self.state.draw_enabled:
            status = "Paused"
        else:
            status = "Hand detected" if self.state.cursor is not None else "No hand detected"
        self.status.setText(status)
        if self.mapper.calibrated:
            self.mapping_label.setText("Mapping: calibrated (homography)")
        else:
            self.mapping_label.setText("Mapping: UNCALIBRATED — linear fallback over full camera frame")
        self.hint.setText(self.message)
        info = self.camera.info if w is not None else None
        if w is None or info is None:
            self.diag.setText("camera FPS : -\ntracking FPS: -\ninference   : -\nresolution  : -\nhands       : -")
            return
        self.diag.setText(
            f"camera FPS   : {self.camera.fps.rate():5.1f}\n"
            f"tracking FPS : {w.fps.rate():5.1f}\n"
            f"inference ms : {w.inference_ms.average():5.1f} (model call only, not end-to-end)\n"
            f"resolution   : {info.width}x{info.height} (driver FPS {info.fps:.0f})\n"
            f"hands        : {w.last_hand_count}\n"
            f"dropped      : {w.dropped} camera frames skipped"
        )

    def closeEvent(self, event):
        if self.opener is not None:
            self.opener.wait()
        self._stop_camera()
        super().closeEvent(event)
