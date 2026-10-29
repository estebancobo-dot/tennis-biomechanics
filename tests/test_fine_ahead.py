"""The ball computed ahead on the CPU while the pose runs on the iGPU (fine_ahead, fine_speed.ball_ahead):
every window's ball is computed exactly once, by the worker or by the main thread, where the fine pass
reads it; the main thread waits at most for the window the worker is finishing; nothing changes when it
is off, on the CPU, without the ball model or with a single window. Also the overlap counter of the
windows and the lazy float input of the ball model (same heatmaps as before)."""
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from tennisbio.fine_ahead import BallAhead, ahead_enabled


def _drive(n, work_s=0.02, job_s=0.01, gap=1, fail=()):
    """Main loop as in stages._fine: claim each window, then 'pose' it (sleep); the worker 'computes the
    ball' (sleep). Returns the ahead object, who did each window and the order the worker took them."""
    lock = threading.Lock()
    done_by, worker_order = {}, []

    def job(i):
        with lock:
            worker_order.append(i)
        time.sleep(job_s)
        if i in fail:
            raise RuntimeError("fallo")
        with lock:
            assert i not in done_by
            done_by[i] = "worker"

    ahead = BallAhead(n, job, gap=gap).start()
    for i in range(n):
        if not ahead.claim(i):
            with lock:
                assert i not in done_by                      # never twice
                done_by[i] = "main"
        time.sleep(work_s)
    ahead.close()
    return ahead, done_by, worker_order


def test_each_window_once_worker_from_the_end_main_from_the_start():
    ahead, done_by, order = _drive(12)
    assert sorted(done_by) == list(range(12))
    assert done_by[0] == "main" and done_by[11] == "worker"
    assert order == sorted(order, reverse=True)              # the worker walks backwards
    w = [i for i, who in done_by.items() if who == "worker"]
    m = [i for i, who in done_by.items() if who == "main"]
    assert max(m) < min(w)                                   # they meet once, in the middle
    assert ahead.done == sorted(w)


def test_the_worker_leaves_the_next_window_to_the_main_thread():
    # gap 1: never the window right after the one the main thread is on
    ahead, done_by, _ = _drive(2, work_s=0.05, job_s=0.0, gap=5)
    assert done_by == {0: "main", 1: "main"}
    ahead, done_by, _ = _drive(4, work_s=0.05, job_s=0.0, gap=1)
    assert done_by[0] == "main" and done_by[1] == "main"


@pytest.mark.parametrize("n", [0, 1])
def test_no_or_single_window_the_worker_does_nothing(n):
    ahead, done_by, order = _drive(n)
    assert order == [] and all(v == "main" for v in done_by.values()) and len(done_by) == n


def test_claim_waits_for_the_window_the_worker_is_finishing():
    started, release = threading.Event(), threading.Event()

    def job(i):
        started.set()
        release.wait(5)
    ahead = BallAhead(3, job, gap=0).start()
    assert started.wait(5)                                   # the worker is on window 2
    threading.Timer(0.2, release.set).start()
    assert ahead.claim(2) is True and ahead.waited >= 0.15   # waited, then found it done
    ahead.close()


def test_a_failed_window_is_left_to_the_main_thread_and_the_worker_stops_after_three():
    ahead, done_by, order = _drive(10, work_s=0.05, job_s=0.0, fail={9, 8, 7})
    assert all(done_by[i] == "main" for i in (7, 8, 9))     # computed by the main thread, as without it
    assert sorted(ahead.errors) == [7, 8, 9] and order == [9, 8, 7]     # then the worker gave up
    assert sorted(done_by) == list(range(10))


def test_close_finishes_the_window_being_done():
    seen = []

    def job(i):
        time.sleep(0.2)
        seen.append(i)
    ahead = BallAhead(5, job, gap=0).start()
    time.sleep(0.05)
    ahead.close()
    assert seen == [4] and ahead.state[4] == "done" and ahead.state[3] == "todo"


def test_enabled_only_on_the_igpu_with_the_ball_and_two_windows():
    on = {"device": "dml"}
    assert ahead_enabled(on, 2, True)
    assert not ahead_enabled({"device": "cpu"}, 5, True)                  # pose on the CPU: same cores
    assert not ahead_enabled({"device": "openvino"}, 5, True)
    assert not ahead_enabled(on, 5, False)                               # no ball model
    assert not ahead_enabled(on, 1, True) and not ahead_enabled(on, 0, True)
    assert not ahead_enabled({**on, "fine_speed": {"ball_ahead": False}}, 5, True)


# ---- windows that overlap -------------------------------------------------------------------------

def test_window_overlap_seconds():
    from tennisbio.stages import window_overlap_s

    assert window_overlap_s([]) == 0
    assert window_overlap_s([(0.0, 3.6, "near")]) == 0                                       # single window
    # two windows of one long rally cut by the 10 s limit, at the start of the video (t0 clipped to 0)
    assert window_overlap_s([(0.0, 11.0, "near"), (9.0, 5.0, "near")]) == pytest.approx(2.0)
    # the same times on the two ends do not count (different players, different poses)
    assert window_overlap_s([(0.0, 11.0, "near"), (9.0, 5.0, "far")]) == 0
    # a window inside another, and one touching the end of the video
    assert window_overlap_s([(10.0, 10.0, "far"), (12.0, 2.0, "far"), (19.0, 3.0, "far")]) == pytest.approx(3.0)


