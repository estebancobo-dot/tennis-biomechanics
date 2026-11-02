"""TennisCourtDetector (candidate; scripts/export_court_tcd.py): 14 court points from one broadcast frame, with the
post-processing of its repository (TennisCourtDetector, MIT): a circle on each heatmap, the point moved to the
crossing of the white lines around it, and the homography of the best of its 12 four-point configurations, from
which all 14 points are re-projected. Here the homography maps our court frame (metres, tennisbio.court) to the
image, so the result is a tennisbio.court.CourtFit like the line-based fit's.

Point order (TennisCourtDetector's): 0-1 far baseline (left, right), 2-3 near baseline, 4-5 left singles line (far,
near end), 6-7 right singles line, 8-9 far service line, 10-11 near service line, 12-13 centre service line (far,
near end)."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from ..court import LENGTH, NET_Y, SERVICE, W_DOUBLES, W_SINGLES, CourtFit

IN_W, IN_H = 640, 360            # network input
REF_W, REF_H = 1280, 720         # the frame size its post-processing works at (heatmap scale 2)
_D, _S, _FS, _NS = W_DOUBLES / 2, W_SINGLES / 2, NET_Y + SERVICE, NET_Y - SERVICE
REF = np.array([[-_D, LENGTH], [_D, LENGTH], [-_D, 0], [_D, 0],
                [-_S, LENGTH], [-_S, 0], [_S, LENGTH], [_S, 0],
                [-_S, _FS], [_S, _FS], [-_S, _NS], [_S, _NS],
                [0, _FS], [0, _NS]], np.float64)
# its 12 court configurations (court_reference.py), as indices of the 14 points
CONFS = [[0, 1, 2, 3], [4, 6, 5, 7], [4, 1, 5, 3], [0, 6, 2, 7], [8, 9, 10, 11], [8, 9, 5, 7], [4, 6, 10, 11],
         [6, 1, 7, 3], [0, 4, 2, 5], [8, 12, 10, 13], [12, 9, 13, 11], [10, 11, 5, 7]]
NO_REFINE = (8, 9, 12)


def heatmap_point(heatmap: np.ndarray, low_thresh: int = 170, min_radius: int = 10, max_radius: int = 25):
    """postprocess.postprocess: the first Hough circle of the thresholded heatmap (sigmoid values 0-1), in REF_W x
    REF_H pixels; None when there is none."""
    hm = (np.clip(heatmap, 0, 1) * 255).astype(np.uint8)
    _, hm = cv2.threshold(hm, low_thresh, 255, cv2.THRESH_BINARY)
    c = cv2.HoughCircles(hm, cv2.HOUGH_GRADIENT, dp=1, minDist=20, param1=50, param2=2, minRadius=min_radius,
                         maxRadius=max_radius)
    if c is None:
        return None
    return float(c[0][0][0]) * 2, float(c[0][0][1]) * 2


def _intersection(l1, l2):
    x1, y1, x2, y2 = (float(v) for v in l1)
    x3, y3, x4, y4 = (float(v) for v in l2)
    d = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(d) < 1e-9:
        return None
    a, b = x1 * y2 - y1 * x2, x3 * y4 - y3 * x4
    return (a * (x3 - x4) - (x1 - x2) * b) / d, (a * (y3 - y4) - (y1 - y2) * b) / d


def _merge_lines(lines):
    lines = sorted([np.asarray(l, float) for l in lines], key=lambda l: l[0])
    keep, out = [True] * len(lines), []
    for i, line in enumerate(lines):
        if not keep[i]:
            continue
        for j in range(i + 1, len(lines)):
            if keep[j] and np.hypot(*(line[:2] - lines[j][:2])) < 20 and np.hypot(*(line[2:] - lines[j][2:])) < 20:
                line = np.round((line + lines[j]) / 2)
                keep[j] = False
        out.append(line)
    return out


def refine_point(img: np.ndarray, x: float, y: float, crop: int = 40) -> tuple[float, float]:
    """postprocess.refine_kps: the crossing of the two white lines in the crop around (x, y) of a REF_W x REF_H
    BGR frame, when exactly two lines are found there and they cross inside it; (x, y) otherwise."""
    h, w = img.shape[:2]
    x, y = int(x), int(y)
    r0, r1, c0, c1 = max(y - crop, 0), min(h, y + crop), max(x - crop, 0), min(w, x + crop)
    patch = img[r0:r1, c0:c1]
    if patch.size == 0:
        return x, y
    gray = cv2.threshold(cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY), 155, 255, cv2.THRESH_BINARY)[1]
    found = cv2.HoughLinesP(gray, 1, np.pi / 180, 30, minLineLength=10, maxLineGap=30)
    lines = [] if found is None else list(np.asarray(found).reshape(-1, 4))     # (N, 1, 4) or (N, 4) by version
    if len(lines) > 1:
        lines = _merge_lines(lines)
        if len(lines) == 2:
            p = _intersection(lines[0], lines[1])
            if p is not None and 0 < p[0] < patch.shape[1] and 0 < p[1] < patch.shape[0]:
                return c0 + int(p[0]), r0 + int(p[1])
    return x, y


def best_homography(pts: np.ndarray) -> np.ndarray | None:
    """homography.get_trans_matrix: court (metres) → image from the configuration whose projection lies closest,
    on average, to the other detected points among the first 12 (NaN rows = not found)."""
    best, best_d = None, np.inf
    for inds in CONFS:
        if np.isnan(pts[inds]).any():
            continue
        m, _ = cv2.findHomography(REF[inds].astype(np.float32), pts[inds].astype(np.float32), method=0)
        if m is None:
            continue
        proj = cv2.perspectiveTransform(REF[:, None].astype(np.float32), m).reshape(-1, 2)
        others = [i for i in range(12) if i not in inds and not np.isnan(pts[i]).any()]
        d = float(np.mean(np.linalg.norm(proj[others] - pts[others], axis=1))) if others else np.inf
        if d < best_d or best is None:
            best, best_d = m, d
    return best


class CourtTcd:
    def __init__(self, onnx_path: str | Path, device: str = "cpu", refine: bool = True):
        from ..pose.estimator import _ort_session

        self.sess = _ort_session(str(onnx_path), device)
        self.refine = refine

    def heatmaps(self, frames: list[np.ndarray]) -> np.ndarray:
        """(n, 15, 360, 640) heatmaps of BGR frames of any size."""
        x = np.stack([cv2.resize(f, (IN_W, IN_H)).astype(np.float32).transpose(2, 0, 1) / 255.0 for f in frames])
        return self.sess.run(None, {self.sess.get_inputs()[0].name: x})[0]

    def points(self, frame: np.ndarray, heatmaps: np.ndarray | None = None) -> np.ndarray:
        """(14, 2) points as detected (before the homography), in pixels of `frame`; NaN where none is found."""
        h, w = frame.shape[:2]
        img = frame if (w, h) == (REF_W, REF_H) else cv2.resize(frame, (REF_W, REF_H), interpolation=cv2.INTER_AREA)
        hm = self.heatmaps([img])[0] if heatmaps is None else heatmaps
        pts = np.full((14, 2), np.nan)
        for k in range(14):
            p = heatmap_point(hm[k])
            if p is None:
                continue
            if self.refine and k not in NO_REFINE:
                p = refine_point(img, *p)
            pts[k] = p
        return pts * [w / REF_W, h / REF_H]

    def fit(self, frame: np.ndarray) -> CourtFit | None:
        """The court of one frame as a CourtFit (court metres → image px), None when no configuration is found.
        Its score is the share of the 14 points the network found."""
        pts = self.points(frame)
        m = best_homography(pts)
        return None if m is None else CourtFit(m, float(np.isfinite(pts[:, 0]).mean()))
