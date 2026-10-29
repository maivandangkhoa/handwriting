"""End to end: a simulated projector + camera drive ProjectorChess through calibration and a real move."""
import chess
import cv2
import numpy as np

from src import config
from src.chess_game import ChessGame
from src.hand_tracker import Detection
from src.projector_calib import marker_centres
from src import projector_chess
from src.projector_chess import ProjectorChess
from tests import scene

CANVAS = (config.CANVAS_WIDTH, config.CANVAS_HEIGHT)
SEEN = np.float32([(200, 100), (1090, 70), (1150, 650), (130, 620)])    # where the camera sees the canvas corners
H = cv2.getPerspectiveTransform(np.float32([(0, 0), (CANVAS[0], 0), CANVAS, (0, CANVAS[1])]), SEEN)
DT = 1 / 30


class Rig:
    """Projector showing whatever the app asks for, a camera looking at it, and a finger that can be placed on it."""

    def __init__(self):
        self.game = ChessGame()
        self.app = ProjectorChess(self.game, (1280, 720), CANVAS, mirror=False, flip_vertical=False)
        self.t = 0.0
        self.seed = 0

    def canvas_image(self) -> np.ndarray:
        img = np.zeros((CANVAS[1], CANVAS[0], 3), np.uint8)
        pattern = self.app.pattern
        if pattern is None:
            img[:] = 110      # the lit margin around the board
        if pattern == "markers":
            for x, y in self.app.markers:
                cv2.circle(img, (int(x), int(y)), int(self.app.marker_radius), (255, 255, 255), -1, cv2.LINE_AA)
        elif pattern is None:
            sq = self.game.square
            for r in range(8):
                for c in range(8):
                    v = 205 if (r + c) % 2 == 0 else 95
                    x0, y0 = int(self.game.origin[0] + c * sq), int(self.game.origin[1] + r * sq)
                    img[y0:y0 + sq, x0:x0 + sq] = v
            ring = self.app.target
            if ring is not None:
                cv2.circle(img, (int(ring[0]), int(ring[1])), 26, (120, 235, 255), 5)
        return img

    def cam_point(self, canvas_pt) -> np.ndarray:
        return cv2.perspectiveTransform(np.float32([[canvas_pt]]), H)[0, 0]

    def frame(self, hand_at=None, height=0.0):
        self.seed += 1
        base = cv2.warpPerspective(self.canvas_image(), H, (1280, 720)).astype(np.float32) * 0.8 + 30
        base = np.clip(base, 0, 255).astype(np.uint8)
        if hand_at is None:
            return scene.render(0, seed=self.seed, shadow=False, hand=False, base=base), None
        shift = self.cam_point(hand_at) - np.array((420.0, 320.0))
        return scene.render(height, seed=self.seed, base=base, shift=shift), scene.hand_landmarks(shift)

    def step(self, hand_at=None, height=0.0, n=1):
        for _ in range(n):
            frame, lm = self.frame(hand_at, height)
            det = Detection(lm, 0 if lm is None else 1, 0.0, [] if lm is None else [lm], frame=frame)
            self.app.on_detection(det, self.t)
            self.t += DT

    def square(self, sq):
        x, y = self.game.square_origin(sq)
        return (x + self.game.square / 2, y + self.game.square / 2)

    def tap(self, sq):
        self.step(self.square(sq), height=60, n=3)     # approach
        self.step(self.square(sq), height=0, n=4)      # land
        self.step(self.square(sq), height=60, n=3)     # lift


def calibrated_rig() -> Rig:
    rig = Rig()
    rig.app.start_calibration(rig.t)
    rig.step(n=int(config.PROJECTOR_PHASE_S / DT) + 2)    # dark
    assert rig.app.phase == "markers"
    rig.step(n=int(config.PROJECTOR_PHASE_S / DT) + 2)    # discs
    assert rig.app.phase == "learn", rig.app.message
    rig.step(n=int((config.BACKGROUND_EMPTY_S) / DT) + config.BACKGROUND_FRAMES + 3)
    assert rig.app.phase == "touch", rig.app.phase
    ring = rig.app.target
    rig.step(ring, height=0, n=int(1.4 / DT) + 3)
    assert rig.app.phase == "hover", rig.app.message
    rig.step(ring, height=35, n=int(1.4 / DT) + 3)
    assert rig.app.phase == "play", rig.app.message
    return rig