# ---- the stage: the worker's ball is where the main thread reads it --------------------------------

class FakeBall:
    calls: list = []

    made: list = []

    def __init__(self, path=None, device="dml", threshold=0.5, threads=None, batch=8, **k):
        self.device, self.threads = device, threads
        FakeBall.made.append((device, batch, threads))

    def track(self, frames, step=1):
        FakeBall.calls.append((self.device, threading.current_thread().name))
        n = sum(1 for _ in frames)
        time.sleep(0.05)
        return np.tile([100.0, 200.0, 0.9], (n, 1))


@pytest.fixture
def tiny_video(tmp_path):
    import cv2
    p = tmp_path / "tiny.avi"
    w = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"MJPG"), 50, (64, 48))
    for i in range(10):
        w.write(np.full((48, 64, 3), i * 10, np.uint8))
    w.release()
    return p


def _fine_ctx(tmp_path, device, n_cands, fine_speed=None):
    from tennisbio import stages
    model = tmp_path / "balltrack.onnx"
    model.write_bytes(b"x")
    cands = [{"t": 20.0 * (k + 1), "side": "near", "target": True} for k in range(n_cands)]
    for name, obj in (("candidates.json", cands), ("court.json", []), ("score.json", {})):
        stages._write(tmp_path / name, obj)
    cfg = {"fine_pass": {"window_s": 1.0}, "device": device, "ball": {"onnx": str(model)},
           "racket_face": {"enabled": False}, "fine_speed": {"workers": 1, **(fine_speed or {})}}
    logs = []
    ctx = SimpleNamespace(cfg=cfg, log=logs.append, path=lambda n: tmp_path / n, video=tmp_path / "match.mp4",
                          progress=lambda *a, **k: None, match=None)
    return ctx, logs


def _patch(monkeypatch, tiny_video):
    """Cut = a copy of a tiny video; the main thread's window = the gate's ball read (computing it on its
    own model when missing, as stages._gate_passes does)."""
    import shutil

    from tennisbio import ball as ball_mod
    from tennisbio import clip_pipeline, stages

    def fake_cut(video, t0, dur, dest, *a, **k):
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(tiny_video, dest)
        return dest
    monkeypatch.setattr(stages, "cut_window", fake_cut)
    monkeypatch.setattr(ball_mod, "BallTracker", FakeBall)
    monkeypatch.setattr("tennisbio.pose.backend.set_device", lambda *a: None)
    seen = {}

    def fake_one(ctx, p, group, pre, post, interlaced, ph, court, score, onsets, scenes, ball, *rest):
        t0, dur, wid = stages._window_of(group, pre, post)
        clip = stages.cut_window(ctx.video, t0, dur, ctx.path("windows") / f"{wid}.mp4")
        track, took, *_ = clip_pipeline.window_ball(clip, clip.with_name(f"{clip.stem}_{ph}.npz"), ball)
        seen[wid] = (track, took)
        time.sleep(0.1)                                      # the pose
        return []
    monkeypatch.setattr(stages, "_fine_one", fake_one)
    FakeBall.calls, FakeBall.made = [], []
    return seen


def test_fine_with_the_worker_computes_each_ball_once_and_the_same(tmp_path, monkeypatch, tiny_video):
    from tennisbio import stages
    seen = _patch(monkeypatch, tiny_video)
    ctx, _ = _fine_ctx(tmp_path, "dml", 8, {"ball_ahead_threads": 2})
    out = stages._fine(ctx, SimpleNamespace(hand="right", height_m=1.84), lambda c: True, "strokes.json")
    assert len(seen) == 8 and len(FakeBall.calls) == 8                      # each window's ball once
    on_cpu = [c for c in FakeBall.calls if c[0] == "cpu"]
    assert on_cpu and all(name == "bola-en-paralelo" for _, name in on_cpu)
    assert len(on_cpu) < 8                                                # the main thread did the first ones
    assert out["counts"]["windows_ball_ahead"] == len(on_cpu)
    assert "bola_en_paralelo_cpu" in out["seconds"] and "espera_bola_en_paralelo" in out["seconds"]
    for track, took in seen.values():                                     # same track wherever it was made
        assert np.array_equal(track, np.tile([100.0, 200.0, 0.9], (10, 1)))
    assert out["counts"]["overlap_s"] == 0
    assert ("cpu", 1, 2) in FakeBall.made           # one frame per pass on the CPU (≈ 0.5 GB, not ≈ 3), 2 threads


@pytest.mark.parametrize("device,fs,n", [("cpu", {}, 6), ("dml", {"ball_ahead": False}, 6), ("dml", {}, 1),
                                          ("dml", {}, 0)])
