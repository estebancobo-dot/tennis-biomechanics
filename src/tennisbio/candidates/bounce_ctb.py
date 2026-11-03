"""Learned ball bounce (candidate; scripts/export_bounce_ctb.py): the CatBoost regressor of yastrebksv/TennisProject
(`bounce_detector.py`), ported to numpy around its ONNX export.

Per frame of the ball path, 12 features: for lags 1 and 2, |x(t−i) − x(t)|, |x(t+i) − x(t)| and their ratio, and the
same for y with the sign kept (y(t−i) − y(t), …). A frame is scored only with the ball seen at t and at the two frames
either side. Before that, as upstream, a gap after at least 5 seen frames is filled by extrapolating those 5 with a
natural cubic spline (at most 3 frames in a row), and a seen point more than 80 px away from such a fill is dropped
as a jump. A frame scoring above the threshold (0.45, upstream's default) is a bounce; a run of consecutive scored
rows above it keeps only the best one (upstream's postprocess, on rows, not on frames).

The model was trained on 30 fps broadcast clips (the TrackNet dataset): `step` reads every step-th frame of a
faster track (as our ball tracker reads 50-60 fps video at ~25-30 fps) and maps the frames back.

Same input as tennisbio.ball's bounce rule (a (T, ≥2) image track, NaN where the ball was not seen), so both are
measured on the same task (scripts/bench_candidates.py, candidate `bounce`)."""
from __future__ import annotations

from pathlib import Path

import numpy as np

THRESHOLD = 0.45
LAGS = (1, 2)
EPS = 1e-15
INTERP = 5            # seen frames needed before a gap to extrapolate into it
MAX_FILL = 3          # extrapolated frames in a row at most
JUMP_PX = 80          # a seen point this far from the extrapolated one before it is dropped


def _extrapolate(xs: np.ndarray, ys: np.ndarray) -> tuple[float, float]:
    from scipy.interpolate import CubicSpline

    t = np.arange(len(xs))
    return (float(CubicSpline(t, xs, bc_type="natural")(len(xs))),
            float(CubicSpline(t, ys, bc_type="natural")(len(ys))))


def smooth(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Upstream's smooth_predictions on float arrays (NaN = not seen). Upstream tests `not x` (so x == 0 counted as
    missing too); here only NaN is missing."""
    x, y = np.array(x, float), np.array(y, float)
    none = np.isnan(x)
    count = 0
    for i in range(INTERP, len(x) - 1):
        if none[i] and not none[i - INTERP:i].any() and count < MAX_FILL:
            x[i], y[i] = _extrapolate(x[i - INTERP:i], y[i - INTERP:i])
            none[i] = False
            if not none[i + 1] and np.hypot(x[i] - x[i + 1], y[i] - y[i + 1]) > JUMP_PX:
                x[i + 1] = y[i + 1] = np.nan
                none[i + 1] = True
            count += 1
        else:
            count = 0
    return x, y


def features(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(features (n, 12) in the model's column order, their frames (n,)) for the frames with x seen at t, t±1, t±2."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    n = len(x)

    def shift(a, k):                        # pandas' shift(k): a[t - k], NaN outside
        out = np.full(n, np.nan)
        if k > 0:
            out[k:] = a[:n - k]
        elif k < 0:
            out[:n + k] = a[-k:]
        else:
            out[:] = a
        return out
    cols, ok = {}, ~np.isnan(x)
    for i in LAGS:
        xl, xr, yl, yr = shift(x, i), shift(x, -i), shift(y, i), shift(y, -i)
        ok &= ~np.isnan(xl) & ~np.isnan(xr)
        cols[f"x_diff_{i}"] = np.abs(xl - x)
        cols[f"x_diff_inv_{i}"] = np.abs(xr - x)
        cols[f"y_diff_{i}"] = yl - y
        cols[f"y_diff_inv_{i}"] = yr - y
        with np.errstate(divide="ignore", invalid="ignore"):
            cols[f"x_div_{i}"] = np.abs(cols[f"x_diff_{i}"] / (cols[f"x_diff_inv_{i}"] + EPS))
            cols[f"y_div_{i}"] = cols[f"y_diff_{i}"] / (cols[f"y_diff_inv_{i}"] + EPS)
    order = ([f"x_diff_{i}" for i in LAGS] + [f"x_diff_inv_{i}" for i in LAGS] + [f"x_div_{i}" for i in LAGS]
             + [f"y_diff_{i}" for i in LAGS] + [f"y_diff_inv_{i}" for i in LAGS] + [f"y_div_{i}" for i in LAGS])
    frames = np.flatnonzero(ok)
    return np.stack([cols[c][frames] for c in order], 1).astype(np.float32).reshape(len(frames), 12), frames


def peaks(rows: np.ndarray, scores: np.ndarray) -> list[int]:
    """Upstream's postprocess: of each run of consecutive row indices above the threshold, the best-scoring one."""
    out: list[int] = []
    for k, r in enumerate(rows):
        if k and r - rows[k - 1] == 1:
            if scores[r] > scores[out[-1]]:
                out[-1] = int(r)
        else:
            out.append(int(r))
    return out


class CatBoostBounce:
    def __init__(self, onnx_path: str | Path, device: str = "cpu", threshold: float = THRESHOLD):
        # tree ensembles run on the CPU in every onnxruntime package (DirectML has no kernel for them)
        from ..pose.estimator import _ort_session

        self.sess = _ort_session(str(onnx_path), "cpu" if device == "dml" else device)
        self.threshold = threshold

    def scores(self, track: np.ndarray, step: int = 1, smooth_track: bool = True) -> tuple[np.ndarray, np.ndarray]:
        """(frames of the full track that were scored, their bounce scores)."""
        t = np.asarray(track, float)[::max(1, int(step))]
        x, y = (smooth(t[:, 0], t[:, 1]) if smooth_track else (t[:, 0], t[:, 1]))
        feats, fr = features(x, y)
        if not len(fr):
            return fr * max(1, int(step)), np.zeros(0)
        s = np.asarray(self.sess.run(None, {self.sess.get_inputs()[0].name: feats})[0], float).reshape(-1)
        return fr * max(1, int(step)), s

    def bounces(self, track: np.ndarray, step: int = 1, smooth_track: bool = True) -> list[int]:
        """Frames (of the full track) with a bounce, ascending."""
        fr, s = self.scores(track, step, smooth_track)
        rows = np.flatnonzero(s > self.threshold)
        return sorted(int(fr[r]) for r in peaks(rows, s)) if len(rows) else []
