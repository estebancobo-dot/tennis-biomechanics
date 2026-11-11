"""Phase E of docs/orquestador.md (11-11): the application uses the single worker and the same queue as the chat."""
import threading

import pytest

from tennisbio import orchestrator as O


@pytest.fixture
def app(tmp_path, monkeypatch):
    sb = tmp_path / "sandbox.yaml"
    sb.write_text(f"paths:\n  output: '{(tmp_path / 'output').as_posix()}'\n  data: '{(tmp_path / 'datos').as_posix()}'\n"
                  f"  videos: '{(tmp_path / 'videos').as_posix()}'\n", encoding="utf-8")
    monkeypatch.setenv("TENNISBIO_SANDBOX", str(sb))
    from tennisbio.app.core import App
    from tennisbio.config import load_config
    a = App(load_config())
    yield a
    a.close()


def test_the_windows_buttons_are_the_chats_orders(app):
    from tennisbio.app import window
    api = window.Api(app)
    j = O.submit(app.db, "flujo", args=["prueba"], source="claude")
    assert "pausa" in api.pause(True)
    assert app.db.setting("pausa") is True
    api.pause(True, True)                                               # «Parar ya»
    assert api.pause(False).startswith("Cola reanudada")
    assert api.cancel(j) == "Cancelado"
    kinds = [(e["kind"], e["text"]) for e in O.status(app.db)["eventos"]]
    assert ("reanudar", "app") in kinds and ("cancelar", "app") in kinds and ("enviado", "flujo prueba (claude)") in kinds


def test_the_queue_screen_shows_the_same_status_as_the_chat(app):
    from tennisbio.app.state import _queue
    j = O.submit(app.db, "flujo", args=["prueba"], source="claude 187")
    app.db.x("UPDATE jobs SET state='en curso', paso=1 WHERE id=?", j)
    q = _queue(app, {})
    run = q["running"][0]
    assert run["step"] == 1 and run["steps"] == 2 and run["source"] == "claude 187" and "prueba" in run["what"]
    assert q["worker"] == {"alive": False, "paused": False}
    assert q["events"][0]["kind"] == "enviado"
    from tennisbio.app.window import tray_text
    assert "paso 2/2" in tray_text(app)


def test_the_window_keeps_the_single_worker_alive_and_runs_no_job_itself(app, monkeypatch):
    from tennisbio.app import window
    started, spawned = [], []
    monkeypatch.setattr(window, "ensure_worker", lambda cfg, a: started.append(1) or "arrancado")
    import subprocess
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: spawned.append(a) or (_ for _ in ()).throw(AssertionError("no child")))
    O.submit(app.db, "comando", args=["registry", "list"], source="app")
    stop = threading.Event()
    t = threading.Thread(target=window.worker, args=(app.cfg, stop), kwargs={"idle_s": 0.05})
    t.start()
    import time
    time.sleep(0.4)
    stop.set()
    t.join(5)
    assert started and not spawned                                      # it asked the single worker, ran nothing itself
    assert window.single_worker({}) and not window.single_worker({"app": {"ejecutor": "propio"}})
