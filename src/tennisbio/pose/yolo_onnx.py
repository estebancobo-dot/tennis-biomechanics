"""YOLO pose / segmentation exported to ONNX and run with ONNX Runtime (cpu, dml) or OpenVINO.

This is the Windows path without PyTorch at inference time: the .pt weights are exported once
(needs `uv sync --extra yolo`) and the .onnx file is reused.
"""
from pathlib import Path

import cv2
import numpy as np

from .estimator import _ort_session

MODELS_DIR = Path(__file__).resolve().parents[3] / "models"


def export_onnx(name: str, imgsz: int, models_dir: Path = MODELS_DIR) -> Path:
    """Export e.g. 'yolo11m-pose' at a fixed input size; cached as models/<name>_<imgsz>.onnx."""
    models_dir.mkdir(parents=True, exist_ok=True)
    target = models_dir / f"{name}_{imgsz}.onnx"
    if target.exists():
        return target
    from ultralytics import YOLO

    # weights kept in models/ (downloaded there the first time), never in the current directory
    exported = Path(YOLO(str(models_dir / f"{name}.pt")).export(format="onnx", imgsz=imgsz, dynamic=False, simplify=False))
    exported.replace(target)
    return target


def letterbox(img: np.ndarray, size: int):
    """Resize keeping aspect ratio and pad to size×size. Returns NCHW float input, scale, (dx, dy)."""
    h, w = img.shape[:2]
    s = size / max(h, w)
    nh, nw = round(h * s), round(w * s)
    canvas = np.full((size, size, 3), 114, np.uint8)
    dy, dx = (size - nh) // 2, (size - nw) // 2
    canvas[dy:dy + nh, dx:dx + nw] = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    x = canvas[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0
    return np.ascontiguousarray(x), s, (dx, dy)


class YoloOnnx:
    """Runs an exported YOLO model on 'cpu', 'dml' or 'openvino'."""

    def __init__(self, path: str | Path, device: str = "cpu"):
        self.path, self.device = str(path), device
        if device == "openvino":
            from openvino import Core

            self.compiled = Core().compile_model(self.path, "CPU")
            self.size = int(self.compiled.input(0).shape[2])
        else:
            self.session = _ort_session(self.path, device)
            self.size = int(self.session.get_inputs()[0].shape[2])

    def infer(self, x: np.ndarray) -> list[np.ndarray]:
        if self.device == "openvino":
            res = self.compiled(x)
            return [res[o] for o in self.compiled.outputs]
        return self.session.run(None, {self.session.get_inputs()[0].name: x})

    def prepare(self, img: np.ndarray):
        """The model's input for img (letterbox): can be computed ahead, in another thread."""
        return letterbox(img, self.size)

    def pose(self, img: np.ndarray, conf=0.3, iou=0.5, prepared=None):
        """People in the frame: boxes (N, 4) xyxy, scores (N,), keypoints (N, 17, 2), kp conf (N, 17).
        prepared: prepare(img) when already computed (the same input, so the same result)."""
        x, s, (dx, dy) = prepared if prepared is not None else letterbox(img, self.size)
        p = self.infer(x)[0][0].T                         # (anchors, 56): cx cy w h score + 17×(x, y, v)
        p = p[p[:, 4] >= conf]
        if not len(p):
            return np.zeros((0, 4)), np.zeros(0), np.zeros((0, 17, 2)), np.zeros((0, 17))
        xywh = p[:, :4]
        boxes = np.c_[xywh[:, :2] - xywh[:, 2:] / 2, xywh[:, :2] + xywh[:, 2:] / 2]
        keep = cv2.dnn.NMSBoxes(np.c_[boxes[:, :2], xywh[:, 2:]].tolist(), p[:, 4].tolist(), conf, iou)
        keep = np.array(keep, dtype=int).ravel()       # NMS may keep nothing: an empty float array is no index
        p, boxes = p[keep], boxes[keep]
        kp = p[:, 5:].reshape(-1, 17, 3)
        undo = lambda xy: (xy - [dx, dy]) / s
        return undo(boxes.reshape(-1, 2, 2)).reshape(-1, 4), p[:, 4], undo(kp[..., :2]), kp[..., 2]

    def segment(self, img: np.ndarray, cls: int, conf=0.15, iou=0.7, n_classes=80) -> list[np.ndarray]:
        """Outlines (polygons (n, 2) in image px) of the objects of one class, as Ultralytics'
        masks.xy: box + 32 mask coefficients per detection, combined with the prototype masks."""
        h0, w0 = img.shape[:2]
        x, s, (dx, dy) = letterbox(img, self.size)
        out = self.infer(x)
        p, protos = out[0][0].T, out[1][0]                 # (anchors, 4 + classes + 32), (32, mh, mw)
        score = p[:, 4 + cls]
        keep = score >= conf
        p, score = p[keep], score[keep]
        if not len(p):
            return []
        xywh = p[:, :4]
        boxes = np.c_[xywh[:, :2] - xywh[:, 2:] / 2, xywh[:, :2] + xywh[:, 2:] / 2]
        idx = np.array(cv2.dnn.NMSBoxes(np.c_[boxes[:, :2], xywh[:, 2:]].tolist(), score.tolist(), conf, iou)).ravel()
        nm, mh, mw = protos.shape
        coef = p[idx, 4 + n_classes:4 + n_classes + nm]
        masks = 1 / (1 + np.exp(-(coef @ protos.reshape(nm, -1)))).reshape(-1, mh, mw)
        polys = []
        r = mw / self.size                                  # letterbox px → prototype px
        for m, b in zip(masks, boxes[idx]):
            x0, y0, x1, y1 = (b * r).round().astype(int)
            crop = np.zeros_like(m)
            crop[max(0, y0):max(0, y1), max(0, x0):max(0, x1)] = m[max(0, y0):max(0, y1), max(0, x0):max(0, x1)]
            up = cv2.resize(crop, (self.size, self.size), interpolation=cv2.INTER_LINEAR)
            nh, nw = round(h0 * s), round(w0 * s)
            up = up[dy:dy + nh, dx:dx + nw]
            full = cv2.resize(up, (w0, h0), interpolation=cv2.INTER_LINEAR) > 0.5
            cs, _ = cv2.findContours(full.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            if cs:                                          # all pieces, as Ultralytics' masks.xy
                polys.append(np.concatenate([c.reshape(-1, 2) for c in cs]).astype(np.float32))
        return polys
