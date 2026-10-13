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
    assert finish_class(around, SK, 3, {}) == "alrededor del cuerpo (cintura contraria)"


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
    # repeatability, as the fine pass does it: per phase (neighbouring frames) and the whole stroke again
    # with the phase instants moved 1-2 frames (timings, steps, classes)
    from tennisbio.reliability import shifted_jitter
    assert "loaded.elbow_dom" in tech["jitter"] and all(v >= 0 for v in tech["jitter"].values())
    moved = [stroke_technique(kp, np.ones((100, 17)), SK, fps, np.full(100, 400.0), 60, {k: v + s for k, v in phases.items()},
                              "forehand", H, opp=5, context={"court_pos": [0.1, -1.0], "displacement": 0.5, "t_avail": 1.3,
                                                              "contact_h": 55, "shot_direction": "cruzada"})
             for s in (-2, -1, 1, 2)]
    j = shifted_jitter(tech, moved)
    assert abs(j["stroke.dur_preparation"]) < 1e-9 and j["stroke.t_loaded"] > 0 and "class.stance_impact" in j


def test_steps_reject_runs_without_ground_contact():
    from tennisbio.footwork import planted, steps
    T, fps = 100, 50.0
    feet = np.zeros((T, 2, 2))
    feet[:, 1, 0] = -0.4
    feet[:, 0, 0] = 0.4 + np.clip((np.arange(T) - 20) / 50, 0, 1) * 3.0      # 3 m in 1 s, never planted
    plant = planted(feet, np.zeros((T, 2), bool), fps)
    assert steps(feet, plant, 0, T, fps) == []


def test_running_towards_the_net_is_not_a_jump():
    from tennisbio.footwork import airborne
    from tennisbio.skeleton import Skeleton
    sk = Skeleton("coco17", "right")
    T, fps = 60, 50.0
    img = np.full((T, 17, 2), np.nan)
    y = 900 - np.arange(T) * 4.0                          # both ankles rise in the image: moving away (depth)
    img[:, sk["dom_ankle"], 1] = y
    img[:, sk["non_ankle"], 1] = y + 5
    img[:, sk["dom_ankle"], 0] = img[:, sk["non_ankle"], 0] = 500
    scale = np.full(T, 300.0)
    assert not airborne(img, sk, scale, fps)[10:50].any()
    hop = y.copy()
    hop[28:34] -= 40                                       # a real jump: up and back down
    img[:, sk["dom_ankle"], 1] = hop
    img[:, sk["non_ankle"], 1] = hop + 5
    assert airborne(img, sk, scale, fps)[29:33].all()


def test_a_lifted_foot_is_not_a_sprint():
    from tennisbio.footwork import footwork
    from tennisbio.skeleton import Skeleton
    sk = Skeleton("coco17", "right")
    T, fps = 60, 50.0
    img = np.full((T, 17, 2), np.nan)
    img[:, sk["dom_ankle"]] = [1.0, 0.0]                  # identity homography: image units = metres
    img[:, sk["non_ankle"]] = [0.0, 0.0]
    img[26:36, sk["non_ankle"], 1] = -0.3                 # the front foot lifts during the swing
    scale = np.full(T, 2.0)
    out = footwork(img, sk, np.eye(3), scale, fps, 30, None, None, None, None)
    assert out["speed_at_impact_mps"] is not None and out["speed_at_impact_mps"] < 0.5
    assert out["movement"] == "parada"


