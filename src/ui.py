"""PySide6 main window: canvas, preview, controls, diagnostics, calibration flow."""
import logging
import time

from PySide6.QtCore import QEvent, QSettings, Qt, QTimer
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from . import config
from .canvas import CANVAS_SIZE, CanvasWidget
from .chess_game import ChessGame
from .calibration import CORNER_NAMES, CalibrationError, CoordinateMapper
from .camera import Camera, list_cameras
from .drawing import DrawingState
from .filters import OneEuroFilter2D
from .gesture import PinchDetector, pinch_point
from .keyboard_layout import base_char
from .typing_mode import PreviewLabel, TypingMode
from .worker import CameraOpener, TrackingWorker

log = logging.getLogger(__name__)

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FingerTrace PoC — air-drawing (not touchscreen)")
        self.resize(1400, 800)
        self.camera = Camera()
        self.worker: TrackingWorker | None = None
        self.state = DrawingState(OneEuroFilter2D())
        self.game = ChessGame()
        self.mode = 0   # 0 = Air Drawing, 1 = Chess, 2 = Keyboard typing
        self.pinch = PinchDetector()
        self.pointer_smoother = OneEuroFilter2D()
        self.settings = QSettings("FingerTrace", "FingerTrace")
        mirror = self.settings.value("mirror", config.DEFAULT_MIRROR, type=bool)
        flip_v = self.settings.value("flip_vertical", config.DEFAULT_FLIP_VERTICAL, type=bool)
        self.pinch_to_draw = self.settings.value("pinch_to_draw", True, type=bool)
        self.mapper = CoordinateMapper((config.CAMERA_REQUEST_WIDTH, config.CAMERA_REQUEST_HEIGHT), CANVAS_SIZE,
                                       mirror=mirror, flip_vertical=flip_v)
        self.typing = TypingMode(self.mapper.frame_size, mirror, flip_v)
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
        QApplication.instance().installEventFilter(self)  # real keystrokes = ground truth in typing mode

    @property
    def chess_mode(self) -> bool:
        return self.mode == 1

    # ---- layout -------------------------------------------------------------------------
    def _build_ui(self):
        self.canvas = CanvasWidget(self.state)
        self.preview = PreviewLabel("Camera stopped")
        self.preview.clicked.connect(self._on_preview_click)
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

        self.app_box = QComboBox()
        self.app_box.addItems(["Air Drawing", "Chess (pinch to move pieces)", "Keyboard typing (camera reads keys)"])
        self.app_box.activated.connect(self._on_app_selected)
        self.camera_box = QComboBox()
        self.camera_box.activated.connect(self._on_camera_selected)  # user-driven only, not programmatic changes
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._refresh_cameras)
        self.start_btn = QPushButton("Start Camera")
        self.start_btn.clicked.connect(self._toggle_camera)
        self.draw_mode_box = QComboBox()
        self.draw_mode_box.addItems(["Pinch to draw", "Always draw"])
        self.draw_mode_box.setCurrentIndex(0 if self.pinch_to_draw else 1)
        self.draw_mode_box.activated.connect(self._on_draw_mode)
        self.draw_chk = QCheckBox("Draw Enabled")
        self.draw_chk.setChecked(True)
        self.draw_chk.toggled.connect(self.state.set_draw_enabled)
        self.mirror_chk = QCheckBox("Mirror Camera")
        self.mirror_chk.setChecked(self.mapper.mirror)  # before connecting, so it does not fire the handler
        self.mirror_chk.toggled.connect(self._on_mirror)
        self.flip_chk = QCheckBox("Flip Vertical (camera upside down)")
        self.flip_chk.setChecked(self.mapper.flip_vertical)
        self.flip_chk.toggled.connect(self._on_flip_vertical)
        clear = QPushButton("Clear Canvas")
        clear.clicked.connect(self._on_clear)
        self.clear_btn = clear
        self.new_game_btn = QPushButton("New Game")
        self.new_game_btn.clicked.connect(self._new_game)
        self.new_game_btn.setVisible(False)
        self.calib_btn = QPushButton("Calibrate")
        self.calib_btn.clicked.connect(self._start_calibration)
        self.confirm_btn = QPushButton("Confirm Point (Space)")
        self.confirm_btn.clicked.connect(self._confirm_point)
        self.confirm_btn.setEnabled(False)
        reset = QPushButton("Reset Calibration")
        reset.clicked.connect(self._reset_calibration)
        self.shortcuts = [  # disabled in typing mode so Space/Esc reach the keystroke logger
            QShortcut(QKeySequence(Qt.Key_Space), self, activated=self._confirm_point),
            QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self._cancel_calibration),
        ]

        cam_row = QHBoxLayout()
        cam_row.addWidget(self.camera_box, 1)
        cam_row.addWidget(refresh)
        side = QVBoxLayout()
        side.addWidget(QLabel("Application"))
        side.addWidget(self.app_box)
        for w in (self.status, self.preview):
            side.addWidget(w)
        side.addLayout(cam_row)
        for w in (self.start_btn, self.draw_mode_box, self.draw_chk, self.mirror_chk, self.flip_chk, clear, self.new_game_btn, self.calib_btn,
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
        if self.worker is not None or self.opener is not None:
            self.message = "Stop the camera before refreshing the camera list."
            return
        current = self.camera_box.currentData()
        self.camera_box.clear()
        found = list_cameras()
        for i, w, h in found:
            self.camera_box.addItem(f"Camera {i} ({w}x{h})", i)
        if current is not None:
            row = self.camera_box.findData(current)
            self.camera_box.setCurrentIndex(max(row, 0))
        if found:
            self.camera_unavailable = False
            self.message = f"Found {len(found)} camera(s)."
        else:
            self.camera_unavailable = True
            self.message = "No camera found. Check the USB cable/port, then press Refresh."

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
        self.typing.mapper.set_frame_size((info.width, info.height))
        self.worker = TrackingWorker(self.camera)
        self.worker.mirror = self.mirror_chk.isChecked()
        self.worker.flip_vertical = self.flip_chk.isChecked()
        self.worker.num_hands = config.TYPING_NUM_HANDS if self.mode == 2 else config.NUM_HANDS
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
        self.game.update(None, False)
        self.typing.session.update({}, time.monotonic())
        self.typing.cancel_calibration()
        self.pointer_smoother.reset()
        self.canvas.pinching = False
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
        pixmap = QPixmap.fromImage(image)
        if self.mode == 2:
            self.typing.overlay(pixmap)
        self.preview.setPixmap(pixmap)
        raw = det.tip_px
        self.last_tip_raw = raw
        if self.mode == 2:
            self.typing.on_detection(det, time.monotonic())
        elif self.chess_mode:
            self._update_chess(det)
        elif self.calibrating:
            self.state.update(None)
            self.canvas.pinching = False
        else:
            self._update_drawing(det)
        self.canvas.update()

    def _update_drawing(self, det):
        """Pinch mode: pointer = thumb/index midpoint, pen down only while pinched. Always mode: index tip."""
        pinching = self.pinch.update(det.landmarks_px)
        if det.landmarks_px is None:
            self.state.update(None)
            self.canvas.pinching = False
            return
        raw = pinch_point(det.landmarks_px) if self.pinch_to_draw else det.tip_px
        self.state.update(self.mapper.map(raw), pen_down=pinching or not self.pinch_to_draw)
        self.canvas.pinching = self.pinch_to_draw and pinching

    def _on_draw_mode(self, row: int):
        self.pinch_to_draw = row == 0
        self.settings.setValue("pinch_to_draw", self.pinch_to_draw)
        self.state.end_stroke()

    def _update_chess(self, det):
        """Pointer = midpoint of thumb and index tips; pinching grabs, opening the fingers drops."""
        pinching = self.pinch.update(det.landmarks_px)
        pointer = None
        if det.landmarks_px is not None and not self.calibrating:
            mapped = self.mapper.map(pinch_point(det.landmarks_px))
            pointer = self.pointer_smoother.update(mapped) if mapped is not None else None
        if pointer is None:
            self.pointer_smoother.reset()
        self.game.update(pointer, pinching and pointer is not None)
        self.canvas.pinching = pinching and pointer is not None

    # ---- application selection ----------------------------------------------------------
    def _on_app_selected(self, row: int):
        self._cancel_calibration()
        self.typing.cancel_calibration()
        self.mode = row
        self.canvas.game = self.game if row == 1 else None
        self.canvas.typing = self.typing if row == 2 else None
        self.state.update(None)
        self.game.update(None, False)
        self.typing.session.update({}, time.monotonic())
        self.pointer_smoother.reset()
        self.canvas.pinching = False
        if self.worker is not None:
            self.worker.num_hands = config.TYPING_NUM_HANDS if row == 2 else config.NUM_HANDS
        for sc in self.shortcuts:
            sc.setEnabled(row != 2)
        self.draw_mode_box.setVisible(row == 0)
        self.draw_chk.setVisible(row == 0)
        self.clear_btn.setVisible(row != 1)
        self.clear_btn.setText("Clear Canvas" if row == 0 else "Clear Text")
        self.new_game_btn.setVisible(row == 1)
        self.confirm_btn.setVisible(row != 2)
        self.calib_btn.setText("Calibrate Keyboard (click 4 corners)" if row == 2 else "Calibrate")
        self.message = ("Make the preview upright (Mirror / Flip Vertical), then Calibrate Keyboard."
                        if row == 2 else "")
        self.canvas.update()

    def _on_clear(self):
        if self.mode == 2:
            self.typing.session.clear()
        else:
            self.state.clear()
        self.canvas.update()

    def _on_preview_click(self, x: float, y: float):
        if self.mode == 2:
            self.typing.click(x, y, self.preview)
            self.message = self.typing.message
            self.canvas.update()

    def eventFilter(self, obj, event):
        """In typing mode, record real keystrokes as ground truth and keep them away from the buttons/combos."""
        if self.mode == 2 and event.type() == QEvent.KeyPress and self.isActiveWindow():
            if event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
                return False  # leave Cmd+Q etc. alone
            if not event.isAutoRepeat() and (ch := self._real_char(event)) is not None:
                self.typing.session.real_key(ch, time.monotonic())
            return True
        return super().eventFilter(obj, event)

    @staticmethod
    def _real_char(event) -> str | None:
        key = event.key()
        if key == Qt.Key_Backspace:
            return "\b"
        if key in (Qt.Key_Return, Qt.Key_Enter):
            return "\n"
        if key == Qt.Key_Tab:
            return "\t"
        text = event.text()
        return base_char(text) if len(text) == 1 and text.isprintable() else None

    def _new_game(self):
        self.game.new_game()
        self.canvas.update()

    def _on_mirror(self, on: bool):
        self.settings.setValue("mirror", on)
        self.mapper.set_mirror(on)  # also invalidates calibration (stored in view coordinates)
        self.typing.mapper.set_mirror(on)
        if self.worker is not None:
            self.worker.mirror = on
        self._orientation_changed("Mirror")

    def _on_flip_vertical(self, on: bool):
        self.settings.setValue("flip_vertical", on)
        self.mapper.set_flip_vertical(on)
        self.typing.mapper.set_flip_vertical(on)
        if self.worker is not None:
            self.worker.flip_vertical = on
        self._orientation_changed("Vertical flip")

    def _orientation_changed(self, what: str):
        self.state.end_stroke()
        self.typing.cancel_calibration()
        self.game.update(None, False)  # a pointer jump from re-mapping must not move a held piece
        if self.calibrating:
            self._start_calibration()
        else:
            self.message = f"{what} changed: calibration reset (linear fallback in use)."

    # ---- calibration --------------------------------------------------------------------
    def _start_calibration(self):
        if self.worker is None:
            self.message = "Start the camera before calibrating."
            return
        if self.mode == 2:
            self.typing.start_calibration()
            self.message = self.typing.message
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
        self.typing.mapper.reset()
        self.typing.cancel_calibration()
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
        elif self.mode == 0 and not self.state.draw_enabled:
            status = "Paused"
        else:
            seen = (bool(self.typing.session.fingertips) if self.mode == 2 else
                    self.game.pointer is not None if self.chess_mode else self.state.cursor is not None)
            status = "Hand detected" if seen else "No hand detected"
        self.status.setText(status)
        if self.mode == 2:
            self.mapping_label.setText("Keyboard mapping: calibrated (homography)" if self.typing.mapper.calibrated
                                       else "Keyboard mapping: NOT calibrated — typing disabled")
        elif self.mapper.calibrated:
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
            + (f"\n{self.typing.stats_text(time.monotonic())}" if self.mode == 2 else "")
        )

    def closeEvent(self, event):
        if self.opener is not None:
            self.opener.wait()
        self._stop_camera()
        super().closeEvent(event)
