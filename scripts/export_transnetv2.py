"""Export TransNetV2 (shot boundary detection, Souček & Lokoč 2020, MIT licence) to ONNX.

The weights are the official ones converted to PyTorch, taken from the `transnetv2-pytorch` wheel on
PyPI (MIT, https://github.com/allenday/transnetv2_pytorch): the wheel is a zip, only the .pth file is
read from it (nothing of that package is installed or executed). Only torch is required
(`uv sync --extra yolo`), as for export_balltrack.py / export_racketpose.py.

The network is re-declared here with ONNX-friendly operations, numerically equal to the reference
(checked on export): the RGB histogram is a product of one-hot matrices instead of scatter_add and the
±50-frame similarity band is taken with a skew/reshape instead of advanced indexing. Both run on the
DirectML iGPU and on the CPU.

Model input: uint8 [n, 100, 27, 48, 3] (RGB, 100 consecutive frames at 48×27); output: probability of
a shot boundary at each frame [n, 100] (the reference keeps frames 25..75 of each window).

    uv run python scripts/export_transnetv2.py --out models/transnetv2.onnx
"""
import argparse
import hashlib
import sys
import urllib.request
import zipfile
from pathlib import Path

WHEEL_URL = ("https://files.pythonhosted.org/packages/85/be/bb14f9015d357c9dff395a065bd658d1f7a199eb1f8d3abb9f4792416f11/"
             "transnetv2_pytorch-1.0.5-py3-none-any.whl")
WHEEL_SHA256 = "9f8e72085526aaa95383d219b6750b1fa45b865fd10d840cafa12ef78ab3bf27"
WEIGHTS_MEMBER = "transnetv2_pytorch/transnetv2-pytorch-weights.pth"
WINDOW = 100


def build(F=16, L=3, S=2, D=1024, window=WINDOW, reference=False):
    """TransNetV2 (inference only). reference=True uses the original scatter/gather operations
    (to check that the ONNX-friendly ones give the same numbers)."""
    import torch
    from torch import nn
    from torch.nn import functional as fn

    def band(sim, lookup=101):
        """sim [B, T, T] → [B, T, lookup] with out[b, t, k] = sim[b, t, t + k - lookup // 2] (0 outside)."""
        B, T = sim.shape[0], window
        h = (lookup - 1) // 2
        if reference:
            p = fn.pad(sim, [h, h])
            bi = torch.arange(B).view(B, 1, 1).repeat(1, T, lookup)
            ti = torch.arange(T).view(1, T, 1).repeat(B, 1, lookup)
            li = torch.arange(lookup).view(1, 1, lookup).repeat(B, T, 1) + ti
            return p[bi, ti, li]
        W = T + 2 * h
        p = fn.pad(sim, [h, h]).reshape(B, T * W)           # element (t, c) at t·W + c
        p = fn.pad(p, [0, T]).reshape(B, T, W + 1)          # row t now starts at t·(W + 1) = t·W + t
        return p[:, :, :lookup]                             # (t, k) = padded (t, t + k)

    class Conv3DConfigurable(nn.Module):
        def __init__(self, i, o, rate, use_bias):
            super().__init__()
            self.layers = nn.ModuleList([
                nn.Conv3d(i, 2 * o, kernel_size=(1, 3, 3), padding=(0, 1, 1), bias=False),
                nn.Conv3d(2 * o, o, kernel_size=(3, 1, 1), dilation=(rate, 1, 1), padding=(rate, 0, 0), bias=use_bias)])

        def forward(self, x):
            for layer in self.layers:
                x = layer(x)
            return x

    class DilatedDCNNV2(nn.Module):
        def __init__(self, i, o, activation):
            super().__init__()
            self.Conv3D_1 = Conv3DConfigurable(i, o, 1, False)
            self.Conv3D_2 = Conv3DConfigurable(i, o, 2, False)
            self.Conv3D_4 = Conv3DConfigurable(i, o, 4, False)
            self.Conv3D_8 = Conv3DConfigurable(i, o, 8, False)
            self.bn = nn.BatchNorm3d(o * 4, eps=1e-3)
            self.activation = activation

        def forward(self, x):
            x = torch.cat([self.Conv3D_1(x), self.Conv3D_2(x), self.Conv3D_4(x), self.Conv3D_8(x)], 1)
            x = self.bn(x)
            return self.activation(x) if self.activation else x

    class StackedDDCNNV2(nn.Module):
        def __init__(self, i, n, o):
            super().__init__()
            self.DDCNN = nn.ModuleList([DilatedDCNNV2(i if k == 1 else o * 4, o, fn.relu if k != n else None)
                                        for k in range(1, n + 1)])
            self.pool = nn.AvgPool3d(kernel_size=(1, 2, 2))

        def forward(self, x):
            shortcut = None
            for block in self.DDCNN:
                x = block(x)
                if shortcut is None:
                    shortcut = x
            return self.pool(fn.relu(x) + shortcut)

    class FrameSimilarity(nn.Module):
        def __init__(self, i):
            super().__init__()
            self.projection = nn.Linear(i, 128, bias=True)
            self.fc = nn.Linear(101, 128)

        def forward(self, feats):
            x = torch.cat([torch.mean(f, dim=[3, 4]) for f in feats], 1).transpose(1, 2)
            x = fn.normalize(self.projection(x), p=2, dim=2)
            return fn.relu(self.fc(band(torch.bmm(x, x.transpose(1, 2)))))

    class ColorHistograms(nn.Module):
        def __init__(self):
            super().__init__()
            self.fc = nn.Linear(101, 128)

        def histograms(self, frames):                   # uint8 [B, T, H, W, 3] → L2-normalised [B, T, 512]
            B = frames.shape[0]
            if reference:
                f = frames.int().view(B * window, -1, 3)
                b = ((f[..., 0] >> 5) << 6) + ((f[..., 1] >> 5) << 3) + (f[..., 2] >> 5)
                b = (b + (torch.arange(B * window) << 9).view(-1, 1)).view(-1)
                h = torch.zeros(B * window * 512, dtype=torch.int32)
                h.scatter_add_(0, b, torch.ones(len(b), dtype=torch.int32))
                h = h.view(B, window, 512).float()
            else:
                q = torch.floor(frames.float() / 32.0).reshape(B * window, -1, 3)        # 0..7 per channel
                levels = torch.arange(8, dtype=torch.float32)
                r, g, bl = [(q[..., c:c + 1] == levels).float() for c in range(3)]       # one-hot [N, P, 8]
                rg = (r.unsqueeze(3) * g.unsqueeze(2)).reshape(B * window, -1, 64)       # [N, P, 64]
                h = torch.bmm(rg.transpose(1, 2), bl).reshape(B, window, 512)            # bin = 64 r + 8 g + b
            return fn.normalize(h, p=2, dim=2)

        def forward(self, frames):
            x = self.histograms(frames)
            return fn.relu(self.fc(band(torch.bmm(x, x.transpose(1, 2)))))

    class TransNetV2(nn.Module):
        def __init__(self):
            super().__init__()
            self.SDDCNN = nn.ModuleList([StackedDDCNNV2(3, S, F)] +
                                        [StackedDDCNNV2(F * 2 ** (i - 1) * 4, S, F * 2 ** i) for i in range(1, L)])
            self.frame_sim_layer = FrameSimilarity(sum(F * 2 ** i * 4 for i in range(L)))
            self.color_hist_layer = ColorHistograms()
            self.fc1 = nn.Linear(F * 2 ** (L - 1) * 4 * 3 * 6 + 256, D)
            self.cls_layer1 = nn.Linear(D, 1)
            self.cls_layer2 = nn.Linear(D, 1)         # "many hot" head: in the weights, not used at inference

        def forward(self, frames):                    # uint8 [B, T, 27, 48, 3]
            x = frames.permute(0, 4, 1, 2, 3).float() / 255.0
            feats = []
            for block in self.SDDCNN:
                x = block(x)
                feats.append(x)
            x = x.permute(0, 2, 3, 4, 1).reshape(x.shape[0], window, -1)
            x = torch.cat([self.color_hist_layer(frames), self.frame_sim_layer(feats), x], 2)
            x = fn.relu(self.fc1(x))
            return torch.sigmoid(self.cls_layer1(x))[..., 0]
    return TransNetV2()