def test_curves_follow_the_hip_dip_and_see_the_head_from_behind():
    from tennisbio.model import _typical_curves
    from tennisbio.technique import CURVE_T, stroke_curves

    fps, T, impact, px = 50.0, 120, 70, 200.0                 # 200 px per body height
    t = (np.arange(T) - impact) / fps
    img = np.full((T, 17, 2), np.nan)
    ground = 900.0
    dip = 0.08 * np.exp(-((t + 0.3) / 0.12) ** 2)             # hips 8 % lower 0.3 s before contact
    for n, h in (("left_ankle", 0.039), ("right_ankle", 0.039), ("left_hip", 0.52), ("right_hip", 0.52),
                 ("left_ear", 0.92), ("right_ear", 0.92), ("right_wrist", 0.55)):
        img[:, SK[n], 0] = 500
        img[:, SK[n], 1] = ground - (h - (dip if "hip" in n or "ear" in n else 0)) * px
    img[:, SK["left_ankle"], 1] += np.where(np.arange(T) % 7 == 0, np.nan, 0)   # a few missing frames
    c = stroke_curves(img, SK, np.full(T, px), impact, fps, None)
    assert set(c) == {"head", "hip", "hand"}                   # no racket points: no racket curve
    hip = np.array([np.nan if v is None else v for v in c["hip"]])
    k = int(np.nanargmin(hip))
    assert abs(CURVE_T[k] + 0.3) <= 0.08 and 42 < hip[k] < 47 and abs(hip[0] - 52) < 1
    assert abs(c["head"][0] - 92) < 1                          # the ears stand in for the hidden nose
    # a frame whose ankles were misdetected (her whole body "jumps" 30 %) is dropped, not drawn
    bad = img.copy()
    bad[impact + 10:impact + 16, [SK["left_ankle"], SK["right_ankle"]], 1] += 0.3 * px
    cb = stroke_curves(bad, SK, np.full(T, px), impact, fps, None)
    i = int(np.argmin(np.abs(CURVE_T - 13 / fps)))
    assert cb["hip"][i] is None or abs(cb["hip"][i] - 52) < 3
    # outside the clip there is no value (nothing invented)
    c2 = stroke_curves(img[40:], SK, np.full(T - 40, px), impact - 40, fps, None)
    assert c2["hip"][0] is None
    # typical curve: needs 12 strokes; the band holds the median
    rows = [{"technique": {"curves": c, "stroke": {"t_loaded": 0.4}, "phases": {"ball_bounce": {"t_to_contact": 0.5}}}}] * 12
    tc = _typical_curves(rows)
    assert tc["hip"]["p50"][k] == c["hip"][k] and tc["events"] == {"loaded": -0.4, "ball_bounce": -0.5}
    assert "hip" not in _typical_curves(rows[:11])                # fewer than 12 strokes: no typical curve


def test_every_step_is_named_like_a_coach():
    from tennisbio.footwork import Step, kinds_text, step_kinds

    fps, impact = 50.0, 100
    st = [Step("non", 40, 50, 0.5, 0.5, 0.05, False),        # side step (shuffle)
          Step("dom", 52, 62, 0.9, 0.8, 0.3, True),          # crossover
          Step("non", 60, 70, 0.9, 0.3, 0.85, False),        # long and quick, alternating: running
          Step("dom", 68, 78, 0.8, 0.2, 0.75, False),
          Step("non", 85, 92, 0.2, 0.1, 0.15, False),        # small, just before contact: adjustment
          Step("dom", 120, 130, 0.6, -0.1, -0.55, False)]    # after contact, backwards (recovery)
    k = step_kinds(st, impact, fps)
    assert k == ["lateral", "cruzado", "carrera", "carrera", "ajuste", "hacia atrás"]
    assert kinds_text(k[:5]) == "1 paso lateral, 1 paso cruzado, 2 pasos de carrera y 1 paso de ajuste"


def test_copy_cue_is_built_only_from_her_values():
    from tennisbio.explain import copy_cue

    st = lambda m: {"median": m, "p25": m, "p75": m, "n": 20, "rel": 2, "unit": "", "name": ""}
    model = {"typical": {"stroke.loaded_vs_bounce": st(-0.1), "loaded.shoulder_turn": st(83), "loaded.shoulder_abd_non": st(80),
                         "impact.wrist_dom_vs_hip": st(8), "stroke.head_motion_cm": st(2)}, "chain": None}
    classes = {"stance_loaded": {"n": 20, "counts": {"abierto": 15, "cerrado": 5}},
               "ball_phase": {"n": 20, "counts": {"bola subiendo": 14}}, "arm": {"n": 4, "counts": {"recto": 4}}}
    c = copy_cue("loaded", model, classes)
    assert c == "Termina de armar antes de que bote la bola, con los hombros girados unos 85°, apoyo abierto y el brazo libre señalando la bola."
    i = copy_cue("impact", model, classes)
    assert i.startswith("Toma la bola subiendo, a la altura de la cintura") and "brazo" not in i      # arm: 4 strokes, not enough
    assert copy_cue("finish", model, classes) is None                                                 # nothing measured: nothing said


def test_contact_type_half_volley_and_volley():
    from tennisbio.technique import contact_type

    assert contact_type(0.08, 30, True, (0, -1)) == "media volea"           # low, just after the bounce
    assert contact_type(0.08, 70, True, (0, -1)) == "tras el bote"          # quick but high: a normal rising ball
    assert contact_type(0.6, 60, True, (0, -1)) == "tras el bote"
    assert contact_type(None, 80, True, (0, 9.0)) == "volea"                # no bounce on her side, near the net
    assert contact_type(None, 80, True, (0, 2.0)) is None                   # no bounce seen at the baseline: unknown
    assert contact_type(None, 80, False, (0, 9.0)) is None                  # ball not followed: never a volley


