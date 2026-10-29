"""Projector UI pieces: the control panel and the fullscreen window shown on the projector."""
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import QComboBox, QLabel, QPushButton, QVBoxLayout, QWidget

from .canvas import CanvasWidget


class ProjectorWindow(CanvasWidget):
    """The canvas alone, fullscreen on one screen (Esc closes it). Chess shows no cursor: the real finger is the pointer."""

    def __init__(self, state, follow: CanvasWidget):
        super().__init__(state)
        self.show_cursor = False
        self._follow = follow        # the main window's canvas: pen state (pinching) is copied from it
        self.setWindowTitle("FingerTrace projector")
        self.setCursor(Qt.BlankCursor)
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self.close)
        self._tick = QTimer(self, interval=33, timeout=self._refresh)   # follows the shared game / stroke state
        self._tick.start()

    def _refresh(self) -> None:
        self.pinching = self._follow.pinching
        self.update()

    def show_on(self, screen) -> None:
        self.setScreen(screen)
        self.setGeometry(screen.geometry())
        self.showFullScreen()


class ProjectorControls(QWidget):
    """Projector panel: calibration button and the screen to project on."""
    calibrate_clicked = Signal()
    open_clicked = Signal(int)   # screen index

    def __init__(self):
        super().__init__()
        self.screens = QComboBox()
        self.screen_help = QLabel("Projector screen:")
        self.open_btn = QPushButton("Open on projector screen")
        self.open_btn.clicked.connect(lambda: self.open_clicked.emit(max(self.screens.currentIndex(), 0)))
        self.calib_btn = QPushButton("Calibrate Projector (auto)")
        self.calib_btn.clicked.connect(self.calibrate_clicked)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for w in (self.screen_help, self.screens, self.open_btn, self.calib_btn):
            layout.addWidget(w)
        self.refresh_screens()

    def refresh_screens(self) -> None:
        self.screens.clear()
        for i, s in enumerate(QGuiApplication.screens()):
            g = s.geometry()
            self.screens.addItem(f"Screen {i}: {s.name()} ({g.width()}x{g.height()})", i)
        if self.screens.count() > 1:
            self.screens.setCurrentIndex(1)   # the second screen is usually the projector
