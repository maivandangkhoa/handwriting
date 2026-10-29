"""Piano-like tones: synthesised once per note (additive harmonics with decay), played through Qt's QSoundEffect."""
import io
import tempfile
import wave
from pathlib import Path

import numpy as np

from .piano_layout import KEYS, frequency

RATE = 44100
LENGTH_S = 2.2
HARMONICS = 7


def render(midi: int) -> np.ndarray:
    """One note as float samples in -1..1: a soft attack, then each harmonic dying away faster than the last."""
    f0 = frequency(midi)
    t = np.arange(int(RATE * LENGTH_S)) / RATE
    out = np.zeros_like(t)
    for k in range(1, HARMONICS + 1):
        f = f0 * k * (1 + 0.0004 * k * k)                    # slight stretch, as in real strings
        if f > 0.45 * RATE:
            break
        out += (1.0 / k ** 1.15) * np.exp(-t * (1.6 + 1.1 * k)) * np.sin(2 * np.pi * f * t)
    out *= np.minimum(t / 0.004, 1.0)                        # 4 ms attack: no click
    out *= np.minimum((LENGTH_S - t) / 0.05, 1.0)            # and a short release at the end
    return 0.55 * out / np.max(np.abs(out))


def wav_bytes(samples: np.ndarray) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
    return buf.getvalue()


class QtPlayer:
    """Plays notes with one QSoundEffect per key, so several notes sound together and a repeated key restarts."""

    def __init__(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtMultimedia import QSoundEffect
        self._folder = tempfile.TemporaryDirectory(prefix="fingertrace_piano_")
        self._effects: dict[int, QSoundEffect] = {}
        for key in KEYS:
            path = Path(self._folder.name) / f"{key.midi}.wav"
            path.write_bytes(wav_bytes(render(key.midi)))
            effect = QSoundEffect()
            effect.setSource(QUrl.fromLocalFile(str(path)))
            effect.setVolume(0.9)
            self._effects[key.midi] = effect

    def play(self, midi: int) -> None:
        effect = self._effects.get(midi)
        if effect is not None:
            effect.stop()
            effect.play()
