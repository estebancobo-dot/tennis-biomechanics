"""Foot points (heels, big and small toes) from the hybrid pose cache, ready for the footwork metrics.

Only the hybrid fine-pass pose (pose.hybrid, `fine_pass.pose_model: hybrid`) has them; with the
default YOLO pose every function here sees no feet and the metrics keep using the ankles. The
analysed stroke run carries them as `run.feet` (T, 6, 2) image px in FOOT_NAMES order (NaN unseen)
and `run.feet_conf` (T, 6) (0 unseen). With them, stance, base width, steps and the foot direction
come from the real ground contact instead of the ankle (the ankle is ~8-10 cm above the ground and,
from the TV camera behind and above, projects further back on the court than the foot).
"""
from __future__ import annotations

import numpy as np

from .court_metrics import to_court
from .skeleton import FOOT_NAMES, Skeleton

MIN_FOOT_CONF = 0.3        # below this a foot point counts as unseen
FOOT_LEN_M = (0.10, 0.45)  # heel → big toe on the court; outside it a foot point is misdetected
_FI = {n: i for i, n in enumerate(FOOT_NAMES)}


def clean_feet(feet, feet_conf=None, min_conf: float = MIN_FOOT_CONF) -> np.ndarray | None:
    """run.feet (T, 6, 2) + run.feet_conf (T, 6) → (T, 6, 2) with the points below min_conf as NaN.
    None when there are no feet (YOLO pose) or not a single confident point: the metrics then use
    the ankles exactly as before."""
    if feet is None:
        return None
    f = np.array(feet, float)
    if f.ndim != 3 or f.shape[1:] != (len(FOOT_NAMES), 2):
        return None
    if feet_conf is not None:
        fc = np.asarray(feet_conf, float)
        if fc.shape != f.shape[:2]:
            return None
        with np.errstate(invalid="ignore"):
            f[~(fc >= min_conf)] = np.nan
    return f if np.isfinite(f).all(axis=2).any() else None


def _side_name(sk: Skeleton, side: str) -> str:
    """'dom' / 'non' → 'right' / 'left' for this player's hand."""
    return sk.hand if side == "dom" else ("left" if sk.hand == "right" else "right")


