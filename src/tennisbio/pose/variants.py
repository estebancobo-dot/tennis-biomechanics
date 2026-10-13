"""Alternative pose models for the automatic model trials (scripts/model_trials.py).

Each variant writes the same cache as pose.yolo.extract (boxes, 17 COCO keypoints, their confidences,
appearance), so the whole stroke pipeline (clip_pipeline.run_clip) runs unchanged on it and the
variants are compared on the same task. RTMPose Halpe26 variants also keep the 6 foot points
(heels, big and small toes), which the YOLO pose model does not have.

    yolo11m-pose@960         the current model (full frame, 960 px)
    yolo11m-pose@960-fp16    the same in half precision
    yolo11m-pose@640         smaller input
    rtmpose-x                YOLOX-m detector + RTMPose-x Halpe26 384×288 on each person
    rtmpose-x-fp16           the same in half precision
    rtmpose-m                YOLOX-m + RTMPose-m Halpe26 256×192
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from ..io.video import open_capture
from ..pipeline import savez_atomic
from .yolo import _objects, appearance
from .yolo_onnx import MODELS_DIR

# in order of importance: the trials run in slices of time and the first ones finish first
VARIANTS = ["yolo11m-pose@960", "rtmpose-x", "rtmpose-m", "yolo11m-pose@960-fp16", "rtmpose-x-fp16", "yolo11m-pose@640"]
BASELINE = "yolo11m-pose@960"


def to_fp16(src: str | Path, dst: str | Path | None = None) -> Path:
    """Half-precision copy of an ONNX model (inputs and outputs stay float32), cached next to it."""
    src = Path(src)
    dst = Path(dst) if dst else src.with_name(src.stem + "_fp16.onnx")
    if dst.exists():
        return dst
    import onnx
    from onnxruntime.transformers.float16 import convert_float_to_float16

    m = convert_float_to_float16(onnx.load(str(src)), keep_io_types=True)
    tmp = dst.with_suffix(".part")
    onnx.save(m, str(tmp))
    tmp.replace(dst)
    return dst


class _Yolo:
    def __init__(self, imgsz: int, fp16: bool, device: str):
        from .backend import PoseModel
        from .yolo_onnx import YoloOnnx, export_onnx

        base = MODELS_DIR / f"yolo11m-pose_{imgsz}.onnx"
        if not base.exists():
            base = export_onnx("yolo11m-pose", imgsz)
        if fp16:
            self.m = YoloOnnx(to_fp16(base), device)
            self.pose = lambda img: self.m.pose(img, conf=0.3)
        else:
            pm = PoseModel("yolo11m-pose", imgsz, device)
            self.pose = lambda img: (lambda b, k, c: (b, None, k, c))(*pm.predict(img, conf=0.3))

    def __call__(self, frame):
        b, _, k, c = self.pose(frame)
        b = np.asarray(b, np.float32).reshape(-1, 4)
        if not len(b):
            return b, np.zeros((0, 17, 2), np.float32), np.zeros((0, 17), np.float32), None, None
        return b, np.asarray(k, np.float32), np.asarray(c, np.float32), None, None


class _Rtm:
    def __init__(self, size: str, fp16: bool, device: str):
        from ..config import load_config
        from .estimator import Detector, PoseEstimator, _ort_session

        cfg = load_config()
        det, pose = cfg["models"]["detectors"]["balanced"], cfg["models"]["poses"]["performance" if size == "x" else "balanced"]
        self.det = Detector(det["url"], det["input_size"], device)
        self.pose = PoseEstimator(pose["url"], pose["input_size"], device)
        if fp16:
            for tool in (self.det.model, self.pose.model):
                tool.session = _ort_session(str(to_fp16(tool.onnx_model)), device)

    def __call__(self, frame):
        b = self.det(frame)
        if not len(b):
            return b, np.zeros((0, 17, 2), np.float32), np.zeros((0, 17), np.float32), np.zeros((0, 6, 2), np.float32), np.zeros((0, 6), np.float32)
        k, c = self.pose(frame, b)
        k, c = np.asarray(k, np.float32), np.asarray(c, np.float32)
        return b.astype(np.float32), k[:, :17], c[:, :17], k[:, 20:26], c[:, 20:26]


def model(variant: str, device: str):
    fp16 = variant.endswith("-fp16")
    name = variant.removesuffix("-fp16")
    if name.startswith("yolo11m-pose@"):
        return _Yolo(int(name.split("@")[1]), fp16, device)
    if name.startswith("rtmpose-"):
        return _Rtm(name.split("-")[1], fp16, device)
    raise ValueError(f"variante desconocida: {variant}")


def extract_variant(video: str | Path, out: str | Path, variant: str, device: str = "cpu") -> dict:
    """Runs one variant on every frame of a clip and writes the pose cache. Returns its timing."""
    m = model(variant, device)
    cap = open_capture(video)
    fps = cap.get(5)
    boxes, kps, confs, feats, feet, feet_c = [], [], [], [], [], []
    t_inf, n = 0.0, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t0 = time.perf_counter()
        b, k, c, fk, fc = m(frame)
        t_inf += time.perf_counter() - t0
        n += 1
        boxes.append(b)
        kps.append(k)
        confs.append(c)
        feats.append(np.array([appearance(frame, bb) for bb in b], np.float32).reshape(len(b), 32))
        feet.append(fk if fk is not None else np.zeros((len(b), 6, 2), np.float32))
        feet_c.append(fc if fc is not None else np.zeros((len(b), 6), np.float32))
    cap.release()
    savez_atomic(Path(out), fps=fps, n=len(boxes), boxes=_objects(boxes), kps=_objects(kps), confs=_objects(confs),
                 feats=_objects(feats), feet=_objects(feet), feet_confs=_objects(feet_c))
    return {"frames": n, "infer_s": round(t_inf, 2), "ms_per_frame": round(1000 * t_inf / max(1, n), 1)}