def test_full_calibration_finds_the_canvas_and_references():
    rig = calibrated_rig()
    assert rig.app.mapper.calibrated and rig.app.detector.calibrated
    cx, cy = rig.cam_point((640, 360))
    mapped = rig.app.mapper.map((float(cx), float(cy)), clamp=False)
    assert np.hypot(mapped[0] - 640, mapped[1] - 360) < 3


def test_tap_a_pawn_then_its_destination_makes_the_move():
    rig = calibrated_rig()
    rig.step(n=40)                       # hand away: the board scene is (re)learned
    rig.tap(chess.E2)
    assert rig.game.held == chess.E2, rig.app.message
    rig.step(n=3)                        # hand leaves; the selection stays
    rig.tap(chess.E4)
    assert rig.game.board.piece_at(chess.E4) is not None and rig.game.board.turn == chess.BLACK


def test_hovering_over_squares_does_not_select_anything():
    rig = calibrated_rig()
    rig.step(n=40)
    for sq in (chess.E2, chess.D2, chess.G1):
        rig.step(rig.square(sq), height=60, n=6)
    assert rig.game.held is None


def test_moving_the_projected_board_makes_touches_wait_for_the_scene_to_be_relearned():
    rig = calibrated_rig()
    rig.step(n=40)
    rig.game.new_game()
    rig.step(rig.square(chess.E2), height=0, n=4)       # hand is there while the scene is stale
    assert rig.game.held is None and "hand away" in rig.app.message


def test_calibration_failure_falls_back_to_manual_clicks():
    rig = Rig()
    rig.app.start_calibration(rig.t)
    rig.step(n=int(config.PROJECTOR_PHASE_S / DT) + 2)
    # the camera stares at a wall: the discs never show up
    for _ in range(int(config.PROJECTOR_PHASE_S / DT) + 2):
        frame = np.full((720, 1280, 3), 40, np.uint8)
        rig.app.on_detection(Detection(None, 0, 0.0, frame=frame), rig.t)
        rig.t += DT
    assert rig.app.phase == "manual" and "not visible" in rig.app.message
    assert rig.app.pattern == "markers"


def test_point_and_hold_selects_and_moves_without_any_shadow_touch():
    rig = calibrated_rig()
    rig.step(n=40)
    hold = int(projector_chess.DWELL_S / DT) + 6
    rig.step(rig.square(chess.E2), height=60, n=hold)       # hovering, never touching: held still on the pawn
    assert rig.game.held == chess.E2
    rig.step(rig.square(chess.E2), height=60, n=hold)       # keeps holding: does not toggle it off again
    assert rig.game.held == chess.E2
    rig.step(rig.square(chess.E4), height=60, n=hold)
    assert rig.game.board.piece_at(chess.E4) is not None and rig.game.board.turn == chess.BLACK


def test_point_and_hold_needs_a_still_finger():
    rig = calibrated_rig()
    rig.step(n=40)
    for _ in range(6):                                       # sweeping across the files, never resting
        for sq in (chess.C2, chess.D2, chess.E2, chess.F2):
            rig.step(rig.square(sq), height=60, n=int(projector_chess.DWELL_S / DT / 3))
    assert rig.game.held is None


def test_rejected_shadow_references_leave_point_and_hold():
    rig = Rig()
    rig.app.start_calibration(rig.t)
    rig.step(n=int(config.PROJECTOR_PHASE_S / DT) * 2 + 4)
    rig.step(n=int(config.BACKGROUND_EMPTY_S / DT) + config.BACKGROUND_FRAMES + 3)
    ring = rig.app.target
    for _ in range(projector_chess.MAX_REFERENCE_TRIES):     # the shadow looks the same touching and hovering
        rig.step(ring, height=0, n=int(1.4 / DT) + 3)
        rig.step(ring, height=0, n=int(1.4 / DT) + 3)
    assert rig.app.phase == "play" and "Point-and-hold" in rig.app.message
