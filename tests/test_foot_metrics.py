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


def test_back_heel_lift_reference_close_to_contact():
    """The flat-foot reference is at most PIVOT_REF_S before contact: a back foot that steps after the
    end of the backswing and then pivots is a pivot (on the PC every forehand with an early backswing
    read «no pivot»); a foot unseen at that reference is not measured."""
    from tennisbio.footpoints import PIVOT_REF_S

    assert PIVOT_REF_S == pytest.approx(0.2)
    kp = standing()
    f, c = neutral_feet()
    put_foot(f, "right", (0.0, -0.4), 0.0, t=slice(45, 50))        # adjustment step after loaded (45): 0.55 m away
    r = FI["right_heel"]
    f[58:72, r, 1] -= 25                                            # then planted from 50 and pivots at 58
    out = heel_lift(clean_feet(f, c), SK, H, np.full(100, 400.0), 50.0, 60, 45, 75)
    assert out["back_heel_lift"] is True and out["back_heel_lift_s"] == pytest.approx(-0.04)
    # same step without the pivot: no
    f2, c2 = neutral_feet()
    put_foot(f2, "right", (0.0, -0.4), 0.0, t=slice(45, 50))
    assert heel_lift(clean_feet(f2, c2), SK, H, np.full(100, 400.0), 50.0, 60, 45, 75)["back_heel_lift"] is False
    # a late backswing end (after the reference instant) is the reference itself, as before
    assert heel_lift(clean_feet(f, c), SK, H, np.full(100, 400.0), 50.0, 60, 55, 75)["back_heel_lift"] is True
    # a heel lift that starts before the reference is the foot's state at the reference: not a lift
    f3, c3 = neutral_feet()
    f3[40:72, r, 1] -= 25
    assert heel_lift(clean_feet(f3, c3), SK, H, np.full(100, 400.0), 50.0, 60, 30, 75)["back_heel_lift"] is False
    # the foot unseen at the reference (seen at loaded): not measured
    c4 = c.copy()
    c4[48:56, [r, FI["right_big_toe"], FI["right_small_toe"]]] = 0.0
    assert heel_lift(clean_feet(f, c4), SK, H, np.full(100, 400.0), 50.0, 60, 45, 75) == {}
    # a finish before the reference instant leaves nothing to measure
    assert heel_lift(clean_feet(f, c), SK, H, np.full(100, 400.0), 50.0, 60, 45, 48) == {}


# --- foot direction from behind and above (PC, 14-10: 20-44 % of the readings had the toes towards her fence) ---

def broadcast_camera(cam=(0.0, -9.6, 3.2), look=(0.0, 2.0, 0.0), f=1940.0, size=(1920, 1080)):
    """A TV camera behind the near baseline and above (the PC's homography gives ~(0, -9.6, 3.2) m,
    f ≈ 1940 px, ~20° down to her feet): 3 × 4 projection court metres (x, y, z up) → image px."""
    C, L = np.asarray(cam, float), np.asarray(look, float)
    z = (L - C) / np.linalg.norm(L - C)                   # camera forward
    x = np.cross(z, [0, 0, 1.0])
    x /= np.linalg.norm(x)                                # image right = court +x
    y = np.cross(z, x)                                    # image down
    R = np.array([x, y, z])
    K = np.array([[f, 0, size[0] / 2], [0, f, size[1] / 2], [0, 0, 1.0]])
    return K @ np.c_[R, -R @ C]


def proj(P, X):
    p = P @ np.r_[np.asarray(X, float), 1.0]
    return p[:2] / p[2]


def foot_3d(P, contact, angle_deg, length, heel_up, T=5, side="right"):
    """One foot on the court through the camera P, heel point heel_up m above the court, toe on it."""
    feet = np.full((T, 6, 2), np.nan)
    a = np.radians(angle_deg)
    u = np.array([np.cos(a), np.sin(a)]) * length / 2
    c = np.asarray(contact, float)
    feet[:, FI[f"{side}_heel"]] = proj(P, [*(c - u), heel_up])
    feet[:, FI[f"{side}_big_toe"]] = proj(P, [*(c + u), 0.0])
    feet[:, FI[f"{side}_small_toe"]] = proj(P, [*(c + u), 0.0])
    return feet


def _scale(P, contact, height_m, T=5):
    """Her height in image px standing at contact (as body_scale gives it)."""
    c = np.asarray(contact, float)
    return np.full(T, float(np.linalg.norm(proj(P, [*c, height_m]) - proj(P, [*c, 0.0]))))


