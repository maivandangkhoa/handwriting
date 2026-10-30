"""MediaPipe Pose Landmarker wrapper (CPU, VIDEO running mode) for the Mirror dance. No Qt, no camera."""
import logging
import time
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

from . import config
from .hand_tracker import Detection, ModelError

log = logging.getLogger(__name__)

# MediaPipe pose landmark indices.
NOSE, L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST = 0, 11, 12, 13, 14, 15, 16
L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANKLE, R_ANKLE = 23, 24, 25, 26, 27, 28
POSE_CONNECTIONS = ((L_SHOULDER, R_SHOULDER), (L_SHOULDER, L_ELBOW), (L_ELBOW, L_WRIST), (R_SHOULDER, R_ELBOW),
                    (R_ELBOW, R_WRIST), (L_SHOULDER, L_HIP), (R_SHOULDER, R_HIP), (L_HIP, R_HIP), (L_HIP, L_KNEE),
                    (L_KNEE, L_ANKLE), (R_HIP, R_KNEE), (R_KNEE, R_ANKLE))


class PoseTracker:
    def __init__(self, model_path: Path = config.POSE_MODEL_PATH):
        if not Path(model_path).is_file():
            raise ModelError(f"Pose Landmarker model not found at {model_path}. Run: python scripts/download_model.py")
        try:
            options = vision.PoseLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(model_path)),
                running_mode=vision.RunningMode.VIDEO, num_poses=1,
                min_pose_detection_confidence=config.POSE_MIN_CONFIDENCE,
                min_pose_presence_confidence=config.POSE_MIN_CONFIDENCE, min_tracking_confidence=config.POSE_MIN_CONFIDENCE)
            self._landmarker = vision.PoseLandmarker.create_from_options(options)
        except Exception as exc:
            log.exception("PoseLandmarker init failed")
            raise ModelError(f"Could not initialise MediaPipe with {model_path}: {exc}") from exc
        self._last_ts_ms = -1

    def detect(self, frame_bgr: np.ndarray) -> Detection:
        """`Detection.pose` is (33, 3): x, y as fractions of the frame, and MediaPipe's visibility (0..1)."""
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        ts = max(int(time.monotonic() * 1000), self._last_ts_ms + 1)
        self._last_ts_ms = ts
        start = time.perf_counter()
        result = self._landmarker.detect_for_video(image, ts)
        ms = (time.perf_counter() - start) * 1000.0
        pose = None
        if result.pose_landmarks:
            pose = np.array([[lm.x, lm.y, lm.visibility] for lm in result.pose_landmarks[0]], dtype=np.float32)
        return Detection(None, 0, ms, frame=frame_bgr, pose=pose)

    def close(self) -> None:
        self._landmarker.close()
