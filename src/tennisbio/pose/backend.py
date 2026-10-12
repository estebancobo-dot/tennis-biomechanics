"""One way to run the YOLO pose model everywhere (cheap pass, fine pass, far player search).

On the Beelink the model runs as ONNX on the iGPU (DirectML); the ONNX file is exported once from
the Ultralytics weights (`scripts/setup_models.py`) at each input size used. Without the ONNX file
(or if the iGPU fails) it falls back to Ultralytics/PyTorch on the CPU, so it always works.
"""
from functools import lru_cache
from pathlib import Path

import numpy as np

from .yolo_onnx import MODELS_DIR


class PoseModel:
    """predict(img, conf) → boxes (N, 4) xyxy, keypoints (N, 17, 2), keypoint conf (N, 17)."""

    def __init__(self, name: str = "yolo11m-pose", imgsz: int = 960, device: str = "cpu"):
        self.name, self.imgsz, self.device = Path(name).stem, int(imgsz), device
        self.onnx = None
        path = MODELS_DIR / f"{self.name}_{self.imgsz}.onnx"
        if not path.exists() and device != "cpu":
            try:                                   # export once (needs the 'yolo' extra)
                from .yolo_onnx import export_onnx
                path = export_onnx(self.name, self.imgsz)
            except Exception:
                path = None
        if path is not None and path.exists():
            try:
                from .yolo_onnx import YoloOnnx
                self.onnx = YoloOnnx(path, device)
            except Exception as e:
                print(f"AVISO: no se pudo cargar {path.name} ({e}); se usa PyTorch en la CPU")
        self.torch = None
        if self.onnx is None:
            from ultralytics import YOLO
            self.torch = YOLO(f"{self.name}.pt" if not str(name).endswith(".pt") else name)

    @property
    def backend(self) -> str:
        return f"onnx-{self.device}" if self.onnx is not None else "torch-cpu"

    def predict(self, img: np.ndarray, conf: float = 0.3):
        if self.onnx is not None:
            b, _, k, c = self.onnx.pose(img, conf=conf)
            return b.astype(np.float32), k.astype(np.float32), c.astype(np.float32)
        r = self.torch.predict(img, imgsz=self.imgsz, conf=conf, verbose=False)[0]
        if not len(r.boxes):
            return np.zeros((0, 4), np.float32), np.zeros((0, 17, 2), np.float32), np.zeros((0, 17), np.float32)
        return (r.boxes.xyxy.cpu().numpy().astype(np.float32), r.keypoints.xy.cpu().numpy().astype(np.float32),
                r.keypoints.conf.cpu().numpy().astype(np.float32))


DEFAULT_DEVICE = "cpu"          # set from the config by the stages (device: dml on the Beelink)


def set_device(device: str | None):
    global DEFAULT_DEVICE
    DEFAULT_DEVICE = device or "cpu"


@lru_cache(maxsize=8)
def _cached(name: str, imgsz: int, device: str) -> PoseModel:
    return PoseModel(name, imgsz, device)


def pose_model(name: str = "yolo11m-pose", imgsz: int = 960, device: str | None = None) -> PoseModel:
    """Loaded once per (model, size, device) and reused (loading takes seconds)."""
    return _cached(Path(str(name)).stem, int(imgsz), device or DEFAULT_DEVICE)