def heel_toe(feet: np.ndarray, sk: Skeleton, side: str, big_toe_only: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """Heel (T, 2) and toes (T, 2) of one foot ('dom' / 'non') in the image, NaN when unseen. The toes
    are the big and small toe averaged (either alone when only one is seen); big_toe_only: the big
    toe alone (the foot axis of the coaching books: heel → big toe)."""
    s = _side_name(sk, side)
    heel = feet[:, _FI[f"{s}_heel"]]
    if big_toe_only:
        return heel, feet[:, _FI[f"{s}_big_toe"]]
    toes = feet[:, [_FI[f"{s}_big_toe"], _FI[f"{s}_small_toe"]]]
    seen = np.isfinite(toes).all(axis=2)
    n = seen.sum(axis=1)[:, None]
    with np.errstate(invalid="ignore", divide="ignore"):
        toe = np.where(n > 0, np.where(seen[:, :, None], toes, 0).sum(axis=1) / np.maximum(n, 1), np.nan)
    return heel, toe


def ground_track(img: np.ndarray, sk: Skeleton, H: np.ndarray, feet: np.ndarray | None = None):
    """Where each foot touches the court, per frame: (T, 2, 2) court metres for the dominant-side and
    the other foot, and (T, 2) bool = taken from the heel and the toes.

    Without feet: the ankles, exactly as footwork.feet_track always did. With feet: the middle of the
    heel and the toes where both are seen; in the other frames the ankle moved by that foot's median
    offset ankle → ground contact over the stroke (so switching source does not look like a step), or
    the plain ankle when that foot was never seen with its heel and toes."""
    T = len(img)
    ank = np.full((T, 2, 2), np.nan)
    for j, name in enumerate(("dom_ankle", "non_ankle")):
        p = img[:, sk[name]]
        ok = np.isfinite(p).all(axis=1)
        if ok.any():
            ank[ok, j] = to_court(H, p[ok])
    used = np.zeros((T, 2), bool)
    if feet is None or len(feet) != T:
        return ank, used
    out = ank.copy()
    for j, side in enumerate(("dom", "non")):
        heel, toe = heel_toe(feet, sk, side)
        mid = (heel + toe) / 2
        ok = np.isfinite(mid).all(axis=1)
        if not ok.any():
            continue
        g = np.full((T, 2), np.nan)
        g[ok] = to_court(H, mid[ok])
        both = ok & np.isfinite(ank[:, j]).all(axis=1)
        off = np.median(g[both] - ank[both, j], axis=0) if both.sum() >= 3 else np.zeros(2)
        out[:, j] = np.where(ok[:, None], g, ank[:, j] + off)
        used[:, j] = ok
    return out, used


# Foot direction (heel → big toe) from the broadcast camera, behind and ~20° above the near player.
# On the PC (14-10) 20-44 % of the single-frame readings pointed the toes back towards her own fence
# (< -45°), clustered around -90° (toes drawn straight below the heel in the image): 8 of 13 front
# feet at the end of the backswing. The court homography cannot do that: to turn a foot pointing at
# the net (heel → toe 23-35 px up the image at her distance) into one pointing at the fence, the heel
# point would have to sit 11-17 cm above the toe point. From behind the toes are hidden behind the heel
# and the shank, and the pose model (trained on people mostly facing the camera) draws them on the
# camera side of the heel. So a reading with the toes behind the heel is a hidden toe, not her foot;
# it is refused (FOOT_BACK_DEG), never folded or guessed, and the share of such strokes decides in
# reliability whether the remaining readings can be given (a selection of only the visible feet
# would be biased). The heel point also sits a little above the court (back of the heel counter, the
# big-toe point at the tip of the sole): mapped on the court through the homography it moves away from
# the camera, and near the sidelines (court-y lines slanted ~35° in the image) also sideways; it is
# lowered by HEEL_RISE_M before mapping. Each reading is the median over ±FOOT_WIN_S around the instant
# (a planted foot does not turn in 40 ms; single-frame flips of the toe are outvoted).
FOOT_BACK_DEG = -45.0      # toes turned back more than this: hidden toe (a planted groundstroke foot never does)
HEEL_RISE_M = 0.015        # heel keypoint above the big-toe keypoint (shod foot; estimate, ≤ ±8° on a sideways foot)
FOOT_FRAC = 0.152          # foot length / standing height (Drillis & Contini; Winter 2009)
FOOT_LEN_TOL = (0.6, 1.4)  # heel → big toe on the court within this × her foot length, or misdetected
FOOT_WIN_S = 0.04          # readings around the instant (±2 frames at 50 fps)
FOOT_SPREAD_DEG = 45.0     # the readings of the window disagree more than this: not a planted foot reading
FOOT_STATUSES = ("medido", "punta_oculta", "incoherente", "sin_pie")


def _foot_frame(feet: np.ndarray, t: int, sk: Skeleton, H: np.ndarray, side: str, hit_side: int,
                drop_px: float, lim: tuple[float, float]) -> tuple[float | None, str]:
    """One frame: (angle or None, status). drop_px: how far the heel point is lowered in the image
    (world vertical ≈ image vertical for the near player: within 7° on the PC's camera)."""
    heel, toe = heel_toe(feet[t:t + 1], sk, side, big_toe_only=True)
    if not (np.isfinite(heel).all() and np.isfinite(toe).all()):
        return None, "sin_pie"
    h = heel[0] + np.array([0.0, drop_px if np.isfinite(drop_px) else 0.0])
    q = to_court(H, np.array([h, toe[0]]))
    d = q[1] - q[0]
    L = float(np.hypot(*d))
    if not np.isfinite(L) or not lim[0] <= L <= lim[1]:
        return None, "incoherente"
    a = float(np.degrees(np.arctan2(d[1], d[0] * hit_side)))
    if a < FOOT_BACK_DEG:
        return None, "punta_oculta"
    return a, "medido"


def foot_reading(feet: np.ndarray | None, frame: int | None, sk: Skeleton, H: np.ndarray, which: str,
                 stroke: str = "forehand", scale: np.ndarray | None = None, height_m: float | None = None,
                 fps: float | None = None) -> tuple[float | None, str]:
    """foot_angle_deg with why it is missing: (angle or None, status), status in FOOT_STATUSES:
    'medido'; 'punta_oculta' (most readings of the window put the toes behind the heel: from behind
    the toes were not seen); 'incoherente' (impossible foot lengths, or the readings of the window
    disagree); 'sin_pie' (heel or big toe not seen)."""
    if feet is None or frame is None or not 0 <= frame < len(feet):
        return None, "sin_pie"
    side = ("non" if which == "front" else "dom") if stroke != "backhand" else ("dom" if which == "front" else "non")
    hit_side = sk.dom_sign if stroke != "backhand" else -sk.dom_sign       # court x of the side she hits on
    if height_m:
        L = FOOT_FRAC * float(height_m)
        lim = (FOOT_LEN_TOL[0] * L, FOOT_LEN_TOL[1] * L)
    else:
        lim = FOOT_LEN_M
    k = max(1, int(round(FOOT_WIN_S * fps))) if fps else 2
    vals, stats = [], []
    for t in range(max(0, frame - k), min(len(feet), frame + k + 1)):
        drop = (HEEL_RISE_M / float(height_m) * float(scale[t])) if (height_m and scale is not None and t < len(scale)) else 0.0
        a, s = _foot_frame(feet, t, sk, H, side, hit_side, drop, lim)
        stats.append(s)
        if a is not None:
            vals.append(a)
    seen = [s for s in stats if s != "sin_pie"]
    if not seen:
        return None, "sin_pie"
    if len(vals) * 2 <= len(seen):              # not a majority of the frames where the foot was seen
        hidden = sum(s == "punta_oculta" for s in seen)
        return None, "punta_oculta" if hidden >= sum(s == "incoherente" for s in seen) else "incoherente"
    if max(vals) - min(vals) > FOOT_SPREAD_DEG:
        return None, "incoherente"
    return float(np.median(vals)), "medido"


def foot_angle_deg(feet: np.ndarray | None, frame: int | None, sk: Skeleton, H: np.ndarray, which: str,
                   stroke: str = "forehand", scale: np.ndarray | None = None, height_m: float | None = None,
                   fps: float | None = None) -> float | None:
    """Direction of one foot on the court at a frame, heel → big toe, against the baseline, in degrees:
    0° = toes along the baseline towards the side she hits on (her dominant side on a forehand, the
    other on a backhand), 90° = toes straight at the net, 180° = along the baseline towards the other
    side, negative = toes turned back towards her own fence (down to FOOT_BACK_DEG). Mirrored for a
    left-hander, so every player reads the same. which: 'front' / 'back' (forehand: the non-dominant
    foot is in front). The median of the readings at ±FOOT_WIN_S (fps; ±2 frames without it).
    scale (her height in px per frame) and height_m: the heel is lowered to the court (HEEL_RISE_M) and
    the foot length checked against hers; without them, no lowering and FOOT_LEN_M.
    None without that foot's heel and big toe, with impossible foot lengths, or with the toes hidden
    (see foot_reading for the reason)."""
    return foot_reading(feet, frame, sk, H, which, stroke, scale, height_m, fps)[0]


HEEL_LIFT_PCT = 0.03       # heel up against the toes by > 3 % of her height (≈ 5 cm) = heel off the ground
TOE_PLANTED_M = 0.12       # the toes stay within 12 cm of where they were at the reference (PIVOT_REF_S)
TOE_LIFT_PCT = 0.02        # and do not rise more than 2 % of her height in the image
HEEL_SEEN_SHARE = 0.6      # heel and toes seen in at least 60 % of the frames loaded → finish
# the flat-foot reference is taken at most this long before contact: the pivot comes with the hips
# turning forward, in the forward swing (on the PC, 14-10: lifts from -0.06 to +0.02 s). Taken at the
# end of the backswing instead, a stroke whose backswing ends 0.4-0.6 s before contact (running in,
# adjustment steps after it) never had its back toes "planted" where they were then: 0 of 6 such
# forehands pivoted, against 5 of 6 of those whose backswing ends ~0.14 s before contact
PIVOT_REF_S = 0.2


def heel_lift(feet: np.ndarray | None, sk: Skeleton, H: np.ndarray, scale: np.ndarray, fps: float, impact: int,
              loaded: int | None, finish: int | None, stroke: str = "forehand") -> dict:
    """Pivot on the ball of the back foot: between loaded and finish, does the back heel lift while its
    toes stay planted? {"back_heel_lift": bool, "back_heel_lift_s": first frame of the lift in s from
    contact (only when it lifts)}; {} without feet or with the heel and toes seen too little.

    From behind and above, a heel that lifts rises in the image against its own toes (heel above toes
    by more than when it was loaded, in % of her height, so moving towards the net, which raises both,
    does not count). The toes must stay on their spot on the court and not rise: a foot that leaves
    the ground whole is a step or a kick back, not a pivot. It must last ≥ 0.04 s (2 frames).
    The foot is compared with itself from loaded, or from PIVOT_REF_S before contact when the
    backswing ends earlier (her feet may still be moving then)."""
    if feet is None or loaded is None or not 0 <= loaded < len(feet):
        return {}
    T = len(feet)
    end = finish if finish is not None and loaded < finish < T else min(T - 1, impact + int(round(0.4 * fps)))
    start = max(loaded, impact - int(round(PIVOT_REF_S * fps)))
    if end <= start:
        return {}
    back = "dom" if stroke != "backhand" else "non"
    heel, toe = heel_toe(feet, sk, back)
    w = np.arange(start, end + 1)
    ok = np.isfinite(heel[w]).all(axis=1) & np.isfinite(toe[w]).all(axis=1) & np.isfinite(scale[w])
    if ok.mean() < HEEL_SEEN_SHARE or ok[:max(1, int(round(0.06 * fps)))].sum() == 0:
        return {}                                 # needs the foot at the start (flat) as the reference
    first = w[ok][:3]
    rel = toe[:, 1] - heel[:, 1]                  # + = heel above the toes in the image (y grows down)
    ref_rel, ref_toe_y = float(np.median(rel[first])), float(np.median(toe[first, 1]))
    toe_c = np.full((T, 2), np.nan)
    toe_c[w[ok]] = to_court(H, toe[w[ok]])
    ref_toe_c = np.median(toe_c[first], axis=0)
    with np.errstate(invalid="ignore"):
        up = (rel[w] - ref_rel) / scale[w] > HEEL_LIFT_PCT
        planted = (np.linalg.norm(toe_c[w] - ref_toe_c, axis=1) <= TOE_PLANTED_M) & \
                  ((ref_toe_y - toe[w, 1]) / scale[w] <= TOE_LIFT_PCT)
    lift = ok & up & planted
    need = max(2, int(round(0.04 * fps)))
    run = 0
    for i, x in enumerate(lift):
        run = run + 1 if x else 0
        if run >= need:
            return {"back_heel_lift": True, "back_heel_lift_s": round((int(w[i - need + 1]) - impact) / fps, 3)}
    return {"back_heel_lift": False}


def series_feet(feet, feet_conf, first: int, n: int) -> dict:
    """The raw foot points of a stroke's series window (series.stroke_series: frames first..first+n-1),
    so the foot measures can be checked and re-derived from the PC's outputs: {"feet": n × 6 × [x, y]
    image px (None unseen), "feet_conf": n × 6}, FOOT_NAMES order; {} without any foot point."""
    if feet is None or feet_conf is None:
        return {}
    f = np.asarray(feet, float)[first:first + n]
    c = np.asarray(feet_conf, float)[first:first + n]
    if f.ndim != 3 or f.shape[1:] != (len(FOOT_NAMES), 2) or c.shape != f.shape[:2] or not np.isfinite(f).any():
        return {}
    pts = [[[round(float(p[0]), 1), round(float(p[1]), 1)] if np.isfinite(p).all() else None for p in fr] for fr in f]
    return {"feet": pts, "feet_conf": np.round(np.nan_to_num(c), 2).tolist()}


def has_feet(d: dict | None) -> bool:
    """Whether a pose cache (pipeline.load_npz) carries foot points (hybrid model)."""
    return d is not None and "feet" in d and "feet_confs" in d


def tracked_feet(d: dict, sel) -> tuple[np.ndarray, np.ndarray]:
    """Foot points of the tracked person: sel[t] = her detection index in frame t (−1 = not seen), as
    tracking.track_target returns. → (T, 6, 2) image px (NaN unseen), (T, 6) confidences (0 unseen).
    Without feet in the cache: all NaN / 0."""
    T = len(sel)
    fk, fc = np.full((T, len(FOOT_NAMES), 2), np.nan), np.zeros((T, len(FOOT_NAMES)))
    if not has_feet(d):
        return fk, fc
    feet, conf = d["feet"], d["feet_confs"]
    for t, j in enumerate(sel):
        if j >= 0 and t < len(feet) and j < len(feet[t]):
            fk[t], fc[t] = feet[t][j], conf[t][j]
    return fk, fc


def with_feet(img: np.ndarray, conf: np.ndarray, feet: np.ndarray, feet_conf: np.ndarray,
              min_conf: float = MIN_FOOT_CONF) -> tuple[np.ndarray, np.ndarray]:
    """Body (T, 17, 2) + feet (T, 6, 2) → (T, 23, 2) for Skeleton(..., feet=True); foot points below
    min_conf become NaN (the body points are left as they are)."""
    f = np.array(feet, float)
    fc = np.asarray(feet_conf, float)
    f[fc < min_conf] = np.nan
    return np.concatenate([np.asarray(img, float), f], axis=1), np.concatenate([np.asarray(conf, float), fc], axis=1)


def ground_point(kp: np.ndarray, sk: Skeleton, side: str) -> np.ndarray | None:
    """Where one foot ('dom' or 'non') touches the ground in the image, for one frame kp (K, 2):
    the middle of the heel and the toes (big and small toe averaged) when both are seen; the ankle
    otherwise (as now); None when nothing is seen."""
    if sk.has_feet:
        heel = kp[sk[f"{side}_heel"]]
        toes = np.array([kp[sk[f"{side}_big_toe"]], kp[sk[f"{side}_small_toe"]]], float)
        toe = np.nanmean(toes, axis=0) if np.isfinite(toes).all(1).any() else np.full(2, np.nan)
        if np.isfinite(heel).all() and np.isfinite(toe).all():
            return (heel + toe) / 2
    ankle = kp[sk[f"{side}_ankle"]]
    return np.asarray(ankle, float) if np.isfinite(ankle).all() else None


def feet_on_court_ground(img_kp: np.ndarray, frame: int, sk: Skeleton, H: np.ndarray):
    """court_metrics.feet_on_court from the ground points (heel-toe middle, falling back to the ankle
    foot by foot): (dominant-side foot, non-dominant-side foot) in court metres, or None."""
    if frame is None or not 0 <= frame < len(img_kp):
        return None
    d, n = ground_point(img_kp[frame], sk, "dom"), ground_point(img_kp[frame], sk, "non")
    if d is None or n is None:
        return None
    q = to_court(H, np.array([d, n]))
    return q[0], q[1]


def foot_direction_deg(img_kp: np.ndarray, frame: int, sk: Skeleton, H: np.ndarray, side: str) -> float | None:
    """Direction of one foot on the court, heel → toes, in degrees from the court x axis (0° = toes
    to the right of the image along the baseline, 90° = towards the net), or None without its heel
    and toes. The heel and toes are both on the ground, so the homography maps them exactly."""
    if not sk.has_feet or frame is None or not 0 <= frame < len(img_kp):
        return None
    kp = img_kp[frame]
    heel = kp[sk[f"{side}_heel"]]
    toes = np.array([kp[sk[f"{side}_big_toe"]], kp[sk[f"{side}_small_toe"]]], float)
    if not np.isfinite(heel).all() or not np.isfinite(toes).all(1).any():
        return None
    q = to_court(H, np.array([heel, np.nanmean(toes, axis=0)]))
    d = q[1] - q[0]
    if np.hypot(*d) < 1e-6:
        return None
    return float(np.degrees(np.arctan2(d[1], d[0])))
