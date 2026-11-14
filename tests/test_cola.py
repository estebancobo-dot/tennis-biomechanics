"""Paso 8 (14-11, #281-#283): the cloud's job queue (cloud/cola.py), its decisions without Modal."""
import json
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud"))

import cola  # noqa: E402
import nube  # noqa: E402

NOV = time.mktime((2026, 11, 14, 12, 0, 0, 0, 0, 0))
DEC = time.mktime((2026, 12, 1, 12, 0, 0, 0, 0, 0))
OFF = {"kaggle": {"ok": False, "motivo": "sin cuenta"}, "pc": {"ok": False, "motivo": "en pausa"}}


def _jobs():
    return [{"id": "prueba_gauff", "accion": "prueba", "partido": "gauff"},
            {"id": "gauff", "accion": "partido", "partido": "gauff", "tras": "prueba_gauff", "aprobado": True,
             "minutos_video": 150},
            {"id": "final", "accion": "partido", "partido": "final", "minutos_video": 210}]


def test_queue_file_and_workflow():
    q = yaml.safe_load((ROOT / "config" / "cola_nube.yaml").read_text(encoding="utf-8"))
    assert isinstance(q["trabajos"], list) and not cola.check_queue(q["trabajos"])
    assert q["gasto_modal_base"]["2026-11"] >= 28.05                 # the Usage page on 14-11
    wf = (ROOT / ".github" / "workflows" / "cola.yml").read_text(encoding="utf-8")
    assert "cron:" in wf and "python cloud/cola.py --cola config/cola_nube.yaml --logs logs" in wf
    assert "contents: write" in wf and "group: cola" in wf and "nube-logs" in wf
    # 14-11: GitHub did not run the schedule for hours: while any job is unfinished, each run starts the next one
    y = yaml.safe_load(wf)
    on = y.get("on") or y.get(True)
    assert {"schedule", "workflow_dispatch", "push", "workflow_run"} <= set(on) and on["workflow_run"]["workflows"] == ["Nube"]
    assert y["permissions"]["actions"] == "write"
    beat = y["jobs"]["latido"]
    last = beat["steps"][-1]
    assert last["name"] == "Siguiente vuelta" and last["if"] == "always()"
    assert "sleep 1500" in last["run"] and "gh workflow run cola.yml" in last["run"]
    assert beat["timeout-minutes"] > 25 + 2
    # 14-11 18:00: a push waited 25 min behind the sleeping heartbeat; now the pass has its own slot (never cancelled)
    # and only the newest heartbeat is kept
    assert "concurrency" not in y
    assert y["jobs"]["cola"]["concurrency"] == {"group": "cola", "cancel-in-progress": False}
    assert beat["concurrency"] == {"group": "cola-latido", "cancel-in-progress": True}
    assert beat["needs"] == "cola" and beat["if"].startswith("always()")
    assert y["jobs"]["cola"]["steps"][-1]["id"] == "cuenta" and "GITHUB_OUTPUT" in y["jobs"]["cola"]["steps"][-1]["run"]


def test_bad_jobs_are_named():
    bad = cola.check_queue([{"id": "a", "accion": "borrar"}, {"id": "b", "accion": "partido"},
                            {"id": "c", "accion": "prueba", "partido": "x", "tras": "z"}, {"id": "c", "accion": "informe"},
                            {"accion": "informe"}, {"id": "d e", "accion": "informe"}, {"id": "f", "accion": "informe",
                                                                                       "donde": "luna"}])
    text = " | ".join(bad)
    for part in ("a: acción", "b: falta el partido", "c: «tras» z", "c: id repetido", "sin id válido", "f: donde"):
        assert part in text, (part, bad)


def test_november_has_no_room_and_says_why():
    """14-11: 28.08 $ used of 30 (cap 29.5): a whole match (≈ 13.65 $) waits with its reason; the test before it fits
    (0.8 $); an unapproved match never goes; a job after an unfinished one waits for it."""
    spend = {}
    cola.set_base(spend, {"2026-11": 28.08})
    assert cola.modal_room(spend, NOV) == 1.42
    d = {i: (src, why) for i, src, why in cola.plan(_jobs(), {}, spend, OFF, NOV)}
    assert d["prueba_gauff"][0] == "modal"
    assert d["gauff"] == ("", "espera a prueba_gauff (pendiente)")
    assert d["final"] == ("", "falta la aprobación del usuario (#262)")
    state = {"prueba_gauff": {"estado": "hecho"}}
    d = {i: (src, why) for i, src, why in cola.plan(_jobs(), state, spend, OFF, NOV)}
    assert d["gauff"][0] == "" and "sin capacidad" in d["gauff"][1] and "Modal: quedan 1.42 $" in d["gauff"][1]
    assert "kaggle: sin cuenta" in d["gauff"][1] and "pc: en pausa" in d["gauff"][1]


