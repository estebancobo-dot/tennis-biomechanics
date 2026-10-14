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
    def __init__(self, onnx_path: str | Path, device="cpu", threshold=0.5, batch=8, static_batch: bool = False,
                 threads: int | None = None):
        """static_batch: the model's batch is fixed to `batch` (the last, shorter batch of a window is
        padded and the padding's heatmaps dropped): on the iGPU, DirectML then compiles the whole
        network for one shape instead of running it as a dynamic graph. Same heatmap for each frame.
        threads: CPU threads of the model (None: all cores; fine_speed.ball_ahead_threads)."""
        from .pose.estimator import _ort_session

        self.static = bool(static_batch)
        self.sess = _ort_session(str(onnx_path), device, {"n": batch} if self.static else None, threads=threads)
        self.threshold, self.batch = threshold, batch

    def track(self, frames, background: np.ndarray | None = None, step: int = 1) -> np.ndarray:
        """(T, 3) array of x, y (image px, NaN when not seen) and confidence for each BGR frame.

        frames: any iterable; each frame is shrunk to 512x288 as it arrives, so a long window at
        1080p does not have to fit in memory. background: median image of the shot (computed from
        the frames themselves when not given). step: run on every step-th frame (the model was
        trained at 25-30 fps: use step 2 for 50-60 fps broadcasts) and interpolate in between."""
        feed = BallFeed(step)
        for f in frames:
            feed.add(f)
        return self.track_feed(feed, background)

    def track_feed(self, feed: "BallFeed", background: np.ndarray | None = None) -> np.ndarray:
        """track() on frames already shrunk by a BallFeed (filled while another model reads the
        same decoded frames, so the window is decoded once)."""
        small, size, total, step = feed.small, feed.size, feed.total, feed.step
        if not small:
            return np.zeros((0, 3))
        h0, w0 = size
        bg = cv2.resize(background, (W, H)) if background is not None else median_background(small)
        bg = np.moveaxis(bg.astype(np.float32) / 255.0, -1, 0)
        # each frame as the model's float input, made when a batch needs it and kept only while a later
        # batch can still use it (the SEQ - 1 frames before it): the same values as converting all
        # frames at once, without holding a long window in float (≈ 1.8 MB per frame)
        held: dict = {}

        def norm_at(i: int) -> np.ndarray:
            if i not in held:
                held[i] = np.moveaxis(small[i].astype(np.float32) / 255.0, -1, 0)
            return held[i]
        out = np.full((len(small), 3), np.nan)
        for s in range(0, len(small), self.batch):
            for i in [i for i in held if i < s - SEQ]:
                del held[i]
            idx = range(s, min(len(small), s + self.batch))
            x = np.stack([np.concatenate([bg] + [norm_at(max(0, i - k)) for k in range(SEQ - 1, -1, -1)])
                          for i in idx]).astype(np.float32)
            if getattr(self, "static", False) and len(x) < self.batch:      # fixed batch: pad, drop after
                x = np.concatenate([x, np.repeat(x[-1:], self.batch - len(x), axis=0)])
            hm = self.sess.run(None, {self.sess.get_inputs()[0].name: x})[0][:len(idx), 0]
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


class BallFeed:
    """Every step-th BGR frame shrunk to the ball model's 512x288 as it arrives (a long window at
    1080p never has to fit in memory), plus the original size and the number of frames seen."""

    def __init__(self, step: int = 1):
        self.step, self.small, self.size, self.total = max(1, int(step)), [], None, 0

    def add(self, frame: np.ndarray):
        k = self.total
        self.total += 1
        if k % self.step:
            return
        self.size = self.size or frame.shape[:2]
        self.small.append(cv2.resize(frame, (W, H)))          # same interpolation as in training


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
        elif vb[1] < 0 and va[1] > 0 and ahead.max() >= xy[i, 1] + 0.5 * away_frac * frame_h:
            # far hit: the ball was going away (up the image) and now comes back; without the
            # first condition a bounce on the near court (descent that flattens) looked the same
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


@dataclass
class Bounce:
    frame: int
    x: float
    y: float          # image px: the ball is on the ground, so the court homography maps it exactly
    turn_deg: float


