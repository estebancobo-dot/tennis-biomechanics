"""Automatic validation of stroke detection on broadcast clips (RacketVision).

Reference contacts come from the annotated ball track (see tennisbio.validation.ball_hits). Tolerance ±6 frames.
Doubles clips (two players on the near side) are out of scope and skipped.

By default (08-11) it measures the PRODUCTION path, the one the analysis of a match runs: every analysis stage on
each clip with the user's configuration (learned spotter `spotting` → `candidates` → fine pass `fine` /
`fine_doubtful`; tennisbio.validation.rv_eval), both ends at once. Writes <root>/reports/rv_validation.json/.md
and a copy in the configured output folder (uploaded by the PC to pc-logs).

    uv run python scripts/validate_rv_strokes.py --root C:\\tenis\\datasets --clips 12

--legacy keeps the old measure (clip_pipeline.run_clip: pose, + ball with --ball; one end, --side), the one PC
request 154 ran (precision 0.64, recall 0.74): it is NOT the analysis's detector and its output says so
(<root>/reports/rv_strokes_validation_<side>.json, "path": "legacy").

    uv run python scripts/validate_rv_strokes.py --legacy --root C:\\tenis\\datasets --clips 12 --ball auto
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio.clip_pipeline import run_clip  # noqa: E402
from tennisbio.validation.ball_hits import hits_from_ball, read_ball_csv  # noqa: E402
from tennisbio.validation.datasets import RV_BASE, fetch, racketvision_video  # noqa: E402
from tennisbio.validation.impact_eval import GTEvent, Pred, match, summarize  # noqa: E402
from tennisbio.validation import rv_eval  # noqa: E402

# the detector this validation measures by default: the analysis's own stages (the learned spotter when
# `spotter.enabled`); the old run_clip path only with --legacy (tests/test_validation_detector.py)
DETECTOR = rv_eval.DETECTOR


def is_doubles(cache: Path, video: Path) -> bool:
    """Two people standing inside the near half of the court (feet on court, via the homography)
    in most frames. Ball kids and line judges stand outside the court lines."""
    import cv2
    import numpy as np

    from tennisbio.court import fit_court
    from tennisbio.court_metrics import to_court

    cap = cv2.VideoCapture(str(video))
    ok, frame = cap.read()
    cap.release()
    fit = fit_court(frame) if ok else None
    if fit is None or fit.score < 0.5:
        return False
    d = np.load(cache, allow_pickle=True)
    counts = []
    for b in d["boxes"][::5]:
        if not len(b):
            continue
        feet = to_court(fit.H, np.c_[(b[:, 0] + b[:, 2]) / 2, b[:, 3]])
        inside = (np.abs(feet[:, 0]) < 6.5) & (feet[:, 1] > -3) & (feet[:, 1] < 11.885)
        counts.append(int(inside.sum()))
    return bool(counts) and float(np.median(counts)) >= 2


def far_init(video: Path, cache: Path, imgsz: int):
    """(far-court region, image row of the net, initial far-player box) from the homography;
    runs the pose on that region (cached) to find her."""
    import cv2
    import numpy as np

    from tennisbio.court import fit_court
    from tennisbio.court_metrics import net_row

    cap = cv2.VideoCapture(str(video))
    ok, frame = cap.read()
    cap.release()
    fit = fit_court(frame) if ok else None
    if fit is None or fit.score < 0.5:
        return None
    from tennisbio.pose.yolo import find_far_player
    box = find_far_player(video, fit.H)
    if box is None:
        return None
    return dict(roi="follow", max_bottom=net_row(fit.H), init_box=box)


def gate_misses(run, video: Path, cache: Path, side: str) -> int:
    """Strokes the full pass found that the cascade gate of the fine pass (fine_gate) would have
    thrown away with a cheap-pass candidate anywhere within its confirmation tolerance: must be 0."""
    import cv2
    import numpy as np

    from tennisbio.clip_pipeline import ball_cache_path
    from tennisbio.fine_gate import CONFIRM_TOL_S, gate_window

    raw = np.load(ball_cache_path(cache))
    cap = cv2.VideoCapture(str(video))
    fw, fh = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    misses = 0
    for r in run.strokes:
        if side == "far" and "ball" not in r.impact_source:       # the fine pass drops these at the far end
            continue
        for off in np.linspace(-CONFIRM_TOL_S, CONFIRM_TOL_S, 5):
            misses += not gate_window(raw, fw, fh, run.fps, [r.impact_frame + off * run.fps], side, 0.0)["passed"]
    return misses


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="datasets")
    ap.add_argument("--legacy", action="store_true",
                    help="la medida antigua (clip_pipeline.run_clip: pose + regla de la bola), NO el detector del análisis")
    ap.add_argument("--clips", type=int, default=12)
    ap.add_argument("--tol", type=int, default=6)
    ap.add_argument("--ball", default=None,
                    help="--legacy: models/balltrack.onnx (o auto) para usar la bola; sin --legacy, la bola del análisis")
    ap.add_argument("--device", default="cpu", help="--legacy: dispositivo de la bola (sin --legacy, el del análisis)")
    ap.add_argument("--side", default="near", choices=["near", "far"],
                    help="--legacy: jugador cercano o lejano (sin --legacy se miden los dos lados a la vez)")
    ap.add_argument("--imgsz", type=int, default=960)
    args = ap.parse_args(argv)
    root = Path(args.root)
    # on the PC the datasets live next to the output (C:\\tenis\\datasets) and a PC request cannot pass a path
    # (08-11): «datasets» missing here → the configured output's sibling; --ball auto → the configured ball model
    if not root.exists() and args.root == "datasets":
        try:
            from tennisbio.config import load_config
            near = Path(load_config()["paths"]["output"]).parent / "datasets"
            root = near if near.exists() else root
        except Exception:  # noqa: BLE001 — keep the default
            pass
    if args.ball == "auto":
        from tennisbio.config import load_config, resolve_path
        cfg = load_config()
        args.ball = str(resolve_path((cfg.get("ball") or {}).get("onnx") or "models/balltrack.onnx"))
    split = json.loads(fetch(f"{RV_BASE}/info/test.json", root / "rv" / "test.json").read_text())
    sel = split[:: max(1, len(split) // args.clips)][:args.clips]
    if args.legacy:
        return legacy_main(args, root, sel)
    return production_main(args, root, sel)


def output_dir() -> Path | None:
    """The configured output folder (C:\\tenis\\output on the PC), where the PC picks the reports up for pc-logs."""
    try:
        from tennisbio.config import load_config
        p = (load_config().get("paths") or {}).get("output")
        return Path(p) if p else None
    except Exception:  # noqa: BLE001 — no configured output: only the copy under <root>/reports
        return None


def production_main(args, root: Path, sel: list) -> int:
    """The analysis's own detector (rv_eval): every stage on each clip with the user's configuration, both ends."""
    import time

    from tennisbio.config import load_config
    from tennisbio.stages import spotter_on

    t0 = time.time()
    cfg = load_config()
    on = spotter_on(cfg)
    detector = ("detector entrenado (spotter.enabled: true) → candidates → pasada fina" if on else
                "reglas (spotter.enabled: false en la configuración, como el análisis) → candidates → pasada fina")
    print(f"Camino de PRODUCCIÓN: {detector}", flush=True)
    out_dir = root / "rv" / "salidas"
    rows, unavailable = [], None
    n_doubles = n_failed = 0
    for match_id, clip in sel:
        name = f"{match_id}_{clip}"
        video = racketvision_video(root, match_id, clip)
        ball = read_ball_csv(fetch(f"{RV_BASE}/all/{match_id}/csv/{clip}_ball.csv", root / "rv" / "ball" / f"{match_id}_{clip}.csv"))
        gt = hits_from_ball(ball, 1080)
        mid = "rv_" + name
        try:
            print(f"  {name}: analizando con las etapas del análisis…", flush=True)
            rv_eval.run_clip_pipeline(video, mid, out_dir, cfg, log=rv_eval.short_log)
        except Exception as e:  # noqa: BLE001 — one clip failing must not stop the others; said in the report
            n_failed += 1
            msg = f"{type(e).__name__}: {e}"
            if on and ("spotting" in msg or "detector" in msg):
                unavailable = msg               # the spotter itself could not run: said, never replaced by the rules
            rows.append(dict(clip=name, gt=gt, pred={}, note=f"error: {msg[:200]}"))
            print(f"  {name}: ERROR {msg[:200]}", flush=True)
            continue
        o = rv_eval.clip_outputs(out_dir / mid)
        if o["doubles"]:
            n_doubles += 1
            print(f"  {name}: dobles, se omite", flush=True)
            continue
        fps = o["fps"] or 25.0
        pred = {side: rv_eval.predicted_frames(o, side, fps) for side in rv_eval.SIDES}
        rows.append(dict(clip=name, gt=gt, pred=pred, spotted=len(o["spotted"]), candidates=len(o["candidates"]),
                         candidate_source=o["candidate_source"], fps=fps,
                         doubtful=sum(s["file"] == "strokes_doubtful.json" for s in o["strokes"])))
        print(f"  {name}: referencia {gt}  detectados {pred}  (detector {len(o['spotted'])}, candidatos "
              f"{len(o['candidates'])} de {o['candidate_source']})", flush=True)
    used = [r for r in rows if "note" not in r]
    fps_used = sorted({r["fps"] for r in used})
    res = {"path": "production", "path_label": "producción: las etapas del análisis (" + detector + ")",
           "detector": detector, "spotter_enabled": on, "spotter_unavailable": unavailable,
           "clips_selected": len(sel), "clips_used": len(used), "clips_doubles": n_doubles, "clips_failed": n_failed,
           "tol_frames": args.tol, "tol_s": round(args.tol / fps_used[0], 3) if fps_used else None,
           "summary": rv_eval.evaluate(used, args.tol), "notes": list(rv_eval.NOTES),
           "legacy_reference": "petición 154: precisión 0,64, recall 0,74, 19 golpes (lado cercano, run_clip)",
           "clips": rows, "minutes": round((time.time() - t0) / 60, 1)}
    md = rv_eval.to_markdown(res)
    for d in [root / "reports", output_dir()]:
        if d is None:
            continue
        try:
            d.mkdir(parents=True, exist_ok=True)
            (d / "rv_validation.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
            (d / "rv_validation.md").write_text(md, encoding="utf-8")
        except OSError as e:
            print(f"  no se pudo escribir en {d}: {e}")
    print("\n" + md)
    return 0 if used else 1


def legacy_main(args, root: Path, sel: list) -> int:
    """The old measure (before 08-11; PC request 154): clip_pipeline.run_clip on each clip, one end. It is NOT the
    analysis's detector: labelled as such on screen and in its JSON ("path": "legacy")."""
    print(rv_eval.LEGACY_LABEL, flush=True)
    tracker = None
    if args.ball:
        from tennisbio.ball import BallTracker
        tracker = BallTracker(args.ball, args.device)
    pairs_all, fp_all, fn_all, rows, misses = [], [], [], [], 0
    for match_id, clip in sel:
        video = racketvision_video(root, match_id, clip)
        ball = read_ball_csv(fetch(f"{RV_BASE}/all/{match_id}/csv/{clip}_ball.csv", root / "rv" / "ball" / f"{match_id}_{clip}.csv"))
        gt = hits_from_ball(ball, 1080)[args.side]
        cache = root / "rv" / "cache" / f"{match_id}_{clip}.npz"
        if cache.exists() and is_doubles(cache, video):
            print(f"  {match_id}_{clip}: dobles, se omite")
            continue
        extra = {}
        if args.side == "far":
            cache = cache.with_name(cache.stem + "_far.npz")
            fi = far_init(video, cache, args.imgsz)
            if fi is None:
                print(f"  {match_id}_{clip}: sin pista o sin jugador lejano, se omite")
                continue
            extra = dict(side="far", **fi)
        run = run_clip(video, cache, rackets=False, imgsz=args.imgsz, init_mode="near", log=lambda *_: None,
                       ball=tracker, **extra)
        if not extra and is_doubles(cache, video):     # cache just created: check now
            print(f"  {match_id}_{clip}: dobles, se omite")
            continue
        if tracker is not None:
            misses += gate_misses(run, video, cache, args.side)
        preds = [Pred(r.impact_frame, "fh" if r.stroke == "forehand" else "bh") for r in run.strokes]
        pairs, fp, fn = match(preds, [GTEvent(g, "near", "stroke", "-", "-") for g in gt], args.tol)
        pairs_all += pairs; fp_all += fp; fn_all += fn
        rows.append(dict(clip=f"{match_id}_{clip}", gt=gt, pred=[p.frame for p in preds], tracked=round(run.tracked_frac, 2)))
        print(f"  {match_id}_{clip}: referencia {gt}  detectados {[p.frame for p in preds]}  seguida {run.tracked_frac:.0%}", flush=True)
    s = summarize(pairs_all, fp_all, fn_all)
    if tracker is not None:
        s["gate_misses"] = misses        # strokes the cascade gate of the fine pass would lose (must be 0)
    out = root / "reports"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"rv_strokes_validation_{args.side}.json").write_text(
        json.dumps({"path": "legacy", "path_label": rv_eval.LEGACY_LABEL, "summary": s, "clips": rows}, indent=1))
    print(f"\nRESUMEN LEGACY (camino antiguo, run_clip; jugador {'cercano' if args.side == 'near' else 'lejano'}, sin audio)")
    for k in ("gt", "detected", "true_positives", "precision", "recall", "f1", "timing_err_frames_median", "timing_bias_frames", "gate_misses"):
        if k in s:
            print(f"  {k:28} {s[k]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