def test_new_month_and_other_sources():
    """1-12: a new month starts with the whole credit; two jobs never count the same dollars; Kaggle, when it is
    connected, goes first; a job tied to a source waits for it."""
    spend = {}
    cola.set_base(spend, {"2026-11": 28.08})
    jobs = [{"id": "a", "accion": "partido", "partido": "a", "aprobado": True, "minutos_video": 210},
            {"id": "b", "accion": "partido", "partido": "b", "aprobado": True, "minutos_video": 210},
            {"id": "c", "accion": "partido", "partido": "c", "aprobado": True, "minutos_video": 210},
            {"id": "k", "accion": "informe", "donde": "pc"}]
    d = {i: (src, why) for i, src, why in cola.plan(jobs, {}, spend, OFF, DEC)}
    assert d["a"][0] == d["b"][0] == "modal"                         # 2 × 13.65 $ fit in 29.5 $
    assert d["c"][0] == "" and "sin capacidad" in d["c"][1]          # the third does not
    assert d["k"] == ("", "sin capacidad: pc: en pausa")
    on = {"kaggle": {"ok": True, "motivo": "quedan 25 h esta semana"}, "pc": {"ok": False}}
    assert cola.plan(jobs[:1], {}, spend, on, DEC)[0][1] == "kaggle"


def test_launch_and_result_keep_the_spend():
    spend, state = {}, {}
    cola.set_base(spend, {"2026-12": 0.0})
    job = {"id": "prueba_x", "accion": "prueba", "partido": "x"}
    cola.record_launch(state, spend, job, "modal", "fc-01ABC", DEC)
    assert state["prueba_x"]["estado"] == "en_marcha"
    assert state["prueba_x"]["ruta"] == "/runs/partido__prueba_x/estado.json"
    assert cola.modal_room(spend, DEC) == round(cola.CAP_USD - 0.8, 2)
    assert cola.plan([job], state, spend, OFF, DEC) == []            # running: not launched again
    cola.record_result(state, spend, "prueba_x", {"estado": "hecho", "coste_usd": 0.42, "segundos": 1400}, DEC)
    assert state["prueba_x"]["estado"] == "hecho" and state["prueba_x"]["resultado"]["coste_usd"] == 0.42
    assert cola.modal_room(spend, DEC) == round(cola.CAP_USD - 0.42, 2)  # the real cost replaces the estimate
    cola.record_launch(state, spend, {"id": "y", "accion": "informe"}, "modal", "fc-2", DEC)
    cola.record_result(state, spend, "y", {"estado": "error", "nota": "falló"}, DEC)
    assert state["y"]["estado"] == "error"
    assert cola.run_path({"id": "z", "accion": "partido", "partido": "p"}) == "/runs/partido_p/estado.json"
    assert cola.run_path({"id": "inf3", "accion": "informe"}) == "/runs/inf3/estado.json"


