"""Footwork from heels and toes (run.feet / run.feet_conf, hybrid pose) and the fallback to the ankles."""
import json

import numpy as np
import pytest

from tennisbio.court_metrics import court_metrics
from tennisbio.footpoints import clean_feet, foot_angle_deg, ground_track, heel_lift
from tennisbio.footwork import feet_track, footwork
from tennisbio.skeleton import FOOT_NAMES, Skeleton
from tennisbio.technique import stroke_technique

SK = Skeleton("coco17", "right")
H = np.array([[100.0, 0, 500], [0, -100.0, 800], [0, 0, 1]])        # court m → image px (100 px per m)
PHASES = {"ready": 10, "takeback": 20, "loaded": 45, "acceleration": 55, "impact": 60, "extension": 62,
          "finish": 75, "recovery": 90}
FI = {n: i for i, n in enumerate(FOOT_NAMES)}


def img_of(c):
    """court m (x, y) → image px."""
    c = np.asarray(c, float)
    return np.array([500 + 100 * c[..., 0], 800 - 100 * c[..., 1]]).T if c.ndim > 1 else np.array([500 + 100 * c[0], 800 - 100 * c[1]])


def standing(T=100):
    """A right-hander from behind (image px, 400 px tall), ankles side by side 0.7 m apart on the court."""
    kp = np.zeros((T, 17, 2))
    pts = {"nose": (0, -370), "left_eye": (-5, -375), "right_eye": (5, -375), "left_ear": (-12, -365), "right_ear": (12, -365),
           "left_shoulder": (-40, -320), "right_shoulder": (40, -320), "left_elbow": (-55, -250), "right_elbow": (55, -250),
           "left_wrist": (-60, -190), "right_wrist": (60, -190), "left_hip": (-25, -200), "right_hip": (25, -200),
           "left_knee": (-30, -100), "right_knee": (30, -100), "left_ankle": (-35, 0), "right_ankle": (35, 0)}
    for n, (dx, dy) in pts.items():
        kp[:, SK[n]] = (500 + dx, 800 + dy)
    return kp


def put_foot(feet, side, contact, angle_deg, t=slice(None), length=0.24):
    """One foot ('left'/'right') on the court: ground contact (heel–toe middle) and direction (court
    degrees from +x), heel and both toes in image px."""
    a = np.radians(angle_deg)
    u = np.array([np.cos(a), np.sin(a)]) * length / 2
    c = np.asarray(contact, float)
    feet[t, FI[f"{side}_heel"]] = img_of(c - u)
    feet[t, FI[f"{side}_big_toe"]] = img_of(c + u)
    feet[t, FI[f"{side}_small_toe"]] = img_of(c + u)


def neutral_feet(T=100):
    """Ankles say 'open' (side by side); the real ground contacts are a neutral stance: the front
    (left) foot 0.8 m straight ahead of the back one, pointing at the net; the back foot along the baseline."""
    f = np.full((T, 6, 2), np.nan)
    put_foot(f, "right", (0.35, 0.0), 0.0)           # back foot (dominant), toes towards her forehand side
    put_foot(f, "left", (0.35, 0.8), 90.0)           # front foot, toes at the net
    return f, np.full((T, 6), 0.9)


def tech(kp, **kw):
    return stroke_technique(kp, np.ones((len(kp), 17)), SK, 50.0, np.full(len(kp), 400.0), 60, PHASES, "forehand", H,
                            opp=5, **kw)


def test_clean_feet_contract():
    f, c = neutral_feet()
    assert clean_feet(None, None) is None
    assert clean_feet(f, np.zeros_like(c)) is None                 # nothing confident: as if there were no feet
    assert clean_feet(np.full_like(f, np.nan), c) is None
    assert clean_feet(f[:, :4], c[:, :4]) is None                  # wrong shape: ignored, never a crash
    c2 = c.copy()
    c2[:, FI["left_heel"]] = 0.1
    g = clean_feet(f, c2)
    assert np.isnan(g[:, FI["left_heel"]]).all() and np.isfinite(g[:, FI["right_heel"]]).all()


