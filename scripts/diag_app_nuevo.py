"""What failed in the application's new-match test (11-11, request 209): the audit of each analysis the test
published in its own folder (<output>/_app_nuevo/output/analisis/<id>/actual|pendiente/auditoria/auditoria.json),
every check that is not ✔ with its detail, and the review against the previous version. Writes
<output>/capturas_diag/app_nuevo_fallos.md and .json (uploaded to pc-logs). Reads only."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio.config import load_config  # noqa: E402


def failing(audit_json: Path) -> list[dict]:
    try:
        items = json.loads(audit_json.read_text(encoding="utf-8")).get("items", [])
    except (OSError, ValueError):
        return []
    return [{"estado": i.get("status"), "area": i.get("area"), "nombre": i.get("name"), "detalle": (i.get("detail") or "")[:400]}
            for i in items if i.get("status") != "ok"]


def main() -> None:
    cfg = load_config()
    root = Path((cfg.get("paths") or {}).get("output") or "output")
    base = root / "_app_nuevo" / "output" / "analisis"
    res = {}
    for a in sorted(base.glob("*/*/auditoria/auditoria.json")) if base.exists() else []:
        res[f"{a.parents[2].name}/{a.parents[1].name}"] = failing(a)
    dst = root / "capturas_diag"
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "app_nuevo_fallos.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    md = ["# Lo que no pasa en la prueba de un partido nuevo con la aplicación", ""]
    if not res:
        md.append(f"Sin auditorías en {base}")
    for k, its in res.items():
        md += [f"## {k}: {len(its)} comprobaciones sin ✔", "", "| estado | apartado | comprobación | detalle |", "|---|---|---|---|"]
        md += [f"| {i['estado']} | {i['area']} | {i['nombre']} | {i['detalle'].replace('|', '/')} |" for i in its]
        md.append("")
    (dst / "app_nuevo_fallos.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
