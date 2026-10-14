"""Hybrid fine-pass pose (YOLO finds people, RTMPose-x refines the big ones, with feet), its cache and
the foot-point helpers: all with fake models (no network, no ONNX files), and nothing changes when off."""
import numpy as np
import pytest

from tennisbio.footpoints import (feet_on_court_ground, foot_direction_deg, ground_point, has_feet, tracked_feet,
                                  with_feet)
from tennisbio.pipeline import load_npz
from tennisbio.pose import hybrid
from tennisbio.pose.hybrid import HybridPose, extract_fine, extract_hybrid, fine_pose_model, pose_cache_tag
from tennisbio.skeleton import COCO17, FOOT_NAMES, HALPE26, Skeleton

BOXES = np.array([[100, 100, 180, 300],      # 200 px: the near player
                  [400, 120, 460, 270],      # 150 px: as tall (≥ 0.6 × 200)
                  [600, 50, 620, 100]],      # 50 px: a line judge far away
                 np.float32)


class FakeYolo:
    backend = "onnx-cpu"

    def __init__(self, boxes=BOXES):
        self.boxes, self.calls = boxes, []

    def prepare(self, img):
        return ("prepared", img.shape)

    def predict(self, img, conf=0.3, prepared=None):
        self.calls.append(prepared)
        n = len(self.boxes)
        return self.boxes.copy(), np.full((n, 17, 2), 5.0, np.float32), np.full((n, 17), 0.5, np.float32)


class FakeRtm:
    def __init__(self):
        self.calls = []

    def __call__(self, img, boxes):
        boxes = np.asarray(boxes)
        self.calls.append(boxes.copy())
        k = np.repeat(np.arange(26, dtype=np.float32)[None, :, None], len(boxes), 0).repeat(2, 2) + boxes[:, :1, None]
        return k, np.full((len(boxes), 26), 0.9, np.float32)


def test_rtmpose_only_on_the_target_sized_people():
    rtm = FakeRtm()
    m = HybridPose(FakeYolo(), rtm)
    b, k, c, fk, fc = m.predict_feet(np.zeros((360, 640, 3), np.uint8))
    assert len(rtm.calls) == 1 and np.array_equal(rtm.calls[0], BOXES[:2])
    assert b.shape == (3, 4) and k.shape == (3, 17, 2) and c.shape == (3, 17)
    assert fk.shape == (3, 6, 2) and fc.shape == (3, 6)
    # the big ones: RTMPose's body points and its 6 foot points (Halpe26 20-25)
    assert k[0, 3, 0] == 3 + 100 and k[1, 16, 1] == 16 + 400 and c[0, 0] == pytest.approx(0.9)
    assert fk[0, 0, 0] == 20 + 100 and fk[1, 5, 0] == 25 + 400 and (fc[:2] == pytest.approx(0.9))
    # the small one keeps YOLO's points and has no feet
    assert (k[2] == 5).all() and (c[2] == 0.5).all() and (fc[2] == 0).all()


def test_contract_matches_pose_model_and_prepared_input_is_passed():
    y = FakeYolo()
    m = HybridPose(y, FakeRtm())
    img = np.zeros((360, 640, 3), np.uint8)
    out = m.predict(img, conf=0.3)
    assert len(out) == 3
    m.predict(img, prepared=m.prepare(img))
    assert y.calls[-1] == ("prepared", img.shape) and "hybrid" in m.backend


def test_caller_targets_pick_only_their_detection():
    rtm = FakeRtm()
    m = HybridPose(FakeYolo(), rtm)
    img = np.zeros((360, 640, 3), np.uint8)
    _, k, _, _, fc = m.predict_feet(img, targets=[[405, 125, 462, 268]])      # the tracked box ~ detection 1
    assert np.array_equal(rtm.calls[-1], BOXES[1:2])
    assert (k[0] == 5).all() and fc[1].min() > 0 and (fc[0] == 0).all()
    _, k, _, _, fc = m.predict_feet(img, targets=[[0, 0, 10, 10]])              # overlaps nobody: no RTMPose
    assert len(rtm.calls) == 1 and (fc == 0).all()


