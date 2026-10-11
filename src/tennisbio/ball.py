"""Ball detection (RacketVision TrackNetV3 exported to ONNX) and ball-based hit detection.

The network sees the last 4 frames plus a median background of the shot, at 512x288, and
returns a heatmap of the ball in the last frame. Export: scripts/export_balltrack.py.
"""
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

W, H, SEQ = 512, 288, 4


def median_background(frames: list[np.ndarray], max_frames=60) -> np.ndarray:
    idx = np.linspace(0, len(frames) - 1, min(max_frames, len(frames))).astype(int)
    return np.median(np.stack([frames[i] for i in idx]), axis=0).astype(np.uint8)


class BallTracker:
    def __init__(self, onnx_path: str | Path, device="cpu", threshold=0.5, batch=8):
        from .pose.estimator import _ort_session

        self.sess = _ort_session(str(onnx_path), device)
        self.threshold, self.batch = threshold, batch

    def track(self, frames: list[np.ndarray], background: np.ndarray | None = None) -> np.ndarray:
        """(T, 3) array of x, y (image px, NaN when not seen) and confidence for each frame (BGR)."""
        h0, w0 = frames[0].shape[:2]
        small = np.stack([cv2.resize(f, (W, H)) for f in frames]).astype(np.float32) / 255.0
        bg = cv2.resize(background if background is not None else median_background(frames), (W, H))
        bg = np.moveaxis(bg.astype(np.float32) / 255.0, -1, 0)
        out = np.full((len(frames), 3), np.nan)
        for s in range(0, len(frames), self.batch):
            idx = range(s, min(len(frames), s + self.batch))
            x = np.stack([np.concatenate([bg] + [np.moveaxis(small[max(0, i - k)], -1, 0) for k in range(SEQ - 1, -1, -1)])
                          for i in idx]).astype(np.float32)
            hm = self.sess.run(None, {self.sess.get_inputs()[0].name: x})[0][:, 0]
            for i, m in zip(idx, hm):
                p = _peak(m, self.threshold)
                if p is not None:
                    out[i] = (p[0] * w0 / W, p[1] * h0 / H, p[2])
        return out


def _peak(heatmap: np.ndarray, threshold: float):
    """Centre of the largest blob above threshold (as the reference inference) and its mean value."""
    mask = (heatmap > threshold).astype(np.uint8)
    if not mask.any():
        return None
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    x, y, w, h = max((cv2.boundingRect(c) for c in cnts), key=lambda r: r[2] * r[3])
    return x + w / 2, y + h / 2, float(heatmap[y:y + h, x:x + w].mean())


def clean_track(track: np.ndarray, max_jump_frac=0.08, width=1920) -> np.ndarray:
    """Drop isolated detections that jump far from both neighbours (false positives)."""
    t = track.copy()
    xy = t[:, :2]
    lim = max_jump_frac * width
    for i in range(1, len(t) - 1):
        if np.isnan(xy[i]).any():
            continue
        d = [np.linalg.norm(xy[i] - xy[j]) for j in (i - 1, i + 1) if not np.isnan(xy[j]).any()]
        if d and min(d) > lim:
            t[i] = np.nan
    return t


@dataclass
class BallHit:
    frame: int
    x: float
    y: float
    side: str          # "near" (moving away after the hit) or "far"
    turn_deg: float


def ball_hits(track: np.ndarray, frame_h: int, fps: float, min_gap_s=0.5, span_s=0.2) -> list[BallHit]:
    """Hits from the ball track: the ball's vertical image motion reverses.

    Near player: the ball comes down the image (towards the camera) and goes back up after the hit.
    A bounce on the near court also slows the descent but the ball keeps coming down afterwards,
    so the reversal must hold for `span_s` on both sides. Far player: the opposite reversal near
    the top of the court.
    """
    xy = track[:, :2]
    T = len(xy)
    k = max(2, round(span_s * fps))
    hits = []
    for i in range(k, T - k):
        if np.isnan(xy[i]).any():
            continue
        before = xy[i - k:i][~np.isnan(xy[i - k:i]).any(1)]
        after = xy[i + 1:i + k + 1][~np.isnan(xy[i + 1:i + k + 1]).any(1)]
        if len(before) < 2 or len(after) < 2:
            continue
        vb = (xy[i] - before[0]) / max(1, i - (i - k))
        va = (after[-1] - xy[i]) / max(1, k)
        side = None
        if vb[1] > 0 and va[1] < 0 and xy[i, 1] >= np.nanmax(np.r_[before[:, 1], after[:, 1]]) - 1:
            side = "near"
        elif vb[1] < 0 and va[1] > 0 and xy[i, 1] <= np.nanmin(np.r_[before[:, 1], after[:, 1]]) + 1:
            side = "far"
        if side is None:
            continue
        cos = vb @ va / (np.linalg.norm(vb) * np.linalg.norm(va) + 1e-9)
        hits.append(BallHit(i, float(xy[i, 0]), float(xy[i, 1]), side, float(np.degrees(np.arccos(np.clip(cos, -1, 1))))))
    out = []                                  # one hit per reversal (keep the sharpest)
    for h in hits:
        if out and h.side == out[-1].side and h.frame - out[-1].frame < min_gap_s * fps:
            if h.turn_deg > out[-1].turn_deg:
                out[-1] = h
            continue
        out.append(h)
    return out
