"""The local application's core against every case of docs/aplicacion_local.md §5 (nominal, limit,
corner, error), with a fake engine in place of the stages (no video, no models): the core only decides
what runs and what to do when something goes wrong, and that is what is tested here."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tennisbio.app import index, jobs, storage, videos
from tennisbio.app.core import App
from tennisbio.app.db import DB, healthy
from tennisbio.pipeline import DiskFull, MissingVideo

GB = 1e9


class FakeEngine:
    """Does what the stages would do to the folders, and fails on demand."""

    def __init__(self, db, paths):
        self.db, self.paths = db, paths
        self.fail = []                      # exceptions to raise, one per call, in order
        self.calls = []
        self.manifests = {}                 # match id → manifest the «stages» leave
        self.audit_items = [{"name": "La lección", "status": "ok", "detail": ""},
                            {"name": "Primera pantalla", "status": "ok", "detail": ""}]
        self.stale_stages = {}
        self.sizes = {}

    def _maybe_fail(self):
        if self.fail:
            e = self.fail.pop(0)
            if e is not None:
                raise e

    def dir(self, mid):
        return self.paths.output / mid

    def video_size(self, mid):
        return self.sizes.get(mid, int(1 * GB))

    def manifest(self, mid):
        return self.manifests.get(mid, {"candidates": {"summary": {"candidates": 40}},
                                        "identity": {"summary": {"confidence": 0.9}},
                                        "audio": {"summary": {"onsets": 300}}, "court": {"summary": {"with_court": 20}},
                                        "fine": {"summary": {"confirmed": 30}}})

    def run_match(self, mid, player, cfg):
        self.calls.append(("partido", mid, cfg.get("device"), (cfg.get("pipeline") or {}).get("parallel")))
        self._maybe_fail()
        d = self.dir(mid)
        d.mkdir(parents=True, exist_ok=True)
        (d / "manifest.json").write_text(json.dumps(self.manifest(mid)), encoding="utf-8")

    def run_opponent(self, mid, player, cfg):
        self.calls.append(("rival", mid, player))
        self._maybe_fail()
        (self.dir(mid) / "strokes_opponent.json").write_text("[]", encoding="utf-8")

    def build_report(self, player, stroke, dest, cfg):
        self.calls.append(("informe", player, stroke))
        self._maybe_fail()
        (dest / "index.html").write_text("<html></html>", encoding="utf-8")
        return 30

    def audit(self, player, stroke, report, dest, cfg):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "auditoria.json").write_text(json.dumps({"items": self.audit_items}), encoding="utf-8")

    def stale(self, mid, cfg):
        return self.stale_stages.get(mid, [])

    def stale_seconds(self, mid, names):
        return 3600.0 * len(names)


@pytest.fixture
def env(tmp_path, monkeypatch):
    cfgdir = tmp_path / "config"
    (cfgdir / "players").mkdir(parents=True)
    (cfgdir / "players" / "rybakina.yaml").write_text("name: Elena Rybakina\nhand: right\nheight_m: 1.84\n", encoding="utf-8")
    (cfgdir / "players" / "sabalenka.yaml").write_text("name: Aryna Sabalenka\nhand: right\nheight_m: 1.82\n", encoding="utf-8")
    vids = tmp_path / "videos"
    vids.mkdir()
    cfg = {"paths": {"output": str(tmp_path / "output"), "videos": str(vids), "data": str(tmp_path / "datos")}}
    monkeypatch.setattr(storage, "free_bytes", lambda p: 200 * GB)
    probe = SimpleNamespace(duration=2 * 3600, fps=50, interlaced=False, audio_tracks=1, audio_rate=48000)
    monkeypatch.setattr(videos, "_probe", lambda p: probe)
    monkeypatch.setattr(videos.propose, "__defaults__", (lambda p: probe,))

    def make(name="2023_Australian_Open_F_Sabalenka_Rybakina.mp4", content=b"a"):
        f = vids / name
        f.write_bytes(content * 4096 + name.encode())
        return f

    def app():
        return App(cfg, engine_factory=FakeEngine, config_dir=cfgdir)

    return SimpleNamespace(cfg=cfg, cfgdir=cfgdir, vids=vids, make=make, app=app, probe=probe, tmp=tmp_path)


def _added(env, a, name="2023_Australian_Open_F_Sabalenka_Rybakina.mp4", content=b"a", **kw):
    prop, mid = a.add(env.make(name, content), player="rybakina", **kw)
    return prop, mid


# ---------------------------------------------------------------- 5.1 nominal ------------------------

def test_add_match_proposes_its_data_and_queues_its_work(env):
    a = env.app()
    prop, mid = _added(env, a)
    assert prop.tournament == "Australian Open" and prop.year == "2023" and prop.surface == "dura"
    assert set(prop.players) == {"sabalenka", "rybakina"} and not prop.flags
    m = a.db.one("SELECT * FROM matches WHERE id=?", mid)
    assert m["player"] == "rybakina" and m["opponent_id"] == "sabalenka" and m["opponent"] == "Aryna Sabalenka"
    assert [j["kind"] for j in a.db.q("SELECT kind FROM jobs")] == ["partido"]


def test_end_of_a_match_feeds_its_analysis_audited_and_published(env):
    a = env.app()
    _, mid = _added(env, a)
    ran = a.work()
    assert [s for _, s in ran] == ["hecho", "hecho"]                          # the match, then its analysis
    an = a.db.one("SELECT * FROM analyses WHERE id='rybakina_forehand'")
    assert an["version"] == 1 and an["state"] == "al día" and an["n_strokes"] == 30
    base = a.paths.analyses / "rybakina_forehand"
    assert (base / "actual" / "index.html").exists() and (base / "actual" / "revision.md").exists()
    assert json.loads((base / "analisis.json").read_text(encoding="utf-8"))["version"] == 1
    assert any("actualizada: 2 ✔, 0 ✘" in n["text"] for n in a.db.q("SELECT text FROM notices"))
    assert a.db.one("SELECT state FROM matches WHERE id=?", mid)["state"] == "analizado"


def test_analyse_the_rival_reuses_the_cheap_pass(env):
    a = env.app()
    _, mid = _added(env, a)
    a.work()
    msg = a.analyze_also("sabalenka")
    assert "pasada fina en 1 partido" in msg
    kinds = [(j["kind"], j["player"]) for j in a.db.q("SELECT * FROM jobs WHERE state='pendiente' ORDER BY priority, id")]
    assert kinds == [("informe", "sabalenka"), ("rival", "sabalenka")]
    a.work()
    assert ("rival", mid, "sabalenka") in a.engine.calls
    assert a.db.one("SELECT * FROM analyses WHERE id='sabalenka_forehand'")


def test_another_stroke_is_only_a_report(env):
    a = env.app()
    _added(env, a)
    a.work()
    assert "solo su informe" in a.analyze_also("rybakina", "backhand")
    a.work()
    assert a.db.one("SELECT version FROM analyses WHERE id='rybakina_backhand'")["version"] == 1
    assert not [c for c in a.engine.calls[2:] if c[0] == "partido"]


def test_new_version_plans_the_recomputation_with_its_cost(env):
    a = env.app()
    _, mid = _added(env, a)
    a.work()
    a.engine.stale_stages = {mid: ["fine"]}
    r = a.plan_updates()
    assert r["matches"] == 1 and not r["confirm"] and r["reports"] == 1      # first plan also stores the web's code
    j = a.db.one("SELECT * FROM jobs WHERE kind='partido' AND state='pendiente'")
    assert "nueva versión: cambió fine" in j["reason"]
    assert "recalcula 1 partido(s) ≈ 1 h 00 min" in a.db.one("SELECT text FROM notices WHERE key='plan'")["text"]


def test_long_plan_waits_for_one_click(env):
    a = env.app()
    _, mid = _added(env, a)
    a.work()
    a.engine.stale_stages = {mid: ["players", "identity", "candidates", "court", "score", "scenes", "fine"]}
    r = a.plan_updates()
    assert r["confirm"] and a.db.one("SELECT state FROM jobs WHERE kind='partido' AND state='por confirmar'")
    assert jobs.next_job(a.db)["kind"] == "informe"                          # the report may run, the long plan waits
    assert a.confirm_plan() == 1 and a.db.one("SELECT state FROM jobs WHERE kind='partido' AND state='pendiente'")


# ---------------------------------------------------------------- 5.2 limit --------------------------

def test_low_disk_notice_and_automatic_freeing(env, monkeypatch):
    a = env.app()
    out = a.paths.output
    (out / "m1").mkdir(parents=True)
    tmpf = out / "m1" / "x.npz.tmp"
    tmpf.write_bytes(b"0" * 100)
    monkeypatch.setattr(storage, "free_bytes", lambda p: 30 * GB)
    assert storage.guard(a.db, out) == "aviso" and tmpf.exists()
    assert "Por debajo de 40 GB" in a.db.one("SELECT text FROM notices WHERE key='disk_low'")["text"]
    monkeypatch.setattr(storage, "free_bytes", lambda p: 10 * GB)
    assert storage.guard(a.db, out) == "liberado" and not tmpf.exists()


def test_a_match_that_does_not_fit_waits_and_starts_when_there_is_room(env, monkeypatch):
    a = env.app()
    _, mid = _added(env, a)
    a.engine.sizes[mid] = int(5 * GB)
    monkeypatch.setattr(storage, "free_bytes", lambda p: 10 * GB)               # needs 5 × 1.1 + 6 = 11.5 GB
    assert a.work() == [(1, "esperando espacio")]
    assert "No cabe" in a.db.one("SELECT message FROM jobs WHERE id=1")["message"]
    monkeypatch.setattr(storage, "free_bytes", lambda p: 100 * GB)
    assert a.work()[0] == (1, "hecho")


def test_short_and_long_videos_are_accepted_with_their_question(env):
    a = env.app()
    env.probe.duration = 12 * 60
    prop, mid = _added(env, a, "2023_Miami_resumen_Rybakina.mp4")
    assert "¿Es un resumen?" in prop.flags["corto"] and mid
    env.probe.duration = 5 * 3600
    prop, mid = _added(env, a, "2024_Wimbledon_F_Rybakina.mp4", b"b")
    assert "se acepta" in prop.flags["largo"] and mid


def test_player_without_height_uses_180_and_says_so(env):
    a = env.app()
    pid = index.add_player(a.db, "Jelena Ostapenko", config_dir=env.cfgdir)
    p = index.player(a.db, pid)
    assert p.height_m == 1.80
    assert "uso 1,80 m (±5 %)" in a.db.one("SELECT text FROM notices WHERE key=?", f"height_{pid}")["text"]
    assert (env.cfgdir / "players" / f"{pid}.yaml").exists()


def test_left_handed_player_reaches_the_stages(env):
    from tennisbio.app.engine import Engine
    a = env.app()
    pid = index.add_player(a.db, "Leylah Fernandez", hand="left", height_m=1.68, config_dir=env.cfgdir)
    prop, mid = a.add(env.make("2023_US_Open_Fernandez.mp4", b"c"), player=pid)
    m = Engine(a.db, a.paths).match(mid)
    assert m.player.hand == "left" and m.player.height_m == 1.68


def test_interrupted_job_resumes_after_the_pc_was_off(env):
    a = env.app()
    _added(env, a)
    a.db.x("UPDATE jobs SET state='en curso', pid=999999999 WHERE id=1")
    assert jobs.recover(a.db) == 1
    j = a.db.one("SELECT * FROM jobs WHERE id=1")
    assert j["state"] == "pendiente" and j["message"] == "reanudado tras un corte"


def test_reports_go_before_heavy_jobs_and_the_band_holds_heavy_ones(env):
    import time
    a = env.app()
    _added(env, a)
    jobs.enqueue(a.db, "informe", player="rybakina", stroke="forehand", reason="x")
    assert jobs.next_job(a.db)["kind"] == "informe"
    a.db.set_setting("franja", ["22:00", "08:00"])
    noon = time.struct_time((2026, 10, 18, 12, 0, 0, 6, 291, 0))
    night = time.struct_time((2026, 10, 18, 23, 0, 0, 6, 291, 0))
    a.db.x("UPDATE jobs SET state='hecho' WHERE kind='informe'")
    assert jobs.next_job(a.db, noon) is None and jobs.next_job(a.db, night)["kind"] == "partido"


# ---------------------------------------------------------------- 5.3 corner -------------------------

def test_same_video_twice_moved_or_copied_is_recognised(env):
    a = env.app()
    f = env.make()
    a.add(f, player="rybakina")
    copy = env.tmp / "otra_carpeta" / "copia.mp4"
    copy.parent.mkdir()
    copy.write_bytes(f.read_bytes())
    prop, mid = a.add(copy, player="rybakina")
    assert mid is None and prop.duplicate_of and "lo reconozco por su contenido" in prop.flags["duplicado"]
    assert a.db.one("SELECT path FROM videos")["path"] == str(copy)
    assert len(a.db.q("SELECT id FROM matches")) == 1 and len(a.db.q("SELECT id FROM jobs")) == 1


def test_same_final_from_another_broadcaster_asks_which(env):
    a = env.app()
    _, first = _added(env, a)
    prop = a.propose(env.make("2023_Australian_Open_final_Rybakina_Sabalenka_ES.mp4", b"z"))
    assert prop.same_match == [first] and "¿Cuál uso?" in prop.flags["otra_cadena"]
    assert videos.confirm(a.db, prop, "rybakina", choose="existente") is None
    new = videos.confirm(a.db, prop, "rybakina", choose="nuevo")
    old = a.db.one("SELECT * FROM matches WHERE id=?", first)
    assert new != first and old["state"] == "archivado" and new in old["note"]
    assert (env.vids / "2023_Australian_Open_F_Sabalenka_Rybakina.mp4").exists()      # never deleted


def test_doubles_match_is_excluded_with_its_reason(env):
    a = env.app()
    _, mid = _added(env, a)
    a.engine.manifests[mid] = {"candidates": {"summary": {"candidates": 0, "doubles": True}}}
    a.work()
    m = a.db.one("SELECT * FROM matches WHERE id=?", mid)
    assert m["state"] == "excluido" and "dobles" in m["note"]
    assert not a.db.q("SELECT id FROM jobs WHERE kind='informe'")


def test_player_not_in_the_video_is_never_replaced_by_someone_else(env):
    a = env.app()
    _, mid = _added(env, a)
    a.engine.manifests[mid] = {"candidates": {"summary": {"candidates": 0}}, "identity": {"summary": {"votes": 0}},
                               "fine": {"summary": {"confirmed": 0}}}
    a.work()
    m = a.db.one("SELECT * FROM matches WHERE id=?", mid)
    assert m["state"] == "sin la jugadora" and "no se analiza a otra persona" in m["note"]
    assert not a.db.q("SELECT id FROM jobs WHERE kind='informe'")


def test_doubtful_identity_is_analysed_and_marked(env):
    a = env.app()
    _, mid = _added(env, a)
    a.engine.manifests[mid] = {"candidates": {"summary": {"candidates": 30}},
                               "identity": {"summary": {"runs": 40, "decided": 20, "conflicts": 1, "confidence": 0.9}},
                               "fine": {"summary": {"confirmed": 20}}}
    a.work()
    m = a.db.one("SELECT * FROM matches WHERE id=?", mid)
    assert m["state"] == "identidad dudosa" and "decidida en el 50 % de los planos" in m["note"]
    assert "no entra en las comparativas" in m["note"]
    assert a.db.one("SELECT version FROM analyses WHERE id='rybakina_forehand'")["version"] == 1


def test_scoreboard_alias_recognises_the_next_video(env):
    a = env.app()
    assert "rybakina" not in videos.find_players(a.db, "2024_Doha_RYBAKINA_E_vs_X")[:0] + videos.find_players(a.db, "2024_Doha_Elenochka")
    index.add_alias(a.db, "rybakina", "Elenochka")
    assert videos.find_players(a.db, "2024_Doha_Elenochka") == ["rybakina"]


def test_transliterated_names_are_recognised(env):
    a = env.app()
    assert videos.find_players(a.db, "tennis-yusipopen-final-sobolenko-rybakin") == ["rybakina"]


# ---------------------------------------------------------------- 5.4 errors -------------------------

def test_damaged_video_is_registered_with_a_notice_and_no_job(env, monkeypatch):
    a = env.app()
    f = env.make("2023_Roma_Rybakina.mp4", b"d")
    def bad(p):
        raise RuntimeError("moov atom not found")
    prop = videos.propose(a.db, f, probe=bad)
    assert "no se puede leer" in prop.flags["danado"]
    mid = videos.confirm(a.db, prop, "rybakina")
    assert a.db.one("SELECT state FROM matches WHERE id=?", mid)["state"] == "con aviso"
    assert not a.db.q("SELECT id FROM jobs")


def test_video_without_audio_is_said(env):
    a = env.app()
    env.probe.audio_tracks, env.probe.audio_rate = 0, None
    prop, mid = _added(env, a)
    assert "no tiene sonido" in prop.flags["sin_audio"] and "sin_audio" not in a.db.one("SELECT note FROM matches")["note"]
    assert a.db.one("SELECT note FROM matches")["note"].startswith("El vídeo no tiene sonido")


def test_igpu_failure_retries_twice_then_the_cpu(env):
    a = env.app()
    _added(env, a)
    gpu = RuntimeError("[ONNXRuntimeError] DmlExecutionProvider: 887A0005 device removed")
    a.engine.fail = [gpu, gpu]
    a.work()
    calls = [c for c in a.engine.calls if c[0] == "partido"]
    assert [c[2] for c in calls] == [None, None, "cpu"]
    assert a.db.one("SELECT state, device FROM jobs WHERE id=1") == {"state": "hecho", "device": "cpu"}
    assert any("sigue en la CPU" in n["text"] for n in a.db.q("SELECT text FROM notices"))


def test_out_of_memory_retries_with_less_at_once_then_errors(env):
    a = env.app()
    _added(env, a)
    a.engine.fail = [MemoryError(), None]
    a.work(max_jobs=2)
    calls = [c for c in a.engine.calls if c[0] == "partido"]
    assert [c[3] for c in calls] == [None, False]                             # second try: no parallel helpers
    assert a.db.one("SELECT state FROM jobs WHERE id=1")["state"] == "hecho"
    a.work()                                                                  # its report too
    _, mid2 = _added(env, a, "2024_Madrid_Rybakina.mp4", b"m")
    a.engine.fail = [MemoryError("std::bad_alloc"), MemoryError("std::bad_alloc")]
    a.work()
    assert a.db.one("SELECT state FROM jobs WHERE match=? AND kind='partido'", mid2)["state"] == "error"


def test_disk_full_half_way_frees_and_resumes_or_waits(env, monkeypatch):
    a = env.app()
    _added(env, a)
    a.engine.fail = [DiskFull("Queda muy poco espacio")]
    monkeypatch.setattr(storage, "free_regenerable", lambda out: 4 * GB)
    a.work()
    assert a.db.one("SELECT state FROM jobs WHERE id=1")["state"] == "hecho"
    _, mid2 = _added(env, a, "2024_Madrid_Rybakina.mp4", b"m")
    a.engine.fail = [DiskFull("Queda muy poco espacio")]
    monkeypatch.setattr(storage, "free_regenerable", lambda out: 0.0)
    free = iter([100 * GB, 100 * GB])                                         # room at the start, full half-way
    monkeypatch.setattr(storage, "free_bytes", lambda p: next(free, 2 * GB))
    a.work()
    j = a.db.one("SELECT * FROM jobs WHERE match=? AND kind='partido'", mid2)
    assert j["state"] == "esperando espacio" and a.db.one("SELECT id FROM notices WHERE key='disk_wait'")


def test_code_exception_errors_with_diagnostic_and_the_rest_goes_on(env):
    a = env.app()
    _added(env, a)
    _, mid2 = _added(env, a, "2024_Madrid_Rybakina.mp4", b"m")
    a.engine.fail = [ValueError("índice fuera de rango")]
    a.work()
    j1 = a.db.one("SELECT * FROM jobs WHERE id=1")
    assert j1["state"] == "error" and Path(j1["diag"]).exists() and "índice fuera de rango" in Path(j1["diag"]).read_text(encoding="utf-8")
    assert a.db.one("SELECT state FROM jobs WHERE match=? AND kind='partido'", mid2)["state"] == "hecho"
    assert any("lo arregla una actualización" in n["text"] for n in a.db.q("SELECT text FROM notices WHERE level='crit'"))


def test_video_gone_or_unusable_is_a_notice_not_an_error(env):
    a = env.app()
    _, mid = _added(env, a)
    a.engine.fail = [MissingVideo("x")]
    a.work(max_jobs=1)
    assert a.db.one("SELECT state FROM jobs WHERE id=1")["state"] == "aviso"
    assert "se conservan sus resultados" in a.db.one("SELECT note FROM matches WHERE id=?", mid)["note"]
    _, mid2 = _added(env, a, "2024_Madrid_Rybakina.mp4", b"m")
    a.engine.fail = [jobs.VideoProblem("sin pista de audio")]
    a.work(max_jobs=1)
    assert a.db.one("SELECT state FROM matches WHERE id=?", mid2)["state"] == "con aviso"


def test_regression_keeps_the_previous_version(env):
    a = env.app()
    _added(env, a)
    a.work()
    a.engine.audit_items = [{"name": "La lección", "status": "falta", "detail": "4 fases sin vídeo"},
                            {"name": "Primera pantalla", "status": "ok", "detail": ""}]
    jobs.enqueue(a.db, "informe", player="rybakina", stroke="forehand", reason="nueva versión del informe")
    a.work()
    an = a.db.one("SELECT * FROM analyses WHERE id='rybakina_forehand'")
    base = a.paths.analyses / "rybakina_forehand"
    assert an["state"] == "pendiente de revisar" and an["version"] == 1 and an["verdict"] == "REGRESIÓN"
    assert (base / "actual" / "index.html").exists() and (base / "pendiente" / "revision.md").exists()
    assert "empeoró" in a.db.one("SELECT text FROM notices WHERE key='regression_rybakina_forehand'")["text"]
    a.engine.audit_items[0]["status"] = "ok"                                  # fixed by an update
    jobs.enqueue(a.db, "informe", player="rybakina", stroke="forehand", reason="arreglo")
    a.work()
    an = a.db.one("SELECT * FROM analyses WHERE id='rybakina_forehand'")
    assert an["version"] == 2 and not (base / "pendiente").exists() and (base / "v1").exists()


def test_damaged_index_is_rebuilt_from_the_folders(env):
    a = env.app()
    _, mid = _added(env, a)
    a.work()
    a.close()
    dbf = Path(env.cfg["paths"]["data"]) / "tennisbio.db"
    dbf.write_bytes(b"esto no es una base de datos" * 100)
    assert not healthy(dbf)
    b = env.app()
    assert b.rebuilt
    assert b.db.one("SELECT state FROM matches WHERE id=?", mid)["state"] == "analizado"
    assert b.db.one("SELECT version FROM analyses WHERE id='rybakina_forehand'")["version"] == 1
    assert list(dbf.parent.glob("tennisbio.danada-*.db"))                      # kept aside, never deleted
    assert "reconstruido" in b.db.one("SELECT text FROM notices WHERE key='db_rebuilt'")["text"]


def test_catalogue_of_today_is_imported(env):
    f = env.make("final.mp4", b"q")
    (env.cfgdir / "matches.yaml").write_text(
        "matches:\n  - id: 2023-ao-f\n    video: final.mp4\n    player: rybakina\n    opponent: Aryna Sabalenka\n"
        "    opponent_id: sabalenka\n    tournament: Australian Open\n    date: 2023-01-28\n", encoding="utf-8")
    a = env.app()
    m = a.db.one("SELECT * FROM matches WHERE id='2023-ao-f'")
    assert m["player"] == "rybakina" and m["opponent_id"] == "sabalenka"
    assert a.db.one("SELECT path FROM videos WHERE sample=?", m["video"])["path"] == str(f)


def test_status_is_readable(env):
    a = env.app()
    _added(env, a)
    a.work()
    s = a.status()
    assert "Análisis:" in s and "rybakina · derecha: v1 · al día · OK · 30 golpes" in s


def test_test_runs_one_level_down_are_indexed_and_reported_from_their_folder(env):
    """The PC's real analyses so far are test runs (<output>/_smoke/<match>, <output>/_poc9_largo/<match>):
    the index sees them (the same video in two runs stays two matches), keeps their folder, deduces the
    player from the folder name when the run did not save it, and picks them up at the next start."""
    from tennisbio.app.engine import Engine
    a = env.app()
    out = a.paths.output
    for grp in ("_smoke", "_poc9_largo"):
        d = out / grp / "smoke_tennis-yusipopen-final-sobolenko-rybakin"
        d.mkdir(parents=True)
        (d / "manifest.json").write_text(json.dumps({"candidates": {"summary": {"candidates": 9}},
                                                     "fine": {"summary": {"confirmed": 9}}}), encoding="utf-8")
    a.close()
    b = env.app()                                               # next start: picks them up
    rows = {r["id"]: r for r in b.db.q("SELECT * FROM matches")}
    assert set(rows) == {"smoke:smoke_tennis-yusipopen-final-sobolenko-rybakin",
                         "poc9_largo:smoke_tennis-yusipopen-final-sobolenko-rybakin"}
    r = rows["poc9_largo:smoke_tennis-yusipopen-final-sobolenko-rybakin"]
    assert r["dir"] == "_poc9_largo/smoke_tennis-yusipopen-final-sobolenko-rybakin" and r["player"] == "rybakina"
    assert r["state"] == "analizado" and "deducida del nombre" in r["note"]
    e = Engine(b.db, b.paths)
    assert e.dir(r["id"]) == out / r["dir"] and e.match(r["id"]).id == "smoke_tennis-yusipopen-final-sobolenko-rybakin"
    root, mine = e._group("rybakina")
    assert root.name in ("_smoke", "_poc9_largo") and len(mine) == 1
    assert "Jugadoras: 2 · partidos: 2" in b.status()


def test_restart_keeps_what_the_application_decided(env):
    a = env.app()
    _, first = _added(env, a)
    a.work()
    a.db.x("UPDATE matches SET state='archivado' WHERE id=?", first)
    a.close()
    b = env.app()
    assert b.db.one("SELECT state FROM matches WHERE id=?", first)["state"] == "archivado"


def test_identity_decided_by_the_end_changes_is_not_doubtful():
    """Real case (PC, 18-10): the clothes' vote was 0.52-0.62 but every shot was decided by the scoreboard's
    end changes: not doubtful. Doubtful: few shots decided, or many in conflict."""
    assert index.identity_doubt({"runs": 11, "votes": 8, "confidence": 0.62, "by_end_changes": 11, "decided": 11, "conflicts": 0}) == ""
    assert index.identity_doubt({"runs": 76, "decided": 74, "conflicts": 2, "confidence": 0.98}) == ""
    assert "en conflicto" in index.identity_doubt({"runs": 20, "decided": 19, "conflicts": 5})
    assert "0,52" in index.identity_doubt({"confidence": 0.52, "runs": 3})          # an old summary without «decided»


def test_restart_rereads_what_the_folders_say(env):
    """A state derived with an older rule (e.g. «identidad dudosa» from the clothes' vote) is read again
    from the folder at the next start; a notice about the video itself is kept."""
    a = env.app()
    _, first = _added(env, a)
    a.work()
    a.db.x("UPDATE matches SET state='identidad dudosa', note='vieja regla' WHERE id=?", first)
    _, second = _added(env, a, "2024_Madrid_Rybakina.mp4", b"m")
    a.work()
    a.db.x("UPDATE matches SET state='con aviso', note='El vídeo ya no está: se conservan sus resultados.' WHERE id=?", second)
    a.close()
    b = env.app()
    assert b.db.one("SELECT state FROM matches WHERE id=?", first)["state"] == "analizado"
    assert b.db.one("SELECT state FROM matches WHERE id=?", second)["state"] == "con aviso"


def test_test_run_clip_is_found_next_to_its_matches(env):
    """Test runs cut their clip into the run's folder (output/_smoke/<name>_1800_4m.mkv), not the videos
    folder; a video not found once is looked for again at the next start."""
    from tennisbio.pipeline import video_fingerprint
    a = env.app()
    run = a.paths.output / "_smoke"
    d = run / "smoke_x-rybakina"
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps({"fine": {"summary": {"confirmed": 3}}}), encoding="utf-8")
    clip = run / "x_1800_4m.mkv"
    clip.write_bytes(b"v" * 5000)
    video_fingerprint(clip, d)                                   # what the pipeline pins in video.json
    clip.rename(env.tmp / "aparte.bin")                          # not there at the first look
    a.close()
    b = env.app()
    assert b.db.one("SELECT path FROM videos")["path"] == ""
    (env.tmp / "aparte.bin").rename(clip)
    b.close()
    c = env.app()
    assert c.db.one("SELECT path FROM videos")["path"] == str(clip)
