"""Automatic model trials on this PC: is each alternative better than what runs now, measured here?

Every pose variant (tennisbio.pose.variants) runs on the same annotated RacketVision broadcast clips
(near player, singles) and feeds the unchanged stroke pipeline. Measured for each one:

- speed: ms per frame of the pose model on this PC (iGPU or CPU);
- strokes: precision, recall, F1 and timing error against the annotated ball turns (as
  scripts/validate_rv_strokes.py), the task that matters;
- steadiness: median frame-to-frame jerk of the tracked hips, shoulders and ankles, as % of her
  height (lower = steadier keypoints = less noise in every measure);
- tracking: share of frames where the near player is followed;
- feet: share of tracked frames with the heels and toes seen (only RTMPose Halpe26 has them);
- half precision: median keypoint difference against the same model in full precision (px).

The ball model is tried the same way (full vs half precision) against the annotated ball positions:
share of annotated balls found within 10 px, and ms per frame.

A variant is recommended only if it keeps the F1 (at most 0.02 less), is not less steady and either
is faster or adds the feet; half precision only if its keypoints move less than 1.5 px. The script
reports; the code changes follow from its results.

    uv run python scripts/model_trials.py --root C:\\tenis\\datasets --device dml [--clips 12]
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

VERSION = 1


def jerk(run) -> float | None:
    """Median frame-to-frame second difference of the tracked trunk and ankle points, % of height."""
    from tennisbio.skeleton import Skeleton

    sk = Skeleton("coco17", "right")
    idx = [sk[n] for n in ("left_hip", "right_hip", "left_shoulder", "right_shoulder", "left_ankle", "right_ankle")]
    p = run.img[:, idx]
    d2 = np.linalg.norm(p[2:] - 2 * p[1:-1] + p[:-2], axis=-1)
    d2 = d2[np.isfinite(d2)]
    if not len(d2) or not run.height_px:
        return None
    return round(float(100 * np.median(d2) / run.height_px), 3)


def feet_seen(cache: Path, run) -> float | None:
    from tennisbio.pipeline import load_npz

    d = load_npz(cache)
    if d is None or "feet_confs" not in d.files:
        return None
    seen = n = 0
    for t, b in enumerate(run.boxes):
        if b is None or t >= len(d["boxes"]) or not len(d["boxes"][t]):
            continue
        bx = np.asarray(d["boxes"][t])
        i = int(np.argmin(np.abs(bx - np.asarray(b)).sum(1)))
        n += 1
        seen += bool(np.mean(np.asarray(d["feet_confs"][t])[i] > 0.3) >= 0.5)
    return round(seen / n, 3) if n else None


def kp_diff(a: Path, b: Path) -> float | None:
    """Median distance (px) between the keypoints of matching people in two caches of the same clip."""
    from tennisbio.pipeline import load_npz

    da, db = load_npz(a), load_npz(b)
    if da is None or db is None:
        return None
    out = []
    for ba, ka, bb, kb in zip(da["boxes"], da["kps"], db["boxes"], db["kps"]):
        for i, box in enumerate(np.asarray(ba).reshape(-1, 4)):
            if not len(bb):
                continue
            j = int(np.argmin(np.abs(np.asarray(bb).reshape(-1, 4) - box).sum(1)))
            out.append(np.median(np.linalg.norm(np.asarray(ka)[i] - np.asarray(kb)[j], axis=-1)))
    return round(float(np.median(out)), 2) if out else None


def ball_trial(onnx: Path, clips, root: Path, device: str) -> dict:
    import cv2

    from tennisbio.ball import BallTracker
    from tennisbio.validation.ball_hits import read_ball_csv
    from tennisbio.validation.datasets import RV_BASE, fetch

    tr = BallTracker(str(onnx), device)
    found = total = frames = 0
    t_inf = 0.0
    for match_id, clip, video in clips:
        gt = read_ball_csv(fetch(f"{RV_BASE}/all/{match_id}/csv/{clip}_ball.csv", root / "rv" / "ball" / f"{match_id}_{clip}.csv"))
        cap = cv2.VideoCapture(str(video))
        fr = []
        while True:
            ok, f = cap.read()
            if not ok:
                break
            fr.append(f)
        cap.release()
        t0 = time.perf_counter()
        track = tr.track(fr)
        t_inf += time.perf_counter() - t0
        frames += len(fr)
        for f, x, y in gt:
            f = int(f)
            if f < len(track):
                total += 1
                found += bool(np.isfinite(track[f, 0]) and np.hypot(track[f, 0] - x, track[f, 1] - y) <= 10)
    return {"found_10px": round(found / total, 3) if total else None, "annotated": total,
            "ms_per_frame": round(1000 * t_inf / max(1, frames), 1)}


def recommend(res: dict, base: str) -> list[str]:
    b = res.get(base) or {}
    out = []
    for v, r in res.items():
        if v == base or r.get("error"):
            continue
        f1_ok = r.get("f1") is not None and b.get("f1") is not None and r["f1"] >= b["f1"] - 0.02
        steady = r.get("jerk_pct") is not None and b.get("jerk_pct") is not None and r["jerk_pct"] <= b["jerk_pct"] * 1.05
        faster = (r.get("ms_per_frame") or 1e9) < 0.9 * (b.get("ms_per_frame") or 0)
        feet = bool(r.get("feet_seen"))
        fp16_ok = r.get("kp_diff_vs_fp32_px") is None or r["kp_diff_vs_fp32_px"] < 1.5
        if f1_ok and steady and fp16_ok and (faster or feet):
            out.append(f"{v}: " + ", ".join(x for x in ("más rápida" if faster else "", "con pies" if feet else "") if x)
                       + f" (F1 {r['f1']} frente a {b['f1']}; {r['ms_per_frame']} frente a {b.get('ms_per_frame')} ms/fotograma)")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="datasets")
    ap.add_argument("--clips", type=int, default=12)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--tol", type=int, default=6)
    ap.add_argument("--variants", default=None, help="lista separada por comas (por defecto todas)")
    ap.add_argument("--ball", default="models/balltrack.onnx")
    args = ap.parse_args()

    from tennisbio.ball import BallTracker
    from tennisbio.clip_pipeline import run_clip
    from tennisbio.pose.backend import set_device
    from tennisbio.pose.variants import BASELINE, VARIANTS, extract_variant, to_fp16
    from tennisbio.validation.ball_hits import hits_from_ball, read_ball_csv
    from tennisbio.validation.datasets import RV_BASE, fetch, racketvision_video
    from tennisbio.validation.impact_eval import GTEvent, Pred, match, summarize
    from validate_rv_strokes import is_doubles

    set_device(args.device)
    root = Path(args.root)
    out_dir = root / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    work = root / "rv" / "trials"
    variants = args.variants.split(",") if args.variants else VARIANTS
    if BASELINE not in variants:
        variants = [BASELINE] + variants
    split = json.loads(fetch(f"{RV_BASE}/info/test.json", root / "rv" / "test.json").read_text())
    sel = split[:: max(1, len(split) // args.clips)][:args.clips]
    ball = Path(args.ball)
    tracker = BallTracker(str(ball), args.device) if ball.exists() else None
    res, clips = {}, []
    t_start = time.time()
    for v in variants:
        print(f"== {v}", flush=True)
        vdir = work / v.replace("@", "_")
        vdir.mkdir(parents=True, exist_ok=True)
        pairs_all, fp_all, fn_all, ms, jk, ft, diffs, tracked = [], [], [], [], [], [], [], []
        try:
            for match_id, clip in sel:
                video = racketvision_video(root, match_id, clip)
                cache = vdir / f"{match_id}_{clip}.npz"
                base_cache = work / BASELINE.replace("@", "_") / cache.name
                if v != BASELINE and not base_cache.exists():
                    continue                       # skipped for the baseline (doubles): skipped here too
                msf = vdir / (cache.stem + "_ms.json")
                if not cache.exists():
                    msf.write_text(json.dumps(extract_variant(video, cache, v, args.device)["ms_per_frame"]))
                if msf.exists():
                    ms.append(json.loads(msf.read_text()))
                if v == BASELINE and is_doubles(cache, video):
                    cache.unlink()
                    print(f"  {match_id}_{clip}: dobles, se omite")
                    continue
                if v == BASELINE:
                    clips.append((match_id, clip, video))
                bnpy = base_cache.with_name(base_cache.stem + "_ball.npy")       # the ball does not depend on the pose
                if v != BASELINE and bnpy.exists() and not cache.with_name(cache.stem + "_ball.npy").exists():
                    shutil.copy(bnpy, cache.with_name(cache.stem + "_ball.npy"))
                gt = hits_from_ball(read_ball_csv(fetch(f"{RV_BASE}/all/{match_id}/csv/{clip}_ball.csv",
                                                        root / "rv" / "ball" / f"{match_id}_{clip}.csv")), 1080)["near"]
                run = run_clip(video, cache, rackets=False, init_mode="near", log=lambda *_: None, ball=tracker)
                preds = [Pred(r.impact_frame, "fh" if r.stroke == "forehand" else "bh") for r in run.strokes]
                pairs, fp, fn = match(preds, [GTEvent(g, "near", "stroke", "-", "-") for g in gt], args.tol)
                pairs_all += pairs; fp_all += fp; fn_all += fn
                jk.append(jerk(run))
                tracked.append(run.tracked_frac)
                ft.append(feet_seen(cache, run))
                if v.endswith("-fp16"):
                    full = work / v.removesuffix("-fp16").replace("@", "_") / cache.name
                    if full.exists():
                        diffs.append(kp_diff(full, cache))
            s = summarize(pairs_all, fp_all, fn_all)
            num = lambda xs: [x for x in xs if x is not None]
            res[v] = {"clips": len(tracked), "ms_per_frame": round(float(np.median(ms)), 1) if ms else None,
                      "precision": s["precision"], "recall": s["recall"], "f1": s["f1"],
                      "timing_err_frames": s["timing_err_frames_median"],
                      "jerk_pct": round(float(np.median(num(jk))), 3) if num(jk) else None,
                      "tracked": round(float(np.mean(tracked)), 3) if tracked else None,
                      "feet_seen": round(float(np.mean(num(ft))), 3) if num(ft) else None,
                      "kp_diff_vs_fp32_px": round(float(np.median(num(diffs))), 2) if num(diffs) else None}
        except Exception as e:                      # one variant that does not run never stops the others
            import traceback
            res[v] = {"error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-800:]}
        print(f"   {res[v]}", flush=True)
    balls = {}
    if ball.exists() and clips:
        for name, path in (("balltrack", ball), ("balltrack-fp16", None)):
            try:
                balls[name] = ball_trial(path or to_fp16(ball), clips, root, args.device)
            except Exception as e:
                balls[name] = {"error": f"{type(e).__name__}: {e}"}
            print(f"== {name}: {balls[name]}", flush=True)
    rec = recommend(res, BASELINE)
    report = {"version": VERSION, "device": args.device, "minutes": round((time.time() - t_start) / 60, 1),
              "pose": res, "ball": balls, "recommended": rec, "baseline": BASELINE,
              "generated": time.strftime("%Y-%m-%d %H:%M")}
    (out_dir / "model_trials.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    lines = [f"# Prueba de modelos en este PC ({report['generated']}, {args.device}, {report['minutes']} min)", "",
             "| Variante | ms/fotograma | F1 golpes | Precisión | Recall | Error instante | Temblor (% altura) | Seguida | Pies | Dif. FP16 (px) |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for v, r in res.items():
        if r.get("error"):
            lines.append(f"| {v} | error: {r['error'][:80]} |||||||||")
            continue
        lines.append("| " + " | ".join(str(x) for x in (v, r["ms_per_frame"], r["f1"], r["precision"], r["recall"], r["timing_err_frames"],
                                                        r["jerk_pct"], r["tracked"], r["feet_seen"] if r["feet_seen"] is not None else "—",
                                                        r["kp_diff_vs_fp32_px"] if r["kp_diff_vs_fp32_px"] is not None else "—")) + " |")
    if balls:
        lines += ["", "| Bola | Encontradas a ≤10 px | ms/fotograma |", "|---|---|---|"]
        lines += [f"| {k} | {b.get('found_10px', b.get('error'))} | {b.get('ms_per_frame', '')} |" for k, b in balls.items()]
    lines += ["", "**Recomendadas frente a la actual (" + BASELINE + "):** " + ("; ".join(rec) if rec else "ninguna mejora en todo a la vez")]
    (out_dir / "model_trials.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
