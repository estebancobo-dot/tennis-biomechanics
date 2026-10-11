"""Reference contacts from annotated ball tracks (RacketVision broadcast clips).

With the main camera behind the near baseline, the ball comes towards the camera (image y grows)
until the near player hits it and then goes away (y shrinks); the far player's hits are the
opposite turning points. Annotations are sparse (every ~5 frames), so the reference time is the
annotated sample at the turning point (±2-3 frames).
"""
import csv
from pathlib import Path

import numpy as np


def read_ball_csv(path: Path) -> np.ndarray:
    """(frame, x, y) of visible annotated ball positions."""
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            if int(r["Visibility"]):
                rows.append((int(r["Frame"]), float(r["X"]), float(r["Y"])))
    return np.array(rows, float).reshape(-1, 3)


def hits_from_ball(track: np.ndarray, height: int, min_swing_px=40.0) -> dict:
    """Turning points of the ball's image y: near-player hits (local maxima, lower part of the
    image) and far-player hits (local minima). A turn must be confirmed by a swing of at least
    min_swing_px on both sides so that small bounces and annotation jitter are ignored."""
    near, far = [], []
    if len(track) < 3:
        return {"near": near, "far": far}
    f, y = track[:, 0], track[:, 2]
    for i in range(1, len(y) - 1):
        before, after = y[max(0, i - 3):i], y[i + 1:i + 4]
        if y[i] >= before.max() and y[i] >= after.max():
            if y[i] - before.min() >= min_swing_px and y[i] - after.min() >= min_swing_px and y[i] > 0.45 * height:
                near.append(int(f[i]))
        elif y[i] <= before.min() and y[i] <= after.min():
            if before.max() - y[i] >= min_swing_px and after.max() - y[i] >= min_swing_px:
                far.append(int(f[i]))
    return {"near": near, "far": far}
