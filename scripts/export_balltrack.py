"""Export the RacketVision ball tracker (TrackNetV3, MIT licence) to ONNX.

Only needs torch (`uv sync --extra yolo`); the network is re-declared here so the original
mmengine code is not required.

    uv run python scripts/export_balltrack.py --out models/balltrack.onnx
"""
import argparse
import sys
import urllib.request
from pathlib import Path

URL = "https://huggingface.co/linfeng302/RacketVision-Models/resolve/main/checkpoints/balltrack_best.pth"


def build(seq_len=4, d=64):
    import torch
    from torch import nn

    def block(i, o, n):
        layers = []
        for k in range(n):
            layers += [nn.Conv2d(i if k == 0 else o, o, 3, padding="same", bias=False), nn.BatchNorm2d(o), nn.ReLU()]
        return nn.Sequential(*layers)

    class TrackNetV3(nn.Module):
        def __init__(self):
            super().__init__()
            self.down_block_1 = block(3 * (seq_len + 1), d, 2)
            self.down_block_2 = block(d, 2 * d, 2)
            self.down_block_3 = block(2 * d, 4 * d, 3)
            self.bottleneck = block(4 * d, 8 * d, 3)
            self.up_block_1 = block(12 * d, 4 * d, 3)
            self.up_block_2 = block(6 * d, 2 * d, 2)
            self.up_block_3 = block(3 * d, d, 2)
            self.predictor = nn.Conv2d(d, seq_len, 1)

        def forward(self, x):
            pool, up = nn.MaxPool2d(2), nn.Upsample(scale_factor=2)
            x1 = self.down_block_1(x)
            x2 = self.down_block_2(pool(x1))
            x3 = self.down_block_3(pool(x2))
            x = self.bottleneck(pool(x3))
            x = self.up_block_1(torch.cat([up(x), x3], 1))
            x = self.up_block_2(torch.cat([up(x), x2], 1))
            x = self.up_block_3(torch.cat([up(x), x1], 1))
            return torch.sigmoid(self.predictor(x))[:, -1:]      # heatmap of the last frame
    return TrackNetV3()


def _stub_pickle():
    """pickle module whose Unpickler replaces missing classes (mmengine bookkeeping) by stubs."""
    import pickle
    import types

    class StubMeta(type):
        def __getattr__(cls, name):            # e.g. getattr(HistoryBuffer, "min")
            return lambda *a, **k: None

    class Stub(metaclass=StubMeta):
        def __init__(self, *a, **k):
            pass

        def __setstate__(self, state):
            pass

    class Unpickler(pickle.Unpickler):
        def find_class(self, module, name):
            try:
                return super().find_class(module, name)
            except (ModuleNotFoundError, AttributeError):
                if module.startswith(("mmengine", "mmcv", "mmdet", "mmpose")):
                    return Stub
                raise

    mod = types.ModuleType("stub_pickle")
    mod.__dict__.update(pickle.__dict__)
    mod.Unpickler = Unpickler
    return mod


def load(ckpt: Path):
    import torch

    state = torch.load(ckpt, map_location="cpu", weights_only=False, pickle_module=_stub_pickle())
    state = state.get("state_dict", state)
    renamed = {}
    for k, v in state.items():
        k = k.removeprefix("module.")
        parts = k.split(".")
        if parts[0] != "predictor":                       # block.conv_N.{conv,bn}.param → block.idx.param
            n = int(parts[1].split("_")[1]) - 1
            k = ".".join([parts[0], str(3 * n + (0 if parts[2] == "conv" else 1)), *parts[3:]])
        renamed[k] = v
    model = build()
    model.load_state_dict(renamed)
    return model.eval()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="models/balltrack_best.pth")
    ap.add_argument("--out", default="models/balltrack.onnx")
    args = ap.parse_args()
    import torch

    ckpt = Path(args.ckpt)
    if not ckpt.exists():
        ckpt.parent.mkdir(parents=True, exist_ok=True)
        print(f"descargando {URL}")
        urllib.request.urlretrieve(URL, ckpt)
    model = load(ckpt)
    x = torch.zeros(1, 15, 288, 512)
    torch.onnx.export(model, x, args.out, input_names=["frames"], output_names=["heatmap"],
                      dynamic_axes={"frames": {0: "n"}, "heatmap": {0: "n"}}, opset_version=17, dynamo=False)
    print(f"guardado {args.out}")


if __name__ == "__main__":
    sys.exit(main())
