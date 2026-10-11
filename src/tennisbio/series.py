"""Per-frame series of one stroke for the report: skeleton, racket, kinetic chain and angles.

Everything is relative to the stroke's window video, so the report can draw the skeleton over
the real frames and scrub through the stroke.
"""
import numpy as np

from .kinematics import joint_angle, line_turn, segment_angle, speed, to_body_frame
from .skeleton import Skeleton

CHAIN = {"pelvis": "Pelvis", "trunk": "Tronco", "upper_arm": "Brazo", "forearm": "Antebrazo"}


def _r(a, nd=1):
    """Rounded list with None for NaN (compact JSON)."""
    a = np.asarray(a, float)
    return [None if not np.isfinite(v) else round(float(v), nd) for v in a.ravel()]


def stroke_series(img: np.ndarray, conf: np.ndarray, boxes: list, sk: Skeleton, fps: float, height_px: float,
                  impact: int, racket_track: list | None = None, ball: np.ndarray | None = None,
                  window=(1.0, 0.8), scale=None) -> dict:
    a = max(0, impact - int(round(window[0] * fps)))
    b = min(len(img), impact + int(round(window[1] * fps)) + 1)
    w = img[a:b]
    hs = np.full(b - a, float(height_px)) if scale is None else np.asarray(scale, float)[a:b]
    body = to_body_frame(w, sk, hs)
    sig = {
        "pelvis": line_turn(w, sk, "hip", scale=hs),
        "trunk": line_turn(w, sk, "shoulder", scale=hs),
        "upper_arm": segment_angle(body[:, sk["dom_shoulder"]], body[:, sk["dom_elbow"]]),
        "forearm": segment_angle(body[:, sk["dom_elbow"]], body[:, sk["dom_wrist"]]),
    }
    kin = {}
    k5 = max(1, int(round(0.05 * fps)))                # ~50 ms moving average: 2D angles are jittery
    for k, x in sig.items():
        v = np.abs(speed(x, fps))
        if k5 > 1:
            ok = np.isfinite(v)
            num = np.convolve(np.where(ok, v, 0), np.ones(k5), "same")
            den = np.convolve(ok.astype(float), np.ones(k5), "same")
            v = np.where(den > 0, num / np.maximum(den, 1e-9), np.nan)
        mx = np.nanmax(v) if np.isfinite(v).any() else np.nan
        kin[k] = _r(v / mx if mx and np.isfinite(mx) else v, 3)
    elbow = joint_angle(body[:, sk["dom_shoulder"]], body[:, sk["dom_elbow"]], body[:, sk["dom_wrist"]])
    xf = sig["trunk"] - sig["pelvis"]
    bx = [None if boxes[f] is None else [round(float(v)) for v in boxes[f]] for f in range(a, b)]
    rk = None
    if racket_track:
        by_t = {round(t, 3): (e, h) for t, e, h in racket_track}
        rk = {"elev": [], "head_cm": []}
        for f in range(a, b):
            e, h = by_t.get(round((f - impact) / fps, 3), (None, None))
            rk["elev"].append(e)
            rk["head_cm"].append(h)
    return {
        "fps": fps, "first": a, "impact": impact, "n": b - a,
        "kp": [_r(w[t], 0) for t in range(len(w))],                  # image px, per frame 2K values
        "conf": [_r(conf[f], 2) for f in range(a, b)],
        "box": bx,
        "kin": {CHAIN[k]: v for k, v in kin.items()},
        "ang": {"Codo": _r(elbow), "X-factor": _r(xf)},
        "racket": rk,
        "ball": None if ball is None else [_r(ball[f, :2], 0) if f < len(ball) else [None, None] for f in range(a, b)],
    }
