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

from tennisbio.stage_times import all_tables, manifests, roots_of, table  # noqa: E402,F401  (the tests use them)


def main() -> None:
    cfg = load_config()
    root = Path((cfg.get("paths") or {}).get("output") or "output")
    res = all_tables(roots_of(cfg))
    dst = root / "capturas_diag"
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "tiempos_etapas.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    md = ["# Tiempo de cada etapa (última ejecución de cada etapa, según su manifest)", ""]
    for t in res:
        md += [f"## {Path(t['carpeta']).name}", f"vídeo {t['minutos_video']} min · total {t['total_min']} min · "
               f"{t['veces_el_video']} veces la duración del vídeo · "
               + ("desde cero" if t["desde_cero"] else f"no es desde cero (releídas: {', '.join(t['releidas'])})"), "", "| etapa | min | s por min de vídeo | parte | terminada |",
               "|---|---|---|---|---|"]
        md += [f"| {r['etapa']} | {r['s'] / 60:.1f} | {r['s_por_min_video']} | {100 * (r['parte'] or 0):.0f} % | {r['terminada']} |"
               for r in t["etapas"]]
        for r in t["etapas"]:
            if r.get("partes_s"):
                top = ", ".join(f"{k} {v / 60:.1f} min" for k, v in list(r["partes_s"].items())[:8])
                md.append(f"- dentro de {r['etapa']}: {top}" + (f"; cuentas {r['cuentas']}" if r.get("cuentas") else ""))
        md.append("")
    (dst / "tiempos_etapas.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
