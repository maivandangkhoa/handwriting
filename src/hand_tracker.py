"""MediaPipe Hand Landmarker wrapper (CPU, VIDEO running mode). No Qt, no camera."""
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

from . import config

log = logging.getLogger(__name__)

# MediaPipe hand landmark index 8 = INDEX_FINGER_TIP (21 landmarks, 0 = wrist).
INDEX_FINGER_TIP = 8
HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10), (10, 11),
    (11, 12), (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
)


class ModelError(RuntimeError):
    """Model asset missing or MediaPipe failed to initialise; the message is shown to the user."""


@dataclass
class Detection:
    landmarks_px: np.ndarray | None   # (21, 2) raw-frame pixels of the first hand, or None
    hand_count: int
    inference_ms: float               # time spent in detect_for_video only (not end-to-end latency)
    hands: list = field(default_factory=list)        # every detected hand, each (21, 2) raw-frame pixels
    handedness: list = field(default_factory=list)   # "Left"/"Right" per hand (MediaPipe's label)
    frame: np.ndarray | None = None                  # the BGR frame this detection came from
    pose: np.ndarray | None = None                   # (33, 3) body landmarks as frame fractions + visibility (Mirror dance): the first body
    poses: list = field(default_factory=list)        # every detected body, each (33, 3) (up to config.DANCE_MAX_PEOPLE)

    @property
    def tip_px(self) -> tuple[float, float] | None:
        if self.landmarks_px is None:
            return None
        x, y = self.landmarks_px[INDEX_FINGER_TIP]
        return float(x), float(y)


class HandTracker:
    def __init__(self, model_path: Path = config.MODEL_PATH, num_hands: int = config.NUM_HANDS):
        self.num_hands = num_hands
        loose = num_hands > 1   # typing: favour finding both hands over avoiding the occasional false hand
        if not Path(model_path).is_file():
            raise ModelError(
                f"Hand Landmarker model not found at {model_path}. Run: python scripts/download_model.py"
            )
        try:
            options = vision.HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(model_path)),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=num_hands,
                min_hand_detection_confidence=config.TYPING_MIN_CONFIDENCE if loose else config.MIN_DETECTION_CONFIDENCE,
                min_hand_presence_confidence=config.TYPING_MIN_CONFIDENCE if loose else config.MIN_PRESENCE_CONFIDENCE,
                min_tracking_confidence=config.TYPING_MIN_CONFIDENCE if loose else config.MIN_TRACKING_CONFIDENCE,
            )
            self._landmarker = vision.HandLandmarker.create_from_options(options)
        except Exception as exc:  # MediaPipe raises bare RuntimeError/ValueError for bad assets
            log.exception("HandLandmarker init failed")
            raise ModelError(f"Could not initialise MediaPipe with {model_path}: {exc}") from exc
        self._last_ts_ms = -1

    def detect(self, frame_bgr: np.ndarray) -> Detection:
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        ts = max(int(time.monotonic() * 1000), self._last_ts_ms + 1)  # must strictly increase
        self._last_ts_ms = ts
        start = time.perf_counter()
        result = self._landmarker.detect_for_video(image, ts)
        ms = (time.perf_counter() - start) * 1000.0
        if not result.hand_landmarks:
            return Detection(None, 0, ms, frame=frame_bgr)
        hands = [np.array([[lm.x * w, lm.y * h] for lm in hand], dtype=np.float32) for hand in result.hand_landmarks]
        labels = [(cats[0].category_name if cats else "") for cats in result.handedness]
        return Detection(hands[0], len(hands), ms, hands, labels, frame_bgr)

    def close(self) -> None:
        self._landmarker.close()
