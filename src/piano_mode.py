"""Piano on a projector: the keyboard is projected, the camera watches the fingertips, struck keys sound.

Geometry calibration is ProjectorSurface's (four discs); after it, every fingertip of up to two hands feeds a
PianoSession and each struck key is handed to `player.play(midi)`.
"""
from PySide6.QtGui import QPainter

from .hand_slots import HandSlots
from .hand_tracker import Detection
from .piano_session import PianoSession
from .piano_view import paint_piano
from .projector_surface import ProjectorSurface

FINGERTIPS = {"thumb": 4, "index": 8, "middle": 12, "ring": 16, "pinky": 20}


class ProjectorPiano(ProjectorSurface):
    paints_canvas = True

    def __init__(self, frame_size: tuple[int, int], canvas_size: tuple[int, int], mirror: bool, flip_vertical: bool,
                 player=None):
        super().__init__(frame_size, canvas_size, mirror, flip_vertical)
        self.session = PianoSession()
        self.slots = HandSlots()
        self.player = player            # anything with play(midi); None = silent
        self.message = "Open the piano on the projector screen, then press Calibrate Projector."

    @property
    def playing(self) -> bool:
        return self.phase == "play" and self.mapper.calibrated

    @property
    def hint(self) -> str:
        return "" if self.session.count else "Move a fingertip onto a key and pause for a moment to play it"

    def _geometry_found(self) -> None:
        self.session.reset()
        self.slots.reset()
        self._enter("play", "")

    def _camera_lost(self) -> None:
        self.session.reset()
        self.slots.reset()

    def on_detection(self, det: Detection, now: float) -> None:
        if self.phase == "play" and not self.mapper.calibrated:
            self.phase, self.message = "idle", "Camera orientation changed: calibrate the projector again."
        if self.phase in ("dark", "markers"):
            if det.frame is not None:
                self._geometry_step(det.frame, now)
        elif self.phase == "play":
            self._play(det, now)

    def _play(self, det: Detection, now: float) -> None:
        points = {}
        mapped = [[self.mapper.map((float(x), float(y)), clamp=False) for x, y in hand] for hand in det.hands]
        wrists = [m[0] for m in mapped if m[0] is not None]
        ids = iter(self.slots.assign(wrists))     # hand identity from wrist continuity, not MediaPipe's label
        for hand in mapped:
            slot = next(ids) if hand[0] is not None else None
            if slot is None:
                continue
            for name, idx in FINGERTIPS.items():
                if hand[idx] is not None:
                    points[f"hand{slot}-{name}"] = hand[idx]
        for key in self.session.update(points, now):
            if self.player is not None:
                self.player.play(key.midi)

    def stats_text(self) -> str:
        last = self.session.last.name if self.session.last else "-"
        return f"notes played : {self.session.count}   last: {last}\nfingertips   : {len(self.session.fingertips)}"

    def paint(self, p: QPainter, to_w, scale: float) -> None:
        paint_piano(p, to_w, scale, self)
