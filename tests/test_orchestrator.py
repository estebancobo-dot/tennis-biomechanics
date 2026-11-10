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
