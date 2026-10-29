"""Text for the diagnostics panel. No Qt."""

EMPTY = "camera FPS : -\ntracking FPS: -\ninference   : -\nresolution  : -\nhands       : -"


def camera_text(camera, worker, extra: str = "") -> str:
    """FPS / timing / resolution lines; `extra` is appended (mode-specific statistics)."""
    info = camera.info if worker is not None else None
    if worker is None or info is None:
        return EMPTY
    return (
        f"camera FPS   : {camera.fps.rate():5.1f}\n"
        f"tracking FPS : {worker.fps.rate():5.1f}\n"
        f"inference ms : {worker.inference_ms.average():5.1f} (model call only, not end-to-end)\n"
        f"resolution   : {info.width}x{info.height} (driver FPS {info.fps:.0f})\n"
        f"hands        : {worker.last_hand_count}\n"
        f"dropped      : {worker.dropped} camera frames skipped" + (f"\n{extra}" if extra else "")
    )


def mapping_text(mode: int, mapper, typing, proj) -> str:
    if mode in (1, 3, 4):
        return f"Projector: {proj.phase}" + (" (calibrated)" if proj.mapper.calibrated and proj.phase == proj.ready_phase
                                              else " — press Calibrate Projector")
    if mode == 2:
        return ("Keyboard mapping: calibrated (homography)" if typing.mapper.calibrated
                else "Keyboard mapping: NOT calibrated — typing disabled")
    return ("Mapping: calibrated (homography)" if mapper.calibrated
            else "Mapping: UNCALIBRATED — linear fallback over full camera frame")
