"""The single worker and the queue's controls (10-11, phase B of docs/orquestador.md)."""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from tennisbio import orchestrator as O


@pytest.fixture
def env(tmp_path, monkeypatch):
    sb = tmp_path / "sandbox.yaml"
    sb.write_text(f"paths:\n  output: '{(tmp_path / 'output').as_posix()}'\n  data: '{(tmp_path / 'datos').as_posix()}'\n"
                  f"  videos: '{(tmp_path / 'videos').as_posix()}'\n", encoding="utf-8")
    monkeypatch.setenv("TENNISBIO_SANDBOX", str(sb))
    from tennisbio.config import load_config
    return load_config()


def test_one_worker_per_pc(env):
    a, b = O.WorkerLock(O.lock_path(env)), O.WorkerLock(O.lock_path(env))
    assert a.acquire()
    if os.name != "nt":           # flock: a second open file in the same process is refused too
        assert not b.acquire()
    a.release()
    assert b.acquire()
    b.release()


def test_submit_pause_resume_cancel_and_status(env):
    db = O.open_db(env)
    j1 = O.submit(db, "comando", args=["registry", "list"], source="claude")
    j2 = O.submit(db, "comando", args=["registry", "sync"], source="app")
    assert j1 != j2                                         # two commands are two jobs
    O.pause(db, source="app")
    from tennisbio.app import jobs
    assert jobs.next_job(db) is None                        # paused: nothing starts
    O.resume(db, source="claude")
    assert jobs.next_job(db)["id"] == j1
    assert O.cancel(db, j2, source="app") == 1
    st = O.status(db)
    assert [r["id"] for r in st["pendientes"]] == [j1] and st["recientes"][0]["state"] == "cancelado"
    kinds = [e["kind"] for e in st["eventos"]]
    assert {"enviado", "pausa", "reanudar", "cancelar"} <= set(kinds)
    db.close()


def test_worker_runs_a_command_in_a_child_and_writes_its_status(env):
    db = O.open_db(env)
    jid = O.submit(db, "comando", args=["registry", "sync"], source="claude")
    db.close()
    out = Path(env["paths"]["output"])
    assert O.serve(env, once=True, idle_s=0.1, status_file=out / "estado_trabajos.json") == 0
    db = O.open_db(env)
    row = db.one("SELECT * FROM jobs WHERE id=?", jid)
    assert row["state"] == "hecho", Path(row["log"]).read_text(encoding="utf-8")
    st = json.loads((out / "estado_trabajos.json").read_text(encoding="utf-8"))
    assert st["ejecutor"]["vivo"] is False and st["recientes"][0]["id"] == jid
    assert [e["kind"] for e in O.status(db)["eventos"]][:3] == ["ejecutor", "hecho", "empieza"]
    db.close()


