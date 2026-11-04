"""Forecast before a long run on the PC (tennisbio.budget, 03-11): for every match of the catalogue, the stages
whose fingerprints changed (they would re-run) and how long each would take from the rates measured on this
machine; stages never measured on a whole match are flagged. Reads only fingerprints and small JSON files: seconds.

    uv run python scripts/preflight.py [--stages fine,fine_doubtful]

Writes <output>/prevision.md (the PC uploads it) and prints it. --stages: only those (as `repetir` forces them).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio import budget, layout, match_files as mf, pipeline, stages  # noqa: E402,F401  (registers the stages)
from tennisbio.catalog import load_matches  # noqa: E402
from tennisbio.config import load_config  # noqa: E402


def rows(cfg: dict, only: list[str] | None = None) -> list[dict]:
    out_root = Path(cfg["paths"]["output"])
    res = []
    for m in load_matches(cfg):
        d = layout.dir_of(out_root, m, cfg)
        ctx = pipeline.Context(m, cfg, d, log=lambda *_: None)
        try:
            st = pipeline.status(ctx)
        except pipeline.MissingVideo:
            continue
        if only:
            st = {n: ("stale" if n in only else "ok") for n in st}
        man = pipeline.load_manifest(d)
        probe = mf.at(d, "probe.json")
        dur = json.loads(probe.read_text(encoding="utf-8")).get("duration", 0) if probe.exists() else 0
        res.append({"match": m.id, "video_min": dur / 60, "stages": st,
                    "seconds": {n: (man.get(n) or {}).get("seconds", 0) for n in st}})
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="")
    ap.add_argument("--max-h", type=float, default=None,
                    help="exit 3 when the worst case is above this many hours (the PC then does not start the run)")
    a = ap.parse_args()
    cfg = load_config()
    out = Path(cfg["paths"]["output"])
    md, total = budget.forecast(rows(cfg, [s for s in a.stages.split(",") if s] or None), out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "prevision.md").write_text(md, encoding="utf-8")
    print(md)
    worst = getattr(budget.forecast, "last_upper", total) / 3600
    if a.max_h is not None and worst > a.max_h:
        print(f"NO SE LANZA: el peor caso ({worst:.1f} h) supera {a.max_h:g} h")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
