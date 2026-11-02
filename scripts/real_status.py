"""Honest status of every user request (02-11): what the registry says (Claude's own label) against what the
automatic audit on the real outputs actually checks. Levels, from weakest to strongest:

  0 sin construir            the registry says FALTA
  1 construido, sin comprobar code exists, but no automatic check on the real outputs (or the check is only a doc)
  2 comprobación que falla    the audit checks it on the real outputs and it fails, warns, or has too few strokes
  3 comprobado en salidas     the audit checks it on the real outputs and it passes (the data or screen exists and
                              is consistent: NOT that it is correct)
  4 validado con verdad       measured against annotated ground truth (VALIDATED below, with its number)
  5 aceptado por el usuario   the user used it and accepted it (none yet)

    uv run python scripts/real_status.py <auditoria.json> [--out docs/estado_real_peticiones.md]
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs" / "peticiones_usuario.md"
# requests measured against annotated ground truth, with the measure (docs/validacion.md, plan_maestro.md)
VALIDATED: dict[int, str] = {}
LEVELS = ["sin construir", "construido, sin comprobar", "comprobación que falla", "comprobado en salidas",
          "validado con verdad", "aceptado por el usuario"]


def registry(path: Path = REGISTRY) -> list[tuple[int, str, str]]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*(\d+)\s*\|\s*([^|]*?)\s*\|\s*([A-ZÁÉÍÓÚ ]+?)\s*\|", line)
        if m:
            out.append((int(m.group(1)), m.group(2), m.group(3)))
    return out


def level(state: str, item: dict | None, rid: int) -> int:
    if rid in VALIDATED:
        return 4
    if state == "FALTA":
        return 0
    if not item:
        return 1
    d = item.get("detail", "")
    if "sin comprobación automática" in d or "no se comprueba en las salidas" in d:
        return 1
    return 3 if item.get("status") == "ok" else 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audit")
    ap.add_argument("--out", default=str(ROOT / "docs" / "estado_real_peticiones.md"))
    a = ap.parse_args()
    aud = json.loads(Path(a.audit).read_text(encoding="utf-8"))
    by = {}
    for it in aud.get("items", []):
        m = re.match(r"#(\d+) ", it.get("name", ""))
        if m:
            by[int(m.group(1))] = it
    rows = [(rid, title, st, level(st, by.get(rid), rid), by.get(rid)) for rid, title, st in registry()
            if st != "NO APLICA"]
    counts = [sum(r[3] == k for r in rows) for k in range(len(LEVELS))]
    lines = ["# Estado real de las peticiones (generado por `scripts/real_status.py`; no editar a mano)", "",
             f"{len(rows)} peticiones (sin las que no aplican). «HECHO» en el registro es la etiqueta de Claude; "
             "aquí cuenta solo lo que se comprueba.", "", "| Nivel | Peticiones |", "|---|---|"]
    lines += [f"| {k} {LEVELS[k]} | {counts[k]} |" for k in range(len(LEVELS))]
    lines += ["", "| # | Petición | Registro | Nivel | Lo que comprueba la auditoría |", "|---|---|---|---|---|"]
    for rid, title, st, lv, it in rows:
        det = (it or {}).get("detail", "—").replace("|", "/")[:140]
        lines.append(f"| {rid} | {title[:90]} | {st} | {lv} {LEVELS[lv]} | {det} |")
    Path(a.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(dict(zip(LEVELS, counts)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
