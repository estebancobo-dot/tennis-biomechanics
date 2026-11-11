"""Speed test of fine_pass.max_fps (10-11): the same stretch of a 50-60 fps match analysed twice, with the windows at
their native frame rate (A) and at half of it (B, max_fps), and compared: time of the fine passes, strokes found (matched
by their time within 0.12 s), their side and kind, and how much each measure moves between A and B (median of the
absolute differences, per metric, against the spread of that metric between strokes). Nothing of a real match is
touched: <output>/_bench_fps/A and B. Writes <output>/capturas_diag/bench_fps.json (uploaded to pc-logs).

    uv run python scripts/bench_fine_fps.py --match pegula [--minutes 20] [--start 1800] [--max-fps 30]

11-11 (R2/R3 of the review of the Base): any setting as B instead of max_fps, in folders of its own, from scratch:
    uv run python scripts/bench_fine_fps.py --match pegula --minutes 15 --tag rtmw --set fine_pass.refine=rtmw-x
writes <output>/_bench_<tag>/A and B (removed first: both runs compute now, with today's code) and
capturas_diag/bench_<tag>.json."""
import argparse
import copy
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio import pipeline, stages  # noqa: E402,F401  (registers the stages)
from tennisbio.catalog import load_matches, trial_match  # noqa: E402
from tennisbio.config import load_config  # noqa: E402

FINE = ("fine", "fine_opponent", "fine_doubtful")


def run(match, cfg, d: Path) -> dict:
    ctx = pipeline.Context(match, cfg, d)
    t0 = time.time()
    done = pipeline.run(ctx)
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    st = json.loads((d / "strokes.json").read_text(encoding="utf-8")) if (d / "strokes.json").exists() else []
    return {"seconds": round(time.time() - t0, 1), "done": done,
            "fine_s": round(sum(float((man.get(k) or {}).get("seconds") or 0) for k in FINE), 1),
            "stage_s": {k: round(float(v.get("seconds") or 0), 1) for k, v in man.items()}, "strokes": st}


def set_key(cfg: dict, kv: str) -> None:
    """«fine_pass.refine=rtmw-x» → cfg["fine_pass"]["refine"] = "rtmw-x" (the value read as YAML: true, 30, 0.5…)."""
    import yaml
    k, _, v = kv.partition("=")
    if not k or not _:
        raise SystemExit(f"--set sin «=»: {kv}")
    d = cfg
    *path, last = k.split(".")
    for p in path:
        d = d.setdefault(p, {})
    d[last] = yaml.safe_load(v)


def flat(s: dict) -> dict:
    out = {}
    for k, v in (s.get("metrics") or {}).items():
        if isinstance(v, (int, float)) and not isinstance(v, bool) and np.isfinite(v):
            out[k] = float(v)
    return out