def test_dry_pass_writes_the_state_without_modal(tmp_path, monkeypatch):
    q = tmp_path / "cola.yaml"
    q.write_text(yaml.safe_dump({"gasto_modal_base": {"2026-11": 28.08}, "trabajos": _jobs() + [{"id": "mal", "accion": "x"}]}),
                 encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert cola.main(["--cola", str(q), "--logs", str(tmp_path / "logs"), "--en-seco"]) == 0
    d = tmp_path / "logs" / "cola"
    md = (d / "estado.md").read_text(encoding="utf-8")
    assert "| gauff | partido | gauff | pendiente |" in md and "espera a prueba_gauff" in md and "mal" not in md
    assert cola._sources(tmp_path)["pc"]["ok"] is False                                 # #284: the PC is never used
    assert json.loads((d / "estado.json").read_text(encoding="utf-8")) == {}       # dry: nothing launched
    assert json.loads((d / "gasto.json").read_text(encoding="utf-8"))["modal"]["2026-11"]["base_usd"] == 28.08


def test_kaggle_takes_one_job_at_a_time_within_its_weekly_hours(monkeypatch):
    spend = {}
    cola.set_base(spend, {"2026-11": 28.08})
    on = {"kaggle": {"ok": True, "motivo": ""}, "pc": {"ok": False, "motivo": "no se usa"}}
    jobs = [{"id": "a", "accion": "partido", "partido": "a", "aprobado": True, "minutos_video": 150},
            {"id": "b", "accion": "prueba", "partido": "b"},
            {"id": "inf", "accion": "informe"}]
    d = {i: (src, why) for i, src, why in cola.plan(jobs, {}, spend, on, NOV)}
    assert d["a"][0] == "kaggle" and "previstas 7.5 h" in d["a"][1]
    assert d["b"][0] == "modal"                               # Kaggle is busy with «a»: the test goes to Modal
    assert d["inf"][0] == "modal"                             # the report never goes to Kaggle
    cola.record_launch(st := {}, spend, jobs[0], "kaggle", "kaggle", NOV)
    assert st["a"]["intentos"] == 1 and cola.kaggle_room(spend, NOV) == cola.KAGGLE_CAP_H - 7.5
    cola.record_launch(st, spend, jobs[0], "kaggle", "kaggle", NOV + 700)        # launched again
    assert st["a"]["intentos"] == 2 and cola.kaggle_room(spend, NOV) == cola.KAGGLE_CAP_H - 7.5
    cola.record_result(st, spend, "a", {"estado": "hecho", "horas_kaggle": 4.2, "coste_usd": 0.0}, NOV + 9000)
    assert cola.kaggle_room(spend, NOV) == round(cola.KAGGLE_CAP_H - 4.2, 2)
    assert cola.modal_room(spend, NOV) == round(29.5 - 28.08, 2)          # a Kaggle job never counts as Modal spend
    full = {"kaggle": {"trabajos": {"x": {"horas": 27.0}}}}
    spend2 = {"kaggle": {cola.week(NOV): full["kaggle"]}}
    cola.set_base(spend2, {"2026-11": 28.08})
    d = {i: (src, why) for i, src, why in cola.plan(jobs[:1], {}, spend2, on, NOV)}
    assert d["a"][0] == "" and "kaggle: quedan 1.0 h esta semana" in d["a"][1]


def test_a_stuck_or_cut_kaggle_session_is_launched_again_then_given_up():
    st = {"lanzado_ts": NOV, "intentos": 1}
    assert cola.kaggle_step(st, "running", None, NOV + 5000) == ("nada", "")
    assert cola.kaggle_step(st, "queued", None, NOV + 300) == ("nada", "")
    assert cola.kaggle_step(st, "queued", None, NOV + 1800) == ("nada", "")      # 14-11: its GPUs busy: it waits
    act, why = cola.kaggle_step(st, "queued", None, NOV + 2701)
    assert act == "relanzar" and "en cola de Kaggle más de 45 min" in why
    assert cola.kaggle_step(st, "error", None, NOV + 60)[0] == "relanzar"
    assert cola.kaggle_step(st, "desconocido", None, NOV + 300) == ("nada", "")
    assert cola.kaggle_step(st, "desconocido", None, NOV + 601)[0] == "relanzar"      # refused launch, nothing behind
    assert cola.kaggle_step(st, "complete", {"estado": "en curso"}, NOV + 43000)[0] == "relanzar"
    assert cola.kaggle_step(st, "complete", {"estado": "hecho"}, NOV + 43000) == ("recoger", "")
    assert cola.kaggle_step(st, "error", {"estado": "error"}, NOV + 60) == ("recoger", "")
    act, why = cola.kaggle_step({"lanzado_ts": NOV, "intentos": cola.KAGGLE_TRIES}, "queued", None, NOV + 2701)
    assert act == "error" and f"({cola.KAGGLE_TRIES} intentos)" in why


def test_kaggle_source_needs_its_keys_its_switch_and_a_free_notebook(monkeypatch):
    monkeypatch.delenv("KAGGLE_API_TOKEN", raising=False)
    assert "sin sus claves" in cola._sources(ROOT)["kaggle"]["motivo"]
    monkeypatch.setenv("KAGGLE_API_TOKEN", "x")
    monkeypatch.setenv("KAGGLE_USERNAME", "u")
    assert "aún no activado" in cola._sources(ROOT, {"kaggle_activo": False})["kaggle"]["motivo"]
    assert cola._sources(ROOT, {"kaggle_activo": True})["kaggle"]["ok"] is True
    busy = {"g": {"estado": "en_marcha", "donde": "kaggle"}}
    assert cola._sources(ROOT, {"kaggle_activo": True}, busy)["kaggle"] == {"ok": True, "motivo": "", "libres": 1}  # T20
    busy["h"] = {"estado": "en_marcha", "donde": "kaggle"}
    assert cola._sources(ROOT, {"kaggle_activo": True}, busy)["kaggle"] == {"ok": False, "motivo": "ocupado con g, h"}
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "cola.yml").read_text(encoding="utf-8"))
    job = wf["jobs"]["cola"]
    assert job["env"]["KAGGLE_API_TOKEN"] == "${{ secrets.KAGGLE_API_TOKEN }}"
    assert "sleep 300" in wf["jobs"]["latido"]["steps"][-1]["run"]                   # every 5 min while running
    q = yaml.safe_load((ROOT / "config" / "cola_nube.yaml").read_text(encoding="utf-8"))
    assert "kaggle_activo" in q


