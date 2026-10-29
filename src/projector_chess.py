"""Chess on a projector: glue between the camera detections, the shadow touch detector and ChessGame.

Geometry calibration (dark -> markers, or manual) lives in ProjectorSurface; after it:
  learn                the empty board is memorised (hand away) for shadow detection
  touch -> hover       two reference scores: fingertip on the ring, then ~3 cm above it
  play                 touches drive the game
"""
import logging
import math

from PySide6.QtGui import QColor

from . import config
from .chess_game import ChessGame
from .filters import OneEuroFilter2D
from .hand_tracker import Detection
from .projector_calib import marker_centres
from .projector_surface import ProjectorSurface
from .touch_detector import ShadowTouchDetector

log = logging.getLogger(__name__)
HOLD_S = 1.4          # how long the fingertip must stay on / above the ring for a reference
SETTLE_S = 0.5        # ...of which the first part is discarded while the finger gets there
DWELL_S = 0.9         # point-and-hold: a fingertip kept still this long counts as a touch, shadow or not
DWELL_RADIUS = 0.4    # ...still = within this many squares of where the hold began
DWELL_TAP_S = 0.15    # how long the synthetic touch lasts
MAX_REFERENCE_TRIES = 2   # shadow references that fail this often leave point-and-hold as the only touch
HOLD_ONLY_NOTE = ("The shadow cannot tell touch from hover here. Point-and-hold: keep your fingertip on a square "
                  "for a second to select it, then hold on the destination.")
LOSS_GRACE_S = 0.4    # hand lost / off the ring for less than this does not restart the hold
RING_TOLERANCE = 1.2  # fingertip must be within this many squares of the ring