def test_a_running_job_is_stopped_at_once_and_resumes_later(env, monkeypatch):
    # a long command: a sleep through `tennisbio jobs run-one` would need a real stage; a script stands for it
    db = O.open_db(env)
    jid = O.submit(db, "comando", args=["registry", "sync"], source="claude")
    db.close()
    real = O._spawn
    monkeypatch.setattr(O, "_spawn", lambda job_id, log, extra_env=None: subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"], **({"start_new_session": True} if os.name != "nt" else {})))
    monkeypatch.setattr(O, "POLL_S", 0.2)
    def stop_soon():
        time.sleep(1.0)
        d = O.open_db(env)
        O.pause(d, now_=True, source="app")
        d.close()
    threading.Thread(target=stop_soon).start()
    t0 = time.time()
    O.serve(env, once=True, idle_s=0.1)
    assert time.time() - t0 < 20
    db = O.open_db(env)
    row = db.one("SELECT * FROM jobs WHERE id=?", jid)
    assert row["state"] == "pendiente" and "sigue donde se quedó" in row["message"]
    db.close()
    monkeypatch.setattr(O, "_spawn", real)


def test_a_second_worker_does_nothing(env):
    lock = O.WorkerLock(O.lock_path(env))
    assert lock.acquire()
    try:
        if os.name != "nt":
            assert O.serve(env, once=True) == 3
    finally:
        lock.release()


def test_restart_ends_the_worker_between_jobs_and_the_signature_changes(env):
    db = O.open_db(env)
    f0 = O.status(db)["firma"]
    O.restart(db, source="ciclo")
    j = O.submit(db, "comando", args=["registry", "list"], source="claude")
    assert O.status(db)["firma"] != f0
    db.close()
    assert O.serve(env, idle_s=0.1) == 0                    # without once: it ends because of the restart
    db = O.open_db(env)
    assert db.one("SELECT state FROM jobs WHERE id=?", j)["state"] == "pendiente"     # untouched, for the new worker
    assert db.setting("reiniciar_ejecutor") is False
    db.close()


def test_the_command_line_as_the_cycle_calls_it(env, tmp_path):
    # 10-11: argparse.REMAINDER kept «--source» and «--json» as words of the action
    from tennisbio import cli
    st = tmp_path / "estado.json"
    assert cli.main(["jobs", "submit", "--source", "claude 184", "--", "run", "--all"]) == 0
    assert cli.main(["jobs", "pause", "--source", "app", "now"]) == 0
    assert cli.main(["jobs", "cancel", "--source", "app", "all"]) == 0
    assert cli.main(["jobs", "resume", "--source", "claude"]) == 0
    assert cli.main(["jobs", "status", "--source", "ciclo", "--json", str(st)]) == 0
    s = json.loads(st.read_text(encoding="utf-8"))
    job = s["recientes"][0]
    assert json.loads(job["args"]) == ["run", "--all"] and job["source"] == "claude 184" and job["state"] == "cancelado"
    assert s["pausa"] is False and s["firma"]
    assert {e["kind"] for e in s["eventos"]} >= {"enviado", "pausa", "cancelar", "reanudar"}


def test_a_flow_runs_its_steps_and_a_resumed_one_goes_on_where_it_was(env):
    # 11-11, phase C: config/flujos.yaml «prueba» (registry sync, registry list)
    assert {"completo", "informe", "prevision", "prueba"} <= set(O.flows())
    db = O.open_db(env)
    a = O.submit(db, "flujo", args=["prueba"], source="claude")
    b = O.submit(db, "flujo", args=["prueba"], source="claude")
    db.x("UPDATE jobs SET paso=1 WHERE id=?", b)               # b was cut after its first step
    with pytest.raises(ValueError):
        O.submit(db, "flujo", args=["no-existe"])
    db.close()
    assert O.serve(env, once=True, idle_s=0.1) == 0
    db = O.open_db(env)
    for j, steps in ((a, 2), (b, 1)):
        row = db.one("SELECT * FROM jobs WHERE id=?", j)
        assert row["state"] == "hecho" and row["paso"] == 2 and row["pasos"] == 2, Path(row["log"]).read_text(encoding="utf-8")
        assert len([e for e in O.status(db, events=200)["eventos"] if e["job"] == j and e["kind"] == "paso"]) == steps
    out = Path(env["paths"]["output"])
    assert (out / "registro_partidos.json").exists()
    db.close()


def test_every_step_of_every_flow_is_a_known_command_or_script():
    from tennisbio import cli
    root = Path(O.FLOWS_FILE).parents[1]
    known = {"run", "status", "report", "export", "audit", "app", "registry", "jobs", "worker"}
    for name, fl in O.flows().items():
        assert fl.get("pasos"), name
        for st in fl["pasos"]:
            assert bool(st.get("tennisbio")) != bool(st.get("script")), (name, st)
            if st.get("tennisbio"):
                assert st["tennisbio"][0] in known, (name, st)
            else:
                assert (root / st["script"][0]).exists(), (name, st)
            assert st.get("si_falla", "parar") in ("parar", "seguir")
    assert cli is not None


def test_a_flow_submitted_the_way_the_cycle_does(env):
    from tennisbio import cli
    assert cli.main(["jobs", "submit", "--source", "claude 187", "--", "flujo", "prueba"]) == 0
    db = O.open_db(env)
    row = db.q("SELECT * FROM jobs ORDER BY id DESC LIMIT 1")[0]
    assert row["kind"] == "flujo" and json.loads(row["args"]) == ["prueba"] and row["pasos"] == 2
    db.close()


def test_end_to_end_submit_as_the_chat_pause_in_the_app_resume_as_the_chat(env, monkeypatch):
    # task 7 of B8 (phase F): scripts/e2e_orquestador.py against a real worker, with a shorter long step
    import yaml
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import e2e_orquestador as E
    fl = O.flows()
    fl["prueba_pausa"]["pasos"][1]["script"] = ["scripts/esperar.py", "12"]
    f = Path(env["paths"]["output"]).parent / "flujos.yaml"
    f.write_text(yaml.safe_dump(fl, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(O, "FLOWS_FILE", f)
    monkeypatch.setenv("TENNISBIO_FLUJOS", str(f))                  # the job's child process reads the same flows
    monkeypatch.setattr(O, "POLL_S", 0.3)
    stop = threading.Event()
    t = threading.Thread(target=O.serve, args=(env,), kwargs={"idle_s": 0.2, "stop": stop.is_set})
    t.start()
    try:
        res = E.run(env, timeout_s=120, poll_s=0.3)
    finally:
        stop.set()
        t.join(30)
    assert res["ok"], res


def test_submit_without_the_double_dash_as_powershell_passes_it(env):
    # 11-11, request 189: PowerShell removed «--» and «--match ID» was taken as an option of the queue
    from tennisbio import cli
    assert cli.main(["jobs", "submit", "--source", "claude 191", "run", "--match", "m-1", "--force"]) == 0
    db = O.open_db(env)
    row = db.q("SELECT * FROM jobs ORDER BY id DESC LIMIT 1")[0]
    assert json.loads(row["args"]) == ["run", "--match", "m-1", "--force"] and row["source"] == "claude 191"
    db.close()


def test_two_processes_upgrading_the_same_old_database_at_once(env, tmp_path):
    # 11-11: «duplicate column name» when the window and the worker added the queue's columns at the same moment: here
    # the other process added every column between this one's look at the table and its ALTER
    from tennisbio.app.db import DB
    db = DB(tmp_path / "t.db")                                 # every column already there

    class Late:                                                # the table as this process saw it a moment before
        def __init__(self, con):
            self.con = con
        def execute(self, sql, *a):
            if sql.startswith("PRAGMA table_info(jobs)"):
                return [r for r in self.con.execute(sql, *a) if r[1] not in ("args", "control", "paso")]
            return self.con.execute(sql, *a)
        def __getattr__(self, k):
            return getattr(self.con, k)

    real = db.con
    db.con = Late(real)
    O.ensure_schema(db)                                        # no error: the other process's columns are kept
    db.con = real
    cols = {r[1] for r in db.con.execute("PRAGMA table_info(jobs)")}
    assert {"args", "control", "paso", "pasos", "log", "source"} <= cols
    db.close()
