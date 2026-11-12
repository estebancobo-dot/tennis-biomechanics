"""Stage time budgets, alarms and the forecast (tennisbio.budget, 03-11)."""
import json

from tennisbio import budget as B
from tennisbio.pipeline import Context


def test_identity_like_slowness_raises_an_alarm_once_warmed_up(tmp_path):
    cfg = {"budgets": {"identity": 0.75, "factor": 2.0}}
    assert B.check(cfg, tmp_path, "identity", 60, 50, 1600) is None          # not warmed up (time)
    assert B.check(cfg, tmp_path, "identity", 300, 50, 1600) is None         # not warmed up (5 %)
    assert B.check(cfg, tmp_path, "identity", 300, 400, 1600) is None        # 0.75 s per frame: within
    al = B.check(cfg, tmp_path, "identity", 290, 100, 1600)                  # 2.9 s per frame (request 84)
    assert al and "identity" in al and "3.9 veces" in al


def test_without_a_budget_the_slowest_past_run_here_is_the_budget(tmp_path):
    for s in (1.0, 1.2, 0.8):
        B.record_unit(tmp_path, "fine", s, 200, "m")
    assert B.budget_per_unit({}, tmp_path, "fine")[0] == 1.2           # the slowest run here
    assert B.check({}, tmp_path, "fine", 400, 200, 400) is None        # 2 s per stroke: within 2 × 1.2
    assert B.check({}, tmp_path, "fine", 600, 200, 400)                # 3 s: alarm


def test_progress_writes_the_alarm_file_and_never_twice(tmp_path):
    class M:
        id = "m1"
    ctx = Context(M(), {"budgets": {"identity": 0.1}, "paths": {}}, tmp_path / "m1", log=lambda *_: None)
    (tmp_path / "m1").mkdir()
    ctx._prog["stage"] = "identity"
    import time
    ctx.progress(0, 100)
    ctx._prog["t0"] = time.time() - 400
    ctx._prog["last"] = 0
    ctx.progress(20, 100)
    ctx._prog["last"] = 0
    ctx.progress(30, 100)
    al = json.loads((tmp_path / B.ALARMS).read_text(encoding="utf-8"))["alarmas"]
    assert len(al) == 1 and al[0]["etapa"] == "identity" and al[0]["partido"] == "m1"


def test_forecast_flags_stages_never_measured_on_a_whole_match(tmp_path):
    B.record_stage(tmp_path, "fine", 1800, 120, "a")          # 15 s per minute on a whole match
    B.record_stage(tmp_path, "identity", 240, 35, "clip")     # only a 35-min clip
    B.record_stage(tmp_path, "views", 5, 120, "c")            # 5 s: read its caches, not a rate
    md, total = B.forecast([{"match": "x", "video_min": 100, "seconds": {"identity": 4},
                             "stages": {"fine": "stale", "identity": "stale", "views": "ok", "court": "missing"}}],
                           tmp_path)
    assert "| x | fine | por rehacer | 25 min | medido en partido entero |" in md          # one rate: no range
    assert "| x | identity | por rehacer | 11 min | **sin medir en partido entero** |" in md
    assert "court" in md and "sin medir aquí" in md and "views" not in md.split("| x |")[-1]
    assert "Etapas sin medir en un partido entero: court, identity" in md
    assert abs(total - (1500 + 685.7)) < 1


def test_forecast_gives_a_range_from_caches_to_computing_everything(tmp_path):
    B.record_stage(tmp_path, "fine", 300, 120, "cached")      # 2.5 s per minute: from its caches
    B.record_stage(tmp_path, "fine", 3600, 120, "fresh")      # 30 s per minute: everything computed
    md, total = B.forecast([{"match": "x", "video_min": 120, "seconds": {}, "stages": {"fine": "stale"}}], tmp_path)
    assert "| x | fine | por rehacer | 5-60 min |" in md and "desde las cachés - calculando todo" in md


