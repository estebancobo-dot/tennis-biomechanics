"""Paso 8 (14-11, #281-#283): the cloud's job queue (cloud/cola.py), its decisions without Modal."""
import json
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud"))

import cola  # noqa: E402

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
    last = y["jobs"]["cola"]["steps"][-1]
    assert last["name"] == "Siguiente vuelta" and last["if"] == "always()"
    assert "sleep 1500" in last["run"] and "gh workflow run cola.yml" in last["run"]
    assert y["jobs"]["cola"]["timeout-minutes"] > 25 + 5


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
    assert cola._sources(ROOT, {"kaggle_activo": True}, busy)["kaggle"] == {"ok": False, "motivo": "ocupado con g"}
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "cola.yml").read_text(encoding="utf-8"))
    job = wf["jobs"]["cola"]
    assert job["env"]["KAGGLE_API_TOKEN"] == "${{ secrets.KAGGLE_API_TOKEN }}"
    assert "sleep 300" in job["steps"][-1]["run"]                                     # every 5 min while running
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
