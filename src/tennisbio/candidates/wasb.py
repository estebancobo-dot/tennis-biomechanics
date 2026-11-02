"""WASB ball tracker (candidate; scripts/export_wasb.py): frames t-1, t, t+1 at 512x288, RGB, ImageNet-normalised,
stacked to 9 channels → a heatmap of the ball in each of the 3 frames. As in the reference project, frame t is read
from the middle heatmap: the blob above the threshold with the largest total value, its weighted centre mapped back
to the frame (WASB's own tracker, which links detections across frames, is not used).

Same output as tennisbio.ball.BallTracker.track, so the two are measured on the same task."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from ..ball import BallFeed

W, H, FRAMES = 512, 288, 3
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)


def normalise(small_bgr: np.ndarray) -> np.ndarray:
    """(3, 288, 512) float input of one frame already shrunk to 512x288 (BGR uint8)."""
    rgb = small_bgr[:, :, ::-1].astype(np.float32) / 255.0
    return ((rgb - MEAN) / STD).transpose(2, 0, 1)


def triplet_index(i: int, n: int) -> tuple[int, int, int]:
    """Frames t-1, t, t+1 of frame i in a sequence of n (the edges repeat the first / last frame)."""
    return max(0, i - 1), i, min(n - 1, i + 1)


def blob_centre(heatmap: np.ndarray, threshold: float = 0.5):
    """(x, y, peak) of the blob above threshold with the largest summed value, its centre weighted by the heatmap;
    None when nothing is above the threshold."""
    mask = (heatmap > threshold).astype(np.uint8)
    if not mask.any():
        return None
    n, lab = cv2.connectedComponents(mask)
    best = max(range(1, n), key=lambda k: float(heatmap[lab == k].sum()))
    ys, xs = np.nonzero(lab == best)
    w = heatmap[ys, xs]
    return float((xs * w).sum() / w.sum()), float((ys * w).sum() / w.sum()), float(w.max())


class WasbTracker:
    def __init__(self, onnx_path: str | Path, device: str = "cpu", threshold: float = 0.5, batch: int = 8,
                 fp16: bool = False, threads: int | None = None):
        from ..pose.estimator import _ort_session

        if fp16 and device != "cpu":
            from ..pose.variants import to_fp16
            onnx_path = to_fp16(onnx_path)
        self.sess = _ort_session(str(onnx_path), device, threads=threads)
        self.threshold, self.batch = threshold, max(1, int(batch))

    def track(self, frames, step: int = 1) -> np.ndarray:
        """(T, 3): x, y (frame px, NaN when not seen) and peak heatmap value, for each BGR frame (any iterable).
        step: every step-th frame (the model was trained at 25-30 fps), linear fill in between."""
        feed = BallFeed(step)
        for f in frames:
            feed.add(f)
        return self.track_feed(feed)

    def track_feed(self, feed: BallFeed) -> np.ndarray:
        small, total, step = feed.small, feed.total, feed.step
        if not small:
            return np.zeros((0, 3))
        h0, w0 = feed.size
        held: dict = {}

        def norm(i):
            if i not in held:
                held[i] = normalise(small[i])
            return held[i]
        out = np.full((len(small), 3), np.nan)
        name = self.sess.get_inputs()[0].name
        for s in range(0, len(small), self.batch):
            for i in [i for i in held if i < s - 1]:
                del held[i]
            idx = range(s, min(len(small), s + self.batch))
            x = np.stack([np.concatenate([norm(j) for j in triplet_index(i, len(small))]) for i in idx])
            hm = self.sess.run(None, {name: x.astype(np.float32)})[0][:, FRAMES // 2]
            for i, m in zip(idx, hm):
                p = blob_centre(m, self.threshold)
                if p is not None:
                    out[i] = (p[0] * w0 / W, p[1] * h0 / H, p[2])
        if step == 1:
            return out
        full = np.full((total, 3), np.nan)
        full[::step] = out
        for i in range(total):
            if i % step and i // step + 1 < len(out):
                a, b = out[i // step], out[i // step + 1]
                if not (np.isnan(a).any() or np.isnan(b).any()):
                    full[i] = a + (b - a) * (i % step) / step
        return full
