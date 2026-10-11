"""2D kinematics from a keypoint track: cleaning, body frame, angles and speeds.

Conventions: input keypoints are image pixels (x right, y down), shape (T, K, 2), NaN when
missing. The body frame is centred on the hip midpoint of each frame, x right, y up, in units
of body height, so camera pans and zooms cancel out.
"""
import numpy as np
from scipy.signal import savgol_filter

from .skeleton import Skeleton


def clean(kp: np.ndarray, conf: np.ndarray, min_conf=0.3, max_gap=6, window=7) -> np.ndarray:
    """Drop low-confidence points, fill short gaps linearly and smooth each continuous run."""
    out = np.array(kp, dtype=float)
    out[np.asarray(conf) < min_conf] = np.nan
    T = len(out)
    idx = np.arange(T)
    for j in range(out.shape[1]):
        for c in range(2):
            v = out[:, j, c]
            ok = ~np.isnan(v)
            if ok.sum() < 2:
                continue
            filled = np.interp(idx, idx[ok], v[ok])
            # only fill gaps up to max_gap frames
            gap = np.zeros(T, int)
            run = 0
            for t in range(T):
                run = run + 1 if not ok[t] else 0
                gap[t] = run
            for t in range(T - 2, -1, -1):
                if not ok[t] and not ok[t + 1]:
                    gap[t] = max(gap[t], gap[t + 1])
            fill = ~ok & (gap <= max_gap) & (idx > idx[ok][0]) & (idx < idx[ok][-1])
            v[fill] = filled[fill]
            # smooth runs long enough for the filter
            good = ~np.isnan(v)
            edges = np.flatnonzero(np.diff(np.r_[0, good.astype(int), 0]))
            for a, b in zip(edges[::2], edges[1::2]):
                if b - a >= window:
                    v[a:b] = savgol_filter(v[a:b], window, 2)
    return out


def body_height(kp: np.ndarray, sk: Skeleton) -> float:
    """Median standing height in pixels: nose-to-lowest-ankle plus ~8 % for the top of the head."""
    feet = np.fmax(kp[:, sk["left_ankle"], 1], kp[:, sk["right_ankle"], 1])
    return float(np.nanmedian(feet - kp[:, sk["nose"], 1]) * 1.08)


def hip_center(kp: np.ndarray, sk: Skeleton) -> np.ndarray:
    return (kp[:, sk["left_hip"]] + kp[:, sk["right_hip"]]) / 2


def to_body_frame(kp: np.ndarray, sk: Skeleton, height: float) -> np.ndarray:
    """Hip-centred coordinates in body heights with y pointing up."""
    rel = (kp - hip_center(kp, sk)[:, None, :]) / height
    rel[..., 1] *= -1
    return rel


def joint_angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Angle ABC in degrees for each frame (arrays of shape (T, 2))."""
    u, w = a - b, c - b
    cos = np.sum(u * w, axis=-1) / (np.linalg.norm(u, axis=-1) * np.linalg.norm(w, axis=-1))
    return np.degrees(np.arccos(np.clip(cos, -1, 1)))


def segment_angle(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Orientation of the segment a→b in degrees (body frame, y up), unwrapped over time."""
    d = b - a
    ang = np.arctan2(d[:, 1], d[:, 0])
    ok = ~np.isnan(ang)
    if ok.any():
        ang[ok] = np.unwrap(ang[ok])
    return np.degrees(ang)


def line_turn(kp: np.ndarray, sk: Skeleton, joint: str, ref_width: float | None = None) -> np.ndarray:
    """Rotation proxy of the shoulder or hip line, in degrees (0 = square to the camera).

    From behind, a line that turns away from the camera plane looks shorter: turn ≈ arccos(w / w0),
    with w0 the square-on width. The sign is ambiguous in 2D, so this is a magnitude.
    """
    w = np.abs(kp[:, sk[f"right_{joint}"], 0] - kp[:, sk[f"left_{joint}"], 0])
    w0 = ref_width if ref_width else np.nanpercentile(w, 95)
    return np.degrees(np.arccos(np.clip(w / w0, 0, 1)))


def speed(series: np.ndarray, fps: float) -> np.ndarray:
    """Speed of a (T, 2) point, or absolute rate of change of a (T,) signal, per second."""
    g = np.gradient(series, axis=0) * fps
    return np.linalg.norm(g, axis=-1) if g.ndim == 2 else np.abs(g)