def test_stance_base_and_foot_angles_from_heels_and_toes():
    kp = standing()
    f, c = neutral_feet()
    with_f = tech(kp, feet=f, feet_conf=c)
    ankles = tech(kp)
    assert ankles["classes"]["stance_impact"] == "abierto"            # the ankles side by side
    assert with_f["classes"]["stance_impact"] == "neutro"             # the ground contacts: front foot ahead
    ph = with_f["phases"]["impact"]
    assert ph["base_court_m"] == pytest.approx(0.8, abs=0.01) and ph["base_m"] == pytest.approx(0.8, abs=0.01)
    assert ph["front_foot_angle_deg"] == pytest.approx(90, abs=0.5)
    assert ph["back_foot_angle_deg"] == pytest.approx(0, abs=0.5)
    assert "front_foot_angle_deg" in with_f["phases"]["loaded"]
    assert "front_foot_angle_deg" not in with_f["phases"]["finish"]  # only loaded and impact
    for p in ankles["phases"].values():                              # no feet: no foot direction at all
        assert not any(k.endswith("_foot_angle_deg") for k in p)
    cm = court_metrics(kp, SK, H, "forehand", 60, 5, feet=f, feet_conf=c)
    assert cm["stance"] == "neutro" and cm["stance_width_m"] == pytest.approx(0.8, abs=0.01)
    assert court_metrics(kp, SK, H, "forehand", 60, 5)["stance"] == "abierto"


def test_without_feet_everything_is_as_before():
    """No feet, feet that are all unseen or all below the confidence: the very same output as the ankles."""
    kp = standing()
    ref = json.dumps(tech(kp), sort_keys=True, default=str)
    f, c = neutral_feet()
    for kw in ({"feet": None, "feet_conf": None}, {"feet": f, "feet_conf": np.zeros_like(c)},
               {"feet": np.full_like(f, np.nan), "feet_conf": c}):
        assert json.dumps(tech(kp, **kw), sort_keys=True, default=str) == ref
    assert court_metrics(kp, SK, H, "forehand", 60, 5, feet=None) == court_metrics(kp, SK, H, "forehand", 60, 5)
    assert np.array_equal(feet_track(kp, SK, H), feet_track(kp, SK, H, None), equal_nan=True)
    assert np.array_equal(ground_track(kp, SK, H)[0], feet_track(kp, SK, H), equal_nan=True)


def test_foot_angle_sign_mirrors_for_left_handers_and_backhands():
    T = 3
    f = np.full((T, 6, 2), np.nan)
    put_foot(f, "right", (0.3, 0.0), 0.0)            # toes to image right (+x)
    put_foot(f, "left", (-0.3, 0.0), 135.0)          # toes forward and to the left
    right, left = Skeleton("coco17", "right"), Skeleton("coco17", "left")
    assert foot_angle_deg(f, 0, right, H, "back") == pytest.approx(0, abs=0.5)            # RH forehand: right foot back
    assert foot_angle_deg(f, 0, right, H, "front") == pytest.approx(135, abs=0.5)
    # a left-hander's forehand: the left foot is the back one; toes forward-left = towards her hitting side
    assert foot_angle_deg(f, 0, left, H, "back") == pytest.approx(45, abs=0.5)
    assert foot_angle_deg(f, 0, left, H, "front") == pytest.approx(180, abs=0.5)
    # a right-hander's backhand: the right foot is in front and the hitting side is her left
    assert foot_angle_deg(f, 0, right, H, "front", "backhand") == pytest.approx(180, abs=0.5)
    put_foot(f, "right", (0.3, 0.0), 0.0, length=0.9)                                     # impossible foot: misdetection
    assert foot_angle_deg(f, 0, right, H, "back") is None
    assert foot_angle_deg(None, 0, right, H, "back") is None and foot_angle_deg(f, 9, right, H, "back") is None


