"""Animal colouring: paint stays inside the shape the brush is over; the palette picks colours and the next animal."""
from PySide6.QtWidgets import QApplication

from src.drawing import DrawingState
from src.projector_animals import KIDS_COLORS, ProjectorAnimals

CANVAS = (1280, 720)


def make():
    state = DrawingState(None)
    return state, ProjectorAnimals(state, (1280, 720), CANVAS, False, False)


def test_a_stroke_belongs_to_the_topmost_shape_under_its_start():
    _, app = make()
    body = app._shape_at((690, 400))
    head = app._shape_at((690, 300))
    assert body is not None and head is not None and body != head
    assert app._shape_at((20, 20)) is None


def test_resting_on_a_swatch_selects_the_colour():
    state, app = make()
    r = app.swatch_rect(2)
    app.on_palette((r.center().x(), r.center().y()), 0.0)
    app.on_palette((r.center().x(), r.center().y()), 1.0)
    assert state.color == KIDS_COLORS[2]


def test_the_next_button_switches_animal_once_and_clears_the_paint():
    state, app = make()
    state.update((690, 400))
    r = app.swatch_rect(len(KIDS_COLORS)).center()
    for t in (0.0, 1.0, 2.0, 3.0):
        app.on_palette((r.x(), r.y()), t)
    assert app.name == "Fish" and state.strokes == []
    app.on_palette((600.0, 400.0), 4.0)
    for t in (5.0, 6.0, 7.0):
        app.on_palette((r.x(), r.y()), t)
    assert app.name == "Duck"


def test_paint_renders_and_clips_to_the_shape(tmp_path):
    from PySide6.QtGui import QImage, QPainter
    QApplication.instance() or QApplication([])
    state, app = make()
    state.color = (230, 50, 50)
    for x in range(600, 880, 10):
        state.update((float(x), 420.0))          # a sweep across the body, running out past the animal
    img = QImage(1280, 720, QImage.Format_RGB32)
    p = QPainter(img)
    app.paint(p, lambda pt: __import__("PySide6.QtCore", fromlist=["QPointF"]).QPointF(*pt), 1.0)
    p.end()
    inside, outside = img.pixelColor(690, 420), img.pixelColor(930, 420)
    assert inside.red() > 200 and inside.green() < 90
    assert not (outside.red() > 200 and outside.green() < 90)


def test_a_sweep_starting_outside_still_paints_where_it_enters_a_shape():
    state, app = make()
    for x in range(100, 700, 20):
        state.update((float(x), 420.0))          # starts on the bare paper left of the animal
    assert any(i is not None for i, _ in app._runs(state.strokes[0]))


def test_main_window_offers_the_animal_colouring():
    QApplication.instance() or QApplication([])
    from src.ui import MainWindow
    w = MainWindow()
    w._on_app_selected(7)
    assert w.projector_app is w.animals and w.canvas.projector is w.animals and w.state.color == KIDS_COLORS[0]
    w.canvas.resize(1280, 720)
    assert not w.canvas.grab().isNull()
    w.close()
