"""Why a near stroke has no pose of hers at the contact (12-12, R10). For up to N near strokes of a match without any
keypoint within ±0.3 s of the impact: the window's pose cache (every person the pose model found, per frame) around
the impact: how many people per frame, their boxes, and the last box of her track before the gap; and an image of the
impact frame with every person found (green) and her last tracked box (red). JPEGs sinpose_<id>.jpg and
diag_sin_pose.json in <output>/capturas_diag (flat). Reads only.

    uv run python scripts/diag_sin_pose.py --match final --n 4"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio import match_files as _mf  # noqa: E402
from tennisbio.config import load_config  # noqa: E402
from tennisbio.stage_times import manifests, roots_of  # noqa: E402


def near_pose(ser: dict, span_s: float = 0.3) -> bool:
    kps, imp, first = ser.get("kp") or [], int(ser.get("impact") or 0), int(ser.get("first") or 0)
    w = int(round(span_s * float(ser.get("fps") or 25)))
    a, b = max(0, imp - first - w), min(len(kps), imp - first + w + 1)
    return any(kps[i] and any(v is not None for v in kps[i]) for i in range(a, b))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", required=True)
    ap.add_argument("--n", type=int, default=4)
    a = ap.parse_args()
    cfg = load_config()
    root = Path((cfg.get("paths") or {}).get("output") or "output")
    rep = []
    for r in roots_of(cfg):
        for man in manifests(r):
            d = man.parent.parent if man.parent.name == "etapas" else man.parent
            if a.match.lower() not in str(d).lower() and a.match.lower() not in json.dumps(
                    json.loads(_mf.at(d, "partido.json").read_text(encoding="utf-8")) if _mf.at(d, "partido.json").exists() else {}).lower():
                continue
            f = _mf.at(d, "strokes.json")
            if not f.exists():
                continue
            done = 0
            for s in json.loads(f.read_text(encoding="utf-8")):
                if done >= a.n or s.get("side") == "far" or not s.get("series") or not s.get("window"):
                    continue
                ser = json.loads(_mf.at(d, s["series"]).read_text(encoding="utf-8"))
                if near_pose(ser):
                    continue
                win = _mf.at(d, "windows") / s["window"]
                caches = sorted(p for p in win.parent.glob(f"{win.stem}_*.npz")
                                if not any(x in p.name for x in ("_far", "_ball", "_r", "_follow")))
                info = {"stroke": s.get("stroke_id"), "kind": s.get("stroke"), "source": s.get("source"),
                        "window": s["window"], "caches": [p.name for p in caches], "impact": ser.get("impact")}
                imp = int(ser.get("impact") or 0)
                last = None
                for i in range(int(ser.get("impact")) - int(ser.get("first")) - 1, -1, -1):
                    b = (ser.get("box") or [None])[i] if i < len(ser.get("box") or []) else None
                    if b:
                        last = (i + int(ser.get("first")), b)
                        break
                info["her_last_box_before"] = last
                if caches:
                    z = np.load(caches[0], allow_pickle=True)
                    boxes = z["boxes"]
                    info["people_per_frame_around_impact"] = {int(t): (0 if boxes[t] is None else int(len(boxes[t])))
                                                              for t in range(max(0, imp - 15), min(len(boxes), imp + 16), 5)}
                    bi = boxes[imp] if imp < len(boxes) else None
                    info["boxes_at_impact"] = [] if bi is None else [[int(v) for v in b[:4]] for b in bi]
                    cap = cv2.VideoCapture(str(win))
                    cap.set(cv2.CAP_PROP_POS_FRAMES, imp)
                    ok, img = cap.read()
                    cap.release()
                    if ok:
                        for b in info["boxes_at_impact"]:
                            cv2.rectangle(img, (b[0], b[1]), (b[2], b[3]), (0, 255, 0), 3)
                        if last:
                            b = [int(v) for v in last[1]]
                            cv2.rectangle(img, (b[0], b[1]), (b[2], b[3]), (0, 0, 255), 3)
                        out = root / "capturas_diag" / f"sinpose_{str(s.get('stroke_id'))[-7:]}.jpg"
                        cv2.imwrite(str(out), cv2.resize(img, (960, int(960 * img.shape[0] / img.shape[1]))))
                        info["image"] = out.name
                rep.append(info)
                done += 1
    dst = root / "capturas_diag"
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "diag_sin_pose.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1, default=str)[:3000])


if __name__ == "__main__":
    main()
