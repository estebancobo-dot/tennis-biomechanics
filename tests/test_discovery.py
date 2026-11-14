"""Capability discovery (#289, T4): the same code picks its adapters on the PC, Modal, Kaggle and a CPU-only machine."""
from tennisbio.infra.discovery import (Capabilities, choose_inference, choose_video, detect_platform, discover,
                                       parse_hwaccels, parse_nvidia_smi)

T4 = [{"name": "Tesla T4", "memory_gib": 15.0, "vendor": "nvidia"}]


def test_platform_from_its_own_environment():
    assert detect_platform({"KAGGLE_KERNEL_RUN_TYPE": "Batch"}) == "kaggle"
    assert detect_platform({"MODAL_TASK_ID": "ta-1"}) == "modal"
    assert detect_platform({"GITHUB_ACTIONS": "true"}) == "github"
    assert detect_platform({"CLAUDE_CODE_SESSION_ID": "x"}) == "claude"
    assert detect_platform({}, os_name="nt") == "pc"
    assert detect_platform({}, os_name="posix") == "desconocida"


def test_parsers():
    assert parse_nvidia_smi("Tesla T4, 15360\nTesla T4, 15360\n") == T4 * 2
    assert parse_nvidia_smi("") == [] and parse_nvidia_smi("garbage") == []
    assert parse_hwaccels("Hardware acceleration methods:\nvdpau\ncuda\nvaapi\n") == ["vdpau", "cuda", "vaapi"]


def test_choices_per_machine():
    kaggle = Capabilities(platform="kaggle", os="Linux", cores=4, gpus=T4 * 2,
                          ort_providers=["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"],
                          hwaccels=["cuda", "vaapi"], ffmpeg=True)
    pc = Capabilities(platform="pc", os="Windows", cores=16, ort_providers=["DmlExecutionProvider", "CPUExecutionProvider"],
                      hwaccels=["d3d11va", "dxva2"], ffmpeg=True)
    claude = Capabilities(platform="claude", os="Linux", cores=4, ort_providers=["CPUExecutionProvider"], ffmpeg=True)
    assert choose_inference(kaggle) == "cuda" and choose_video(kaggle) == "nvdec"
    assert choose_inference(kaggle, ("tensorrt", "cuda", "cpu")) == "tensorrt"        # once a proof of concept says so
    assert choose_inference(pc) == "dml" and choose_video(pc) == "d3d11va"
    assert choose_inference(claude) == "cpu" and choose_video(claude) == "cpu"
    # a CUDA provider without an NVIDIA GPU seen (a wheel installed on a CPU machine) is not CUDA
    odd = Capabilities(ort_providers=["CUDAExecutionProvider", "CPUExecutionProvider"], hwaccels=["cuda"])
    assert choose_inference(odd) == "cpu" and choose_video(odd) == "cpu"


def test_discover_never_raises_here():
    caps = discover()
    assert caps.cores >= 1 and isinstance(caps.gpus, list) and "CPUExecutionProvider" in caps.ort_providers
    assert choose_inference(caps) in ("cuda", "dml", "openvino", "cpu")