def test_a_test_with_a_serious_fault_is_not_passed_and_keeps_its_match_waiting():
    """R40 (14-11): Gauff's 10-minute test ended «hecho» with 0 scoreboard readings (C1): the match after it would have
    started with a known fault (#247). Now such a test is «revisar» and its match waits."""
    spend, state = {}, {}
    cola.set_base(spend, {"2026-12": 0.0})
    t = {"id": "t", "accion": "prueba", "partido": "g"}
    m = {"id": "m", "accion": "partido", "partido": "g", "tras": "t", "aprobado": True}
    cola.record_launch(state, spend, t, "kaggle", "kaggle", DEC)
    assert state["t"]["ruta"] == "/runs/kaggle_t/estado.json"            # its own folder, never over Modal's test
    cola.record_result(state, spend, "t", {"estado": "hecho", "fallos": {"score": {"entrada.cobertura_baja": {
        "nivel": "C1", "n": 1}}}}, DEC)
    assert state["t"]["estado"] == "revisar" and "score: entrada.cobertura_baja (C1)" in state["t"]["resultado"]["nota"]
    d = {i: (src, why) for i, src, why in cola.plan([t, m], state, spend, OFF, DEC)}
    assert "t" not in d and d["m"] == ("", "espera a t (revisar)")
    cola.record_launch(state, spend, t, "modal", "fc", DEC)
    cola.record_result(state, spend, "t", {"estado": "hecho", "fallos": {"court": {"x": {"nivel": "C2"}}}}, DEC)
    assert state["t"]["estado"] == "hecho"                                  # a C2 within budget does not stop it
    assert cola.run_path(t) == "/runs/partido__prueba_g/estado.json"


def test_an_older_runs_state_is_not_taken_for_this_launch():
    """Bringing a match up to date writes in the folder of its first analysis, whose estado.json says «hecho»: only a
    state started after this launch counts."""
    launched = {"lanzado_ts": DEC}
    old = {"estado": "hecho", "inicio": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(NOV))}
    new = {"estado": "en curso", "inicio": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(DEC + 60))}
    assert not cola.fresh(old, launched) and cola.fresh(new, launched)
    assert cola.fresh({"estado": "hecho"}, launched) and not cola.fresh(None, launched)
    assert cola.fresh(old, {})                                        # launched before this check: as before


def test_whole_matches_can_wait_and_a_job_can_start_again():
    """14-11 (#287): whole matches wait for the cloud-native phase B (`partidos_en_espera`); the final launched on Kaggle
    (left queued) starts again once (`reiniciar: ["final#1"]`), never a job already done."""
    spend, state = {}, {}
    cola.set_base(spend, {"2026-12": 0.0})
    on = {"kaggle": {"ok": True, "motivo": ""}, "pc": {"ok": False}}
    jobs = [{"id": "final", "accion": "partido", "partido": "f", "aprobado": True},
            {"id": "t", "accion": "prueba", "partido": "g", "donde": "kaggle"}]
    cola.record_launch(state, spend, jobs[0], "kaggle", "kaggle", DEC)
    state["hecho"] = {"estado": "hecho"}
    done = []
    assert cola.restart(state, spend, ["final#1", "hecho#1"], done) == ["final#1"]
    assert "final" not in state and "final" not in spend["kaggle"][cola.week(DEC)]["trabajos"] and "hecho" in state
    assert cola.restart(state, spend, ["final#1"], ["final#1"]) == []            # once per token
    d = {i: (src, why) for i, src, why in cola.plan(jobs, state, spend, on, DEC, "después de la fase B")}
    assert d["final"] == ("", "después de la fase B") and d["t"][0] == "kaggle"


