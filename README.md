# FingerTrace PoC

**Air-drawing, not touchscreen input.** A USB camera sees your index fingertip in front of the screen; the app
draws its path on a canvas. CPU-only, fully local, no accounts or network (except the explicit model download).

```mermaid
flowchart LR
  A[USB camera<br/>camera.py thread, latest-frame slot] --> B[TrackingWorker<br/>worker.py QThread]
  B --> C[MediaPipe Hand Landmarker<br/>hand_tracker.py]
  C --> D[fingertip landmark 8, raw px]
  D --> E[CoordinateMapper<br/>calibration.py]
  E --> F[DrawingState<br/>smoothing + strokes]
  F --> G[Canvas + preview<br/>ui.py PySide6]
```

## Verified environment
macOS 15 (Darwin 24.6) on Apple Silicon, Python 3.14.7 (Homebrew), `mediapipe==1.1.1`,
`opencv-python==5.0.0.93`, `PySide6==6.12.0`. Unit tests, model load and offscreen UI launch were verified;
**physical camera tracking was not validated** (the build sandbox had no camera permission).

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python scripts/download_model.py     # explicit, one-time, ~8 MB
python app.py
pytest                               # unit tests
```

## Camera and macOS permission
Grant camera access to the app that launches Python (Terminal / iTerm / VS Code):
System Settings > Privacy & Security > Camera. Restart that app afterwards. Pick the camera in the dropdown
(`Refresh` re-probes indices 0-3; the built-in camera is usually 0, the USB one 1) and press **Start Camera**.
Requested 1280x720 @ 30 FPS; the actual values are read back and shown in Diagnostics.

## Using it
- **Draw mode** (remembered): *Pinch to draw* (default) draws only while thumb and index are pinched, with the
  pointer at their midpoint (green dot = pen down, red = pen up); *Always draw* follows the index tip and always
  draws. This is the practical substitute for touch detection, which one ordinary camera cannot do.
- **Draw Enabled** off = *Paused* (cursor still follows, nothing is drawn). **Clear Canvas** removes all strokes.
- Losing the hand ends the stroke; when it returns a new stroke starts, so no long connecting line.
- **Mirror Camera** (default off, remembered between runs): off = raw camera view, correct when the camera looks
  the same way you do (e.g. aimed at the screen). On = selfie-style mirror, correct when the camera faces you.
  If the stroke moves opposite to your hand, flip this checkbox. Toggling mirror resets calibration.
- **Calibrate**: point your fingertip at each highlighted target (TL, TR, BR, BL) and press **Space** /
  *Confirm Point*; Esc cancels. Points are checked (duplicates, wrong order, degenerate area) and a homography
  (`cv2.getPerspectiveTransform`) maps the camera quadrilateral to the canvas. Without calibration the app shows
  **UNCALIBRATED — linear fallback** (full camera frame stretched to the canvas). *Reset Calibration* returns to it.
- **Flip Vertical** (remembered): for a camera mounted upside down. Like Mirror, it resets calibration.
- Smoothing: One Euro filter (`ONE_EURO_MIN_CUTOFF` lower = steadier at rest, `ONE_EURO_BETA` higher = less lag
  while moving, both in `src/config.py`).

## Chess application
Choose **Chess (pinch to move pieces)** in the *Application* dropdown (default: Air Drawing). Both sides are
played by you (hot-seat); rules and legality come from [`python-chess`](https://pypi.org/project/chess/).
- Pointer = midpoint between thumb tip and index tip (green dot while pinching, red otherwise).
- **Pinch** (bring thumb and index together) over a piece of the side to move to pick it up: the square turns blue
  and legal destinations get green dots. **Open the fingers** over a square to drop it. Illegal drops, drops
  outside the board, or dropping on the origin square return the piece.
- Losing the hand cancels the move; you must open the fingers once before grabbing again.
- Pawn promotion is automatic (queen). *New Game* resets. Calibrate the same way as for drawing (recommended:
  the board is in the middle of the canvas, so the uncalibrated fallback already works roughly).
- Pinch thresholds (`PINCH_ON_RATIO` / `PINCH_OFF_RATIO`) and board size are in `src/config.py`.

## Troubleshooting
| Symptom | Fix |
|---|---|
| "No camera found" / "not authorized to capture video" | Grant camera permission (above), restart the terminal/IDE, press Refresh |
| Wrong camera | Choose another index in the dropdown (macOS Continuity Camera can shift indices) |
| "Hand Landmarker model not found" | `python scripts/download_model.py` |
| Cursor mirrored the wrong way | Toggle *Mirror Camera*, then recalibrate |
| Camera disconnected mid-run | Status shows *Camera unavailable*; reconnect, Refresh, Start |

## Layout
`src/camera.py` capture thread · `hand_tracker.py` MediaPipe · `worker.py` tracking thread/preview ·
`filters.py` One Euro smoothing · `calibration.py` mapping · `gesture.py` pinch · `chess_game.py` chess interaction · `canvas.py` rendering · `drawing.py` strokes · `metrics.py` FPS/timing · `ui.py` window · `config.py` constants.

## Known limitations
Air-drawing has no contact detection; depth/perspective makes the canvas area depend on hand distance.
One hand only. Inference time shown is the model call only, **not** end-to-end latency (see PERFORMANCE_TEST.md).
Camera index probing briefly opens each camera. No touch/contact detection: one RGB camera has no reliable depth (use pinch, a side-mounted camera or a depth camera).
Next experiment: measure end-to-end latency and tune the pinch thresholds and One Euro parameters on real use.
