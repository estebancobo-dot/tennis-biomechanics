"""Where the time of the stroke videos goes, and whether the iGPU's encoder can take it (B5, step 4.1, 03-11).

On the same strokes of the analysed matches, one process, each encoder of `tennisbio.export.ENCODERS`:
reading + drawing (the clip's frames) against waiting on the encoder, seconds per video, and how far each
encoder's image is from libx264's (PSNR, ffmpeg). Criterion written before measuring: h264_amf is adopted
(`export.encoder: h264_amf`) only if it is faster per video **and** its PSNR against libx264 is ≥ 38 dB.

    uv run python scripts/bench_export.py [--strokes 20]

Writes <output>/bench_export.json (and the test videos in <output>/bench_export/, deleted at the end).
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

PSNR_MIN = 38.0


def psnr(a: Path, b: Path) -> float | None:
    """Average PSNR (dB) of video a against b, from ffmpeg's psnr filter."""
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(a), "-i", str(b), "-lavfi", "psnr", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=600)
    m = re.search(r"average:(\S+)", r.stderr)
    if not m:
        return None
    v = m.group(1)
    return 99.0 if v == "inf" else round(float(v), 2)


def encode(s, out: Path, ctx, key_metrics, dist, codec: str) -> dict:
    from tennisbio.export import Encoder, StrokeClip

    t0 = time.perf_counter()
    clip = StrokeClip(s, ctx)
    enc = Encoder(out, codec=codec)
    n = 0
    try:
        for img in clip.strokes_frames(key_metrics, dist):
            enc.write(img)
            n += 1
        t1 = time.perf_counter()
        enc.close()
    except Exception:
        enc.abort()
        raise
    t2 = time.perf_counter()
    return {"s": t2 - t0, "wait": enc.waited + (t2 - t1), "frames": n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strokes", type=int, default=20)
    a = ap.parse_args()
    from tennisbio import findings as F
    from tennisbio import match_files as mf
    from tennisbio.catalog import load_matches
    from tennisbio.config import load_config
    from tennisbio.export import ENCODERS
    from tennisbio.report import player_dict, prepare

    cfg = load_config()
    out_root = Path(cfg["paths"]["output"])
    matches = load_matches(cfg)
    if not matches:
        print("No hay partidos en el catálogo")
        return 1
    pid = matches[0].player.id
    mine = [m for m in matches if m.player.id == pid or m.extra.get("opponent_id") == pid]
    data = prepare(mine, out_root, "forehand", pid)
    dist = F.distributions(data)
    F.representativeness(data, dist)
    ctx = {"player": player_dict(mine, pid).get("name", "Jugador"), "hand": player_dict(mine, pid).get("hand"),
           "stroke": "forehand", "rival": [m["rival"] for m in data["matches"]]}
    ok = [s for s in data["strokes"] if s.get("_window") and s.get("_series")
          and (mf.at(Path(s["_dir"]), "windows") / s["_window"]).exists() and (Path(s["_dir"]) / s["_series"]).exists()]
    # spread over the matches, not the first N of one
    step = max(1, len(ok) // max(1, a.strokes))
    pick = ok[::step][:a.strokes]
    work = out_root / "bench_export"
    shutil.rmtree(work, ignore_errors=True)
    res = {"strokes": len(pick), "of": len(ok), "encoders": {}}
    for codec in ENCODERS:
        d = work / codec
        d.mkdir(parents=True, exist_ok=True)
        runs, err = [], None
        for s in pick:
            try:
                runs.append(encode(s, d / f"{s['id']}.mp4", ctx, data["metrics"], dist, codec))
            except Exception as e:  # noqa: BLE001 — an encoder that does not run here is a result too
                err = str(e)[:300]
                break
        if err:
            res["encoders"][codec] = {"error": err}
            print(codec, "error:", err, flush=True)
            continue
        tot = sum(r["s"] for r in runs)
        res["encoders"][codec] = {"s_per_video": round(tot / len(runs), 2) if runs else None,
                                  "wait_share": round(sum(r["wait"] for r in runs) / tot, 3) if tot else None,
                                  "frames": sum(r["frames"] for r in runs)}
        print(codec, res["encoders"][codec], flush=True)
    base = res["encoders"].get("libx264") or {}
    for codec, r in res["encoders"].items():
        if codec == "libx264" or "error" in r:
            continue
        ps = [p for p in (psnr(work / codec / f"{s['id']}.mp4", work / "libx264" / f"{s['id']}.mp4") for s in pick)
              if p is not None]
        r["psnr_vs_libx264_min"] = min(ps) if ps else None
        r["adopt"] = bool(ps and min(ps) >= PSNR_MIN and base.get("s_per_video")
                          and r["s_per_video"] < base["s_per_video"])
    shutil.rmtree(work, ignore_errors=True)
    (out_root / "bench_export.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
