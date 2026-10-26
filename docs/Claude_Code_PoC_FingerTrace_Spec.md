# Claude Code Specification — FingerTrace PoC

**Version:** 1.0  
**Platform:** macOS on the user's existing MacBook  
**Goal:** Build a local application that uses a USB camera to track the index fingertip and draw a continuous line on a canvas displayed on the MacBook screen.

## 1. Objective

Build a CPU-only proof of concept that validates:

`USB camera → OpenCV capture → MediaPipe hand landmarks → fingertip coordinate mapping → drawing canvas`

The app must run locally without a discrete GPU, cloud service, account, or paid API. Keep it small, measurable, and easy to extend later to floor-projection interaction.

## 2. Scope

### In scope
- Python desktop app for macOS.
- External USB camera selection and live preview.
- OpenCV for camera capture, frame transforms, and drawing utilities.
- MediaPipe Tasks Hand Landmarker to detect a hand and the index fingertip.
- Drawing canvas, fingertip cursor, clear/pause controls, mirror setting, and basic calibration.
- FPS, inference timing, and camera resolution diagnostics.
- Setup guide, troubleshooting, and unit tests.

### Out of scope
- YOLO, GPU/CUDA, DEEPX, or other accelerators.
- Cloud inference, remote APIs, telemetry, accounts, or network uploads.
- Multi-person tracking, feet/body detection, projector/floor mapping, or production packaging.
- Controlling the macOS cursor or writing into other apps.
- Physical touchscreen/contact detection. This is **air-drawing**: the camera sees a finger in front of the screen and draws its path.

Do not add features that do not help validate the core interaction.

## 3. Expected user experience

Create one desktop window with:
- Large drawing canvas.
- Smaller live camera preview with hand landmarks and the index fingertip highlighted.
- Camera selector; Start/Stop Camera.
- Draw Enabled toggle; Clear Canvas.
- Calibrate/Recalibrate controls.
- Mirror Camera toggle.
- Status: `Hand detected`, `No hand detected`, `Camera unavailable`, or `Paused`.
- Diagnostics: camera FPS, hand-tracking/inference FPS, approximate inference time in ms, actual camera resolution, and detected hand count if available.

When a hand is detected, show a cursor/dot on the canvas at the mapped fingertip position. When drawing is enabled, draw a continuous line. If tracking is lost, immediately end the current stroke. When the hand reappears, start a new stroke; **never connect the old and new points with a long line**.

Always-draw mode is required. Optional pinch-to-draw may be added only if it does not delay the core app.

## 4. Recommended technology

- Python 3 version compatible with the selected MediaPipe package.
- `opencv-python`.
- MediaPipe Tasks **Hand Landmarker**.
- Prefer **PySide6** for a responsive desktop UI and canvas. Use one UI approach consistently; do not build parallel UIs.
- `pytest` for coordinate mapping and drawing-state tests.
- CPU inference by default.

### Model asset
Hand Landmarker requires a compatible model asset. Provide a setup/download script or documented user-triggered setup step for the official model. Do not silently download at app startup. If the asset is missing, show an actionable error. Verify official API names, model URL, package compatibility, and license/attribution requirements instead of guessing. Do not commit a large binary model unless justified.

## 5. Coordinate mapping and calibration

Camera and canvas coordinates may differ because of camera position, mirroring, and perspective.

Implement calibration:
1. Show four targets in order: top-left, top-right, bottom-right, bottom-left.
2. User positions the fingertip at each target and confirms with a key or UI button. Do not require physical screen contact.
3. Store the four fingertip points in camera-image coordinates.
4. If valid, use an OpenCV perspective transform/homography to map the camera quadrilateral to the canvas.
5. If calibration is skipped, use normalized linear mapping and clearly label the fallback.
6. Provide Recalibrate and Reset Calibration.
7. Reject duplicate/near-duplicate points, bad ordering, and degenerate quadrilaterals with a helpful message.

Keep calibration isolated in its own module so it can later be adapted for camera-to-floor mapping.

### Mirroring
- Choose and document a sensible default (mirror preview by default is acceptable).
- Keep mapping consistent with the preview and canvas.
- Provide a Mirror Camera toggle.
- Test that moving the finger left moves the cursor left as expected in both modes.

## 6. Camera capture and hand tracking

### Camera
- Use OpenCV `VideoCapture`.
- Allow selecting among available camera indices.
- Initially request 1280×720 at 30 FPS; gracefully fall back if unsupported.
- Read back and display actual resolution/FPS; do not assume the camera honored the request.
- Keep capture separate from inference/UI if needed to avoid freezing the UI.
- Use a bounded buffer, ideally one latest-frame slot. Drop stale frames rather than queueing them and creating lag.
- Release the camera on stop and app exit.

### Hand tracking
- Use the official MediaPipe Hand Landmarker API in a compatible video/live-stream mode.
- Locate the index fingertip using the documented landmark index and comment it in code.
- Convert normalized landmark coordinates into image coordinates.
- Start with one hand and no custom model training.
- Keep tracking code separate from UI code.

### Smoothing and stroke state
- Add light configurable smoothing to reduce jitter without noticeable lag.
- Track current stroke, previous point, drawing-enabled status, hand detection, calibration validity, and paused status explicitly.
- Append points only when drawing is enabled and a valid fingertip is detected.
- Break the stroke when tracking is lost or drawing is paused.
- Clear Canvas removes all strokes.
- Store strokes in canvas coordinates so they can be redrawn after window resizing.
- Clamp valid mapped points to canvas bounds; reject invalid transforms rather than causing sudden jumps.

## 7. Performance diagnostics

