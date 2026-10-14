"""The automatic cycle of the PC, without the user: what to run for the new code, and the review of
the result against the previous run.

    python scripts/auto_cycle.py decide <changed file> ...     → prints: medidas | informe | nada
    python scripts/auto_cycle.py review <audit.json> <previous audit.json> <out.md> [log ...]

decide: a change in how strokes are measured needs the fine pass again from the caches (minutes,
scripts/recompute_measures.py); a change in the report, the audit or the configuration only needs the
report and the audit (scripts/rebuild_report.py); documents and tests need nothing on the PC.

review: compares the new audit with the previous one item by item, by name: what fails now, what got
worse (and was fine before), what got better, what is new, how the reliability of each measure
changed, and Python errors in the logs. The first line is the verdict (OK / REGRESIÓN / ERROR), so a
person or Claude reads one line; the rest is the detail.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# code that changes what is measured per stroke (the fine pass); the rest of src/ is report/audit
MEASURE = re.compile(r"^src/tennisbio/(technique|stages|clip_pipeline|stroke_analysis|footwork|kinematics|"
                     r"racket_orientation|racket|racket3d|racket_face|racket_pose|phases|court_metrics|ball3d|ball|limits|"
                     r"identity|impacts|tracking|returns|skeleton|series|outcome|reliability|replays|catalog|"
                     r"fine_gate|fine_ahead|footpoints|body_scale|pose/|io/)|^scripts/recompute_measures\.py$|^config/(strokes|players)/")
# the audit reads the matrix and the list of requests: a change there changes the audit
REPORT = re.compile(r"^src/|^config/|^scripts/(rebuild_report|auto_cycle)\.py$|^docs/(matriz_cobertura|peticiones_usuario)\.md$")
SETUP = re.compile(r"^(pyproject\.toml|uv\.lock)$")
ORDER = {"falta": 0, "aviso": 1, "pocos datos": 2, "ok": 3}
ERR = re.compile(r"Traceback \(most recent call last\)|^ERROR:|Error: ", re.M)


def decide(files: list[str]) -> str:
    files = [f.replace("\\", "/").strip() for f in files if f.strip()]
    if any(MEASURE.search(f) for f in files):
        return "medidas"
    if any(REPORT.search(f) or SETUP.search(f) for f in files):
        return "informe"
    return "nada"


def _items(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {i["name"]: i for i in data.get("items", [])}


def _reliability(items: dict) -> dict:
    """measure → verdict, read from the reliability item of the audit."""
    it = next((v for k, v in items.items() if k.startswith("Cada medida comprobada")), None)
    return {"detail": it["detail"]} if it else {}


def review(new: Path, old: Path, logs: list[Path]) -> tuple[str, str]:
    a, b = _items(new), _items(old)
    errors = []
    for lg in logs:
        if lg.exists():
            txt = lg.read_text(encoding="utf-8", errors="replace")
            errors += [f"{lg.name}: {m.group(0).strip()} … {txt[m.start():m.start() + 300].splitlines()[-1][:200]}"
                       for m in ERR.finditer(txt)][:3]
    fails = [i for i in a.values() if i["status"] == "falta"]
    worse = [(n, b[n]["status"], i["status"]) for n, i in a.items() if n in b and ORDER[i["status"]] < ORDER[b[n]["status"]]]
    better = [(n, b[n]["status"], i["status"]) for n, i in a.items() if n in b and ORDER[i["status"]] > ORDER[b[n]["status"]]]
    gone = [n for n in b if n not in a]
    added = [n for n in a if n not in b]
    if errors or not a:
        verdict = "ERROR"
    elif fails or [w for w in worse if w[2] == "falta"]:
        verdict = "REGRESIÓN" if worse else "FALLOS"
    else:
        verdict = "OK"
    cnt = {s: sum(i["status"] == s for i in a.values()) for s in ORDER}
    out = [f"# Revisión automática: {verdict}", "",
           f"{cnt['ok']} cumplidos · {cnt['falta']} no cumplidos · {cnt['pocos datos']} sin golpes suficientes · {cnt['aviso']} avisos"
           + (f" (antes: {sum(i['status'] == 'ok' for i in b.values())} cumplidos, {sum(i['status'] == 'falta' for i in b.values())} no cumplidos)" if b else " (primera revisión)"), ""]
    if errors:
        out += ["## Errores en los registros", ""] + [f"- {e}" for e in errors] + [""]
    if fails:
        out += ["## No cumplidos", ""] + [f"- **{i['name']}**: {i['detail'][:300]}" for i in fails] + [""]
    if worse:
        out += ["## Empeora respecto a la ejecución anterior", ""] + [f"- **{n}**: {x} → {y}: {a[n]['detail'][:200]}" for n, x, y in worse] + [""]
    if better:
        out += ["## Mejora", ""] + [f"- {n}: {x} → {y}" for n, x, y in better] + [""]
    if added:
        out += ["## Comprobaciones nuevas", ""] + [f"- {n}: {a[n]['status']} ({a[n]['detail'][:160]})" for n in added] + [""]
    if gone:
        out += ["## Comprobaciones que ya no aparecen", ""] + [f"- {n}" for n in gone] + [""]
    ra, rb = _reliability(a), _reliability(b)
    if ra and ra != rb:
        out += ["## Fiabilidad de las medidas", "", f"- ahora: {ra['detail'][:600]}"] + ([f"- antes: {rb['detail'][:600]}"] if rb else []) + [""]
    return verdict, "\n".join(out)


def main(argv: list[str]) -> int:
    if len(argv) >= 1 and argv[0] == "decide":
        print(decide(argv[1:]))
        return 0
    if len(argv) >= 4 and argv[0] == "review":
        verdict, md = review(Path(argv[1]), Path(argv[2]), [Path(x) for x in argv[4:]])
        Path(argv[3]).write_text(md, encoding="utf-8")
        print(md.splitlines()[0])
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
