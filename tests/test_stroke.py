import numpy as np
import pytest

from tennisbio.impacts import fuse
from tennisbio.kinematics import body_height, clean, joint_angle, line_turn, to_body_frame
from tennisbio.phases import detect_phases
from tennisbio.racket import racket_from_polygon
from tennisbio.skeleton import Skeleton
from tennisbio.stroke_analysis import analyze_stroke
from tennisbio.tracking import track_target

FPS, IMPACT = 50, 50


def synthetic_forehand(T=90):
    """A right-handed forehand seen from behind with known timing (image px, y down).

    split step lands at t≈-0.80 s · takeback from -0.60 · loaded at -0.30 · wrist low point -0.12 ·
    contact 0.00 · finish +0.30 · first recovery step at +0.45.
    """
    sk = Skeleton("coco17", "right")
    t = (np.arange(T) - IMPACT) / FPS
    kp = np.zeros((T, 17, 2))
    turn = np.interp(t, [-1, -0.6, -0.3, 0, 1], [0, 0, 60, 0, 0])
    hturn = np.interp(t, [-1, -0.6, -0.3, 0, 1], [0, 0, 30, 0, 0])
    ws, wh = 40 * np.cos(np.radians(turn)), 25 * np.cos(np.radians(hturn))
    kp[:, sk["nose"]] = [200, 40]
    for n in ("left_eye", "right_eye", "left_ear", "right_ear"):
        kp[:, sk[n]] = [200, 35]
    kp[:, sk["left_shoulder"]] = np.c_[200 - ws, np.full(T, 90)]
    kp[:, sk["right_shoulder"]] = np.c_[200 + ws, np.full(T, 90)]
    kp[:, sk["left_hip"]] = np.c_[200 - wh, np.full(T, 230)]
    kp[:, sk["right_hip"]] = np.c_[200 + wh, np.full(T, 230)]
    tk = [-1, -0.6, -0.3, -0.12, 0, 0.3, 0.6, 1]
    wx = np.interp(t, tk, [220, 220, 300, 290, 260, 150, 200, 210])
    wy = np.interp(t, tk, [200, 200, 150, 262, 190, 60, 180, 200])
    kp[:, sk["right_wrist"]] = np.c_[wx, wy]
    kp[:, sk["left_wrist"]] = np.c_[np.full(T, 170), np.full(T, 190)]
    for side in ("left", "right"):
        kp[:, sk[f"{side}_elbow"]] = (kp[:, sk[f"{side}_shoulder"]] + kp[:, sk[f"{side}_wrist"]]) / 2
    hop = 15 * np.exp(-((t + 0.85) ** 2) / (2 * 0.035 ** 2))
    lx = np.interp(t, [-1, 0.45, 0.55, 1], [170, 170, 135, 135])
    kp[:, sk["left_ankle"]] = np.c_[lx, 440 - hop]
    kp[:, sk["right_ankle"]] = np.c_[np.full(T, 230), 440 - hop]
    for side in ("left", "right"):
        kp[:, sk[f"{side}_knee"]] = (kp[:, sk[f"{side}_hip"]] + kp[:, sk[f"{side}_ankle"]]) / 2
    return sk, kp, np.ones((T, 17))


def test_dominant_side_aliases():
    assert Skeleton("coco17", "right")["dom_wrist"] == Skeleton("coco17", "left")["non_wrist"]
    with pytest.raises(ValueError):
        Skeleton("coco17", "both")


def test_angles_and_turn():
    a, b, c = np.array([[0, 1.0]]), np.array([[0, 0.0]]), np.array([[1, 0.0]])
    assert joint_angle(a, b, c)[0] == pytest.approx(90)
    sk, kp, _ = synthetic_forehand()
    turn = line_turn(kp, sk, "shoulder")
    assert turn[IMPACT - 15] == pytest.approx(60, abs=1)   # loaded at -0.30 s
    assert turn[0] == pytest.approx(0, abs=1)


def test_clean_fills_short_gaps_only():
    kp = np.tile(np.arange(30.0)[:, None, None], (1, 1, 2))
    conf = np.ones((30, 1))
    conf[5:8] = 0      # 3-frame gap: filled
    conf[15:25] = 0    # 10-frame gap: left empty
    out = clean(kp, conf, max_gap=6)
    assert not np.isnan(out[5:8]).any()
    assert np.isnan(out[15:25]).all()


def test_phases_on_synthetic_forehand():
    sk, kp, conf = synthetic_forehand()
    h = body_height(kp, sk)
    ev = {e.name: e for e in detect_phases(kp, to_body_frame(kp, sk, h), conf, sk, FPS, h, IMPACT)}
    expect = {"ready": -0.80, "takeback": -0.525, "loaded": -0.30, "acceleration": -0.12,
              "impact": 0.0, "extension": 0.05, "finish": 0.30, "recovery": 0.45}
    for name, t in expect.items():
        assert ev[name].frame is not None, name
        assert (ev[name].frame - IMPACT) / FPS == pytest.approx(t, abs=0.07), name
    assert ev["ready"].method == "split_step_landing"


def test_analyze_stroke_metrics():
    sk, kp, conf = synthetic_forehand()
    r = analyze_stroke(kp, conf, sk, FPS, body_height(kp, sk), IMPACT, "audio+swing")
    assert r.stroke == "forehand"
    assert r.metrics["shoulder_turn_loaded_deg"] == pytest.approx(60, abs=2)
    assert r.metrics["x_factor_deg"] == pytest.approx(30, abs=3)
    assert set(r.chain["order"]) == {"pelvis", "trunk", "upper_arm", "forearm"}
    assert r.review == []


def test_racket_axis_and_head():
    # a racket pointing up-right from the wrist: thin handle then a wide head
    poly = np.vstack([[100, 300], [150, 250], [140, 240], [170, 200], [200, 190], [205, 215], [175, 255], [160, 262], [104, 304]])
    r = racket_from_polygon(poly.astype(float), wrist=np.array([95.0, 305.0]))
    assert np.linalg.norm(r.butt - [100, 302]) < 15
    assert r.head[0] > 160 and r.head[1] < 240
    assert 30 < r.elevation_deg < 60


def test_fuse_prefers_audio_when_close():
    imps = fuse(np.array([100, 200]), 50, np.array([2.06, 5.0]))
    assert imps[0].source == "audio+swing" and imps[0].frame == 103
    assert imps[1].source == "swing" and imps[1].confidence < 0.9


def test_tracking_does_not_jump_to_another_person():
    me, coach = np.array([100, 100, 200, 400.0]), np.array([400, 50, 480, 300.0])
    f_me, f_coach = np.r_[np.ones(4), np.zeros(4)] / 4, np.r_[np.zeros(4), np.ones(4)] / 4
    boxes = [np.array([me]), np.array([me + 3]), np.array([coach]), np.array([coach, me + 300])]
    feats = [np.array([f_me]), np.array([f_me]), np.array([f_coach]), np.array([f_coach, f_me])]
    sel = track_target(boxes, feats, me)
    assert list(sel) == [0, 0, -1, 1]   # skips the coach after the cut, re-acquires by appearance
