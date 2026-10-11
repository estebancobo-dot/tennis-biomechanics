"""Automatic racket validation against RacketVision (tennis broadcast, human-annotated keypoints).

Downloads the test split annotations and the needed clips, runs racket segmentation + pose on the
annotated frames, and reports detection recall and orientation/position errors.

    uv run python scripts/validate_racket.py --root C:\\tenis\\datasets --images 300
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio.pose.yolo import RACKET_CLASS  # noqa: E402
from tennisbio.validation.datasets import racketvision_split, racketvision_video  # noqa: E402
from tennisbio.validation.racket_eval import match_racket, summarize, to_rows  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="datasets")
    ap.add_argument("--images", type=int, default=300, help="fotogramas anotados a evaluar (muestra uniforme)")
    ap.add_argument("--imgsz", type=int, default=1280)
    ap.add_argument("--seg-model", default="yolo11m-seg.pt")
    ap.add_argument("--pose-model", default="yolo11m-pose.pt")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    root = Path(args.root)
    out = Path(args.out or root / "reports")
    out.mkdir(parents=True, exist_ok=True)

    coco = racketvision_split(root, "test")
    rackets = defaultdict(list)
    for a in coco["annotations"]:
        if a["category_id"] == 2 and a.get("keypoints"):
            rackets[a["image_id"]].append(a)
    images = [im for im in coco["images"] if im["id"] in rackets]
    step = max(1, len(images) // args.images)
    images = images[::step][:args.images]
    print(f"{len(images)} fotogramas con {sum(len(rackets[i['id']]) for i in images)} raquetas anotadas")

    cache_path = out / f"racket_predictions_{args.imgsz}.npz"
    cache = dict(np.load(cache_path, allow_pickle=True)["preds"].item()) if cache_path.exists() else {}
    seg = pose = None
    by_video = defaultdict(list)
    for im in images:
        match, _, clip, name = im["file_name"].split("/")
        by_video[(match, clip)].append((int(Path(name).stem), im))

    matches, examples = [], 0
    for (match, clip), items in sorted(by_video.items()):
        cap = None
        for f, im in sorted(items, key=lambda x: x[0]):
            frame = None
            if im["id"] not in cache or examples < 12:
                cap = cap or cv2.VideoCapture(str(racketvision_video(root, match, clip)))
                cap.set(cv2.CAP_PROP_POS_FRAMES, f)
                ok, frame = cap.read()
                if not ok:
                    continue
            if im["id"] not in cache:
                if seg is None:
                    from ultralytics import YOLO
                    seg, pose = YOLO(args.seg_model), YOLO(args.pose_model)
                s = seg.predict(frame, imgsz=args.imgsz, conf=0.1, classes=[RACKET_CLASS], verbose=False)[0]
                polys = [p.astype(float) for p in (s.masks.xy if s.masks is not None else [])]
                pr = pose.predict(frame, imgsz=args.imgsz, conf=0.25, verbose=False)[0]
                wr = pr.keypoints.xy.cpu().numpy()[:, [9, 10]].reshape(-1, 2) if len(pr.boxes) else np.zeros((0, 2))
                cache[im["id"]] = (polys, wr[(wr > 0).all(1)])
            polys, wr = cache[im["id"]]
            for a in rackets[im["id"]]:
                kps = np.array(a["keypoints"], float).reshape(5, 3)
                m = match_racket(kps, a["bbox"], polys, wr)
                if m is None:
                    continue
                matches.append(m)
                if frame is not None and examples < 12 and m.length_px > 60:
                    vis = frame.copy()
                    for p in polys:
                        cv2.polylines(vis, [p.astype(np.int32)], True, (255, 80, 220), 2)
                    for k in kps[:, :2]:
                        cv2.circle(vis, tuple(map(int, k)), 4, (60, 240, 60), -1)
                    x, y, w, h = map(int, a["bbox"])
                    pad = int(max(w, h) * 1.5)
                    crop = vis[max(0, y - pad):y + h + pad, max(0, x - pad):x + w + pad]
                    cv2.imwrite(str(out / f"racket_example_{examples:02d}.jpg"), cv2.resize(crop, (300, 300)))
                    examples += 1
        print(f"  {match}_{clip}: {len(matches)} raquetas evaluadas", flush=True)

    np.savez_compressed(cache_path, preds=np.array(cache, dtype=object))
    report = {"all": summarize(matches), "near_player_like (>=80 px)": summarize(matches, 80),
              "large (>=120 px)": summarize(matches, 120)}
    (out / "racket_validation.json").write_text(json.dumps({"summary": report, "rows": to_rows(matches)}, indent=1))
    for k, v in report.items():
        print(f"\n[{k}]")
        for kk, vv in v.items():
            print(f"  {kk:28} {vv}")


if __name__ == "__main__":
    main()
