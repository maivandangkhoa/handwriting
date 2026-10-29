"""Piano: key geometry, synthesised tones, fingertip -> note, and the projector app end to end."""
import cv2
import numpy as np

from src import config
from src.hand_tracker import Detection
from src.piano_layout import BLACK_H, KEYS, TOP, WHITE_COUNT, WHITE_W, frequency, key_at
from src.piano_mode import ProjectorPiano
from src.piano_session import PianoSession
from src.piano_sound import RATE, render, wav_bytes

CANVAS = (config.CANVAS_WIDTH, config.CANVAS_HEIGHT)
SEEN = np.float32([(200, 100), (1090, 70), (1150, 650), (130, 620)])
H = cv2.getPerspectiveTransform(np.float32([(0, 0), (CANVAS[0], 0), CANVAS, (0, CANVAS[1])]), SEEN)
DT = 1 / 30


def by_midi(m):
    return next(k for k in KEYS if k.midi == m)


def centre(m, low=False):
    k = by_midi(m)
    return (k.x + k.w / 2, k.y + (k.h * 0.85 if low else k.h / 2))


# ---- layout -------------------------------------------------------------------------------
def test_two_octaves_with_the_right_number_of_keys():
    assert len([k for k in KEYS if not k.black]) == WHITE_COUNT == 14
    assert len([k for k in KEYS if k.black]) == 10
    assert min(k.midi for k in KEYS) == 60 and max(k.midi for k in KEYS) == 83
    assert by_midi(60).name == "C4" and by_midi(61).name == "C#4" and by_midi(81).name == "A5"


def test_keys_fit_on_the_canvas_and_white_keys_do_not_overlap():
    assert all(0 <= k.x and k.x + k.w <= CANVAS[0] and 0 <= k.y and k.y + k.h <= CANVAS[1] for k in KEYS)
    whites = sorted((k for k in KEYS if not k.black), key=lambda k: k.x)
    assert all(abs(a.x + a.w - b.x) < 1e-6 for a, b in zip(whites, whites[1:]))


def test_black_key_wins_over_the_white_keys_behind_it():
    black = by_midi(61)
    assert key_at(black.x + black.w / 2, TOP + 10).midi == 61
    assert key_at(black.x + black.w / 2, TOP + BLACK_H + 20).midi in (60, 62)      # below the black key: a white one
    assert key_at(5, 5) is None


# ---- sound --------------------------------------------------------------------------------
def test_rendered_note_has_the_right_pitch_and_stays_in_range():
    samples = render(69)                                                           # A4 = 440 Hz
    assert np.max(np.abs(samples)) <= 1.0
    spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))
    assert abs(np.fft.rfftfreq(len(samples), 1 / RATE)[int(np.argmax(spectrum))] - 440) < 3
    assert abs(frequency(60) - 261.63) < 0.01


def test_a_note_dies_away_and_wav_is_valid():
    samples = render(60)
    n = len(samples) // 10
    assert np.abs(samples[:n]).max() > 4 * np.abs(samples[-n:]).max()
    assert wav_bytes(samples)[:4] == b"RIFF"


# ---- fingertip -> note --------------------------------------------------------------------
def play(session, fid, x0, y0, x1, y1, t0=0.0, rest=0.4):
    """Finger rests at (x0,y0), travels to (x1,y1) and stays there; returns the keys struck."""
    fired, t = [], t0
    for _ in range(int(0.5 / DT)):
        session.update({fid: (x0, y0)}, t)
        t += DT
    for i in range(1, 7):
        fired += session.update({fid: (x0 + (x1 - x0) * i / 6, y0 + (y1 - y0) * i / 6)}, t)
        t += DT
    for _ in range(int(rest / DT)):
        fired += session.update({fid: (x1, y1)}, t)
        t += DT
    return fired


def test_finger_travelling_onto_a_key_and_pausing_strikes_it_once():
    s = PianoSession()
    x, y = centre(64)
    fired = play(s, "h0-index", x - 2 * WHITE_W, y, x, y)
    assert [k.midi for k in fired] == [64]


def test_resting_fingers_never_sound():
    s = PianoSession()
    t = 0.0
    for _ in range(90):
        assert s.update({"a": centre(60), "b": centre(64)}, t) == []
        t += DT


