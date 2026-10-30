"""Mirror dance: joints follow the pose (mirrored), the character switches on raised hands, painting and the window."""
import numpy as np
from PySide6.QtCore import QPointF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from src.hand_tracker import Detection
from src.pose_tracker import L_WRIST, NOSE, R_WRIST, PoseTracker
from src.dance_figure import CHARACTERS
from src.projector_dance import ProjectorDance


def make():
    return ProjectorDance((1280, 720), (1280, 720), False, False)


def pose(**moves) -> np.ndarray:
    """A standing figure in the middle of the frame; `moves` overrides landmark index -> (x, y)."""
    p = np.zeros((33, 3), dtype=np.float32)
    p[:, 2] = 1.0
    base = {0: (0.5, 0.2), 11: (0.45, 0.35), 12: (0.55, 0.35), 13: (0.4, 0.45), 14: (0.6, 0.45), 15: (0.38, 0.55),
            16: (0.62, 0.55), 23: (0.47, 0.6), 24: (0.53, 0.6), 25: (0.47, 0.75), 26: (0.53, 0.75), 27: (0.47, 0.9),
            28: (0.53, 0.9)}
    base.update({int(k[1:]): v for k, v in moves.items()})
    for i, (x, y) in base.items():
        p[i, :2] = (x, y)
    return p


def feed(app, p, now):
    app.on_detection(Detection(None, 0, 1.0, pose=p), now)


def test_the_character_mirrors_the_person():
    app = make()
    feed(app, pose(w16=(0.8, 0.5)), 1.0)      # the person's right wrist, far right in the camera image
    assert app.visible
    assert app.joints["r_wrist"][0] < 640      # shows on the left of the canvas, like a mirror


def test_a_joint_that_is_not_visible_keeps_its_last_position():
    app = make()
    feed(app, pose(), 1.0)
    before = app.joints["l_wrist"]
    p = pose(w15=(0.1, 0.1))
    p[L_WRIST, 2] = 0.1
    feed(app, p, 1.1)
    assert app.joints["l_wrist"] == before


def test_raising_both_hands_for_a_second_changes_the_character_once():
    app = make()
    up = pose(w15=(0.4, 0.05), w16=(0.6, 0.05))
    for i in range(40):
        feed(app, up, 1.0 + i * 0.05)
    assert app.character == 1
    feed(app, pose(), 4.0)
    assert app.progress == 0.0 and app.character == 1


def test_the_character_leaves_when_nobody_is_seen():
    app = make()
    feed(app, pose(), 1.0)
    app.on_detection(Detection(None, 0, 1.0), 3.0)
    assert not app.visible and not app.joints


def test_a_lone_hand_is_not_a_person():
    app = make()
    p = pose()
    p[[11, 12, 23, 24, 25, 26, 27, 28], 2] = 0.2      # only the hand-ish joints look visible
    feed(app, p, 1.0)
    assert not app.visible
    tiny = pose(w11=(0.49, 0.35), w12=(0.51, 0.35))     # shoulders 2 % of the frame apart
    feed(app, tiny, 1.1)
    assert not app.visible


def test_every_character_paints_something():
    QApplication.instance() or QApplication([])
    app = make()
    for character in range(len(CHARACTERS)):
        app.character = character
        feed(app, pose(), 1.0 + character)
        img = QImage(1280, 720, QImage.Format_RGB32)
        p = QPainter(img)
        app.paint(p, lambda pt: QPointF(*pt), 1.0)
        p.end()
        assert img.pixelColor(640, 300).rgb() != img.pixelColor(10, 700).rgb()    # body over the dark background


def test_no_body_in_a_blank_frame():
    assert PoseTracker().detect(np.zeros((720, 1280, 3), dtype=np.uint8)).pose is None


def test_main_window_offers_the_dance():
    QApplication.instance() or QApplication([])
    from src.ui import MainWindow
    win = MainWindow()
    win.app_box.setCurrentIndex(8)
    win._on_app_selected(8)
    assert win.projector_app is win.dance and win.proj_ctl.isVisibleTo(win)
    assert "no calibration" in win.mapping_label.text() or win._update_diagnostics() is None
