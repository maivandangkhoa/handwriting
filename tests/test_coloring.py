"""Colouring book rules, and the main window hosting it."""
from src.coloring_game import KEYS, NEXT_CELL, PALETTE_COL, PICTURES, RESET_CELL, ColoringGame


def press(g, cell):
    x, y = g.square_origin(cell)
    g.update((x + g.square / 2, y + g.square / 2), True)
    g.update(None, False)


def test_a_colour_is_chosen_from_the_palette_then_painted_onto_the_picture():
    g = ColoringGame()
    press(g, (PALETTE_COL, KEYS.index("L")))
    press(g, (3, 4))
    assert g.painted == {(3, 4): "L"}


def test_background_cells_cannot_be_painted():
    g = ColoringGame()
    assert g.target((0, 0)) is None
    press(g, (0, 0))
    assert g.painted == {}


def test_painting_every_cell_in_its_colour_finishes_the_picture():
    g = ColoringGame()
    cells = [(c, r) for c in range(8) for r in range(10) if g.target((c, r))]
    for cell in cells:
        press(g, (PALETTE_COL, KEYS.index(g.target(cell))))
        press(g, cell)
    assert g.done and "Well done" in g.notice


def test_next_picture_and_reset_buttons():
    g = ColoringGame()
    press(g, (3, 4))
    press(g, RESET_CELL)
    assert g.painted == {}
    press(g, NEXT_CELL)
    assert g.name == list(PICTURES)[1]


def test_every_picture_fits_the_grid_and_uses_known_colours():
    from src.coloring_game import COLORS, PICTURE_COLS, PICTURE_ROWS
    for rows in PICTURES.values():
        assert len(rows) == PICTURE_ROWS and all(len(r) == PICTURE_COLS for r in rows)
        assert set("".join(rows)) <= set(COLORS) | {"."}


def test_main_window_offers_the_colouring_book(qtbot=None):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from src.ui import MainWindow
    w = MainWindow()
    w.app_box.setCurrentIndex(6)
    w._on_app_selected(6)
    assert w.active_game is w.coloring_game and w.projector_app is w.coloring and w.canvas.game is w.coloring_game
    w.canvas.resize(1280, 720)
    assert not w.canvas.grab().isNull()
    w.close()
