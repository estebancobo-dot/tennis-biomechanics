"""Stages at the same time (players on the iGPU while score does OCR on the CPU) and the players
stage's reader thread: same results as one after the other."""
import json
import threading
import time

import numpy as np
import pytest

from tennisbio import pipeline
from tennisbio.catalog import Match, Player


def make_ctx(tmp_path, cfg=None, log=None):
    video = tmp_path / "v.mp4"
    if not video.exists():
        video.write_bytes(b"0" * 10)
    return pipeline.Context(Match("m1", video, Player("p", "P")), cfg if cfg is not None else {}, tmp_path / "out",
                            log=log or (lambda *_: None))


@pytest.fixture
def dag(monkeypatch):
    """a → (g on the gpu, c on the cpu) → z. g and c meet at a barrier when they run at the same time."""
    monkeypatch.setattr(pipeline, "STAGES", {})
    st = {"events": [], "active": 0, "max_active": 0, "fail": None, "barrier": threading.Barrier(2, timeout=5),
          "wait": True}
    lock = threading.Lock()

    def body(name, meet=False):
        def fn(ctx):
            with lock:
                st["events"].append(("start", name))
                st["active"] += 1
                st["max_active"] = max(st["max_active"], st["active"])
            try:
                ctx.log(f"  hola desde {name}")
                if meet and st["wait"]:
                    st["barrier"].wait()             # proves both run at once (raises after 5 s otherwise)
                    time.sleep(0.3)
                else:
                    time.sleep(0.05)
                if st["fail"] == name:
                    raise RuntimeError(f"{name} falla")
                ctx.path(f"{name}.txt").write_text(name)
                return {"n": name}
            finally:
                with lock:
                    st["active"] -= 1
                    st["events"].append(("end", name))
        return fn

    pipeline.stage("a", "1", outputs=("a.txt",))(body("a"))
    pipeline.stage("g", "1", deps=("a",), outputs=("g.txt",), resource="gpu")(body("g", meet=True))
    pipeline.stage("c", "1", deps=("a",), outputs=("c.txt",), resource="cpu")(body("c", meet=True))
    pipeline.stage("z", "1", deps=("g", "c"), outputs=("z.txt",))(body("z"))
    return st


def _pos(events, kind, name):
    return events.index((kind, name))


def test_gpu_and_cpu_stages_run_at_the_same_time_in_dependency_order(tmp_path, dag):
    lines = []
    done = pipeline.run(make_ctx(tmp_path, log=lines.append))
    assert sorted(done) == ["a", "c", "g", "z"] and done[0] == "a" and done[-1] == "z"
    ev = dag["events"]
    assert dag["max_active"] == 2                                     # g and c overlapped
    assert _pos(ev, "end", "a") < min(_pos(ev, "start", "g"), _pos(ev, "start", "c"))
    assert _pos(ev, "start", "z") > max(_pos(ev, "end", "g"), _pos(ev, "end", "c"))
    m = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert set(m) == {"a", "g", "c", "z"} and m["g"]["summary"] == {"n": "g"}
    # what ran at the same time is counted once in the total
    assert pipeline.total_seconds(m) == pytest.approx(sum(e["seconds"] for e in m.values()) - m["g"].get("overlap_s", 0)
                                                      - m["c"].get("overlap_s", 0))
    assert m["g"].get("overlap_s", 0) + m["c"].get("overlap_s", 0) > 0
    # the lines of a stage in a thread carry its name; the others as before
    assert "  [g] hola desde g" in lines and "  [c] hola desde c" in lines and "  hola desde a" in lines
    assert pipeline.run(make_ctx(tmp_path)) == []                      # all up to date


def test_disabled_runs_one_after_the_other_in_the_old_order(tmp_path, dag):
    dag["wait"] = False
    done = pipeline.run(make_ctx(tmp_path, cfg={"pipeline": {"parallel": False}}))
    assert done == ["a", "g", "c", "z"]
    assert dag["max_active"] == 1
    assert not any("overlap_s" in e for e in json.loads((tmp_path / "out" / "manifest.json").read_text()).values())


