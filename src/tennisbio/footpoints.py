"""Foot points (heels, big and small toes) from the hybrid pose cache, ready for the footwork metrics.

Only the hybrid fine-pass pose (pose.hybrid, `fine_pass.pose_model: hybrid`) has them; with the
default YOLO pose every function here sees no feet and the metrics keep using the ankles. Nothing
in the current metrics calls these yet: they are the pieces for stance / base / foot direction from
the real ground contact instead of the ankle (the ankle is ~8-10 cm above the ground and, from the
TV camera behind and above, projects further back on the court than the foot).
"""
from __future__ import annotations

import numpy as np

from .court_metrics import to_court
from .skeleton import FOOT_NAMES, Skeleton

MIN_FOOT_CONF = 0.3        # below this a foot point counts as unseen


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
