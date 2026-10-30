"""Colouring book on a projector: the gomoku board geometry with its own instructions."""
from .projector_gomoku import ProjectorGomoku


class ProjectorColoring(ProjectorGomoku):
    ready_note = "Ready: touch a colour, then touch the picture to paint."
    hold_note = "The shadow cannot tell touch from hover here. Point-and-hold: keep your fingertip on a cell to press it."
