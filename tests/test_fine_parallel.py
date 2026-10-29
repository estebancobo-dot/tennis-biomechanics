"""The fine pass's windows in several processes (B-4): the same strokes, the time breakdown summed, and a
process that dies leaves its windows to the one-by-one loop."""
import pickle
from pathlib import Path
from types import SimpleNamespace

import pytest

from tennisbio import stages
from tennisbio.catalog import Match, Player


def test_workers_default_by_device(monkeypatch):
    monkeypatch.setattr("os.cpu_count", lambda: 16)
    monkeypatch.setattr(stages, "available_ram_gb", lambda: None)
    assert stages._fine_workers({"device": "dml"}, 50) == 2
    assert stages._fine_workers({"device": "cpu"}, 50) == 1
    assert stages._fine_workers({"device": "dml", "fine_speed": {"workers": 3}}, 50) == 3
    assert stages._fine_workers({"device": "dml"}, 1) == 1                       # one window: one process
    monkeypatch.setattr("os.cpu_count", lambda: 4)
    assert stages._fine_workers({"device": "dml", "fine_speed": {"workers": 3}}, 50) == 1


def test_workers_fit_in_the_free_memory(monkeypatch):
    cfg = {"device": "dml", "fine_speed": {"workers": 3}}
    monkeypatch.setattr("os.cpu_count", lambda: 16)
    assert stages._fine_workers(cfg, 50, free_gb=20) == 3
    assert stages._fine_workers(cfg, 50, free_gb=13) == 2                     # 6 GB each
    assert stages._fine_workers(cfg, 50, free_gb=4) == 1                      # never less than one
    assert stages.available_ram_gb() is None or stages.available_ram_gb() > 0


def test_what_a_process_gets_can_be_sent(tmp_path):
    m = Match("m1", tmp_path / "v.mp4", Player("p", "P"))
    assert pickle.loads(pickle.dumps((m, {"device": "dml"}, str(tmp_path), m.player)))[0].id == "m1"


class FakePool:
    """ProcessPoolExecutor in this process (the patches reach the workers)."""
    die_at = None

    def __init__(self, n, mp_context=None, initializer=None, initargs=()):
        initializer(*initargs)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def submit(self, fn, job):
        f = SimpleNamespace()
        if FakePool.die_at is not None and job[0] >= FakePool.die_at:
            def boom():
                raise RuntimeError("A process in the process pool was terminated abruptly")
            f.result = boom
        else:                                  # its own module state, as in another process
            saved = [(d, dict(d)) for d in (stages._TIMES, stages._COUNTS, stages._GATE)]
            r = fn(job)
            for d, v in saved:
                d.clear()
                d.update(v)
            f.result = lambda: r
        return f


@pytest.fixture
def fake(monkeypatch, tmp_path):
    import concurrent.futures as cf
    monkeypatch.setattr(cf, "ProcessPoolExecutor", FakePool)
    monkeypatch.setattr(cf, "as_completed", lambda fs: list(fs))
    monkeypatch.setattr(stages, "_fine_models", lambda ctx: (None, None, None, {}, None, []))
    monkeypatch.setattr(stages, "load_onsets", lambda ctx: [])
    for name, obj in (("court.json", []), ("score.json", {})):
        stages._write(tmp_path / name, obj)

    def one(ctx, p, g, *a):
        if g[0]["t"] == 3:
            raise ValueError("ventana mala")
        stages._TIMES["pose"] = stages._TIMES.get("pose", 0) + 1.0
        stages._GATE["passed"] += 1
        stages._GATE["reasons"]["bola"] = stages._GATE["reasons"].get("bola", 0) + 1
        ctx.log(f"ventana {g[0]['t']}")
        return [{"match_time_s": c["t"]} for c in g]
    monkeypatch.setattr(stages, "_fine_one", one)
    FakePool.die_at = None
    return tmp_path


def _run(tmp_path, groups):
    logs, got = [], []
    ctx = SimpleNamespace(match=Match("m1", tmp_path / "v.mp4", Player("p", "P")), cfg={}, dir=tmp_path, log=logs.append)
    stages._TIMES.clear()
    stages._GATE.clear()
    stages._GATE.update(passed=0, gated=0, off=0, reasons={}, seconds_gated=0.0)
    left = stages._fine_parallel(ctx, None, groups, 2, (1.0, 1.0, False, "k"), got.append)
    return left, got, logs


def test_results_and_breakdown_come_back(fake):
    groups = [[{"t": 1}], [{"t": 2}, {"t": 2.5}], [{"t": 3}], [{"t": 4}]]
    left, got, logs = _run(fake, groups)
    assert left == []
    assert sorted(s["match_time_s"] for r in got for s in r["strokes"]) == [1, 2, 2.5, 4]
    assert [e["t"] for r in got for e in r["errors"]] == [3]                     # one bad window, not the match
    assert stages._TIMES["pose"] == 3.0 and stages._GATE["passed"] == 3 and stages._GATE["reasons"] == {"bola": 3}
    assert "ventana 4" in logs


def test_a_dead_process_leaves_its_windows(fake):
    FakePool.die_at = 2
    left, got, logs = _run(fake, [[{"t": 1}], [{"t": 2}], [{"t": 4}], [{"t": 5}]])
    assert left == [2, 3] and len(got) == 2
    assert any("se hacen una a una" in line for line in logs)


def test_real_processes_start_and_answer(tmp_path):
    """Spawned processes import the package, build their context and models, and send back a window's error."""
    for name, obj in (("court.json", []), ("score.json", {})):
        stages._write(tmp_path / name, obj)
    m = Match("m1", tmp_path / "v.mp4", Player("p", "P"))
    logs, got = [], []
    ctx = SimpleNamespace(match=m, cfg={"fine_pass": {"window_s": 1.0}, "racket_face": {"enabled": False}},
                          dir=tmp_path, log=logs.append)
    left = stages._fine_parallel(ctx, m.player, [[{"t": 5.0}], [{"t": 9.0}]], 2, (1.0, 1.0, False, "k"), got.append)
    assert left == [] and len(got) == 2, logs
    assert all(r["errors"] and r["strokes"] == [] for r in got)                # no video here: an error each
