"""RTMW-x 2D whole-body pose (candidate; scripts/export_rtmw.py): 133 COCO-WholeBody points per person box, given
here in our Halpe26 layout so the stroke pipeline reads it unchanged: the 17 body points are the same, the feet
come from the whole-body feet (17-22), and Halpe's head, neck and hip centre are made from the body points.

For the trial (scripts/bench_candidates.py) RTMW-x replaces RTMPose-x in the cascade of the fine pass
(tennisbio.pose.hybrid): YOLO11m-pose finds every person and RTMW-x runs on the big ones."""
from __future__ import annotations

from pathlib import Path

import numpy as np

INPUT_SIZE = (288, 384)                 # w, h
# COCO-WholeBody feet: 17 left big toe, 18 left small toe, 19 left heel, 20 right big toe, 21 right small toe,
# 22 right heel → Halpe26 20-25 (left/right big toe, left/right small toe, left/right heel)
WB_FEET = [17, 20, 18, 21, 19, 22]
MIN_REL_HEIGHT = 0.6


def to_halpe26(kps: np.ndarray, scores: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(N, 133, 2) and (N, 133) whole-body points → (N, 26, 2) and (N, 26) in Halpe26 order."""
    kps, scores = np.asarray(kps, np.float32), np.asarray(scores, np.float32)
    n = len(kps)
    k, s = np.zeros((n, 26, 2), np.float32), np.zeros((n, 26), np.float32)
    if not n:
        return k, s
    k[:, :17], s[:, :17] = kps[:, :17], scores[:, :17]
    k[:, 17], s[:, 17] = kps[:, 0], scores[:, 0]                                     # head: the nose
    k[:, 18], s[:, 18] = kps[:, [5, 6]].mean(1), scores[:, [5, 6]].min(1)              # neck: between the shoulders
    k[:, 19], s[:, 19] = kps[:, [11, 12]].mean(1), scores[:, [11, 12]].min(1)          # hip: between the hips
    k[:, 20:26], s[:, 20:26] = kps[:, WB_FEET], scores[:, WB_FEET]
    return k, s


class RtmwPose:
    """callable (frame, boxes (M, 4) xyxy) → Halpe26 keypoints (M, 26, 2), scores (M, 26), like
    tennisbio.pose.estimator.PoseEstimator (the `rtm` of tennisbio.pose.hybrid.HybridPose)."""

    def __init__(self, onnx_path: str | Path, device: str = "cpu"):
        from ..pose.estimator import PoseEstimator

        self.est = PoseEstimator(str(onnx_path), INPUT_SIZE, device)

    def __call__(self, frame: np.ndarray, boxes: np.ndarray):
        boxes = np.asarray(boxes, np.float32).reshape(-1, 4)
        if not len(boxes):
            return np.zeros((0, 26, 2), np.float32), np.zeros((0, 26), np.float32)
        k, s = self.est.model(frame, bboxes=list(boxes))
        return to_halpe26(k, s)


class HybridRtmw:
    """The trial model (same call as tennisbio.pose.variants' models: frame → boxes, 17 keypoints, their
    confidences, 6 foot points, their confidences): YOLO11m-pose (half precision on the iGPU, as in the fine pass)
    finds every person; RTMW-x refines the ones at least MIN_REL_HEIGHT as tall as the tallest."""

    def __init__(self, onnx_path: str | Path, device: str = "cpu"):
        from ..pose.variants import _Yolo

        self.yolo = _Yolo(960, True, device)
        self.rtm = RtmwPose(onnx_path, device)

    def __call__(self, frame):
        b, k, c, _, _ = self.yolo(frame)
        fk, fc = np.zeros((len(b), 6, 2), np.float32), np.zeros((len(b), 6), np.float32)
        if not len(b):
            return b, k, c, fk, fc
        h = b[:, 3] - b[:, 1]
        big = np.where(h >= MIN_REL_HEIGHT * h.max())[0]
        rk, rc = self.rtm(frame, b[big])
        k, c = k.copy(), c.copy()
        k[big], c[big] = rk[:, :17], rc[:, :17]
        fk[big], fc[big] = rk[:, 20:26], rc[:, 20:26]
        return b, k, c, fk, fc
