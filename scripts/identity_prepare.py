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


def _summary(d: Path, ps: dict, dest: Path) -> None:
    """A small copy of the identity for pc-logs (09-11): the clothes check, how the click goes, the photos' check
    and, per run, its group, end changes and margin (not the clothing codes), so Claude can tell why two photos
    look alike without asking for the whole match folder."""
    from tennisbio import match_files as mf
    f = mf.at(d, "identity.json")
    if not f.exists():
        return
    ident = json.loads(f.read_text(encoding="utf-8"))
    runs = [{k: r.get(k) for k in ("start", "end", "cluster", "clothes_margin", "end_changes", "near_is_target", "method")}
            for r in ident.get("runs", [])]
    dest.write_text(json.dumps({"fps": ident.get("fps"), "click_by": ident.get("click_by", "clothes (v8)"),
                                "clothes": ident.get("clothes"), "fotos": {k: ps.get(k) for k in ("by", "check")},
                                "photos_t": [p["t"] for p in ps.get("photos", [])], "runs": runs},
                               ensure_ascii=False), encoding="utf-8")


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
    from tennisbio import layout
    for m in matches:
        t0 = time.time()
        # the match's real folder, the one the analysis uses (09-11: «root / m.id» was another folder, so the cheap pass
        # was redone from scratch for the 4 reference matches and the click would not reach the analysis)
        d = layout.dir_of(root, m, cfg)
        if d.exists() and ic.state(d).get("done"):
            state[m.id] = {"listo": True, "grupos": 2, "clic_hecho": True, "minutos": 0.0}
            print(f"[{m.id}] clic ya hecho: nada que preparar", flush=True)
            (out / "estado.json").write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
            continue
        print(f"[{m.id}] pasada barata hasta la identidad ({d})", flush=True)
        try:
            pipeline.run(pipeline.Context(m, cfg, d, log=lambda s: print(f"  {s}", flush=True)), ["identity"])
            st = ic.state(d)
            ps = ic.photo_set(d, Path(m.video)) if st["possible"] else {"photos": [], "by": None,
                                                                            "check": ic.stage_check(d) or {}}
            photos = ps["photos"]
            for p in photos:
                shutil.copy(p["path"], out / f"{m.id}_{p['cluster']}.jpg")
            state[m.id] = {"listo": bool(photos) and len(photos) == 2, "grupos": len(photos), "clic_hecho": st["done"],
                           "minutos": round((time.time() - t0) / 60, 1)}
            # 09-11 (request 167): the automatic check that the two photos are two different groups
            ck = ps.get("check") or {}
            if ck.get("distinguishable") is False:
                state[m.id]["fotos"] = "fotos no distinguibles"
                state[m.id]["motivo"] = ck.get("why")
                state[m.id]["fotos_por"] = {"ends": "cambios de lado del marcador"}.get(ps.get("by"), "ninguno: sin clic")
            elif photos:
                state[m.id]["fotos"] = "distinguibles"
            state[m.id]["distancia_fotos"] = ck.get("photo_dist")
            _summary(d, ps, out / f"{m.id}_identidad.json")
        except Exception as e:  # noqa: BLE001 — one broken match never stops the others
            state[m.id] = {"listo": False, "error": f"{type(e).__name__}: {e}"[:300]}
        print(f"[{m.id}] {state[m.id]}", flush=True)
        (out / "estado.json").write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(s.get("listo", False) for s in state.values())
    print(f"\nListos para el clic: {ok} de {len(state)} partidos.", flush=True)
    alike = [k for k, s in state.items() if s.get("fotos") == "fotos no distinguibles"]
    if alike:
        print(f"Fotos no distinguibles por la ropa: {', '.join(alike)}", flush=True)


if __name__ == "__main__":
    main()