def test_same_resource_never_runs_together(tmp_path, dag):
    dag["wait"] = False
    pipeline.STAGES["g"].resource = lambda cfg: "cpu"                 # pose on the CPU (no iGPU)
    assert pipeline.resource("g", {}) == "cpu"
    pipeline.run(make_ctx(tmp_path))
    assert dag["max_active"] == 1


def test_an_error_stops_new_stages_but_the_running_one_finishes(tmp_path, dag):
    dag["fail"] = "c"
    dag["barrier"] = threading.Barrier(2, timeout=5)
    lines = []
    with pytest.raises(RuntimeError, match="c falla"):
        pipeline.run(make_ctx(tmp_path, log=lines.append))
    m = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert set(m) == {"a", "g"}                                       # g finished and was recorded; z never started
    assert ("start", "z") not in dag["events"]
    assert any("c falló" in ln for ln in lines)
    dag["fail"], dag["wait"] = None, False
    assert sorted(pipeline.run(make_ctx(tmp_path))) == ["c", "z"]     # the next run goes on from there


def test_an_error_in_an_exclusive_stage_raises_as_before(tmp_path, dag):
    dag["fail"] = "a"
    with pytest.raises(RuntimeError, match="a falla"):
        pipeline.run(make_ctx(tmp_path))
    assert dag["events"] == [("start", "a"), ("end", "a")]


def test_overlap_counts_the_union_once():
    assert pipeline._overlap((0, 10), []) == 0
    assert pipeline._overlap((0, 10), [(2, 4), (3, 6), (8, 20)]) == pytest.approx(6)
    assert pipeline._overlap((5, 6), [(0, 4)]) == 0


def test_real_stages_players_and_score_are_paired_only_on_the_igpu():
    from tennisbio import stages  # noqa: F401  (registers the stages)
    assert pipeline.resource("score", {}) == "cpu"
    assert pipeline.resource("players", {"device": "dml"}) == "gpu"
    assert pipeline.resource("players", {"device": "cpu"}) == "cpu"
    assert set(pipeline.STAGES["players"].deps) == set(pipeline.STAGES["score"].deps) == {"scenes", "court"}
    # every other stage still runs alone
    assert {n for n in pipeline.STAGES if pipeline.STAGES[n].resource is not None} == {"players", "score"}


def test_default_config_has_parallel_on():
    from tennisbio.config import load_config
    assert pipeline.parallel_enabled(load_config()) is True
    assert pipeline.parallel_enabled({}) is True
    assert pipeline.parallel_enabled({"pipeline": {"parallel": False}}) is False


# --- reader thread (io.video.read_ahead)

def test_read_ahead_keeps_order_and_stops_early():
    from tennisbio.io.video import read_ahead

    state = {"closed": False, "made": 0}

    def source():
        try:
            for i in range(1000):
                state["made"] += 1
                yield i
        finally:
            state["closed"] = True                                   # where read_frames kills its ffmpeg

    stats = {}
    assert list(read_ahead(lambda: iter(range(50)), prefetch=3, stats=stats)) == list(range(50))
    assert stats["busy_s"] >= 0
    got = []
    for x in read_ahead(source, prefetch=3):
        got.append(x)
        if x == 4:
            break
    assert got == [0, 1, 2, 3, 4]
    assert state["closed"] and state["made"] < 20                    # stopped, not read to the end
    assert not any(t.name == "read_ahead" and t.is_alive() for t in threading.enumerate())


def test_read_ahead_hands_errors_to_the_caller():
    from tennisbio.io.video import read_ahead

    def source():
        yield 1
        raise ValueError("vídeo roto")

    out = []
    with pytest.raises(ValueError, match="vídeo roto"):
        for x in read_ahead(source):
            out.append(x)
    assert out == [1]


def test_read_ahead_stops_when_the_caller_fails():
    from tennisbio.io.video import read_ahead

    state = {"closed": False}

    def source():
        try:
            yield from range(10**6)
        finally:
            state["closed"] = True

    with pytest.raises(KeyError):
        for x in read_ahead(source, prefetch=2):
            if x == 3:
                raise KeyError(x)
    assert state["closed"]


# --- players stage: same output with the reader thread and the appearance thread

