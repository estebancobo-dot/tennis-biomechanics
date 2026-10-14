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
    """predict(img, conf) → boxes (N, 4) xyxy, keypoints (N, 17, 2), keypoint conf (N, 17).

    fp16: on the iGPU (dml) only, a half-precision copy of the ONNX model (float32 inputs and
    outputs; pose.variants.to_fp16). Off by default: it changes the keypoints slightly, so it is
    used only after it is validated against the full-precision model."""

    def __init__(self, name: str = "yolo11m-pose", imgsz: int = 960, device: str = "cpu", fp16: bool = False):
        self.name, self.imgsz, self.device = Path(name).stem, int(imgsz), device
        self.fp16 = False
        self.onnx = None
        path = MODELS_DIR / f"{self.name}_{self.imgsz}.onnx"
        if not path.exists() and device != "cpu":
            try:                                   # export once (needs the 'yolo' extra)
                from .yolo_onnx import export_onnx
                path = export_onnx(self.name, self.imgsz)
            except Exception:
                path = None
        if path is not None and path.exists() and fp16 and device == "dml":
            try:
                from .variants import to_fp16
                path, self.fp16 = to_fp16(path), True
            except Exception as e:
                print(f"AVISO: no se pudo preparar la copia en media precisión de {path.name} ({e}); se usa la normal")
        if path is not None and path.exists():
            try:
                from .yolo_onnx import YoloOnnx
                self.onnx = YoloOnnx(path, device)
            except Exception as e:
                print(f"AVISO: no se pudo cargar {path.name} ({e}); se usa PyTorch en la CPU")
        self.torch = None
        if self.onnx is None:
            from ultralytics import YOLO
            self.torch = YOLO(str(MODELS_DIR / f"{self.name}.pt"))     # downloaded into models/ if missing

    @property
    def backend(self) -> str:
        return (f"onnx-{self.device}" + ("-fp16" if self.fp16 else "")) if self.onnx is not None else "torch-cpu"

    def prepare(self, img: np.ndarray):
        """predict's input for img (letterbox), to compute ahead in a reader thread while the model runs
        on the previous frame; None on the PyTorch path (it prepares its own input)."""
        return self.onnx.prepare(img) if self.onnx is not None else None

    def predict(self, img: np.ndarray, conf: float = 0.3, prepared=None):
        if self.onnx is not None:
            b, _, k, c = self.onnx.pose(img, conf=conf, prepared=prepared)
            return b.astype(np.float32), k.astype(np.float32), c.astype(np.float32)
        r = self.torch.predict(img, imgsz=self.imgsz, conf=conf, verbose=False)[0]
        if not len(r.boxes):
            return np.zeros((0, 4), np.float32), np.zeros((0, 17, 2), np.float32), np.zeros((0, 17), np.float32)
        return (r.boxes.xyxy.cpu().numpy().astype(np.float32), r.keypoints.xy.cpu().numpy().astype(np.float32),
                r.keypoints.conf.cpu().numpy().astype(np.float32))


DEFAULT_DEVICE = "cpu"          # set from the config by the stages (device: dml on the Beelink)
DEFAULT_FP16 = False            # set from the config (fp16: true), used only on dml


def set_device(device: str | None, fp16: bool = False):
    global DEFAULT_DEVICE, DEFAULT_FP16
    DEFAULT_DEVICE = device or "cpu"
    DEFAULT_FP16 = bool(fp16)


def uses_fp16(cfg: dict) -> bool:
    """Whether the config asks for the half-precision pose model where it applies (the iGPU)."""
    return bool(cfg.get("fp16", False)) and cfg.get("device", "cpu") == "dml"


@lru_cache(maxsize=8)
def _cached(name: str, imgsz: int, device: str, fp16: bool = False) -> PoseModel:
    return PoseModel(name, imgsz, device, fp16)


def pose_model(name: str = "yolo11m-pose", imgsz: int = 960, device: str | None = None) -> PoseModel:
    """Loaded once per (model, size, device, precision) and reused (loading takes seconds)."""
    device = device or DEFAULT_DEVICE
    return _cached(Path(str(name)).stem, int(imgsz), device, DEFAULT_FP16 and device == "dml")
