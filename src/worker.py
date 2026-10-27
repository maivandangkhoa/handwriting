"""Tracking thread: takes the newest camera frame, runs the hand tracker, renders the preview."""
import logging

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from . import config
from .camera import Camera, CameraError
from .hand_tracker import HAND_CONNECTIONS, INDEX_FINGER_TIP, Detection, HandTracker, ModelError
from .metrics import RateCounter, TimingStat

log = logging.getLogger(__name__)


def render_preview(frame: np.ndarray, det: Detection, mirror: bool, flip_vertical: bool = False) -> QImage:
    """Downscaled BGR frame with landmarks and a highlighted index fingertip, optionally mirrored/flipped."""
    h, w = frame.shape[:2]
    scale = config.PREVIEW_WIDTH / w
    img = cv2.resize(frame, (config.PREVIEW_WIDTH, int(h * scale)))
    if det.landmarks_px is not None:
        pts = (det.landmarks_px * scale).astype(int)
        for a, b in HAND_CONNECTIONS:
            cv2.line(img, tuple(pts[a]), tuple(pts[b]), (0, 255, 0), 2)
        for p in pts:
            cv2.circle(img, tuple(p), 3, (0, 200, 255), -1)
        cv2.circle(img, tuple(pts[INDEX_FINGER_TIP]), 9, (0, 0, 255), 2)
    if mirror or flip_vertical:
        img = cv2.flip(img, -1 if mirror and flip_vertical else 1 if mirror else 0)
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format_RGB888).copy()


class TrackingWorker(QThread):
    result = Signal(QImage, object)   # preview, Detection (raw-frame coordinates)
    failed = Signal(str)

    def __init__(self, camera: Camera):
        super().__init__()
        self._camera = camera
        self.mirror = True
        self.flip_vertical = False
        self.fps = RateCounter(config.METRICS_WINDOW_SECONDS)
        self.inference_ms = TimingStat()
        self.processed = 0
        self.last_hand_count = 0

    def stop(self) -> None:
        self.requestInterruption()
        self.wait(3000)

    def run(self) -> None:
        try:
            tracker = HandTracker()  # created here so MediaPipe lives on this thread
        except ModelError as exc:
            self.failed.emit(str(exc))
            return
        last_seq = -1
        try:
            while not self.isInterruptionRequested():
                item = self._camera.latest()
                if item is None or item[0] == last_seq:
                    self.msleep(2)
                    continue
                last_seq, frame = item
                det = tracker.detect(frame)
                self.processed += 1
                self.fps.tick()
                self.inference_ms.add(det.inference_ms)
                self.last_hand_count = det.hand_count
                self.result.emit(render_preview(frame, det, self.mirror, self.flip_vertical), det)
        except Exception as exc:
            log.exception("Tracking loop crashed")
            self.failed.emit(f"Tracking stopped: {exc}")
        finally:
            tracker.close()

    @property
    def dropped(self) -> int:
        """Camera frames that were overwritten before the tracker could process them."""
        return max(self._camera.frames_read - self.processed, 0)


class CameraOpener(QThread):
    """Closes the previous camera and opens a new one off the UI thread (USB cameras can take seconds)."""
    opened = Signal(object)  # CameraInfo
    failed = Signal(str)

    def __init__(self, camera: Camera, index: int):
        super().__init__()
        self._camera = camera
        self._index = index

    def run(self) -> None:
        try:
            self.opened.emit(self._camera.open(self._index))
        except CameraError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            log.exception("Unexpected camera open failure")
            self.failed.emit(f"Camera error: {exc}")
