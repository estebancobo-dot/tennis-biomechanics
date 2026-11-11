import json
import sqlite3

from tennisbio.audit import ORCH_ALIVE_ITEM, ORCH_E2E_ITEM, ORCH_WAIT_ITEM, orchestrator_items

E2E_OK = ('Peticion 205: prueba\n{\n "ok": true,\n "checks": {\n  "llega al paso largo": true,\n  "reanudado, acaba hecho": true\n'
          ' }\n}\ncodigo de salida: 0; termina 2026-11-11T17:19:19\n')
NOW = 1794430000.0          # 2026-11-11 ~22:46 local (the jobs below are from that evening)


def _db(base, jobs, beat_at=None, pid=4242, paused=False):
    (base / "datos").mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(base / "datos" / "tennisbio.db")
    con.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY, state TEXT, created TEXT, started TEXT, finished TEXT)")
    con.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
    con.executemany("INSERT INTO jobs (id, state, created, started, finished) VALUES (?, ?, ?, ?, ?)", jobs)
    if beat_at is not None:
        con.execute("INSERT INTO settings VALUES ('ejecutor', ?)", (json.dumps({"pid": pid, "at": beat_at}),))
    con.execute("INSERT INTO settings VALUES ('pausa', ?)", (json.dumps(paused),))
    con.commit()
    con.close()


def _by(items):
    return {i["name"]: i for i in items}


def test_the_evening_of_11_11_fails_the_wait(tmp_path):
    (tmp_path / "prueba_e2e.log").write_text(E2E_OK, encoding="utf-8")
    # jobs 54 and 55 (requests 208, 209): queued 21:02 and 21:08, started 21:13 (the worker had ended at 20:54)
    _db(tmp_path, [(53, "hecho", "2026-11-11 17:17:24", "2026-11-11 17:17:47", "2026-11-11 17:19:19"),
                   (54, "hecho", "2026-11-11 21:02:29", "2026-11-11 21:13:00", "2026-11-11 21:13:02"),
                   (55, "hecho", "2026-11-11 21:08:25", "2026-11-11 21:13:02", "2026-11-11 21:13:05")], beat_at=NOW - 20)
    by = _by(orchestrator_items([tmp_path], now_s=NOW))
    assert by[ORCH_E2E_ITEM]["status"] == "ok"
    assert by[ORCH_ALIVE_ITEM]["status"] == "ok"
    w = by[ORCH_WAIT_ITEM]
    assert w["status"] == "aviso" and "10.5 min (trabajo 54)" in w["detail"] and "1 esperaron" in w["detail"]


def test_jobs_waiting_with_no_worker_fail_and_a_quick_queue_passes(tmp_path):
    _db(tmp_path, [(1, "hecho", "2026-11-11 21:00:00", "2026-11-11 21:00:10", "2026-11-11 21:30:00"),
                   (2, "hecho", "2026-11-11 21:10:00", "2026-11-11 21:30:05", "2026-11-11 21:31:00"),  # waited for job 1
                   (3, "pendiente", "2026-11-11 22:40:00", None, None)], beat_at=NOW - 900)
    by = _by(orchestrator_items([tmp_path], now_s=NOW))
    assert by[ORCH_ALIVE_ITEM]["status"] == "falta"          # a job waits and the heartbeat is 15 min old
    assert by[ORCH_WAIT_ITEM]["status"] == "ok"              # job 2 waited behind job 1, not for a worker
    assert by[ORCH_E2E_ITEM]["status"] == "aviso"            # never run
    (tmp_path / "prueba_e2e.log").write_text(E2E_OK.replace('"reanudado, acaba hecho": true', '"reanudado, acaba hecho": false'),
                                             encoding="utf-8")
    assert _by(orchestrator_items([tmp_path], now_s=NOW))[ORCH_E2E_ITEM]["status"] == "falta"


def test_a_paused_queue_is_not_a_dead_worker(tmp_path):
    _db(tmp_path, [(3, "pendiente", "2026-11-11 22:40:00", None, None)], beat_at=None, paused=True)
    assert _by(orchestrator_items([tmp_path], now_s=NOW))[ORCH_ALIVE_ITEM]["status"] == "ok"
