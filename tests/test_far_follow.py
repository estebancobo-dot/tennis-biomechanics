"""#219 (08-11): a far stroke kept by the fine pass has her pose around its contact whenever she is visible.

PC 08-11 (analisis_completo.log, auditoria_partidos.md): 19/56/52/45 of her far strokes «sin pose en la ventana»;
the far windows where none of her keypoints was found (altura nan px) were posed «a 960 px por perderla» in all
but 2-3 of their frames: the follow crop lost her at the start and, growing up to 16 × her height, made her
~70 px in the model's input, too small for YOLO to see her again. The follow now searches the far half again
(as far_start does) while it has lost her, and restarts from the frame where far_start found her."""
from types import SimpleNamespace

import numpy as np
import pytest

from test_fine_ranges import FPS, _synth_pose, _synth_video  # noqa: F401

W, H = 1280, 720
HER = np.array([880, 150, 920, 240], float)          # 90 px tall, standing still at the far baseline
WRONG = np.array([300, 150, 340, 240], float)        # where the follow was told to start (no one there)


class _SizeLimitedModel:
    """Finds the white player in a crop only when she is ≥ 110 px tall in the model's input (YOLO does not see
    the far player at ~60-90 px: CLAUDE.md, «Lado lejano»)."""

    def __init__(self, imgsz):
        self.imgsz = imgsz

    def predict(self, crop, conf=0.25, prepared=None):
        ys, xs = np.nonzero(crop[..., 0] > 128)
        if not len(ys):
            return np.zeros((0, 4)), np.zeros((0, 17, 2)), np.zeros((0, 17))
        h = ys.max() + 1 - ys.min()
        if h * self.imgsz / max(crop.shape[:2]) < 110:
            return np.zeros((0, 4)), np.zeros((0, 17, 2)), np.zeros((0, 17))
        b = np.array([[xs.min(), ys.min(), xs.max() + 1, ys.max() + 1]], np.float32)
        k = np.repeat(((b[:, :2] + b[:, 2:]) / 2)[:, None], 17, axis=1)
        return b, k, np.full((1, 17), 0.9, np.float32)


@pytest.fixture
def far_frames(monkeypatch):
    from tennisbio.io import video as vio
    from tennisbio.pose import backend, yolo
    import tennisbio.court_metrics as cm

    frame = np.zeros((H, W, 3), np.uint8)
    x0, y0, x1, y1 = HER.astype(int)
    frame[y0:y1, x0:x1] = 255
    frames = [frame] * 40
    monkeypatch.setattr(vio, "capture_frames", lambda p, prefetch=4: iter(frames))
    monkeypatch.setattr(yolo, "_fps", lambda v: FPS)
    monkeypatch.setattr(backend, "pose_model", lambda name, imgsz=640, *a, **k: _SizeLimitedModel(imgsz))
    searched = []

    def fake_detect(fr, roi=None, **k):              # the far half searched at 1920 px: she is seen there
        searched.append(1)
        ys, xs = np.nonzero(fr[..., 0] > 128)
        return np.array([[xs.min(), ys.min(), xs.max() + 1, ys.max() + 1]], float) if len(ys) else np.zeros((0, 4))
    monkeypatch.setattr(yolo, "detect_people", fake_detect)
    monkeypatch.setattr(cm, "far_roi", lambda Hm, shape: None)
    monkeypatch.setattr(cm, "pick_far_player", lambda boxes, Hm: boxes[0] if len(boxes) else None)
    return SimpleNamespace(searched=searched)


def _near_her(z, t):
    b = z["boxes"][t]
    return len(b) and np.abs((b[:, 0] + b[:, 2]) / 2 - (HER[0] + HER[2]) / 2).min() < 10


def test_lost_far_player_is_found_again_by_searching_the_far_half(tmp_path, far_frames):
    from tennisbio.pose import yolo

    # as before (no court): lost from the first frame, the crop grows until she is too small to be seen again
    st_old = {}
    z = np.load(yolo.extract_follow("v.mp4", tmp_path / "old.npz", WRONG, stats=st_old), allow_pickle=True)
    assert not any(_near_her(z, t) for t in range(40))
    assert st_old["frames_960"] >= 37 and not far_frames.searched
    # with the court: searched again after FOLLOW_RESEARCH_AFTER frames without her, then followed in a small crop
    st = {}
    z = np.load(yolo.extract_follow("v.mp4", tmp_path / "new.npz", WRONG, stats=st, far_H=np.eye(3)), allow_pickle=True)
    first = yolo.FOLLOW_RESEARCH_AFTER
    assert all(_near_her(z, t) for t in range(first, 40))
    assert st["far_searches"] == st["far_refound"] == 1 == len(far_frames.searched)
    assert st["frames_960"] <= first


