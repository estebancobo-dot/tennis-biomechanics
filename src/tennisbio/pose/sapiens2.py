"""#307 (21-11): Sapiens2 (Meta, 2026; the user allowed its licence) as the fine pass's refiner, in place of RTMPose-x:
`fine_pass.refine: sapiens2` (tennisbio.pose.hybrid). YOLO still finds the people; this poses the target's crop.

Chosen by measure (docs/registro_decisiones.md, Sapiens2): the 0.4B at 512x384 input shakes 36 % less than the hybrid
on the body and 7 % less on the feet, and sees the feet in every frame (96.6 % before), at 136 ms per crop on a T4.

The network runs from ONNX (scripts/export_sapiens2.py, the same heatmaps as PyTorch within 1e-6) through the project's
own session factory (CUDA, DirectML or the CPU, half precision on a GPU); its crop and its heatmap decoding are the
transformers processor's (Sapiens2ImageProcessor: an affine crop with 1.25 padding to 4:3, bicubic when it enlarges,
ImageNet normalisation; argmax refined by the Hessian of the blurred log-heatmap, «DARK»), ported to numpy and checked
against it. Its 308 points (goliath order, keypoints308.py) are taken to Halpe26 by name: COCO17 body, neck, the
hips' midpoint as hip, the six foot points; the head's top is not among them (unused by the fine pass: score 0).
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

ONNX = Path(__file__).resolve().parents[3] / "models" / "sapiens2_pose_0.4b_512x384.onnx"
SIZE = (512, 384)                              # input height, width
PADDING = 1.25
MEAN = np.array([0.485, 0.456, 0.406], np.float32) * 255.0
STD = np.array([0.229, 0.224, 0.225], np.float32) * 255.0
BLUR = 11                                      # the processor's DARK kernel (sigma 2.0, cv2's rule)
# Sapiens2's 308 points → Halpe26 (−1: none)
TO_HALPE26 = [0, 1, 2, 3, 4, 5, 6, 7, 8, 62, 41, 9, 10, 11, 12, 13, 14,      # COCO17 body
              -1, 69, -1,                                                    # head (none), neck, hip (hips' middle)
              15, 18, 16, 19, 17, 20]                                        # big toes, small toes, heels (L, R)


def crop_params(box_xyxy, size=SIZE, padding: float = PADDING) -> tuple[np.ndarray, np.ndarray]:
    """Center (x, y) and the crop's width, height in the image: the box padded and widened or heightened to 4:3."""
    x0, y0, x1, y1 = (float(v) for v in box_xyxy[:4])
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, h = (x1 - x0) * padding, (y1 - y0) * padding
    ar = size[1] / size[0]
    sw, sh = (w, w / ar) if w > h * ar else (h * ar, h)
    return np.array([cx, cy], np.float64), np.array([sw, sh], np.float64)


