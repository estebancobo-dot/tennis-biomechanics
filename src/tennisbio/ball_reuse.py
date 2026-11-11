"""The detector's ball reused by the fine pass (11-11, R2 of the review of the Base; fine_pass.ball_from_spotting, off by
default, measured A/B with scripts/bench_fine_fps.py before adopting it). A module of its own: in ball_features.py it
changed the code fingerprint of the spotting stage (its ball over the whole match would have been recomputed)."""
from __future__ import annotations

import numpy as np

from .ball_features import BALL_FPS
def window_from_play(track: np.ndarray, t0: float, n: int, fps: float, w: int, h: int,
                     max_gap_s: float = 1.5 / BALL_FPS) -> np.ndarray:
    """11-11 (R2 of the review of the Base; fine_pass.ball_from_spotting, off by default): the detector's ball over the
    play (track_play: time s, x, y as fractions of the frame, confidence) as the fine pass's ball of a window (n frames
    at fps from t0; image px, NaN unseen), so the window does not run the ball model again. Each frame takes the
    linear interpolation of the two play samples around it when both were seen and are at most max_gap_s apart."""
    out = np.full((n, 3), np.nan)
    if track is None or not len(track) or n <= 0:
        return out
    t = np.asarray(track[:, 0], float)
    order = np.argsort(t)
    t, xs, ys, cs = t[order], track[order, 1], track[order, 2], track[order, 3]
    ft = t0 + np.arange(n) / float(fps)
    j = np.searchsorted(t, ft)
    for i, k in enumerate(j):
        a, b = k - 1, k
        if b < len(t) and abs(t[b] - ft[i]) < 1e-6:            # the frame is a play sample: that sample
            if np.isfinite(xs[b]):
                out[i] = (xs[b] * w, ys[b] * h, cs[b])
            continue
        if a < 0 or b >= len(t):
            continue
        if t[b] - t[a] > max_gap_s or not (np.isfinite(xs[a]) and np.isfinite(xs[b])):
            continue
        u = 0.0 if t[b] == t[a] else (ft[i] - t[a]) / (t[b] - t[a])
        out[i] = (((1 - u) * xs[a] + u * xs[b]) * w, ((1 - u) * ys[a] + u * ys[b]) * h, (1 - u) * cs[a] + u * cs[b])
    return out

