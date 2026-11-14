"""Capability discovery (#289, task T4 of the plan): what the machine that runs has, so the code chooses its video and
inference adapters by configuration and discovery instead of being fixed to the PC (`device: dml`, patched to CUDA in the
cloud by cloud/arranque/nube_gpu.py).

Read only and cheap (a few subprocess calls); every probe that fails gives «not there», never an exception. The
choice functions are pure: they take the capabilities and an order of preference (from the configuration) and return
the first adapter the machine supports, so the same code runs on the PC (DirectML), Modal or Kaggle (CUDA, TensorRT,
NVDEC) and a CPU-only machine (the Claude cloud, GitHub Actions).
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass, field

# ONNX Runtime providers for each inference adapter (the names the configuration uses)
PROVIDERS = {
    "tensorrt": ["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"],
    "cuda": ["CUDAExecutionProvider", "CPUExecutionProvider"],
    "dml": ["DmlExecutionProvider", "CPUExecutionProvider"],
    "openvino": ["OpenVINOExecutionProvider", "CPUExecutionProvider"],
    "cpu": ["CPUExecutionProvider"],
}
# Defaults until the proofs of concept decide (docs/nube_nativa.md): TensorRT is not first until it is measured
DEFAULT_INFERENCE = ("cuda", "dml", "openvino", "cpu")
DEFAULT_VIDEO = ("nvdec", "d3d11va", "cpu")


@dataclass
class Capabilities:
    platform: str = "desconocida"          # pc | kaggle | modal | claude | github | desconocida
    os: str = ""
    cores: int = 1
    memory_gib: float = 0.0
    gpus: list = field(default_factory=list)          # [{"name", "memory_gib", "vendor"}]
    ort_providers: list = field(default_factory=list)
    hwaccels: list = field(default_factory=list)      # ffmpeg -hwaccels (cuda, d3d11va, ...)
    ffmpeg: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


def detect_platform(env: dict | None = None, os_name: str | None = None) -> str:
    """Which infrastructure this is, from its own environment variables."""
    env = os.environ if env is None else env
    if env.get("KAGGLE_KERNEL_RUN_TYPE") or env.get("KAGGLE_URL_BASE"):
        return "kaggle"
    if env.get("MODAL_TASK_ID") or env.get("MODAL_ENVIRONMENT") or env.get("MODAL_IS_REMOTE"):
        return "modal"
    if env.get("GITHUB_ACTIONS") == "true":
        return "github"
    if env.get("CLAUDE_CODE_REMOTE_SDK_URL") or env.get("CLAUDE_CODE_SESSION_ID"):
        return "claude"
    if (os_name or os.name) == "nt":
        return "pc"
    return "desconocida"


def _out(cmd: list[str], run=subprocess.run) -> str:
    try:
        r = run(cmd, capture_output=True, text=True, timeout=30)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):  # esperado: the probe is not on this machine
        return ""


def parse_nvidia_smi(text: str) -> list[dict]:
    """`nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits` → GPUs."""
    gpus = []
    for line in text.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2 and parts[0]:
            try:
                mem = round(float(parts[1]) / 1024, 1)
            except ValueError:  # esperado: a value nvidia-smi could not give
                mem = 0.0
            gpus.append({"name": parts[0], "memory_gib": mem, "vendor": "nvidia"})
    return gpus


def parse_hwaccels(text: str) -> list[str]:
    """`ffmpeg -hide_banner -hwaccels` → the accelerators after its header line."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return [ln for ln in lines if not ln.lower().startswith("hardware acceleration")]


def _memory_gib() -> float:
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return round(int(line.split()[1]) / 2 ** 20, 1)
    except OSError:  # esperado: no /proc on this system (Windows)
        pass
    return 0.0


def discover(run=subprocess.run) -> Capabilities:
    """The capabilities of this machine (each probe that fails counts as absent)."""
    caps = Capabilities(platform=detect_platform(), os=platform.system(), cores=os.cpu_count() or 1,
                        memory_gib=_memory_gib())
    if shutil.which("nvidia-smi"):
        caps.gpus = parse_nvidia_smi(_out(["nvidia-smi", "--query-gpu=name,memory.total",
                                           "--format=csv,noheader,nounits"], run))
    try:
        import onnxruntime as ort

        caps.ort_providers = list(ort.get_available_providers())
    except Exception:  # esperado: no ONNX Runtime here, so no providers  # noqa: BLE001
        caps.ort_providers = []
    if shutil.which("ffmpeg"):
        caps.ffmpeg = True
        caps.hwaccels = parse_hwaccels(_out(["ffmpeg", "-hide_banner", "-hwaccels"], run))
    return caps


def choose_inference(caps: Capabilities, prefer=DEFAULT_INFERENCE) -> str:
    """The first inference adapter in `prefer` this machine can run (its ONNX Runtime provider is there and, for the
    NVIDIA ones, a GPU is seen); «cpu» always can."""
    for name in prefer:
        main = PROVIDERS.get(name, ["CPUExecutionProvider"])[0]
        if name == "cpu":
            return "cpu"
        if main not in caps.ort_providers:
            continue
        if name in ("cuda", "tensorrt") and not any(g.get("vendor") == "nvidia" for g in caps.gpus):
            continue
        return name
    return "cpu"


def choose_video(caps: Capabilities, prefer=DEFAULT_VIDEO) -> str:
    """The first video decoder in `prefer` this machine has: NVDEC (an NVIDIA GPU and ffmpeg built with cuda), the PC's
    d3d11va (Windows), or the CPU."""
    for name in prefer:
        if name == "nvdec" and "cuda" in caps.hwaccels and any(g.get("vendor") == "nvidia" for g in caps.gpus):
            return "nvdec"
        if name == "d3d11va" and "d3d11va" in caps.hwaccels and caps.os == "Windows":
            return "d3d11va"
        if name == "cpu":
            return "cpu"
    return "cpu"


def main() -> int:
    import json

    caps = discover()
    print(json.dumps({**caps.as_dict(), "inferencia": choose_inference(caps), "video": choose_video(caps)},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