def test_two_fingers_strike_a_chord():
    s = PianoSession()
    t = 0.0
    start = {"a": (centre(60)[0] - 200, centre(60)[1]), "b": (centre(67)[0] - 200, centre(67)[1])}
    for _ in range(15):
        s.update(start, t)
        t += DT
    fired = []
    for i in range(1, 7):
        fired += s.update({"a": (start["a"][0] + 200 * i / 6, start["a"][1]), "b": (start["b"][0] + 200 * i / 6, start["b"][1])}, t)
        t += DT
    for _ in range(12):
        fired += s.update({"a": centre(60), "b": centre(67)}, t)
        t += DT
    assert sorted(k.midi for k in fired) == [60, 67]


def test_struck_key_glows_briefly():
    s = PianoSession()
    x, y = centre(62)
    play(s, "f", x - WHITE_W * 2, y, x, y)
    assert s.last.midi == 62 and 62 in s.lit(s.struck[62] + 0.1) and 62 not in s.lit(s.struck[62] + 1.0)


# ---- the projector app ----------------------------------------------------------------------
class Recorder:
    def __init__(self):
        self.notes = []

    def play(self, midi):
        self.notes.append(midi)


def camera_frame(app, seed):
    img = np.zeros((CANVAS[1], CANVAS[0], 3), np.uint8)
    if app.pattern == "markers":
        for x, y in app.markers:
            cv2.circle(img, (int(x), int(y)), int(app.marker_radius), (255, 255, 255), -1, cv2.LINE_AA)
    view = cv2.warpPerspective(img, H, (1280, 720)).astype(np.float32) * 0.8 + 40
    return np.clip(view + np.random.default_rng(seed).normal(0, 2, view.shape), 0, 255).astype(np.uint8)


def hand_with_index_at(canvas_pt):
    tip = cv2.perspectiveTransform(np.float32([[canvas_pt]]), H)[0, 0]
    lm = np.tile(tip + (0, -1500), (21, 1)).astype(np.float32)     # the rest of the hand is far off the keyboard
    lm[8] = tip
    return lm


def calibrated_piano():
    rec = Recorder()
    app = ProjectorPiano((1280, 720), CANVAS, False, False, player=rec)
    app.start_calibration(0.0)
    t = 0.0
    for i in range(int(config.PROJECTOR_PHASE_S / DT) * 2 + 4):
        app.on_detection(Detection(None, 0, 0.0, frame=camera_frame(app, i)), t)
        t += DT
    assert app.playing, app.message
    return app, rec, t


def test_calibration_then_a_tap_on_a_key_plays_that_note():
    app, rec, t = calibrated_piano()
    x, y = centre(67)
    for i in range(int(0.5 / DT)):                                  # finger hangs back, then moves onto the key
        lm = hand_with_index_at((x - 2 * WHITE_W, y))
        app.on_detection(Detection(lm, 1, 0.0, [lm], frame=camera_frame(app, 100 + i)), t)
        t += DT
    for i in range(1, 7):
        lm = hand_with_index_at((x - 2 * WHITE_W + 2 * WHITE_W * i / 6, y))
        app.on_detection(Detection(lm, 1, 0.0, [lm], frame=camera_frame(app, 200 + i)), t)
        t += DT
    for i in range(12):
        lm = hand_with_index_at((x, y))
        app.on_detection(Detection(lm, 1, 0.0, [lm], frame=camera_frame(app, 300 + i)), t)
        t += DT
    assert rec.notes == [67], (rec.notes, app.stats_text())


def test_without_a_player_the_piano_still_tracks_and_does_not_fail():
    app = ProjectorPiano((1280, 720), CANVAS, False, False)
    app.start_calibration(0.0)
    t = 0.0
    for i in range(int(config.PROJECTOR_PHASE_S / DT) * 2 + 4):
        app.on_detection(Detection(None, 0, 0.0, frame=camera_frame(app, i)), t)
        t += DT
    x, y = centre(64)
    for k in range(40):
        lm = hand_with_index_at((x - (200 if k < 15 else 0), y))
        app.on_detection(Detection(lm, 1, 0.0, [lm], frame=camera_frame(app, 500 + k)), t)
        t += DT
    assert app.player is None and app.session.count >= 1