def test_nobody_in_the_frame():
    rtm = FakeRtm()
    b, k, c, fk, fc = HybridPose(FakeYolo(np.zeros((0, 4), np.float32)), rtm).predict_feet(np.zeros((8, 8, 3), np.uint8))
    assert b.shape == (0, 4) and k.shape == (0, 17, 2) and c.shape == (0, 17) and fk.shape == (0, 6, 2) and fc.shape == (0, 6)
    assert rtm.calls == []


def test_hybrid_cache_is_the_yolo_cache_plus_feet(tmp_path, monkeypatch):
    import tennisbio.pose.yolo as yolo
    monkeypatch.setattr(yolo, "_fps", lambda v: 50.0)
    frames = [np.zeros((360, 640, 3), np.uint8)] * 3
    out = extract_hybrid("x.mp4", tmp_path / "w.npz", frames=frames, model=HybridPose(FakeYolo(), FakeRtm()),
                         progress=False, roi=(10, 20, 640, 360))
    d = load_npz(out)
    assert {"fps", "n", "boxes", "kps", "confs", "feats", "feet", "feet_confs"} <= set(d)
    assert float(d["fps"]) == 50.0 and int(d["n"]) == 3 and has_feet(d)
    assert d["boxes"][0].shape == (3, 4) and d["kps"][0].shape == (3, 17, 2) and d["feats"][0].shape == (3, 32)
    assert d["feet"][0].shape == (3, 6, 2) and d["feet_confs"][0].shape == (3, 6)
    # roi offsets: boxes, body and feet back in full-frame coordinates
    assert d["boxes"][0][0, 0] == 110 and d["kps"][0][2, 0, 1] == 25 and d["feet"][0][0, 0, 1] == 20 + 100 + 20


def test_config_switch_on_by_default(tmp_path, monkeypatch):
    from tennisbio.config import load_config

    cfg = load_config()
    # on since 14-10 (measured on the PC): the window caches get the hybrid tag
    assert cfg["fine_pass"]["pose_model"] == "hybrid"
    assert fine_pose_model(cfg) == "hybrid" and pose_cache_tag(cfg) == ["hybrid"]
    assert fine_pose_model({"fine_pass": {"pose_model": "Hybrid"}}) == "hybrid"
    assert pose_cache_tag({"fine_pass": {"pose_model": "yolo"}}) == [] and pose_cache_tag({}) == []
    assert fine_pose_model({"fine_pass": {"pose_model": "rtmpose"}}) == "yolo"      # typo: never stops
    assert fine_pose_model({}) == "yolo"

    called = []
    import tennisbio.pose.yolo as yolo
    monkeypatch.setattr(yolo, "extract", lambda *a, **k: called.append(("yolo", a, k)) or "y")
    monkeypatch.setattr(hybrid, "extract_hybrid", lambda *a, **k: called.append(("hybrid", a, k)) or "h")
    keep, stats = np.ones(4, bool), {}
    assert extract_fine("v.mp4", "c.npz", imgsz=960, progress=False, roi=None, frames=None, cfg={},
                        prefetch=False, keep=keep, stats=stats) == "y"
    # yolo: exactly pose.yolo.extract's call (positional arguments in its own order, the rest passed on)
    assert called[-1][1] == ("v.mp4", "c.npz", "yolo11m-pose.pt", 960, 1, False, None, None)
    assert called[-1][2]["prefetch"] is False and called[-1][2]["keep"] is keep and called[-1][2]["stats"] is stats
    assert "model" not in called[-1][2] and stats["pose_model"] == "yolo"
    assert extract_fine("v.mp4", "c.npz", cfg={"fine_pass": {"pose_model": "hybrid"}}, keep=keep) == "h"
    assert called[-1][0] == "hybrid" and called[-1][2]["keep"] is keep and called[-1][2]["prefetch"] is True
    # the caller's choice (run_clip: the far side is always yolo) wins over the config
    assert extract_fine("v.mp4", "c.npz", cfg={"fine_pass": {"pose_model": "hybrid"}}, model_name="yolo") == "y"


