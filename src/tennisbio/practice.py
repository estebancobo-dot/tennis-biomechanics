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
MIN_N = 12          # as everywhere in the report: no summary from fewer strokes


def _mean_pt(kp, *idx):
    with warnings.catch_warnings():                 # a joint not seen in a frame stays NaN
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(np.stack([kp[..., i, :] for i in idx]), axis=0)


def camera_view(img: np.ndarray, conf: np.ndarray, sk: Skeleton, ready: int | None, impact: int, fps: float) -> str:
    """Where the camera films her from, judged while she waits facing the net (split step): from the
    side her shoulders overlap; from behind or the front they are far apart. Front and back are told
    apart by the face (eyes and nose detected)."""
    f = ready if ready is not None else max(0, impact - int(0.9 * fps))
    a, b = max(0, f - int(0.1 * fps)), min(len(img), f + int(0.1 * fps) + 1)
    seg = img[a:b]
    if not len(seg):
        return "diagonal"
    sh = np.abs(seg[:, sk["left_shoulder"], 0] - seg[:, sk["right_shoulder"], 0])
    torso = np.linalg.norm(_mean_pt(seg, sk["left_shoulder"], sk["right_shoulder"]) - _mean_pt(seg, sk["left_hip"], sk["right_hip"]), axis=-1)
    with np.errstate(invalid="ignore", divide="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        r = np.nanmedian(sh / torso)
    if not np.isfinite(r):
        return "diagonal"
    if r < 0.35:
        return "lateral"
    if r > 0.6:
        face = np.nanmean(conf[a:b][:, [sk["nose"], sk["left_eye"], sk["right_eye"]]])
        return "frontal" if face > 0.5 else "trasera"
    return "diagonal"


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


def summarize(strokes: list[dict]) -> dict:
    """Median and spread of each side-view measurement over the side-view forehands; a measurement
    with fewer than MIN_N strokes only gives its count (nothing is concluded from it)."""
    side = [s for s in strokes if s.get("view") == "lateral" and s.get("stroke") == "forehand"]
    out = {}
    for k, (lab, unit, what) in SIDE_METRICS.items():
        v = np.array([s["metrics"][k] for s in side if s.get("metrics", {}).get(k) is not None], float)
        e = {"label": lab, "unit": unit, "what": what, "n": int(len(v))}
        if len(v) >= MIN_N:
            q1, med, q3 = np.percentile(v, [25, 50, 75])
            e.update(median=round(float(med), 1), q1=round(float(q1), 1), q3=round(float(q3), 1))
        out[k] = e
    return out


def views_count(strokes: list[dict]) -> dict:
    c = {}
    for s in strokes:
        c[s.get("view", "diagonal")] = c.get(s.get("view", "diagonal"), 0) + 1
    return c
