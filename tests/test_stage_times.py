import json

from tennisbio.audit import SCRATCH_TIME_ITEM, audit, scratch_time_item
from tennisbio.stage_times import all_tables, latest_from_scratch, not_real, stage_real

FRESH = {"probe": {"seconds": 1, "summary": {"duration_min": 35}},
         "scenes": {"seconds": 300, "finished": "2026-11-11 19:40:07"},
         "players": {"seconds": 458, "finished": "2026-11-11 19:49:16"},
         "spotting": {"seconds": 783, "summary": {"seconds": {"bola": 775.0}}, "finished": "2026-11-11 20:03:23"},
         "fine": {"seconds": 2013, "summary": {"seconds": {"pose": 2068.0}}, "finished": "2026-11-11 20:37:57"}}
# the same match re-read from its caches (11-11, «_smoke»): the fine pass took 113 s, its pose 29 s; no ball computed
CACHED = {**FRESH, "fine": {"seconds": 113, "summary": {"seconds": {"pose": 29.0}}, "finished": "2026-11-11 16:31:23"},
          "spotting": {"seconds": 9, "summary": {"seconds": {"bola": 0.0}}, "finished": "2026-11-11 16:20:00"}}


def test_a_stage_that_only_re_read_its_caches_is_not_a_time():
    assert not_real(FRESH) == []
    assert not_real(CACHED) == ["spotting", "fine"]
    big = {"seconds": 11251, "summary": {"seconds": {"bola_en_paralelo_cpu": 7510.0, "pose": 5530.0}}}
    assert stage_real("fine", big, 210)                 # the whole final: its pose half of it, the ball in parallel


def _dir(tmp_path, name, man):
    d = tmp_path / name
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps(man), encoding="utf-8")
    (d / "strokes.json").write_text("[]", encoding="utf-8")
    return d


def test_the_time_of_a_cached_run_is_information_not_a_pass(tmp_path):
    items = audit([_dir(tmp_path, "cached", CACHED)], None)["items"]
    t = next(i for i in items if i["name"].startswith("Tiempo:"))
    assert t["area"] == "Rendimiento (información)" and t["status"] == "pocos datos" and "no es desde cero" in t["detail"]
    items = audit([_dir(tmp_path, "fresh", FRESH)], None)["items"]
    t = next(i for i in items if i["name"].startswith("Tiempo:"))
    assert t["area"] == "Rendimiento" and t["status"] == "ok"           # 76 min for 35: 7.6 h ≤ 8 h


def test_the_scratch_time_takes_the_last_run_from_scratch_and_can_fail(tmp_path):
    _dir(tmp_path / "out", "_app_nuevo/output/prueba", FRESH)
    _dir(tmp_path / "out", "smoke", CACHED)
    tabs = all_tables([tmp_path / "out"])
    t = latest_from_scratch(tabs)
    assert t is not None and t["carpeta"].endswith("prueba")
    it = scratch_time_item(tabs, today="2026-11-12")
    assert it["name"] == SCRATCH_TIME_ITEM and it["status"] == "ok" and "prueba" in it["detail"]
    assert scratch_time_item(tabs, today="2026-12-12")["status"] == "aviso"          # a month old: other code
    slow = {**FRESH, "fine": {"seconds": 6000, "summary": {"seconds": {"pose": 5000.0}}, "finished": "2026-11-11 22:00:00"}}
    _dir(tmp_path / "out", "_poc9_35/m", slow)
    assert scratch_time_item(all_tables([tmp_path / "out"]), today="2026-11-12")["status"] == "aviso"   # > 8 h
    assert scratch_time_item(all_tables([tmp_path / "nada"]))["status"] == "pocos datos"
