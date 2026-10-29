"""Air Drawing on a projector: the canvas is found from four discs, then camera points land on the canvas."""
import cv2
import numpy as np

from src import config
from src.drawing import DrawingState
from src.hand_tracker import Detection
from src.projector_draw import COLORS, PICK_S, ProjectorDraw

CANVAS = (config.CANVAS_WIDTH, config.CANVAS_HEIGHT)
SEEN = np.float32([(200, 100), (1090, 70), (1150, 650), (130, 620)])
H = cv2.getPerspectiveTransform(np.float32([(0, 0), (CANVAS[0], 0), CANVAS, (0, CANVAS[1])]), SEEN)
DT = 1 / 30


def camera_frame(app, seed):
    img = np.zeros((CANVAS[1], CANVAS[0], 3), np.uint8)
    if app.pattern == "markers":
        for x, y in app.markers:
            cv2.circle(img, (int(x), int(y)), int(app.marker_radius), (255, 255, 255), -1, cv2.LINE_AA)
    view = cv2.warpPerspective(img, H, (1280, 720)).astype(np.float32) * 0.8 + 40
    noise = np.random.default_rng(seed).normal(0, 2, view.shape)
    return np.clip(view + noise, 0, 255).astype(np.uint8)


def run(app, frames, t=0.0):
    for i in range(frames):
        app.on_detection(Detection(None, 0, 0.0, frame=camera_frame(app, i)), t)
        t += DT
    return t


def test_discs_are_inset_so_the_camera_needs_only_most_of_the_canvas():
    app = ProjectorDraw(DrawingState(), (1280, 720), CANVAS, False, False)
    xs = [x for x, _ in app.markers]
    assert min(xs) > 0.05 * CANVAS[0] and max(xs) < 0.95 * CANVAS[0]


def test_calibration_finds_the_canvas_and_maps_camera_points_onto_it():
    app = ProjectorDraw(DrawingState(), (1280, 720), CANVAS, False, False)
    t = 0.0
    app.start_calibration(t)
    run(app, int(config.PROJECTOR_PHASE_S / DT) * 2 + 4, t)
    assert app.drawing, app.message
    seen = cv2.perspectiveTransform(np.float32([[(900, 200)]]), H)[0, 0]
    mapped = app.mapper.map((float(seen[0]), float(seen[1])), clamp=False)
    assert np.hypot(mapped[0] - 900, mapped[1] - 200) < 3


def test_camera_orientation_change_drops_back_to_idle():
    app = ProjectorDraw(DrawingState(), (1280, 720), CANVAS, False, False)
    app.start_calibration(0.0)
    run(app, int(config.PROJECTOR_PHASE_S / DT) * 2 + 4)
    app.mapper.set_mirror(True)
    run(app, 1)
    assert not app.drawing and app.phase == "idle"


def test_a_stopped_camera_keeps_a_finished_calibration_but_ends_an_unfinished_one():
    app = ProjectorDraw(DrawingState(), (1280, 720), CANVAS, False, False)
    app.start_calibration(0.0)
    app.camera_stopped()
    assert app.phase == "idle"
    app.start_calibration(0.0)
    run(app, int(config.PROJECTOR_PHASE_S / DT) * 2 + 4)
    app.camera_stopped()
    assert app.drawing


def centre(app, i):
    r = app.swatch_rect(i)
    return (r.center().x(), r.center().y())


def test_resting_on_a_swatch_picks_its_colour_and_blocks_drawing():
    state = DrawingState()
    app = ProjectorDraw(state, (1280, 720), CANVAS, False, False)
    assert app.on_palette(centre(app, 2), 0.0)               # just arrived: over the palette, nothing picked
    assert state.color == COLORS[0]
    assert app.on_palette(centre(app, 2), PICK_S + 0.01)
    assert state.color == COLORS[2]


def test_sweeping_over_swatches_does_not_pick_and_leaving_the_palette_frees_the_pen():
    state = DrawingState()
    app = ProjectorDraw(state, (1280, 720), CANVAS, False, False)
    for i in range(len(COLORS)):                              # moving faster than PICK_S
        app.on_palette(centre(app, i), i * 0.1)
    assert state.color == COLORS[0]
    assert not app.on_palette((600, 360), 2.0) and app.resting_swatch is None
    assert not app.on_palette(None, 2.1)


def test_picking_ends_the_current_stroke_so_the_next_one_has_the_new_colour():
    state = DrawingState()
    app = ProjectorDraw(state, (1280, 720), CANVAS, False, False)
    state.update((600, 360))
    app.on_palette(centre(app, 5), 0.0)
    app.on_palette(centre(app, 5), PICK_S + 0.01)
    state.update((610, 360))
    assert [c for c in state.colors] == [COLORS[0], COLORS[5]]


def test_palette_swatches_stay_on_the_canvas_and_apart():
    app = ProjectorDraw(DrawingState(), (1280, 720), CANVAS, False, False)
    rects = [app.swatch_rect(i) for i in range(len(COLORS))]
    assert all(0 <= r.left() and r.right() <= CANVAS[0] and 0 <= r.top() and r.bottom() <= CANVAS[1] for r in rects)
    assert all(not a.intersects(b) for a, b in zip(rects, rects[1:]))