def crop(img_bgr: np.ndarray, box_xyxy, size=SIZE) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The network's input (1, 3, H, W) float32 for one person, and its crop's center and scale."""
    c, s = crop_params(box_xyxy, size)
    H, W = size
    sx, sy = (W - 1) / s[0], (H - 1) / s[1]
    m = np.array([[1 / sx, 0, c[0] - s[0] / 2], [0, 1 / sy, c[1] - s[1] / 2]], np.float64)
    flags = (cv2.INTER_LINEAR if min(sx, sy) < 1.0 else cv2.INTER_CUBIC) | cv2.WARP_INVERSE_MAP
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
    x = cv2.warpAffine(rgb, m, (W, H), flags=flags, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    x = (x - MEAN) / STD
    return np.ascontiguousarray(x.transpose(2, 0, 1)[None]), c, s


def decode(hm: np.ndarray, center: np.ndarray, scale: np.ndarray, idx: list[int]) -> tuple[np.ndarray, np.ndarray]:
    """Points idx of one person's heatmaps (K, h, w) in image px, refined as the processor does, and their scores."""
    h, w = hm.shape[1:]
    sigma = 0.3 * ((BLUR - 1) * 0.5 - 1) + 0.8
    pts, scores = np.zeros((len(idx), 2)), np.zeros(len(idx))
    for j, k in enumerate(idx):
        m = hm[k].astype(np.float32)
        scores[j] = float(m.max())
        i = int(m.argmax())
        x, y = float(i % w), float(i // w)
        if scores[j] <= 0:
            pts[j] = (-1.0, -1.0)
            continue
        b = cv2.GaussianBlur(m, (BLUR, BLUR), sigma, borderType=cv2.BORDER_CONSTANT)
        if b.max() > 0:
            b *= m.max() / b.max()
        lg = np.log(np.clip(b, 1e-3, 50.0))
        p = np.pad(lg, 1, mode="edge")
        xi, yi = int(x) + 1, int(y) + 1
        v = lambda dy, dx: p[yi + dy, xi + dx]  # noqa: E731
        gx, gy = 0.5 * (v(0, 1) - v(0, -1)), 0.5 * (v(1, 0) - v(-1, 0))
        eps = np.finfo(np.float32).eps
        hxx, hyy = v(0, 1) - 2 * v(0, 0) + v(0, -1) + eps, v(1, 0) - 2 * v(0, 0) + v(-1, 0) + eps
        hxy = 0.5 * (v(1, 1) - v(0, 1) - v(1, 0) + 2 * v(0, 0) - v(0, -1) - v(-1, 0) + v(-1, -1))
        det = hxx * hyy - hxy * hxy
        x -= (hyy * gx - hxy * gy) / det
        y -= (-hxy * gx + hxx * gy) / det
        pts[j] = (x, y)
    pts = pts / np.array([w - 1, h - 1]) * scale + center - 0.5 * scale
    return pts, scores


def to_halpe26(pts: np.ndarray, scores: np.ndarray, idx: list[int]) -> tuple[np.ndarray, np.ndarray]:
    at = {k: j for j, k in enumerate(idx)}
    kp, sc = np.zeros((26, 2), np.float32), np.zeros(26, np.float32)
    for h, k in enumerate(TO_HALPE26):
        if k >= 0:
            kp[h], sc[h] = pts[at[k]], scores[at[k]]
    kp[17], sc[17] = kp[0], 0.0                                  # head's top: not a Sapiens2 point
    kp[19], sc[19] = (kp[11] + kp[12]) / 2, min(sc[11], sc[12])  # hip: the hips' middle
    return kp, sc


class Sapiens2Pose:
    """callable (img, boxes (M, 4) xyxy) → Halpe26 keypoints (M, 26, 2) and scores (M, 26), as RTMPose-x's
    PoseEstimator for the hybrid."""

    name = "sapiens2-0.4b-512x384"

    def __init__(self, onnx_path: str | Path = ONNX, device: str = "cpu"):
        from .estimator import _ort_session, is_gpu
        from .variants import to_fp16

        path = to_fp16(onnx_path) if is_gpu(device) else Path(onnx_path)
        self.session = _ort_session(str(path), device)
        self.input = self.session.get_inputs()[0].name
        self.idx = sorted({k for k in TO_HALPE26 if k >= 0})

    def __call__(self, img: np.ndarray, boxes) -> tuple[np.ndarray, np.ndarray]:
        boxes = np.asarray(boxes, float).reshape(-1, 4)
        kps, scs = np.zeros((len(boxes), 26, 2), np.float32), np.zeros((len(boxes), 26), np.float32)
        for i, b in enumerate(boxes):                       # the model's batch is one crop (scripts/export_sapiens2.py)
            x, c, s = crop(img, b)
            hm = self.session.run(None, {self.input: x})[0][0]
            pts, sc = decode(hm, c, s, self.idx)
            kps[i], scs[i] = to_halpe26(pts, sc, self.idx)
        return kps, scs
