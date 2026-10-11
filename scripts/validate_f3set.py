"""Automatic stroke validation on TV broadcast with F3Set-Tennis ground truth.

Picks annotated rally clips (by default from Rybakina's matches), downloads the source videos
from YouTube with yt-dlp, cuts each clip, runs the same pipeline as analyze_clip.py on it and
compares near-player contacts with the annotations: precision, recall, timing error and
forehand/backhand accuracy. Doubles as the smoke test: --clips 5 takes a few minutes.

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

HAND = {"forehand": "fh", "backhand": "bh"}


def download(yt_id: str, dest: Path) -> Path | None:
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["yt-dlp", "-q", "--no-warnings", "-f", "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]",
           "--merge-output-format", "mp4", "-o", str(dest), f"https://www.youtube.com/watch?v={yt_id}"]
    r = subprocess.run(cmd, capture_output=True, text=True)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="datasets")
    ap.add_argument("--split", default="test")
    ap.add_argument("--player", default="Rybakina", help="solo clips donde juega (vacío = todos)")
    ap.add_argument("--clips", type=int, default=20)
    ap.add_argument("--tol", type=int, default=3, help="tolerancia en fotogramas para casar un impacto")
    ap.add_argument("--no-racket", action="store_true")
    args = ap.parse_args()
    root = Path(args.root)
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
        full = download(yt[name]["yt_id"], root / "f3set" / "videos" / f"{name}.mp4")
        if full is None:
            continue
        clip = cut(full, a, b, c["fps"], root / "f3set" / "clips" / f"{c['video']}.mp4")
        hand = "right" if c["near_hand"] == "RH" else "left"
        run = run_clip(clip, clip.with_suffix(".npz"), hand=hand, rackets=not args.no_racket, log=lambda *_: None)
        k = c["fps"] / run.fps                 # if YouTube served another frame rate, map back to annotation frames
        preds = [Pred(int(round(r.impact_frame * k)), HAND[r.stroke]) for r in run.strokes]
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
