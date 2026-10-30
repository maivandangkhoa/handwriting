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
DRAW_FILTER = (ONE_EURO_MIN_CUTOFF, ONE_EURO_BETA, 1.0)    # One Euro (min_cutoff, beta, d_cutoff) for pen drawing
BRUSH_FILTER = (4.0, 0.08, 5.0)    # animal brush: a fast-opening filter, the brush must keep up with the finger

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
# Index finger extension = wrist-to-fingertip / wrist-to-index-knuckle: about 2 when straight, under 1 when curled.
POINT_ON_RATIO = 1.75    # straight enough to start drawing
POINT_OFF_RATIO = 1.50   # curled this far lifts the pen (early, so the fingertip's inward swing leaves no tail)

BRUSH_LIFT_RATIO = 1.25   # animal brush: index extension below this (finger curled, fist) lifts the brush

# Chess board in logical canvas coordinates. The board leaves a lit margin: a finger near the edge casts its shadow
# there, and the projector casts none outside the canvas.
CHESS_SQUARE = 76
CHESS_ORIGIN = ((CANVAS_WIDTH - 8 * CHESS_SQUARE) // 2, (CANVAS_HEIGHT - 8 * CHESS_SQUARE) // 2)

# Gomoku board: GOMOKU_CELLS square cells a side, centred like the chess board.
GOMOKU_CELLS = 10
GOMOKU_SQUARE = 62
GOMOKU_ORIGIN = ((CANVAS_WIDTH - GOMOKU_CELLS * GOMOKU_SQUARE) // 2, (CANVAS_HEIGHT - GOMOKU_CELLS * GOMOKU_SQUARE) // 2)

# Keyboard typing mode. Speeds are in key units per second (1 unit = one standard key width, ~19 mm).
TYPING_NUM_HANDS = 2
TYPING_MIN_CONFIDENCE = 0.35       # looser detect/presence/tracking thresholds so the second hand is picked up from above
TYPING_FILTER_MIN_CUTOFF = 3.0     # One Euro filter per fingertip, in key units
TYPING_FILTER_BETA = 1.0
TYPING_ARM_DIST = 0.35             # a fingertip leaving its resting spot by this much (key units) is "on its way to a key"
TYPING_STILL_RADIUS = 0.22         # ...and staying within this radius ...
TYPING_DWELL_S = 0.12              # ...for this long = a key press
TYPING_SENSITIVITY = 7             # 1..10 slider; 5 = the distances above, higher = smaller movements count
PIANO_SENSITIVITY = 7              # 1..10, as TYPING_SENSITIVITY: higher = smaller finger movements strike a key
TYPING_EVAL_WINDOW_S = 0.6         # a predicted key within this of a real keystroke counts as its match

# Automatic keyboard detection (chamfer matching of the key outlines against the layout)
KEYBOARD_DETECT_WIDTH = 640        # frames are downscaled to this width for detection
KEYBOARD_DETECT_MAX_COST = 1.2     # mean distance (px at that width) from layout key edges to image edges; above = reject
KEYBOARD_DETECT_RETRY_S = 2.0      # while typing mode is uncalibrated, retry this often

# Projector chess: a touch = the fingertip meets its own shadow on the projected surface.
TOUCH_WORK_WIDTH = 640             # frames are downscaled to this width for shadow analysis
TOUCH_SHADOW_RATIO = 0.72          # a pixel below this fraction of its empty-scene brightness is shadow
TOUCH_MIN_BACKGROUND = 25          # pixels darker than this in the empty scene cannot show a shadow
TOUCH_MIN_PROJECTED = 10           # with the room light known: the projector must add this much (0..255) for a shadow to show
TOUCH_SHADOW_FRACTION = 0.4        # ...and shadow is where this share of the projected light has gone
TOUCH_NEAR_MAX = 0.32              # a touch also needs visible shadow this close to the fingertip (palm lengths); farther = hovering high
TOUCH_DISC_RADIUS = 0.7            # shadow is counted within this distance of the fingertip (palm lengths)
TOUCH_HAND_MARGIN = 0.10           # the hand silhouette is the landmark hull grown by this (palm lengths)
TOUCH_ON_FRACTION = 0.35           # touch starts when the visible-shadow score is this far from "touching" toward "hovering" ...
TOUCH_OFF_FRACTION = 0.60          # ... and ends at this far
TOUCH_MIN_CONTRAST = 0.04          # hover score must exceed touch score by this (palm^2), else the shadow is unusable
TOUCH_CONFIRM_FRAMES = 2           # frames the touch condition must hold before it counts
BACKGROUND_EMPTY_S = 0.4           # no hand for this long before the empty scene is (re)learned
BACKGROUND_FRAMES = 8              # frames averaged into the empty-scene model
PROJECTOR_MARKER_SCALE = 0.32      # calibration disc radius, in board squares (discs sit on the four corner squares)
PROJECTOR_PHASE_S = 0.8            # how long each calibration pattern is shown before the frame is captured