@pytest.mark.parametrize("contact", [(0.0, -1.0), (-4.0, -1.5), (4.0, -1.5)])
@pytest.mark.parametrize("angle", [-30.0, 0.0, 45.0, 90.0, 135.0])
def test_foot_angle_with_a_raised_heel_from_the_broadcast_camera(contact, angle):
    """Nominal: the heel point sits HEEL_RISE_M above the court; lowered before mapping it on the court,
    the direction comes back within 1° in the middle and near both sidelines (court-y lines slanted
    ~35° in the image there, so the raised heel also moved sideways)."""
    from tennisbio.footpoints import HEEL_RISE_M, foot_reading

    P = broadcast_camera()
    Hc = P[:, [0, 1, 3]]
    L = 0.152 * 1.84
    f = foot_3d(P, contact, angle, L, HEEL_RISE_M)
    s = _scale(P, contact, 1.84)
    a, why = foot_reading(f, 2, SK, Hc, "back", "forehand", s, 1.84, 50.0)
    assert why == "medido" and a == pytest.approx(angle, abs=1.0)
    # without lowering the heel (no height): the error the old method had, larger near the sidelines
    raw = foot_angle_deg(f, 2, SK, Hc, "back")
    assert raw is None or abs(raw - angle) >= abs(a - angle)


def test_a_raised_heel_cannot_turn_a_foot_back_towards_the_fence():
    """The cause found: to read a foot that points at the net as pointing at her fence through the
    homography, the heel point would have to be > 10 cm above the toe point. A planted heel never is,
    so the readings clustered at -90° on the PC are hidden toes, not perspective."""
    P = broadcast_camera()
    Hc = P[:, [0, 1, 3]]
    for up in (0.0, 0.03, 0.06):
        assert foot_angle_deg(foot_3d(P, (0.0, -1.0), 90.0, 0.28, up), 2, SK, Hc, "back") == pytest.approx(90, abs=1)
    assert foot_angle_deg(foot_3d(P, (0.0, -1.0), 90.0, 0.28, 0.15), 2, SK, Hc, "back") is None


def test_hidden_toes_are_refused_not_folded_and_single_flips_are_outvoted():
    """Toes drawn on the camera side of the heel (from behind, hidden) in most frames of the instant's
    window: no reading ('punta_oculta'); in one frame of five: the median of the others."""
    from tennisbio.footpoints import foot_reading

    f = np.full((5, 6, 2), np.nan)
    put_foot(f, "right", (0.3, 0.0), 60.0)
    hidden = f.copy()
    put_foot(hidden, "right", (0.3, 0.0), -90.0, t=slice(0, 4))               # 4 of 5 frames: toe below the heel
    a, why = foot_reading(hidden, 2, SK, H, "back")
    assert a is None and why == "punta_oculta"
    one = f.copy()
    put_foot(one, "right", (0.3, 0.0), -90.0, t=slice(2, 3))                   # only at the instant itself
    a, why = foot_reading(one, 2, SK, H, "back")
    assert why == "medido" and a == pytest.approx(60, abs=0.5)
    # corner: the limit itself is possible (a closed stance's back foot slightly back)
    lim = np.full((5, 6, 2), np.nan)
    put_foot(lim, "right", (0.3, 0.0), -44.0)
    assert foot_angle_deg(lim, 2, SK, H, "back") == pytest.approx(-44, abs=0.5)
    put_foot(lim, "right", (0.3, 0.0), -46.0)
    assert foot_reading(lim, 2, SK, H, "back") == (None, "punta_oculta")


def test_foot_reading_window_edges_and_errors():
    """Edge, corner and error cases: the window is clipped at the ends of the stroke; readings that
    disagree, an impossible length for her height, a missing heel or a short scale never crash."""
    from tennisbio.footpoints import FOOT_STATUSES, foot_reading

    f = np.full((5, 6, 2), np.nan)
    put_foot(f, "right", (0.3, 0.0), 30.0, length=0.28)
    assert foot_reading(f, 0, SK, H, "back")[1] == "medido" and foot_reading(f, 4, SK, H, "back")[1] == "medido"
    assert foot_reading(f, 5, SK, H, "back") == (None, "sin_pie") and foot_reading(None, 0, SK, H, "back") == (None, "sin_pie")
    assert foot_reading(f, 2, SK, H, "front") == (None, "sin_pie")             # the other foot never seen
    # disagreeing readings (a foot turning 80° in 80 ms is a detection jumping, not a planted foot)
    jump = f.copy()
    put_foot(jump, "right", (0.3, 0.0), 110.0, t=slice(3, 5))
    assert foot_reading(jump, 2, SK, H, "back") == (None, "incoherente")
    # her foot length: 0.28 m fits a 1.84 m player and a 1.40 m one (≤ 1.4 × 0.21 m), not a 0.9 m one
    assert foot_reading(f, 2, SK, H, "back", height_m=1.84)[1] == "medido"
    assert foot_reading(f, 2, SK, H, "back", height_m=1.40)[1] == "medido"
    assert foot_reading(f, 2, SK, H, "back", height_m=0.9) == (None, "incoherente")
    # a scale shorter than the feet, or NaN: the heel is not lowered there, no crash
    assert foot_reading(f, 2, SK, H, "back", "forehand", np.full(2, 400.0), 1.84)[1] == "medido"
    assert foot_reading(f, 2, SK, H, "back", "forehand", np.full(5, np.nan), 1.84)[1] == "medido"
    # fps sets the window: at 25 fps ±1 frame
    one = f.copy()
    put_foot(one, "right", (0.3, 0.0), -90.0, t=slice(0, 1))
    assert foot_reading(one, 2, SK, H, "back", fps=25.0)[1] == "medido"
    assert set(FOOT_STATUSES) == {"medido", "punta_oculta", "incoherente", "sin_pie"}


