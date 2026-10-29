"""Piano keyboard geometry on the logical canvas: two octaves, C4 to B5. No Qt."""
from dataclasses import dataclass

FIRST_MIDI = 60                    # C4
OCTAVES = 2
LEFT, RIGHT, TOP, BOTTOM = 40.0, 1240.0, 300.0, 660.0     # canvas px
WHITE_STEPS = [0, 2, 4, 5, 7, 9, 11]                       # semitones of the white keys in an octave
BLACK_AFTER = {0: 1, 2: 3, 5: 6, 7: 8, 9: 10}              # white key (semitone) -> the black semitone to its right
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
WHITE_COUNT = len(WHITE_STEPS) * OCTAVES
WHITE_W = (RIGHT - LEFT) / WHITE_COUNT                     # also the unit of fingertip distances for press detection
BLACK_W, BLACK_H = 0.6 * WHITE_W, 0.62 * (BOTTOM - TOP)


@dataclass(frozen=True)
class Key:
    midi: int
    name: str
    black: bool
    x: float
    y: float
    w: float
    h: float

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px < self.x + self.w and self.y <= py < self.y + self.h


def _build() -> list[Key]:
    white, black = [], []
    for i in range(WHITE_COUNT):
        octave, step = divmod(i, len(WHITE_STEPS))
        semitone = WHITE_STEPS[step]
        midi = FIRST_MIDI + 12 * octave + semitone
        x = LEFT + i * WHITE_W
        white.append(Key(midi, f"{NAMES[semitone]}{midi // 12 - 1}", False, x, TOP, WHITE_W, BOTTOM - TOP))
        if semitone in BLACK_AFTER and i < WHITE_COUNT - 1:
            bm = midi + 1
            black.append(Key(bm, f"{NAMES[BLACK_AFTER[semitone]]}{bm // 12 - 1}", True,
                             x + WHITE_W - BLACK_W / 2, TOP, BLACK_W, BLACK_H))
    return white + black


KEYS: list[Key] = _build()          # white keys first, then black keys (the order to paint them in)


def key_at(x: float, y: float) -> Key | None:
    """The key under a canvas point; a black key wins over the white keys behind it."""
    for key in reversed(KEYS):
        if key.contains(x, y):
            return key
    return None


def frequency(midi: int) -> float:
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)