def test_a_refused_kaggle_push_is_not_a_launch():
    """14-11: Kaggle refused every push for two hours («Maximum batch GPU session count of 2 reached») with exit code 0,
    and the queue counted them as launches."""
    assert cola.push_refused("Kernel push error: Maximum batch GPU session count of 2 reached.\n") \
        == "Kernel push error: Maximum batch GPU session count of 2 reached."
    assert cola.push_refused("Kernel version 9 successfully pushed.  Please check progress at ...") == ""


def test_a_proof_of_concept_goes_to_kaggle_only():
    jobs = [{"id": "medir_raqueta_trt", "accion": "medir", "prueba": "raqueta", "donde": "kaggle"}]
    assert cola.check_queue(jobs) == [] and cola.check_queue([{"id": "m", "accion": "medir"}]) != []
    on = {"kaggle": {"ok": True, "motivo": ""}, "pc": {"ok": False}}
    assert cola.plan(jobs, {}, {}, on, DEC)[0][1] == "kaggle"
    assert cola.run_path(jobs[0], "kaggle") == "/runs/kaggle_medir_raqueta_trt/estado.json"
    any_src = [{"id": "m2", "accion": "medir", "prueba": "raqueta"}]
    d = cola.plan(any_src, {}, {}, OFF, DEC)[0]
    assert d[1] == "" and "Modal: las pruebas de concepto van en Kaggle" in d[2]


def test_the_queue_state_goes_to_the_volume_for_the_audit(tmp_path):
    """T3 (14-11): the cloud's audit («Cola de la nube», B7/B8) reads the queue's state on the volume (/cola/)."""
    class Batch:
        def __init__(self):
            self.put = []

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def put_file(self, src, dst):
            self.put.append(dst)

    class Vol:
        b = Batch()

        def batch_upload(self, force=False):
            assert force
            return self.b

    for f in ("estado.json", "vuelta.json"):
        (tmp_path / f).write_text("{}", encoding="utf-8")
    v = Vol()
    assert cola.upload_state(v, tmp_path) and v.b.put == ["/cola/estado.json", "/cola/vuelta.json"]

    class Broken:
        def batch_upload(self, force=False):
            raise RuntimeError("sin red")
    assert cola.upload_state(Broken(), tmp_path) is False           # said, never the pass
    state = {}
    cola.record_launch(state, {}, {"id": "g", "accion": "partido", "partido": "m"}, "kaggle", "kaggle", 0.0)
    assert state["g"]["partido"] == "m"


def test_two_kaggle_sessions_at_once():
    """T20 (14-11): Kaggle's two GPU sessions used at once (one notebook per job); a third job waits."""
    jobs = [{"id": f"m{i}", "accion": "medir", "prueba": "raqueta", "donde": "kaggle"} for i in range(3)]
    src = {"kaggle": {"ok": True, "motivo": "", "libres": 2}}
    got = cola.plan(jobs, {}, {}, src, 0.0)
    assert [g[1] for g in got] == ["kaggle", "kaggle", ""] and "sesiones ocupadas" in got[2][2]
    got = cola.plan(jobs, {}, {}, {"kaggle": {"ok": True, "motivo": "", "libres": 1}}, 0.0)
    assert [g[1] for g in got] == ["kaggle", "", ""]


