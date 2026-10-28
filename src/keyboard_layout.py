"""Key geometry of a US/ANSI-style laptop keyboard, in key units (1 unit = one standard key width).

Six full-height rows (function row, number row ... space bar), 14.5 x 6 units, measured from a MacBook Air
(Apple rows are 14.5 key pitches wide; the arrow cluster is three keys with up/down half-height).
`char` is the text a key produces: "\\b" backspace, "\\n" enter, "\\t" tab, None for keys that type nothing here.
"""
from dataclasses import dataclass

LAYOUT_W, LAYOUT_H = 14.5, 6.0


@dataclass(frozen=True)
class Key:
    name: str
    char: str | None
    x: float
    y: float
    w: float
    h: float = 1.0

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px < self.x + self.w and self.y <= py < self.y + self.h


def _row(items: list[tuple[str, str | None, float]], y: float, expected_width: float = LAYOUT_W) -> list[Key]:
    keys, x = [], 0.0
    for name, char, width in items:
        keys.append(Key(name, char, x, y, width))
        x += width
    assert abs(x - expected_width) < 1e-9, f"row at y={y} is {x} units wide, expected {expected_width}"
    return keys


def _chars(text: str) -> list[tuple[str, str, float]]:
    return [(c, c, 1.0) for c in text]


_ROWS = [
    [("esc", None, 1.5)] + [(f"F{i}", None, 1.0) for i in range(1, 13)] + [("\u23fb", None, 1.0)],
    _chars("`1234567890-=") + [("⌫", "\b", 1.5)],
    [("⇥", "\t", 1.5)] + _chars("qwertyuiop[]") + [("\\", "\\", 1.0)],
    [("⇪", None, 1.75)] + _chars("asdfghjkl;'") + [("⏎", "\n", 1.75)],
    [("⇧", None, 2.25)] + _chars("zxcvbnm,./") + [("⇧", None, 2.25)],
    [("fn", None, 1.0), ("ctrl", None, 1.0), ("opt", None, 1.0), ("cmd", None, 1.25), ("space", " ", 5.0),
     ("cmd", None, 1.25), ("opt", None, 1.0)],
]
_ARROW_X, _ARROW_Y = 11.5, 5.0   # arrow cluster: left, up/down (half-height each), right

KEYS: list[Key] = [k for y, row in enumerate(_ROWS[:-1]) for k in _row(row, float(y))]
KEYS += _row(_ROWS[-1], 5.0, expected_width=_ARROW_X)   # bottom row up to the arrow cluster
KEYS += [Key("◀", None, _ARROW_X, _ARROW_Y, 1.0), Key("▲", None, _ARROW_X + 1, _ARROW_Y, 1.0, 0.5),
         Key("▼", None, _ARROW_X + 1, _ARROW_Y + 0.5, 1.0, 0.5), Key("▶", None, _ARROW_X + 2, _ARROW_Y, 1.0)]
assert abs(sum(k.w * k.h for k in KEYS) - LAYOUT_W * LAYOUT_H) < 1e-9

# Shifted character -> the key that produces it (for comparing against what the real keyboard reported).
_SHIFTED = dict(zip('~!@#$%^&*()_+{}|:"<>?', "`1234567890-=[]\\;',./"))
_SHIFTED["\r"] = "\n"


def key_at(x: float, y: float) -> Key | None:
    for key in KEYS:
        if key.contains(x, y):
            return key
    return None


def base_char(ch: str) -> str | None:
    """The layout character a real keystroke corresponds to ('A' -> 'a', '!' -> '1'), or None if not on the layout."""
    ch = _SHIFTED.get(ch, ch.lower())
    return ch if any(k.char == ch for k in KEYS) else None
