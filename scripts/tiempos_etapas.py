"""Where the time of an analysis goes (11-11): for every match folder under the output (the real ones and the
application's test folder `_app_nuevo`), each stage's seconds from its manifest (what the stage measured itself on
its last run), per minute of video, the total and the share of each stage. Writes
<output>/capturas_diag/tiempos_etapas.json and .md (uploaded to pc-logs). Reads only; changes nothing."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio.config import load_config  # noqa: E402

SKIP = {"windows", "series", "clips", "informe", "capturas_diag", "videos", "datos", "biblioteca"}


def manifests(root: Path, depth: int = 4) -> list[Path]:
    out, todo = [], [(root, 0)]
    while todo:
        d, k = todo.pop()
        f = d / "manifest.json"
        if f.exists():
            out.append(f)
        if k < depth:
            try:
                todo += [(c, k + 1) for c in d.iterdir() if c.is_dir() and c.name not in SKIP]
            except OSError:
                pass
    return sorted(out)


def table(f: Path) -> dict | None:
    try:
        man = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    dur = ((man.get("probe") or {}).get("summary") or {}).get("duration_min")
    st = {n: e for n, e in man.items() if isinstance(e, dict) and "seconds" in e}
    if not st:
        return None
    rows = sorted(({"etapa": n, "s": float(e.get("seconds") or 0), "a_la_vez_s": float(e.get("overlap_s") or 0),
                    "terminada": e.get("finished")} for n, e in st.items()), key=lambda r: -r["s"])
    wall = sum(r["s"] - r["a_la_vez_s"] for r in rows)
    for r in rows:
        r["s_por_min_video"] = round(r["s"] / dur, 2) if dur else None
        r["parte"] = round(r["s"] / sum(x["s"] for x in rows), 3) if rows else None
    return {"carpeta": str(f.parent), "minutos_video": dur, "total_min": round(wall / 60, 1),
            "veces_el_video": round(wall / 60 / dur, 2) if dur else None, "etapas": rows}


def main() -> None:
    cfg = load_config()
    root = Path((cfg.get("paths") or {}).get("output") or "output")
    res = [t for f in manifests(root) if (t := table(f))]
    dst = root / "capturas_diag"
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "tiempos_etapas.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    md = ["# Tiempo de cada etapa (última ejecución de cada etapa, según su manifest)", ""]
    for t in res:
        md += [f"## {Path(t['carpeta']).name}", f"vídeo {t['minutos_video']} min · total {t['total_min']} min · "
               f"{t['veces_el_video']} veces la duración del vídeo", "", "| etapa | min | s por min de vídeo | parte | terminada |",
               "|---|---|---|---|---|"]
        md += [f"| {r['etapa']} | {r['s'] / 60:.1f} | {r['s_por_min_video']} | {100 * (r['parte'] or 0):.0f} % | {r['terminada']} |"
               for r in t["etapas"]]
        md.append("")
    (dst / "tiempos_etapas.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
