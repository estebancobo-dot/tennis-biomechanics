import numpy as np

from tennisbio.footwork import planted, steps
from tennisbio.skeleton import Skeleton
from tennisbio.technique import finish_class, posture, situation, stance_class, stroke_technique, flatten
from tennisbio.kinematics import to_body_frame

SK = Skeleton("coco17", "right")


def standing(T=50, x0=500.0, y_feet=800.0, h=400.0):
    """A right-hander seen from behind, standing still (image px, y down)."""
    kp = np.zeros((T, 17, 2))
    pts = {"nose": (0, -370), "left_eye": (-5, -375), "right_eye": (5, -375), "left_ear": (-12, -365), "right_ear": (12, -365),
           "left_shoulder": (-40, -320), "right_shoulder": (40, -320), "left_elbow": (-55, -250), "right_elbow": (55, -250),
           "left_wrist": (-60, -190), "right_wrist": (60, -190), "left_hip": (-25, -200), "right_hip": (25, -200),
           "left_knee": (-30, -100), "right_knee": (30, -100), "left_ankle": (-35, 0), "right_ankle": (35, 0)}
    for n, (dx, dy) in pts.items():
        kp[:, SK[n]] = (x0 + dx, y_feet + dy)
    return kp


def test_stance_four_classes_right_and_left_handed():
    right = Skeleton("coco17", "right")
    back = np.array([0.0, 0.0])
    assert stance_class(back, np.array([-0.8, 0.0]), "forehand", right.dom_sign)[0] == "abierto"
    assert stance_class(back, np.array([-0.6, 0.6]), "forehand", right.dom_sign)[0] == "semiabierto"
    assert stance_class(back, np.array([0.0, 0.8]), "forehand", right.dom_sign)[0] == "neutro"
    assert stance_class(back, np.array([0.5, 0.6]), "forehand", right.dom_sign)[0] == "cerrado"
    left = Skeleton("coco17", "left")          # a left-hander's open stance is the mirror image
    assert stance_class(back, np.array([0.8, 0.0]), "forehand", left.dom_sign)[0] == "abierto"


def test_posture_of_a_standing_player():
    kp = standing()
    body = to_body_frame(kp, SK, np.full(len(kp), 400.0))
    d = posture(body, kp, SK, 10, 400.0)
    assert 95 < d["body_height"] < 105            # nose at 370/400 of the height ×1.08
    assert abs(d["trunk_tilt"]) < 1 and abs(d["shoulder_tilt"]) < 1
    assert abs(d["head_over_base"]) < 1 and 0.4 < d["com_over_feet"] < 0.6
    assert d["elbow_dom"] > 150 and 15 < d["base_width"] < 20


def test_scale_per_frame_cancels_walking_towards_the_camera():
    """The same posture twice as big (closer to the camera) gives the same descriptors."""
    a = standing(h=400)
    b = (standing() - [500, 800]) * 2 + [500, 900]
    da = posture(to_body_frame(a, SK, np.full(50, 400.0)), a, SK, 5, 400.0)
    db = posture(to_body_frame(b, SK, np.full(50, 800.0)), b, SK, 5, 800.0)
    for k in ("body_height", "hip_height", "base_width", "wrist_dom_height"):
        assert abs(da[k] - db[k]) < 0.5


def test_finish_classes():
    kp = standing()
    body = to_body_frame(kp, SK, np.full(50, 400.0))
    over = body.copy()
    over[:, SK["right_wrist"]] = over[:, SK["left_shoulder"]] + [-0.05, 0.06]     # above the other shoulder
    assert finish_class(over, SK, 3, {}) == "sobre el hombro"
    around = body.copy()
    around[:, SK["right_wrist"]] = [-0.15, 0.1]                                  # low, on the other side
    assert finish_class(around, SK, 3, {}) == "alrededor del cuerpo"


