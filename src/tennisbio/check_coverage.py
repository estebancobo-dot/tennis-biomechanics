"""Can every check of the audit fail? (11-11, R1 of the review of the Base, docs/revision_base_11-11.md)

The 11-11 review found checks that had never been seen failing: «Tiempo» passed while it summed stages that only re-read
their caches, «Nada pide revisión manual» was always ok. A check no test ever drives to a non-ok status proves nothing.

- While the tests run with TENNISBIO_REC_CHECKS=<folder> (the PC's background tests, scripts/windows/pruebas_fondo.ps1),
  tests/conftest.py wraps `audit._item` and writes every (area, name, status) a test produced to
  <folder>/rec_<worker>.json.
- `coverage_item(items, bases)` compares the checks of a real audit with that record: the ones no test ran, the ones
  no test made fail, and above all those of the main tests of the Base packages (config/plan_peticiones.yaml «prueba»)."""
from __future__ import annotations

import json
import re
from pathlib import Path

REC_ENV = "TENNISBIO_REC_CHECKS"
REC_DIR = "comprobaciones_pruebas"          # <output>/comprobaciones_pruebas/rec_*.json on the PC
ITEM = "Comprobaciones que saben fallar"


def norm(name: str) -> str:
    """The kind of a check: its name before «:» (the match or the detail after it), digits as N. «Partido <id>: <what>»
    carries the match first: its kind is «Partido · <what>»."""
    n = str(name)
    if n.startswith("Partido ") and ":" in n:
        return "Partido · " + re.sub(r"\d+", "N", n.split(":", 1)[1]).strip()
    return re.sub(r"\d+", "N", n.split(":")[0]).strip()


def install(out_dir: str):
    """Record every check the tests produce (called from tests/conftest.py when REC_ENV is set). Returns the function
    that writes the record (conftest calls it in pytest_unconfigure: each xdist worker writes its own file)."""
    import os

    from . import audit as _a
    rec: set = set()
    orig = _a._item

    def wrapped(req, area, name, status, detail, **kw):
        rec.add((str(area), norm(name), str(status)))
        return orig(req, area, name, status, detail, **kw)

    _a._item = wrapped

    def dump():
        d = Path(out_dir)
        d.mkdir(parents=True, exist_ok=True)
        (d / f"rec_{os.environ.get('PYTEST_XDIST_WORKER', 'main')}.json").write_text(
            json.dumps(sorted(rec), ensure_ascii=False), encoding="utf-8")

    return dump


def recorded(folder: Path) -> dict[tuple[str, str], set[str]]:
    out: dict = {}
    for f in sorted(Path(folder).glob("rec_*.json")):
        try:
            for a, n, s in json.loads(f.read_text(encoding="utf-8")):
                out.setdefault((a, n), set()).add(s)
        except (OSError, ValueError, TypeError):
            continue
    return out


def main_patterns() -> list[str]:
    from .real_status import packages
    pats = []
    for k, v in packages().items():
        if str(k).startswith("B"):
            pats += [p.lstrip("?") for p in (v.get("prueba") or [])]
    return pats


def compare(items: list[dict], rec: dict, patterns: list[str]) -> dict:
    """The kinds of check in `items` that no test ran, that no test made fail, and those of them in a main test."""
    kinds: dict = {}
    for it in items:
        kinds.setdefault((str(it.get("area")), norm(it.get("name", ""))), it.get("name", ""))
    no_test = sorted(k for k in kinds if k not in rec)
    never_fail = sorted(k for k in kinds if k in rec and not (rec[k] - {"ok"}))
    main = sorted({k for k in no_test + never_fail if any(re.search(p, kinds[k]) for p in patterns)})
    return {"kinds": len(kinds), "no_test": no_test, "never_fail": never_fail, "main": main}


def coverage_item(items: list[dict], bases: list[Path]) -> dict:
    from .audit import _item
    folder = next((b / REC_DIR for b in bases if (b / REC_DIR).is_dir() and any((b / REC_DIR).glob("rec_*.json"))), None)
    if folder is None:
        return _item(5, "Automático", ITEM, "aviso", f"sin el registro de las pruebas en este PC ({REC_DIR}/rec_*.json)")
    c = compare(items, recorded(folder), main_patterns())
    bad = len(c["no_test"]) + len(c["never_fail"])
    show = "; ".join(f"{a} | {n}" for a, n in c["main"][:6])
    return _item(5, "Automático", ITEM, "ok" if not c["main"] else "aviso",
                 f"{c['kinds'] - bad} de {c['kinds']} tipos de comprobación con una prueba que las hace fallar; "
                 f"{len(c['no_test'])} sin ninguna prueba y {len(c['never_fail'])} que nunca fallan en las pruebas; "
                 f"de las pruebas principales de la Base: {len(c['main'])}" + (f" ({show})" if show else ""))
