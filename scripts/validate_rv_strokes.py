"""Automatic validation of near-player stroke detection on broadcast clips (RacketVision).

Reference contacts come from the annotated ball track (see tennisbio.validation.ball_hits).
These clips have no audio: this measures pose (+ ball, with --ball) detection; tolerance ±6
frames (annotations are every 5-11 frames). Doubles clips (two players on the near side) are
out of scope and skipped.

    uv run python scripts/validate_rv_strokes.py --root C:\\tenis\\datasets --clips 12
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="datasets")
    ap.add_argument("--clips", type=int, default=12)
    ap.add_argument("--tol", type=int, default=6)
    ap.add_argument("--ball", default=None, help="models/balltrack.onnx para usar la bola")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--imgsz", type=int, default=960)
    args = ap.parse_args()
    root = Path(args.root)
    split = json.loads(fetch(f"{RV_BASE}/info/test.json", root / "rv" / "test.json").read_text())
    sel = split[:: max(1, len(split) // args.clips)][:args.clips]
    ball = None
    if args.ball:
        from tennisbio.ball import BallTracker
        ball = BallTracker(args.ball, args.device)
    pairs_all, fp_all, fn_all, rows = [], [], [], []
    for match_id, clip in sel:
        video = racketvision_video(root, match_id, clip)
        ball = read_ball_csv(fetch(f"{RV_BASE}/all/{match_id}/csv/{clip}_ball.csv", root / "rv" / "ball" / f"{match_id}_{clip}.csv"))
        gt = hits_from_ball(ball, 1080)["near"]
        cache = root / "rv" / "cache" / f"{match_id}_{clip}.npz"
        run = run_clip(video, cache, rackets=False, imgsz=args.imgsz, init_mode="near", log=lambda *_: None, ball=ball)
        if is_doubles(cache, video):
            print(f"  {match_id}_{clip}: dobles, se omite")
            continue
        preds = [Pred(r.impact_frame, "fh" if r.stroke == "forehand" else "bh") for r in run.strokes]
        pairs, fp, fn = match(preds, [GTEvent(g, "near", "stroke", "-", "-") for g in gt], args.tol)
        pairs_all += pairs; fp_all += fp; fn_all += fn
        rows.append(dict(clip=f"{match_id}_{clip}", gt=gt, pred=[p.frame for p in preds], tracked=round(run.tracked_frac, 2)))
        print(f"  {match_id}_{clip}: referencia {gt}  detectados {[p.frame for p in preds]}  seguida {run.tracked_frac:.0%}", flush=True)
    s = summarize(pairs_all, fp_all, fn_all)
    out = root / "reports"
    out.mkdir(parents=True, exist_ok=True)
    (out / "rv_strokes_validation.json").write_text(json.dumps({"summary": s, "clips": rows}, indent=1))
    print("\nRESUMEN (jugador cercano, sin audio)")
    for k in ("gt", "detected", "true_positives", "precision", "recall", "f1", "timing_err_frames_median", "timing_bias_frames"):
        print(f"  {k:28} {s[k]}")


if __name__ == "__main__":
    main()
