"""Speed-ups of the fine pass that must not change any result: the persistent racket worker, the
shared decode (pose + ball), batched racket keypoints and the half-precision option."""
import io
import json
import sys
import threading
from pathlib import Path

import cv2
import numpy as np
import pytest

SRC = str(Path(__file__).resolve().parents[1] / "src")


# ---- racket segmentation worker -------------------------------------------------------------------

def test_serve_replies_ok_and_errors_and_keeps_serving():
    from tennisbio.pose.yolo import serve

    seen = []

    def handler(job):
        if job["frames"] == [-1]:
            raise ValueError("mal")
        seen.append(job)

    inp = io.BytesIO(b'{"video": "a.mp4", "frames": [1, 2], "out": "o.npz"}\n\n'
                     b'{"video": "b.mp4", "frames": [-1], "out": "o.npz"}\n'
                     b'{"video": "c.mp4", "frames": [3], "out": "o.npz"}\n')
    out = io.BytesIO()
    serve(handler, inp, out)
    replies = [json.loads(x) for x in out.getvalue().splitlines()]
    assert [r["ok"] for r in replies] == [True, False, True]
    assert "ValueError: mal" in replies[1]["error"]
    assert [j["video"] for j in seen] == ["a.mp4", "c.mp4"]


# a stand-in worker process: same protocol, writes the frames it was given; frames [-1] raise in
# Python (a reply), frames [-2] kill the process outright (as the iGPU driver crash did)
FAKE = f"""
import json, os, sys
sys.path.insert(0, {SRC!r})
from tennisbio.pose.yolo import serve
out = os.fdopen(os.dup(sys.stdout.fileno()), "wb")
os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
sys.stdout = sys.stderr
print("ruido de una librería")          # must not reach the protocol
def handler(job):
    if job["frames"] == [-2]:
        sys.stderr.write("access violation\\n"); sys.stderr.flush()
        os._exit(3)
    if job["frames"] == [-1]:
        raise RuntimeError("fallo python")
    open(job["out"], "w", encoding="utf-8").write(json.dumps([job["video"], job["frames"], os.getpid()]))
serve(handler, sys.stdin.buffer, out)
"""


def test_worker_persists_between_jobs_and_reports_crash(tmp_path):
    from tennisbio.pose.yolo import SegWorker

    w = SegWorker([sys.executable, "-c", FAKE])
    try:
        ok1 = w.run(tmp_path / "vídeo ñ.mp4", [5, 3, 3], tmp_path / "a.json")
        ok2 = w.run(tmp_path / "v2.mp4", [7], tmp_path / "b.json")
        a, b = (json.loads((tmp_path / n).read_text(encoding="utf-8")) for n in ("a.json", "b.json"))
        assert ok1 == (True, 0, "") and ok2 == (True, 0, "")
        assert a[0].endswith("vídeo ñ.mp4") and a[1] == [3, 5]          # sorted, unique, accents intact
        assert a[2] == b[2]                                              # the same process served both
        ok, code, err = w.run("x.mp4", [-1], tmp_path / "c.json")
        assert not ok and code == 1 and "fallo python" in err and w.alive()
        ok, code, err = w.run("x.mp4", [-2], tmp_path / "d.json")
        assert not ok and code == 3 and "access violation" in err and not w.alive()
        assert w.run("x.mp4", [1], tmp_path / "e.json")[0] is False      # dead: never hangs
    finally:
        w.close()


def test_extract_rackets_falls_back_to_cpu_when_worker_dies(tmp_path, monkeypatch):
    from tennisbio.pose import backend, yolo, yolo_onnx

    monkeypatch.setattr(yolo_onnx, "MODELS_DIR", tmp_path)
    monkeypatch.setattr(backend, "DEFAULT_DEVICE", "dml")
    started = []

    def fake_worker(model, imgsz, device):
        w = yolo.SegWorker([sys.executable, "-c", FAKE], (model, imgsz, device))
        started.append(w)
        yolo._WORKER["w"] = w
        return w

    cpu_calls = []
    monkeypatch.setattr(yolo, "seg_worker", fake_worker)
    monkeypatch.setattr(yolo, "_extract_rackets", lambda v, fr, out, m, sz, dev: cpu_calls.append(dev) or Path(out))
    out = yolo.extract_rackets("x.mp4", [-2], tmp_path / "r.npz")
    assert out == tmp_path / "r.npz" and cpu_calls == ["cpu"]
    flag = tmp_path / "seg_gpu_falla.txt"
    assert flag.exists() and flag.read_text(encoding="utf-8").startswith("codigo 3")
    assert "w" not in yolo._WORKER and not started[0].alive()
    yolo.extract_rackets("x.mp4", [1], tmp_path / "r2.npz")             # flag set: CPU, no worker
    assert cpu_calls == ["cpu", "cpu"] and len(started) == 1


