"""USB camera capture on a background thread with a single latest-frame slot."""
import logging
import sys
import threading
from dataclasses import dataclass

import cv2
import numpy as np

from . import config
from .metrics import RateCounter

log = logging.getLogger(__name__)


class CameraError(RuntimeError):
    """Camera could not be opened or was lost; the message is shown to the user."""


@dataclass(frozen=True)
class CameraInfo:
    width: int
    height: int
    fps: float


def _open_capture(index: int) -> cv2.VideoCapture:
    backend = cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else cv2.CAP_ANY
    return cv2.VideoCapture(index, backend)


def list_cameras(count: int = config.CAMERA_PROBE_COUNT) -> list[int]:
    """Indices that open and deliver a frame. Briefly opens each camera."""
    found = []
    for i in range(count):
        cap = _open_capture(i)
        try:
            if cap.isOpened() and cap.read()[0]:
                found.append(i)
        finally:
            cap.release()
    return found


class Camera:
    def __init__(self):
        self._cap: cv2.VideoCapture | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._frame: np.ndarray | None = None
        self._seq = 0
        self.error: str | None = None
        self.fps = RateCounter(config.METRICS_WINDOW_SECONDS)
        self.info: CameraInfo | None = None

    @property
    def frames_read(self) -> int:
        return self._seq

    def open(self, index: int) -> CameraInfo:
        self.close()
        cap = _open_capture(index)
        if not cap.isOpened():
            cap.release()
            raise CameraError(
                f"Cannot open camera {index}. Check the USB connection and that your terminal/IDE has "
                "camera permission (System Settings > Privacy & Security > Camera)."
            )
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_REQUEST_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_REQUEST_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, config.CAMERA_REQUEST_FPS)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        ok, frame = cap.read()
        if not ok or frame is None:
            cap.release()
            raise CameraError(f"Camera {index} opened but returned no frame (permission denied or busy?).")
        h, w = frame.shape[:2]
        self.info = CameraInfo(w, h, cap.get(cv2.CAP_PROP_FPS) or 0.0)  # actual values, not the request
        log.info("Camera %d opened: %dx%d, driver-reported %.1f FPS", index, w, h, self.info.fps)
        self._cap, self.error, self._seq = cap, None, 0
        self._frame = frame
        self.fps.reset()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="camera", daemon=True)
        self._thread.start()
        return self.info

    def latest(self) -> tuple[int, np.ndarray] | None:
        """(sequence number, frame) of the newest frame, or None. Older frames are never queued."""
        with self._lock:
            return None if self._frame is None else (self._seq, self._frame)

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        with self._lock:
            self._frame = None

    def _run(self) -> None:
        failures = 0
        while not self._stop.is_set():
            ok, frame = self._cap.read()
            if not ok or frame is None:
                failures += 1
                if failures >= config.CAMERA_MAX_READ_FAILURES:
                    self.error = "Camera disconnected or stopped delivering frames."
                    log.error(self.error)
                    return
                continue
            failures = 0
            with self._lock:
                self._frame = frame
                self._seq += 1
            self.fps.tick()
