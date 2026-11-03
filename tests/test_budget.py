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


def test_without_a_budget_the_median_of_past_runs_here_is_the_budget(tmp_path):
    for s in (1.0, 1.2, 0.8):
        B.record_unit(tmp_path, "fine", s, 200, "m")
    assert B.budget_per_unit({}, tmp_path, "fine")[0] == 1.0
    assert B.check({}, tmp_path, "fine", 300, 200, 400) is None        # 1.5 s per stroke: within 2×
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
    assert "| x | fine | por rehacer | 25 min | medido en partido entero |" in md
    assert "| x | identity | por rehacer | 11 min | **sin medir en partido entero** |" in md
    assert "court" in md and "sin medir aquí" in md and "views" not in md.split("| x |")[-1]
    assert "Etapas sin medir en un partido entero: court, identity" in md
    assert abs(total - (1500 + 685.7)) < 1