def weights(cache: Path) -> Path:
    """The .pth with the official weights, extracted once from the PyPI wheel (checked by its hash)."""
    pth = cache / "transnetv2-pytorch-weights.pth"
    if pth.exists():
        return pth
    whl = cache / "transnetv2_pytorch-1.0.5.whl"
    if not whl.exists():
        cache.mkdir(parents=True, exist_ok=True)
        print(f"descargando {WHEEL_URL}")
        urllib.request.urlretrieve(WHEEL_URL, whl)
    if hashlib.sha256(whl.read_bytes()).hexdigest() != WHEEL_SHA256:
        whl.unlink()
        raise RuntimeError("el fichero descargado de TransNetV2 no coincide con el esperado; se borra")
    with zipfile.ZipFile(whl) as z:
        pth.with_suffix(".part").write_bytes(z.read(WEIGHTS_MEMBER))
    pth.with_suffix(".part").replace(pth)
    whl.unlink()
    return pth


def load(pth: Path, reference=False):
    import torch

    model = build(reference=reference)
    state = torch.load(pth, map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    return model.eval()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="models/transnetv2.onnx")
    ap.add_argument("--cache", default="models", help="dónde se guardan los pesos .pth")
    args = ap.parse_args()
    import numpy as np
    import torch

    pth = weights(Path(args.cache))
    model, ref = load(pth), load(pth, reference=True)
    rng = np.random.default_rng(0)
    x = torch.from_numpy(rng.integers(0, 256, (2, WINDOW, 27, 48, 3), dtype=np.uint8))
    x[:, 50:] = x[:, 50:] // 4                         # a "cut" in the middle
    with torch.no_grad():
        diff = float((model(x) - ref(x)).abs().max())
    if diff > 1e-4:
        raise RuntimeError(f"la red reescrita no coincide con la de referencia (diferencia {diff:.2g})")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + ".part.onnx")      # an interrupted export never leaves a broken model
    torch.onnx.export(model, x[:1], str(tmp), input_names=["frames"], output_names=["cut"],
                      dynamic_axes={"frames": {0: "n"}, "cut": {0: "n"}}, opset_version=17, dynamo=False)
    tmp.replace(out)
    print(f"guardado {out} (diferencia con la referencia {diff:.1g})")


if __name__ == "__main__":
    sys.exit(main())