Display:
- Camera FPS.
- Hand-tracking/inference FPS, separately from camera FPS.
- Approximate inference/per-frame processing time in milliseconds.
- Hand detection status and camera resolution.
- Dropped-frame/overrun indicator if practical.

Label metrics accurately: inference time is not end-to-end latency.

### Initial engineering targets
These are targets to measure, not guaranteed performance:
- Stable camera stream near 30 FPS if supported.
- At least 20 fingertip updates per second on the user's MacBook.
- Smooth ordinary drawing without obvious gaps.
- No growing queue of stale frames; process the newest available frame.
- Responsive UI during normal use.
- Measure perceived end-to-end response across capture, inference, coordinate mapping, UI update, and display. Do not infer latency from FPS alone.

Add `PERFORMANCE_TEST.md` or a README section with a repeatable 60-second test and a results table.

## 8. Reliability, logging, and privacy

Gracefully handle:
- No camera, camera unavailable, denied permission, or disconnect.
- Unsupported resolution/FPS.
- Missing/invalid model asset or MediaPipe initialization failure.
- No hand/intermittent tracking loss.
- Invalid calibration.
- Stop/pause/clear and window close.

Show useful UI messages and log technical details using Python's `logging`. Release camera resources on exit. Do not save frames/video by default. Keep all processing local; no telemetry, analytics, cloud inference, or uploads. Network use is allowed only for an explicit model setup/download step.

## 9. Suggested project structure

Claude Code may adjust this if needed, but keep clear module responsibilities:

```text
fingertrace-poc/
├── README.md
├── PERFORMANCE_TEST.md
├── requirements.txt
├── .gitignore
├── app.py
├── assets/
│   └── README.md
├── src/
│   ├── __init__.py
│   ├── camera.py
│   ├── hand_tracker.py
│   ├── calibration.py
│   ├── drawing.py
│   ├── metrics.py
│   ├── ui.py
│   └── config.py
├── scripts/
│   └── download_model.py
└── tests/
    ├── test_calibration.py
    ├── test_drawing.py
    └── test_metrics.py
```

Do not create empty modules just to match the tree; each module must have a real responsibility.

## 10. Setup and README requirements

README must include:
- Purpose and architecture diagram (Mermaid acceptable).
- macOS/Python assumptions and verified dependency versions.
- Exact environment setup, model setup, and launch commands.
- Camera selection and macOS permission guidance.
- Drawing, mirroring, and calibration behavior.
- Troubleshooting for permissions, camera index, and missing model.
- Performance test procedure and known limitations.
- Clear note that this is air-drawing, not touchscreen input.

Use a virtual environment. Adapt these example commands to the verified implementation:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python scripts/download_model.py
python app.py
```

Do not claim commands work until imports and setup have been verified.

## 11. Acceptance criteria

- [ ] App installs and launches on macOS with documented commands.
- [ ] USB camera is detected or a clear diagnostic is shown.
- [ ] Live camera preview appears.
- [ ] Hand landmarks and index fingertip are detected and visualized.
- [ ] Canvas cursor follows fingertip in the expected direction.
- [ ] Mirror setting behaves consistently.
- [ ] Continuous drawing works when enabled.
- [ ] Clear removes all strokes; pause stops new strokes.
- [ ] Losing the hand breaks the stroke; reacquisition never draws a long connecting line.
- [ ] Calibration works or fallback mapping is clearly indicated.
- [ ] FPS and timing metrics are visible and correctly labeled.
- [ ] UI remains responsive and camera resources are released on exit.
- [ ] Camera/model/permission errors are actionable.
- [ ] Unit tests for coordinate mapping and drawing-state logic pass.
- [ ] README and performance test instructions are complete.
- [ ] No GPU, DEEPX, paid API, or cloud service is required.

## 12. Manual test plan

Record pass/fail, observations, and known limitations:
1. Basic hand detection for 30 seconds.
2. Draw a square and circle with slow movement.
3. Move the finger quickly across the camera view.
4. Occlude the hand, then reveal it.
5. Move the hand out of view and return on the opposite side; verify no connecting line.
6. Toggle mirror mode and verify left/right behavior.
7. Calibrate and test near all four canvas corners.
8. Stop/restart the camera; disconnect/reconnect if practical and safe.
9. Run continuously for 10 minutes and observe responsiveness/memory.
10. Record camera FPS, inference FPS, typical inference time, and perceived end-to-end responsiveness.

## 13. How Claude Code should execute the task

Before coding:
1. Inspect the current repository and files.
2. Verify macOS, Python, MediaPipe, and model-asset compatibility.
3. State a short implementation plan.
4. Then implement the complete working app; do not stop at a design proposal.

During implementation:
- Keep code small and readable.
- Pin compatible dependency versions after verification.
- Do not invent API names or model URLs; verify against official documentation.
- Add tests for coordinate transforms and stroke state.
- Run tests, imports, and launch checks where possible; fix errors found.
- If camera hardware is unavailable, test error paths and use synthetic frames for unit tests. Do not claim physical-camera validation.
- Use sensible defaults; ask questions only if a genuine blocker prevents progress.

At completion, report:
1. Files created/changed.
2. Exact setup and launch commands.
3. Tests run and actual results.
4. Remaining user actions (e.g., grant camera permission/connect USB camera).
5. Known limitations and the next recommended experiment.

## 14. Future extension — do not implement now

Keep the architecture extensible for a later floor-projection PoC:
- Replace hand landmarks with foot/person detection.
- Calibrate camera coordinates to floor coordinates.
- Convert positions into interaction events.
- Feed events into a simple game engine.
- Benchmark CPU first; compare GPU or DEEPX only if measured performance requires it.

**Immediate priority:** get a reliable fingertip-tracking and drawing demo running on the MacBook with the USB camera, using CPU-only inference.
