"""Export TennisCourtDetector (yastrebksv, MIT licence: 14 court points from a broadcast frame) to ONNX.

Candidate of docs/plan_maestro.md, "Plan a corto plazo (02-11)", paso 2 (B-9 / B-15c): measured on the PC against
our line-based court fit (tennisbio.court) with scripts/bench_candidates.py; not used by any stage.

The network (a TrackNet-like encoder-decoder with 15 output channels: the 14 points and the court centre) is
re-declared here in plain PyTorch (TennisCourtDetector `tracknet.py`, MIT). Input: the frame resized to 640x360,
BGR, /255. Output: the 15 heatmaps after the sigmoid, (n, 15, 360, 640). Post-processing (circle on each heatmap,
refinement on the lines, homography): tennisbio.candidates.court14.

Weights: Google Drive file 1f-Co64ehgq4uddcQm1aFBDtbnyZhQvgG (model_tennis_court_det.pt), linked from
https://github.com/yastrebksv/TennisCourtDetector (README, "Pretrained model").

    uv run python scripts/export_court_tcd.py [--out models/court_tcd.onnx]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _candidate_export import check_onnx, download  # noqa: E402

URL = "https://drive.usercontent.google.com/download?id=1f-Co64ehgq4uddcQm1aFBDtbnyZhQvgG&export=download&confirm=t"
W, H, OUT = 640, 360, 15


def build():
    import torch
    from torch import nn

    class ConvBlock(nn.Module):
        def __init__(self, i, o):
            super().__init__()
            self.block = nn.Sequential(nn.Conv2d(i, o, 3, stride=1, padding=1, bias=True), nn.ReLU(), nn.BatchNorm2d(o))

        def forward(self, x):
            return self.block(x)

    class BallTrackerNet(nn.Module):
        def __init__(self):
            super().__init__()
            chans = [(3, 64), (64, 64), (64, 128), (128, 128), (128, 256), (256, 256), (256, 256), (256, 512),
                     (512, 512), (512, 512), (512, 256), (256, 256), (256, 256), (256, 128), (128, 128), (128, 64),
                     (64, 64), (64, OUT)]
            for k, (i, o) in enumerate(chans, 1):
                setattr(self, f"conv{k}", ConvBlock(i, o))
            self.pool = nn.MaxPool2d(2, 2)
            self.up = nn.Upsample(scale_factor=2)

        def forward(self, x):
            c = lambda k, y: getattr(self, f"conv{k}")(y)
            x = self.pool(c(2, c(1, x)))
            x = self.pool(c(4, c(3, x)))
            x = self.pool(c(7, c(6, c(5, x))))
            x = self.up(c(10, c(9, c(8, x))))
            x = self.up(c(13, c(12, c(11, x))))
            x = self.up(c(15, c(14, x)))
            return torch.sigmoid(c(18, c(17, c(16, x))))
    return BallTrackerNet()


def load(ckpt: Path):
    import torch

    state = torch.load(ckpt, map_location="cpu", weights_only=True)
    state = state.get("state_dict", state) if isinstance(state, dict) else state
    model = build()
    model.load_state_dict({k.removeprefix("module."): v for k, v in state.items()})
    return model.eval()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="models/model_tennis_court_det.pt")
    ap.add_argument("--out", default="models/court_tcd.onnx")
    args = ap.parse_args()
    import torch

    model = load(download(URL, Path(args.ckpt)))
    torch.onnx.export(model, torch.zeros(1, 3, H, W), args.out, input_names=["image"], output_names=["heatmaps"],
                      dynamic_axes={"image": {0: "n"}, "heatmaps": {0: "n"}}, opset_version=17, dynamo=False)
    diff = check_onnx(model, args.out, [torch.rand(2, 3, H, W)])
    print(f"guardado {args.out}; diferencia máxima ONNX frente a PyTorch: {diff:.2e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
