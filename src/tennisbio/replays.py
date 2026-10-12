"""Replays from the main camera (behind the baseline), at normal speed or in slow motion.

Most broadcasts hide the scoreboard during a replay, and the candidates stage already skips those
shots. When the scoreboard stays, a replay looks like live play: the same stroke would be counted
twice and, in slow motion, every time-based measure would be wrong. A replay shows her doing again
what she did a few seconds before, on the same spot: her feet follow the same path on the court
(in metres, from the homography). Live play does not repeat a path that closely so soon, and to be
sure the replay must also be slower than the original (slow motion) or carry no impact sounds."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Run:
    t0: float                  # s, start and end of the run in the video
    t1: float
    path: np.ndarray           # (N, 2) her feet on the court, metres, one sample per frame (NaN = unseen)
    fps: float
    impacts: int = 0           # impact sounds heard during the run


def _clean(path: np.ndarray) -> np.ndarray:
    p = np.asarray(path, float)
    return p[np.isfinite(p).all(1)] if len(p) else p.reshape(0, 2)


def path_speed(path: np.ndarray, fps: float) -> float:
    """Median speed of the feet along the path (m/s), over the frames where she moves."""
    p = np.asarray(path, float)
    d = np.linalg.norm(np.diff(p, axis=0), axis=1) * fps
    d = d[np.isfinite(d)]
    d = d[d > 0.3]
    return float(np.median(d)) if len(d) else 0.0


def matches(run: Run, earlier: Run, tol_m: float = 0.6, share: float = 0.8, min_extent_m: float = 1.5) -> bool:
    """Her path in `run` retraces part of `earlier` (each point within tol_m of it, for share of the points)."""
    a, b = _clean(run.path), _clean(earlier.path)
    if len(a) < 10 or len(b) < 10:
        return False
    if np.linalg.norm(a.max(0) - a.min(0)) < min_extent_m:     # standing still: any point would match
        return False
    d = np.min(np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2), axis=1)
    return bool(np.mean(d <= tol_m) >= share)


def find_replays(runs: list[Run], window_s: float = 90.0, slow_ratio: float = 0.7) -> list[int]:
    """Indices of the runs that are replays of an earlier run of the last window_s seconds."""
    out = []
    for i, r in enumerate(runs):
        for e in runs[:i]:
            if i in out or not (0 <= r.t0 - e.t1 <= window_s) or not matches(r, e):
                continue
            v_r, v_e = path_speed(r.path, r.fps), path_speed(e.path, e.fps)
            slow = v_e > 0 and v_r < slow_ratio * v_e
            silent = r.impacts == 0 and e.impacts > 0
            if slow or silent:
                out.append(i)
                break
    return out