class _ImgYolo:
    """Fake YOLO whose people depend only on the image (as test_fine_ranges._Model), with prepare."""

    def __init__(self):
        self.calls, self.prepared = 0, []

    def prepare(self, img):
        return ("prep", float(img.mean()), img.shape)

    def predict(self, img, conf=0.3, prepared=None):
        self.calls += 1
        v = float(img.mean())
        assert prepared is None or prepared == ("prep", v, img.shape)
        self.prepared.append(prepared is not None)
        k = int(v) % 3 + 1
        b = np.array([[5 + i * 20, 5, 20 + i * 20, 40] for i in range(k)], np.float32).reshape(k, 4)
        return b, np.full((k, 17, 2), v, np.float32), np.full((k, 17), 0.5, np.float32)


def test_hybrid_extract_honours_keep_prefetch_and_frames(tmp_path, monkeypatch):
    """The hybrid model runs in pose.yolo.extract's own loop: the frames handed by the caller (tee'd with
    the ball: read once, never decoded again), only the kept ones posed, the input prepared ahead with
    prefetch (same output as without), the model's frames and time in stats."""
    import tennisbio.io.video as vio
    import tennisbio.pose.yolo as yolo

    def no_decode(*a, **k):
        raise AssertionError("decoded again")
    monkeypatch.setattr(yolo, "_fps", lambda v: 50.0)
    monkeypatch.setattr(vio, "capture_frames", no_decode)
    rng = np.random.default_rng(1)
    frames = [rng.integers(0, 255, (48, 64, 3), np.uint8) for _ in range(30)]
    keep = np.zeros(30, bool)
    keep[4:11] = keep[20:24] = True
    outs = {}
    for prefetch in (False, True):
        y, rtm, stats, seen = _ImgYolo(), FakeRtm(), {}, []
        gen = (seen.append(i) or f for i, f in enumerate(frames))          # a generator, read once
        out = extract_hybrid("x.mp4", tmp_path / f"h{prefetch}.npz", frames=gen, prefetch=prefetch, keep=keep,
                             stats=stats, progress=False, model=HybridPose(y, rtm))
        assert seen == list(range(30))
        assert y.calls == keep.sum() == stats["frames"] and stats["model_s"] >= 0
        assert y.prepared == [prefetch] * int(keep.sum())
        outs[prefetch] = d = load_npz(out)
        assert int(d["n"]) == 30 and has_feet(d)
        for i in range(30):
            assert len(d["feet"][i]) == len(d["boxes"][i]) == len(d["feet_confs"][i]) == len(d["feats"][i])
            if not keep[i]:
                assert d["boxes"][i].shape == (0, 4) and d["feet"][i].shape == (0, 6, 2)
                assert d["feet_confs"][i].shape == (0, 6)
            else:
                assert len(d["boxes"][i]) and (d["feet_confs"][i] > 0).all()   # all the same size: all refined
        assert len(rtm.calls) == keep.sum()
    for key in ("boxes", "kps", "confs", "feats", "feet", "feet_confs"):
        assert all(np.array_equal(a, b) for a, b in zip(outs[False][key], outs[True][key])), key


def test_model_loaded_once(monkeypatch):
    import tennisbio.pose.backend as backend

    hybrid._cached.cache_clear()
    loads = []
    monkeypatch.setattr(backend, "pose_model", lambda n, s, d: loads.append(("yolo", n, s, d)) or FakeYolo())
    monkeypatch.setattr(hybrid, "_rtmpose", lambda u, s, d: loads.append(("rtm", u, s, d)) or FakeRtm())
    cfg = {"fine_pass": {"pose": "performance"}, "models": {"poses": {"performance": {"url": "u", "input_size": [288, 384]}}}}
    try:
        a = hybrid.hybrid_model(device="cpu", cfg=cfg)
        b = hybrid.hybrid_model("yolo11m-pose.pt", device="cpu", cfg=cfg)
        assert a is b and len(loads) == 2
        assert loads[0] == ("yolo", "yolo11m-pose", 960, "cpu") and loads[1] == ("rtm", "u", (288, 384), "cpu")
    finally:
        hybrid._cached.cache_clear()


