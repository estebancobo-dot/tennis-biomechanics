"""Side view from practice videos (YouTube): what the TV camera behind the baseline cannot see.

A separate, clearly marked source (decision of the user, 12-10): her practice sessions filmed from
other angles. Only the strokes filmed from the side are measured, and only what that view shows
better than the TV camera: how far in front of the hip she meets the ball, the real low-to-high
angle of the swing, knee bend, trunk lean, elbow, how low the racket drops and the racket–forearm
angle (lag). Nothing here is mixed with the match data: it lives in its own folder, its own file
and its own screen of the report.

Practice is not a match, every video has its own camera and the player is assumed to be the
largest person in the image (the camera follows her): the report says so next to every value."""
from __future__ import annotations

import warnings

import numpy as np

from .kinematics import joint_angle
from .skeleton import Skeleton

VIEW_ES = {"lateral": "de lado", "frontal": "de frente", "trasera": "por detrás", "diagonal": "en diagonal"}

# per-stroke measurements of the side view: key -> (label, unit, what it says)
SIDE_METRICS = {
    "contact_in_front_pct": ("Impacto delante de la cadera", "% altura",
                             "distancia de la mano por delante del centro de la cadera en el impacto"),
    "swing_angle_deg": ("Ángulo del swing (de abajo arriba)", "°",
                        "inclinación de la trayectoria de la mano en los ~70 ms previos al impacto"),
    "elbow_impact_deg": ("Codo en el impacto", "°", "180° = brazo recto"),
    "back_knee_loaded_deg": ("Rodilla de atrás en el armado", "°", "180° = pierna recta"),
    "front_knee_impact_deg": ("Rodilla de delante en el impacto", "°", "180° = pierna recta"),
    "trunk_lean_impact_deg": ("Tronco en el impacto", "°", "+ inclinado hacia delante, − hacia atrás"),
    "racket_drop_below_contact_cm": ("Caída de la raqueta bajo el impacto", "cm",
                                     "cuánto baja la cabeza de la raqueta por debajo de la altura del impacto antes de subir"),
    "lag_accel_deg": ("Ángulo antebrazo–raqueta al acelerar", "°",
                      "retraso de la raqueta respecto al antebrazo al empezar a acelerar (180° = en línea)"),
    "lag_pre_impact_deg": ("Ángulo antebrazo–raqueta antes del impacto", "°",
                           "el mismo ángulo ~50 ms antes del impacto: si ya está en línea mucho antes, suelta la muñeca pronto"),
}
# per-stroke measurement of the front view (face visible): where the head points at contact
FRONT_METRICS = {
    "head_to_contact_idx": ("Cabeza girada hacia el impacto", "índice",
                            "+1 = la cara mira hacia el lado del impacto, 0 = al frente, −1 = al lado contrario"),
}
# the same measurements from the 3D pose (RTMW3D), in her own body frame: usable from a diagonal camera
# too (not from behind, where the depth is exactly the forward axis); estimates, marked as such
D3_METRICS = {
    "contact_in_front_3d_pct": ("Impacto delante de la cadera (3D)", "% altura", "estimación 3D: mano por delante del centro de la cadera"),
    "swing_angle_3d_deg": ("Ángulo del swing (3D)", "°", "estimación 3D: subida de la mano en los ~70 ms previos al impacto"),
    "elbow_impact_3d_deg": ("Codo en el impacto (3D)", "°", "estimación 3D; 180° = brazo recto"),
    "back_knee_loaded_3d_deg": ("Rodilla de atrás en el armado (3D)", "°", "estimación 3D; 180° = pierna recta"),
    "trunk_lean_impact_3d_deg": ("Tronco en el impacto (3D)", "°", "estimación 3D; + hacia delante"),
}
D3_VIEWS = ("lateral", "diagonal", "frontal")
MIN_N = 12
# a value outside these is a measurement error (wrong contact frame, arm hidden behind the body): the
# whole stroke is left out, since its contact frame cannot be trusted either
LIMITS = {"contact_in_front_pct": (-40, 80), "swing_angle_deg": (-30, 80), "elbow_impact_deg": (60, 180),
          "back_knee_loaded_deg": (70, 180), "front_knee_impact_deg": (70, 180), "trunk_lean_impact_deg": (-35, 45),
          "racket_drop_below_contact_cm": (-40, 90), "lag_accel_deg": (40, 180), "lag_pre_impact_deg": (40, 180),
          "head_to_contact_idx": (-1.5, 1.5), "contact_in_front_3d_pct": (-40, 80), "swing_angle_3d_deg": (-30, 80),
          "elbow_impact_3d_deg": (60, 180), "back_knee_loaded_3d_deg": (70, 180), "trunk_lean_impact_3d_deg": (-35, 45)}