def test_yolo_prepared_input_gives_the_same_result():
    from tennisbio.pose.yolo_onnx import YoloOnnx

    m = YoloOnnx.__new__(YoloOnnx)
    m.size, m.device = 64, "cpu"

    def infer(x):                     # two people whose position depends on the image content
        out = np.zeros((1, 56, 10), np.float32)
        v = float(x.mean())
        out[0, :4, 0] = [20 + 10 * v, 30, 10, 20]
        out[0, :4, 1] = [40, 30 + 5 * v, 8, 16]
        out[0, 4, :2] = 0.9
        out[0, 5:, :2] = 32 + v
        return [out]
    m.infer = infer
    img = np.random.default_rng(0).integers(0, 255, (36, 64, 3), dtype=np.uint8)
    a, b = m.pose(img), m.pose(img, prepared=m.prepare(img))
    assert all(np.array_equal(x, y) for x, y in zip(a, b)) and len(a[0]) == 2


def test_players_stage_output_is_the_same_as_one_frame_at_a_time(tmp_path, monkeypatch):
    from tennisbio import stages
    from tennisbio.io.video import VideoInfo
    from tennisbio.pose.yolo import _objects, appearance

    fps, n = 10, 120
    shots = [{"start": 0, "end": 40, "main_camera": True}, {"start": 40, "end": 55, "main_camera": False},
             {"start": 55, "end": n, "main_camera": True}]
    out = tmp_path / "out"
    out.mkdir()
    (out / "scenes.json").write_text(json.dumps({"fps": fps, "shots": shots}))
    rng = np.random.default_rng(1)
    video = rng.integers(0, 255, (n + 5, 54, 96, 3), dtype=np.uint8)

    info = VideoInfo(tmp_path / "v.mp4", 192, 108, fps, n / fps, "h264", False, None, None)

    def fake_read(info_, start=0.0, duration=None, width=None, fps=None, hwaccel=None):
        a = round(start * fps)
        yield from video[a:a + round(duration * fps) + 2]           # ffmpeg can hand over a frame or two more

    class Model:
        def prepare(self, frame):
            return float(frame.mean())

        def predict(self, frame, conf=0.3, prepared=None):
            v = float(frame.mean())
            assert prepared is None or prepared == v
            k = int(v) % 3
            b = np.array([[5 + i * 20, 5, 20 + i * 20, 50] for i in range(k)], np.float32).reshape(k, 4)
            kp = np.full((k, 17, 2), v, np.float32)
            return b, kp, np.full((k, 17), 0.5, np.float32)

    monkeypatch.setattr(stages, "probe", lambda p: info)
    monkeypatch.setattr(stages, "read_frames", fake_read)
    monkeypatch.setattr(stages, "_pose_detector", lambda cfg: Model())
    ctx = pipeline.Context(Match("m1", tmp_path / "v.mp4", Player("p", "P")), {"cheap_pass": {"fps": fps, "imgsz": 96}},
                           out, log=lambda *_: None)
    ctx._prog["stage"] = "players"
    res = stages.st_players(ctx)

    # reference: the stage as it was (one frame at a time, everything in this thread)
    ref = {"boxes": [], "kps": [], "confs": [], "feats": [], "idx": []}
    main = np.zeros(n, bool)
    for s in shots:
        main[s["start"]:s["end"]] = s["main_camera"]
    m = Model()
    for i in np.flatnonzero(main):
        fr = video[i]
        b, k, c = m.predict(fr)
        ref["feats"].append(np.array([appearance(fr, bb) for bb in b], np.float32).reshape(len(b), 32))
        ref["boxes"].append(b * 2.0); ref["kps"].append(k * 2.0); ref["confs"].append(c); ref["idx"].append(i)
    with np.load(out / "players.npz", allow_pickle=True) as z:
        assert z["frames"].tolist() == ref["idx"] and res["frames"] == 40 + 65
        for key in ("boxes", "kps", "confs", "feats"):
            assert len(z[key]) == len(ref[key])
            assert all(np.array_equal(x, y) for x, y in zip(z[key], _objects(ref[key])))
    assert {"wall_min", "model_min", "read_min", "wait_min", "appearance_min"} <= set(res)
