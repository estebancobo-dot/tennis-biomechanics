"""Main camera from the court's lines (scenes v3). Synthetic broadcast frames drawn at 960×540 and
reduced to 160×90 as the stage reads them (the lines end up thinner than a pixel): the main camera
(court seen from behind, blue court in a green surround, white lines) against what the colour rule
took for it at the US Open (close-up in front of a blue wall, side view of the wall and the floor,
crowd), plus the rules over shots: views without visible lines, missed cuts, and broadcasts where
the lines are never seen (the colour rule stays)."""
import cv2
import numpy as np

from tennisbio.scenes import (Shot, analyse_video, court_line_evidence, main_camera_from_lines,
                              view_thumb)

W, H = 960, 540
BLUE, GREEN, NAVY, WHITE = (150, 95, 45), (70, 120, 60), (110, 50, 20), (235, 235, 235)


def small(img):
    return cv2.resize(img, (160, 90), interpolation=cv2.INTER_AREA)


def court_view(dx=0, lines=True, player=(480, 420), seed=0):
    """Main camera: stands and wall at the top, the court as a trapezoid, players small."""
    rng = np.random.default_rng(seed)
    img = np.full((H, W, 3), GREEN, np.uint8)
    img[:110] = rng.integers(40, 220, (110, W, 3), dtype=np.uint8)            # crowd
    img[95:130] = NAVY                                                        # wall
    far_l, far_r, near_l, near_r = (330 + dx, 160), (630 + dx, 160), (150 + dx, 470), (810 + dx, 470)
    cv2.fillPoly(img, [np.array([far_l, far_r, near_r, near_l], np.int32)], BLUE)
    if lines:
        def along(a, b, t):
            return int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t)
        cv2.line(img, far_l, near_l, WHITE, 4)                                # sidelines
        cv2.line(img, far_r, near_r, WHITE, 4)
        cv2.line(img, far_l, far_r, WHITE, 3)                                 # far baseline
        cv2.line(img, near_l, near_r, WHITE, 5)                               # near baseline
        for t in (0.25, 0.72):                                                # service lines
            cv2.line(img, along(far_l, near_l, t), along(far_r, near_r, t), WHITE, 4)
        cv2.line(img, along(far_l, far_r, 0.5), along(near_l, near_r, 0.5), WHITE, 3)
        cv2.line(img, along(far_l, near_l, 0.45), along(far_r, near_r, 0.45), (200, 200, 200), 6)   # net
    x, y = player
    cv2.rectangle(img, (x + dx - 12, y - 70), (x + dx + 12, y), (40, 200, 230), -1)                 # player
    cv2.rectangle(img, (60, 450), (330, 500), (60, 30, 20), -1)                                      # scoreboard
    return small(img)


def wall_closeup(seed=0):
    """Close-up of a player in front of the blue wall with big white letters (US Open)."""
    rng = np.random.default_rng(seed)
    img = np.full((H, W, 3), NAVY, np.uint8)
    for k in range(6):                                                        # sponsor letters
        x = 80 + 70 * k
        cv2.putText(img, "USOPEN"[k], (x, 330), cv2.FONT_HERSHEY_SIMPLEX, 4, WHITE, 18)
    cv2.ellipse(img, (650, 300), (150, 260), 0, 0, 360, (90, 140, 200), -1)  # skin / body
    cv2.rectangle(img, (560, 330), (740, 540), (40, 200, 230), -1)           # shirt
    img[500:] = GREEN
    img += rng.integers(0, 6, img.shape, dtype=np.uint8)
    return small(img)


def side_view(seed=0):
    """Side camera at court level: wall with logos, the floor and one court line, a player."""
    rng = np.random.default_rng(seed)
    img = np.full((H, W, 3), NAVY, np.uint8)
    img[:120] = rng.integers(40, 220, (120, W, 3), dtype=np.uint8)
    cv2.putText(img, "Emirates", (60, 250), cv2.FONT_HERSHEY_SIMPLEX, 2.5, WHITE, 8)
    cv2.putText(img, "J.P.Morgan", (520, 250), cv2.FONT_HERSHEY_SIMPLEX, 2.5, WHITE, 8)
    img[400:] = GREEN
    img[470:] = BLUE
    cv2.line(img, (0, 470), (W, 455), WHITE, 6)                               # the line on the floor
    cv2.rectangle(img, (440, 150), (520, 460), (40, 120, 230), -1)           # player
    return small(img)