def test_forecast_keeps_its_worst_case_for_the_guard(tmp_path):
    B.record_stage(tmp_path, "fine", 300, 120, "cached")
    B.record_stage(tmp_path, "fine", 3600, 120, "fresh")
    B.forecast([{"match": "x", "video_min": 120, "seconds": {}, "stages": {"fine": "stale"}}], tmp_path)
    assert abs(B.forecast.last_upper - 3600) < 1


def test_preflight_refuses_a_run_whose_worst_case_passes_the_limit(tmp_path, monkeypatch, capsys):
    """Request #77 (no 6-hour runs to validate): scripts/preflight.py --max-h exits 3 when the forecast's worst case
    is above the limit (ciclo_automatico.ps1 then does not start «completo»), 0 otherwise; prevision.md always written."""
    import importlib.util
    import sys
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("preflight", Path(__file__).resolve().parents[1] / "scripts" / "preflight.py")
    pf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pf)
    B.record_stage(tmp_path, "fine", 300, 120, "cached")
    B.record_stage(tmp_path, "fine", 3600 * 8, 120, "fresh")          # computing everything: 8 h
    monkeypatch.setattr(pf, "load_config", lambda: {"paths": {"output": str(tmp_path)}})
    monkeypatch.setattr(pf, "rows", lambda cfg, only=None: [{"match": "x", "video_min": 120, "seconds": {},
                                                              "stages": {"fine": "stale"}}])
    monkeypatch.setattr(sys, "argv", ["preflight.py", "--max-h", "6"])
    assert pf.main() == 3 and "NO SE LANZA" in capsys.readouterr().out
    assert (tmp_path / "prevision.md").exists()
    monkeypatch.setattr(sys, "argv", ["preflight.py", "--max-h", "9"])
    assert pf.main() == 0 and "NO SE LANZA" not in capsys.readouterr().out


def test_a_rate_of_another_version_of_the_stage_is_not_a_measure_of_it(tmp_path):
    """12-11 (R17): the spotter was timed without the ball of the match (1.4 s per minute of video); with it the ball
    model runs over all the play. The rate of spotting v1 must not stand for v2: flagged and measured first."""
    B.record_stage(tmp_path, "spotting", 100, 71.4, "osaka", "1")              # without the ball
    row = [{"match": "x", "video_min": 100, "seconds": {}, "stages": {"spotting": "stale"}}]
    md, _ = B.forecast(row, tmp_path)
    ver = B.stage_version("spotting")
    assert ver != "1"
    assert f"**medido con otra versión** (ahora v{ver})" in md and "spotting → se miden antes" in md
    B.record_stage(tmp_path, "spotting", 3600, 71.4, "osaka", ver)             # with the ball: ~50 s per minute
    md, total = B.forecast(row, tmp_path)
    assert "medido en partido entero" in md and "otra versión" not in md
    assert abs(total - 3600 / 71.4 * 100) < 1                                  # only the current version's rate


def test_rates_written_before_versions_count_until_a_versioned_one_exists(tmp_path):
    B.record_stage(tmp_path, "fine", 1800, 120, "a")                           # before 12-11: no version
    assert B.per_minute(tmp_path, "fine", B.stage_version("fine"))[0] == 15.0
    B.record_stage(tmp_path, "fine", 3600, 120, "b", B.stage_version("fine"))
    assert B.per_minute(tmp_path, "fine", B.stage_version("fine")) == (30.0, True, 30.0)


def test_the_pipeline_records_the_version_with_the_rate(tmp_path):
    import json as _j
    B.record_stage(tmp_path, "fine", 600, 100, "m", B.stage_version("fine"))
    B.record_unit(tmp_path, "fine", 2.0, 100, "m", B.stage_version("fine"))
    d = _j.loads((tmp_path / B.RATES).read_text(encoding="utf-8"))
    assert d["fine:minuto"][0]["v"] == d["fine:unidad"][0]["v"] == B.stage_version("fine")
    import ast
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "src" / "tennisbio" / "pipeline.py").read_text(encoding="utf-8")
    calls = [n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr in ("record_stage", "record_unit")]
    assert len(calls) == 2 and all(len(c.args) == 6 for c in calls)            # both pass the stage's version
