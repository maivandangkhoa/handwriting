from src.keyboard_layout import KEYS, LAYOUT_H, LAYOUT_W, base_char, key_at


def test_rows_fill_the_layout_without_gaps_or_overlap():
    assert max(k.x + k.w for k in KEYS) == LAYOUT_W and max(k.y + k.h for k in KEYS) == LAYOUT_H
    assert sum(k.w * k.h for k in KEYS) == LAYOUT_W * LAYOUT_H


def test_key_lookup_by_position():
    assert key_at(0.5, 0.5).name == "esc" and key_at(0.5, 1.5).char == "`"
    assert key_at(2.0, 2.5).char == "q"          # tab is 1.5 wide, so q starts at x = 1.5
    assert key_at(1.6, 2.5).char == "⇪" or key_at(1.6, 3.5).char is None   # caps lock types nothing
    assert key_at(8.0, 5.5).char == " "
    assert key_at(14.5, 1.5).char == "\b"
    assert key_at(-0.1, 0.5) is None and key_at(15.0, 0.5) is None and key_at(5, 6.0) is None


def test_home_row_letters_in_order():
    assert [key_at(x, 3.5).char for x in (2.0, 3.0, 4.0, 5.0)] == ["a", "s", "d", "f"]   # caps lock is 1.75 wide
    letters = "".join(k.char for k in KEYS if k.y == 3.0 and k.char and k.char.isalpha())
    assert letters == "asdfghjkl"


def test_base_char_maps_shifted_and_rejects_unknown():
    assert base_char("A") == "a" and base_char("!") == "1" and base_char("?") == "/"
    assert base_char("\r") == "\n" and base_char("\b") == "\b" and base_char(" ") == " "
    assert base_char("é") is None
