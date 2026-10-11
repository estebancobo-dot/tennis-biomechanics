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


def hits_from_ball(track: np.ndarray, height: int, fps: float = 25.0) -> dict:
    """Near- and far-player hit frames from annotated (frame, x, y) ball positions, with the same
    definition as the pipeline (tennisbio.ball.turning_hits): sharpest turn of the path after which
    the ball travels away. Annotations are sparse (~every 5 frames), hence the wider span."""
    from ..ball import turning_hits

    if len(track) < 3:
        return {"near": [], "far": []}
    hits = turning_hits(track[:, 0].astype(int), track[:, 1:3], height, span=12, away=round(0.6 * fps),
                        group=round(0.6 * fps))
    return {"near": [h.frame for h in hits if h.side == "near"], "far": [h.frame for h in hits if h.side == "far"]}
