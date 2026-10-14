"""Her height in image pixels, frame by frame: the scale of every measure in % of height or in cm.

Three estimates, in order of preference (fine_pass.height_scale):

- **court** (default): the image length of a vertical segment of her real height (config/players,
  height_m) standing where she is on the court. The camera (focal length, pitch, position) comes
  from the court homography (ball3d.camera); her court position from her ankles, mapped on the
  horizontal plane at ankle height and smoothed over ~1 s (a hop or a split step lifts the feet for
  a few frames). It depends neither on her posture nor on which frames were posed, and it follows
  the perspective as she moves towards or away from the camera.
- **segments** (no court, or a court the body contradicts): body segments seen from behind, upper
  envelopes over the window (trunk: shoulder centre → hip centre; leg: hip centre → lowest ankle),
  divided by their anthropometric share of the standing height; the trunk length over ~1 s gives
  the per-frame changes (kinematics.scale_track).
- **pose**: the former estimate, the median nose → ankle distance × 1.08 over the frames where both
  are seen. From behind the face is rarely seen (on a RacketVision clip, 4 of 600 frames) and in
  play she is crouched, so it read 65-95 % of her height depending on the clip and on which frames
  were posed. Kept only to find the swings (impacts.swing_peaks, whose thresholds were tuned with
  it) and as a check.

The court estimate is checked against the segments: if her trunk and legs measured with it are not
those of a person of her height (within SEG_BAND), the court (a wrong fit, a zoom since the court
was read) is not used.
"""
import warnings

import numpy as np

from .kinematics import body_height, scale_track
from .skeleton import Skeleton

# shares of the standing height (anthropometric tables, Winter 2009; Drillis & Contini), checked on
# the near players of 10 RacketVision clips with the court scale (trunk 0.28-0.34, leg 0.43-0.53 for
# an assumed 1.84 m)
ANKLE_FRAC = 0.039       # ankle joint above the ground
TORSO_FRAC = 0.30        # shoulder centre to hip centre (pose keypoints)
LEG_FRAC = 0.48          # hip centre to the ankle, leg straight
SEG_BAND = (0.8, 1.25)   # court scale kept when the segments say she is 0.8-1.25 × her height
SEG_PCT = 90             # upper envelope: the trunk and the legs at their longest (upright)
MODES = ("court", "segments", "pose")


def _nan_rolling_median(x: np.ndarray, k: int) -> np.ndarray:
    """Centred median over 2k + 1 frames, ignoring NaN; NaN where the whole window is NaN."""
    T = len(x)
    pad = np.r_[np.full(k, np.nan), x, np.full(k, np.nan)]
    win = np.lib.stride_tricks.sliding_window_view(pad, 2 * k + 1)[:T]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmedian(win, axis=1)


def _fill(x: np.ndarray) -> np.ndarray:
    ok = np.isfinite(x)
    idx = np.arange(len(x))
    return np.interp(idx, idx[ok], x[ok]) if ok.any() else x


def ground_track(img: np.ndarray, sk: Skeleton, P: np.ndarray, height_m: float, fps: float,
                 smooth_s: float = 1.0) -> np.ndarray | None:
    """(T, 2) her court position (m) per frame: the ankles' midpoint on the horizontal plane at ankle
    height, centred median over smooth_s, gaps interpolated. None without three frames seen."""
    ank = np.stack([img[:, sk["left_ankle"]], img[:, sk["right_ankle"]]])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        mid = np.nanmean(ank, axis=0)                  # one ankle when the other is not seen
    z = ANKLE_FRAC * height_m
    Hz = np.column_stack([P[:, 0], P[:, 1], P[:, 2] * z + P[:, 3]])
    try:
        Hi = np.linalg.inv(Hz)
    except np.linalg.LinAlgError:
        return None
    q = np.c_[mid, np.ones(len(mid))] @ Hi.T
    with np.errstate(invalid="ignore", divide="ignore"):
        xy = q[:, :2] / q[:, 2:]
    bad = ~np.isfinite(xy).all(1) | (np.abs(xy[:, 0]) > 15) | (xy[:, 1] < -15) | (xy[:, 1] > 40)
    xy[bad] = np.nan
    if (~bad).sum() < 3:
        return None
    k = max(1, int(round(smooth_s * fps / 2)))
    return np.stack([_fill(_nan_rolling_median(xy[:, c], k)) for c in range(2)], axis=1)


def vertical_px(P: np.ndarray, xy: np.ndarray, height_m: float) -> np.ndarray:
    """Image length (px) of a vertical segment from the ground to height_m at each court point."""
    n = len(xy)
    X0 = np.c_[xy, np.zeros(n), np.ones(n)] @ P.T
    X1 = np.c_[xy, np.full(n, height_m), np.ones(n)] @ P.T
    with np.errstate(invalid="ignore", divide="ignore"):
        a, b = X0[:, :2] / X0[:, 2:], X1[:, :2] / X1[:, 2:]
    return np.linalg.norm(b - a, axis=1)