def test_seg_worker_reused_and_restarted(monkeypatch):
    from tennisbio.pose import yolo

    made = []

    class Dummy:
        def __init__(self, cmd, key):
            self.key, self.dead, self.closed = key, False, False
            made.append(self)

        def alive(self):
            return not self.dead

        def close(self):
            self.closed = True

    monkeypatch.setattr(yolo, "SegWorker", Dummy)
    monkeypatch.setattr(yolo, "_WORKER", {"atexit": True})
    a = yolo.seg_worker("m.pt", 960, "dml")
    assert yolo.seg_worker("m.pt", 960, "dml") is a
    b = yolo.seg_worker("m.pt", 640, "dml")                  # other settings: a new one
    assert b is not a and a.closed
    b.dead = True
    c = yolo.seg_worker("m.pt", 640, "dml")                  # ended: started again
    assert c is not b and len(made) == 3


def test_seg_model_loaded_once(monkeypatch):
    from tennisbio.pose import yolo, yolo_onnx

    loads = []

    class FakeOnnx:
        def __init__(self, path, device):
            loads.append(device)

        def segment(self, frame, cls, conf):
            return [np.array([[0, 0], [1, 1]], np.float32)]

    monkeypatch.setattr(yolo_onnx, "YoloOnnx", FakeOnnx)
    monkeypatch.setattr(yolo_onnx, "export_onnx", lambda name, imgsz: Path(__file__))
    monkeypatch.setattr(yolo, "_SEG_MODELS", {})
    f1 = yolo._seg_model("fake-seg.pt", 320, "cpu")
    f2 = yolo._seg_model("fake-seg.pt", 320, "cpu")
    assert f1 is f2 and loads == ["cpu"] and len(f1(np.zeros((4, 4, 3), np.uint8))) == 1


# ---- one decode for pose and ball ------------------------------------------------------------------

@pytest.fixture(scope="module")
def tiny_video(tmp_path_factory):
    p = tmp_path_factory.mktemp("v") / "t.avi"
    w = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"MJPG"), 50, (64, 48))
    rng = np.random.default_rng(0)
    for i in range(23):
        f = rng.integers(0, 255, (48, 64, 3), np.uint8)
        f[:8, :8] = i * 10
        w.write(f)
    w.release()
    return p


def _plain(video):
    cap = cv2.VideoCapture(str(video))
    out = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        out.append(f)
    cap.release()
    return out


def test_capture_frames_same_as_read_loop(tiny_video):
    from tennisbio.io.video import capture_frames

    ref = _plain(tiny_video)
    got = list(capture_frames(tiny_video, prefetch=3))
    assert len(ref) == len(got) == 23 and all(np.array_equal(a, b) for a, b in zip(ref, got))


def test_capture_frames_early_stop_ends_thread(tiny_video):
    from tennisbio.io.video import capture_frames

    before = threading.active_count()
    gen = capture_frames(tiny_video, prefetch=2)
    for i, _ in enumerate(gen):
        if i == 2:
            break
    gen.close()
    assert threading.active_count() <= before


def test_ball_feed_matches_track():
    from tennisbio.ball import BallFeed, BallTracker

    class FakeSess:          # the heatmap peak follows the mean of the newest frame: frame-dependent
        def get_inputs(self):
            return [type("I", (), {"name": "frames"})()]

        def run(self, _, feed):
            x = feed["frames"]
            hm = np.zeros((len(x), 1, 288, 512), np.float32)
            for n in range(len(x)):
                c = int(x[n, -3:].mean() * 400) + 20
                hm[n, 0, 100:104, c:c + 4] = 0.9
            return [hm]

    rng = np.random.default_rng(1)
    frames = [rng.integers(0, 255, (108, 192, 3), np.uint8) for _ in range(11)]
    bt = BallTracker.__new__(BallTracker)
    bt.sess, bt.threshold, bt.batch = FakeSess(), 0.5, 4
    feed = BallFeed(2)
    for f in frames:
        feed.add(f)
    a, b = bt.track(iter(frames), step=2), bt.track_feed(feed)
    assert a.shape == (11, 3) and np.array_equal(a, b, equal_nan=True)


def test_tee_hands_every_frame_once():
    from tennisbio.ball import BallFeed
    from tennisbio.clip_pipeline import _tee

    feed = BallFeed(3)
    frames = [np.full((20, 30, 3), i, np.uint8) for i in range(7)]
    assert len(list(_tee(iter(frames), feed))) == 7
    assert feed.total == 7 and len(feed.small) == 3 and feed.size == (20, 30)


# ---- batched racket keypoints ----------------------------------------------------------------------

class _CropSess:
    """Stand-in RacketPose model: per-sample SimCC peaks from the crop content (batch-independent)."""

    def get_inputs(self):
        return [type("I", (), {"name": "input"})()]

    def run(self, _, feed):
        x = feed["input"]
        self.batches = getattr(self, "batches", []) + [len(x)]
        sx = np.zeros((len(x), 5, 512), np.float32)
        sy = np.zeros((len(x), 5, 512), np.float32)
        for n in range(len(x)):
            for k in range(5):
                v = float(x[n, k % 3, 40 * k:40 * k + 30, 50:90].mean())
                sx[n, k, int(abs(v) * 97) % 512] = 1.0
                sy[n, k, int(abs(v) * 53 + k) % 512] = 0.8
        return [sx, sy]


