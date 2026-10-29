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
from .camera import Camera
from .diagnostics import camera_text, mapping_text
from .drawing import DrawingState
from .filters import OneEuroFilter2D
from .gesture import PinchDetector, PointDetector, pinch_point
from .preview import PreviewLabel
from .piano_mode import ProjectorPiano
from .piano_sound import QtPlayer
from .projector_chess import ProjectorChess
from .projector_draw import ProjectorDraw
from .projector_window import ProjectorControls, ProjectorWindow
from .typing_mode import TypingControls, TypingMode, real_char
from .ui_camera import CameraLifecycle
from .worker import CameraOpener, TrackingWorker

log = logging.getLogger(__name__)

class MainWindow(CameraLifecycle, QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FingerTrace PoC — air-drawing (not touchscreen)")
        self.resize(1400, 800)
        self.camera = Camera()
        self.worker: TrackingWorker | None = None
        self.state = DrawingState(OneEuroFilter2D())
        self.game = ChessGame()
        self.mode = 0   # 0 = Air Drawing, 1 = Chess on projector, 2 = Keyboard typing, 3 = Air Drawing on projector, 4 = Piano on projector
        self.pinch = PinchDetector()
        self.point = PointDetector()
        self.settings = QSettings("FingerTrace", "FingerTrace")
        mirror = self.settings.value("mirror", config.DEFAULT_MIRROR, type=bool)
        flip_v = self.settings.value("flip_vertical", config.DEFAULT_FLIP_VERTICAL, type=bool)
        legacy = 0 if self.settings.value("pinch_to_draw", True, type=bool) else 1     # the earlier two-way setting
        self.draw_style = self.settings.value("draw_style", legacy, type=int)   # 0 pinch, 1 always, 2 index out = draw
        self.mapper = CoordinateMapper((config.CAMERA_REQUEST_WIDTH, config.CAMERA_REQUEST_HEIGHT), CANVAS_SIZE,
                                       mirror=mirror, flip_vertical=flip_v)
        self.typing = TypingMode(self.mapper.frame_size, mirror, flip_v)
        self.proj = ProjectorChess(self.game, self.mapper.frame_size, CANVAS_SIZE, mirror, flip_v)
        self.draw_proj = ProjectorDraw(self.state, self.mapper.frame_size, CANVAS_SIZE, mirror, flip_v)
        self.piano = ProjectorPiano(self.mapper.frame_size, CANVAS_SIZE, mirror, flip_v)
        self.mappers = [self.mapper, self.typing.mapper, self.proj.mapper, self.draw_proj.mapper, self.piano.mapper]   # all follow the camera size / orientation
        self.proj_ctl = ProjectorControls()
        self.proj_ctl.calibrate_clicked.connect(self._calibrate_projector)
        self.proj_ctl.open_clicked.connect(self._open_projector)
        self.proj_ctl.setVisible(False)
        self.proj_win: ProjectorWindow | None = None
        sensitivity = self.settings.value("typing_sensitivity", config.TYPING_SENSITIVITY, type=int)
        self.typing.session.set_sensitivity(sensitivity)
        self.typing.auto_detect = self.settings.value("auto_detect_keyboard", True, type=bool)
        self.typing_ctl = TypingControls(sensitivity, self.typing.auto_detect)
        self.typing_ctl.sensitivity_changed.connect(self._on_sensitivity)
        self.typing_ctl.auto_toggled.connect(self._on_auto_detect)
        self.typing_ctl.auto_clicked.connect(lambda: self.typing.maybe_auto_calibrate(self.camera.latest, time.monotonic(), force=True))
        self.typing_ctl.setVisible(False)
        self.last_tip_raw: tuple[float, float] | None = None
        self.calib_points: list[tuple[float, float]] = []
        self.calibrating = False
        self.message = ""
        self.camera_unavailable = False
        self.opener: CameraOpener | None = None
        self._shown_typing_message = ""
        self._build_ui()
        self._refresh_cameras()
        self.timer = QTimer(self, interval=250, timeout=self._update_diagnostics)
        self.timer.start()
        self._update_diagnostics()
        QApplication.instance().installEventFilter(self)  # real keystrokes = ground truth in typing mode

    @property
    def chess_mode(self) -> bool:
        return self.mode == 1

    @property
    def projector_app(self):
        """The projector app of the current mode (chess or drawing), else None."""
        return {1: self.proj, 3: self.draw_proj, 4: self.piano}.get(self.mode)

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
        self.app_box.addItems(["Air Drawing", "Chess on projector (touch the pieces)", "Keyboard typing (camera reads keys)",
                                "Air Drawing on projector (move your hand over the canvas)",
                                "Piano on projector (tap the keys to play)"])
        self.app_box.activated.connect(self._on_app_selected)
        self.camera_box = QComboBox()
        self.camera_box.activated.connect(self._on_camera_selected)  # user-driven only, not programmatic changes
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._refresh_cameras)
        self.start_btn = QPushButton("Start Camera")
        self.start_btn.clicked.connect(self._toggle_camera)
        self.draw_mode_box = QComboBox()
        self.draw_mode_box.addItems(["Pinch to draw", "Always draw", "Point to draw (index out = draw, curled = lift)"])
        self.draw_mode_box.setCurrentIndex(self.draw_style)
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
                  self.confirm_btn, reset, self.typing_ctl, self.proj_ctl, self.mapping_label, self.hint, self.diag):
            side.addWidget(w)
        side.addStretch(1)
        panel = QWidget()
        panel.setLayout(side)
        panel.setFixedWidth(config.PREVIEW_WIDTH + 20)
        root = QHBoxLayout(self)
        root.addWidget(self.canvas, 1)
        root.addWidget(panel)

    # ---- camera -------------------------------------------------------------------------
    def _on_opened(self, info):
        self._finish_open()
        for m in self.mappers:
            m.set_frame_size((info.width, info.height))
        self.worker = TrackingWorker(self.camera)
        self.worker.mirror = self.mirror_chk.isChecked()
        self.worker.flip_vertical = self.flip_chk.isChecked()
        self.worker.num_hands = config.TYPING_NUM_HANDS if self.mode in (2, 4) else config.NUM_HANDS
        self.worker.result.connect(self._on_result)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()
        self.start_btn.setText("Stop Camera")
        self.message = ""

    def _stop_worker(self):
        if self.worker is not None:
            self.worker.stop()
            self.worker = None
        self.state.update(None)
        self.game.update(None, False)
        self.typing.session.update({}, time.monotonic())
        self.typing.cancel_calibration()
        self.canvas.pinching = False
        self.last_tip_raw = None
        self.proj.camera_stopped()
        self.draw_proj.camera_stopped()
        self.piano.camera_stopped()
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
        elif self.projector_app is not None:
            self.projector_app.overlay(pixmap)
        self.preview.setPixmap(pixmap)
        raw = det.tip_px
        self.last_tip_raw = raw
        if self.mode == 2:
            self.typing.maybe_auto_calibrate(self.camera.latest, time.monotonic())
            self.typing.on_detection(det, time.monotonic())
        elif self.chess_mode:
            self.proj.on_detection(det, time.monotonic())
        elif self.mode == 4:
            self.piano.on_detection(det, time.monotonic())
        elif self.mode == 3:
            self.draw_proj.on_detection(det, time.monotonic())
            if self.draw_proj.drawing:
                self._update_drawing(det, self.draw_proj)
            else:
                self.state.update(None)
                self.canvas.pinching = False
        elif self.calibrating:
            self.state.update(None)
            self.canvas.pinching = False
        else:
            self._update_drawing(det)
        self.canvas.update()

    def _update_drawing(self, det, surface=None):
        """Pinch mode: pointer = thumb/index midpoint, pen down only while pinched. Always mode: index tip, pen always
        down. Point mode: index tip, pen down while the index finger is straight, lifted when it is curled.
        On a projector `surface` supplies the mapping and the colour palette, which the pen must not draw on."""
        mapper = self.mapper if surface is None else surface.mapper
        pinching = self.pinch.update(det.landmarks_px)
        pointing = self.point.update(det.landmarks_px)
        if det.landmarks_px is None:
            self.state.update(None)
            self.canvas.pinching = False
            if surface is not None:
                surface.on_palette(None, time.monotonic())
            return
        raw = pinch_point(det.landmarks_px) if self.draw_style == 0 else det.tip_px
        point = mapper.map(raw)
        pen_down = (pinching, True, pointing)[self.draw_style]
        if surface is not None and surface.on_palette(point, time.monotonic()):
            pen_down = False
        self.state.update(point, pen_down=pen_down)
        self.canvas.pinching = self.draw_style != 1 and pen_down      # the cursor turns green while the pen is down

    def _on_draw_mode(self, row: int):
        self.draw_style = row
        self.settings.setValue("draw_style", row)
        self.state.end_stroke()

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
        self.canvas.pinching = False
        self.canvas.projector = self.projector_app
        self._bind_projector_window()
        if self.worker is not None:
            self.worker.num_hands = config.TYPING_NUM_HANDS if row in (2, 4) else config.NUM_HANDS
        for sc in self.shortcuts:
            sc.setEnabled(row != 2)
        self.draw_mode_box.setVisible(row in (0, 3))
        self.draw_chk.setVisible(row in (0, 3))
        self.clear_btn.setVisible(row not in (1, 4))
        self.clear_btn.setText("Clear Canvas" if row == 0 else "Clear Text")
        self.new_game_btn.setVisible(row == 1)
        self.confirm_btn.setVisible(row == 0)
        self.calib_btn.setVisible(row in (0, 2))
        self.proj_ctl.setVisible(row in (1, 3, 4))
        self._load_piano_sounds(row)
        self.typing_ctl.setVisible(row == 2)
        self.calib_btn.setText("Calibrate Keyboard (click 4 corners)" if row == 2 else "Calibrate")
        self.message = ("Make the preview upright (Mirror / Flip Vertical), then Calibrate Keyboard."
                        if row == 2 else "")
        self.canvas.update()

    def _load_piano_sounds(self, row: int):
        """The 24 tones are synthesised on first use of the piano, not at start-up."""
        if row == 4 and self.piano.player is None:
            try:
                self.piano.player = QtPlayer()
            except Exception as exc:   # no audio support: the piano still shows, silently
                log.error("Piano sound unavailable: %s", exc)
                self.piano.message = f"Piano sound unavailable ({exc}); the keys will light up but stay silent."

    def _on_auto_detect(self, on: bool):
        self.settings.setValue("auto_detect_keyboard", on)
        self.typing.auto_detect = on

    def _on_sensitivity(self, level: int):
        self.settings.setValue("typing_sensitivity", level)
        self.typing.session.set_sensitivity(level)

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
        elif self.projector_app is not None:
            self.projector_app.click(x, y, self.preview)

    def eventFilter(self, obj, event):
        """In typing mode, record real keystrokes as ground truth and keep them away from the buttons/combos."""
        if self.mode == 2 and event.type() == QEvent.KeyPress and self.isActiveWindow():
            if event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
                return False  # leave Cmd+Q etc. alone
            if not event.isAutoRepeat() and (ch := real_char(event)) is not None:
                self.typing.session.real_key(ch, time.monotonic())
            return True
        return super().eventFilter(obj, event)

    def _new_game(self):
        self.game.new_game()
        self.canvas.update()

    def _calibrate_projector(self):
        if self.worker is None:
            self.message = "Start the camera before calibrating."
            return
        self.projector_app.start_calibration()

    def _open_projector(self, index: int):
        screens = QApplication.screens()
        if self.proj_win is None:
            self.proj_win = ProjectorWindow(self.state, self.canvas)
            self._bind_projector_window()
        self.proj_win.show_on(screens[min(index, len(screens) - 1)])

    def _bind_projector_window(self):
        """The projector window shows what the current app shows; only the cursor differs (the finger is the cursor
        for chess, but the drawing pen position is useful to see)."""
        win = self.proj_win
        if win is not None:
            win.game, win.projector, win.show_cursor = self.game if self.mode == 1 else None, self.projector_app, self.mode == 3
            win.update()

    def _on_mirror(self, on: bool):
        self.settings.setValue("mirror", on)
        for m in self.mappers:
            m.set_mirror(on)  # also invalidates calibration (stored in view coordinates)
        if self.worker is not None:
            self.worker.mirror = on
        self._orientation_changed("Mirror")

    def _on_flip_vertical(self, on: bool):
        self.settings.setValue("flip_vertical", on)
        for m in self.mappers:
            m.set_flip_vertical(on)
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
        for m in self.mappers:
            m.reset()
        self.typing.cancel_calibration()
        self._end_calibration()
        self.message = "Calibration reset: using linear fallback mapping."

    # ---- diagnostics --------------------------------------------------------------------
    def _update_diagnostics(self):
        w = self.worker
        if self.mode == 2 and self.typing.message != self._shown_typing_message:
            self._shown_typing_message = self.message = self.typing.message   # set by the background detection
        elif self.projector_app is not None:
            self.message = self.projector_app.message
        if self.camera.error and w is not None:
            self._stop_camera()
            self.camera_unavailable = True
            self.message = self.camera.error
        if self.opener is not None:
            status = "Opening camera…"
        elif w is None:
            status = "Camera unavailable" if self.camera_unavailable else "Camera stopped"
        elif self.mode in (0, 3) and not self.state.draw_enabled:
            status = "Paused"
        else:
            seen = (bool(self.typing.session.fingertips) if self.mode == 2 else
                    bool(self.piano.session.fingertips) if self.mode == 4 else
                    self.game.pointer is not None if self.chess_mode else self.state.cursor is not None)
            status = "Hand detected" if seen else "No hand detected"
        self.status.setText(status)
        self.mapping_label.setText(mapping_text(self.mode, self.mapper, self.typing, self.projector_app))
        self.hint.setText(self.message)
        extra = (self.typing.stats_text(time.monotonic()) if self.mode == 2 else
                 self.proj.stats_text() if self.chess_mode else self.piano.stats_text() if self.mode == 4 else "")
        self.diag.setText(camera_text(self.camera, w, extra))

    def closeEvent(self, event):
        if self.opener is not None:
            self.opener.wait()
        self.typing.wait_for_job()
        if self.proj_win is not None:
            self.proj_win.close()
        self._stop_camera()
        super().closeEvent(event)
