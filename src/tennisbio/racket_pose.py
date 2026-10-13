"""Racket keypoints with the RacketVision RTMPose model (ONNX, scripts/export_racketpose.py).

Top-down: a racket box (from YOLO segmentation) → 256x256 crop → 5 keypoints:
0 top (tip), 1 bottom (throat), 2 handle (butt), 3 left, 4 right (frame edges, image sides).
"""
from pathlib import Path

import cv2
import numpy as np

TIP, THROAT, BUTT, LEFT, RIGHT = range(5)
SIZE, SPLIT = 256, 2.0
MEAN = np.array([123.675, 116.28, 103.53], np.float32)
STD = np.array([58.395, 57.12, 57.375], np.float32)


def _affine(box, padding=1.25):
    """2x3 matrix mapping the padded square around box (xyxy) onto the SIZE x SIZE input."""
    x0, y0, x1, y1 = box
    c = np.array([(x0 + x1) / 2, (y0 + y1) / 2])
    s = max(x1 - x0, y1 - y0) * padding
    k = SIZE / s
    return np.array([[k, 0, SIZE / 2 - k * c[0]], [0, k, SIZE / 2 - k * c[1]]], np.float32)


class RacketPose:
    def __init__(self, onnx_path: str | Path, device="cpu"):
        from .pose.estimator import _ort_session

        self.sess = _ort_session(str(onnx_path), device)

    def __call__(self, frame: np.ndarray, boxes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Keypoints (N, 5, 2) in image px and scores (N, 5) for each box (N, 4) xyxy of a BGR frame."""
        boxes = np.asarray(boxes, float).reshape(-1, 4)
        if not len(boxes):
            return np.zeros((0, 5, 2)), np.zeros((0, 5))
        return self._run([(frame, b) for b in boxes])

    def many(self, items: list, batch: int = 16) -> tuple[np.ndarray, np.ndarray]:
        """One racket box in each of many frames: items = [(frame, box xyxy), ...] → keypoints
        (N, 5, 2) and scores (N, 5), as calling the model frame by frame, but `batch` crops per run
        (the model takes any batch size; one run per frame cost a call each on the iGPU)."""
        kps, scores = [np.zeros((0, 5, 2))], [np.zeros((0, 5))]
        for s in range(0, len(items), max(1, batch)):
            k, sc = self._run([(f, np.asarray(b, float).reshape(4)) for f, b in items[s:s + batch]])
            kps.append(k)
            scores.append(sc)
        return np.concatenate(kps), np.concatenate(scores)

    def _run(self, items: list) -> tuple[np.ndarray, np.ndarray]:
        mats = [_affine(b) for _, b in items]
        crops = [cv2.warpAffine(f, m, (SIZE, SIZE), flags=cv2.INTER_LINEAR) for (f, _), m in zip(items, mats)]
        x = np.stack([((c[..., ::-1].astype(np.float32) - MEAN) / STD).transpose(2, 0, 1) for c in crops])
        sx, sy = self.sess.run(None, {self.sess.get_inputs()[0].name: x})
        px, py = sx.argmax(-1) / SPLIT, sy.argmax(-1) / SPLIT
        score = np.minimum(sx.max(-1), sy.max(-1))
        kps = np.zeros((len(items), 5, 2))
        for n, m in enumerate(mats):
            k = m[0, 0]
            kps[n, :, 0] = (px[n] - m[0, 2]) / k
            kps[n, :, 1] = (py[n] - m[1, 2]) / k
        return kps, score
