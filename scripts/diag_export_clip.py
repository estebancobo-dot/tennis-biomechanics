"""The export's own view of a stroke (12-11, R5): for each stroke id given (a part of it), what the export's StrokeClip
reads and draws at the impact: its cropped frame with the series' keypoints mapped by its crop (P), next to the raw
window frame at the same index read with OpenCV, plus the window's start_time, fps and frame count from ffmpeg and the
crop at that frame. Shows whether the export's frames and the series are out of step (time) or the crop is off.
JPEGs expclip_<id>.jpg and diag_export_clip.json in <output>/capturas_diag (flat). Reads only.

    uv run python scripts/diag_export_clip.py 0312430 0966569 0048549"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio import match_files as _mf  # noqa: E402
from tennisbio.config import load_config  # noqa: E402
from tennisbio.stage_times import manifests, roots_of  # noqa: E402


def main() -> None:
    from tennisbio.export import StrokeClip
    cfg = load_config()
    root = Path((cfg.get("paths") or {}).get("output") or "output")
    want, rep = sys.argv[1:], []
    for r in roots_of(cfg):
        for man in manifests(r):
            d = man.parent.parent if man.parent.name == "etapas" else man.parent
            f = _mf.at(d, "strokes.json")
            try:
                strokes = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
            except (OSError, ValueError):
                continue
            for s in strokes:
                sid = str(s.get("stroke_id") or "")
                if not any(w in sid for w in want) or not s.get("series") or not s.get("window"):
                    continue
                # as the report gives it to the export (report.py: the folder of strokes.json, its relative series)
                rec = {"_dir": str(f.parent), "_series": s["series"], "_window": s["window"]}
                try:
                    c = StrokeClip(rec, {"hand": "right"})
                except Exception as e:  # noqa: BLE001
                    rep.append({"stroke": sid, "error": f"StrokeClip: {e}"})
                    continue
                k = c.impact - c.first
                cand = [i for i in range(max(0, k - 15), min(c.n, k + 16)) if c.kp[i] is not None and np.isfinite(c.kp[i]).any()]
                k = min(cand, key=lambda i: abs(i - (c.impact - c.first))) if cand else k
                crop = c.frames[k].copy()
                if c.kp[k] is not None:
                    for p in c.kp[k]:
                        if np.isfinite(p).all():
                            x, y = c.P(k, p)
                            cv2.circle(crop, (int(x), int(y)), 6, (0, 255, 0), -1)
                cap = cv2.VideoCapture(str(c.video))
                cap.set(cv2.CAP_PROP_POS_FRAMES, c.first + k)
                ok, raw = cap.read()
                cap.release()
                if ok and c.kp[k] is not None:
                    for p in c.kp[k]:
                        if np.isfinite(p).all():
                            cv2.circle(raw, (int(p[0]), int(p[1])), 6, (0, 255, 0), -1)
                    raw = cv2.resize(raw, (crop.shape[1], int(crop.shape[1] * raw.shape[0] / raw.shape[1])))
                img = np.vstack([crop, raw]) if ok else crop
                out = root / "capturas_diag" / f"expclip_{sid[-7:]}.jpg"
                cv2.imwrite(str(out), cv2.resize(img, (img.shape[1] // 2, img.shape[0] // 2)))
                rep.append({"stroke": sid, "frame": int(k), "impact": int(c.impact), "first": int(c.first), "n": int(c.n),
                            "start_time": getattr(c.info, "start_time", None), "fps": getattr(c.info, "fps", None),
                            "size": [c.vw, c.vh], "crop": [float(c.sx[k]), float(c.sy[k]), float(c.scale[k])],
                            "kp_at_frame": None if c.kp[k] is None else [round(float(v), 1) for v in c.kp[k][[0, 5, 6, 9, 10]].ravel()],
                            "image": out.name})
    dst = root / "capturas_diag"
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "diag_export_clip.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1, default=str)[:3000])


if __name__ == "__main__":
    main()
