"""Export the WASB ball tracker (NTT, BMVC 2023, MIT licence; HRNet, its tennis weights) to ONNX.

Candidate of docs/plan_maestro.md, "Plan a corto plazo (02-11)", paso 2 (B-7 / B-15c): measured on the PC against
our TrackNetV3 (scripts/bench_candidates.py); not used by any stage.

The network is re-declared here in plain PyTorch (the HRNet of WASB-SBDT `src/models/hrnet.py`, MIT, with its
`configs/model/wasb.yaml` fixed in the code), so WASB's repository and its CUDA-only runner are not needed.
Input: frames t-1, t, t+1 at 512x288, RGB, ImageNet-normalised, stacked to 9 channels. Output: the ball heatmap
(sigmoid) of each of the 3 frames, (n, 3, 288, 512); the wrapper (tennisbio.candidates.wasb) reads the middle one.

Weights: Google Drive file 14AeyIOCQ2UaQmbZLNQJa1H_eSwxUXk7z (wasb_tennis_best.pth.tar), linked from
https://github.com/nttcom/WASB-SBDT/blob/main/MODEL_ZOO.md (row "WASB (Ours)", column Tennis).

    uv run python scripts/export_wasb.py [--out models/wasb_tennis.onnx]

Needs torch (`uv sync --extra yolo`). Prints the largest difference between the ONNX model (onnxruntime CPU) and
PyTorch on a random input.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _candidate_export import check_onnx, download  # noqa: E402

URL = "https://drive.usercontent.google.com/download?id=14AeyIOCQ2UaQmbZLNQJa1H_eSwxUXk7z&export=download&confirm=t"
W, H, FRAMES = 512, 288, 3

# WASB-SBDT configs/model/wasb.yaml
STAGES = {
    "STAGE1": {"NUM_MODULES": 1, "NUM_BRANCHES": 1, "BLOCK": "BOTTLENECK", "NUM_BLOCKS": [1], "NUM_CHANNELS": [32]},
    "STAGE2": {"NUM_MODULES": 1, "NUM_BRANCHES": 2, "BLOCK": "BASIC", "NUM_BLOCKS": [2, 2], "NUM_CHANNELS": [16, 32]},
    "STAGE3": {"NUM_MODULES": 1, "NUM_BRANCHES": 3, "BLOCK": "BASIC", "NUM_BLOCKS": [2, 2, 2], "NUM_CHANNELS": [16, 32, 64]},
    "STAGE4": {"NUM_MODULES": 1, "NUM_BRANCHES": 4, "BLOCK": "BASIC", "NUM_BLOCKS": [2, 2, 2, 2],
               "NUM_CHANNELS": [16, 32, 64, 128]},
}
STEM_INPLANES = 64


def build():
    """WASB's HRNet (same module names as the original, so its state dict loads strictly). Copyright (c) Microsoft,
    MIT licence (HRNet), as modified in WASB-SBDT (MIT)."""
    import torch
    from torch import nn

    BN_MOMENTUM = 0.1

    class BasicBlock(nn.Module):
        expansion = 1

        def __init__(self, inplanes, planes, stride=1, downsample=None):
            super().__init__()
            self.conv1 = nn.Conv2d(inplanes, planes, 3, stride, 1, bias=False)
            self.bn1 = nn.BatchNorm2d(planes, momentum=BN_MOMENTUM)
            self.relu = nn.ReLU(inplace=True)
            self.conv2 = nn.Conv2d(planes, planes, 3, 1, 1, bias=False)
            self.bn2 = nn.BatchNorm2d(planes, momentum=BN_MOMENTUM)
            self.downsample = downsample

        def forward(self, x):
            residual = x if self.downsample is None else self.downsample(x)
            out = self.relu(self.bn1(self.conv1(x)))
            out = self.bn2(self.conv2(out))
            return self.relu(out + residual)

    class Bottleneck(nn.Module):
        expansion = 4

        def __init__(self, inplanes, planes, stride=1, downsample=None):
            super().__init__()
            self.conv1 = nn.Conv2d(inplanes, planes, 1, bias=False)
            self.bn1 = nn.BatchNorm2d(planes, momentum=BN_MOMENTUM)
            self.conv2 = nn.Conv2d(planes, planes, 3, stride, 1, bias=False)
            self.bn2 = nn.BatchNorm2d(planes, momentum=BN_MOMENTUM)
            self.conv3 = nn.Conv2d(planes, planes * 4, 1, bias=False)
            self.bn3 = nn.BatchNorm2d(planes * 4, momentum=BN_MOMENTUM)
            self.relu = nn.ReLU(inplace=True)
            self.downsample = downsample

        def forward(self, x):
            residual = x if self.downsample is None else self.downsample(x)
            out = self.relu(self.bn1(self.conv1(x)))
            out = self.relu(self.bn2(self.conv2(out)))
            out = self.bn3(self.conv3(out))
            return self.relu(out + residual)

    blocks = {"BASIC": BasicBlock, "BOTTLENECK": Bottleneck}

    class HighResolutionModule(nn.Module):
        def __init__(self, num_branches, block, num_blocks, num_inchannels, num_channels):
            super().__init__()
            self.num_inchannels = list(num_inchannels)
            self.num_branches = num_branches
            self.branches = nn.ModuleList([self._branch(i, block, num_blocks, num_channels) for i in range(num_branches)])
            self.fuse_layers = self._fuse()
            self.relu = nn.ReLU(True)

        def _branch(self, i, block, num_blocks, num_channels):
            down = None
            if self.num_inchannels[i] != num_channels[i] * block.expansion:
                down = nn.Sequential(nn.Conv2d(self.num_inchannels[i], num_channels[i] * block.expansion, 1, 1, bias=False),
                                     nn.BatchNorm2d(num_channels[i] * block.expansion, momentum=BN_MOMENTUM))
            layers = [block(self.num_inchannels[i], num_channels[i], 1, down)]
            self.num_inchannels[i] = num_channels[i] * block.expansion
            layers += [block(self.num_inchannels[i], num_channels[i]) for _ in range(1, num_blocks[i])]
            return nn.Sequential(*layers)

        def _fuse(self):
            if self.num_branches == 1:
                return None
            c = self.num_inchannels
            out = []
            for i in range(self.num_branches):
                row = []
                for j in range(self.num_branches):
                    if j > i:
                        row.append(nn.Sequential(nn.Conv2d(c[j], c[i], 1, 1, 0, bias=False), nn.BatchNorm2d(c[i]),
                                                 nn.Upsample(scale_factor=2 ** (j - i), mode="nearest")))
                    elif j == i:
                        row.append(None)
                    else:
                        convs = []
                        for k in range(i - j):
                            if k == i - j - 1:
                                convs.append(nn.Sequential(nn.Conv2d(c[j], c[i], 3, 2, 1, bias=False), nn.BatchNorm2d(c[i])))
                            else:
                                convs.append(nn.Sequential(nn.Conv2d(c[j], c[j], 3, 2, 1, bias=False), nn.BatchNorm2d(c[j]),
                                                           nn.ReLU(True)))
                        row.append(nn.Sequential(*convs))
                out.append(nn.ModuleList(row))
            return nn.ModuleList(out)

        def forward(self, x):
            if self.num_branches == 1:
                return [self.branches[0](x[0])]
            x = [self.branches[i](x[i]) for i in range(self.num_branches)]
            fused = []
            for i in range(len(self.fuse_layers)):
                y = x[0] if i == 0 else self.fuse_layers[i][0](x[0])
                for j in range(1, self.num_branches):
                    y = y + (x[j] if i == j else self.fuse_layers[i][j](x[j]))
                fused.append(self.relu(y))
            return fused

    def transition(pre, cur):
        layers = []
        for i in range(len(cur)):
            if i < len(pre):
                layers.append(None if cur[i] == pre[i] else nn.Sequential(
                    nn.Conv2d(pre[i], cur[i], 3, 1, 1, bias=False), nn.BatchNorm2d(cur[i], momentum=BN_MOMENTUM),
                    nn.ReLU(inplace=True)))
            else:
                convs = []
                for j in range(i + 1 - len(pre)):
                    o = cur[i] if j == i - len(pre) else pre[-1]
                    convs.append(nn.Sequential(nn.Conv2d(pre[-1], o, 3, 2, 1, bias=False),
                                               nn.BatchNorm2d(o, momentum=BN_MOMENTUM), nn.ReLU(inplace=True)))
                layers.append(nn.Sequential(*convs))
        return nn.ModuleList(layers)

    def stage(cfg, inch):
        mods = []
        for _ in range(cfg["NUM_MODULES"]):
            mods.append(HighResolutionModule(cfg["NUM_BRANCHES"], blocks[cfg["BLOCK"]], cfg["NUM_BLOCKS"], inch,
                                             cfg["NUM_CHANNELS"]))
            inch = mods[-1].num_inchannels
        return nn.Sequential(*mods), inch

    class HRNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.conv1 = nn.Conv2d(3 * FRAMES, STEM_INPLANES, 3, 1, 1, bias=False)
            self.bn1 = nn.BatchNorm2d(STEM_INPLANES, momentum=BN_MOMENTUM)
            self.conv2 = nn.Conv2d(STEM_INPLANES, STEM_INPLANES, 3, 1, 1, bias=False)
            self.bn2 = nn.BatchNorm2d(STEM_INPLANES, momentum=BN_MOMENTUM)
            self.relu = nn.ReLU(inplace=True)
            s1 = STAGES["STAGE1"]
            ch1 = s1["NUM_CHANNELS"][0]
            down = nn.Sequential(nn.Conv2d(STEM_INPLANES, ch1 * 4, 1, 1, bias=False), nn.BatchNorm2d(ch1 * 4, momentum=BN_MOMENTUM))
            self.layer1 = nn.Sequential(Bottleneck(STEM_INPLANES, ch1, 1, down),
                                        *[Bottleneck(ch1 * 4, ch1) for _ in range(1, s1["NUM_BLOCKS"][0])])
            pre = [ch1 * 4]
            for k, name in ((1, "STAGE2"), (2, "STAGE3"), (3, "STAGE4")):
                cur = STAGES[name]["NUM_CHANNELS"]
                setattr(self, f"transition{k}", transition(pre, cur))
                st, pre = stage(STAGES[name], cur)
                setattr(self, f"stage{k + 1}", st)
            self.deconv_layers = nn.ModuleList()
            self.final_layers = nn.ModuleList([nn.Conv2d(pre[0], FRAMES, 1)])

        def forward(self, x):
            x = self.relu(self.bn1(self.conv1(x)))
            x = self.relu(self.bn2(self.conv2(x)))
            y = [self.layer1(x)]
            for k in (1, 2, 3):
                tr, st = getattr(self, f"transition{k}"), getattr(self, f"stage{k + 1}")
                xs = []
                for i in range(len(tr)):
                    if tr[i] is None:
                        xs.append(y[i])
                    else:
                        xs.append(tr[i](y[-1]))
                y = st(xs)
            return torch.sigmoid(self.final_layers[0](y[0]))       # (n, 3, 288, 512): one heatmap per frame
    return HRNet()


def load(ckpt: Path):
    import torch

    state = torch.load(ckpt, map_location="cpu", weights_only=True)
    state = state.get("model_state_dict", state)
    model = build()
    model.load_state_dict({k.removeprefix("module."): v for k, v in state.items()})
    return model.eval()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="models/wasb_tennis_best.pth.tar")
    ap.add_argument("--out", default="models/wasb_tennis.onnx")
    args = ap.parse_args()
    import torch

    ckpt = download(URL, Path(args.ckpt))
    model = load(ckpt)
    x = torch.zeros(1, 3 * FRAMES, H, W)
    torch.onnx.export(model, x, args.out, input_names=["frames"], output_names=["heatmaps"],
                      dynamic_axes={"frames": {0: "n"}, "heatmaps": {0: "n"}}, opset_version=17, dynamo=False)
    diff = check_onnx(model, args.out, [torch.randn(2, 3 * FRAMES, H, W)])
    print(f"guardado {args.out}; diferencia máxima ONNX frente a PyTorch: {diff:.2e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
