"""Gets every match ready for the user's one click (19-10, «¿Cuál es ella?»): the cheap pass up to the identity
stage (clothes split into two people) and one photo per clothes group, so the app shows them at once.

    uv run python scripts/identity_prepare.py OUT_DIR [--match ID ...]

OUT_DIR gets <match>_<group>.jpg and estado.json (per match: ready or why not, groups, click done), copied to
pc-logs so Claude can check that the two photos are two different people before telling the user to click.
Never writes the click itself."""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio import pipeline, stages  # noqa: E402,F401  (registers the stages)
from tennisbio.app import identity_click as ic  # noqa: E402
from tennisbio.catalog import load_matches  # noqa: E402
from tennisbio.config import load_config  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--match", nargs="+")
    args = ap.parse_args()
    cfg = load_config()
    root = Path(cfg.get("paths", {}).get("output", "output"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    matches = [m for m in load_matches(cfg) if not args.match or m.id in args.match]
    state = {}
    for m in matches:
        t0 = time.time()
        d = root / m.id
        print(f"[{m.id}] pasada barata hasta la identidad", flush=True)
        try:
            pipeline.run(pipeline.Context(m, cfg, d, log=lambda s: print(f"  {s}", flush=True)), ["identity"])
            st = ic.state(d)
            photos = ic.photos(d, Path(m.video)) if st["possible"] else []
            for p in photos:
                shutil.copy(p["path"], out / f"{m.id}_{p['cluster']}.jpg")
            state[m.id] = {"listo": bool(photos) and len(photos) == 2, "grupos": len(photos), "clic_hecho": st["done"],
                           "minutos": round((time.time() - t0) / 60, 1)}
        except Exception as e:  # noqa: BLE001 — one broken match never stops the others
            state[m.id] = {"listo": False, "error": f"{type(e).__name__}: {e}"[:300]}
        print(f"[{m.id}] {state[m.id]}", flush=True)
        (out / "estado.json").write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(s.get("listo", False) for s in state.values())
    print(f"\nListos para el clic: {ok} de {len(state)} partidos.", flush=True)


if __name__ == "__main__":
    main()
