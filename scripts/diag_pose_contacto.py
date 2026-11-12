"""How many analysed strokes have no pose of hers at the contact (12-12, R5: exported videos without skeleton; their
series had no keypoint within ±15 frames of the impact). For every match folder: per side and kind, the strokes, those
with no keypoint within ±0.3 s of the impact, and how many of those still carry body measures (elbow, knees, height of
the contact). Writes <output>/capturas_diag/diag_pose_contacto.json. Reads only.

    uv run python scripts/diag_pose_contacto.py"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio import match_files as _mf  # noqa: E402
from tennisbio.config import load_config  # noqa: E402
from tennisbio.stage_times import manifests, roots_of  # noqa: E402

BODY = ("elbow_impact_deg", "contact_height_pct", "knee_dom_impact_deg", "hip_drop_pct", "contact_lateral_pct")


def pose_near(ser: dict, span_s: float = 0.3) -> int:
    kps, imp, first, fps = ser.get("kp") or [], int(ser.get("impact") or 0), int(ser.get("first") or 0), float(ser.get("fps") or 25)
    w = int(round(span_s * fps))
    a, b = max(0, imp - first - w), min(len(kps), imp - first + w + 1)
    return sum(1 for i in range(a, b) if kps[i] and any(v is not None for v in kps[i]))


def main() -> None:
    cfg = load_config()
    root = Path((cfg.get("paths") or {}).get("output") or "output")
    rep = {}
    for r in roots_of(cfg):
        for man in manifests(r):
            d = man.parent.parent if man.parent.name == "etapas" else man.parent
            f = _mf.at(d, "strokes.json")
            if not f.exists() or "_poc" in str(d) or "_bench" in str(d) or "_app_nuevo" in str(d):
                continue
            try:
                strokes = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            agg = defaultdict(lambda: {"golpes": 0, "sin_pose_en_el_contacto": 0, "de_ellos_con_medidas": 0, "ejemplos": []})
            for s in strokes:
                key = f"{s.get('side')}/{s.get('stroke')}"
                a = agg[key]
                a["golpes"] += 1
                try:
                    ser = json.loads(_mf.at(d, s["series"]).read_text(encoding="utf-8")) if s.get("series") else {}
                except (OSError, ValueError):
                    ser = {}
                if pose_near(ser) == 0:
                    a["sin_pose_en_el_contacto"] += 1
                    m = s.get("metrics") or {}
                    if any(m.get(k) is not None for k in BODY):
                        a["de_ellos_con_medidas"] += 1
                    if len(a["ejemplos"]) < 3:
                        a["ejemplos"].append(s.get("stroke_id"))
            rep[d.name] = dict(agg)
    dst = root / "capturas_diag"
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "diag_pose_contacto.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1)[:3000])


if __name__ == "__main__":
    main()
