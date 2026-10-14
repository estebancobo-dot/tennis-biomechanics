"""2D kinematics from a keypoint track: cleaning, body frame, angles and speeds.

Conventions: input keypoints are image pixels (x right, y down), shape (T, K, 2), NaN when
missing. The body frame is centred on the hip midpoint of each frame, x right, y up, in units
of body height, so camera pans and zooms cancel out.
"""
import warnings

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


def scale_track(kp: np.ndarray, sk: Skeleton, height_px: float, fps: float, window_s=1.0) -> np.ndarray:
    """Body height in pixels for every frame.

    A player who runs towards the camera, or a camera zoom, changes her size in the image; a
    constant height would read that as technique (the hips "dropping", the head "moving").
    The trunk length (shoulder centre to hip centre) follows the size; its upper envelope over
    ~1 s (90th percentile) ignores the short shortening of a forward lean. Scaled so that its
    median equals the clip's standing height, so the units stay body heights."""
    sh = (kp[:, sk["left_shoulder"]] + kp[:, sk["right_shoulder"]]) / 2
    hp = (kp[:, sk["left_hip"]] + kp[:, sk["right_hip"]]) / 2
    torso = np.linalg.norm(sh - hp, axis=-1)
    T = len(torso)
    if np.isfinite(torso).sum() < 3:
        return np.full(T, float(height_px))
    k = max(1, int(round(window_s * fps / 2)))
    env = np.array([np.nanpercentile(torso[max(0, t - k):t + k + 1], 90) if np.isfinite(torso[max(0, t - k):t + k + 1]).any()
                    else np.nan for t in range(T)])
    idx = np.arange(T)
    ok = np.isfinite(env)
    env = np.interp(idx, idx[ok], env[ok])
    return env * (height_px / float(np.median(env)))


def hip_center(kp: np.ndarray, sk: Skeleton) -> np.ndarray:
    return (kp[:, sk["left_hip"]] + kp[:, sk["right_hip"]]) / 2


def to_body_frame(kp: np.ndarray, sk: Skeleton, height) -> np.ndarray:
    """Hip-centred coordinates in body heights with y pointing up. height: a number, or one per
    frame (see scale_track) so that size changes in the image cancel out."""
    h = np.asarray(height, float)
    rel = (kp - hip_center(kp, sk)[:, None, :]) / (h[:, None, None] if h.ndim == 1 else h)
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


# a signed width below this share of the square-on width would be a turn past ~140°, which no
# groundstroke trunk reaches: it is the pose model swapping the left/right labels, not a rotation
LABEL_SWAP_RATIO = -0.75


def camera_yaw(kp: np.ndarray, sk: Skeleton, joint: str, H: np.ndarray) -> np.ndarray:
    """Per frame, the angle β (degrees) between the court's net direction (+y of the court frame
    of H) and the ground direction that the camera sees edge-on at her position.

    Geometry: the image column through the joint line is the trace of one plane through the camera
    centre. A horizontal segment lying in that plane has no image width, whatever its height (the
    plane cuts every horizontal plane, the court and the one 1.4 m up at her shoulders, along
    parallel lines), so its ground trace — the same image column mapped to the court with H —
    gives that direction. Straight behind the camera β = 0; a player standing 4 m to the side of
    a broadcast camera ~20 m behind her is seen ~8-10° obliquely. + = the line of sight points to
    court +x (her right on the near side). H: court (x, y, 1) → image, her own court frame."""
    Hi = np.linalg.inv(np.asarray(H, float))
    x = (kp[:, sk[f"right_{joint}"], 0] + kp[:, sk[f"left_{joint}"], 0]) / 2
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)          # frames without feet: filled below
        y = np.nanmax(kp[:, [sk["left_ankle"], sk["right_ankle"]], 1], axis=1)
        step = np.maximum(5.0, 0.05 * np.abs(y - kp[:, sk[f"left_{joint}"], 1]))

    def court(px, py):
        p = np.c_[px, py, np.ones(len(px))] @ Hi.T
        return p[:, :2] / p[:, 2:]

    d = court(x, y - step) - court(x, y)        # up the image column = away from the camera
    beta = np.degrees(np.arctan2(d[:, 0], d[:, 1]))
    ok = np.isfinite(beta)
    if not ok.any():
        return np.zeros(len(kp))
    idx = np.arange(len(kp))
    return np.interp(idx, idx[ok], beta[ok])      # frames without feet: her position barely changes


