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
                     r"identity|impacts|tracking|returns|situations|skeleton|series|outcome|reliability|replays|views|catalog|"
                     r"fine_gate|fine_ahead|footpoints|body_scale|trunk3d|point_count|candidates/bounce_own|candidates/bounce_ctb|"
                     r"pose/|io/)|^scripts/recompute_measures\.py$|^config/(strokes|players)/")
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


def _pending() -> str:
    """The unfinished user requests of docs/peticiones_usuario.md (tennisbio.requests_check)."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from tennisbio.requests_check import pending_markdown
        return pending_markdown()
    except Exception as e:                     # the review must still be written
        return f"## Peticiones del usuario SIN TERMINAR: no se pudo leer el registro ({e})"


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
    # what the user asked for and is not done, right under the verdict: «OK» only means «no regression»
    out += [_pending(), ""]
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


FLOW_OF = {"medidas": "medidas_prueba", "informe": "informe_prueba"}
QUEUE_PRIORITY = 9            # behind what was asked (the default is 5; lower goes first)


def to_queue(mode: str, submit=None) -> str:
    """13-11 (R28): what a code change needs goes to the single queue as a flow (FLOW_OF), behind what was asked;
    returns what the cycle must still do itself: always «nada». Before, the cycle ran the recompute in its own process,
    outside the queue: for an hour after the code of #265 (its window caches new) the queue's orders (a cancel) waited
    for it and it shared the iGPU with the job running."""
    if mode not in FLOW_OF:
        return "nada"
    if submit is None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from tennisbio.cli import main as tb
        submit = lambda flow: tb(["jobs", "submit", "--source", "ciclo", "--prioridad", str(QUEUE_PRIORITY), "--", "flujo", flow])
    rc = submit(FLOW_OF[mode])
    print(f"{mode}: en la cola como el flujo {FLOW_OF[mode]} (prioridad {QUEUE_PRIORITY})" if not rc else
          f"{mode}: no se pudo poner en la cola (código {rc})")
    return "nada"


def main(argv: list[str]) -> int:
    if len(argv) >= 1 and argv[0] == "decide":
        # the cycle reads the last line: «nada», what it does itself; the work went to the queue (R28)
        print(to_queue(decide(argv[1:])))
        return 0
    if len(argv) == 3 and argv[0] == "snapshot":          # the audit of before, kept for the review
        import shutil
        if Path(argv[1]).exists():
            Path(argv[2]).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(argv[1], argv[2])
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