def test_racket_head_beside_or_behind_the_body():
    import numpy as np
    from tennisbio.skeleton import Skeleton
    from tennisbio.technique import racket_at

    sk = Skeleton("coco17", "right")
    img = np.full((3, 17, 2), np.nan)
    img[1, sk["dom_wrist"]] = (330, 200)
    img[1, sk["dom_elbow"]] = (320, 230)
    img[1, sk["dom_shoulder"]] = (300, 150)
    # seen from behind, right-hander: image-right is her hitting side
    beside = {"1": [[380, 120], [370, 140], [335, 205], [375, 130], [385, 130]]}     # head 70 px outside the shoulder
    behind = {"1": [[260, 120], [270, 140], [320, 205], [265, 130], [255, 130]]}     # head towards her back
    a = racket_at(beside, img, sk, 1, 400.0, np.nan, None, None)["racket_head_lateral"]
    b = racket_at(behind, img, sk, 1, 400.0, np.nan, None, None)["racket_head_lateral"]
    assert a > 5 and b < -2


def test_tip_vs_head_and_shoulder_brake():
    from tennisbio.technique import racket_at
    kp = standing(T=100)
    nose_y = kp[10, SK["nose"], 1]
    # tip 40 px above the nose with a 400 px tall body: +10 % of her height
    k = {"10": [[300.0, nose_y - 40], [300.0, nose_y], [300.0, nose_y + 60], [290.0, nose_y - 20], [310.0, nose_y - 20]]}
    r = racket_at(k, kp, SK, 10, 400.0, float(kp[10, SK["left_ankle"], 1]), None, None)
    assert abs(r["racket_tip_vs_head"] - 10.0) < 0.6
    # the shoulder line turns fast after the backswing and slows down before contact: braking
    t = np.arange(100)
    w0 = kp[:, SK["right_shoulder"], 0] - kp[:, SK["left_shoulder"], 0]
    turn = np.radians(np.interp(t, [0, 45, 52, 58, 60, 100], [80, 80, 40, 8, 5, 5]))
    mid = (kp[:, SK["right_shoulder"], 0] + kp[:, SK["left_shoulder"], 0]) / 2
    kp[:, SK["right_shoulder"], 0] = mid + w0 / 2 * np.cos(turn)
    kp[:, SK["left_shoulder"], 0] = mid - w0 / 2 * np.cos(turn)
    phases = {"ready": 10, "takeback": 20, "loaded": 45, "acceleration": 55, "impact": 60, "extension": 62,
              "finish": 75, "recovery": 90}
    tech = stroke_technique(kp, np.ones((100, 17)), SK, 50.0, np.full(100, 400.0), 60, phases, "forehand", None)
    assert tech["stroke"]["shoulder_brake"] > 50


def test_ready_hands_from_wrists_and_racket():
    """Two hands on the racket leave the wrists a grip-to-throat apart (14-19 % of height): not "free hand"."""
    phases = {"ready": 10, "takeback": 20, "loaded": 45, "acceleration": 55, "impact": 60, "extension": 62,
              "finish": 75, "recovery": 90}

    def run(gap_pct, throat_near=None):
        kp = standing(T=100)
        dw, nw = SK["right_wrist"], SK["left_wrist"]
        kp[:, nw] = kp[:, dw] + np.array([-gap_pct / 100 * 400, 0.0])      # body 400 px tall
        faces = None
        if throat_near is not None:
            thr = kp[10, nw] + np.array([throat_near / 100 * 400, 0.0])
            faces = {"first": 0, "keypoints": {"10": [list(thr - [0, 40]), list(thr), list(kp[10, dw]), list(thr), list(thr)]}}
        return stroke_technique(kp, np.ones((100, 17)), SK, 50.0, np.full(100, 400.0), 60, phases, "forehand", None,
                                faces=faces)["classes"].get("ready_hands")

    assert run(12) == "dos manos en la raqueta"
    assert run(35) == "mano libre separada"
    assert run(20) is None                                         # ambiguous and no racket: not given
    assert run(20, throat_near=4) == "dos manos en la raqueta"
    assert run(20, throat_near=18) == "mano libre separada"
