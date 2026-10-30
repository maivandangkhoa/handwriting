"""Mirror dance: the camera watches one person's body and a cartoon character on the projector copies the moves.

No geometry calibration: the canvas shows what the camera sees (mirrored, like a mirror), so the character mirrors the
person. Raise both hands above the head for a second to change character.
"""
from collections import deque

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter

from . import config
from .dance_figure import BACKGROUND, CHARACTERS, paint_figure, paint_trails
from .filters import OneEuroFilter2D
from .hand_tracker import Detection
from .pose_tracker import (L_ANKLE, L_ELBOW, L_HIP, L_KNEE, L_SHOULDER, L_WRIST, NOSE, R_ANKLE, R_ELBOW, R_HIP, R_KNEE,
                           R_SHOULDER, R_WRIST)
from .projector_surface import ProjectorSurface

JOINTS = {"nose": NOSE, "l_shoulder": L_SHOULDER, "r_shoulder": R_SHOULDER, "l_elbow": L_ELBOW, "r_elbow": R_ELBOW,
          "l_wrist": L_WRIST, "r_wrist": R_WRIST, "l_hip": L_HIP, "r_hip": R_HIP, "l_knee": L_KNEE, "r_knee": R_KNEE,
          "l_ankle": L_ANKLE, "r_ankle": R_ANKLE}
MIN_VISIBILITY = 0.5     # a joint less visible than this keeps its last position
LOST_S = 1.0             # no body this long and the character leaves
SWITCH_S = 1.0           # both hands above the head this long: next character
TRAIL_LEN = 16
BODY_JOINTS = (NOSE, L_SHOULDER, R_SHOULDER, L_HIP, R_HIP)     # a person: head, both shoulders and both hips all seen
BODY_VISIBILITY = 0.6
MIN_SHOULDERS = 0.06     # shoulder width as a fraction of the frame width: smaller is a hand or a far-off blob


def is_person(pose) -> bool:
    """A real torso, not a lone hand (the model happily invents a body around one): head, shoulders and hips all
    clearly visible and shoulders wide enough."""
    if pose is None or any(pose[i, 2] < BODY_VISIBILITY for i in BODY_JOINTS):
        return False
    return abs(float(pose[L_SHOULDER, 0] - pose[R_SHOULDER, 0])) >= MIN_SHOULDERS


class ProjectorDance(ProjectorSurface):
    paints_canvas = True

    def __init__(self, frame_size, canvas_size, mirror, flip_vertical):
        super().__init__(frame_size, canvas_size, mirror, flip_vertical)
        self.phase, self.message = "play", ""
        self.character = 0
        self.joints: dict[str, tuple[float, float]] = {}
        self.trails = {"l_wrist": deque(maxlen=TRAIL_LEN), "r_wrist": deque(maxlen=TRAIL_LEN)}
        self.progress = 0.0           # 0..1 of the raised-hands hold (drawn as a bar)
        self._now = 0.0
        self._seen = -LOST_S
        self._raised_since: float | None = None
        self._switched = False
        self._filters = {k: OneEuroFilter2D(*config.DANCE_FILTER, clock=lambda: self._now) for k in JOINTS}

    @property
    def name(self) -> str:
        return CHARACTERS[self.character]

    @property
    def visible(self) -> bool:
        return self._now - self._seen < LOST_S

    @property
    def hint(self) -> str:
        return ("Raise both hands above your head for a second to change character" if self.visible else
                "Stand 2-4 m from the camera so it sees your whole body")

    def start_calibration(self, now: float | None = None) -> None:
        """Nothing to calibrate: the canvas simply shows the camera view."""

    def camera_stopped(self) -> None:
        self._forget()

    def _forget(self) -> None:
        self.joints.clear()
        for trail in self.trails.values():
            trail.clear()
        for f in self._filters.values():
            f.reset()
        self._raised_since, self.progress, self._seen = None, 0.0, self._now - LOST_S

    def _canvas_point(self, nx: float, ny: float) -> tuple[float, float]:
        w, h = self.canvas_size
        return (1.0 - nx) * w, (1.0 - ny if self.mapper.flip_vertical else ny) * h

    def on_detection(self, det: Detection, now: float) -> None:
        self._now = now
        if not is_person(det.pose):
            if not self.visible:
                self._forget()
            return
        self._seen = now
        for name, idx in JOINTS.items():
            x, y, visibility = det.pose[idx]
            if visibility >= MIN_VISIBILITY or name not in self.joints:
                self.joints[name] = self._filters[name].update(self._canvas_point(float(x), float(y)))
        for name, trail in self.trails.items():
            if name in self.joints:
                trail.append(self.joints[name])
        self._watch_raised_hands(now)

    def _watch_raised_hands(self, now: float) -> None:
        j = self.joints
        up = all(k in j for k in ("l_wrist", "r_wrist", "nose")) and max(j["l_wrist"][1], j["r_wrist"][1]) < j["nose"][1]
        if not up:
            self._raised_since, self.progress, self._switched = None, 0.0, False
            return
        if self._raised_since is None:
            self._raised_since = now
        self.progress = min((now - self._raised_since) / SWITCH_S, 1.0)
        if self.progress >= 1.0 and not self._switched:
            self._switched = True
            self.character = (self.character + 1) % len(CHARACTERS)

    def stats_text(self) -> str:
        return f"character    : {self.name}\nbody visible : {'yes' if self.visible else 'no'}"

    def paint(self, p: QPainter, to_w, scale: float) -> None:
        w, h = self.canvas_size
        p.fillRect(QRectF(to_w((0, 0)), to_w((w, h))), BACKGROUND)
        p.save()
        p.translate(to_w((0, 0)))
        p.scale(scale, scale)
        if self.visible:
            paint_trails(p, self.trails)
            paint_figure(p, self.joints, self.name, self._now)
        p.restore()
        p.setPen(QColor(235, 235, 235))
        font = p.font()
        font.setPixelSize(int(26 * scale) + 4)
        p.setFont(font)
        p.drawText(to_w((30, 50)), f"{self.name}: {self.hint}")
        if self.progress > 0:
            p.fillRect(QRectF(to_w((30, 66)), to_w((30 + 300 * self.progress, 76))), QColor(60, 230, 90))
