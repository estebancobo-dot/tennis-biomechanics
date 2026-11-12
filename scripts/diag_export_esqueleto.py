"""Why some exported stroke videos show no skeleton (12-11: «Vídeos exportados» found it in 6, 3 and 4 of 8 sampled
videos of the forehand, backhand and serve exports, looking at three moments of each). For the same sample the audit
takes, each video's stroke is found in the strokes.json of the match folders (output and library): its side, its
kind, and how many frames of its series carry keypoints, in all and around the impact; plus the skeleton pixels the
audit counts at its three moments. Writes <output>/capturas_diag/diag_export_esqueleto.json. Reads only.

    uv run python scripts/diag_export_esqueleto.py"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio import match_files as _mf  # noqa: E402
from tennisbio.audit import EXPORT_SAMPLE, _skeleton_pixels  # noqa: E402
from tennisbio.config import load_config  # noqa: E402
from tennisbio.stage_times import manifests, roots_of  # noqa: E402


def strokes_by_id(roots: list[Path]) -> dict:
    out = {}
    for r in roots:
        for man in manifests(r):
            d = man.parent.parent if man.parent.name == "etapas" else man.parent
            for name in ("strokes.json", "strokes_doubtful.json", "strokes_opponent.json"):
                f = _mf.at(d, name)
                try:
                    for s in json.loads(f.read_text(encoding="utf-8")) if f.exists() else []:
                        sid = s.get("stroke_id") or s.get("id")       # the export names its videos by stroke_id
                        if sid:
                            out.setdefault(sid, (d, s))
                except (OSError, ValueError):
                    continue
    return out


def main() -> None:
    import subprocess
    cfg = load_config()
    root = Path((cfg.get("paths") or {}).get("output") or "output")
    by_id = strokes_by_id(roots_of(cfg))
    rep = {}
    for exp in sorted(p for p in root.glob("exportar*") if (p / "golpes").is_dir()):
        vids = sorted((exp / "golpes").glob("*.mp4"))
        k = min(EXPORT_SAMPLE, len(vids))
        sample = [vids[round(i * (len(vids) - 1) / max(1, k - 1))] for i in range(k)] if k else []
        rows = []
        for v in sample:
            try:
                r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(v)],
                                   capture_output=True, text=True, timeout=20)
                dur = float(r.stdout.strip() or 0)
            except (OSError, subprocess.SubprocessError, ValueError):
                dur = 0.0
            px = [_skeleton_pixels(v, f * dur) for f in (0.3, 0.6, 0.9)] if dur else []
            d, s = by_id.get(v.stem, (None, {}))
            kp_all = kp_imp = n = None
            if s.get("series") and d is not None:
                try:
                    ser = json.loads(_mf.at(d, s["series"]).read_text(encoding="utf-8"))
                    kps, imp, first = ser.get("kp") or [], int(ser.get("impact") or 0), int(ser.get("first") or 0)
                    n = len(kps)
                    kp_all = sum(k is not None for k in kps)
                    w = int(round(0.3 * float(ser.get("fps") or 25)))
                    a, b = max(0, imp - first - w), min(n, imp - first + w + 1)
                    kp_imp = sum(kps[i] is not None for i in range(a, b))
                except (OSError, ValueError, TypeError):
                    pass
            rows.append({"video": v.name, "duracion_s": round(dur, 1), "pixeles_esqueleto": px,
                         "lado": s.get("side"), "golpe": s.get("stroke"), "fotogramas_serie": n,
                         "con_pose": kp_all, "con_pose_cerca_del_impacto": kp_imp, "encontrado": bool(s)})
        rep[exp.name] = rows
    dst = root / "capturas_diag"
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "diag_export_esqueleto.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1, default=str)[:3000])


if __name__ == "__main__":
    main()
