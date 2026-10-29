"""Where the time of the ball over the whole play goes (29-10, B-4): the learned spotter's stage took 50 min on 35
min of a new broadcast with the PC almost idle, so a new match would spend hours there. Measures, on the first
stretches of play of an analysed match: decoding (as track_play reads them, and with the GPU decoder) and the ball
model (fp32 and fp16, several batch sizes, on the iGPU and the CPU), and how far fp16's ball is from fp32's.

    uv run python scripts/bench_ball.py [--match <id>] [--seconds 90]

Writes <output>/bench_ball.json and prints a table.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def stretches(mdir: Path, seconds: float) -> list[tuple[float, float]]:
    from tennisbio import match_files as mf
    from tennisbio.ball_features import play_segments

    rd = lambda n: json.loads(mf.at(mdir, n).read_text(encoding="utf-8")) if mf.at(mdir, n).exists() else None
    sc, court = rd("scenes.json") or {"shots": []}, rd("court.json")
    segs, total = [], 0.0
    for a, b in play_segments(sc, court, float(sc.get("fps") or 25.0)):
        segs.append((a, b))
        total += b - a
        if total >= seconds:
            break
    return segs


def decode(info, segs, hw=None) -> tuple[list, float]:
    from tennisbio.ball_features import BALL_FPS
    from tennisbio.io.video import read_frames

    import cv2

    from tennisbio.ball import H, W

    # kept at the model's size (as BallFeed does it): two minutes at 1280 px would take 8 GB
    t0, out = time.time(), []
    for a, b in segs:
        out.append([cv2.resize(f, (W, H)) for f in read_frames(info, a, b - a, width=min(1280, info.width),
                                                                fps=BALL_FPS, hwaccel=hw)])
    return out, time.time() - t0


def model(path, device, batch, static, frames) -> tuple[list, float]:
    from tennisbio.ball import BallTracker

    tr = BallTracker(str(path), device, 0.5, batch=batch, static_batch=static)
    tr.track(frames[0][:batch * 2])                     # compile / warm up
    t0 = time.time()
    res = [tr.track(f) for f in frames]
    return res, time.time() - t0


def distance(a: list, b: list) -> dict:
    """Agreement of two tracks: same seen/not seen, and pixels apart where both see it."""
    A, B = np.concatenate(a), np.concatenate(b)
    sa, sb = ~np.isnan(A[:, 0]), ~np.isnan(B[:, 0])
    both = sa & sb
    d = np.linalg.norm(A[both, :2] - B[both, :2], axis=1) if both.any() else np.zeros(0)
    return {"same_seen": round(float((sa == sb).mean()), 4),
            "px_median": round(float(np.median(d)), 2) if len(d) else None,
            "px_p95": round(float(np.percentile(d, 95)), 2) if len(d) else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", default=None, help="id del partido (por defecto, el primero del catálogo)")
    ap.add_argument("--seconds", type=float, default=90.0)
    a = ap.parse_args()
    from tennisbio import layout
    from tennisbio.catalog import load_matches
    from tennisbio.config import load_config, resolve_path
    from tennisbio.io.video import auto_hwaccel, probe
    from tennisbio.pose.variants import to_fp16

    cfg = load_config()
    out = Path(cfg["paths"]["output"])
    ms = [m for m in load_matches(cfg) if a.match in (None, m.id)]
    if not ms:
        print("No hay partidos en el catálogo")
        return 1
    m = ms[0]
    mdir = layout.dir_of(out, m, cfg)
    segs = stretches(mdir, a.seconds)
    info = probe(m.video)
    res = {"match": m.id, "stretches": len(segs), "seconds_of_play": round(sum(b - a for a, b in segs), 1),
           "video": f"{info.width}x{info.height} {info.fps:g} fps"}
    frames, t = decode(info, segs)
    n = sum(len(f) for f in frames)
    res["frames"] = n
    res["decode_cpu_s"] = round(t, 1)
    hw = auto_hwaccel()
    if hw:
        _, t = decode(info, segs, hw)
        res[f"decode_{hw}_s"] = round(t, 1)
    onnx = resolve_path((cfg.get("ball") or {}).get("onnx"))
    dev = cfg.get("device", "cpu")
    base = None
    runs = [("fp32", onnx, dev, 8, True), ("fp32", onnx, dev, 16, True), ("fp32", onnx, dev, 32, True),
            ("fp16", None, dev, 8, True), ("fp16", None, dev, 16, True), ("fp32_cpu", onnx, "cpu", 8, False)]
    for name, path, device, batch, static in runs:
        key = f"model_{name}_b{batch}_{device}"
        try:
            path = path or to_fp16(onnx)
            tr, t = model(path, device, batch, static and device != "cpu", frames)
        except Exception as e:                       # noqa: BLE001 — a variant that does not run is a result too
            res[key] = f"error: {str(e)[:200]}"
            continue
        res[key] = {"s": round(t, 1), "fps": round(n / t, 1) if t else None}
        if base is None:
            base = tr
        else:
            res[key].update(distance(base, tr))
        print(key, res[key], flush=True)
    dest = out / "bench_ball.json"
    dest.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