def sharpest_turn(track: np.ndarray, lo: int, hi: int, fps: float, min_turn=15.0, span_s=0.06,
                  min_y: float | None = None, max_y: float | None = None) -> Bounce | None:
    """Sharpest turn of the ball path between frames lo and hi, within an image band of rows."""
    c = turn_candidates(track, lo, hi, fps, min_turn, span_s, min_y, max_y)
    return c[0] if c else None


def turn_candidates(track: np.ndarray, lo: int, hi: int, fps: float, min_turn=15.0, span_s=0.06,
                    min_y: float | None = None, max_y: float | None = None, sep_s=0.15) -> list[Bounce]:
    """Turns of the ball path between frames lo and hi, sharpest first, one per sep_s."""
    ok = ~np.isnan(track[:, :2]).any(1)
    k = max(2, round(span_s * fps))
    found = []
    for i in range(max(lo, k), min(hi, len(track) - k)):
        if not (ok[i] and ok[i - k] and ok[i + k]):
            continue
        y = track[i, 1]
        if (min_y is not None and y < min_y) or (max_y is not None and y > max_y):
            continue
        vb, va = track[i, :2] - track[i - k, :2], track[i + k, :2] - track[i, :2]
        nb, na = np.linalg.norm(vb), np.linalg.norm(va)
        if nb < 1e-6 or na < 1e-6:
            continue
        turn = float(np.degrees(np.arccos(np.clip(vb @ va / nb / na, -1, 1))))
        if turn >= min_turn:
            found.append(Bounce(i, float(track[i, 0]), float(track[i, 1]), turn))
    out = []
    for b in sorted(found, key=lambda b: -b.turn_deg):
        if all(abs(b.frame - o.frame) > sep_s * fps for o in out):
            out.append(b)
    return out


def bounce_before(track: np.ndarray, hit_frame: int, fps: float, prev_hit: int | None = None,
                  min_turn=15.0, span_s=0.06, guard_s=0.05, min_y: float | None = None,
                  max_y: float | None = None) -> Bounce | None:
    """Bounce of the incoming ball before a near-player hit: the sharpest turn of the ball path
    between the previous hit (or 1.5 s before) and just before the hit. min_y: only below this
    image row (the near half of the court; the opponent's hit is also a sharp turn, further up)."""
    k = max(2, round(span_s * fps))
    lo = (prev_hit + k) if prev_hit is not None else hit_frame - round(1.5 * fps)
    hi = hit_frame - max(1, round(guard_s * fps))
    return sharpest_turn(track, lo, hi, fps, min_turn, span_s, min_y=min_y, max_y=max_y)


def bounce_after(track: np.ndarray, hit_frame: int, fps: float, next_hit: int | None = None,
                 max_s=1.6, min_turn=10.0, span_s=0.06, guard_s=0.15, max_y: float | None = None,
                 min_y: float | None = None) -> list[Bounce]:
    """Candidates for the bounce of the player's own shot on the far court, sharpest first: turns
    after her hit and before the opponent's next hit (or max_s). The opponent's hit, when the ball
    tracker missed it as a hit, is a sharp turn too; the caller keeps the first candidate that maps
    onto the far court (a ball in the air does not). max_y: only above this image row (far half;
    far away the image motion is small, so turns are subtler: lower min_turn)."""
    lo = hit_frame + max(1, round(guard_s * fps))
    hi = (next_hit - max(1, round(0.05 * fps))) if next_hit is not None else hit_frame + round(max_s * fps)
    return turn_candidates(track, lo, hi, fps, min_turn, span_s, min_y=min_y, max_y=max_y)[:4]


def ball_hits(track: np.ndarray, frame_h: int, fps: float, span_s=0.12, away_s=0.6) -> list[BallHit]:
    """Hits from a per-frame ball track (T, ≥2) with NaN where the ball was not seen."""
    ok = ~np.isnan(track[:, :2]).any(1)
    frames = np.flatnonzero(ok)
    hits = turning_hits(frames, track[ok, :2], frame_h, max(2, round(span_s * fps)), round(away_s * fps),
                        group=round(0.6 * fps))
    edge = round(0.2 * fps)                    # too little track around it to tell a hit from a bounce
    return [h for h in hits if edge <= h.frame < len(track) - edge]
