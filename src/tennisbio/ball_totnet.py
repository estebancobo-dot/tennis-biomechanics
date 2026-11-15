"""T15 (15-11): TOTNet (github.com/AugustRushG/TOTNet, MIT, tennis weights) as a ball tracker candidate, in ONNX
(scripts/export_totnet.py). Its input is the 5 frames ending at the frame it answers for (RGB, 512x288, ImageNet mean
and std); its output, one softmax over every pixel: the ball is the most likely pixel and its probability the
confidence. Same answer as tennisbio.ball.BallTracker: (T, 3) x, y (image px, NaN when not seen) and confidence.

Measured against TrackNetV3 by tennisbio.infra.poc_bola; nothing of the analysis uses it until a measure says so."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

W, H, N = 512, 288, 5
# 15-11: a missing ball is written (-1, -1) in its training labels and clamped into the map; with its horizontal flips
# it lands on one of the two top corners, so a peak there is TOTNet's «no ball» (seen on RacketVision: (1918, 2) of a
# 1920x1080 frame wherever the annotation had the ball elsewhere)
NO_BALL = {(0, 0), (W - 1, 0)}
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)


def prep(frame: np.ndarray) -> np.ndarray:
    """A BGR frame as TOTNet's input (3, 288, 512): as its own loader (resize, RGB, /255, mean and std)."""
    rgb = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), (W, H)).astype(np.float32) / 255.0
    return np.ascontiguousarray(((rgb - MEAN) / STD).transpose(2, 0, 1))


def peak(heatmap: np.ndarray, size: tuple[int, int]) -> tuple[float, float, float]:
    """The most likely pixel of a (288, 512) heatmap, in image px of an (h, w) frame, and its probability; NaN position
    when the peak is TOTNet's «no ball» corner."""
    k = int(np.argmax(heatmap))
    y, x = divmod(k, W)
    if (x, y) in NO_BALL:
        return np.nan, np.nan, float(heatmap.flat[k])
    h0, w0 = size
    return (x + 0.5) * w0 / W, (y + 0.5) * h0 / H, float(heatmap.flat[k])


class TotNetTracker:
    def __init__(self, onnx_path: str | Path, device: str = "cpu", threshold: float = 0.0):
        from .pose.estimator import _ort_session

        self.sess = _ort_session(str(onnx_path), device)
        self.input = self.sess.get_inputs()[0].name
        self.threshold = float(threshold)

    def window(self, inputs: list[np.ndarray], size: tuple[int, int]) -> tuple[float, float, float]:
        """x, y (px of an (h, w) frame) and probability of the ball in the last of 5 prepared frames (prep)."""
        hm = self.sess.run(None, {self.input: np.stack(inputs)[None]})[0][0]
        return peak(hm, size)

    def at(self, frames: list[np.ndarray], i: int, step: int = 1) -> tuple[float, float, float]:
        """x, y and probability of the ball in frame i; its window: frames i-4*step..i every `step` (the pipeline's,
        max(1, round(fps / 25)): it was trained at ~25-30 fps), the first repeated before 0."""
        return self.window([prep(frames[max(0, i - k * step)]) for k in range(N - 1, -1, -1)], frames[i].shape[:2])

    def track(self, frames: list[np.ndarray], only: set[int] | None = None, step: int = 1) -> np.ndarray:
        """(T, 3): x, y, probability per frame; NaN position below the threshold. `only`: just those frames (the rest
        NaN), e.g. the annotated ones of a measured clip."""
        out = np.full((len(frames), 3), np.nan)
        for i in range(len(frames)):
            if only is not None and i not in only:
                continue
            x, y, p = self.at(frames, i, step)
            out[i] = (x, y, p) if p >= self.threshold else (np.nan, np.nan, p)
        return out
