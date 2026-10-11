"""Racket position and orientation from a segmentation outline.

A segmentation mask gives where the racket is and which way it points (handle → head), but not
whether the face is open or closed: that needs the 5-keypoint racket model (RacketVision-style).
"""
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class RacketObs:
    butt: np.ndarray          # end nearest the hand (image px)
    head: np.ndarray          # centre of the far end (image px)
    elevation_deg: float      # angle of butt→head above the horizontal (y up); +90 = head straight up
    length_px: float
    area_px: float


def polygon_mask(poly: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    m = np.zeros(shape, np.uint8)
    cv2.fillPoly(m, [np.round(poly).astype(np.int32)], 1)
    return m.astype(bool)


def racket_from_points(pts: np.ndarray, wrist: np.ndarray) -> RacketObs | None:
    """Principal axis of the racket pixels; the head is the end farther from the wrist."""
    if len(pts) < 20 or np.any(np.isnan(wrist)):
        return None
    mean = pts.mean(0)
    _, vecs = np.linalg.eigh(np.cov((pts - mean).T))
    axis = vecs[:, -1]
    proj = (pts - mean) @ axis
    lo, hi = np.percentile(proj, [2, 98])
    ends = [mean + lo * axis, mean + hi * axis]
    if np.linalg.norm(ends[0] - wrist) > np.linalg.norm(ends[1] - wrist):
        ends.reverse()
        proj, lo, hi = -proj, -hi, -lo
    butt = ends[0]
    # head centre: mean of the pixels in the far 35 % of the racket (the frame is wider there)
    far = pts[proj >= lo + 0.65 * (hi - lo)]
    head = far.mean(0) if len(far) else ends[1]
    d = head - butt
    return RacketObs(butt=butt, head=head, elevation_deg=float(np.degrees(np.arctan2(-d[1], d[0]))),
                     length_px=float(hi - lo), area_px=float(len(pts)))


def racket_from_polygon(poly: np.ndarray, wrist: np.ndarray) -> RacketObs | None:
    if len(poly) < 3:
        return None
    x0, y0 = np.floor(poly.min(0)).astype(int)
    x1, y1 = np.ceil(poly.max(0)).astype(int)
    m = polygon_mask(poly - [x0, y0], (y1 - y0 + 1, x1 - x0 + 1))
    ys, xs = np.nonzero(m)
    return racket_from_points(np.c_[xs + x0, ys + y0].astype(float), wrist)


def pick_racket(polys: list[np.ndarray], wrist: np.ndarray, max_dist: float) -> np.ndarray | None:
    """The outline whose nearest vertex is closest to the wrist, if within max_dist pixels."""
    best, best_d = None, max_dist
    for p in polys:
        if len(p) < 3 or np.any(np.isnan(wrist)):
            continue
        d = float(np.min(np.linalg.norm(p - wrist, axis=1)))
        if d < best_d:
            best, best_d = p, d
    return best
