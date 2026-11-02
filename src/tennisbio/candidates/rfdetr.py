"""RF-DETR Medium person detector (candidate; scripts/export_rfdetr.py). The frame is resized to the model's square
input (bilinear without antialias, as RF-DETR's own predict()), RGB, /255, ImageNet-normalised. Each of its 300
queries has a box (cx, cy, w, h, normalised) and independent class sigmoids; a person is a query whose person score
(COCO id 1) is above the threshold. No NMS: DETR models give one query per object."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

PERSON = 1
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)


def decode_people(dets: np.ndarray, logits: np.ndarray, width: int, height: int, threshold: float) -> np.ndarray:
    """(N, 5) x1 y1 x2 y2 score (frame px) of the queries whose person score is above threshold, best first."""
    score = 1.0 / (1.0 + np.exp(-np.clip(logits[:, PERSON], -88, 88)))
    keep = np.flatnonzero(score > threshold)
    keep = keep[np.argsort(-score[keep])]
    cx, cy, bw, bh = dets[keep].T
    out = np.stack([(cx - bw / 2) * width, (cy - bh / 2) * height, (cx + bw / 2) * width, (cy + bh / 2) * height,
                    score[keep]], 1) if len(keep) else np.zeros((0, 5))
    return out.astype(np.float32)


class RfDetrPeople:
    def __init__(self, onnx_path: str | Path, device: str = "cpu", threshold: float = 0.3):
        from ..pose.estimator import _ort_session

        self.sess = _ort_session(str(onnx_path), device)
        shape = self.sess.get_inputs()[0].shape
        self.size = int(shape[-1]) if isinstance(shape[-1], int) else 1152
        self.threshold = threshold
        self.names = [o.name for o in self.sess.get_outputs()]

    def prepare(self, bgr: np.ndarray) -> np.ndarray:
        rgb = cv2.resize(bgr, (self.size, self.size), interpolation=cv2.INTER_LINEAR)[:, :, ::-1]
        return ((rgb.astype(np.float32) / 255.0 - MEAN) / STD).transpose(2, 0, 1)

    def people(self, frames: list[np.ndarray]) -> list[np.ndarray]:
        """Per BGR frame: (N, 5) x1 y1 x2 y2 score of the people found."""
        if not frames:
            return []
        x = np.stack([self.prepare(f) for f in frames])
        out = dict(zip(self.names, self.sess.run(None, {self.sess.get_inputs()[0].name: x})))
        return [decode_people(out["dets"][k], out["labels"][k], f.shape[1], f.shape[0], self.threshold)
                for k, f in enumerate(frames)]