def test_compare_jobs_wait_and_run_here(tmp_path):
    """T9: «comparar» waits for both runs, then the queue itself compares them (no GPU) and records the verdict."""
    assert cola.TEST_PREFIX == nube.TEST_PREFIX
    j = {"id": "c", "accion": "comparar", "a": "/kaggle_pruebas/output/_prueba_m", "b": "p2"}
    assert not cola.check_queue([j, {"id": "p2", "accion": "prueba", "partido": "m"}])
    assert "comparar necesita" in cola.check_queue([{"id": "c", "accion": "comparar", "a": "x"}])[0]
    assert cola.plan([j], {}, {}, {}, 0.0) == [("c", "", "espera a p2")]
    state = {"p2": {"estado": "hecho"}}
    assert cola.plan([j], state, {}, {}, 0.0)[0][1] == "github"
    # where a Kaggle test leaves its outputs (each its own folder), recorded at its launch
    p2 = {"id": "p2", "accion": "prueba", "partido": "m"}
    assert cola.output_of(p2, "kaggle") == "/kaggle_pruebas/p2/output/_prueba_m"
    assert cola.output_of({"id": "g", "accion": "partido", "partido": "m"}, "kaggle") == "/output/m"
    st = {}
    cola.record_launch(st, {}, p2, "kaggle", "kaggle", 0.0)
    assert st["p2"]["salida"] == "/kaggle_pruebas/p2/output/_prueba_m"
    state["p2"]["salida"] = st["p2"]["salida"]
    man = json.dumps({"fine": {"out_hash": "h"}}).encode()
    strokes = json.dumps([{"t": 1.0, "stroke": "forehand", "m": {"x": 1.0}}]).encode()
    files = {"kaggle_pruebas/output/_prueba_m/manifest.json": man, "kaggle_pruebas/p2/output/_prueba_m/manifest.json": man,
             "kaggle_pruebas/output/_prueba_m/strokes.json": strokes,
             "kaggle_pruebas/p2/output/_prueba_m/strokes.json": strokes}

    class Vol:
        def read_file(self, path):
            if path not in files:
                raise FileNotFoundError(path)
            return [files[path]]
    r = cola.compare_job(Vol(), j, state, tmp_path, 0.0)
    assert r["estado"] == "hecho" and r["resultado"]["veredicto"] == "idéntica"
    assert json.loads((tmp_path / "comparaciones" / "c.json").read_text(encoding="utf-8"))["veredicto"] == "idéntica"
    files["kaggle_pruebas/p2/output/_prueba_m/strokes.json"] = json.dumps([]).encode()
    files["kaggle_pruebas/p2/output/_prueba_m/manifest.json"] = json.dumps({"fine": {"out_hash": "z"}}).encode()
    assert cola.compare_job(Vol(), j, state, tmp_path, 0.0)["estado"] == "revisar"     # Claude looks, nothing goes on
    assert cola.compare_job(Vol(), {**j, "b": "nadie"}, state, tmp_path, 0.0)["estado"] == "error"


def test_a_test_with_other_settings(monkeypatch):
    """T5: a test job may carry «config» (the settings a proof of concept tries on the whole clip): Kaggle only."""
    j = {"id": "p", "accion": "prueba", "partido": "m", "config": {"hwaccel": "cuda"}}
    assert not cola.check_queue([j])
    assert "solo vale para una prueba" in cola.check_queue([{**j, "accion": "partido"}])[0]
    assert "es un diccionario" in cola.check_queue([{**j, "config": "hwaccel=cuda"}])[0]
    got = cola.plan([{**j, "donde": "modal"}], {}, {"modal": {}}, {}, NOV)
    assert got[0][1] == "" and "Kaggle" in got[0][2]
    calls = []

    class R:
        returncode, stdout, stderr = 0, "ok", ""
    monkeypatch.setattr(cola, "_kaggle", lambda args: calls.append(args) or R())
    assert cola.kaggle_launch(j)
    launch = calls[-1]
    assert launch[launch.index("--config") + 1] == '{"hwaccel": "cuda"}'


def test_what_wakes_claude(tmp_path):
    """#291 (14-11): only what needs Claude wakes him (no polling): a job that has just finished, failed or stopped in
    «revisar», or a new Kaggle refusal; a pass where nothing changed posts nothing."""
    before = {"a": {"estado": "en_marcha"}, "b": {"estado": "hecho"}, "c": {}}
    after = {"a": {"estado": "hecho", "resultado": {"nota": "idéntica"}}, "b": {"estado": "hecho"},
             "c": {"aviso": "Kaggle no lo aceptó: Maximum batch GPU session count"}, "d": {"estado": "en_marcha"}}
    ev = cola.events(before, after)
    assert ev == ["`a` → **hecho**: idéntica", "`c` → aviso: Kaggle no lo aceptó: Maximum batch GPU session count"]
    assert cola.events(after, after) == [] and cola.wake_message([], NOV) == ""
    msg = cola.wake_message(ev, NOV)
    assert "2 cambio(s)" in msg and "- `a` → **hecho**" in msg
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "cola.yml").read_text(encoding="utf-8"))
    steps = {s.get("name"): s for s in wf["jobs"]["cola"]["steps"]}
    assert "--avisos avisos.md" in steps["Una vuelta de la cola"]["run"]
    assert "gh pr comment" in steps["Avisar a Claude"]["run"] and wf["permissions"]["pull-requests"] == "write"
    # the dry run writes the (empty) message too
    q = tmp_path / "q.yaml"
    q.write_text("trabajos: []\n", encoding="utf-8")
    assert cola.main(["--cola", str(q), "--logs", str(tmp_path / "logs"), "--en-seco", "--avisos", str(tmp_path / "a.md")]) == 0
    assert (tmp_path / "a.md").read_text(encoding="utf-8") == ""
