"""The reference strokes for diagnosis in the cloud (27-10): every match's strokes of one type (strokes.json rows)
and their frame-by-frame series, in one zip (<output>/referencia_<stroke>.zip), uploaded to pc-logs by the cycle.

    uv run python scripts/pack_reference.py [--stroke forehand] [--side near]
"""
import argparse
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def pack(dirs: list[tuple[str, Path]], dest: Path, stroke: str = "forehand", side: str | None = "near") -> dict:
    from tennisbio import match_files as mf

    n_strokes, n_series = 0, 0
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for mid, d in dirs:
            f = mf.at(d, "strokes.json")
            if not f.exists():
                continue
            rows = [s for s in json.loads(f.read_text(encoding="utf-8"))
                    if s.get("stroke") == stroke and (side is None or s.get("side", "near") == side)]
            z.writestr(f"{mid}/strokes.json", json.dumps(rows, ensure_ascii=False))
            n_strokes += len(rows)
            for s in rows:
                p = f.parent / (s.get("series") or "")
                if s.get("series") and p.is_file():
                    z.write(p, f"{mid}/{s['series']}")
                    n_series += 1
    return {"golpes": n_strokes, "series": n_series, "zip": str(dest)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stroke", default="forehand")
    ap.add_argument("--side", default="near")
    a = ap.parse_args()
    from tennisbio import layout
    from tennisbio.catalog import load_matches
    from tennisbio.config import load_config

    cfg = load_config()
    out = Path(cfg["paths"]["output"])
    dirs = [(m.id, layout.dir_of(out, m, cfg)) for m in load_matches(cfg)]
    print(json.dumps(pack(dirs, out / f"referencia_{a.stroke}.zip", a.stroke, a.side or None), ensure_ascii=False))


if __name__ == "__main__":
    main()
