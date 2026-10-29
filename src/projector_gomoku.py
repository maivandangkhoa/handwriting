"""Gomoku on a projector: the chess touch machinery (shadow touch, point-and-hold) driving a GomokuGame."""
from .projector_calib import marker_centres
from .projector_chess import ProjectorChess


class ProjectorGomoku(ProjectorChess):
    ready_note = "Ready: touch an empty cell to place your stone."
    hold_note = "The shadow cannot tell touch from hover here. Point-and-hold: keep your fingertip on a cell for a second."

    @property
    def markers(self) -> list[tuple[float, float]]:
        return marker_centres(self.game.origin, self.game.square, self.game.cells)
