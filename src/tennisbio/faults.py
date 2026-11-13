"""Faults by criticality (request #265, approved by the user on 13-11: «adelante con la gestión de errores por niveles»).

Why: until 12-11 the only rule was implicit, «the analysis never stops», and most caught errors said nothing; the stroke
spotter ran without the ball of the match for three weeks (R17) with «bola 0 s» in every log. Now every caught error is
a fault with a code of the catalogue (config/fallos.yaml, an FMEA: where it happens, its effect, how it is detected,
its level, its reaction and its test), and the level decides the reaction, not whoever writes that line:

    C0 critical      the result would be wrong: the match stops, nothing of it is published, the job fails with its reason
    C1 degrading     the result is valid but worse and measurable (another model, an input under its minimum): it goes
                     on, marked in the manifest and the report; a full analysis is never accepted with one
    C2 local         one unit fails (a window, a stroke, a shot): isolated and recorded; over its budget (share of the
                     units) it becomes C0
    C3 transient     something passing (the iGPU lost, a locked file, the network): bounded retry; exhausted, it becomes
                     what the catalogue says (C0, or C1 when the fallback is worse)
    C4 informative   cosmetic: only recorded

    from tennisbio.faults import fault
    fault("bola.vacia", f"{cov['min']} min de bola en {play_min} min de juego")    # C0: raises CriticalFault

Every fault goes to the collector of the stage that runs (pipeline.run opens one per stage; manifest[stage]["faults"]
and the audit's «Fallos por niveles» read it). A handler whose exception is an expected outcome, not a fault (a number
that does not parse is «no number»), says so on its line: `except ValueError:  # esperado: <why>`;
tests/test_faults.py fails on any except that neither re-raises, nor calls fault(), nor says why it is expected.
"""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from pathlib import Path

LEVELS = ("C0", "C1", "C2", "C3", "C4")
CATALOG = Path(__file__).resolve().parents[2] / "config" / "fallos.yaml"
LOGGED = 3                       # lines per code and stage in the log (the rest only counted)
EXAMPLES = 5                     # details kept per code


class CriticalFault(RuntimeError):
    """A C0 fault: the match stops and nothing of it is published."""

    def __init__(self, code: str, detail: str = ""):
        self.code, self.detail = code, detail
        super().__init__(f"C0 {code}: {detail}" if detail else f"C0 {code}")


_cat: dict | None = None
_cat_lock = threading.Lock()


def catalog() -> dict:
    """{code: entry} of config/fallos.yaml (read once)."""
    global _cat
    with _cat_lock:
        if _cat is None:
            import yaml
            data = yaml.safe_load(CATALOG.read_text(encoding="utf-8")) or {}
            _cat = dict(data.get("fallos") or {})
        return _cat


def entry(code: str) -> dict:
    e = catalog().get(code)
    if e is None:
        raise KeyError(f"fallo «{code}» no está en config/fallos.yaml")       # a programming error, never silent
    return e


def level(code: str) -> str:
    return str(entry(code)["nivel"])


class Collector:
    """The faults of one stage (or of one process of it): counts and a few details per code."""

    def __init__(self, log=None):
        self.log = log
        self.counts: dict[str, int] = {}
        self.examples: dict[str, list[str]] = {}
        self._lock = threading.Lock()

    def add(self, code: str, lvl: str, detail: str, n: int = 1):
        with self._lock:
            k = self.counts.get(code, 0)
            self.counts[code] = k + n
            ex = self.examples.setdefault(code, [])
            if detail and len(ex) < EXAMPLES:
                ex.append(detail[:300])
        if self.log is not None and k < LOGGED:
            self.log(f"  FALLO {lvl} {code}: {detail}" if detail else f"  FALLO {lvl} {code}")

    def summary(self) -> dict:
        """{code: {"nivel", "n", "ejemplos"}} (what the manifest keeps)."""
        with self._lock:
            return {c: {"nivel": level(c), "n": n, "ejemplos": list(self.examples.get(c, []))}
                    for c, n in sorted(self.counts.items())}

    def merge(self, summary: dict | None):
        """Adds the summary of another collector (a process of the fine pass)."""
        for c, v in (summary or {}).items():
            with self._lock:
                self.counts[c] = self.counts.get(c, 0) + int(v.get("n", 0))
                ex = self.examples.setdefault(c, [])
                ex += [d for d in v.get("ejemplos", []) if len(ex) < EXAMPLES]

    def worst(self) -> str | None:
        lv = [level(c) for c in self.counts]
        return min(lv) if lv else None


