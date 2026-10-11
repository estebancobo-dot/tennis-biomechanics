"""Person detection and 2D pose (rtmlib YOLOX + RTMPose Halpe26) on a chosen device."""
import numpy as np
import onnxruntime as ort
from rtmlib import YOLOX, RTMPose

# Our device names -> ONNX Runtime providers. "openvino" uses rtmlib's OpenVINO backend instead.
ORT_PROVIDERS = {
    "cpu": ["CPUExecutionProvider"],
    "dml": ["DmlExecutionProvider", "CPUExecutionProvider"],
}


_warned: set = set()


def _ort_session(model_path: str, device: str) -> ort.InferenceSession:
    """Session on the requested device, falling back to the CPU (with a warning) when that device
    is not available or fails to load the model: the analysis is slower but never stops."""
    available = set(ort.get_available_providers())
    providers = [p for p in ORT_PROVIDERS.get(device, ORT_PROVIDERS["cpu"]) if p in available] or ["CPUExecutionProvider"]
    if device not in ORT_PROVIDERS or providers == ["CPUExecutionProvider"] and device != "cpu":
        if device not in _warned:
            print(f"AVISO: el dispositivo '{device}' no está disponible; se usa la CPU (más lento)")
            _warned.add(device)
    opts = ort.SessionOptions()
    if "DmlExecutionProvider" in providers:
        # Required by the DirectML provider.
        opts.enable_mem_pattern = False
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    try:
        return ort.InferenceSession(model_path, sess_options=opts, providers=providers)
    except Exception as e:                    # driver problem on the iGPU: CPU instead
        if providers == ["CPUExecutionProvider"]:
            raise
        print(f"AVISO: la iGPU falló al cargar {model_path} ({e}); se usa la CPU")
        return ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])


def _build(cls, model: str, input_size, device: str, **kwargs):
    backend = "openvino" if device == "openvino" else "onnxruntime"
    tool = cls(model, model_input_size=tuple(input_size), backend=backend, device="cpu", **kwargs)
    if device == "dml":
        tool.session = _ort_session(tool.onnx_model, device)
    return tool


class Detector:
    def __init__(self, model: str, input_size, device: str = "cpu"):
        self.model = _build(YOLOX, model, input_size, device)

    def __call__(self, frame: np.ndarray) -> np.ndarray:
        """Return person boxes as an (N, 4) xyxy array in frame coordinates."""
        boxes = np.asarray(self.model(frame), dtype=np.float32)
        return boxes.reshape(-1, 4)


class PoseEstimator:
    def __init__(self, model: str, input_size, device: str = "cpu"):
        self.model = _build(RTMPose, model, input_size, device)

    def __call__(self, frame: np.ndarray, boxes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Return keypoints (N, 26, 2) and scores (N, 26) for each box."""
        if len(boxes) == 0:
            return np.zeros((0, 26, 2), np.float32), np.zeros((0, 26), np.float32)
        return self.model(frame, bboxes=list(boxes))
