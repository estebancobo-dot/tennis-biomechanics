"""Export MotionAGFormer (Mehraban et al., WACV 2024, Apache-2.0; github.com/TaatiTeam/MotionAGFormer) to ONNX.

Candidate of paso 2.5 (B3, request #203): a 2D→3D lifter for the trunk rotation (shoulder and hip turn), measured
on the PC against our RTMW3D (tennisbio.pose.wholebody3d) with scripts/bench_candidates.py on CalTennis; not used by
any stage. It lifts a sequence of 17 Human3.6M joints (x, y normalised to the image width, and the 2D score) to 3D
relative to the pelvis, so it reuses the 2D pose the fine pass already has (tennisbio.candidates.motionagformer).

The network is re-declared here in plain PyTorch (the repository's `model/MotionAGFormer.py` and its modules,
Apache-2.0, without timm: drop path 0 is the identity) with the same module names, so the published checkpoints load
strictly. The fixed spatial graph is a constant; the temporal graph (top-2 most similar frames) is computed in the
graph, as in the original.

Weights (Human3.6M, Google Drive files linked from the repository's README, table "H3.6M weights"):

    xs  27 frames  1Pab7cPvnWG8NOVd0nnL1iqAfYCUY4hDH   (12 layers, 64 channels, 2.2 M parameters)
    s   81 frames  1DrF7WZdDvRPsH12gQm5DPXbviZ4waYFf   (26 layers, 64 channels, 4.8 M parameters)

The ONNX input is fixed to (2, frames, 17, 3): the sequence and its left-right flip, as the original demo averages
them (fixed shapes are what DirectML compiles once).

    uv run python scripts/export_motionagformer.py [--size xs|s] [--out models/motionagformer_xs.onnx]

Needs torch (`uv sync --extra yolo`). Prints the largest difference between the ONNX model (onnxruntime CPU) and
PyTorch on a random input.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _candidate_export import check_onnx, download  # noqa: E402

DRIVE = "https://drive.usercontent.google.com/download?id={}&export=download&confirm=t"
SIZES = {   # configs/h36m/MotionAGFormer-{xsmall,small}.yaml
    "xs": {"id": "1Pab7cPvnWG8NOVd0nnL1iqAfYCUY4hDH", "n_layers": 12, "dim_feat": 64, "n_frames": 27},
    "s": {"id": "1DrF7WZdDvRPsH12gQm5DPXbviZ4waYFf", "n_layers": 26, "dim_feat": 64, "n_frames": 81},
}
COMMON = {"dim_rep": 512, "mlp_ratio": 4, "num_heads": 8, "neighbour_num": 2, "layer_scale_init_value": 1e-5}
JOINTS = 17
# model/modules/graph.py CONNECTIONS (Human3.6M skeleton)
CONNECTIONS = {10: [9], 9: [8, 10], 8: [7, 9], 14: [15, 8], 15: [16, 14], 11: [12, 8], 12: [13, 11],
               7: [0, 8], 0: [1, 7], 1: [2, 0], 2: [3, 1], 4: [5, 0], 5: [6, 4], 16: [15], 13: [12], 3: [2], 6: [5]}


def build(size: str = "xs", n_frames: int | None = None):
    """MotionAGFormer for Human3.6M with the configuration of `size` (module names as the checkpoints)."""
    import torch
    from torch import nn

    cfg = {**COMMON, **SIZES[size]}
    T = n_frames or cfg["n_frames"]

    class Attention(nn.Module):
        def __init__(self, dim, num_heads, mode):
            super().__init__()
            self.num_heads, self.mode = num_heads, mode
            self.scale = (dim // num_heads) ** -0.5
            self.proj = nn.Linear(dim, dim)
            self.qkv = nn.Linear(dim, dim * 3, bias=False)

        def forward(self, x):
            B, T_, J, C = x.shape
            qkv = self.qkv(x).reshape(B, T_, J, 3, self.num_heads, C // self.num_heads).permute(3, 0, 4, 1, 2, 5)
            q, k, v = qkv[0], qkv[1], qkv[2]                                     # (B, H, T, J, c)
            if self.mode == "temporal":
                q, k, v = q.transpose(2, 3), k.transpose(2, 3), v.transpose(2, 3)   # (B, H, J, T, c)
                a = ((q @ k.transpose(-2, -1)) * self.scale).softmax(-1)
                x = (a @ v).permute(0, 3, 2, 1, 4).reshape(B, T_, J, C)
            else:
                a = ((q @ k.transpose(-2, -1)) * self.scale).softmax(-1)
                x = (a @ v).permute(0, 2, 3, 1, 4).reshape(B, T_, J, C)
            return self.proj(x)

    def norm_adj(adj):                      # GCN.normalize_digraph: D^-1/2 A D^-1/2 (row degrees)
        d = adj.sum(-1) ** -0.5
        return adj * d.unsqueeze(-1) * d.unsqueeze(-2)

    class GCN(nn.Module):
        def __init__(self, dim, num_nodes, neighbour_num, mode):
            super().__init__()
            self.mode, self.neighbour_num = mode, neighbour_num
            self.relu = nn.ReLU()
            self.U, self.V = nn.Linear(dim, dim), nn.Linear(dim, dim)
            self.batch_norm = nn.BatchNorm1d(num_nodes)
            if mode == "spatial":
                adj = torch.zeros(num_nodes, num_nodes)
                for i in range(num_nodes):
                    for j in CONNECTIONS[i]:
                        adj[i, j] = 1
                self.register_buffer("adj", norm_adj(adj[None])[0], persistent=False)   # not in the checkpoint

        def forward(self, x):
            b, t, j, c = x.shape
            if self.mode == "temporal":
                x = x.transpose(1, 2).reshape(-1, t, c)
                sim = x @ x.transpose(1, 2)
                thr = sim.topk(k=self.neighbour_num, dim=-1, largest=True)[0][..., -1:]
                adj = norm_adj((sim >= thr).float())
            else:
                x = x.reshape(-1, j, c)
                adj = self.adj
            x = self.relu(x + self.batch_norm(adj @ self.V(x) + self.U(x)))
            return x.reshape(-1, t, j, c) if self.mode == "spatial" else x.reshape(-1, j, t, c).transpose(1, 2)

    class MLP(nn.Module):
        def __init__(self, dim, hidden):
            super().__init__()
            self.fc1, self.act, self.fc2 = nn.Linear(dim, hidden), nn.GELU(), nn.Linear(hidden, dim)

        def forward(self, x):
            return self.fc2(self.act(self.fc1(x)))

    class AGFormerBlock(nn.Module):
        def __init__(self, dim, mode, mixer):
            super().__init__()
            self.norm1, self.norm2 = nn.LayerNorm(dim), nn.LayerNorm(dim)
            self.mixer = (Attention(dim, cfg["num_heads"], mode) if mixer == "attention"
                          else GCN(dim, JOINTS if mode == "spatial" else T, cfg["neighbour_num"], mode))
            self.mlp = MLP(dim, int(dim * cfg["mlp_ratio"]))
            self.layer_scale_1 = nn.Parameter(cfg["layer_scale_init_value"] * torch.ones(dim))
            self.layer_scale_2 = nn.Parameter(cfg["layer_scale_init_value"] * torch.ones(dim))

        def forward(self, x):
            x = x + self.layer_scale_1 * self.mixer(self.norm1(x))
            return x + self.layer_scale_2 * self.mlp(self.norm2(x))

    class MotionAGFormerBlock(nn.Module):
        def __init__(self, dim):
            super().__init__()
            self.att_spatial = AGFormerBlock(dim, "spatial", "attention")
            self.att_temporal = AGFormerBlock(dim, "temporal", "attention")
            self.graph_spatial = AGFormerBlock(dim, "spatial", "graph")
            self.graph_temporal = AGFormerBlock(dim, "temporal", "graph")
            self.fusion = nn.Linear(dim * 2, 2)

        def forward(self, x):
            xa = self.att_temporal(self.att_spatial(x))
            xg = self.graph_temporal(self.graph_spatial(x))
            alpha = self.fusion(torch.cat((xa, xg), dim=-1)).softmax(dim=-1)
            return xa * alpha[..., 0:1] + xg * alpha[..., 1:2]

    class MotionAGFormer(nn.Module):
        def __init__(self):
            super().__init__()
            d = cfg["dim_feat"]
            self.joints_embed = nn.Linear(3, d)
            self.pos_embed = nn.Parameter(torch.zeros(1, JOINTS, d))
            self.norm = nn.LayerNorm(d)
            self.layers = nn.Sequential(*[MotionAGFormerBlock(d) for _ in range(cfg["n_layers"])])
            self.rep_logit = nn.Sequential()
            self.rep_logit.add_module("fc", nn.Linear(d, cfg["dim_rep"]))
            self.rep_logit.add_module("act", nn.Tanh())
            self.head = nn.Linear(cfg["dim_rep"], 3)

        def forward(self, x):                                      # (B, T, 17, 3) → (B, T, 17, 3)
            x = self.joints_embed(x) + self.pos_embed
            x = self.norm(self.layers(x))
            return self.head(self.rep_logit(x))
    return MotionAGFormer()


def load(ckpt: Path, size: str):
    import torch

    state = torch.load(ckpt, map_location="cpu", weights_only=False)      # the published file also holds the optimiser
    state = state.get("model", state)
    model = build(size)
    model.load_state_dict({k.removeprefix("module."): v for k, v in state.items()})
    return model.eval()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", choices=sorted(SIZES), default="xs")
    ap.add_argument("--ckpt", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    import torch

    s = SIZES[args.size]
    ckpt = download(DRIVE.format(s["id"]), Path(args.ckpt or f"models/motionagformer-{args.size}-h36m.pth.tr"))
    out = Path(args.out or f"models/motionagformer_{args.size}.onnx")
    out.parent.mkdir(parents=True, exist_ok=True)
    model = load(ckpt, args.size)
    x = torch.zeros(2, s["n_frames"], JOINTS, 3)
    torch.onnx.export(model, x, str(out), input_names=["joints2d"], output_names=["joints3d"], opset_version=17,
                      dynamo=False)
    diff = check_onnx(model, out, [torch.randn(2, s["n_frames"], JOINTS, 3) * 0.3])
    print(f"guardado {out}; diferencia máxima ONNX frente a PyTorch: {diff:.2e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
