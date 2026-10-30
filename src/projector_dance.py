"""Mirror dance: the camera watches up to three people and a cartoon character per person copies the moves.

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
MATCH_DIST = 0.25        # same person next frame if their hips moved less than this fraction of the canvas width


def is_person(pose) -> bool:
    """A real torso, not a lone hand (the model happily invents a body around one): head, shoulders and hips all
    clearly visible and shoulders wide enough."""
    if pose is None or any(pose[i, 2] < BODY_VISIBILITY for i in BODY_JOINTS):
        return False
    return abs(float(pose[L_SHOULDER, 0] - pose[R_SHOULDER, 0])) >= MIN_SHOULDERS

class Dancer:
    """One person on the stage: their own smoothed joints, wrist trails, character and raised-hands hold."""

    def __init__(self, character: int, clock):
        self.character = character
        self.joints: dict[str, tuple[float, float]] = {}
        self.trails = {"l_wrist": deque(maxlen=TRAIL_LEN), "r_wrist": deque(maxlen=TRAIL_LEN)}
        self.progress = 0.0           # 0..1 of the raised-hands hold (drawn as a bar)
        self.seen = 0.0
        self._raised_since: float | None = None
        self._switched = False
        self._filters = {k: OneEuroFilter2D(*config.DANCE_FILTER, clock=clock) for k in JOINTS}

    @property
    def name(self) -> str:
        return CHARACTERS[self.character]

    @property
    def x(self) -> float:
        """Where they stand on the canvas (hip centre), for telling people apart between frames."""
        return (self.joints["l_hip"][0] + self.joints["r_hip"][0]) / 2

    def update(self, points: dict[str, tuple[float, float, float]], now: float) -> None:
        """`points`: joint name -> (canvas x, canvas y, visibility)."""
        for name, (x, y, visibility) in points.items():
            if visibility >= MIN_VISIBILITY or name not in self.joints:
                self.joints[name] = self._filters[name].update((x, y))
        for name, trail in self.trails.items():
            if name in self.joints:
                trail.append(self.joints[name])
        self.seen = now

    def watch_raised_hands(self, now: float) -> bool:
        """True once, when both hands have been above the head for SWITCH_S."""
        j = self.joints
        up = all(k in j for k in ("l_wrist", "r_wrist", "nose")) and max(j["l_wrist"][1], j["r_wrist"][1]) < j["nose"][1]
        if not up:
            self._raised_since, self.progress, self._switched = None, 0.0, False
            return False
        if self._raised_since is None:
            self._raised_since = now
        self.progress = min((now - self._raised_since) / SWITCH_S, 1.0)
        if self.progress >= 1.0 and not self._switched:
            self._switched = True
            return True
        return False


class ProjectorDance(ProjectorSurface):
    paints_canvas = True

    def __init__(self, frame_size, canvas_size, mirror, flip_vertical):
        super().__init__(frame_size, canvas_size, mirror, flip_vertical)
        self.phase, self.message = "play", ""
        self.dancers: list[Dancer] = []
        self._preferred = 0           # the character the last person picked: where the next newcomer starts looking
        self._now = 0.0

    @property
    def visible(self) -> bool:
        return bool(self.dancers)

    @property
    def hint(self) -> str:
        return ("Raise both hands above your head for a second to change character" if self.visible else
                "Stand 2-4 m from the camera so it sees your whole body")

    def start_calibration(self, now: float | None = None) -> None:
        """Nothing to calibrate: the canvas simply shows the camera view."""

    def camera_stopped(self) -> None:
        self.dancers.clear()

    def _canvas_point(self, nx: float, ny: float) -> tuple[float, float]:
        w, h = self.canvas_size
        return (1.0 - nx) * w, (1.0 - ny if self.mapper.flip_vertical else ny) * h

    def _free_character(self, start: int) -> int:
        """The first character from `start` on that nobody else is using."""
        taken = {d.character for d in self.dancers}
        n = len(CHARACTERS)
        return next(((start + i) % n for i in range(n) if (start + i) % n not in taken), start % n)

    def _new_dancer(self) -> Dancer:
        return Dancer(self._free_character(self._preferred), lambda: self._now)

    def on_detection(self, det: Detection, now: float) -> None:
        self._now = now
        people = [pose for pose in det.poses if is_person(pose)]
        unclaimed = list(self.dancers)
        for pose in sorted(people, key=lambda q: float(q[L_HIP, 0] + q[R_HIP, 0])):
            points = {name: (*self._canvas_point(float(pose[i, 0]), float(pose[i, 1])), float(pose[i, 2]))
                      for name, i in JOINTS.items()}
            hip_x = (points["l_hip"][0] + points["r_hip"][0]) / 2
            near = min(unclaimed, key=lambda d: abs(d.x - hip_x), default=None)
            if near is not None and abs(near.x - hip_x) <= MATCH_DIST * self.canvas_size[0]:
                unclaimed.remove(near)
                dancer = near
            elif len(self.dancers) < config.DANCE_MAX_PEOPLE:
                dancer = self._new_dancer()
                self.dancers.append(dancer)
            else:
                continue
            dancer.update(points, now)
            if dancer.watch_raised_hands(now):
                dancer.character = self._preferred = self._free_character(dancer.character + 1)
        self.dancers = [d for d in self.dancers if now - d.seen < LOST_S]

    def stats_text(self) -> str:
        names = ", ".join(d.name for d in self.dancers) or "-"
        return f"characters   : {names}\npeople       : {len(self.dancers)}"

    def paint(self, p: QPainter, to_w, scale: float) -> None:
        w, h = self.canvas_size
        p.fillRect(QRectF(to_w((0, 0)), to_w((w, h))), BACKGROUND)
        p.save()
        p.translate(to_w((0, 0)))
        p.scale(scale, scale)
        for d in self.dancers:
            paint_trails(p, d.trails)
            paint_figure(p, d.joints, d.name, self._now)
            if d.progress > 0 and "nose" in d.joints:
                x, y = d.joints["nose"]
                p.fillRect(QRectF(x - 60, y - 90, 120 * d.progress, 10), QColor(60, 230, 90))
        p.restore()
        p.setPen(QColor(235, 235, 235))
        font = p.font()
        font.setPixelSize(int(26 * scale) + 4)
        p.setFont(font)
        p.drawText(to_w((30, 50)), self.hint)
