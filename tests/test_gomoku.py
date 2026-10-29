"""Gomoku rules, and the shared projector machinery driving a gomoku board end to end."""
import cv2
import numpy as np

from src import config
from src.gomoku_game import GomokuGame
from src.projector_gomoku import ProjectorGomoku
from src import projector_chess
from tests.test_projector_chess import CANVAS, DT, Rig, calibrated_rig


def centre(g, cell):
    x, y = g.square_origin(cell)
    return (x + g.square / 2, y + g.square / 2)


def place(g, *cells):
    for cell in cells:
        g.update(centre(g, cell), True)
        g.update(None, False)


def test_stones_alternate_and_taken_cells_are_refused():
    g = GomokuGame()
    place(g, (3, 3), (4, 4), (3, 3))
    assert g.stones == {(3, 3): 0, (4, 4): 1} and g.turn == 0 and "taken" in g.notice


def test_five_in_a_row_wins_in_every_direction():
    for run in ([(i, 2) for i in range(5)], [(2, i) for i in range(5)],
                [(i, i) for i in range(5)], [(4 - i, i) for i in range(5)]):
        g = GomokuGame()
        others = [(9, 9), (9, 8), (9, 7), (9, 6)]
        for mine, theirs in zip(run, others + [None]):
            place(g, mine)
            if theirs:
                place(g, theirs)
        assert g.winner == 0 and sorted(g.line) == sorted(run) and g.over, run


def test_four_is_not_enough_and_nothing_can_be_placed_after_a_win():
    g = GomokuGame()
    place(g, (0, 0), (0, 5), (1, 0), (1, 5), (2, 0), (2, 5), (3, 0), (3, 5))
    assert g.winner is None
    place(g, (4, 0))
    assert g.winner == 0
    place(g, (6, 6))
    assert (6, 6) not in g.stones


def test_six_in_a_row_also_wins():
    g = GomokuGame()
    place(g, (0, 0), (0, 5), (1, 0), (1, 5), (2, 0), (2, 5), (4, 0), (4, 5), (5, 0), (5, 6))
    assert g.winner is None
    place(g, (3, 0))
    assert g.winner == 0 and len(g.line) == 6


class GomokuRig(Rig):
    def __init__(self):
        super().__init__()
        self.game = GomokuGame()
        self.app = ProjectorGomoku(self.game, (1280, 720), CANVAS, mirror=False, flip_vertical=False)

    def canvas_image(self):
        img = np.zeros((CANVAS[1], CANVAS[0], 3), np.uint8)
        pattern = self.app.pattern
        if pattern is None:
            img[:] = 110
        if pattern == "markers":
            for x, y in self.app.markers:
                cv2.circle(img, (int(x), int(y)), int(self.app.marker_radius), (255, 255, 255), -1, cv2.LINE_AA)
        elif pattern is None:
            g = self.game
            x0, y0 = g.origin
            img[y0:y0 + g.cells * g.square, x0:x0 + g.cells * g.square] = 170
            ring = self.app.target
            if ring is not None:
                cv2.circle(img, (int(ring[0]), int(ring[1])), 26, (120, 235, 255), 5)
        return img


def calibrated_gomoku() -> GomokuRig:
    rig = GomokuRig()
    rig.app.start_calibration(rig.t)
    rig.step(n=int(config.PROJECTOR_PHASE_S / DT) * 2 + 4)
    assert rig.app.phase == "learn", rig.app.message
    rig.step(n=int(config.BACKGROUND_EMPTY_S / DT) + config.BACKGROUND_FRAMES + 3)
    ring = rig.app.target
    rig.step(ring, height=0, n=int(1.4 / DT) + 3)
    rig.step(ring, height=35, n=int(1.4 / DT) + 3)
    assert rig.app.phase == "play", rig.app.message
    return rig


def test_calibration_finds_the_ten_by_ten_board():
    rig = calibrated_gomoku()
    cx, cy = rig.cam_point((640, 360))
    mapped = rig.app.mapper.map((float(cx), float(cy)), clamp=False)
    assert np.hypot(mapped[0] - 640, mapped[1] - 360) < 3


def test_point_and_hold_places_a_stone_then_the_other_player_moves():
    rig = calibrated_gomoku()
    rig.step(n=40)
    hold = int(projector_chess.DWELL_S / DT) + 6
    rig.step(centre(rig.game, (4, 4)), height=60, n=hold)
    assert rig.game.stones == {(4, 4): 0}, rig.app.message
    rig.step(n=40)
    rig.step(centre(rig.game, (5, 5)), height=60, n=hold)
    assert rig.game.stones.get((5, 5)) == 1
