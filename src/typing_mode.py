"""Keyboard-typing glue: click calibration on the camera preview, preview overlay, detections -> TypingSession."""
import time

import cv2
from PySide6.QtCore import QPointF, QThread, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QCheckBox, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from . import config
from .calibration import CORNER_NAMES, CalibrationError, CoordinateMapper
from .hand_slots import HandSlots
from .hand_tracker import Detection
from .keyboard_detect import Detection as KeyboardFound, detect_keyboard
from .keyboard_layout import KEYS, LAYOUT_H, LAYOUT_W, base_char
from .typing_session import FINGERTIPS, TypingSession

# Corner order matches CoordinateMapper.calibrate: layout TL, TR, BR, BL. Named by key (not by screen direction)
# so it stays unambiguous when the camera sees the keyboard rotated or mirrored.
CALIB_STEPS = (("the outer top-left corner of the ESC key", (0.0, 0.0)),
               ("the outer top-right corner of the power / Touch ID key", (LAYOUT_W, 0.0)),
               ("the outer bottom-right corner of the arrow-key cluster", (LAYOUT_W, LAYOUT_H)),
               ("the outer bottom-left corner of the FN key", (0.0, LAYOUT_H)))


def real_char(event) -> str | None:
    """Layout character of a real key event ('\\b' backspace, '\\n' enter, '\\t' tab), or None if not typeable."""
    key = event.key()
    if key == Qt.Key_Backspace:
        return "\b"
    if key in (Qt.Key_Return, Qt.Key_Enter):
        return "\n"
    if key == Qt.Key_Tab:
        return "\t"
    text = event.text()
    return base_char(text) if len(text) == 1 and text.isprintable() else None


class TypingControls(QWidget):
    """Typing-mode panel: automatic keyboard detection and the sensitivity slider (1..10)."""
    auto_toggled = Signal(bool)
    auto_clicked = Signal()
    sensitivity_changed = Signal(int)

    def __init__(self, sensitivity: int, auto: bool):
        super().__init__()
        self.auto_chk = QCheckBox("Auto-detect keyboard")
        self.auto_chk.setChecked(auto)
        self.auto_chk.toggled.connect(self.auto_toggled)
        self.auto_btn = QPushButton("Auto-calibrate Keyboard now")
        self.auto_btn.clicked.connect(self.auto_clicked)
        self.label = QLabel()
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(1, 10)
        self.slider.setValue(sensitivity)
        self.slider.valueChanged.connect(self._on_change)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for w in (self.auto_chk, self.auto_btn, self.label, self.slider):
            layout.addWidget(w)
        self._update_label(sensitivity)

    def _update_label(self, level: int) -> None:
        self.label.setText(f"Typing sensitivity: {level}/10 (higher = smaller movements count, more false keys)")

    def _on_change(self, level: int) -> None:
        self._update_label(level)
        self.sensitivity_changed.emit(level)


class DetectJob(QThread):
    """Runs the keyboard detector off the UI thread (about a quarter of a second of OpenCV)."""
    done = Signal(object)   # KeyboardFound | None

    def __init__(self, frame):
        super().__init__()
        self._frame = frame

    def run(self) -> None:
        self.done.emit(detect_keyboard(self._frame))


class PreviewLabel(QLabel):
    """Camera preview that reports clicks (position in label coordinates)."""
    clicked = Signal(float, float)

    def mousePressEvent(self, event):
        self.clicked.emit(event.position().x(), event.position().y())


