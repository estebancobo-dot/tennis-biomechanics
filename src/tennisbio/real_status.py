"""Honest status of every user request (02-11): what the registry says (Claude's own label) against what the
automatic audit on the real outputs actually checks. Levels, from weakest to strongest:

  0 sin construir            the registry says FALTA
  1 construido, sin comprobar code exists, but no automatic check on the real outputs (or the check is only a doc)
  2 comprobación que falla    the audit checks it on the real outputs and it fails, warns, or has too few strokes
  3 comprobado en salidas     the audit checks it on the real outputs and it passes (the data or screen exists and
                              is consistent: NOT that it is correct)
  4 validado con verdad       measured against annotated ground truth with its threshold (VALIDATED below)
(No "accepted by the user" level: validation is always automatic, request #238.)

Each request belongs to one work package of the plan (config/plan_peticiones.yaml); the progress of a package
is the levels of its requests.

Written next to each audit (cli.run_audit → <auditoria>/estado_real_peticiones.md, uploaded to pc-logs) and by
scripts/real_status.py.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "docs" / "peticiones_usuario.md"
# requests measured against annotated ground truth, with the measure (docs/validacion.md, plan_maestro.md)
VALIDATED: dict[int, str] = {}
LEVELS = ["sin construir", "construido, sin comprobar", "comprobación que falla", "comprobado en salidas",
          "validado con verdad"]
PLAN = ROOT / "config" / "plan_peticiones.yaml"


def packages(path: Path = PLAN) -> dict:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))["paquetes"]


def registry(path: Path = REGISTRY) -> list[tuple[int, str, str]]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        # the state may carry a note after it: "FALTA (19-10: …)", "HECHO (como «no medible»)"
        m = re.match(r"^\|\s*(\d+)\s*\|\s*([^|]*?)\s*\|\s*(HECHO|PARCIAL|FALTA|NO MEDIBLE|NO APLICA)[^|]*\|", line)
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


def render(aud: dict) -> tuple[str, dict]:
    """(markdown, {level: count}) of every request from one audit result (audit.audit's dict)."""
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
             "aquí cuenta solo lo que se comprueba. «Comprobado en salidas» = existe y es coherente con los datos "
             "reales, no que sea correcto; eso es «validado con verdad».", "", "| Nivel | Peticiones |", "|---|---|"]
    lines += [f"| {k} {LEVELS[k]} | {counts[k]} |" for k in range(len(LEVELS))]
    pk = packages()
    of = {rid: code for code, p in pk.items() for rid in p["peticiones"]}
    lv_of = {r[0]: r[3] for r in rows}
    lines += ["", "## Por paquete del plan (en el orden de ejecución)", "",
              "| Paquete | Peticiones | " + " | ".join(LEVELS) + " | Se cierra con |",
              "|---|---|" + "---|" * len(LEVELS) + "---|"]
    for code, p in pk.items():
        ids = [i for i in p["peticiones"] if i in lv_of]
        c = [sum(lv_of[i] == k for i in ids) for k in range(len(LEVELS))]
        lines.append(f"| {code} {p['nombre']} | {len(ids)} | " + " | ".join(str(x) for x in c) + f" | {p['cierre']} |")
    lines += ["", "## Cada petición", "", "| # | Petición | Paquete | Registro | Nivel | Lo que comprueba la auditoría |",
              "|---|---|---|---|---|---|"]
    for rid, title, st, lv, it in rows:
        det = (it or {}).get("detail", "—").replace("|", "/")[:140]
        lines.append(f"| {rid} | {title[:90]} | {of.get(rid, '—')} | {st} | {lv} {LEVELS[lv]} | {det} |")
    return "\n".join(lines) + "\n", dict(zip(LEVELS, counts))