_local = threading.local()
_open: list[Collector] = []      # collectors open in this process: a helper thread of a stage reports to the latest
_open_lock = threading.Lock()
_orphan = Collector()            # faults outside any stage (command line, application): counted, never lost


def active() -> Collector:
    st = getattr(_local, "stack", None)
    if st:
        return st[-1]
    with _open_lock:
        return _open[-1] if _open else _orphan


@contextmanager
def collecting(log=None):
    """The collector of the faults raised while the block runs (in this thread and in the helper threads it starts)."""
    col = Collector(log)
    st = getattr(_local, "stack", None)
    if st is None:
        st = _local.stack = []
    st.append(col)
    with _open_lock:
        _open.append(col)
    try:
        yield col
    finally:
        st.pop()
        with _open_lock:
            _open.remove(col)


def fault(code: str, detail: str = "", exc: BaseException | None = None) -> None:
    """Records the fault in the stage's collector and reacts as its level says: C0 raises CriticalFault (from exc),
    the others return. An unknown code is a KeyError (tests/test_faults.py also checks every code in the code)."""
    lvl = level(code)
    if exc is not None and not detail:
        detail = f"{type(exc).__name__}: {exc}"
    elif exc is not None:
        detail = f"{detail} ({type(exc).__name__}: {str(exc)[:200]})"
    active().add(code, lvl, detail)
    if lvl == "C0":
        raise CriticalFault(code, detail) from exc


def check_budget(code: str, failed: int, total: int, what: str = "") -> None:
    """A C2 code's budget: more than `presupuesto` (share) of the units failed → its `escala_a` (a C0 code) is raised."""
    e = entry(code)
    b = e.get("presupuesto")
    if not total or b is None or failed / total <= float(b):
        return
    fault(str(e.get("escala_a") or "presupuesto.superado"),
          f"{code}: {failed} de {total} {what or 'unidades'} ({failed / total:.1%}; presupuesto {float(b):.0%})")


def check_stage_budgets(col: Collector, summary: dict) -> None:
    """At the end of a stage: each C2 code of `col` whose catalogue entry names `total_en` (the key of the stage's
    summary with its number of units) is held to its budget."""
    for code, n in list(col.counts.items()):
        e = entry(code)
        key = e.get("total_en")
        if e.get("presupuesto") is None or not key:
            continue
        total = (summary or {}).get(key)
        if isinstance(total, (int, float)) and total > 0:
            check_budget(code, n, int(total), key)


def retry(fn, code: str, attempts: int | None = None, wait_s: float | None = None):
    """A C3 code: fn() up to `intentos` times (waits doubling from `espera_s`); each failure recorded; exhausted, the
    code's `escala_a` is raised (C0) or recorded (C1) and the last exception is re-raised. A CriticalFault inside is
    never retried."""
    e = entry(code)
    n = int(attempts or e.get("intentos", 3))
    w = float(wait_s if wait_s is not None else e.get("espera_s", 1.0))
    last: BaseException | None = None
    for i in range(n):
        try:
            return fn()
        except CriticalFault:
            raise
        except Exception as ex:  # noqa: BLE001 — recorded as the C3 fault it is, then retried or escalated
            last = ex
            fault(code, f"intento {i + 1} de {n}", exc=ex)
            if i + 1 < n and w > 0:
                time.sleep(w * (2 ** i))
    fault(str(e.get("escala_a") or "reintentos.agotados"), f"{code} tras {n} intentos", exc=last)
    raise last  # type: ignore[misc]  (escala_a of level C1: the caller decides how to go on)


def worst_level(summaries: list[dict]) -> str | None:
    """The most critical level in some summaries ({code: {"nivel"…}})."""
    lv = [v.get("nivel") for s in summaries for v in (s or {}).values() if v.get("nivel") in LEVELS]
    return min(lv) if lv else None
