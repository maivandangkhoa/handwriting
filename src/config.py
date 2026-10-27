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
CAMERA_WARMUP_SECONDS = 3.0       # how long to retry the first frame before giving up
CAMERA_MAX_READ_FAILURES = 30   # consecutive failed reads before declaring the camera lost

# Logical canvas size (strokes are stored in this space and scaled to the widget).
CANVAS_WIDTH = 1280
CANVAS_HEIGHT = 720

# Hand tracking
NUM_HANDS = 1
MIN_DETECTION_CONFIDENCE = 0.5
MIN_PRESENCE_CONFIDENCE = 0.5
MIN_TRACKING_CONFIDENCE = 0.5

# Mirror the camera by default? Off suits a camera that faces the same way as the user (e.g. aimed at the screen).
DEFAULT_MIRROR = False

# Smoothing: One Euro filter on canvas coordinates (pixels). Lower MIN_CUTOFF = steadier at rest;
# higher BETA = less lag during fast movement.
ONE_EURO_MIN_CUTOFF = 1.5
ONE_EURO_BETA = 0.01

# Camera orientation defaults (see README): vertical flip is for a camera mounted upside down.
DEFAULT_FLIP_VERTICAL = False

# Calibration validation (fractions of the camera frame)
CALIB_MIN_POINT_DISTANCE = 0.05   # of frame diagonal
CALIB_MIN_AREA = 0.02             # of frame area

# Preview
PREVIEW_WIDTH = 480
METRICS_WINDOW_SECONDS = 2.0

# Pinch gesture (thumb tip <-> index tip distance divided by palm length, with hysteresis)
PINCH_ON_RATIO = 0.30
PINCH_OFF_RATIO = 0.50

# Chess board in logical canvas coordinates
CHESS_SQUARE = 88
CHESS_ORIGIN = ((CANVAS_WIDTH - 8 * CHESS_SQUARE) // 2, (CANVAS_HEIGHT - 8 * CHESS_SQUARE) // 2)
