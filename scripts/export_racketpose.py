"""Export the RacketVision racket pose model (RTMPose-m, 5 keypoints, MIT licence) to ONNX.

Keypoints: 0 top (tip), 1 bottom (throat), 2 handle (butt), 3 left, 4 right (frame edges).
The network (CSPNeXt-m backbone + RTMCC head) is re-declared in plain PyTorch so mmpose,
mmdet and mmcv are not needed. Only torch is required (`uv sync --extra yolo`).

    uv run python scripts/export_racketpose.py --out models/racketpose.onnx
"""
import argparse
import math
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_balltrack import _stub_pickle  # noqa: E402

URL = "https://huggingface.co/linfeng302/RacketVision-Models/resolve/main/checkpoints/best_PCK_epoch_90.pth"


def build(num_kp=5, size=256, split=2.0):
    import torch
    from torch import nn

    class ConvModule(nn.Module):
        def __init__(self, i, o, k, s=1, groups=1):
            super().__init__()
            self.conv = nn.Conv2d(i, o, k, s, k // 2, groups=groups, bias=False)
            self.bn = nn.BatchNorm2d(o)
            self.act = nn.SiLU()

        def forward(self, x):
            return self.act(self.bn(self.conv(x)))

    class DWConv(nn.Module):
        def __init__(self, i, o, k):
            super().__init__()
            self.depthwise_conv = ConvModule(i, i, k, groups=i)
            self.pointwise_conv = ConvModule(i, o, 1)

        def forward(self, x):
            return self.pointwise_conv(self.depthwise_conv(x))

    class Block(nn.Module):
        def __init__(self, c, identity):
            super().__init__()
            self.conv1 = ConvModule(c, c, 3)
            self.conv2 = DWConv(c, c, 5)
            self.identity = identity

        def forward(self, x):
            y = self.conv2(self.conv1(x))
            return x + y if self.identity else y

    class ChannelAttention(nn.Module):
        def __init__(self, c):
            super().__init__()
            self.fc = nn.Conv2d(c, c, 1)

        def forward(self, x):
            w = torch.nn.functional.hardsigmoid(self.fc(x.mean((2, 3), keepdim=True)))
            return x * w

    class CSPLayer(nn.Module):
        def __init__(self, i, o, n, identity):
            super().__init__()
            m = o // 2
            self.main_conv = ConvModule(i, m, 1)
            self.short_conv = ConvModule(i, m, 1)
            self.final_conv = ConvModule(2 * m, o, 1)
            self.blocks = nn.Sequential(*[Block(m, identity) for _ in range(n)])
            self.attention = ChannelAttention(2 * m)

        def forward(self, x):
            y = torch.cat([self.blocks(self.main_conv(x)), self.short_conv(x)], 1)
            return self.final_conv(self.attention(y))

    class SPP(nn.Module):
        def __init__(self, c):
            super().__init__()
            self.conv1 = ConvModule(c, c // 2, 1)
            self.conv2 = ConvModule(c // 2 * 4, c, 1)
            self.pools = nn.ModuleList([nn.MaxPool2d(k, 1, k // 2) for k in (5, 9, 13)])

        def forward(self, x):
            x = self.conv1(x)
            return self.conv2(torch.cat([x] + [p(x) for p in self.pools], 1))

    class ScaleNorm(nn.Module):
        def __init__(self, dim, eps=1e-5):
            super().__init__()
            self.scale, self.eps = dim ** -0.5, eps
            self.g = nn.Parameter(torch.ones(1))

        def forward(self, x):
            return x / (torch.norm(x, dim=-1, keepdim=True) * self.scale).clamp(min=self.eps) * self.g

    class Scale(nn.Module):
        def __init__(self, dim):
            super().__init__()
            self.scale = nn.Parameter(torch.ones(dim))

        def forward(self, x):
            return x * self.scale

    class GAU(nn.Module):
        def __init__(self, d=256, s=128, expansion=2):
            super().__init__()
            self.e, self.s = d * expansion, s
            self.uv = nn.Linear(d, 2 * self.e + s, bias=False)
            self.gamma = nn.Parameter(torch.zeros(2, s))
            self.beta = nn.Parameter(torch.zeros(2, s))
            self.o = nn.Linear(self.e, d, bias=False)
            self.ln = ScaleNorm(d)
            self.res_scale = Scale(d)

        def forward(self, x):
            uv = torch.nn.functional.silu(self.uv(self.ln(x)))
            u, v, base = torch.split(uv, [self.e, self.e, self.s], dim=2)
            base = base.unsqueeze(2) * self.gamma[None, None] + self.beta
            q, k = base[:, :, 0], base[:, :, 1]
            kernel = torch.square(torch.relu(torch.bmm(q, k.transpose(1, 2)) / math.sqrt(self.s)))
            return self.res_scale(x) + self.o(u * torch.bmm(kernel, v))

    class RacketPose(nn.Module):
        def __init__(self):
            super().__init__()
            bb = nn.Module()
            bb.stem = nn.Sequential(ConvModule(3, 24, 3, 2), ConvModule(24, 24, 3), ConvModule(24, 48, 3))
            bb.stage1 = nn.Sequential(ConvModule(48, 96, 3, 2), CSPLayer(96, 96, 2, True))
            bb.stage2 = nn.Sequential(ConvModule(96, 192, 3, 2), CSPLayer(192, 192, 4, True))
            bb.stage3 = nn.Sequential(ConvModule(192, 384, 3, 2), CSPLayer(384, 384, 4, True))
            bb.stage4 = nn.Sequential(ConvModule(384, 768, 3, 2), SPP(768), CSPLayer(768, 768, 2, False))
            self.backbone = bb
            hd = nn.Module()
            hd.final_layer = nn.Conv2d(768, num_kp, 7, padding=3)
            hd.mlp = nn.Sequential(ScaleNorm((size // 32) ** 2), nn.Linear((size // 32) ** 2, 256, bias=False))
            hd.gau = GAU()
            hd.cls_x = nn.Linear(256, int(size * split), bias=False)
            hd.cls_y = nn.Linear(256, int(size * split), bias=False)
            self.head = hd

        def forward(self, x):
            b = self.backbone
            for m in (b.stem, b.stage1, b.stage2, b.stage3, b.stage4):
                x = m(x)
            h = self.head
            f = h.gau(h.mlp(h.final_layer(x).flatten(2)))
            return h.cls_x(f), h.cls_y(f)
    return RacketPose()


def load(ckpt: Path):
    import torch

    state = torch.load(ckpt, map_location="cpu", weights_only=False, pickle_module=_stub_pickle())
    state = {k.removeprefix("module."): v for k, v in state.get("state_dict", state).items()}
    model = build()
    model.load_state_dict(state)
    return model.eval()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="models/racketpose.pth")
    ap.add_argument("--out", default="models/racketpose.onnx")
    args = ap.parse_args()
    import torch

    ckpt = Path(args.ckpt)
    if not ckpt.exists():
        ckpt.parent.mkdir(parents=True, exist_ok=True)
        print(f"descargando {URL}")
        urllib.request.urlretrieve(URL, ckpt)
    model = load(ckpt)
    torch.onnx.export(model, torch.zeros(1, 3, 256, 256), args.out, input_names=["input"],
                      output_names=["simcc_x", "simcc_y"], dynamic_axes={"input": {0: "n"}},
                      opset_version=17, dynamo=False)
    print(f"guardado {args.out}")


if __name__ == "__main__":
    sys.exit(main())
