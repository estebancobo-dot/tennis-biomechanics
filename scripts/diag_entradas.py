"""Whether the learned stroke detector sees each player in the matches as it did in F3Set (13-11: in Osaka the far
player is in the features in 0 % of the play, while the near one is in 96 %; the audit's «Entradas de los modelos»
said so for the first time). If F3Set, where the detector was trained and validated, had her and the matches do not,
it is a training/serving skew like R17 (the ball). Reads only: for each match of the catalogue and each F3Set
compilation of the recount (salidas_<tag>), the detector's features as the spotting stage builds them (no sound
flux), and over the play frames: the share with the near player, with the far player, with a court homography, with
two or more detections, and why the far one was not taken (no court, fewer than two boxes, no box on the far half).
Writes <output>/capturas_diag/diag_entradas.json.

    uv run python scripts/diag_entradas.py [--tag v16] [--max-frames 20000]"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio import layout, match_files as mf, pipeline, stages  # noqa: E402,F401  (registers the stages)
from tennisbio.catalog import load_matches  # noqa: E402
from tennisbio.config import load_config  # noqa: E402


def one(mdir: Path, hand: str, max_frames: int) -> dict:
    from tennisbio.court_metrics import to_court
    from tennisbio.spotting import PERSON_DIM, build_features
    from tennisbio.stages import court_at, play_mask

    f = build_features(mdir, hand)
    X, fps = f["X"], f["fps"]
    play = X[:, -1] > 0
    out = {"play_min": round(float(play.sum()) / fps / 60, 1),
           "near_seen": round(float((X[play, 54] > 0).mean()), 3) if play.any() else None,
           "far_seen": round(float((X[play, PERSON_DIM + 54] > 0).mean()), 3) if play.any() else None}
    # why the far one is missing, on a sample of the play frames
    with np.load(mf.at(mdir, "players.npz"), allow_pickle=True) as z:
        frames = np.asarray(z["frames"], int)
        boxes = z["boxes"]
    court = json.loads(mf.at(mdir, "court.json").read_text(encoding="utf-8")) if mf.at(mdir, "court.json").exists() else None
    pf = [i for i, fr in enumerate(frames) if fr < len(play) and play[fr]]
    if len(pf) > max_frames:
        pf = pf[:: max(1, len(pf) // max_frames)]
    n_h = n_two = n_far_half = 0
    ys = []
    for i in pf:
        bx = boxes[i]
        H = court_at(court, frames[i] / fps)[0] if court else None
        if H is None:
            continue
        n_h += 1
        if len(bx) < 2:
            continue
        n_two += 1
        c = to_court(H, np.c_[(bx[:, 0] + bx[:, 2]) / 2, bx[:, 3]])
        ys += [float(v) for v in c[:, 1] if np.isfinite(v)]
        if ((np.abs(c[:, 0]) <= 6.5) & (c[:, 1] >= 13.0) & (c[:, 1] <= 31.0)).any():
            n_far_half += 1
    k = max(1, len(pf))
    out.update(sample=len(pf), with_court=round(n_h / k, 3), two_or_more_boxes=round(n_two / k, 3),
               a_box_on_the_far_half=round(n_far_half / k, 3),
               feet_y_m_percentiles=[round(float(np.percentile(ys, q)), 1) for q in (5, 25, 50, 75, 95)] if ys else None,
               boxes_per_frame=round(float(np.mean([len(boxes[i]) for i in pf])), 2) if pf else None)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="v16", help="F3Set: salidas_<tag> del recuento")
    ap.add_argument("--max-frames", type=int, default=20000)
    a = ap.parse_args()
    cfg = load_config()
    out_root = Path((cfg.get("paths") or {}).get("output") or "output")
    rep = {"partidos": {}, "f3set": {}}
    for m in load_matches(cfg):
        d = layout.dir_of(out_root, m, cfg)
        if not mf.at(d, "players.npz").exists():
            continue
        try:
            rep["partidos"][m.id] = one(d, m.player.hand, a.max_frames)
        except Exception as e:  # noqa: BLE001 — a diagnosis: each match on its own, the error said in the report
            rep["partidos"][m.id] = {"error": f"{type(e).__name__}: {e}"}
        print(m.id, rep["partidos"][m.id], flush=True)
    rec = out_root.parent / "datasets" / "f3set" / "recall" / f"salidas_{a.tag}"
    for d in sorted(rec.glob("recall_*")) if rec.exists() else []:
        if not mf.at(d, "players.npz").exists():
            continue
        try:
            rep["f3set"][d.name] = one(d, "right", a.max_frames)
        except Exception as e:  # noqa: BLE001 — a diagnosis: each compilation on its own, the error said
            rep["f3set"][d.name] = {"error": f"{type(e).__name__}: {e}"}
        print(d.name, rep["f3set"][d.name], flush=True)
    dst = out_root / "capturas_diag"
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "diag_entradas.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
