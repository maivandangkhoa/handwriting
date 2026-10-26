"""Tunable constants for FingerTrace. Kept in one place so experiments are one-line edits."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / "assets" / "hand_landmarker.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)

# Camera: requested values; the camera may not honour them, actuals are read back.
CAMERA_REQUEST_WIDTH = 1280
CAMERA_REQUEST_HEIGHT = 720
CAMERA_REQUEST_FPS = 30
CAMERA_PROBE_COUNT = 4          # indices 0..N-1 are probed
CAMERA_MAX_READ_FAILURES = 30   # consecutive failed reads before declaring the camera lost

# Logical canvas size (strokes are stored in this space and scaled to the widget).
CANVAS_WIDTH = 1280
CANVAS_HEIGHT = 720

# Hand tracking
NUM_HANDS = 1
MIN_DETECTION_CONFIDENCE = 0.5
MIN_PRESENCE_CONFIDENCE = 0.5
MIN_TRACKING_CONFIDENCE = 0.5

# Smoothing: exponential moving average weight of the newest point (1.0 = off).
SMOOTHING_ALPHA = 0.5

# Calibration validation (fractions of the camera frame)
CALIB_MIN_POINT_DISTANCE = 0.05   # of frame diagonal
CALIB_MIN_AREA = 0.02             # of frame area

# Preview
PREVIEW_WIDTH = 480
METRICS_WINDOW_SECONDS = 2.0