def _heel_lift_case(kind):
    kp = standing()
    f, c = neutral_feet()
    r = FI["right_heel"]
    if kind == "pivot":                      # back heel up 25 px (6 % of her height) from 0.04 s before contact
        f[58:72, r, 1] -= 25
    elif kind == "whole_foot":               # the whole back foot leaves the ground: a step, not a pivot
        f[58:72, [r, FI["right_big_toe"], FI["right_small_toe"]], 1] -= 25
    elif kind == "toe_slides":               # heel up but the toes slide 0.3 m: not planted
        f[58:72, r, 1] -= 25
        f[58:72, [FI["right_big_toe"], FI["right_small_toe"]], 0] -= 30
    elif kind == "hidden":                   # back heel unseen most of the time
        c[40:80, r] = 0.0
    return footwork(kp, SK, H, np.full(len(kp), 400.0), 50.0, 60, 5, None, 75, 45, foot_points=clean_feet(f, c))


def test_back_heel_lift_pivot_and_not():
    out = _heel_lift_case("pivot")
    assert out["back_heel_lift"] is True and out["back_heel_lift_s"] == pytest.approx(-0.04)
    assert _heel_lift_case("flat")["back_heel_lift"] is False and "back_heel_lift_s" not in _heel_lift_case("flat")
    assert _heel_lift_case("whole_foot")["back_heel_lift"] is False
    assert _heel_lift_case("toe_slides")["back_heel_lift"] is False
    assert "back_heel_lift" not in _heel_lift_case("hidden")          # too little seen: not measured, not "no"
    no_feet = footwork(standing(), SK, H, np.full(100, 400.0), 50.0, 60, 5, None, 75, 45)
    assert "back_heel_lift" not in no_feet and "back_heel_lift_s" not in no_feet
    # a left-hander pivots on her left foot
    lh = Skeleton("coco17", "left")
    f, c = neutral_feet()
    f[58:72, FI["left_heel"], 1] -= 25
    assert heel_lift(clean_feet(f, c), lh, H, np.full(100, 400.0), 50.0, 60, 45, 75)["back_heel_lift"] is True


def test_ground_track_falls_back_to_the_ankle_with_its_offset():
    """Frames without heel and toes use the ankle moved by that foot's median offset: no jump between sources."""
    kp = standing()
    f, c = neutral_feet()
    c[30:40] = 0.0                                                    # feet unseen for 0.2 s
    g, used = ground_track(kp, SK, H, clean_feet(f, c))
    assert not used[30:40].any() and used[:30].all()
    assert np.allclose(g[35], g[20], atol=1e-6)                      # the same spot, from the ankle + offset
    assert np.allclose(g[20, 1], [0.35, 0.8])


def test_steps_from_ground_contacts_ignore_ankle_jitter():
    """A clean side step of the front foot, seen through jittery ankles: the heel–toe contacts give one step
    of the right length; the ankles alone see a moving foot most of the time."""
    T, fps = 100, 50.0
    kp = standing(T)
    rng = np.random.default_rng(0)
    f = np.full((T, 6, 2), np.nan)
    x = np.interp(np.arange(T), [0, 40, 50, T - 1], [-0.35, -0.35, -0.85, -0.85])    # left foot steps 0.5 m sideways
    for t in range(T):
        put_foot(f, "right", (0.35, 0.0), 0.0, t=t)
        put_foot(f, "left", (x[t], 0.0), 90.0, t=t)
    kp[:, SK["left_ankle"], 0] = 500 + 100 * x
    kp[:, [SK["left_ankle"], SK["right_ankle"]]] += rng.normal(0, 6, (T, 2, 2))        # ±6 cm ankle jitter
    c = np.full((T, 6), 0.9)
    with_f = footwork(kp, SK, H, np.full(T, 400.0), fps, 80, None, None, None, None, foot_points=clean_feet(f, c))
    st = [s for s in with_f["steps"] if s["foot"] == "non"]
    assert len(st) == 1 and st[0]["length_m"] == pytest.approx(0.5, abs=0.05)
    assert with_f["steps_reliable"] is True and with_f["feet_still_share"] > 0.8
    ank = footwork(kp, SK, H, np.full(T, 400.0), fps, 80, None, None, None, None)
    assert ank["feet_still_share"] < with_f["feet_still_share"]