class ProjectorChess(ProjectorSurface):
    def __init__(self, game: ChessGame, frame_size: tuple[int, int], canvas_size: tuple[int, int],
                 mirror: bool, flip_vertical: bool):
        super().__init__(frame_size, canvas_size, mirror, flip_vertical)
        self.game = game
        self.detector = ShadowTouchDetector()
        self.smoother = OneEuroFilter2D()
        self.sample = None
        self._scores: list[tuple[float, float]] = []   # (time, score) while the reference pose is held
        self._last_ok = 0.0
        self._anchor = None                            # where the current point-and-hold began
        self._hold_start = self._fired_at = None
        self._failures = 0
        self.hold_only = False                         # the shadow could not be calibrated: point-and-hold only
        self.dwell = 0.0                               # 0..1 of DWELL_S completed, drawn on the square under the finger
        self.progress = 0.0                            # 0..1 of HOLD_S completed, drawn as an arc on the ring
        self._touch_ref = 0.0
        self._revision = game.revision
        self.message = "Open the board on the projector screen, then press Calibrate Projector."

    # ---- what the canvas should show ----
    @property
    def markers(self) -> list[tuple[float, float]]:
        return marker_centres(self.game.origin, self.game.square)

    @property
    def marker_radius(self) -> float:
        return config.PROJECTOR_MARKER_SCALE * self.game.square

    @property
    def target(self) -> tuple[float, float] | None:
        """Canvas point of the ring shown while recording the touch / hover references."""
        if self.phase not in ("touch", "hover"):
            return None
        g = self.game
        return (g.origin[0] + 4 * g.square, g.origin[1] + 4 * g.square)

    @property
    def dwell_square(self) -> tuple[float, float] | None:
        """Canvas centre of the square being held on, while a point-and-hold is filling."""
        if self.dwell <= 0 or self._anchor is None:
            return None
        g = self.game
        sq = g.square_at(self._anchor)
        if sq is None:
            return None
        x, y = g.square_origin(sq)
        return (x + g.square / 2, y + g.square / 2)

    @property
    def hint(self) -> str:
        """Short instruction drawn on the projected board while the touch detector is being set up."""
        return {"learn": "Keep your hand away: memorising the empty board",
                "touch": "Touch the ring with your index fingertip and hold still",
                "hover": "Lift the fingertip about 3 cm above the ring and hold still"}.get(self.phase, "")

    @property
    def playing(self) -> bool:
        return self.phase == "play"

    # ---- calibration ----
    def start_calibration(self, now: float | None = None) -> None:
        self.detector.set_region(None)
        self.detector.invalidate()
        self.game.update(None, False)
        self._failures, self.hold_only = 0, False
        super().start_calibration(now)

    def _camera_lost(self) -> None:
        self.sample = None
        self.smoother.reset()

    def _enter(self, phase: str, message: str, now: float | None = None) -> None:
        super()._enter(phase, message, now)
        self._scores, self.progress = [], 0.0
        self._anchor, self.dwell = None, 0.0

    def _geometry_found(self) -> None:
        view = self.canvas_in_view()
        self.detector.set_region([self.mapper.to_view(p) for p in view] if view else None)   # flips are involutions
        self.detector.invalidate()
        self.detector.set_ambient(self._dark)    # the black-canvas frame: room light without the projector
        self._enter("learn", "Canvas found. Keep your hand away while the empty board is memorised.")

    # ---- per frame ----
    def on_detection(self, det: Detection, now: float) -> None:
        frame = det.frame
        if self.phase in ("learn", "touch", "hover", "play") and not self.mapper.calibrated:
            self.phase, self.message = "idle", "Camera orientation changed: calibrate the projector again."
        if frame is None or self.phase in ("idle", "manual"):
            self.game.update(None, False)
            return
        if self.phase in ("dark", "markers"):
            self._geometry_step(frame, now)
        elif self.phase == "learn":
            self._learn_step(det, now)
        elif self.phase in ("touch", "hover"):
            self._reference_step(det, now)
        else:
            self._play_step(det, now)

    def _learn_step(self, det: Detection, now: float) -> None:
        if det.landmarks_px is None:
            self.detector.observe_empty(det.frame, now)
        else:
            self.detector.hand_seen()
        if self.detector.ready:
            self._enter("touch", "Touch the ring on the board with your index fingertip and hold still.", now)

    def _reference_step(self, det: Detection, now: float) -> None:
        pointer = self._pointer(det)
        ring = self.target
        near = (pointer is not None and ring is not None
                and math.dist(pointer, ring) < RING_TOLERANCE * self.game.square)
        if det.landmarks_px is None or not near:
            if now - self._last_ok > LOSS_GRACE_S:     # a brief tracking dropout must not restart the hold
                if self._scores:
                    log.info("reference hold lost: hand %s, pointer %s, ring %s", det.landmarks_px is not None,
                             None if pointer is None else (round(pointer[0]), round(pointer[1])), ring)
                self._scores, self._phase_start, self.progress = [], now, 0.0
            return
        self._last_ok = now
        self.progress = min((now - self._phase_start) / HOLD_S, 1.0)
        sample = self.detector.measure(det.frame, det.landmarks_px)
        if sample.score is not None:
            self._scores.append((now, sample.score))
        if now - self._phase_start < HOLD_S or not self._scores:
            return
        settled = sorted(s for t, s in self._scores if t - self._phase_start >= SETTLE_S)
        score = settled[len(settled) // 2] if settled else self._scores[-1][1]
        log.info("reference %s: score %.3f from %d samples", self.phase, score, len(settled))
        if self.phase == "touch":
            self._touch_ref = score
            self._enter("hover", "Now lift the fingertip about 3 cm above the ring and hold still.", now)
        elif self.detector.set_references(self._touch_ref, score):
            self._enter("play", "Ready: touch a piece, then touch where it should go.", now)
        elif self._reference_failed():
            self._enter("play", HOLD_ONLY_NOTE, now)
        else:
            blind = max(self._touch_ref, score) < 0.005
            lead = "No shadow is seen at all: dim the room lights or raise the projector brightness. " if blind else ""
            self._enter("touch", lead + "The hand's shadow barely changes between touching and hovering. Check that "
                        "the projector lights the hand from the side and the shadow is visible; then touch the ring "
                        "again.", now)

    def _reference_failed(self) -> bool:
        """Count a rejected pair of references; True once point-and-hold has to be the only way to touch."""
        self._failures += 1
        self.hold_only = self._failures >= MAX_REFERENCE_TRIES
        return self.hold_only

    def _pointer(self, det: Detection):
        if det.tip_px is None:
            self.smoother.reset()
            return None
        mapped = self.mapper.map(det.tip_px)
        return self.smoother.update(mapped) if mapped is not None else None

    def _play_step(self, det: Detection, now: float) -> None:
        if self.game.revision != self._revision:    # the projected board changed: its empty-scene model is stale
            self._revision = self.game.revision
            self.detector.invalidate()
        pointer = self._pointer(det)
        if det.landmarks_px is None or pointer is None:
            self.detector.observe_empty(det.frame, now)
            self.sample = None
            self._anchor, self.dwell = None, 0.0
            self.game.update(None, False)
            self.message = ("Memorising the board… keep your hand away." if not self.detector.ready
                            else HOLD_ONLY_NOTE if self.hold_only else "")
            return
        self.sample = self.detector.measure(det.frame, det.landmarks_px)
        self.message = ("" if self.sample.ready else "Board changed: take your hand away for a moment.") or (
            HOLD_ONLY_NOTE if self.hold_only else "")
        self.game.update(pointer, self._hold(pointer, now) or self.sample.touching)

    def _hold(self, pointer, now: float) -> bool:
        """Point-and-hold touch, for when the hand hides its own shadow from the camera: True for a moment once the
        fingertip has stayed put for DWELL_S. It fires once; the finger must move away before it can fire again."""
        if self._anchor is None or math.dist(pointer, self._anchor) > DWELL_RADIUS * self.game.square:
            self._anchor, self._hold_start, self._fired_at, self.dwell = pointer, now, None, 0.0
            return False
        if self._fired_at is not None:
            return now - self._fired_at < DWELL_TAP_S
        self.dwell = min((now - self._hold_start) / DWELL_S, 1.0)
        if self.dwell >= 1.0:
            self._fired_at, self.dwell = now, 0.0
            return True
        return False

    def stats_text(self) -> str:
        s = self.sample
        if not self.playing or s is None or s.score is None:
            return f"touch: {self.phase}"
        near = "none" if s.near is None else f"{s.near:.2f}"
        return (f"touch        : {'TOUCH' if s.touching else 'hover'}  shadow score {s.score:.3f}\n"
                f"nearest shadow: {near} palm (a touch needs <= {config.TOUCH_NEAR_MAX})")

    def pointer_ring(self):
        if self.game.pointer is None:
            return None
        touching = self.sample is not None and self.sample.touching
        return self.game.pointer, QColor(40, 220, 70) if touching else QColor(255, 200, 0)