class TypingMode:
    def __init__(self, frame_size: tuple[int, int], mirror: bool, flip_vertical: bool):
        self.mapper = CoordinateMapper(frame_size, (LAYOUT_W, LAYOUT_H), mirror=mirror, flip_vertical=flip_vertical)
        self.session = TypingSession()
        self.slots = HandSlots(max_slots=config.TYPING_NUM_HANDS)
        self.calibrating = False
        self.pending: list[tuple[float, float]] = []   # clicked view points
        self.message = ""
        self.auto_detect = True
        self._job: DetectJob | None = None
        self._job_view: tuple | None = None     # (mirror, flip, frame size) the running job's frame was prepared for
        self._last_try = 0.0

    @property
    def ready(self) -> bool:
        return self.mapper.calibrated and not self.calibrating

    # ---- automatic keyboard detection ----
    def _view_key(self) -> tuple:
        return (self.mapper.mirror, self.mapper.flip_vertical, self.mapper.frame_size)

    def maybe_auto_calibrate(self, latest_frame, now: float, force: bool = False) -> None:
        """Start a background detection when uncalibrated (retrying every few seconds) or when forced."""
        if self._job is not None or self.calibrating:
            return
        if not force and (not self.auto_detect or self.mapper.calibrated or now - self._last_try < config.KEYBOARD_DETECT_RETRY_S):
            return
        item = latest_frame()
        if item is None:
            return
        frame = item[1]
        if self.mapper.mirror:
            frame = cv2.flip(frame, 1)
        if self.mapper.flip_vertical:
            frame = cv2.flip(frame, 0)     # same transforms as CoordinateMapper.to_view, so corners are view coordinates
        self._last_try, self._job_view = now, self._view_key()
        self.message = "Looking for the keyboard…"
        self._job = DetectJob(frame.copy())
        self._job.done.connect(self._on_detected)
        self._job.start()

    def _on_detected(self, found: KeyboardFound | None) -> None:
        job, self._job = self._job, None
        if job is not None:
            job.wait()
        if self._job_view != self._view_key() or self.calibrating:
            return    # orientation changed or the user started clicking while it ran: the result no longer applies
        if found is None:
            self.message = ("Keyboard not found automatically: keep the whole keyboard in view and sharp, "
                            "or use Calibrate Keyboard and click the 4 corners.")
            return
        try:
            self.mapper.calibrate(found.corners)
        except CalibrationError as exc:
            self.message = f"Automatic detection gave an unusable result ({exc}). Calibrate by clicking instead."
            return
        self.session.update({}, time.monotonic())
        self.message = (f"Keyboard found automatically (match {found.cost:.2f}, lower is better). "
                        "If the grid looks off, use Calibrate Keyboard to click the corners.")

    def wait_for_job(self) -> None:
        if self._job is not None:
            self._job.wait()

    # ---- calibration (mouse clicks on the preview) ----
    def start_calibration(self) -> None:
        self.calibrating, self.pending = True, []
        self.slots.reset()
        self.session.update({}, time.monotonic())
        self._prompt()

    def cancel_calibration(self) -> None:
        self.calibrating, self.pending = False, []

    def _prompt(self) -> None:
        i = len(self.pending)
        self.message = (f"Keyboard {i + 1}/4: click {CALIB_STEPS[i][0]} on the camera preview "
                        "(the highlighted key on the canvas shows which one).")

    def calib_corner(self) -> tuple[float, float] | None:
        """Layout corner the user is being asked to click, while calibrating."""
        return CALIB_STEPS[len(self.pending)][1] if self.calibrating and len(self.pending) < 4 else None

    def click(self, x: float, y: float, label: QLabel) -> None:
        """Handle a click at label coordinates (x, y) while calibrating."""
        pm = label.pixmap()
        if not self.calibrating or pm is None or pm.isNull():
            return
        scale = config.PREVIEW_WIDTH / self.mapper.frame_size[0]
        px = x - (label.width() - pm.width()) / 2
        py = y - (label.height() - pm.height()) / 2
        if not (0 <= px < pm.width() and 0 <= py < pm.height()):
            return
        self.pending.append((px / scale, py / scale))
        if len(self.pending) < 4:
            self._prompt()
            return
        try:
            self.mapper.calibrate(self.pending)
        except CalibrationError as exc:
            self.message = f"Calibration rejected: {exc} Click the 4 corners again."
            self.pending = []
            return
        self.calibrating, self.pending = False, []
        self.message = "Keyboard calibrated. Type!"

    # ---- per frame ----
    def on_detection(self, det: Detection, now: float) -> None:
        points = {}
        if self.ready:
            # Hand identity comes from wrist continuity, not MediaPipe's Left/Right label (unreliable from above).
            mapped = [[self.mapper.map((float(x), float(y)), clamp=False) for x, y in hand] for hand in det.hands]
            wrists = [m[0] for m in mapped if m[0] is not None]
            ids = iter(self.slots.assign(wrists))
            for hand_pts in mapped:
                slot = next(ids) if hand_pts[0] is not None else None
                if slot is None:
                    continue
                for name, idx in FINGERTIPS.items():
                    if hand_pts[idx] is not None:
                        points[f"hand{slot}-{name}"] = hand_pts[idx]
        else:
            self.slots.reset()
        self.session.update(points, now)

    def stats_text(self, now: float) -> str:
        s = self.session.evaluator.stats(now)
        acc = "-" if s.accuracy is None else f"{100 * s.accuracy:.0f}%"
        return (f"camera keys  : {s.predicted}   real keys: {s.truth}\n"
                f"correct/wrong: {s.correct}/{s.wrong}  missed {s.missed}  false {s.false_pos}\n"
                f"accuracy     : {acc} (correct / real keys, 0.6 s match window)")

    # ---- preview overlay ----
    def overlay(self, pixmap: QPixmap) -> None:
        """Draw clicked corners, or the calibrated key grid projected back onto the camera preview."""
        if pixmap.isNull():
            return
        scale = config.PREVIEW_WIDTH / self.mapper.frame_size[0]
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)
        if self.calibrating:
            p.setPen(QPen(QColor(255, 60, 60), 2))
            for n, (x, y) in enumerate(self.pending):
                p.drawEllipse(QPointF(x * scale, y * scale), 5, 5)
                p.drawText(QPointF(x * scale + 8, y * scale - 6), CORNER_NAMES[n])
        elif self.mapper.calibrated:
            p.setPen(QPen(QColor(0, 255, 255, 170), 1))
            corners = [c for key in KEYS for c in
                       ((key.x, key.y), (key.x + key.w, key.y), (key.x + key.w, key.y + key.h), (key.x, key.y + key.h))]
            view = self.mapper.canvas_to_view_many(corners)
            if view is not None:
                for i in range(0, len(view), 4):
                    p.drawPolygon(QPolygonF([QPointF(x * scale, y * scale) for x, y in view[i:i + 4]]))
            p.setPen(QPen(QColor(255, 255, 0), 2))
            for pt in self.session.fingertips.values():
                v = self.mapper.canvas_to_view(pt)
                if v is not None:
                    p.drawEllipse(QPointF(v[0] * scale, v[1] * scale), 4, 4)
        p.end()
