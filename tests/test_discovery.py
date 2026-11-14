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


def test_racket_proof_of_concept_compares_and_times(tmp_path):
    """T6: the comparison of an option's outputs with CUDA FP32's (largest difference, keypoints moved)."""
    import numpy as np

    from tennisbio.infra import poc_raqueta as poc
    a = [np.zeros((2, 5, 10), np.float32)]
    b = [np.zeros((2, 5, 10), np.float32)]
    b[0][0, 0, 3] = 1.0
    c = poc.compare(a, b)
    assert c["puntos_movidos"] == 1 and c["puntos"] == 10 and c["max_diff"] == 1.0


def test_device_auto_and_gpu_paths(monkeypatch):
    """T4 (14-11, #289): «device: auto» is resolved by discovery; every «is it the iGPU?» is now «is it a GPU?», so the
    cloud's CUDA takes the same code paths the PC's DirectML takes (static batches, 2 workers, fp16 pose)."""
    from tennisbio.infra import devices
    assert devices.is_gpu("dml") and devices.is_gpu("cuda") and devices.is_gpu("tensorrt")
    assert not devices.is_gpu("cpu") and not devices.is_gpu(None) and not devices.is_gpu("openvino")
    assert devices.resolve("dml") == "dml" and devices.resolve(None) == "cpu"
    devices._auto.cache_clear()
    kaggle = Capabilities(platform="kaggle", gpus=T4, ort_providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
    monkeypatch.setattr(devices, "discover", lambda: kaggle)
    assert devices.resolve("auto") == "cuda"
    devices._auto.cache_clear()
    monkeypatch.setattr(devices, "discover", lambda: Capabilities(ort_providers=["CPUExecutionProvider"]))
    assert devices.resolve("auto") == "cpu"
    devices._auto.cache_clear()
    assert devices.provider_options(["CUDAExecutionProvider", "CPUExecutionProvider"]) == [devices.CUDA_OPTIONS, {}]
    assert devices.provider_options(["DmlExecutionProvider", "CPUExecutionProvider"]) is None
    assert devices.providers_for("cuda") == ["CUDAExecutionProvider", "CPUExecutionProvider"]
    assert devices.providers_for("openvino") == ["CPUExecutionProvider"] == devices.providers_for("nada")


def test_the_cloud_patch_and_the_estimator_use_the_same_cuda_options():
    """The equivalence of T4: the CUDA options and the memory given back are those of cloud/arranque/nube_gpu.py."""
    import sys
    from pathlib import Path

    from tennisbio.infra import devices
    from tennisbio.pose import estimator
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud" / "arranque"))
    import nube_gpu
    assert devices.CUDA_OPTIONS == nube_gpu.CUDA_OPTIONS
    assert estimator.ORT_PROVIDERS["cuda"] == ["CUDAExecutionProvider", "CPUExecutionProvider"]
    assert estimator.ORT_PROVIDERS["dml"] == ["DmlExecutionProvider", "CPUExecutionProvider"]

    class Fake:
        def get_providers(self):
            return ["CPUExecutionProvider"]
    assert estimator._shrink_options(Fake()) is None


def test_config_resolves_auto(tmp_path, monkeypatch):
    from tennisbio import config
    from tennisbio.infra import devices
    (tmp_path / "default.yaml").write_text("device: auto\n", encoding="utf-8")
    monkeypatch.setattr(devices, "resolve", lambda d, prefer=None: "cuda")
    cfg = config.load_config(tmp_path)
    assert cfg["device"] == "cuda" and cfg["device_configurado"] == "auto"


def test_video_proof_of_concept_pieces(tmp_path):
    """T7: the windows spread over the broadcast, and how far two decodings' pictures are."""
    import numpy as np

    from tennisbio.infra import poc_video as pv
    ts = pv.window_times(3600.0, 4, 2.0)
    assert len(ts) == 4 and ts[0] >= 60 and ts[-1] <= 3600 - 60 and ts == sorted(ts)
    assert pv.window_times(1.0, 4, 2.0) == [0.0]
    a = np.zeros((2, 2, 3), np.uint8)
    b = a.copy()
    b[0, 0, 0] = 9
    mean, mx, share = pv.frame_diff(a, b)
    assert mx == 9 and round(mean, 3) == 0.75 and round(share, 3) == round(1 / 12, 3)


def test_video_all_on_the_gpu_command():
    """T7: the third option keeps the frames on the GPU (decode, deinterlace, convert) and copies them once."""
    from types import SimpleNamespace

    from tennisbio.infra import poc_video as pv
    cmd = pv.gpu_command(SimpleNamespace(path="v.ts", interlaced=True), 12.0, 2.0)
    vf = cmd[cmd.index("-vf") + 1]
    assert vf.startswith("yadif_cuda=1,") and "hwdownload" in vf and cmd[cmd.index("-hwaccel_output_format") + 1] == "cuda"
    assert "yadif_cuda" not in pv.gpu_command(SimpleNamespace(path="v.mp4", interlaced=False), 0, 2)[-9]
    assert cmd[-1] == "pipe:1" and "bgr24" in cmd and set(pv.OPTIONS) == {"cpu", "nvdec", "gpu_entera"}


def test_racket_poc_refuses_a_time_measured_on_the_cpu(tmp_path, monkeypatch):
    """R47: an option whose session ONNX Runtime put on the CPU is reported as an error, never with its times."""
    import numpy as np

    from tennisbio.infra import poc_raqueta as poc

    class Inp:
        name, shape = "input", ["N", 3, 4, 4]

    class Sess:
        def __init__(self, *a, **k):
            pass

        def get_inputs(self):
            return [Inp()]

        def get_providers(self):
            return ["CPUExecutionProvider"]

        def run(self, names, feed):
            return [np.zeros((feed["input"].shape[0], 5, 8), np.float32)]
    import onnxruntime as ort
    monkeypatch.setattr(ort, "InferenceSession", Sess)
    monkeypatch.setattr("tennisbio.infra.devices.preload_cuda", lambda: None)
    out = poc.run("m.onnx", tmp_path, repeats=1)
    assert all("CPUExecutionProvider" in o["error"] for o in out["opciones"].values())
