"""Validation of «pausa arriba» (technique.loaded_pause, stroke.pause_at_loaded) on broadcast clips.

The measure reads the dominant wrist of the body pose. The independent reference is the racket:
a real pause at the top of the backswing stops the racket head too, while a continuous loop keeps
the head moving even when the hand moves little. Two racket signals, neither from the body pose:
- the racket silhouette (YOLO11m-seg, head centre; validated in docs/validacion.md), dense;
- the racket keypoints annotated by hand in RacketVision (tip and throat), every ~0.2 s.

Per near-player stroke found by the pipeline (pose + ball, as validate_rv_strokes.py) it compares the
pause of the hand with the time the racket head is still, and repeats the measure with the pose
subsampled to 25 fps. Also runs the synthetic checks (tennisbio.validation.pause_eval).

    uv run python scripts/validate_pause.py --root <datasets> --clips 43 --ball models/balltrack.onnx
"""
import argparse
import json
import pickle
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio.validation.datasets import RV_BASE, fetch, racketvision_split, racketvision_video  # noqa: E402


def annotated_rackets(coco: dict) -> dict:
    """{clip: {frame: [(tip, throat, butt), ...]}} from the RacketVision COCO annotations."""
    names = {i["id"]: i["file_name"] for i in coco["images"]}
    out = defaultdict(lambda: defaultdict(list))
    for a in coco["annotations"]:
        if a["category_id"] != 2 or "keypoints" not in a:
            continue
        m = re.match(r"(match\d+)/frame/(\d+)/(\d+)\.jpg", names[a["image_id"]])
        k = np.asarray(a["keypoints"], float).reshape(5, 3)
        out[f"{m.group(1)}_{m.group(2)}"][int(m.group(3))].append(k[:3, :2])
    return out


def collect(root: Path, clips: int, ball: str | None, device: str, imgsz: int, cached_only: bool = False) -> list[dict]:
    """Per near-player stroke: the series the measure and the references need (cached)."""
    from tennisbio.clip_pipeline import run_clip
    from tennisbio.kinematics import hip_center, to_body_frame
    from tennisbio.racket import pick_racket, racket_from_polygon

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from validate_rv_strokes import is_doubles

    out_path = root / "reports" / "pause_series.pkl"
    done = pickle.loads(out_path.read_bytes()) if out_path.exists() else {}
    split = json.loads(fetch(f"{RV_BASE}/info/test.json", root / "rv" / "test.json").read_text())
    sel = split[:: max(1, len(split) // clips)][:clips]
    ann = annotated_rackets(racketvision_split(root, "test"))
    tracker = None
    if ball:
        from tennisbio.ball import BallTracker
        tracker = BallTracker(ball, device)
    for match_id, clip in sel:
        name = f"{match_id}_{clip}"
        if name in done:
            continue
        cache = root / "rv" / "cache" / f"{name}.npz"
        if cached_only and not cache.exists():          # the pose of a new clip takes ~10 min on a CPU
            continue
        video = racketvision_video(root, match_id, clip)
        if cache.exists() and is_doubles(cache, video):
            done[name] = []
            continue
        run = run_clip(video, cache, rackets=True, imgsz=imgsz, init_mode="near", log=lambda *_: None, ball=tracker)
        if is_doubles(cache, video):
            done[name] = []
            continue
        sk, fps, img = run.sk, run.fps, run.img
        scale = run.height_t if run.height_t is not None else np.full(len(img), run.height_px)
        body = to_body_frame(img, sk, scale)
        hips = hip_center(img, sk)
        rows = []
        for r in run.strokes:
            ph = {k: v.get("frame") for k, v in r.phases.items()}
            if ph.get("loaded") is None:
                continue
            head = np.full((len(img), 2), np.nan)
            for f, polys in enumerate(run.rackets):
                w = img[f, sk["dom_wrist"]]
                if not len(polys) or not np.isfinite(w).all():
                    continue
                p = pick_racket(polys, w, 0.3 * float(scale[f]))
                o = racket_from_polygon(p, w) if p is not None else None
                if o is not None:
                    head[f] = o.head
            annot = {}
            for f, ks in ann.get(name, {}).items():
                if f >= len(img) or abs(f - r.impact_frame) > fps:
                    continue
                w = img[f, sk["dom_wrist"]]
                if not np.isfinite(w).all():
                    continue
                d = [min(np.linalg.norm(k[1] - w), np.linalg.norm(k[2] - w)) for k in ks]
                j = int(np.argmin(d))
                if d[j] < 0.25 * float(scale[f]):
                    annot[f] = ks[j]
            rows.append(dict(clip=name, fps=fps, impact=r.impact_frame, stroke=r.stroke, phases=ph,
                             dw=body[:, sk["dom_wrist"]], hips=hips, scale=np.asarray(scale, float),
                             head=head, annot=annot))
        done[name] = rows
        print(f"  {name}: {len(rows)} golpes del jugador cercano con armado", flush=True)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(pickle.dumps(done))
    return [r for rows in done.values() for r in rows]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="datasets")
    ap.add_argument("--clips", type=int, default=43)
    ap.add_argument("--ball", default=None)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--cached-only", action="store_true", help="solo los clips con la pose ya extraída")
    args = ap.parse_args()
    root = Path(args.root)
    from tennisbio.validation.pause_eval import evaluate, injected, loaded_pause_v1, synthetic
    strokes = collect(root, args.clips, args.ball, args.device, args.imgsz, args.cached_only)
    res = {"before": {"real": evaluate(strokes, loaded_pause_v1), "injected": injected(strokes, loaded_pause_v1),
                      "synthetic": synthetic(loaded_pause_v1)},
           "now": {"real": evaluate(strokes), "injected": injected(strokes), "synthetic": synthetic()}}
    out = root / "reports" / "pause_validation.json"
    out.write_text(json.dumps(res, indent=1, default=float))
    for k, v in res.items():
        print(f"\n{k.upper()}  ({len({r['clip'] for r in strokes})} clips)")
        print(json.dumps({**{a: b for a, b in v["real"].items() if a != "rows"}, "injected": v["injected"], "synthetic": v["synthetic"]}, indent=1, default=float))


if __name__ == "__main__":
    main()
