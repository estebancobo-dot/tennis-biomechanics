"""Export F3ED's hit spotter (F3Set, ICLR 2025; trained on broadcast tennis) to ONNX.

Candidate of docs/plan_maestro.md, "Plan a corto plazo (02-11)", paso 2 (golpes): measured on the PC against our
learned detector (tennisbio.spotting, stage `spotting`) with scripts/bench_candidates.py; not used by any stage.

What is exported is F3ED's localiser and its per-frame labels: RegNetY-002 with temporal shift (TSM, step 2) on each
frame, a bidirectional GRU over the clip, and two heads: hit / no hit (softmax) and the 29 elements (sigmoid; side,
position, serve/return/stroke, forehand/backhand, technique, direction, outcome). F3ED's contextual module (a
second GRU that only re-labels the hits already found, and needs the players' handedness) is left out: it does not
change which frames are hits.

Everything is re-declared here in plain PyTorch (timm's RegNetY-002 layout, F3Set's `model/impl/tsm.py` and
`model/modules.py`), so neither timm nor F3Set's repository is needed. Input: (n, 96, 3, 224, 224): 96 frames
taken every 2nd frame of 25-30 fps video (the model was trained so; at 50/60 fps take every 4th), each resized to
224 px high and centre-cropped to 224x224, RGB, /255, ImageNet-normalised. Outputs: `hit` (n, 96, 2) softmax and
`elements` (n, 96, 29) sigmoid. Decoding: tennisbio.candidates.f3ed.

Weights: Google Drive folder https://drive.google.com/drive/folders/1SnHkYFWvt4v9E0m5j3J1GbjNH6b0NNuk (linked from
https://github.com/F3Set/F3Set, "Trained models"), subfolder f3ed: checkpoint_049.pt (file
1QM9FSHpZ0e6WWaNepUdIsORc56B4GPEK) and config.json (file 1MILmsh_SF89U-56ymkhYNDDJ7C1FqBre).

    uv run python scripts/export_f3ed.py [--out models/f3ed.onnx]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _candidate_export import check_onnx, download  # noqa: E402

DRIVE = "https://drive.usercontent.google.com/download?id={}&export=download&confirm=t"
CKPT_ID, CONFIG_ID = "1QM9FSHpZ0e6WWaNepUdIsORc56B4GPEK", "1MILmsh_SF89U-56ymkhYNDDJ7C1FqBre"
CLIP, STEP, CROP, CLASSES = 96, 2, 224, 29
# RegNetY-002 (timm regnety_002): stem 32, stage widths and depths, group width 8, SE ratio 0.25
WIDTHS, DEPTHS, GROUP_W, STEM = (24, 56, 152, 368), (1, 1, 4, 7), 8, 32
HIDDEN = 368


def build(clip: int = CLIP, step: int = STEP):
    import torch
    from torch import nn

    def shift(x, n_segment):
        """F3Set's TemporalShift.shift (inplace=False), written with slices and concatenation for ONNX: an 8th of
        the channels comes from `step` frames later, another 8th from `step` frames earlier, the rest stays."""
        nt, c, h, w = x.shape
        x = x.reshape(-1, n_segment, c, h, w)
        fold = c // 8
        zeros = torch.zeros_like(x[:, :step, :fold])
        a = torch.cat([x[:, step:, :fold], zeros], 1)
        b = torch.cat([zeros, x[:, :-step, fold:2 * fold]], 1)
        return torch.cat([a, b, x[:, :, 2 * fold:]], 2).reshape(nt, c, h, w)

    class ConvNormAct(nn.Module):
        def __init__(self, i, o, k=1, s=1, groups=1, act=True):
            super().__init__()
            self.conv = nn.Conv2d(i, o, k, s, (k - 1) // 2, groups=groups, bias=False)
            self.bn = nn.BatchNorm2d(o)
            self.act = nn.ReLU(inplace=True) if act else nn.Identity()

        def forward(self, x):
            return self.act(self.bn(self.conv(x)))

    class Shifted(nn.Module):
        """F3Set's TemporalShift wrapper (its module is `net`, as in the checkpoint)."""

        def __init__(self, net):
            super().__init__()
            self.net = net

        def forward(self, x):
            return self.net(shift(x, clip))

    class SE(nn.Module):
        def __init__(self, c, rd):
            super().__init__()
            self.fc1 = nn.Conv2d(c, rd, 1)
            self.fc2 = nn.Conv2d(rd, c, 1)

        def forward(self, x):
            return x * torch.sigmoid(self.fc2(torch.relu(self.fc1(x.mean((2, 3), keepdim=True)))))

    class Block(nn.Module):
        def __init__(self, i, o, s):
            super().__init__()
            self.conv1 = Shifted(ConvNormAct(i, o, 1))
            self.conv2 = ConvNormAct(o, o, 3, s, groups=o // GROUP_W)
            self.se = SE(o, int(round(i * 0.25)))
            self.conv3 = ConvNormAct(o, o, 1, act=False)
            self.downsample = ConvNormAct(i, o, 1, s, act=False) if (i != o or s != 1) else None
            self.act3 = nn.ReLU(inplace=True)

        def forward(self, x):
            y = self.conv3(self.se(self.conv2(self.conv1(x))))
            return self.act3(y + (x if self.downsample is None else self.downsample(x)))

    class RegNetY002(nn.Module):
        def __init__(self):
            super().__init__()
            self.stem = ConvNormAct(3, STEM, 3, 2)
            i = STEM
            for k, (w, d) in enumerate(zip(WIDTHS, DEPTHS), 1):
                stage = nn.Sequential()
                for b in range(d):
                    stage.add_module(f"b{b + 1}", Block(i if b == 0 else w, w, 2 if b == 0 else 1))
                setattr(self, f"s{k}", stage)
                i = w

        def forward(self, x):
            x = self.s4(self.s3(self.s2(self.s1(self.stem(x)))))
            return x.mean((2, 3))

    class GRUHead(nn.Module):
        def __init__(self):
            super().__init__()
            self._gru = nn.GRU(HIDDEN, HIDDEN, num_layers=1, batch_first=True, bidirectional=True)
            self._fc_out = nn.Module()
            self._fc_out._fc_out = nn.Linear(2 * HIDDEN, HIDDEN)

        def forward(self, x):
            return self._fc_out._fc_out(self._gru(x)[0])

    class F3ED(nn.Module):
        def __init__(self):
            super().__init__()
            self._glb_feat = RegNetY002()
            self._head = GRUHead()
            self._coarse_pred = nn.Linear(HIDDEN, 2)
            self._fine_pred = nn.Linear(HIDDEN, CLASSES)

        def forward(self, frames):
            n, t, c, h, w = frames.shape
            f = self._glb_feat(frames.reshape(n * t, c, h, w)).reshape(n, t, -1)
            e = self._head(f)
            return torch.softmax(self._coarse_pred(e), -1), torch.sigmoid(self._fine_pred(e))
    return F3ED()


def load(ckpt: Path):
    import torch

    state = torch.load(ckpt, map_location="cpu", weights_only=True)
    state = state.get("model_state_dict", state)
    state = {k.removeprefix("module."): v for k, v in state.items() if not k.removeprefix("module.").startswith("_ctx.")}
    model = build()
    model.load_state_dict(state)
    return model.eval()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="models/f3ed")
    ap.add_argument("--out", default="models/f3ed.onnx")
    args = ap.parse_args()
    import torch

    d = Path(args.dir)
    cfg = json.loads(download(DRIVE.format(CONFIG_ID), d / "config.json").read_text())
    want = {"clip_len": CLIP, "stride": STEP, "crop_dim": CROP, "num_classes": CLASSES, "feature_arch": "rny002_tsm",
            "temporal_arch": "gru"}
    bad = {k: cfg.get(k) for k, v in want.items() if cfg.get(k) != v}
    if bad:
        sys.exit(f"config.json de F3ED distinto del previsto: {bad}")
    model = load(download(DRIVE.format(CKPT_ID), d / "checkpoint_049.pt"))
    x = torch.zeros(1, CLIP, 3, CROP, CROP)
    torch.onnx.export(model, x, args.out, input_names=["frames"], output_names=["hit", "elements"],
                      dynamic_axes={"frames": {0: "n"}, "hit": {0: "n"}, "elements": {0: "n"}}, opset_version=17,
                      dynamo=False)
    diff = check_onnx(model, args.out, [torch.randn(1, CLIP, 3, CROP, CROP)])
    print(f"guardado {args.out}; diferencia máxima ONNX frente a PyTorch: {diff:.2e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