def test_racket_pose_many_equals_one_by_one():
    from tennisbio.racket_pose import RacketPose

    rp = RacketPose.__new__(RacketPose)
    rp.sess = _CropSess()
    rng = np.random.default_rng(2)
    frames = [rng.integers(0, 255, (120, 160, 3), np.uint8) for _ in range(7)]
    boxes = [[10 + i, 20, 60 + 3 * i, 90] for i in range(7)]
    one = [rp(f, [b]) for f, b in zip(frames, boxes)]
    k, s = rp.many(list(zip(frames, boxes)), batch=3)
    assert rp.sess.batches[-3:] == [3, 3, 1]
    assert np.array_equal(k, np.concatenate([o[0] for o in one])) and np.array_equal(s, np.concatenate([o[1] for o in one]))
    k0, s0 = rp.many([])
    assert k0.shape == (0, 5, 2) and s0.shape == (0, 5)


@pytest.mark.skipif(not (Path(__file__).resolve().parents[1] / "models" / "racketpose.onnx").exists(),
                    reason="sin models/racketpose.onnx")
def test_racket_pose_batch_same_on_real_model_cpu():
    from tennisbio.racket_pose import RacketPose

    rp = RacketPose(Path(__file__).resolve().parents[1] / "models" / "racketpose.onnx", "cpu")
    rng = np.random.default_rng(3)
    frames = [cv2.GaussianBlur(rng.integers(0, 255, (360, 640, 3), np.uint8), (9, 9), 3) for _ in range(5)]
    boxes = [[100 + 10 * i, 80, 220 + 10 * i, 260] for i in range(5)]
    one = np.concatenate([rp(f, [b])[0] for f, b in zip(frames, boxes)])
    k, _ = rp.many(list(zip(frames, boxes)))
    assert np.array_equal(k, one)


# ---- half precision (off by default) --------------------------------------------------------------

def test_fp16_only_when_asked_and_on_dml():
    from tennisbio.config import load_config
    from tennisbio.pose.backend import uses_fp16
    from tennisbio.stages import _fp16_setting

    cfg = load_config()
    # on by default since the model trials on the PC (same strokes found, points within 0.25 px, 2.2x faster)
    assert cfg.get("fp16") is True and uses_fp16(cfg) == (cfg.get("device") == "dml")
    assert not uses_fp16({"fp16": False, "device": "dml"}) and _fp16_setting({"fp16": False, "device": "dml"}) == {}
    assert uses_fp16({"fp16": True, "device": "dml"}) and not uses_fp16({"fp16": True, "device": "cpu"})
    assert _fp16_setting({"fp16": True, "device": "dml"}) == {"fp16": True}


def test_pose_model_fp16_uses_half_copy_on_dml(tmp_path, monkeypatch):
    from tennisbio.pose import backend, variants, yolo_onnx

    (tmp_path / "m_96.onnx").write_bytes(b"x")
    (tmp_path / "m_96_fp16.onnx").write_bytes(b"x")
    monkeypatch.setattr(backend, "MODELS_DIR", tmp_path)
    loaded = []

    class FakeOnnx:
        def __init__(self, path, device):
            loaded.append((Path(path).name, device))

    monkeypatch.setattr(yolo_onnx, "YoloOnnx", FakeOnnx)
    monkeypatch.setattr(variants, "to_fp16", lambda p: Path(p).with_name(Path(p).stem + "_fp16.onnx"))
    assert backend.PoseModel("m", 96, "dml", fp16=True).backend == "onnx-dml-fp16"
    assert backend.PoseModel("m", 96, "dml").backend == "onnx-dml"
    assert backend.PoseModel("m", 96, "cpu", fp16=True).backend == "onnx-cpu"        # only on the iGPU
    assert loaded == [("m_96_fp16.onnx", "dml"), ("m_96.onnx", "dml"), ("m_96.onnx", "cpu")]

    def broken(p):
        raise ImportError("sin onnx")
    monkeypatch.setattr(variants, "to_fp16", broken)
    assert backend.PoseModel("m", 96, "dml", fp16=True).backend == "onnx-dml"        # falls back to fp32


def test_set_device_resets_fp16():
    from tennisbio.pose import backend

    try:
        backend.set_device("dml", True)
        assert backend.DEFAULT_FP16
        backend.set_device("dml")
        assert not backend.DEFAULT_FP16
    finally:
        backend.set_device("cpu")


def test_worker_that_hangs_is_killed_not_waited_forever(tmp_path, monkeypatch):
    import time

    from tennisbio.pose.yolo import SegWorker

    hang = "import sys,time\nfor l in sys.stdin:\n    time.sleep(60)\n"
    monkeypatch.setattr(SegWorker, "timeout_s", staticmethod(lambda n: 1.0))
    w = SegWorker([sys.executable, "-c", hang])
    try:
        t0 = time.time()
        ok, code, err = w.run("x.mp4", [1], tmp_path / "a.json")
        assert not ok and "colgado" in err and time.time() - t0 < 15 and not w.alive()
    finally:
        w.close()