def crowd(seed=0):
    rng = np.random.default_rng(seed)
    img = rng.integers(0, 255, (H // 20, W // 20, 3), dtype=np.uint8)
    img = cv2.resize(img, (W, H), interpolation=cv2.INTER_NEAREST)            # faces, shirts, seats
    for k in range(0, H, 60):
        cv2.line(img, (0, k), (W, k + 20), (200, 200, 200), 3)                # rails
    return small(img)


def test_line_evidence_tells_the_main_camera_from_what_colour_confused():
    assert all(court_line_evidence(court_view(dx, seed=s)) == 2 for dx in (-60, 0, 60) for s in range(3))
    for f in (wall_closeup(), side_view(), crowd(), crowd(1), court_view(lines=False)):
        assert court_line_evidence(f) == 0
    # a flat or uniform frame (fade to black, graphics) has no lines either
    assert court_line_evidence(np.zeros((90, 160, 3), np.uint8)) == 0
    assert court_line_evidence(np.full((90, 160, 3), 255, np.uint8)) == 0


def _shots(parts):
    frames, shots = [], []
    for fr in parts:
        shots.append(Shot(len(frames), len(frames) + len(fr), True, 0.5))      # colour rule: all main
        frames += fr
    ev = np.array([court_line_evidence(f) for f in frames])
    th = np.stack([view_thumb(f) for f in frames])
    return shots, ev, th


def test_shots_main_camera_by_lines_and_by_the_same_view():
    parts = [[court_view(k % 3, seed=k) for k in range(40)],                  # rally
             [wall_closeup(k) for k in range(30)],                            # close-up (blue wall)
             [side_view(k) for k in range(30)],                               # side view
             [crowd(k) for k in range(20)],                                   # crowd
             [court_view(k % 3, lines=False, seed=k) for k in range(30)],     # same view, lines hidden
             [court_view(k % 3, seed=k) for k in range(25)] + [wall_closeup(k) for k in range(35)]]   # missed cut
    shots, ev, th = _shots(parts)
    info = main_camera_from_lines(shots, ev, th, fps=10)
    assert info["main_rule"] == "lines" and info["views"] >= 1
    assert [s.main_camera for s in shots] == [True, False, False, False, True, True]
    assert shots[0].court_lines == 1.0 and shots[4].main_view == 1.0
    assert info["main_frames_colour"] == len(ev) and info["main_frames_lines"] == 40 + 30 + 60


def test_a_stray_frame_does_not_make_a_shot_main_camera():
    parts = [[court_view(seed=k) for k in range(30)],
             [wall_closeup(k) for k in range(59)] + [court_view(seed=99)]]   # one court frame in 60 (a flash)
    shots, ev, th = _shots(parts)
    main_camera_from_lines(shots, ev, th, fps=10)
    assert [s.main_camera for s in shots] == [True, False]


def test_without_visible_lines_the_colour_rule_stays():
    # a broadcast whose main camera shows no lines at 160 px (low camera, faint lines): nothing changes
    parts = [[court_view(lines=False, seed=k) for k in range(40)], [wall_closeup(k) for k in range(20)]]
    shots, ev, th = _shots(parts)
    shots[1].main_camera = False
    info = main_camera_from_lines(shots, ev, th, fps=10)
    assert info["main_rule"] == "colour" and [s.main_camera for s in shots] == [True, False]


def test_short_and_empty_shots():
    parts = [[court_view()], [wall_closeup()], [court_view(seed=k) for k in range(30)]]
    shots, ev, th = _shots(parts)
    main_camera_from_lines(shots, ev, th, fps=10)
    assert [s.main_camera for s in shots] == [True, False, True]   # a 1-frame shot: its frame decides
    assert main_camera_from_lines([], np.zeros(0), np.zeros((0, 9, 16, 3), np.uint8), fps=10)["main_rule"] == "colour"


def test_analyse_video_uses_the_lines():
    frames = [court_view(k % 3, seed=k) for k in range(40)] + [wall_closeup(k) for k in range(30)] + \
             [court_view(k % 3, seed=k) for k in range(40)]
    info = {}
    shots, mask = analyse_video(frames, fps=10, info=info)
    assert info["main_rule"] == "lines"
    assert mask[:38].all() and not mask[42:68].any() and mask[72:].all()
    info = {}
    _, mask_colour = analyse_video(frames, fps=10, info=info, lines=False)
    assert info["main_rule"] == "colour"
