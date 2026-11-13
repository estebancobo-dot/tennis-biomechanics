"""Faults by criticality (#265, approved by the user on 13-11): the catalogue (config/fallos.yaml), the reaction of
every level, the stage collector, the data contracts, the acceptance gate, and the test that walks the code so that no
caught error is left unclassified («es esperpéntico que en algo tan importante te comas el error y no pase nada»)."""
import ast
import json
import re
from pathlib import Path

import pytest

from tennisbio import faults as F
from tennisbio import pipeline
from tennisbio.catalog import Match, Player

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "tennisbio"
MARK = re.compile(r"#\s*(esperado|fallo):\s*\S")
CALLS = ("fault", "check_budget", "retry", "check_stage_budgets")
# R24 (13-11): every handler is classified; a new one must be too
MAX_UNCLASSIFIED = 0


def _handlers():
    for f in sorted(SRC.rglob("*.py")):
        src = f.read_text(encoding="utf-8")
        lines = src.splitlines()
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, ast.ExceptHandler):
                yield f, n, lines


def _classified(n: ast.ExceptHandler, lines: list[str]) -> bool:
    if MARK.search(lines[n.lineno - 1]):
        return True
    for x in ast.walk(n):
        if isinstance(x, ast.Raise):
            return True
        if isinstance(x, ast.Call):
            name = x.func.attr if isinstance(x.func, ast.Attribute) else getattr(x.func, "id", "")
            if name in CALLS:
                return True
    return False


def test_no_caught_error_is_left_unclassified():
    """Every except re-raises, calls fault() (or a budget/retry of the catalogue), or says on its line why its
    exception is an expected outcome (`# esperado: …`) or which fault a helper it calls raises (`# fallo: …`)."""
    bad = [f"{f.relative_to(ROOT)}:{n.lineno}" for f, n, lines in _handlers() if not _classified(n, lines)]
    assert len(bad) <= MAX_UNCLASSIFIED, f"{len(bad)} sin clasificar (máximo {MAX_UNCLASSIFIED}): {bad[:40]}"


def _codes_in_code() -> set[str]:
    used = set()
    for f in sorted(SRC.rglob("*.py")):
        src = f.read_text(encoding="utf-8")
        for n in ast.walk(ast.parse(src)):
            if not isinstance(n, ast.Call):
                continue
            name = n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
            args = n.args
            if name in ("fault", "check_budget") and args and isinstance(args[0], ast.Constant):
                used.add(args[0].value)
            if name == "retry" and len(args) > 1 and isinstance(args[1], ast.Constant):
                used.add(args[1].value)
        for m in re.finditer(r"#\s*fallo:\s*([a-z0-9_.]+)(?:\s+or\s+([a-z0-9_.]+))?", src):
            used.update(c for c in m.groups() if c)
    return used


def test_the_catalogue_and_the_code_agree():
    cat = F.catalog()
    used = _codes_in_code()
    assert not (used - set(cat)), f"códigos usados que no están en config/fallos.yaml: {sorted(used - set(cat))}"
    targets = {e["escala_a"] for e in cat.values() if e.get("escala_a")} | {"presupuesto.superado", "reintentos.agotados"}
    unused = set(cat) - used - targets
    assert not unused, f"entradas del catálogo que ningún código lanza: {sorted(unused)}"
    tests = {p.name: p.read_text(encoding="utf-8") for p in (ROOT / "tests").glob("test_*.py")}
    for code, e in cat.items():
        assert e.get("nivel") in F.LEVELS, code
        for k in ("donde", "efecto", "deteccion", "reaccion", "prueba"):
            assert e.get(k), f"{code}: falta «{k}»"
        fn, _, name = str(e["prueba"]).partition("::")
        assert f"def {name}(" in tests.get(Path(fn).name, ""), f"{code}: su prueba {e['prueba']} no existe"
        if e.get("presupuesto") is not None:
            assert e["nivel"] == "C2", code
        if e.get("escala_a"):
            assert cat[e["escala_a"]]["nivel"] in ("C0", "C1"), code