def compare(a: list, b: list, tol: float = 0.12) -> dict:
    ta = np.array([float(s.get("match_time_s", 0)) for s in a])
    tb = np.array([float(s.get("match_time_s", 0)) for s in b])
    used, pairs = set(), []
    for i, t in enumerate(ta):
        if not len(tb):
            break
        j = int(np.argmin(np.abs(tb - t)))
        if abs(tb[j] - t) <= tol and j not in used:
            used.add(j)
            pairs.append((i, j))
    same_kind = sum(a[i].get("stroke") == b[j].get("stroke") for i, j in pairs)
    same_side = sum(a[i].get("side") == b[j].get("side") for i, j in pairs)
    dt = [abs(ta[i] - tb[j]) for i, j in pairs]
    per = {}
    for i, j in pairs:
        fa, fb = flat(a[i]), flat(b[j])
        for k in fa.keys() & fb.keys():
            per.setdefault(k, []).append((fa[k], fb[k]))
    spread = {}
    for s in a:
        for k, v in flat(s).items():
            spread.setdefault(k, []).append(v)
    metrics = {}
    for k, v in per.items():
        if len(v) < 5:
            continue
        x = np.array(v)
        sd = float(np.std(spread.get(k, [0]))) or float("nan")
        mad = float(np.median(np.abs(x[:, 0] - x[:, 1])))
        metrics[k] = {"n": len(v), "median_abs_diff": round(mad, 3), "spread_sd": round(sd, 3),
                      "diff_vs_spread": None if not np.isfinite(sd) or sd == 0 else round(mad / sd, 3)}
    worst = sorted((m for m in metrics.items() if m[1]["diff_vs_spread"] is not None),
                   key=lambda kv: -kv[1]["diff_vs_spread"])[:12]
    return {"A": len(a), "B": len(b), "matched": len(pairs), "only_A": len(a) - len(pairs), "only_B": len(b) - len(pairs),
            "same_kind": same_kind, "same_side": same_side,
            "median_dt_s": round(float(np.median(dt)), 3) if dt else None,
            "metrics_close": sum(1 for m in metrics.values() if (m["diff_vs_spread"] or 0) <= 0.25),
            "metrics": len(metrics), "worst": dict(worst)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", required=True)
    ap.add_argument("--minutes", type=float, default=20)
    ap.add_argument("--start", type=float, default=None, help="default: centred on the user's click of this match")
    ap.add_argument("--max-fps", type=float, default=30)
    ap.add_argument("--set", action="append", default=[], help="clave.subclave=valor para B (en lugar de max_fps)")
    ap.add_argument("--tag", default="", help="carpeta _bench_<tag> y capturas_diag/bench_<tag>.json, desde cero")
    args = ap.parse_args()
    cfg = load_config()
    root = Path((cfg.get("paths") or {}).get("output") or "output")
    ms = [m for m in load_matches(cfg) if args.match in m.id]
    if len(ms) != 1:
        sys.exit(f"partidos con «{args.match}»: {[m.id for m in ms]} (hace falta exactamente uno)")
    m = ms[0]
    src = Path(m.video)
    # the user's click of this match, so that both runs follow her and not the opponent: the stretch holds it
    from tennisbio import match_files as mf
    from tennisbio.identity import PICK_FILE
    from tennisbio.layout import dir_of
    pick = mf.at(dir_of(root, m, cfg), PICK_FILE)
    if args.start is None:
        pt = float(json.loads(pick.read_text(encoding="utf-8"))["t"]) if pick.exists() else 1800.0
        args.start = max(0.0, pt - args.minutes * 30)
    out = root / (f"_bench_{args.tag}" if args.tag else "_bench_fps")
    if args.tag:                       # from scratch: A also computes now (an older A kept older caches and times)
        for sub in ("A", "B"):
            shutil.rmtree(out / sub, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    clip = out / f"tramo_{int(args.start)}_{int(args.minutes)}m{src.suffix}"
    if not clip.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(args.start), "-i", str(src), "-t", str(args.minutes * 60),
                        "-c", "copy", str(clip)], check=True)
    match = trial_match("bench_fps", clip, m.player, cfg, source=src, opponent=m.opponent or "",
                        surface=getattr(m, "surface", "") or "")
    rep = {"match": m.id, "start_s": args.start, "minutes": args.minutes, "max_fps": args.max_fps}
    print(f"A: ventanas a sus fps ({time.strftime('%H:%M:%S')})", flush=True)
    da = out / "A"
    da.mkdir(parents=True, exist_ok=True)
    if pick.exists():
        p = json.loads(pick.read_text(encoding="utf-8"))
        p["t"] = float(p["t"]) - args.start
        if 0 <= p["t"] <= args.minutes * 60:
            (da / PICK_FILE).write_text(json.dumps(p), encoding="utf-8")
    ra = run(match, cfg, da)
    print(f"A: {ra['seconds'] / 60:.1f} min, pasadas finas {ra['fine_s'] / 60:.1f} min, {len(ra['strokes'])} golpes", flush=True)
    db = out / "B"
    if not db.exists():          # the cheap pass and everything before the fine pass, from A
        shutil.copytree(da, db, ignore=shutil.ignore_patterns("windows", "series", "informe"))
    cfg_b = copy.deepcopy(cfg)
    if args.set:
        for kv in args.set:
            set_key(cfg_b, kv)
        rep["set"] = args.set
        print(f"B: {', '.join(args.set)} ({time.strftime('%H:%M:%S')})", flush=True)
    else:
        cfg_b.setdefault("fine_pass", {})["max_fps"] = args.max_fps
        print(f"B: ventanas a max_fps {args.max_fps:g} ({time.strftime('%H:%M:%S')})", flush=True)
    rb = run(match, cfg_b, db)
    print(f"B: {rb['seconds'] / 60:.1f} min, pasadas finas {rb['fine_s'] / 60:.1f} min, {len(rb['strokes'])} golpes", flush=True)
    rep.update({"A": {k: v for k, v in ra.items() if k != "strokes"}, "B": {k: v for k, v in rb.items() if k != "strokes"},
                "compare": compare(ra["strokes"], rb["strokes"])})
    rep["fine_speedup"] = round(ra["fine_s"] / rb["fine_s"], 2) if rb["fine_s"] else None
    dst = root / "capturas_diag"
    dst.mkdir(parents=True, exist_ok=True)
    (dst / (f"bench_{args.tag}.json" if args.tag else "bench_fps.json")).write_text(
        json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("fine_speedup", "compare")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
