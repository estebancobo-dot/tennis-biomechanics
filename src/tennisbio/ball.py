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

    def track(self, frames, background: np.ndarray | None = None, step: int = 1) -> np.ndarray:
        """(T, 3) array of x, y (image px, NaN when not seen) and confidence for each BGR frame.

        frames: any iterable; each frame is shrunk to 512x288 as it arrives, so a long window at
        1080p does not have to fit in memory. background: median image of the shot (computed from
        the frames themselves when not given). step: run on every step-th frame (the model was
        trained at 25-30 fps: use step 2 for 50-60 fps broadcasts) and interpolate in between."""
        small, size, total = [], None, 0
        for k, f in enumerate(frames):
            total = k + 1
            if k % step:
                continue
            size = size or f.shape[:2]
            small.append(cv2.resize(f, (W, H)))          # same interpolation as in training
        if not small:
            return np.zeros((0, 3))
        h0, w0 = size
        bg = cv2.resize(background, (W, H)) if background is not None else median_background(small)
        bg = np.moveaxis(bg.astype(np.float32) / 255.0, -1, 0)
        norm = [np.moveaxis(f.astype(np.float32) / 255.0, -1, 0) for f in small]
        out = np.full((len(small), 3), np.nan)
        for s in range(0, len(small), self.batch):
            idx = range(s, min(len(small), s + self.batch))
            x = np.stack([np.concatenate([bg] + [norm[max(0, i - k)] for k in range(SEQ - 1, -1, -1)])
                          for i in idx]).astype(np.float32)
            hm = self.sess.run(None, {self.sess.get_inputs()[0].name: x})[0][:, 0]
            for i, m in zip(idx, hm):
                p = _peak(m, self.threshold)
                if p is not None:
                    out[i] = (p[0] * w0 / W, p[1] * h0 / H, p[2])
        if step == 1:
            return out
        full = np.full((total, 3), np.nan)
        full[::step] = out
        for i in range(total):                    # linear fill between two seen samples only
            if i % step and i // step + 1 < len(out):
                a, b = out[i // step], out[i // step + 1]
                if not (np.isnan(a).any() or np.isnan(b).any()):
                    full[i] = a + (b - a) * (i % step) / step
        return full


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
    side: str          # "near" (the ball then goes up the image, away from the camera) or "far"
    turn_deg: float


def turning_hits(frames: np.ndarray, xy: np.ndarray, frame_h: int, span: int, away: int,
                 away_frac=0.12, group=15, near_min_y=0.45) -> list[BallHit]:
    """Hits as the sharpest turns of the ball path after which the ball travels away.

    frames: (N,) frame numbers of the visible ball positions xy (N, 2), sorted. A bounce also
    turns the ball, but less sharply than a hit, and on the near court the ball keeps coming
    towards the camera; so each hit is the point of maximum turn in its group of candidates
    that are followed, within `away` frames, by the ball moving up the image (near player) by
    away_frac of the frame height, or down it by half that (far player).
    """
    cands = []
    for i in range(len(frames)):
        f = frames[i]
        b = np.flatnonzero((frames >= f - span) & (frames < f))
        a = np.flatnonzero((frames > f) & (frames <= f + span))
        if not len(b) or not len(a):
            continue
        vb, va = xy[i] - xy[b[0]], xy[a[-1]] - xy[i]
        if np.linalg.norm(vb) < 1e-6 or np.linalg.norm(va) < 1e-6:
            continue
        turn = float(np.degrees(np.arccos(np.clip(vb @ va / np.linalg.norm(vb) / np.linalg.norm(va), -1, 1))))
        ahead = xy[(frames > f) & (frames <= f + away), 1]
        if va[1] < 0 and xy[i, 1] > near_min_y * frame_h and ahead.min() <= xy[i, 1] - away_frac * frame_h:
            side = "near"
        elif va[1] > 0 and ahead.max() >= xy[i, 1] + 0.5 * away_frac * frame_h:
            side = "far"
        else:
            continue
        cands.append(BallHit(int(f), float(xy[i, 0]), float(xy[i, 1]), side, turn))
    out = []
    for h in cands:
        if out and h.side == out[-1].side and h.frame - out[-1].frame <= group:
            if h.turn_deg > out[-1].turn_deg:
                out[-1] = h
            continue
        out.append(h)
    return [h for h in out if h.turn_deg >= 30]


def ball_hits(track: np.ndarray, frame_h: int, fps: float, span_s=0.12, away_s=0.6) -> list[BallHit]:
    """Hits from a per-frame ball track (T, ≥2) with NaN where the ball was not seen."""
    ok = ~np.isnan(track[:, :2]).any(1)
    frames = np.flatnonzero(ok)
    return turning_hits(frames, track[ok, :2], frame_h, max(2, round(span_s * fps)), round(away_s * fps),
                        group=round(0.6 * fps))