@pytest.mark.parametrize("code", sorted(F.catalog()))
def test_every_catalogued_fault_reacts_as_its_level(code):
    """Injection of every mode: C0 raises (the match stops, with its code); the others are recorded with their level
    and the work goes on."""
    lvl = F.level(code)
    with F.collecting() as col:
        if lvl == "C0":
            with pytest.raises(F.CriticalFault) as ei:
                F.fault(code, "inyectado")
            assert ei.value.code == code and str(ei.value).startswith(f"C0 {code}")
        else:
            assert F.fault(code, "inyectado") is None
    s = col.summary()
    assert s[code]["nivel"] == lvl and s[code]["n"] == 1 and s[code]["ejemplos"] == ["inyectado"]


def test_an_unknown_code_is_an_error_not_silence():
    with pytest.raises(KeyError, match="no está en config/fallos.yaml"):
        F.fault("no.existe")


def test_a_window_budget_over_its_share_stops_the_match():
    with F.collecting():
        F.check_budget("ventana.fallida", 2, 100, "golpes candidatos")              # 2 %: within
        with pytest.raises(F.CriticalFault) as ei:
            F.check_budget("ventana.fallida", 3, 100, "golpes candidatos")          # 3 %: over
    assert ei.value.code == "ventanas.demasiadas" and "3 de 100" in ei.value.detail


def test_a_stage_budget_from_its_summary_escalates():
    with F.collecting() as col:
        for _ in range(10):
            F.fault("golpe.medida", "x")
        F.check_stage_budgets(col, {"confirmed": 100})                               # 10 %: within
        assert "golpes.medidas_fallidas" not in col.counts
        F.fault("golpe.medida", "x")
        F.check_stage_budgets(col, {"confirmed": 100})                               # 11 %: a C1
    assert col.summary()["golpes.medidas_fallidas"]["nivel"] == "C1"


def test_a_transient_fault_is_retried_and_then_escalated():
    tries = []

    def flaky():
        tries.append(1)
        if len(tries) < 3:
            raise OSError("bloqueado")
        return "ok"
    with F.collecting() as col:
        assert F.retry(flaky, "gpu.perdida", attempts=3, wait_s=0) == "ok"
    assert col.counts == {"gpu.perdida": 2}

    def never():
        raise OSError("sigue bloqueado")
    with F.collecting():
        with pytest.raises(F.CriticalFault) as ei:
            F.retry(never, "gpu.perdida", attempts=2, wait_s=0)
    assert ei.value.code == "reintentos.agotados"


def test_a_critical_fault_is_never_retried():
    def crit():
        F.fault("bola.vacia", "x")
    with F.collecting() as col:
        with pytest.raises(F.CriticalFault):
            F.retry(crit, "gpu.perdida", attempts=3, wait_s=0)
    assert "gpu.perdida" not in col.counts


def test_a_helper_thread_reports_to_the_stage_that_runs():
    import threading
    with F.collecting() as col:
        t = threading.Thread(target=lambda: F.fault("cache.danada", "en un hilo"))
        t.start()
        t.join()
    assert col.counts == {"cache.danada": 1}


def test_a_process_summary_merges_into_the_stage():
    a, b = F.Collector(), F.Collector()
    b.add("golpe.medida", "C2", "en un proceso", 2)
    a.add("golpe.medida", "C2", "aquí")
    a.merge(b.summary())
    assert a.counts == {"golpe.medida": 3} and a.examples["golpe.medida"] == ["aquí", "en un proceso"]


# ------------------------------------------------------------------ the pipeline: collector, contracts, fallos.json

@pytest.fixture
def stages(monkeypatch):
    reg = {}
    monkeypatch.setattr(pipeline, "STAGES", reg)
    return reg


def _ctx(tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"0" * 10)
    return pipeline.Context(Match("m1", video, Player("p", "P")), {}, tmp_path / "out", log=lambda *_: None)


def test_the_faults_of_a_stage_go_to_its_manifest(tmp_path, stages):
    @pipeline.stage("a", "1", outputs=("a.json",))
    def a(ctx):
        F.fault("cache.danada", "una")
        F.fault("modelo.transnet", "histogramas")
        ctx.path("a.json").write_text("{}")
    pipeline.run(_ctx(tmp_path))
    m = json.loads((tmp_path / "out" / "manifest.json").read_text(encoding="utf-8"))
    assert m["a"]["faults"]["modelo.transnet"]["nivel"] == "C1" and m["a"]["faults"]["cache.danada"]["n"] == 1


