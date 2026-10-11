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

    exported = Path(YOLO(f"{name}.pt").export(format="onnx", imgsz=imgsz, dynamic=False, simplify=False))
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

    def pose(self, img: np.ndarray, conf=0.3, iou=0.5):
        """People in the frame: boxes (N, 4) xyxy, scores (N,), keypoints (N, 17, 2), kp conf (N, 17)."""
        x, s, (dx, dy) = letterbox(img, self.size)
        p = self.infer(x)[0][0].T                         # (anchors, 56): cx cy w h score + 17×(x, y, v)
        p = p[p[:, 4] >= conf]
        if not len(p):
            return np.zeros((0, 4)), np.zeros(0), np.zeros((0, 17, 2)), np.zeros((0, 17))
        xywh = p[:, :4]
        boxes = np.c_[xywh[:, :2] - xywh[:, 2:] / 2, xywh[:, :2] + xywh[:, 2:] / 2]
        keep = cv2.dnn.NMSBoxes(np.c_[boxes[:, :2], xywh[:, 2:]].tolist(), p[:, 4].tolist(), conf, iou)
        keep = np.array(keep).ravel()
        p, boxes = p[keep], boxes[keep]
        kp = p[:, 5:].reshape(-1, 17, 3)
        undo = lambda xy: (xy - [dx, dy]) / s
        return undo(boxes.reshape(-1, 2, 2)).reshape(-1, 4), p[:, 4], undo(kp[..., :2]), kp[..., 2]