def court_height_track(img: np.ndarray, sk: Skeleton, P: np.ndarray, height_m: float, fps: float,
                       smooth_s: float = 1.0) -> np.ndarray | None:
    """Her standing height in image px per frame at her court position (see the module docstring)."""
    xy = ground_track(img, sk, P, height_m, fps, smooth_s)
    if xy is None:
        return None
    h = vertical_px(P, xy, height_m)
    return h if np.isfinite(h).all() and (h > 0).all() else None


def _segments(img: np.ndarray, sk: Skeleton):
    sh = (img[:, sk["left_shoulder"]] + img[:, sk["right_shoulder"]]) / 2
    hp = (img[:, sk["left_hip"]] + img[:, sk["right_hip"]]) / 2
    torso = np.linalg.norm(sh - hp, axis=-1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        low = np.nanmax(np.stack([img[:, sk["left_ankle"], 1], img[:, sk["right_ankle"], 1]]), axis=0)
    leg = low - hp[:, 1]
    leg[leg <= 0] = np.nan
    return torso, leg


def segment_ratio(img: np.ndarray, sk: Skeleton, height_t: np.ndarray, min_frames: int = 5) -> float:
    """Her height as her trunk and legs give it, as a share of height_t (1 = they agree), from their
    upper envelopes; NaN when neither is seen in min_frames frames."""
    vals = []
    for seg, frac in zip(_segments(img, sk), (TORSO_FRAC, LEG_FRAC)):
        r = seg / np.asarray(height_t, float)
        if np.isfinite(r).sum() >= min_frames:
            vals.append(np.nanpercentile(r, SEG_PCT) / frac)
    return float(np.median(vals)) if vals else float("nan")


def segment_height(img: np.ndarray, sk: Skeleton, min_frames: int = 5) -> float:
    """Her standing height in px from her trunk and legs (upper envelopes); NaN when not seen."""
    vals = []
    for seg, frac in zip(_segments(img, sk), (TORSO_FRAC, LEG_FRAC)):
        if np.isfinite(seg).sum() >= min_frames:
            vals.append(np.nanpercentile(seg, SEG_PCT) / frac)
    return float(np.median(vals)) if vals else float("nan")


def height_scale(img: np.ndarray, sk: Skeleton, fps: float, height_m: float, H: np.ndarray | None = None,
                 frame_shape=None, mode: str = "court", smooth_s: float = 1.0) -> tuple[np.ndarray, str, dict]:
    """(height in px per frame, source, info) for the measures of a window.

    img: cleaned image keypoints of the tracked player (real image coordinates, not mirrored);
    H: court → image homography of the window (real court frame), frame_shape: (h, w) of the window.
    mode: 'court' (court, else segments, else pose), 'segments' (segments, else pose) or 'pose'.
    source: the estimate used ('court' | 'segments' | 'pose'); info: the checks (pose / used ratio,
    segments / used ratio, and why the court was not used)."""
    if mode not in MODES:
        raise ValueError(f"fine_pass.height_scale: {mode!r} (court | segments | pose)")
    T = len(img)
    info: dict = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)           # no frame with face and feet: NaN
        pose_h = body_height(img, sk)
    if mode == "court":
        if H is None or frame_shape is None:
            info["court"] = "sin_pista"
        else:
            from .ball3d import camera
            P = camera(np.asarray(H, float), frame_shape)
            ht = None if P is None else court_height_track(img, sk, P, height_m, fps, smooth_s)
            if ht is None:
                info["court"] = "sin_camara" if P is None else "sin_pies"
            else:
                seg = segment_ratio(img, sk, ht)
                info["segments_ratio"] = None if not np.isfinite(seg) else round(seg, 3)
                if np.isfinite(seg) and not SEG_BAND[0] <= seg <= SEG_BAND[1]:
                    info["court"] = "contradicha_por_el_cuerpo"
                else:
                    if np.isfinite(pose_h):
                        info["pose_ratio"] = round(float(pose_h / np.median(ht)), 3)
                    return ht, "court", info
    if mode in ("court", "segments"):
        sh = segment_height(img, sk)
        if np.isfinite(sh):
            if np.isfinite(pose_h):
                info["pose_ratio"] = round(float(pose_h / sh), 3)
            return scale_track(img, sk, sh, fps), "segments", info
    return (scale_track(img, sk, pose_h, fps) if np.isfinite(pose_h) else np.full(T, np.nan)), "pose", info
