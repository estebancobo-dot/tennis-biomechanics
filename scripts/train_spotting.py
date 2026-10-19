"""Trains and measures the learned stroke spotter (tennisbio.spotting) on the F3Set numbers the PC exported
(scripts/spotting_data.py → pc-logs/entreno_golpes/*.npz). Runs in the cloud session (hybrid plan, 19-10):
no video here, only features.

Split by match: Rybakina's matches ("test") are never seen in training; two training matches are held out to
choose the detection threshold. Writes models/spotting.onnx (with the feature normalisation inside),
models/spotting.json (classes, fps, threshold, measures) and docs/validacion_detector.md (the measure, in Spanish).

    uv run python scripts/train_spotting.py DATA_DIR [--epochs 40] [--seed 0]
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tennisbio import spotting as S  # noqa: E402


def load(data_dir: Path) -> list[dict]:
    out = []
    for f in sorted(Path(data_dir).glob("*.npz")):
        with np.load(f, allow_pickle=False) as z:
            fps = float(z["fps"])
            X = z["X"].astype(np.float32)
            ev = [{"t": float(t), "side": S.SIDES[int(s)], "kind": S.KINDS[int(k)]}
                  for t, s, k in zip(z["ev_t"], z["ev_side"], z["ev_kind"])]
            out.append({"name": str(z["name"]), "split": str(z["split"]), "fps": fps, "X": X, "events": ev,
                        "spans": z["spans"].reshape(-1, 2), "y": S.labels_for(
                            [{**e, "kind": {"other": "volley_other"}.get(e["kind"], e["kind"])} for e in ev], len(X), fps)})
    return out


def model_class(F: int, C: int, width: int = 96):
    import torch
    from torch import nn

    class Block(nn.Module):
        def __init__(self, d):
            super().__init__()
            self.c1 = nn.Conv1d(width, width, 3, padding=d, dilation=d)
            self.c2 = nn.Conv1d(width, width, 1)
            self.act = nn.GELU()
            self.drop = nn.Dropout(0.1)

        def forward(self, x):
            return x + self.c2(self.drop(self.act(self.c1(x))))

    class Spotter(nn.Module):
        """(batch, frames, F) → (batch, frames, C) class probabilities; the normalisation is part of the model."""

        def __init__(self, mean, std):
            super().__init__()
            self.register_buffer("mean", torch.tensor(mean, dtype=torch.float32))
            self.register_buffer("std", torch.tensor(std, dtype=torch.float32))
            self.inp = nn.Conv1d(F, width, 5, padding=2)
            self.blocks = nn.Sequential(*[Block(d) for d in (1, 2, 4, 8, 1, 2, 4)])
            self.out = nn.Conv1d(width, C, 1)

        def logits(self, x):
            x = ((x - self.mean) / self.std).transpose(1, 2)
            return self.out(self.blocks(torch.nn.functional.gelu(self.inp(x)))).transpose(1, 2)

        def forward(self, x):
            return torch.softmax(self.logits(x), dim=-1)

    return Spotter


def windows(m: dict, length=256, stride=128):
    n = len(m["X"])
    for a in range(0, max(1, n - length + 1), stride):
        yield m["X"][a:a + length], m["y"][a:a + length]


def predict(net, X: np.ndarray) -> np.ndarray:
    import torch
    with torch.no_grad():
        return net(torch.from_numpy(X[None])).numpy()[0]


def in_spans(pred, spans, pad=0.5):
    return [p for p in pred if any(a - pad <= p["t"] <= b + pad for a, b in spans)]


def measure(net, ms: list[dict], thr: float) -> dict:
    preds, gts = [], []
    per = []
    for k, m in enumerate(ms):
        p = in_spans(S.decode(predict(net, m["X"]), m["fps"], thr), m["spans"])
        r = S.evaluate(p, m["events"])
        per.append({"match": m["name"], **{x: r[x] for x in ("gt", "found", "recall", "precision")},
                    "near": r["near"]["recall"], "far": r["far"]["recall"]})
        sh = 1e6 * k
        preds += [{**x, "t": x["t"] + sh} for x in p]
        gts += [{**x, "t": x["t"] + sh} for x in m["events"]]
    return {"total": S.evaluate(preds, gts), "per_match": per}


def main():
    import torch

    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    torch.manual_seed(args.seed)
    rng = np.random.default_rng(args.seed)
    ms = load(Path(args.data))
    test = [m for m in ms if m["split"] == "test"]
    train_all = [m for m in ms if m["split"] != "test"]
    if len(train_all) < 3 or not test:
        sys.exit(f"Pocos datos: {len(train_all)} partidos de entrenamiento y {len(test)} de prueba")
    val = train_all[-2:]
    train = train_all[:-2]
    Xcat = np.concatenate([m["X"] for m in train])
    mean, std = Xcat.mean(0), Xcat.std(0) + 1e-3
    C = len(S.CLASSES)
    net = model_class(Xcat.shape[1], C)(mean, std)
    counts = np.bincount(np.concatenate([m["y"] for m in train]), minlength=C).astype(float)
    w = torch.tensor(np.where(counts > 0, (counts.sum() / np.maximum(counts, 1)) ** 0.5, 1.0), dtype=torch.float32)
    w = w / w[0]
    opt = torch.optim.AdamW(net.parameters(), lr=2e-3, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, args.epochs)
    data = [wnd for m in train for wnd in windows(m)]
    t0 = time.time()
    for ep in range(args.epochs):
        net.train()
        rng.shuffle(data)
        tot = 0.0
        for b in range(0, len(data), 16):
            xb = torch.from_numpy(np.stack([x for x, _ in data[b:b + 16]]))
            yb = torch.from_numpy(np.stack([y for _, y in data[b:b + 16]]))
            xb = xb + 0.02 * torch.randn_like(xb) * torch.from_numpy(std)
            loss = torch.nn.functional.cross_entropy(net.logits(xb).reshape(-1, C), yb.reshape(-1), weight=w)
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += float(loss)
        sched.step()
        if ep % 5 == 4 or ep == args.epochs - 1:
            print(f"época {ep + 1}: pérdida {tot / max(1, len(data) // 16):.3f} ({time.time() - t0:.0f} s)", flush=True)
    net.eval()
    best = max(((measure(net, val, t)["total"], t) for t in np.arange(0.2, 0.85, 0.05)),
               key=lambda rt: (2 * (rt[0]["recall"] or 0) * (rt[0]["precision"] or 0)
                               / max(1e-9, (rt[0]["recall"] or 0) + (rt[0]["precision"] or 0))))
    thr = round(float(best[1]), 2)
    res = measure(net, test, thr)
    out = ROOT / "models"
    out.mkdir(exist_ok=True)
    torch.onnx.export(net, torch.zeros(1, 64, Xcat.shape[1]), out / "spotting.onnx", input_names=["features"],
                      output_names=["prob"], dynamic_axes={"features": {1: "frames"}, "prob": {1: "frames"}}, opset_version=17,
                      dynamo=False)
    meta = {"classes": list(S.CLASSES), "feature_dim": int(Xcat.shape[1]), "fps": train[0]["fps"], "threshold": thr,
            "train_matches": [m["name"] for m in train], "val_matches": [m["name"] for m in val],
            "test_matches": [m["name"] for m in test], "epochs": args.epochs, "seed": args.seed,
            "val": best[0], "test": res}
    (out / "spotting.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    (ROOT / "docs" / "validacion_detector.md").write_text(report(meta), encoding="utf-8")
    print(report(meta))


def report(meta: dict) -> str:
    t = meta["test"]["total"]
    pct = lambda x: "—" if x is None else f"{x * 100:.0f} %"
    L = ["# Detector de golpes entrenado: medida", "",
         f"Entrenado con {len(meta['train_matches'])} partidos de F3Set; umbral elegido con {len(meta['val_matches'])} "
         f"partidos aparte; medido en {len(meta['test_matches'])} partidos de Rybakina que **no** vio al entrenar "
         f"(±0,2 s, mismo lado). Lo genera `scripts/train_spotting.py`.", "",
         f"**Golpes encontrados: {t['found']} de {t['gt']} ({pct(t['recall'])})**, precisión {pct(t['precision'])}, "
         f"tipo de golpe acertado en el {pct(t['kind_accuracy'])} de los encontrados.", "",
         "| | saque | derecha | revés | otro | total |", "|---|---|---|---|---|---|"]
    for side, name in (("near", "cercana"), ("far", "lejana")):
        s = t[side]
        L.append(f"| {name} | " + " | ".join(f"{s[k]['found']}/{s[k]['gt']}" for k in S.KINDS)
                 + f" | **{s['found']}/{s['gt']}** ({pct(s['recall'])}) |")
    L += ["", "| Partido | encontrados | recall | precisión | cercana | lejana |", "|---|---|---|---|---|---|"]
    for p in meta["test"]["per_match"]:
        L.append(f"| {p['match']} | {p['found']}/{p['gt']} | {pct(p['recall'])} | {pct(p['precision'])} | "
                 f"{pct(p['near'])} | {pct(p['far'])} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