def test_technique_says_why_a_foot_direction_is_missing_and_reliability_counts_it():
    """technique "feet_check" (loaded / impact × front / back); the refused readings count as impossible
    ones in reliability, so the visible feet alone (a biased selection) are not given as hers."""
    from tennisbio.reliability import assess

    kp = standing()
    f, c = neutral_feet()
    put_foot(f, "left", (0.35, 0.8), -90.0, t=slice(40, 50))                  # front toes hidden at loaded (45)
    t = tech(kp, feet=f, feet_conf=c)
    assert t["feet_check"] == {"loaded.front": "punta_oculta", "loaded.back": "medido",
                               "impact.front": "medido", "impact.back": "medido"}
    assert "front_foot_angle_deg" not in t["phases"]["loaded"]
    assert t["phases"]["impact"]["front_foot_angle_deg"] == pytest.approx(90, abs=0.5)
    assert "feet_check" not in tech(kp)                                         # no feet: as before
    k = "loaded.front_foot_angle_deg"
    rows = [{"technique": {"phases": {"loaded": {"front_foot_angle_deg": float(v)}}, "jitter": {k: 2.0},
                           "feet_check": {"loaded.front": "medido"}}} for v in range(0, 100, 10)]
    assert assess(rows, {k: "°"})[k]["verdict"] == "fiable"
    refused = [{"technique": {"phases": {"loaded": {}}, "jitter": {}, "feet_check": {"loaded.front": "punta_oculta"}}}] * 2
    r = assess(rows + refused, {k: "°"})[k]
    assert r["verdict"] == "sesgo" and r["refused"] == 2                         # 2 of 12 > 15 %
    one = assess(rows + refused[:1], {k: "°"})[k]
    assert one["verdict"] == "fiable" and one["refused"] == 1                    # 1 of 11: not systematic


def test_series_keep_the_raw_foot_points_of_the_window():
    from tennisbio.footpoints import series_feet

    f, c = neutral_feet(10)
    f[3, FI["left_heel"]] = np.nan
    s = series_feet(f, c, 2, 5)
    assert len(s["feet"]) == 5 and len(s["feet"][0]) == 6 and s["feet"][1][FI["left_heel"]] is None
    assert s["feet"][0][FI["right_heel"]] == [round(float(v), 1) for v in f[2, FI["right_heel"]]]
    assert s["feet_conf"][0] == [0.9] * 6
    json.dumps(s)
    assert series_feet(None, None, 0, 5) == {} and series_feet(f, None, 0, 5) == {}
    assert series_feet(np.full_like(f, np.nan), c, 0, 5) == {} and series_feet(f[:, :4], c[:, :4], 0, 5) == {}


def test_running_strides_keep_their_steps_but_noise_does_not():
    """27-10: running, each foot is in the air about half the time, yet one foot is always on the ground:
    the steps are measured (each foot still ~half the time used to drop them). Both feet jumping around by
    noise: no foot is ever still and the steps are not measured."""
    T, fps = 100, 50.0
    kp = standing(T)
    f = np.full((T, 6, 2), np.nan)
    lx, rx = np.zeros(T), np.zeros(T)
    for k in range(5):                             # alternate strides of 0.6 m, one foot moving at a time
        a, b = 20 * k, 20 * k + 10
        if k % 2 == 0:
            lx[a:b] = np.linspace(0, 0.6, b - a) + lx[a - 1 if a else 0]
            lx[b:] = lx[b - 1]
        else:
            rx[a:b] = np.linspace(0, 0.6, b - a) + rx[a - 1]
            rx[b:] = rx[b - 1]
    for t in range(T):
        put_foot(f, "left", (-0.35 + lx[t], 0.0), 90.0, t=t)
        put_foot(f, "right", (0.35 + rx[t], 0.0), 90.0, t=t)
    c = np.full((T, 6), 0.9)
    run = footwork(kp, SK, H, np.full(T, 400.0), fps, 80, None, None, None, None, foot_points=clean_feet(f, c))
    assert run["steps_reliable"] is True and run["feet_still_share"] > 0.9
    noisy = f + np.random.default_rng(1).normal(0, 40, f.shape)        # ~0.4 m of jitter on every point
    bad = footwork(kp, SK, H, np.full(T, 400.0), fps, 80, None, None, None, None, foot_points=clean_feet(noisy, c))
    assert bad["steps_reliable"] is False and "steps" not in bad