def line_turn(kp: np.ndarray, sk: Skeleton, joint: str, ref_width: float | None = None, scale=None,
              H: np.ndarray | None = None, coil: int = 1) -> np.ndarray:
    """Turn of the shoulder or hip line about the vertical, in degrees, from the 2D keypoints.

    0 = line square to the camera (with H: parallel to the baseline); 90 = side-on (the line points
    at the camera / at the net); > 90 = turned past side-on, as in a full forehand or serve coil.

    Geometry. The broadcast camera has no roll, so image x is horizontal: a horizontal segment of
    length L at angle φ from the camera's edge-on plane shows an image width L·cos φ whatever the
    camera pitch (the pitch only foreshortens the depth into image y, which is mixed with the
    lateral tilt of the trunk and is not used). The width is *signed*: from behind (and after the
    far player's image is mirrored) the right joint is to the right of the left one while the line
    is less than 90° turned, and the two swap sides when it turns past side-on. So
        φ = arccos(w / w0),  w = x_right − x_left (per body height),  w0 = square-on width,
    which covers 0-180°. The former |w| folded every turn at 90°: a shoulder line turned 120° read
    60°, and the peak of the coil (and its timing) was lost.

    H (court → image, her own court frame) refers the angle to the baseline instead of the line of
    sight: the camera sees her at the yaw β of camera_yaw, so the turn from the baseline is
    θ = φ + dom_sign·β. The direction of the turn (back, as in the backswing, or forward) is not
    observable in the width; the turn is read as backwards (dominant joint towards the camera),
    the direction of a forehand coil (coil=-1: the other way, a backhand coil). Near square-on (φ < |β|) this leaves an error of up to 2|β|.

    scale: body height per frame (scale_track); the width is divided by it, so moving towards or
    away from the camera is not read as a rotation. A reading past ~140° (LABEL_SWAP_RATIO) is a
    left/right label swap of the pose model: no value.
    """
    w = kp[:, sk[f"right_{joint}"], 0] - kp[:, sk[f"left_{joint}"], 0]
    if scale is not None:
        w = w / np.asarray(scale, float)
    w0 = ref_width if ref_width else np.nanpercentile(np.abs(w), 95)
    r = w / w0
    with np.errstate(invalid="ignore"):
        turn = np.degrees(np.arccos(np.clip(r, -1, 1)))
        turn[r < LABEL_SWAP_RATIO] = np.nan
    if H is not None:
        turn = turn + coil * sk.dom_sign * camera_yaw(kp, sk, joint, H)
    return turn


def smooth(x: np.ndarray, fps: float, seconds=0.05) -> np.ndarray:
    """Centred moving average over ~`seconds` that tolerates NaN gaps (1D, or (T, ...) along time)."""
    k = max(1, int(round(seconds * fps)))
    if k <= 1:
        return x
    x = np.asarray(x, float)
    v = np.where(np.isnan(x), 0.0, x)
    w = (~np.isnan(x)).astype(float)
    ker = np.ones(k)
    conv = lambda a: np.apply_along_axis(lambda c: np.convolve(c, ker, "same"), 0, a)
    num, den = conv(v), conv(w)
    out = num / np.maximum(den, 1e-9)
    out[den == 0] = np.nan
    return out


def speed(series: np.ndarray, fps: float) -> np.ndarray:
    """Speed of a (T, 2) point, or absolute rate of change of a (T,) signal, per second."""
    g = np.gradient(series, axis=0) * fps
    return np.linalg.norm(g, axis=-1) if g.ndim == 2 else np.abs(g)
