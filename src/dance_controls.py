"""Mirror dance side panel: how many people to follow and which song to dance to."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

from . import config
from .dance_music import SONG_NAMES


class DanceControls(QWidget):
    people_changed = Signal(int)
    music_changed = Signal(int)     # 0 = off, then the songs in order

    def __init__(self, people: int, music: int):
        super().__init__()
        self.people = QComboBox()
        self.people.addItems([f"{n} {'person' if n == 1 else 'people'}" for n in range(1, config.DANCE_MAX_PEOPLE + 1)])
        self.people.setCurrentIndex(min(max(people, 1), config.DANCE_MAX_PEOPLE) - 1)
        self.people.activated.connect(lambda i: self.people_changed.emit(i + 1))
        self.music = QComboBox()
        self.music.addItems(["Music off", *SONG_NAMES])
        self.music.setCurrentIndex(min(max(music, 0), len(SONG_NAMES)))
        self.music.activated.connect(self.music_changed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for w in (QLabel("Dancers:"), self.people, QLabel("Music:"), self.music):
            layout.addWidget(w)
