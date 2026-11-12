"""12-11: the empty terminal window on the PC's screen (scripts/ventanas_visibles.py found it: Windows Terminal titled
«...\\.venv\\Scripts\\python.exe», opened at 11:08:21, the second the worker started its successor). Cause: the worker
and the application started the worker with DETACHED_PROCESS, next to which Windows ignores CREATE_NO_WINDOW; the venv
launcher then had no console and its child, the real interpreter, got a new visible one."""
from __future__ import annotations

import ast
from pathlib import Path

from tennisbio import orchestrator as O

SRC = Path(__file__).resolve().parents[1] / "src" / "tennisbio"


def test_background_processes_get_a_console_without_window_never_detached():
    kw = O.background_kwargs(nt=True)
    flags = kw["creationflags"]
    assert flags & O.CREATE_NO_WINDOW
    assert not flags & O.DETACHED_PROCESS          # with it, Windows ignores CREATE_NO_WINDOW (the window of 12-11)
    assert O.background_kwargs(nt=False) == {"start_new_session": True}


def test_no_process_of_ours_is_started_detached():
    bad = []
    for f in SRC.rglob("*.py"):
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Constant) and n.value == "DETACHED_PROCESS":
                bad.append(f"{f.relative_to(SRC)}:{n.lineno}")
    assert not bad, bad


def test_worker_alone_in_a_visible_console_starts_hidden_and_ends(monkeypatch):
    monkeypatch.setattr(O, "_log", lambda cfg, msg: None)
    started = []
    assert O.leave_visible_console(alone=lambda: True, successor=started.append, env={}) is True
    assert started == [{O.HIDDEN_RESPAWN_ENV: "1"}]          # the hidden one never does it again


def test_worker_started_hidden_or_by_a_person_stays(monkeypatch):
    monkeypatch.setattr(O, "_log", lambda cfg, msg: None)
    started = []
    assert O.leave_visible_console(alone=lambda: False, successor=started.append, env={}) is False
    # already restarted once: it stays whatever it finds (no loop of restarts)
    assert O.leave_visible_console(alone=lambda: True, successor=started.append, env={O.HIDDEN_RESPAWN_ENV: "1"}) is False
    assert started == []


def test_worker_keeps_working_in_its_window_when_it_cannot_restart(monkeypatch):
    monkeypatch.setattr(O, "_log", lambda cfg, msg: None)

    def fails(env):
        raise OSError("no")
    assert O.leave_visible_console(alone=lambda: True, successor=fails, env={}) is False


def test_off_windows_nothing_is_ever_alone():
    assert O._alone_in_own_console() is False


def test_worker_command_checks_the_console_before_serving(monkeypatch, tmp_path):
    from tennisbio import cli
    calls = []
    monkeypatch.setattr(O, "leave_visible_console", lambda: calls.append("check") or True)
    monkeypatch.setattr(O, "serve", lambda *a, **k: calls.append("serve") or 0)
    monkeypatch.setattr(cli, "load_config", lambda: {"paths": {"output": str(tmp_path)}})

    class A:
        cmd, once = "worker", False
    assert cli._jobs(A()) == 0
    assert calls == ["check"]                    # it ends without taking the queue: the hidden one serves it