def test_the_crop_grows_less_with_the_search(tmp_path, far_frames, monkeypatch):
    """Nobody to be found (another shot): the search is retried every FOLLOW_RESEARCH_EVERY frames and the crop
    never becomes the whole frame, where she would be too small to be seen."""
    from tennisbio.io import video as vio
    from tennisbio.pose import backend, yolo

    empty = [np.zeros((H, W, 3), np.uint8)] * 40
    monkeypatch.setattr(vio, "capture_frames", lambda p, prefetch=4: iter(empty))
    sizes = []

    class M(_SizeLimitedModel):
        def predict(self, crop, conf=0.25, prepared=None):
            sizes.append(max(crop.shape[:2]))
            return super().predict(crop, conf, prepared)
    monkeypatch.setattr(backend, "pose_model", lambda name, imgsz=640, *a, **k: M(imgsz))
    st = {}
    yolo.extract_follow("v.mp4", tmp_path / "e.npz", HER, stats=st, far_H=np.eye(3))
    a, e = yolo.FOLLOW_RESEARCH_AFTER, yolo.FOLLOW_RESEARCH_EVERY
    assert st["far_searches"] == len(range(a, 40, e)) and st["far_refound"] == 0
    assert max(sizes) <= 4 * 90 * (1 + 0.5 * yolo.FOLLOW_MAX_GROWTH)


def test_find_far_player_at_gives_the_frame(tmp_path, monkeypatch):
    import cv2

    from tennisbio.pose import yolo
    import tennisbio.court_metrics as cm

    p = tmp_path / "v.avi"
    w = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"MJPG"), 25, (64, 48))
    for i in range(100):
        w.write(np.full((48, 64, 3), i * 2, np.uint8))
    w.release()
    monkeypatch.setattr(yolo, "detect_people", lambda fr, roi=None, **k: (np.array([[1, 2, 3, 4]], float)
                                                                         if fr.mean() >= 35 else np.zeros((0, 4))))
    monkeypatch.setattr(cm, "far_roi", lambda Hm, shape: None)
    monkeypatch.setattr(cm, "pick_far_player", lambda boxes, Hm: boxes[0] if len(boxes) else None)
    f, box = yolo.find_far_player_at(p, np.eye(3), search_s=2.0, step=5)
    assert f == 20 and list(box) == [1, 2, 3, 4]              # first searched frame where she is seen
    assert list(yolo.find_far_player(p, np.eye(3))) == [1, 2, 3, 4]           # unchanged API
    assert yolo.find_far_player_at(p, np.eye(3), search_s=0.5, step=5) is None


def test_far_start_gives_the_frame_and_the_court(monkeypatch):
    from tennisbio import stages
    from tennisbio.pose import yolo

    monkeypatch.setattr(yolo, "find_far_player_at", lambda clip, Hm, s=2.0, st=5: (12, np.array([1, 2, 3, 4.0])))
    Hm = np.array([[1.0, 0, 0], [0, -20.0, 600], [0, 0, 1]])
    fi = stages.far_start("w.mp4", Hm)
    assert fi["roi"] == "follow" and fi["init_frame"] == 12 and np.array_equal(fi["far_H"], Hm)
    assert list(fi["init_box"]) == [1, 2, 3, 4] and fi["max_bottom"] == pytest.approx(600 - 20 * 11.885)
    assert stages.far_start("w.mp4", None) is None


# ---- run_clip: the far stroke has her pose at its contact ------------------------------------------------

def _far_pose_with_decoy(n, swings, until):
    """She is 200 px to the left before `until` (she ran); a person of her size stands where she is found
    later (a ball kid crouched behind her start), with other clothes, then leaves."""
    pose = _synth_pose(n, swings)
    for t in range(until):
        her_b = pose["boxes"][t] - np.float32([200, 0, 200, 0])
        her_k = pose["kps"][t] - np.float32([200, 0])
        decoy = np.float32([[255, 135, 345, 355]])
        pose["boxes"][t] = np.vstack([her_b, decoy])
        pose["kps"][t] = np.vstack([her_k, pose["kps"][t]])          # a body like hers, standing still
        pose["confs"][t] = np.vstack([pose["confs"][t], np.full((1, 17), 0.9, np.float32)])
        other = np.zeros((1, 32), np.float32)
        other[0, 0] = 1.0
        pose["feats"][t] = np.vstack([pose["feats"][t], other])
    return pose


