"""T15 (15-11): TOTNet's tennis weights (github.com/AugustRushG/TOTNet, MIT; trained on the TrackNet tennis broadcast
dataset; 5 frames at 288x512, the ball of the last frame) exported to ONNX, to be measured against TrackNetV3
(tennisbio.infra.poc_bola). Needs PyTorch and einops (Kaggle's own Python has them), not the analysis' environment.

- The repository is fetched at a fixed commit and the weights are checked against their SHA-256.
- The checkpoint also pickles its training settings: it is read with an unpickler that builds only an allowlist of
  classes (tensors, dicts, the settings dict), so the file cannot run code.
- TOTNet's three AdaptiveMaxPool3d layers cannot be exported with einops' shapes: each is replaced by the same pooling
  written with fixed slices for its one input size (PyTorch's bins), checked equal on a real forward pass.
- The ONNX model is checked against PyTorch on the same input.

    python scripts/export_totnet.py --salida models/totnet_tennis.onnx [--repo /tmp/totnet]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pickle
import subprocess
import sys
import types
from pathlib import Path

REPO_URL = "https://github.com/AugustRushG/TOTNet"
COMMIT = "8a757f63391b262c14d18b4095486336852dbeef"
NAME = "TOTNet_Tennis_(5)_(288,512)_30epochs_Occl(0.25)_WBCE[1,2,3,3]_bs8_ch64"
WEIGHTS = f"weights/{NAME}/{NAME}_best.pth"
SHA256 = "36caadd2453cf1a37f26afb0024b861fd3285ca6e9a91e9e4a20d35e90a0a24a"
H, W, N = 288, 512, 5
ALLOWED = {("collections", "OrderedDict"), ("torch._utils", "_rebuild_tensor_v2"), ("torch._utils", "_rebuild_parameter"),
           ("torch", "FloatStorage"), ("torch", "LongStorage"), ("torch", "IntStorage"), ("torch", "HalfStorage"),
           ("torch", "BoolStorage"), ("torch", "device"), ("torch", "Size"), ("builtins", "set"),
           ("numpy", "dtype"), ("numpy.core.multiarray", "scalar"), ("numpy._core.multiarray", "scalar")}


class _Settings(dict):
    """Stands for easydict.EasyDict (the training settings in the checkpoint): a plain dict, never used."""


class _SafeUnpickler(pickle.Unpickler):
    def find_class(self, mod, name):
        if (mod, name) == ("easydict", "EasyDict"):
            return _Settings
        if (mod, name) not in ALLOWED:
            raise pickle.UnpicklingError(f"clase no permitida en el fichero de pesos: {mod}.{name}")
        return super().find_class(mod, name)


def fetch_repo(dest: Path) -> Path:
    if not (dest / ".git").exists():
        subprocess.run(["git", "init", "-q", str(dest)], check=True)
        subprocess.run(["git", "-C", str(dest), "remote", "add", "origin", REPO_URL], check=True)
    subprocess.run(["git", "-C", str(dest), "fetch", "-q", "--depth", "1", "origin", COMMIT], check=True)
    subprocess.run(["git", "-C", str(dest), "checkout", "-q", COMMIT], check=True)
    return dest


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fixed_pooling(torch):
    class FixedAdaptiveMax3d(torch.nn.Module):
        """AdaptiveMaxPool3d for one known input size with fixed slices: PyTorch's bins along time (start
        floor(i*n/m), end ceil((i+1)*n/m)); the spatial sizes divide evenly."""

        def __init__(self, si, so):
            super().__init__()
            if si[1] % so[1] or si[2] % so[2]:
                raise ValueError(f"tamaños espaciales que no se dividen: {si} → {so}")
            self.si, self.so, self.k = si, so, (1, si[1] // so[1], si[2] // so[2])

        def forward(self, x):
            x = torch.nn.functional.max_pool3d(x, self.k, self.k)
            n, m = self.si[0], self.so[0]
            if n == m:
                return x
            return torch.cat([x[:, :, (i * n) // m: -((-(i + 1) * n) // m)].amax(dim=2, keepdim=True) for i in range(m)], 2)
    return FixedAdaptiveMax3d


def export(repo: Path, out: Path) -> dict:
    import numpy as np
    import torch

    weights = repo / WEIGHTS
    got = sha256(weights)
    if got != SHA256:
        raise SystemExit(f"los pesos no son los esperados (sha256 {got})")
    spec = importlib.util.spec_from_file_location("totnet_model", repo / "src" / "model" / "TOTNet.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    net = mod.TemporalConvNet(input_shape=(H, W), spatial_channels=64, num_frames=N)
    safe = types.ModuleType("safe_pickle")
    safe.Unpickler, safe.load, safe.__name__ = _SafeUnpickler, pickle.load, "safe_pickle"
    ck = torch.load(str(weights), map_location="cpu", weights_only=False, pickle_module=safe)
    sd = {k.replace("module.", "", 1): v for k, v in ck["state_dict"].items()}
    missing, unexpected = net.load_state_dict(sd, strict=False)
    if missing or unexpected:
        raise SystemExit(f"pesos que no encajan: faltan {missing[:5]}, sobran {unexpected[:5]}")
    net.eval()
    x = torch.from_numpy(np.random.default_rng(3).standard_normal((1, N, 3, H, W)).astype(np.float32))
    sizes, hooks = {}, []
    for k, m in net.named_modules():
        if isinstance(m, torch.nn.AdaptiveMaxPool3d):
            hooks.append(m.register_forward_hook(
                lambda m, i, o, k=k: sizes.__setitem__(k, (tuple(i[0].shape[2:]), tuple(o.shape[2:])))))
    with torch.no_grad():
        ref = net(x)
    for h in hooks:
        h.remove()
    Fixed = fixed_pooling(torch)
    for k, (si, so) in sizes.items():
        parent = net.get_submodule(k.rsplit(".", 1)[0]) if "." in k else net
        setattr(parent, k.rsplit(".", 1)[-1], Fixed(si, so))
    with torch.no_grad():
        same = float((net(x) - ref).abs().max())
    if same > 1e-6:
        raise SystemExit(f"la agrupación fija no da lo mismo ({same})")

    class Heatmap(torch.nn.Module):
        def __init__(self, n):
            super().__init__()
            self.n = n

        def forward(self, frames):
            return self.n(frames).view(-1, H, W)

    out.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(Heatmap(net), x, str(out), input_names=["frames"], output_names=["heatmap"], opset_version=17,
                      dynamo=False)
    import onnxruntime as ort

    sess = ort.InferenceSession(str(out), providers=["CPUExecutionProvider"])
    diff = float(np.abs(sess.run(None, {"frames": x.numpy()})[0].reshape(1, -1) - ref.numpy()).max())
    if diff > 1e-4:
        raise SystemExit(f"ONNX no da lo mismo que PyTorch ({diff})")
    info = {"modelo": "TOTNet tenis", "repositorio": REPO_URL, "commit": COMMIT, "pesos": WEIGHTS, "sha256": SHA256,
            "agrupaciones": {k: [list(a), list(b)] for k, (a, b) in sizes.items()}, "onnx_vs_pytorch": diff}
    out.with_suffix(".json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    return info


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", type=Path, required=True)
    ap.add_argument("--repo", type=Path, default=Path("/tmp/totnet"))
    a = ap.parse_args(argv)
    print(json.dumps(export(fetch_repo(a.repo), a.salida), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
