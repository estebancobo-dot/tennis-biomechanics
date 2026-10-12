import numpy as np

from tennisbio import practice
from tennisbio.skeleton import Skeleton

SK = Skeleton("coco17", "right")
FPS = 30.0
H = 400.0          # body height in px


def body(T=60, shoulder_w=100.0, face_conf=0.9):
    """A standing player, image px: shoulders shoulder_w apart (0 from the side), feet at y=500."""
    kp = np.full((T, 17, 2), np.nan)
    cf = np.full((T, 17), 0.9)
    pts = {"nose": (300, 120), "left_eye": (295, 115), "right_eye": (305, 115),
           "left_shoulder": (300 + shoulder_w / 2, 170), "right_shoulder": (300 - shoulder_w / 2, 170),
           "left_elbow": (300 + shoulder_w / 2, 240), "right_elbow": (300 - shoulder_w / 2, 240),
           "left_wrist": (300 + shoulder_w / 2, 300), "right_wrist": (300 - shoulder_w / 2, 300),
           "left_hip": (300 + shoulder_w / 3, 310), "right_hip": (300 - shoulder_w / 3, 310),
           "left_knee": (300 + shoulder_w / 3, 410), "right_knee": (300 - shoulder_w / 3, 410),
           "left_ankle": (300 + shoulder_w / 3, 500), "right_ankle": (300 - shoulder_w / 3, 500)}
    for n, p in pts.items():
        kp[:, SK[n]] = p
    cf[:, [SK["nose"], SK["left_eye"], SK["right_eye"]]] = face_conf
    return kp, cf


def test_camera_view_side_back_front():
    kp, cf = body(shoulder_w=8)
    assert practice.camera_view(kp, cf, SK, 10, 40, FPS) == "lateral"
    kp, cf = body(shoulder_w=100, face_conf=0.1)
    assert practice.camera_view(kp, cf, SK, 10, 40, FPS) == "trasera"
    kp, cf = body(shoulder_w=100, face_conf=0.9)
    assert practice.camera_view(kp, cf, SK, 10, 40, FPS) == "frontal"
    kp, cf = body(shoulder_w=70)
    assert practice.camera_view(kp, cf, SK, None, 40, FPS) == "diagonal"
    kp[:] = np.nan                                     # player not seen: never a confident view
    assert practice.camera_view(kp, cf, SK, 10, 40, FPS) == "diagonal"


def test_side_metrics_forward_low_to_high_both_directions():
    for direction in (1, -1):
        kp, cf = body(shoulder_w=8)
        i = 40
        w = SK["dom_wrist"]
        # the hand rises 30° while moving forward and meets the ball 80 px (20 % of H) in front of the hips
        for f in range(i - 10, i + 3):
            dx = (f - i) * 10.0
            kp[f, w] = (300 + direction * (80 + dx), 300 - dx * np.tan(np.radians(30)))
        m = practice.side_metrics(kp, cf, SK, FPS, i, {"loaded": 20, "acceleration": 32}, H, 1.84)
        assert abs(m["contact_in_front_pct"] - 20) < 1
        assert abs(m["swing_angle_deg"] - 30) < 2
        assert abs(m["trunk_lean_impact_deg"]) < 1
        assert abs(m["back_knee_loaded_deg"] - 180) < 1


def test_side_metrics_racket_drop_and_lag():
    kp, cf = body(shoulder_w=8)
    i = 40
    kp[:, SK["dom_elbow"]] = (300, 240)
    kp[:, SK["dom_wrist"]] = (360, 240)                # forearm horizontal, pointing forward
    heads = {f: (360, 240 + 60) for f in range(25, 40)}            # racket head 60 px below the hand
    heads[32] = (360, 240 + 100)                                    # lowest: 100 px under the contact height
    m = practice.side_metrics(kp, cf, SK, FPS, i, {"loaded": 20, "acceleration": 32}, H, 1.84, heads)
    assert abs(m["racket_drop_below_contact_cm"] - 100 / H * 184) < 0.5
    assert abs(m["lag_accel_deg"] - 90) < 1                         # racket at right angles to the forearm


def test_side_metrics_skips_hidden_joints():
    kp, cf = body(shoulder_w=8)
    cf[:, SK["dom_elbow"]] = 0.1                       # arm hidden behind the body (camera on her other side)
    m = practice.side_metrics(kp, cf, SK, FPS, 40, {"loaded": None}, H, 1.84)
    assert "elbow_impact_deg" not in m and "back_knee_loaded_deg" not in m
    assert "lag_accel_deg" not in m


def test_summarize_needs_min_n_and_only_side_forehands():
    st = [{"view": "lateral", "stroke": "forehand", "metrics": {"contact_in_front_pct": 20.0 + k}} for k in range(practice.MIN_N)]
    st += [{"view": "trasera", "stroke": "forehand", "metrics": {"contact_in_front_pct": 99.0}}] * 5
    st += [{"view": "lateral", "stroke": "backhand", "metrics": {"contact_in_front_pct": 99.0}}] * 5
    s = practice.summarize(st)
    assert s["contact_in_front_pct"]["n"] == practice.MIN_N
    assert abs(s["contact_in_front_pct"]["median"] - 25.5) < 0.01
    s = practice.summarize(st[:practice.MIN_N - 1])
    assert "median" not in s["contact_in_front_pct"] and s["contact_in_front_pct"]["n"] == practice.MIN_N - 1
    assert practice.summarize([])["swing_angle_deg"]["n"] == 0
    assert practice.views_count(st) == {"lateral": 17, "trasera": 5}


def test_audit_combinations_flag_hidden_measure_and_count_few():
    from tennisbio.audit import _combination_items
    from tennisbio.explain import LINES
    from tennisbio.model import FACTORS

    key = LINES["impact"][0][0]
    vals = [{"class.ball_speed": "lenta", key: 1.0} for _ in range(3)] + [{"class.ball_speed": "media", key: 1.0}]
    view = {"ball_speed|lenta": {"cards": [{"phase": f"p{i}", "lines": [{"key": "otra"}]} for i in range(8)], "strokes": ["a"]}}
    it = {i["name"].split(":")[0]: i for i in _combination_items({"variants": view}, vals, 3, FACTORS)}["Bola rápida / lenta"]
    assert it["status"] == "falta" and key in it["detail"]          # enough strokes, measure not shown
    view["ball_speed|lenta"]["cards"][0]["lines"].append({"key": key})
    it = {i["name"].split(":")[0]: i for i in _combination_items({"variants": view}, vals, 3, FACTORS)}["Bola rápida / lenta"]
    assert it["status"] == "ok" and it["shown"] == 1 and "media 1" in it["detail"]
