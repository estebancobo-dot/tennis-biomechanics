"""Proof of concept T15 (15-11): the ball model. TOTNet (tennis weights, MIT; scripts/export_totnet.py) against
TrackNetV3 (RacketVision's, what runs today), on RacketVision's annotated broadcast clips: per annotated frame, the
ball found within `tol` px of the annotation (hit), found elsewhere or where the ball is not visible (false), or not
found (miss); precision, recall and F1, and the time per frame. Read only: nothing of the analysis changes.
The same measure as the PC's candidate bench (scripts/bench_candidates.py, «wasb»: F1 of the ball at 10 px on
RacketVision's test clips; 07-11: WASB 0.863 against TrackNetV3 0.906, set aside); TOTNet was not in it.

- TrackNetV3 at its own operating point (its threshold inside tennisbio.ball). TOTNet's threshold (the probability of
  its most likely pixel) is chosen on the validation clips (best F1) and then measured on the test clips.
- Bias, said before measuring: TrackNetV3 was trained on RacketVision (these clips' own domain); TOTNet was not (the
  TrackNet tennis broadcasts). A TOTNet that is not worse here is a strong candidate.
- Rule written before measuring: TOTNet goes on to the end-to-end test (strokes of F3Set with the whole analysis) if
  its test F1 is at least TrackNetV3's minus 0.02; otherwise it is set aside with this measure as the reason.

    python -m tennisbio.infra.poc_bola --modelo models/balltrack.onnx --totnet models/totnet_tennis.onnx \
        --datos /tmp/datasets --salida poc.json [--val 10 --test 30]
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np

TOL_PX = 10
GRID = (0.005, 0.01, 0.02, 0.03, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5)
MARGIN_F1 = 0.02


def read_rows(path: Path) -> list[tuple[int, bool, float, float]]:
    """(frame, visible, x, y) of every annotated frame (the visible and the not visible ones)."""
    with open(path, newline="") as f:
        return [(int(r["Frame"]), bool(int(r["Visibility"])), float(r["X"] or 0), float(r["Y"] or 0))
                for r in csv.DictReader(f)]


def score(pred: dict, rows, thr: float | None = None, tol: float = TOL_PX) -> dict:
    """pred: frame → (x, y, p) (x NaN: not found). thr: also not found below it. Hits, false and missed balls."""
    tp = fp = fn = fp_hidden = 0
    for f, vis, x, y in rows:
        px, py, p = pred.get(f, (np.nan, np.nan, np.nan))
        found = bool(np.isfinite(px)) and (thr is None or (np.isfinite(p) and p >= thr))
        if vis:
            if found and np.hypot(px - x, py - y) <= tol:
                tp += 1
            else:
                fn += 1
                fp += found
        elif found:
            fp += 1
            fp_hidden += 1
    pr = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    return {"aciertos": tp, "falsas": fp, "falsas_sin_bola": fp_hidden, "perdidas": fn, "precision": round(pr, 3),
            "recall": round(rc, 3), "f1": round(2 * pr * rc / (pr + rc), 3) if pr + rc else 0.0}


def total(parts: list[dict]) -> dict:
    """The scores of several clips together (counts summed, rates recomputed)."""
    tp, fp, fn = (sum(p[k] for p in parts) for k in ("aciertos", "falsas", "perdidas"))
    pr = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    return {"aciertos": tp, "falsas": fp, "falsas_sin_bola": sum(p["falsas_sin_bola"] for p in parts), "perdidas": fn,
            "precision": round(pr, 3), "recall": round(rc, 3), "f1": round(2 * pr * rc / (pr + rc), 3) if pr + rc else 0.0}


def pick_threshold(preds: list[dict], rows: list, grid=GRID) -> tuple[float, dict]:
    """The threshold of the grid with the best F1 over the clips (preds and rows: one per clip)."""
    best = None
    for t in grid:
        s = total([score(p, r, t) for p, r in zip(preds, rows)])
        if best is None or s["f1"] > best[1]["f1"]:
            best = (t, s)
    return best


def clip_preds(video: Path, rows, track_v3, totnet) -> tuple[dict, dict, float, float, int, int]:
    """One decoding of the clip: TrackNetV3 on every frame (its own feed), TOTNet on each annotated frame (its 5-frame
    window). Both every `step` frames as the analysis does (max(1, round(fps / 25)): 2 at 50-60 fps; TrackNetV3
    interpolates in between). Returns both predictions at the annotated frames, their inference seconds and counts."""
    import cv2

    from ..ball import BallFeed
    from ..ball_totnet import N, prep

    cap = cv2.VideoCapture(str(video))
    step = max(1, round((cap.get(cv2.CAP_PROP_FPS) or 25) / 25))
    want = {f for f, *_ in rows}
    need = {max(0, f - k * step) for f in want for k in range(N)}
    feed, ready, size = BallFeed(step), {}, None
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        size = fr.shape[:2]
        feed.add(fr)
        if i in need:
            ready[i] = prep(fr)
        i += 1
    cap.release()
    t0 = time.perf_counter()
    tr = track_v3.track_feed(feed)
    t_v3 = time.perf_counter() - t0
    v3 = {f: tuple(tr[f]) for f in want if f < len(tr)}
    tot, t_tot = {}, 0.0
    for f in sorted(want):
        if f >= i:
            continue
        t0 = time.perf_counter()
        tot[f] = totnet.window([ready[max(0, f - k * step)] for k in range(N - 1, -1, -1)], size)
        t_tot += time.perf_counter() - t0
    return v3, tot, t_v3, t_tot, i, len(tot)


def run(model: Path, totnet_model: Path, data: Path, n_val: int, n_test: int, device: str = "cpu") -> dict:
    from ..ball import BallTracker
    from ..ball_totnet import TotNetTracker
    from ..validation.datasets import RV_BASE, fetch, racketvision_video

    v3, tot = BallTracker(str(model), device), TotNetTracker(str(totnet_model), device)
    out = {"prueba": "bola", "tolerancia_px": TOL_PX, "dispositivo": device, "modelos": {}}
    acc = {"tracknetv3": {"s": 0.0, "n": 0}, "totnet": {"s": 0.0, "n": 0}}
    per = {}
    for split, n in (("val", n_val), ("test", n_test)):
        clips = json.loads(fetch(f"{RV_BASE}/info/{split}.json", data / "rv" / f"{split}.json").read_text())
        clips = clips[:: max(1, len(clips) // max(1, n))][:n]
        per[split] = {"v3": [], "tot": [], "rows": [], "clips": []}
        for match_id, clip in clips:
            rows = read_rows(fetch(f"{RV_BASE}/all/{match_id}/csv/{clip}_ball.csv",
                                   data / "rv" / "ball" / f"{match_id}_{clip}.csv"))
            video = racketvision_video(data, match_id, clip)
            p3, pt, s3, st, frames, windows = clip_preds(video, rows, v3, tot)
            acc["tracknetv3"]["s"] += s3
            acc["tracknetv3"]["n"] += frames
            acc["totnet"]["s"] += st
            acc["totnet"]["n"] += windows
            for k, v in (("v3", p3), ("tot", pt), ("rows", rows), ("clips", f"{match_id}_{clip}")):
                per[split][k].append(v)
            print(f"{split} {match_id}_{clip}: TrackNetV3 {score(p3, rows)['f1']}, {windows} ventanas de TOTNet", flush=True)
    thr, val_tot = pick_threshold(per["val"]["tot"], per["val"]["rows"])
    for name, key, t in (("tracknetv3", "v3", None), ("totnet", "tot", thr)):
        out["modelos"][name] = {
            "val": total([score(p, r, t) for p, r in zip(per["val"][key], per["val"]["rows"])]),
            "test": total([score(p, r, t) for p, r in zip(per["test"][key], per["test"]["rows"])]),
            "ms_por_fotograma": round(1000 * acc[name]["s"] / max(1, acc[name]["n"]), 1)}
    out["modelos"]["totnet"]["umbral"] = thr
    out["clips"] = {s: per[s]["clips"] for s in per}
    f3, ft = out["modelos"]["tracknetv3"]["test"]["f1"], out["modelos"]["totnet"]["test"]["f1"]
    out["sigue"] = ft >= f3 - MARGIN_F1
    out["conclusion"] = (f"TOTNet F1 {ft} frente a TrackNetV3 {f3} en {len(per['test']['clips'])} clips de prueba: "
                         + ("pasa a la prueba de golpes de F3Set con todo el análisis" if out["sigue"] else
                            "se aparta (peor que TrackNetV3 más allá del margen)"))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", type=Path, required=True, help="TrackNetV3 (balltrack.onnx)")
    ap.add_argument("--totnet", type=Path, required=True)
    ap.add_argument("--datos", type=Path, default=Path("/tmp/datasets"))
    ap.add_argument("--val", type=int, default=10)
    ap.add_argument("--test", type=int, default=30)
    ap.add_argument("--dispositivo", default="cpu")
    ap.add_argument("--salida", type=Path, required=True)
    a = ap.parse_args(argv)
    res = run(a.modelo, a.totnet, a.datos, a.val, a.test, a.dispositivo)
    a.salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(res["conclusion"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