def test_a_stage_that_leaves_no_output_stops_the_match(tmp_path, stages):
    @pipeline.stage("a", "1", outputs=("a.json",))
    def a(ctx):
        return {"n": 1}                          # forgets its output

    @pipeline.stage("b", "1", deps=("a",))
    def b(ctx):
        raise AssertionError("must not run after a C0")
    with pytest.raises(F.CriticalFault) as ei:
        pipeline.run(_ctx(tmp_path))
    assert ei.value.code == "etapa.sin_salida"
    out = tmp_path / "out"
    assert "a" not in json.loads((out / "manifest.json").read_text(encoding="utf-8") if (out / "manifest.json").exists() else "{}")
    rec = json.loads((out / pipeline.FAULTS_FILE).read_text(encoding="utf-8"))["c0"]
    assert rec[-1]["etapa"] == "a" and rec[-1]["codigo"] == "etapa.sin_salida"


def test_the_fine_pass_stops_without_the_ball_model(tmp_path):
    from tennisbio import stages as S
    ctx = pipeline.Context(Match("m1", tmp_path / "v.mp4", Player("p", "P")), {"ball": {"onnx": str(tmp_path / "no.onnx")}},
                           tmp_path / "out", log=lambda *_: None)
    with pytest.raises(F.CriticalFault) as ei:
        S._ball_tracker(ctx)
    assert ei.value.code == "modelo.bola_falta"


# ------------------------------------------------------------------ the gate of the audit

def test_the_gate_refuses_a_pending_c0_and_any_c1():
    from tennisbio.audit import faults_item
    man = {"a": {"fingerprint": "x", "finished": "2026-11-13 10:00:00", "faults": {}},
           "b": {"fingerprint": "y", "finished": "2026-11-13 10:05:00",
                 "faults": {"cache.danada": {"nivel": "C4", "n": 2, "ejemplos": []}}}}
    assert faults_item("m", man, [])["status"] == "ok"
    c0 = [{"etapa": "c", "codigo": "bola.vacia", "detalle": "0 de 30 min", "hora": "2026-11-13 11:00:00"}]
    it = faults_item("m", man, c0)
    assert it["status"] == "falta" and "bola.vacia" in it["detail"]
    man["c"] = {"fingerprint": "z", "finished": "2026-11-13 12:00:00", "faults": {}}      # done again since: resolved
    assert faults_item("m", man, c0)["status"] == "ok"
    man["b"]["faults"]["modelo.transnet"] = {"nivel": "C1", "n": 1, "ejemplos": []}
    it = faults_item("m", man, c0)
    assert it["status"] == "falta" and "C1: modelo.transnet (b) ×1" in it["detail"]
    del man["b"]["faults"]
    assert faults_item("m", man, [])["status"] == "aviso"                 # a stage done before #265 existed


def test_a_missing_input_of_a_stage_stops_it(tmp_path):
    """R18/#265: the output of a stage these depend on, missing or damaged, is C0, never an empty default (the views
    of no strokes looked like a match without replays)."""
    from tennisbio import view_stages as V
    with pytest.raises(F.CriticalFault) as ei:
        V._read(tmp_path / "strokes.json", [])
    assert ei.value.code == "entrada.ilegible"
    (tmp_path / "strokes.json").write_text("{dañado", encoding="utf-8")
    with pytest.raises(F.CriticalFault):
        V._read(tmp_path / "strokes.json", [])
    (tmp_path / "strokes.json").write_text("[]", encoding="utf-8")
    assert V._read(tmp_path / "strokes.json", None) == []


def test_an_audit_check_without_its_data_is_not_met(tmp_path):
    """#265: a check that cannot read its data is never silent: a C1 of the audit, and its item «Fallos por niveles:
    auditoría» is ✘ in that same audit."""
    from tennisbio import cli
    m = tmp_path / "m1"
    m.mkdir()
    (m / "manifest.json").write_text("{}", encoding="utf-8")
    (tmp_path / "ritmos.json").write_text("{dañado", encoding="utf-8")       # the PC's rates, damaged
    assert cli.run_audit(tmp_path, tmp_path / "informe", tmp_path / "auditoria", dirs=[m]) == 0
    res = json.loads((tmp_path / "auditoria" / "auditoria.json").read_text(encoding="utf-8"))
    it = next(i for i in res["items"] if i["name"] == "Fallos por niveles: auditoría")
    assert it["status"] == "falta" and "auditoria.dato_ilegible" in it["detail"]
