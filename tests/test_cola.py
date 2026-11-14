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
