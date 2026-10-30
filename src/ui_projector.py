"""What the main window needs to host the projector apps: which app and game a mode means, the projector window, and
the piano's sounds. Mixed into MainWindow."""
import logging

from PySide6.QtWidgets import QApplication

from .piano_sound import QtPlayer
from .projector_window import ProjectorWindow

log = logging.getLogger(__name__)


class ProjectorApps:
    @property
    def chess_mode(self) -> bool:
        """A board game on the projector (chess, gomoku, colouring)."""
        return self.mode in (1, 5, 6)

    @property
    def active_game(self):
        return {1: self.game, 5: self.gomoku_game, 6: self.coloring_game}.get(self.mode)

    @property
    def projector_app(self):
        """The projector app of the current mode, else None."""
        return {1: self.proj, 3: self.draw_proj, 4: self.piano, 5: self.gomoku, 6: self.coloring,
                7: self.animals}.get(self.mode)

    def _load_piano_sounds(self, row: int):
        """The 24 tones are synthesised on first use of the piano, not at start-up."""
        if row == 4 and self.piano.player is None:
            try:
                self.piano.player = QtPlayer()
            except Exception as exc:   # no audio support: the piano still shows, silently
                log.error("Piano sound unavailable: %s", exc)
                self.piano.message = f"Piano sound unavailable ({exc}); the keys will light up but stay silent."

    def _release_pointers(self):
        for g in (self.game, self.gomoku_game, self.coloring_game):
            g.update(None, False)

    def _new_game(self):
        self.active_game.new_game()
        self.canvas.update()

    def _calibrate_projector(self):
        if self.worker is None:
            self.message = "Start the camera before calibrating."
            return
        self.projector_app.start_calibration()

    def _open_projector(self, index: int):
        screens = QApplication.screens()
        if self.proj_win is None:
            self.proj_win = ProjectorWindow(self.state, self.canvas)
            self._bind_projector_window()
        self.proj_win.show_on(screens[min(index, len(screens) - 1)])

    def _bind_projector_window(self):
        """The projector window shows what the current app shows; only the cursor differs (the finger is the cursor
        for chess, but the drawing pen position is useful to see)."""
        win = self.proj_win
        if win is not None:
            win.game, win.projector, win.show_cursor = self.active_game, self.projector_app, self.mode == 3
            win.update()
