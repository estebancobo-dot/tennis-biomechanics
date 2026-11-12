"""Do a stroke's series and its window video line up? (12-11, R5: exported videos with the skeleton off the player or
missing.) For each stroke id given (a part of it), the window frame at the impact with the series' keypoints drawn as
stored (green), mirrored in x (red) and scaled to the window's width if they look like another frame size (blue), plus
the numbers: window size and frames, series fps/first/impact/n, the range of the keypoints and boxes, the stroke's
side and kind. JPEGs and diag_serie_ventana.json in <output>/capturas_diag (flat). Reads only.

    uv run python scripts/diag_serie_ventana.py 0312430 0925800 0048549"""
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
    cfg = load_config()
    root = Path((cfg.get("paths") or {}).get("output") or "output")
    want = sys.argv[1:]
    rep = []
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
                ser = json.loads(_mf.at(d, s["series"]).read_text(encoding="utf-8"))
                win = _mf.at(d, "windows") / s["window"]
                cap = cv2.VideoCapture(str(win))
                W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                N, fps = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), cap.get(cv2.CAP_PROP_FPS)
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(ser["impact"]))
                ok, img = cap.read()
                cap.release()
                k = int(ser["impact"]) - int(ser["first"])
                kp = ser["kp"][k] if 0 <= k < len(ser["kp"]) else None
                pts = np.array([np.nan if v is None else v for v in (kp or [])], float).reshape(-1, 2)
                allk = np.array([[np.nan if v is None else v for v in (q or [np.nan, np.nan])] for q in ser["kp"]], dtype=object)
                xs = [v for q in ser["kp"] if q for v in q[0::2] if v is not None]
                ys = [v for q in ser["kp"] if q for v in q[1::2] if v is not None]
                bx = [b for b in ser.get("box") or [] if b]
                info = {"stroke": sid, "side": s.get("side"), "kind": s.get("stroke"), "window": s["window"],
                        "window_size": [W, H], "window_frames": N, "window_fps": fps,
                        "series": {k2: ser.get(k2) for k2 in ("fps", "first", "impact", "n")},
                        "kp_x": [min(xs), max(xs)] if xs else None, "kp_y": [min(ys), max(ys)] if ys else None,
                        "box_x": [min(b[0] for b in bx), max(b[2] for b in bx)] if bx else None,
                        "box_y": [min(b[1] for b in bx), max(b[3] for b in bx)] if bx else None,
                        "frame_read": bool(ok)}
                if ok and len(pts):
                    for (x, y) in pts:
                        if np.isfinite(x):
                            cv2.circle(img, (int(x), int(y)), 6, (0, 255, 0), -1)
                            cv2.circle(img, (int(W - x), int(y)), 6, (0, 0, 255), -1)
                    out = root / "capturas_diag" / f"serie_{sid[-7:]}.jpg"
                    cv2.imwrite(str(out), cv2.resize(img, (960, int(960 * H / max(1, W)))))
                    info["image"] = out.name
                rep.append(info)
                del allk
    dst = root / "capturas_diag"
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "diag_serie_ventana.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1, default=str)[:3000])


if __name__ == "__main__":
    main()
