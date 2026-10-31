"""Music for the Mirror dance: a few nursery tunes with a bouncy beat, synthesised once per song into a seamless loop and
played on repeat through Qt's QSoundEffect."""
import tempfile
from pathlib import Path

import numpy as np

from .piano_layout import frequency
from .piano_sound import RATE, wav_bytes

BPM = 120
BEATS_PER_BAR = 4
SEMITONE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
CHORDS = {"C": (0, 4, 7), "F": (5, 9, 0), "G": (7, 11, 2)}     # pitch classes of the three chords that fit C major

SONGS = {
    "Twinkle Twinkle": " ".join([
        "C4 C4 G4 G4 A4 A4 G4:2  F4 F4 E4 E4 D4 D4 C4:2",
        "G4 G4 F4 F4 E4 E4 D4:2  G4 G4 F4 F4 E4 E4 D4:2",
        "C4 C4 G4 G4 A4 A4 G4:2  F4 F4 E4 E4 D4 D4 C4:2"]),
    "Old MacDonald": " ".join([
        "C4 C4 C4 G3 A3 A3 G3:2  E4 E4 D4 D4 C4:2 G3:2",
        "C4 C4 C4 G3 A3 A3 G3:2  E4 E4 D4 D4 C4:2 G3:2",
        "C4 C4 C4:.5 C4:.5 C4 C4 C4:.5 C4:.5 C4 C4:.5 C4:.5 C4 C4",
        "C4 C4 C4 G3 A3 A3 G3:2  E4 E4 D4 D4 C4:4"]),
    "Ode to Joy": " ".join([
        "E4 E4 F4 G4 G4 F4 E4 D4  C4 C4 D4 E4 E4:1.5 D4:.5 D4:2",
        "E4 E4 F4 G4 G4 F4 E4 D4  C4 C4 D4 E4 D4:1.5 C4:.5 C4:2",
        "D4 D4 E4 C4 D4 E4:.5 F4:.5 E4 C4  D4 E4:.5 F4:.5 E4 D4 C4 D4 G3:2",
        "E4 E4 F4 G4 G4 F4 E4 D4  C4 C4 D4 E4 D4:1.5 C4:.5 C4:2"]),
}
SONG_NAMES = list(SONGS)


def parse(score: str) -> list[tuple[int, float, float]]:
    """'C4 G4:2 ...' -> (midi, start beat, length in beats). Length defaults to one beat."""
    notes, beat = [], 0.0
    for token in score.split():
        name, _, length = token.partition(":")
        midi = 12 * (int(name[-1]) + 1) + SEMITONE[name[0]]
        beats = float(length) if length else 1.0
        notes.append((midi, beat, beats))
        beat += beats
    return notes


def chord_for_bar(notes, bar: int) -> str:
    """The chord (C, F or G) whose notes cover most of the melody in this bar."""
    lo, hi = bar * BEATS_PER_BAR, (bar + 1) * BEATS_PER_BAR
    weight = {c: 0.0 for c in CHORDS}
    for midi, start, length in notes:
        overlap = min(hi, start + length) - max(lo, start)
        if overlap > 0:
            for c, tones in CHORDS.items():
                weight[c] += overlap * (midi % 12 in tones)
    return max(weight, key=weight.get)


def _tone(midi: int, seconds: float, bright: float) -> np.ndarray:
    """A soft xylophone-like note: a few harmonics with a quick decay."""
    t = np.arange(int(RATE * seconds)) / RATE
    f = frequency(midi)
    out = sum(bright ** k / k * np.sin(2 * np.pi * f * k * t) for k in (1, 2, 3))
    return out * np.exp(-t * 4.0) * np.minimum(t / 0.004, 1.0)


def _kick() -> np.ndarray:
    t = np.arange(int(RATE * 0.18)) / RATE
    return np.sin(2 * np.pi * (50 * t + 60 * (1 - np.exp(-t * 30)) / 30)) * np.exp(-t * 22)


def _noise(seconds: float, decay: float, rng) -> np.ndarray:
    t = np.arange(int(RATE * seconds)) / RATE
    return rng.uniform(-1, 1, t.size) * np.exp(-t * decay)


def _add(mix: np.ndarray, sound: np.ndarray, at: float, gain: float) -> None:
    """Mix `sound` in at `at` seconds; what runs past the end wraps round to the start so the loop has no gap."""
    idx = (int(at * RATE) + np.arange(sound.size)) % mix.size
    np.add.at(mix, idx, gain * sound)


def render(name: str) -> np.ndarray:
    """One full pass of the song as float samples in -1..1: melody, walking bass, kick on 1 and 3, snare on 2 and 4,
    hi-hat on every half beat."""
    notes = parse(SONGS[name])
    total = sum(n[2] for n in notes)
    bars = int(round(total / BEATS_PER_BAR))
    sec = 60.0 / BPM
    mix = np.zeros(int(round(bars * BEATS_PER_BAR * sec * RATE)))
    rng = np.random.default_rng(1)
    for midi, start, length in notes:
        _add(mix, _tone(midi, min(length * sec + 0.4, 1.5), 0.45), start * sec, 0.5)
    for bar in range(bars):
        root = {"C": 36, "F": 41, "G": 43}[chord_for_bar(notes, bar)]
        for beat in range(BEATS_PER_BAR):
            at = (bar * BEATS_PER_BAR + beat) * sec
            _add(mix, _tone(root + (7 if beat % 2 else 0), 0.45, 0.3), at, 0.45)
            if beat % 2 == 0:
                _add(mix, _kick(), at, 0.7)
            else:
                _add(mix, _noise(0.12, 28, rng), at, 0.18)
            _add(mix, _noise(0.04, 90, rng), at, 0.06)
            _add(mix, _noise(0.04, 90, rng), at + sec / 2, 0.05)
    return 0.8 * mix / np.max(np.abs(mix))


class DancePlayer:
    """Plays one song at a time on repeat; each song is rendered the first time it is chosen."""

    def __init__(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtMultimedia import QSoundEffect
        self._url = QUrl
        self._folder = tempfile.TemporaryDirectory(prefix="fingertrace_dance_")
        self._effects: dict[str, QSoundEffect] = {}
        self._effect_class = QSoundEffect
        self._current: str | None = None

    def play(self, name: str | None) -> None:
        """Start `name` (None = silence), stopping whatever played before."""
        if name == self._current:
            return
        if self._current is not None:
            self._effects[self._current].stop()
        self._current = name
        if name is None:
            return
        if name not in self._effects:
            path = Path(self._folder.name) / f"{len(self._effects)}.wav"
            path.write_bytes(wav_bytes(render(name)))
            effect = self._effect_class()
            effect.setSource(self._url.fromLocalFile(str(path)))
            effect.setLoopCount(self._effect_class.Loop.Infinite.value)
            effect.setVolume(0.8)
            self._effects[name] = effect
        self._effects[name].play()

    def stop(self) -> None:
        self.play(None)
