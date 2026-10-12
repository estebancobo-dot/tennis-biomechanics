"""Automatic stroke validation on TV broadcast with F3Set-Tennis ground truth.

Picks annotated points (by default from Rybakina's matches, 4 of them in F3Set), downloads only
those seconds from YouTube with yt-dlp, runs the same pipeline (pose + ball + court) and compares
every near-player stroke with the annotations: detection (precision, recall, timing),
forehand/backhand, direction of her shot (cross, down the line, middle, inside-out, inside-in),
approach to the net and errors. Runs on the user's PC (YouTube blocks data-centre addresses).

    uv run python scripts/validate_f3set.py --root C:\\tenis\\datasets --player Rybakina --clips 20
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio.clip_pipeline import run_clip  # noqa: E402
from tennisbio.validation.datasets import f3set_tennis  # noqa: E402
from tennisbio.validation.impact_eval import Pred, clip_bounds, match, parse_label, summarize  # noqa: E402

HAND = {"forehand": "fh", "backhand": "bh", "overhead": "-"}


def download(yt_id: str, dest: Path, t0: float | None = None, t1: float | None = None) -> Path | None:
    """The video, or only [t0, t1] seconds of it (much smaller and faster)."""
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "yt_dlp", "-q", "--no-warnings", "-f", "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]",
           "--merge-output-format", "mp4", "-o", str(dest)]
    if t0 is not None:
        cmd += ["--download-sections", f"*{t0:.2f}-{t1:.2f}", "--force-keyframes-at-cuts"]
    cmd.append(f"https://www.youtube.com/watch?v={yt_id}")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode or not dest.exists():
        print(f"  no se pudo descargar {yt_id}: {r.stderr.strip()[-200:]}")
        return None
    return dest


def cut(src: Path, start: int, end: int, fps: float, dest: Path) -> Path:
    """Frame-accurate cut (re-encoded) of [start, end] frames, keeping the audio."""
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start / fps:.3f}", "-i", str(src),
                        "-t", f"{(end - start + 1) / fps:.3f}", "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
                        "-c:a", "aac", str(dest)], check=True)
    return dest


def court_H(clip: Path):
    """Court homography (her own frame, near side) from a frame in the middle of the clip."""
    import cv2

    from tennisbio.court import fit_court
    cap = cv2.VideoCapture(str(clip))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, n // 2)
    ok, frame = cap.read()
    cap.release()
    fit = fit_court(frame) if ok else None
    return None if fit is None else fit.H


def shot_labels(run, r, H, hand: str):
    """(direction code, approach, error) of one detected stroke, as F3Set labels them."""
    import numpy as np

    from tennisbio.court_metrics import court_metrics, feet_on_court, shot_landing
    if H is None:
        return "-", None, None
    cm = court_metrics(run.img, run.sk, H, r.stroke, r.impact_frame)
    x = (cm.get("court_pos_m") or [None])[0]
    land = shot_landing(H, (r.ball or {}).get("shot_bounce_candidates") or [], x, run.fps, r.impact_frame)
    d = {"cruzada": "CC", "paralela": "DL", "al centro": "DM"}.get(land.get("shot_direction"), "-")
    dom = 1 if hand == "right" else -1
    if r.stroke == "forehand" and x is not None and x * dom < -0.5 and d in ("CC", "DL"):
        d = "IO" if d == "CC" else "II"          # forehand from her backhand side
    if r.stroke == "backhand" and x is not None and x * dom > 0.5 and d in ("CC", "DL"):
        d = "IO" if d == "CC" else "II"
    a = feet_on_court(run.img, r.impact_frame, run.sk, H)
    b = feet_on_court(run.img, min(len(run.img) - 1, r.impact_frame + int(run.fps)), run.sk, H)
    approach = None if a is None or b is None else bool(np.mean([b[0][1], b[1][1]]) - np.mean([a[0][1], a[1][1]]) > 1.5)
    err = None if land.get("shot_in") is None else not land["shot_in"]
    from tennisbio.technique import stroke_technique
    ph = {k: v.get("frame") for k, v in r.phases.items()}
    tech = stroke_technique(run.img, run.conf, run.sk, run.fps, run.height_t, r.impact_frame, ph, r.stroke)
    sw = tech["classes"].get("swing")
    return d, approach, err, None if sw is None else sw.startswith("cortado")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="datasets")
    ap.add_argument("--split", default="test")
    ap.add_argument("--player", default="Rybakina", help="solo clips donde juega (vacío = todos)")
    ap.add_argument("--clips", type=int, default=20)
    ap.add_argument("--tol", type=int, default=3, help="tolerancia en fotogramas para casar un impacto")
    ap.add_argument("--no-racket", action="store_true")
    ap.add_argument("--ball", default=str(Path(__file__).resolve().parents[1] / "models" / "balltrack.onnx"))
    ap.add_argument("--device", default="dml")
    args = ap.parse_args()
    root = Path(args.root)
    tracker = None
    if Path(args.ball).exists():
        from tennisbio.ball import BallTracker
        tracker = BallTracker(args.ball, args.device)
    clips, videos = f3set_tennis(root, args.split)
    yt = {v["video_name"]: v for v in videos}
    sel = [c for c in clips if not args.player or args.player.lower() in (c["near_name"] + c["far_name"]).lower()]
    sel = sel[:: max(1, len(sel) // args.clips)][:args.clips]
    print(f"{len(sel)} clips seleccionados")

    all_pairs, all_fp, all_fn, rows = [], [], [], []
    for c in sel:
        name, a, b = clip_bounds(c["video"])
        if name not in yt:
            continue
        fps = float(yt[name].get("fps") or c["fps"])
        clip = root / "f3set" / "clips" / f"{c['video']}.mp4"
        if not clip.exists():
            # only this point: download its seconds (plus a margin) and cut it frame-exactly
            part = download(yt[name]["yt_id"], root / "f3set" / "parts" / f"{c['video']}.mp4", max(0, a / fps - 3), b / fps + 3)
            if part is None:
                continue
            cut(part, int(round((a / fps - max(0, a / fps - 3)) * fps)), int(round((a / fps - max(0, a / fps - 3)) * fps)) + b - a,
                fps, clip)
        hand = "right" if c["near_hand"] == "RH" else "left"
        run = run_clip(clip, clip.with_suffix(".npz"), hand=hand, rackets=not args.no_racket, log=lambda *_: None,
                       init_mode="near", ball=tracker)
        k = c["fps"] / run.fps                 # if YouTube served another frame rate, map back to annotation frames
        H = court_H(clip)
        preds = [Pred(int(round(r.impact_frame * k)), HAND[r.stroke], *shot_labels(run, r, H, hand)) for r in run.strokes]
        gts = [g for g in (parse_label(e["frame"], e["label"]) for e in c["events"]) if g.side == "near"]
        pairs, fp, fn = match(preds, gts, args.tol)
        all_pairs += pairs; all_fp += fp; all_fn += fn
        s = summarize(pairs, fp, fn)
        rows.append(dict(clip=c["video"], near=c["near_name"], tracked=round(run.tracked_frac, 2), **s))
        print(f"  {c['video'][:70]:70} gt {s['gt']:2} det {s['detected']:2} tp {s['true_positives']:2} "
              f"fh/bh {s['fh_bh_accuracy']}", flush=True)

    total = summarize(all_pairs, all_fp, all_fn)
    out = root / "reports"
    out.mkdir(parents=True, exist_ok=True)
    (out / "f3set_validation.json").write_text(json.dumps({"summary": total, "clips": rows}, indent=1))
    print("\nRESUMEN (jugador cercano)")
    for k, v in total.items():
        print(f"  {k:28} {v}")


if __name__ == "__main__":
    main()
