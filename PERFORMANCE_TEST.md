# Performance test (60 s, repeatable)

Setup: MacBook on power, no other heavy apps, USB camera at fixed position, good lighting, calibrated.

1. `python app.py`, select the USB camera, Start Camera. Note the resolution shown.
2. Hold the hand in view and draw slow circles for 30 s, then fast sweeps for 30 s.
3. Read Diagnostics every ~10 s (values are 2 s moving averages); record min/typical.
4. **End-to-end latency** (not derivable from FPS): record the screen with a second phone camera at 60+ FPS
   showing both your fingertip and the cursor; count frames between a fast finger start/stop and the cursor
   reacting; latency = frames / phone FPS.
5. After 10 min continuous use, note UI responsiveness and process memory (Activity Monitor).

| Run date | Mac model | Camera / actual res | Camera FPS | Tracking FPS | Inference ms (model only) | Dropped frames | End-to-end latency (ms) | Notes |
|---|---|---|---|---|---|---|---|---|
| _pending_ | | | | | | | | |

Targets: camera ≈ 30 FPS, tracking ≥ 20 FPS, no growing lag. Pass/fail per the manual test plan in the spec §12.