def test_far_stroke_has_pose_at_contact_when_tracked_from_where_she_was_found(tmp_path):
    from tennisbio.clip_pipeline import FOLLOW_CACHE_TAG, run_clip
    from tennisbio.pipeline import savez_atomic

    n, swings, found = 300, (150,), 100
    video = _synth_video(tmp_path / "w.avi", n)
    pose = _far_pose_with_decoy(n, swings, found)
    savez_atomic(tmp_path / "w.npz", **pose)                       # the former follow's cache
    savez_atomic(tmp_path / f"w_{FOLLOW_CACHE_TAG}.npz", **pose)   # the new follow's (same detections here)
    init = pose["boxes"][found][0]
    kw = dict(rackets=False, init_mode="near", log=lambda *_: None, side="far", roi="follow", init_box=init)
    old = run_clip(video, tmp_path / "w.npz", **kw)
    # as before: her start box applied at the window's first frame, where the other person stands: tracked on him,
    # she is never taken back (other clothes) and the stroke has no pose of hers at its contact
    assert old.boxes[150] is None
    new = run_clip(video, tmp_path / "w.npz", init_frame=found, far_H=np.eye(3), **kw)
    assert all(new.boxes[t] is not None for t in range(found, n))      # her, from where she was found
    s = min(new.strokes, key=lambda s: abs(s.impact_frame - 150))
    assert abs(s.impact_frame - 150) <= 4
    assert any((s.phases.get(k) or {}).get("frame") is not None
               for k in ("takeback", "loaded", "acceleration", "finish", "recovery"))    # the audit's «con pose»


def test_near_windows_unchanged(tmp_path, monkeypatch):
    """The near end keeps its cache, its pose call and its arguments: no follow, no new keys."""
    from tennisbio import clip_pipeline, stages
    from tennisbio.pipeline import savez_atomic
    from tennisbio.pose import yolo

    n, swings = 300, (60, 150, 240)
    video = _synth_video(tmp_path / "w.avi", n)
    savez_atomic(tmp_path / "w.npz", **_synth_pose(n, swings))
    monkeypatch.setattr(yolo, "extract_follow", lambda *a, **k: pytest.fail("no follow at the near end"))
    a = clip_pipeline.run_clip(video, tmp_path / "w.npz", rackets=False, init_mode="near", log=lambda *_: None)
    b = clip_pipeline.run_clip(video, tmp_path / "w.npz", rackets=False, init_mode="near", log=lambda *_: None,
                               far_H=np.eye(3))           # the court alone changes nothing without the follow
    assert [s.impact_frame for s in a.strokes] == [s.impact_frame for s in b.strokes] and len(a.strokes) == 3
    for x, y in zip(a.strokes, b.strokes):
        assert x.phases == y.phases and x.metrics == y.metrics
    assert not list(tmp_path.glob("w_f*.npz"))

    # the stage: near windows get no start frame nor court for a follow
    calls = []
    clip = tmp_path / "windows" / "w000010000_12000.mp4"
    monkeypatch.setattr(stages, "cut_window", lambda *a, **k: clip)
    monkeypatch.setattr(stages, "court_at", lambda court, t, s=1.0: (np.eye(3), 20.0))
    monkeypatch.setattr(stages, "_gate_passes", lambda *a, **k: {"passed": True, "possible": []})
    monkeypatch.setattr(stages, "far_start", lambda clip, Hm, search_s=2.0, step=5:
                        dict(roi="follow", init_box=[1, 2, 3, 4], max_bottom=500.0, init_frame=7, far_H=np.eye(3)))
    monkeypatch.setattr(clip_pipeline, "run_clip", lambda *a, **k: calls.append(k) or SimpleNamespace(
        timing={}, strokes=[], fps=FPS, stats={}))
    monkeypatch.setattr("tennisbio.pose.backend.set_device", lambda *a: None)
    # the far refind is off by default since 09-11 (request 156); this test checks the path when it is on
    ctx = SimpleNamespace(cfg={"fine_pass": {"height_scale": "pose", "far_refind": True}, "device": "cpu"}, log=lambda *_: None,
                          path=lambda nm: tmp_path / nm, video=tmp_path / "v.mp4")
    for side in ("near", "far"):
        stages._fine_one(ctx, SimpleNamespace(hand="right", height_m=1.84), [{"t": 12.0, "side": side}], 2.0, 1.0,
                         False, "abc", [], [], np.zeros(0), {"fps": 1, "shots": []}, None, None, None, {})
    near, far = calls
    assert not {"init_frame", "far_H", "roi", "init_box", "side"} & set(near)
    assert far["init_frame"] == 7 and far["roi"] == "follow" and far["side"] == "far"
    assert np.array_equal(far["far_H"], np.eye(3))



def test_the_far_refind_is_off_by_default():
    """09-11, request 156: on, F3Set fell to 455/517 found and precision 0.93 (from 466 and 0.94)."""
    from tennisbio.config import load_config
    assert (load_config().get("fine_pass") or {}).get("far_refind") is False