def test_fine_without_the_worker_is_as_before(tmp_path, monkeypatch, tiny_video, device, fs, n):
    from tennisbio import stages
    seen = _patch(monkeypatch, tiny_video)
    ctx, _ = _fine_ctx(tmp_path, device, n, fs)
    out = stages._fine(ctx, SimpleNamespace(hand="right", height_m=1.84), lambda c: True, "strokes.json")
    assert len(seen) == n and all(c[0] == device for c in FakeBall.calls) and len(FakeBall.calls) == n
    assert "windows_ball_ahead" not in out["counts"] and "bola_en_paralelo_cpu" not in out["seconds"]


def test_fine_worker_failure_falls_back_to_the_igpu(tmp_path, monkeypatch, tiny_video):
    from tennisbio import stages
    seen = _patch(monkeypatch, tiny_video)

    class Broken(FakeBall):
        def __init__(self, path=None, device="dml", *a, **k):
            if device == "cpu":
                raise RuntimeError("sin CPU")
            super().__init__(path, device, *a, **k)
    from tennisbio import ball as ball_mod
    monkeypatch.setattr(ball_mod, "BallTracker", Broken)
    ctx, _ = _fine_ctx(tmp_path, "dml", 6)
    out = stages._fine(ctx, SimpleNamespace(hand="right", height_m=1.84), lambda c: True, "strokes.json")
    assert len(seen) == 6 and all(c[0] == "dml" for c in FakeBall.calls) and len(FakeBall.calls) == 6
    assert out["counts"]["windows_ball_ahead"] == 0 and any("bola en paralelo" in w for w in out["warnings"])


def test_ball_said_in_the_window_log():
    from tennisbio import stages
    stages._BALL_AHEAD.clear()
    stages._BALL_AHEAD["w1"] = 12.4
    assert stages._ball_said({"ball_s": 0.0}, "w1") == "12 s en paralelo (CPU)"
    assert stages._ball_said({"ball_s": 7.2}, "w2") == "7 s"
    stages._BALL_AHEAD.clear()


# ---- the ball model's input made lazily: identical heatmap inputs ----------------------------------

def test_ball_track_feed_lazy_input_is_identical(monkeypatch):
    from tennisbio import ball as ball_mod
    from tennisbio.ball import SEQ, BallFeed, BallTracker

    rng = np.random.default_rng(0)
    feed = BallFeed(1)
    for _ in range(21):                                   # 2 full batches + a short one
        feed.add(rng.integers(0, 255, (96, 160, 3), np.uint8))
    inputs = []

    class Sess:
        def get_inputs(self):
            return [SimpleNamespace(name="frames")]

        def run(self, _, feed_):
            x = feed_["frames"]
            inputs.append(x.copy())
            return [np.zeros((len(x), 1, ball_mod.H, ball_mod.W), np.float32)]
    bt = BallTracker.__new__(BallTracker)
    bt.sess, bt.threshold, bt.batch, bt.static = Sess(), 0.5, 8, False
    bt.track_feed(feed)
    small = feed.small
    bg = np.moveaxis(ball_mod.median_background(small).astype(np.float32) / 255.0, -1, 0)
    norm = [np.moveaxis(f.astype(np.float32) / 255.0, -1, 0) for f in small]          # as before
    ref = [np.stack([np.concatenate([bg] + [norm[max(0, i - k)] for k in range(SEQ - 1, -1, -1)])
                     for i in range(s, min(len(small), s + 8))]) for s in range(0, len(small), 8)]
    assert len(inputs) == len(ref) == 3
    for a, b in zip(inputs, ref):
        assert np.array_equal(a, b)


def test_ball_session_threads_reach_onnxruntime(monkeypatch, tmp_path):
    from tennisbio.pose import estimator

    got = {}

    class FakeSess:
        def __init__(self, path, sess_options=None, providers=None):
            got["threads"], got["providers"] = sess_options.intra_op_num_threads, providers
    monkeypatch.setattr(estimator.ort, "InferenceSession", FakeSess)
    estimator._ort_session(str(tmp_path / "m.onnx"), "cpu", threads=3)
    assert got == {"threads": 3, "providers": ["CPUExecutionProvider"]}
    estimator._ort_session(str(tmp_path / "m.onnx"), "cpu")
    assert got["threads"] == 0                                               # onnxruntime's default


def test_base_on_the_court_and_crossover_steps_say_why_they_matter():
    from tennisbio.explain import COACH
    for k in ("loaded.base_court_m", "impact.base_court_m", "finish.base_court_m", "stroke.feet_move_m",
              "footwork.crossover_steps"):
        why, src = COACH[k]
        assert why.endswith(".") and len(why) > 40 and src


def test_audit_base_row_has_its_explanation(monkeypatch):
    """The audit item «3. Pies y desplazamiento · Base y anchura de la base sobre la pista» warns when no
    measured key of the row has a COACH entry: every key it can find there now has one."""
    from tennisbio.audit import _matches, parse_matrix, planned_keys
    from tennisbio.explain import COACH
    row = next(r for r in parse_matrix() if r["element"].startswith("Base y anchura de la base"))
    planned = planned_keys()
    keys = [k for k in planned for i in row["ids"] if _matches(i, k)]
    assert keys and all(k in COACH or k.split(".")[-1] in COACH for k in keys)
