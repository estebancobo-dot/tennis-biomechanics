"""The inference port (#289, T4): which device the analysis's ONNX models run on, by configuration and discovery.

`device` in the configuration is a name: «cpu», «dml» (DirectML, the PC's iGPU), «cuda» (an NVIDIA GPU: Kaggle, Modal),
«tensorrt» (the same GPU through TensorRT, only once a proof of concept says so) or «auto»: the first in
`inference_preference` (default `discovery.DEFAULT_INFERENCE`) that this machine can run. Everything that used to ask
«is it the iGPU?» (`device == "dml"`) asks `is_gpu(device)`, so the same code paths run on the PC and in the cloud
(until 14-11 the cloud kept «dml» and cloud/arranque/nube_gpu.py put those sessions on CUDA).
"""
from __future__ import annotations

from functools import lru_cache

from .discovery import DEFAULT_INFERENCE, PROVIDERS, choose_inference, discover

GPU_DEVICES = ("dml", "cuda", "tensorrt")
NVIDIA_DEVICES = ("cuda", "tensorrt")
# 13-11 (Pegula's 10-minute test, cloud/arranque/nube_gpu.py): the fine pass's two workers each open several CUDA
# sessions; with ONNX Runtime's defaults (an arena that doubles, cuDNN's exhaustive search with the largest workspace)
# the T4's 15 GB filled up and the next sessions failed and went to the CPU. Each session takes only what it asks for;
# cuDNN picks its algorithm by heuristics within a small workspace.
CUDA_OPTIONS = {"arena_extend_strategy": "kSameAsRequested", "cudnn_conv_algo_search": "HEURISTIC",
                "cudnn_conv_use_max_workspace": "0"}


def is_gpu(device: str | None) -> bool:
    """Whether the models run on a GPU (the PC's iGPU or an NVIDIA card): the code paths made for one (static batches,
    two fine-pass workers, the half-precision pose model, the ball ahead) apply."""
    return str(device or "cpu") in GPU_DEVICES


@lru_cache(maxsize=4)
def _auto(prefer: tuple) -> str:
    return choose_inference(discover(), prefer)


def resolve(device: str | None, prefer=None) -> str:
    """The configured device name, with «auto» replaced by what this machine can run (discovered once per process)."""
    name = str(device or "cpu")
    if name != "auto":
        return name
    return _auto(tuple(prefer or DEFAULT_INFERENCE))


def providers_for(device: str) -> list[str]:
    """ONNX Runtime's providers for a device name (unknown names: the CPU)."""
    return list(PROVIDERS.get(device, PROVIDERS["cpu"])) if device in PROVIDERS and device != "openvino" \
        else list(PROVIDERS["cpu"])


def provider_options(providers: list[str]) -> list[dict] | None:
    """ONNX Runtime's provider_options for a list of provider names: CUDA_OPTIONS for CUDA, none for the rest."""
    if "CUDAExecutionProvider" not in providers:
        return None
    return [dict(CUDA_OPTIONS) if p == "CUDAExecutionProvider" else {} for p in providers]


@lru_cache(maxsize=1)
def nvidia_gpus() -> int:
    """How many NVIDIA GPUs this machine has (discovered once per process; 0 without nvidia-smi)."""
    return len([g for g in discover().gpus if g.get("vendor") == "nvidia"])


def gpu_slots(device: str, workers: int) -> list[int]:
    """T8 (14-11, Kaggle's two T4s, the second one idle): the GPU each worker of the fine pass uses, one after the
    other (worker i → GPU i mod n); [] when there is nothing to spread (not NVIDIA, one GPU or one worker)."""
    n = nvidia_gpus() if device in NVIDIA_DEVICES else 0
    return [i % n for i in range(workers)] if n > 1 and workers > 1 else []


_preloaded = False


def preload_cuda() -> None:
    """The CUDA and cuDNN libraries of the onnxruntime-gpu[cuda,cudnn] wheels, once per process (older wheels: the
    system's libraries are used)."""
    global _preloaded
    if _preloaded:
        return
    _preloaded = True
    try:
        import onnxruntime as ort

        ort.preload_dlls()
    except Exception as e:  # esperado: an older wheel without preload_dlls; the system libraries are used  # noqa: BLE001
        print(f"AVISO: preload_dlls ({e})")
