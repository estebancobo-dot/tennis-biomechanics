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


# Signs of a lost GPU (Windows DXGI): driver reset, device removed/suspended/hung. Seen on the PC (28-10)
# in the middle of a fine pass: every later stroke failed until the process ended.
DEVICE_LOST = ("887a0005", "887a0006", "887a0007", "887a0020", "device instance has been suspended",
               "device removed", "device_removed", "device hung", "device_hung", "device reset")
_dml_lost = False          # once the iGPU has been lost twice in this process, new sessions go to the CPU


def device_lost(e: BaseException) -> bool:
    msg = str(e).lower()
    return any(k in msg for k in DEVICE_LOST)


class RecoveringSession:
    """An ONNX Runtime session that survives the iGPU being lost while it runs: the session is made
    again on the iGPU once (a driver reset usually comes back) and, if that fails too, on the CPU;
    the same call is then repeated, so no frame or stroke is lost. Other errors are raised as before.
    Everything else (get_inputs, get_providers, ...) is the wrapped session's."""

    def __init__(self, make, device: str):
        self._make, self._device = make, device
        self._sess = make(device)
        self.recoveries = 0

    def __getattr__(self, name):
        return getattr(self._sess, name)

    def run(self, *args, **kwargs):
        global _dml_lost
        try:
            return self._sess.run(*args, **kwargs)
        except Exception as e:                    # noqa: BLE001 — only a lost device is handled
            if not device_lost(e) or self._sess.get_providers() == ["CPUExecutionProvider"]:
                raise
            first = str(e)[:160]
        self.recoveries += 1
        if not _dml_lost:
            print(f"AVISO: la iGPU se perdió ({first}); se vuelve a crear la sesión en la iGPU")
            try:
                self._sess = self._make(self._device)
                return self._sess.run(*args, **kwargs)
            except Exception as e:                # noqa: BLE001
                print(f"AVISO: la iGPU sigue sin responder ({str(e)[:160]}); se sigue en la CPU")
                _dml_lost = True
        self._sess = self._make("cpu")
        return self._sess.run(*args, **kwargs)


def _ort_session(model_path: str, device: str, free_dims: dict | None = None,
                 threads: int | None = None) -> RecoveringSession:
    """See _new_session; the session recovers by itself if the iGPU is lost while running."""
    if device != "cpu" and _dml_lost:
        device = "cpu"
    return RecoveringSession(lambda d: _new_session(model_path, d, free_dims, threads), device)


def _new_session(model_path: str, device: str, free_dims: dict | None = None,
                 threads: int | None = None) -> ort.InferenceSession:
    """Session on the requested device, falling back to the CPU (with a warning) when that device
    is not available or fails to load the model: the analysis is slower but never stops.
    free_dims: {name: size} fixes dynamic input dimensions (e.g. the batch) so that DirectML can
    compile the whole graph for that shape (ONNX Runtime's free dimension overrides).
    threads: CPU threads of the session (ONNX Runtime's intra-op threads; None: its default, all cores),
    so that a CPU model running next to the iGPU leaves cores for the rest of the work."""
    available = set(ort.get_available_providers())
    providers = [p for p in ORT_PROVIDERS.get(device, ORT_PROVIDERS["cpu"]) if p in available] or ["CPUExecutionProvider"]
    if device not in ORT_PROVIDERS or providers == ["CPUExecutionProvider"] and device != "cpu":
        if device not in _warned:
            print(f"AVISO: el dispositivo '{device}' no está disponible; se usa la CPU (más lento)")
            _warned.add(device)
    opts = ort.SessionOptions()
    for name, size in (free_dims or {}).items():
        opts.add_free_dimension_override_by_name(name, int(size))
    if threads:
        opts.intra_op_num_threads = int(threads)
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
        cpu = ort.SessionOptions()
        for name, size in (free_dims or {}).items():
            cpu.add_free_dimension_override_by_name(name, int(size))
        if threads:
            cpu.intra_op_num_threads = int(threads)
        return ort.InferenceSession(model_path, sess_options=cpu, providers=["CPUExecutionProvider"])


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