def test_steps_and_first_step_on_the_court():
    """Feet on a flat image = court (H identity): a split step, then three lateral steps to the right."""
    fps = 50.0
    T = 120
    feet = np.full((T, 2, 2), np.nan)
    dom = np.array([0.4, 0.0])
    non = np.array([-0.4, 0.0])
    for t in range(T):
        feet[t, 0] = dom
        feet[t, 1] = non
        for k, t0 in enumerate((30, 50, 70)):                     # each step takes 8 frames
            foot = k % 2                                         # dom, non, dom
            if t0 <= t < t0 + 8:
                feet[t, foot, 0] += 0.6 * (t - t0) / 8 + 0.6 * (k // 2 if foot == 0 else 0)
        # positions after the steps
    dom_x = 0.4 + np.where(np.arange(T) >= 38, 0.6, 0) + np.where(np.arange(T) >= 78, 0.6, 0)
    non_x = -0.4 + np.where(np.arange(T) >= 58, 0.6, 0)
    for t in range(T):
        feet[t, 0, 0] = dom_x[t] if not (30 <= t < 38 or 70 <= t < 78) else feet[t, 0, 0]
        feet[t, 1, 0] = non_x[t] if not (50 <= t < 58) else feet[t, 1, 0]
    air = np.zeros((T, 2), bool)
    plant = planted(feet, air, fps)
    st = steps(feet, plant, 20, 100, fps)
    assert len(st) == 3 and st[0].foot == "dom" and all(s.dx > 0 for s in st)


def test_situation_classes():
    s = situation({}, [1.0, -2.5], 3.2, 0.85, 30, 1)
    assert s["ball_speed"] == "muy rápida" and s["ball_height"] == "rodilla" and s["depth"] == "2-4 m detrás"
    assert s["width"] == "muy abierta" and s["intent"] == "defensa" and s["court_side"] == "lado de su derecha"
    a = situation({}, [-1.5, 1.0], 0.5, 1.6, 70, 1)
    assert a["intent"] == "ataque" and a["court_side"] == "lado de su revés"


def test_stroke_technique_end_to_end_on_a_synthetic_swing():
    fps = 50.0
    kp = standing(T=100)
    t = np.arange(100)
    # the dominant wrist goes back and up, drops, then forward-up across the body
    kp[:, SK["right_wrist"], 0] += np.interp(t, [0, 30, 45, 55, 60, 75], [0, 80, 90, 40, -60, -120])
    kp[:, SK["right_wrist"], 1] += np.interp(t, [0, 30, 45, 55, 60, 75], [0, -60, -40, 20, -20, -150])
    H = np.array([[100.0, 0, 500], [0, -100.0, 800], [0, 0, 1]])            # court m → image px
    phases = {"ready": 10, "takeback": 20, "loaded": 45, "acceleration": 55, "impact": 60, "extension": 62,
              "finish": 75, "recovery": 90}
    tech = stroke_technique(kp, np.ones((100, 17)), SK, fps, np.full(100, 400.0), 60, phases, "forehand", H, opp=5,
                            context={"court_pos": [0.1, -1.0], "displacement": 0.5, "t_avail": 1.3, "contact_h": 55,
                                     "shot_direction": "cruzada"})
    assert set(tech["phases"]) == set(phases)
    s = tech["stroke"]
    assert abs(s["dur_forward"] - 0.3) < 1e-6 and s["tempo_ratio"] > 1 and s["swing_low_to_high"] > 0
    c = tech["classes"]
    assert c["stance_impact"] in ("abierto", "semiabierto") and c["movement"] == "parada" and c["intent"] == "neutra"
    flat = flatten(tech)
    assert "loaded.elbow_dom" in flat and "stroke.dur_forward" in flat and "footwork.steps_to_impact" in flat


def test_steps_reject_runs_without_ground_contact():
    from tennisbio.footwork import planted, steps
    T, fps = 100, 50.0
    feet = np.zeros((T, 2, 2))
    feet[:, 1, 0] = -0.4
    feet[:, 0, 0] = 0.4 + np.clip((np.arange(T) - 20) / 50, 0, 1) * 3.0      # 3 m in 1 s, never planted
    plant = planted(feet, np.zeros((T, 2), bool), fps)
    assert steps(feet, plant, 0, T, fps) == []
