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


def turning(w_wait, w_turn, face_conf=0.9):
    """Shoulders w_wait apart while she waits (frames < 25) and w_turn apart once turned."""
    kp, cf = body(shoulder_w=w_wait, face_conf=face_conf)
    k2, _ = body(shoulder_w=w_turn, face_conf=face_conf)
    kp[25:] = k2[25:]
    return kp, cf


def test_camera_view_side_back_front():
    kp, cf = turning(8, 100)                           # side: narrow waiting, wide when turned
    assert practice.camera_view(kp, cf, SK, 10, 40, FPS, 30) == "lateral"
    kp, cf = turning(100, 15, face_conf=0.1)           # behind: wide waiting, narrow when turned
    assert practice.camera_view(kp, cf, SK, 10, 40, FPS, 30) == "trasera"
    kp, cf = turning(100, 15, face_conf=0.9)
    assert practice.camera_view(kp, cf, SK, 10, 40, FPS, 30) == "frontal"
    kp, cf = turning(8, 10)                            # narrow all along: an angled camera, never "side"
    assert practice.camera_view(kp, cf, SK, 10, 40, FPS, 30) == "diagonal"
    kp, cf = turning(70, 70)
    assert practice.camera_view(kp, cf, SK, None, 40, FPS) == "diagonal"
    kp[:] = np.nan                                     # player not seen: never a confident view
    assert practice.camera_view(kp, cf, SK, 10, 40, FPS, 30) == "diagonal"


def test_implausible_values_are_named():
    assert practice.implausible({"elbow_impact_deg": 23.7, "swing_angle_deg": 30.0, "racket_drop_below_contact_cm": 140}) == \
        ["elbow_impact_deg", "racket_drop_below_contact_cm"]
    assert practice.implausible({"elbow_impact_deg": 140.0}) == []


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


def test_exam_needs_min_n_and_decides():
    from tennisbio.exam import CONFIRMS, FEW, REFUTES, UNDECIDABLE, claims

    v = {"class.swing": "liftado (de abajo arriba)", "stroke.swing_low_to_high": 40.0, "stroke.loaded_vs_bounce": 0.05,
         "class.finish": "sobre el hombro", "class.takeback": "amplia"}
    got = {c[0]: c[2] for c in claims([v] * 12, 12)}
    assert got["R1"] == CONFIRMS and got["R10"] == CONFIRMS and got["R17"] == CONFIRMS and got["R18"] == REFUTES
    assert got["R2"] == FEW and got["R16"] == UNDECIDABLE         # no data / not visible from TV: never confirmed
    assert {c[0]: c[2] for c in claims([v] * 5, 12)}["R1"] == FEW


def test_front_head_towards_contact():
    kp, cf = body(shoulder_w=100)
    i = 40
    kp[:, SK["left_ear"]], kp[:, SK["right_ear"]] = (320, 120), (280, 120)
    kp[i, SK["dom_wrist"]] = (150, 300)                # right hand, seen from the front: image-left
    kp[i, SK["nose"]] = (285, 125)                     # nose towards the hand
    cf[:, [SK["left_ear"], SK["right_ear"]]] = 0.9
    assert practice.front_metrics(kp, cf, SK, i)["head_to_contact_idx"] == 0.75
    kp[i, SK["nose"]] = (315, 125)
    assert practice.front_metrics(kp, cf, SK, i)["head_to_contact_idx"] == -0.75
    cf[i, SK["left_ear"]] = 0.1
    assert practice.front_metrics(kp, cf, SK, i) == {}


def test_faces_camera_by_the_face():
    kp, cf = body(face_conf=0.9)
    assert practice.faces_camera(cf, SK)
    kp, cf = body(face_conf=0.1)                     # from behind: no face
    assert not practice.faces_camera(cf, SK)
    cf[:] = 0.0                                      # nobody seen: never decided
    assert not practice.faces_camera(cf, SK)


def _k3(wrist_xyz, ppm=100.0):
    """133 RTMW3D keypoints of a standing player 1.84 m tall (crop px, y down; z in metres)."""
    k = np.zeros((133, 3))
    J = practice._J
    pts = {"nose": (0, -0.85, 0), "left_shoulder": (-0.2, -0.65, 0), "right_shoulder": (0.2, -0.65, 0),
           "right_elbow": (0.35, -0.4, 0.2), "left_hip": (-0.15, 0, 0), "right_hip": (0.15, 0, 0),
           "right_knee": (0.15, 0.45, 0), "left_knee": (-0.15, 0.45, 0),
           "left_ankle": (-0.15, 0.861, 0), "right_ankle": (0.15, 0.861, 0)}     # nose → ankle = 0.93 × 1.84 m
    pts["right_wrist"] = wrist_xyz
    for n, (x, y, z) in pts.items():
        k[J[n]] = (x * ppm, y * ppm, z)
    return k, np.full(133, 0.9)


def test_metrics_3d_in_her_body_frame():
    # the hand travels forward along the depth axis (towards the camera's far side) and up, then
    # meets the ball 0.37 m (20 % of 1.84 m) in front of the hips: a diagonal or frontal camera
    pre, imp = _k3((0.4, -0.2, -0.1)), _k3((0.4, -0.3, 0.37))
    m = practice.metrics_3d({"pre": pre, "impact": imp, "loaded": imp}, "right", 1.84)
    assert abs(m["contact_in_front_3d_pct"] - 20) < 1
    assert 10 < m["swing_angle_3d_deg"] < 20                 # 0.1 m up over 0.47 m forward
    assert abs(m["trunk_lean_impact_3d_deg"]) < 1
    assert "elbow_impact_3d_deg" in m and "back_knee_loaded_3d_deg" in m
    assert practice.metrics_3d({"pre": imp, "impact": imp}, "right", 1.84) == {}       # hand not moving
    low = _k3((0.4, -0.3, 0.37)); low[1][practice._J["right_wrist"]] = 0.1
    assert practice.metrics_3d({"pre": pre, "impact": low}, "right", 1.84) == {}       # wrist not seen


def test_clip_without_anybody_is_not_an_error():
    from tennisbio.clip_pipeline import pick_initial
    assert pick_initial([np.zeros((0, 4))] * 5) == (None, None)