# ---- skeleton with feet ---------------------------------------------------------------------------

def test_skeleton_foot_names():
    assert FOOT_NAMES == ["left_big_toe", "right_big_toe", "left_small_toe", "right_small_toe", "left_heel", "right_heel"]
    sk = Skeleton("coco17", "right")
    assert len(sk) == 17 and not sk.has_feet and sk.names == COCO17           # unchanged by default
    with pytest.raises(KeyError):
        sk["dom_heel"]
    f = Skeleton("coco17", "right", feet=True)
    assert len(f) == 23 and f.has_feet and f["left_big_toe"] == 17 and f["right_heel"] == 22
    assert f["dom_heel"] == 22 and f["non_big_toe"] == 17 and f["dom_wrist"] == sk["dom_wrist"]
    lf = Skeleton("coco17", "left", feet=True)
    assert lf["dom_heel"] == 21 and lf["non_small_toe"] == 20
    h = Skeleton("halpe26", "right", feet=True)
    assert len(h) == 26 and h.names == HALPE26 and h["dom_heel"] == 25


# ---- foot points ----------------------------------------------------------------------------------

def _cache_with_feet():
    return {"feet": np.array([np.full((2, 6, 2), 1.0), np.full((1, 6, 2), 2.0)], dtype=object),
            "feet_confs": np.array([np.full((2, 6), 0.8), np.full((1, 6), 0.7)], dtype=object)}


def test_tracked_feet_and_merge():
    fk, fc = tracked_feet(_cache_with_feet(), np.array([1, -1]))
    assert fk.shape == (2, 6, 2) and (fk[0] == 1).all() and np.isnan(fk[1]).all() and fc[0, 0] == 0.8 and fc[1].sum() == 0
    fk, fc = tracked_feet({"kps": None}, np.array([0, 0]))      # YOLO cache: no feet
    assert np.isnan(fk).all() and not has_feet({"kps": None}) and not has_feet(None)
    img, conf = np.zeros((2, 17, 2)), np.ones((2, 17))
    fcf = np.array([[0.9] * 6, [0.1] * 6])
    m, mc = with_feet(img, conf, np.ones((2, 6, 2)), fcf)
    assert m.shape == (2, 23, 2) and mc.shape == (2, 23) and (m[0, 17:] == 1).all() and np.isnan(m[1, 17:]).all()


def _frame_kp(sk):
    kp = np.full((len(sk), 2), np.nan)
    kp[sk["dom_ankle"]] = [10, 90]
    kp[sk["non_ankle"]] = [30, 90]
    kp[sk["dom_heel"]], kp[sk["dom_big_toe"]], kp[sk["dom_small_toe"]] = [10, 100], [10, 110], [12, 110]
    return kp


def test_ground_point_heel_toe_or_ankle():
    sk = Skeleton("coco17", "right", feet=True)
    kp = _frame_kp(sk)
    assert np.allclose(ground_point(kp, sk, "dom"), [10.5, 105])          # heel-toe middle
    assert np.allclose(ground_point(kp, sk, "non"), [30, 90])             # no foot points: the ankle
    plain = Skeleton("coco17", "right")
    assert np.allclose(ground_point(kp[:17], plain, "dom"), [10, 90])      # YOLO skeleton: the ankle, as now
    kp[sk["non_ankle"]] = np.nan
    assert ground_point(kp, sk, "non") is None


def test_feet_on_court_ground_and_direction():
    sk = Skeleton("coco17", "right", feet=True)
    kp = _frame_kp(sk)[None]
    H = np.eye(3)
    d, n = feet_on_court_ground(kp, 0, sk, H)
    assert np.allclose(d, [10.5, 105]) and np.allclose(n, [30, 90])
    assert feet_on_court_ground(kp, 5, sk, H) is None
    assert foot_direction_deg(kp, 0, sk, H, "dom") == pytest.approx(np.degrees(np.arctan2(10, 1)))
    assert foot_direction_deg(kp, 0, sk, H, "non") is None
    assert foot_direction_deg(kp[:, :17], 0, Skeleton("coco17"), H, "dom") is None