def implausible(metrics: dict) -> list[str]:
    """Names of the values outside their physical limits."""
    return [k for k, (lo, hi) in LIMITS.items() if metrics.get(k) is not None and not lo <= metrics[k] <= hi]          # as everywhere in the report: no summary from fewer strokes


def _mean_pt(kp, *idx):
    with warnings.catch_warnings():                 # a joint not seen in a frame stays NaN
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(np.stack([kp[..., i, :] for i in idx]), axis=0)


def _shoulder_ratio(img: np.ndarray, sk: Skeleton, f: int, fps: float, half: float = 0.08) -> float:
    """Apparent shoulder width / torso length around frame f (0 = shoulders overlap)."""
    a, b = max(0, f - int(half * fps)), min(len(img), f + int(half * fps) + 1)
    seg = img[a:b]
    if not len(seg):
        return float("nan")
    sh = np.abs(seg[:, sk["left_shoulder"], 0] - seg[:, sk["right_shoulder"], 0])
    torso = np.linalg.norm(_mean_pt(seg, sk["left_shoulder"], sk["right_shoulder"]) - _mean_pt(seg, sk["left_hip"], sk["right_hip"]), axis=-1)
    with np.errstate(invalid="ignore", divide="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return float(np.nanmedian(sh / torso))


def camera_view(img: np.ndarray, conf: np.ndarray, sk: Skeleton, ready: int | None, impact: int, fps: float,
                loaded: int | None = None) -> str:
    """Where the camera films her from. A forehand turns the shoulders about 90° between the wait
    (facing the net) and the end of the backswing: filmed from the side, the shoulders look narrow
    while she waits and wide when she has turned; from behind or the front, the other way round.
    Both moments are needed: one alone is fooled by a camera at an angle. Front and back are told
    apart by the face (eyes and nose detected)."""
    fr = ready if ready is not None else max(0, impact - int(0.9 * fps))
    fl = loaded if loaded is not None else max(0, impact - int(0.3 * fps))
    r_wait, r_turn = _shoulder_ratio(img, sk, fr, fps), _shoulder_ratio(img, sk, fl, fps)
    if not (np.isfinite(r_wait) and np.isfinite(r_turn)) or fl <= fr:
        return "diagonal"
    if r_wait < 0.35 and r_turn > r_wait + 0.25:
        return "lateral"
    if r_wait > 0.6 and r_wait > r_turn + 0.2:
        a, b = max(0, fr - int(0.1 * fps)), min(len(img), fr + int(0.1 * fps) + 1)
        face = np.nanmean(conf[a:b][:, [sk["nose"], sk["left_eye"], sk["right_eye"]]])
        return "frontal" if face > 0.5 else "trasera"
    return "diagonal"


def faces_camera(conf: np.ndarray, sk: Skeleton, min_share: float = 0.6) -> bool:
    """Most of the time her face is seen (nose and both eyes detected): the camera is in front of her
    (or in front and to one side), so the image is a mirror of the view from behind."""
    face = conf[:, [sk["nose"], sk["left_eye"], sk["right_eye"]]].min(axis=1)
    seen = conf[:, [sk["left_shoulder"], sk["right_shoulder"]]].min(axis=1) > 0.3
    return bool(seen.sum() >= 10 and np.mean(face[seen] > 0.6) >= min_share)


def forward_sign(img: np.ndarray, sk: Skeleton, impact: int) -> int:
    """Direction of the shot in the image (+1 towards image-right): where the hand travels at contact."""
    w = img[:, sk["dom_wrist"], 0]
    a, b = max(0, impact - 2), min(len(img) - 1, impact + 2)
    d = w[b] - w[a]
    if not np.isfinite(d) or d == 0:
        h = _mean_pt(img[[a, b]], sk["left_hip"], sk["right_hip"])[:, 0]
        d = w[impact] - np.nanmean(h) if np.isfinite(w[impact]) else 1.0
    return 1 if d >= 0 else -1


def _angle(a, b, c):
    v = joint_angle(np.asarray(a, float)[None], np.asarray(b, float)[None], np.asarray(c, float)[None])[0]
    return None if not np.isfinite(v) else round(float(v), 1)


def side_metrics(img: np.ndarray, conf: np.ndarray, sk: Skeleton, fps: float, impact: int, phases: dict,
                 height_px: float, height_m: float, heads: dict | None = None) -> dict:
    """The measurements that the side view gives (image px in, degrees / % of her height / cm out).
    phases: name -> absolute frame or None. heads: frame -> racket head (x, y) in px, when seen."""
    heads = heads or {}
    s = forward_sign(img, sk, impact)
    up = lambda p: -p[1]                                  # image y grows downwards
    i = impact
    dw, de, ds = sk["dom_wrist"], sk["dom_elbow"], sk["dom_shoulder"]
    hipc = _mean_pt(img, sk["left_hip"], sk["right_hip"])
    shc = _mean_pt(img, sk["left_shoulder"], sk["right_shoulder"])
    out = {}
    if np.isfinite(img[i, dw]).all() and np.isfinite(hipc[i]).all() and conf[i, dw] >= 0.3:
        out["contact_in_front_pct"] = round(float((img[i, dw, 0] - hipc[i, 0]) * s / height_px * 100), 1)
    k = max(2, int(round(0.07 * fps)))
    if i - k >= 0 and np.isfinite(img[[i - k, i], dw]).all():
        d = img[i, dw] - img[i - k, dw]
        if abs(d[0]) + abs(d[1]) > 0.02 * height_px:
            out["swing_angle_deg"] = round(float(np.degrees(np.arctan2(-d[1], d[0] * s))), 1)
    if min(conf[i, ds], conf[i, de], conf[i, dw]) >= 0.4:
        out["elbow_impact_deg"] = _angle(img[i, ds], img[i, de], img[i, dw])
    ld = phases.get("loaded")
    # forehand: the back leg is on the side of the hitting arm
    if ld is not None and min(conf[ld, sk["dom_hip"]], conf[ld, sk["dom_knee"]], conf[ld, sk["dom_ankle"]]) >= 0.4:
        out["back_knee_loaded_deg"] = _angle(img[ld, sk["dom_hip"]], img[ld, sk["dom_knee"]], img[ld, sk["dom_ankle"]])
    if min(conf[i, sk["non_hip"]], conf[i, sk["non_knee"]], conf[i, sk["non_ankle"]]) >= 0.4:
        out["front_knee_impact_deg"] = _angle(img[i, sk["non_hip"]], img[i, sk["non_knee"]], img[i, sk["non_ankle"]])
    if np.isfinite(shc[i]).all() and np.isfinite(hipc[i]).all():
        v = shc[i] - hipc[i]
        out["trunk_lean_impact_deg"] = round(float(np.degrees(np.arctan2(v[0] * s, up(v)))), 1)
    # racket: lowest head between the loading and contact, and the forearm–racket angle
    lo = ld if ld is not None else i - int(0.4 * fps)
    seen = {f: h for f, h in heads.items() if lo <= f < i and h is not None}
    if len(seen) >= 2 and np.isfinite(img[i, dw, 1]):
        low = max(h[1] for h in seen.values())
        out["racket_drop_below_contact_cm"] = round(float((low - img[i, dw, 1]) / height_px * height_m * 100), 1)

    def lag(f):
        h = heads.get(f)
        if f is None or h is None or not np.isfinite(img[f, [de, dw]]).all():
            return None
        return _angle(img[f, de], img[f, dw], h)

    ac = phases.get("acceleration")
    out["lag_accel_deg"] = lag(ac)
    out["lag_pre_impact_deg"] = lag(i - max(1, int(round(0.05 * fps))))
    return {k: v for k, v in out.items() if v is not None}


def front_metrics(img: np.ndarray, conf: np.ndarray, sk: Skeleton, impact: int) -> dict:
    """Head turn towards the contact, from the front: the nose against the middle of the ears, in units
    of half the distance between the ears, signed towards the side of the hitting hand."""
    i = impact
    le, re_, n, w = sk["left_ear"], sk["right_ear"], sk["nose"], sk["dom_wrist"]
    if min(conf[i, le], conf[i, re_], conf[i, n]) < 0.4 or not np.isfinite(img[i, [le, re_, n, w]]).all():
        return {}
    mid = (img[i, le, 0] + img[i, re_, 0]) / 2
    half = abs(img[i, le, 0] - img[i, re_, 0]) / 2
    side = np.sign(img[i, w, 0] - mid)
    if half < 1 or side == 0:
        return {}
    return {"head_to_contact_idx": round(float(np.clip((img[i, n, 0] - mid) / half * side, -1.5, 1.5)), 2)}


# COCO body indices inside RTMW3D's 133 keypoints
_J = {"nose": 0, "left_shoulder": 5, "right_shoulder": 6, "left_elbow": 7, "right_elbow": 8, "left_wrist": 9, "right_wrist": 10,
      "left_hip": 11, "right_hip": 12, "left_knee": 13, "right_knee": 14, "left_ankle": 15, "right_ankle": 16}


def to_metres(kp3d: np.ndarray, height_m: float) -> np.ndarray:
    """RTMW3D keypoints (x, y in crop px, z depth) → metres with y up: the image axes are scaled by her
    height (nose to the lowest ankle ≈ 0.93 of it), as in racket3d.hand_prior."""
    k = np.asarray(kp3d, float)
    ppm = (max(k[15, 1], k[16, 1]) - k[0, 1]) / (0.93 * height_m)
    if not np.isfinite(ppm) or ppm <= 0:
        return np.full_like(k, np.nan)
    return np.stack([k[:, 0] / ppm, -k[:, 1] / ppm, k[:, 2]], axis=1)


def metrics_3d(frames: dict, hand: str, height_m: float, min_score: float = 0.4) -> dict:
    """Measures in her body frame from 3D keypoints. frames: name -> (kp3d (133, 3), scores (133,))
    for "loaded", "pre" (~70 ms before contact) and "impact". Forward = horizontal direction of the
    hand in the last ~70 ms; up = vertical."""
    d, n = ("right", "left") if hand == "right" else ("left", "right")
    P = {k: (to_metres(v[0], height_m), np.asarray(v[1], float)) for k, v in frames.items() if v is not None}
    if "impact" not in P or "pre" not in P:
        return {}
    (ki, si), (kp, sp) = P["impact"], P["pre"]
    j = lambda name: _J[name]
    w = j(f"{d}_wrist")
    if min(si[w], sp[w]) < min_score:
        return {}
    move = ki[w] - kp[w]
    hor = np.array([move[0], 0.0, move[2]])
    if np.linalg.norm(hor) < 0.05:                      # the hand barely moved: no direction to measure from
        return {}
    fwd = hor / np.linalg.norm(hor)
    out = {}
    hip = (ki[j("left_hip")] + ki[j("right_hip")]) / 2
    if min(si[j("left_hip")], si[j("right_hip")]) >= min_score:
        out["contact_in_front_3d_pct"] = round(float((ki[w] - hip) @ fwd / height_m * 100), 1)
        sh = (ki[j("left_shoulder")] + ki[j("right_shoulder")]) / 2
        v = sh - hip
        out["trunk_lean_impact_3d_deg"] = round(float(np.degrees(np.arctan2(v @ fwd, v[1]))), 1)
    out["swing_angle_3d_deg"] = round(float(np.degrees(np.arctan2(move[1], np.linalg.norm(hor)))), 1)

    def ang(k, s, a, b, c):
        if min(s[j(a)], s[j(b)], s[j(c)]) < min_score:
            return None
        u, v = k[j(a)] - k[j(b)], k[j(c)] - k[j(b)]
        cosv = u @ v / (np.linalg.norm(u) * np.linalg.norm(v) + 1e-9)
        return round(float(np.degrees(np.arccos(np.clip(cosv, -1, 1)))), 1)

    out["elbow_impact_3d_deg"] = ang(ki, si, f"{d}_shoulder", f"{d}_elbow", f"{d}_wrist")
    if "loaded" in P:
        kl, sl = P["loaded"]
        out["back_knee_loaded_3d_deg"] = ang(kl, sl, f"{d}_hip", f"{d}_knee", f"{d}_ankle")
    return {k: v for k, v in out.items() if v is not None and np.isfinite(v)}


def summarize(strokes: list[dict]) -> dict:
    """Median and spread of each measurement over the forehands filmed from its view (side or front);
    a measurement with fewer than MIN_N strokes only gives its count (nothing is concluded from it)."""
    out = {}
    for view, table in (("lateral", SIDE_METRICS), ("frontal", FRONT_METRICS), ("3d", D3_METRICS)):
        own = [s for s in strokes if (s.get("view") in D3_VIEWS if view == "3d" else s.get("view") == view)
               and s.get("stroke") == "forehand" and not s.get("discarded") and not s.get("unconfirmed")]
        for k, (lab, unit, what) in table.items():
            v = np.array([s["metrics"][k] for s in own if s.get("metrics", {}).get(k) is not None], float)
            e = {"label": lab, "unit": unit, "what": what, "n": int(len(v)), "view": view}
            if len(v) >= MIN_N:
                q1, med, q3 = np.percentile(v, [25, 50, 75])
                e.update(median=round(float(med), 2), q1=round(float(q1), 2), q3=round(float(q3), 2))
            out[k] = e
    return out


def views_count(strokes: list[dict]) -> dict:
    c = {}
    for s in strokes:
        c[s.get("view", "diagonal")] = c.get(s.get("view", "diagonal"), 0) + 1
    return c
