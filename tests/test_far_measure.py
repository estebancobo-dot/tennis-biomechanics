"""#219 (09-11): a second far pose, for measuring only (fine_pass.far_measure_refind).

About half of her far strokes had no pose around contact (audit «Golpes del fondo»: position 75/44/59/66 %, target
≥ 80 %): the far follow lost her at the window start. The follow that searches for her again (fine_pass.far_refind)
raised the measures but lowered the detection on F3Set (request 156: 455/517, precision 0.93, from 466 and 0.94),
since the pose also takes part in confirming strokes. Now the window is analysed as before, and only the confirmed
far strokes with no keypoint of hers within 0.3 s of contact take their far-reliable measures (position,
displacement, contact height) from a second far pose with that search (cache _f2m): the strokes, their contact,
type, identity, side and confirmation never change."""
from types import SimpleNamespace

import numpy as np
import pytest

from test_fine_ranges import FPS, _synth_pose, _synth_video  # noqa: F401

N, CONTACT = 300, 150
GAP = (CONTACT - 25, CONTACT + 26)          # 0.5 s without her either side of contact in the first far pose
# her court frame → image: 20 px per metre, her baseline at image row 350 (where the synthetic ankles stand)
HM = np.array([[20.0, 0, 300], [0, -20.0, 350], [0, 0, 1]])


def _without(pose, a, b):
    """The pose with nobody detected in frames [a, b)."""
    for t in range(a, b):
        pose["boxes"][t] = np.zeros((0, 4), np.float32)
        pose["kps"][t] = np.zeros((0, 17, 2), np.float32)
        pose["confs"][t] = np.zeros((0, 17), np.float32)
        pose["feats"][t] = np.zeros((0, 32), np.float32)
    return pose


@pytest.fixture
def window(tmp_path, monkeypatch):
    """A far (or near) window of 300 frames at 50 fps; her strokes come from the detector (source spotter)."""
    from tennisbio import clip_pipeline, stages
    from tennisbio.pose import yolo
    from tennisbio.pipeline import savez_atomic

    (tmp_path / "windows").mkdir()
    clip = _synth_video(tmp_path / "windows" / "w000010000_6000.avi", N)
    calls = []
    real = clip_pipeline.run_clip

    def spy(*a, **k):
        calls.append(k)
        return real(*a, **k)
    monkeypatch.setattr(clip_pipeline, "run_clip", spy)
    monkeypatch.setattr(stages, "cut_window", lambda *a, **k: clip)
    monkeypatch.setattr(stages, "court_at", lambda court, t, s=1.0: (HM, 20.0))
    monkeypatch.setattr(stages, "_check_court", lambda clip_, t, H, pitch, min_score=0.5: (H, pitch, {"ok": True}))
    monkeypatch.setattr(stages, "far_start", lambda clip_, H, search_s=2.0, step=5: dict(
        roi="follow", init_box=np.array([255, 135, 345, 355], float), max_bottom=1000.0, init_frame=50,
        far_H=np.asarray(H, float)))
    monkeypatch.setattr("tennisbio.pose.backend.set_device", lambda *a: None)
    monkeypatch.setattr(yolo, "extract_follow", lambda *a, **k: pytest.fail("the pose caches are given"))

    def no_rackets(video_, frames, out, imgsz=960, **k):            # near end: no racket outline anywhere
        frames = sorted({int(f) for f in frames})
        savez_atomic(out, frames=np.array(frames), polys=yolo._objects([[] for _ in frames]))
        return out
    monkeypatch.setattr(yolo, "extract_rackets", no_rackets)

    def run(side, measure, pose=None, refind_pose=None, swings=(CONTACT,), times=(CONTACT,)):
        stages._GATE.clear()
        stages._GATE.update(passed=0, gated=0, off=0, reasons={}, seconds_gated=0.0, dropped=[])
        calls.clear()
        for f in clip.parent.glob("*.npz"):
            f.unlink()
        cache = clip.with_name(f"{clip.stem}_abc{'_far' if side == 'far' else ''}.npz")
        savez_atomic(cache, **(pose if pose is not None else _synth_pose(N, swings)))
        if refind_pose is not None:
            from tennisbio.clip_pipeline import FAR_MEASURE_TAG
            savez_atomic(cache.with_name(f"{cache.stem}_{FAR_MEASURE_TAG}.npz"), **refind_pose)
        ctx = SimpleNamespace(cfg={"device": "cpu", "fine_pass": {"height_scale": "pose", "far_measure_refind": measure}},
                              log=lambda *_: None, path=lambda nm: tmp_path / nm, video=tmp_path / "v.mp4",
                              match=SimpleNamespace(id="m", surface="", player=SimpleNamespace(id="x")))
        p = SimpleNamespace(hand="right", height_m=1.84, id="x", forehand_grip_close_deg=0.0, backhand_grip_close_deg=0.0)
        t0 = 10.0
        group = [{"t": t0 + f / FPS, "side": side, "source": "spotter", "kind": "forehand", "target": True,
                  "identity": True} for f in times]
        out = stages._fine_one(ctx, p, group, CONTACT / FPS, (N - CONTACT) / FPS, False, "abc", [], {}, np.zeros(0),
                               {"fps": 1, "shots": []}, None, None, None, {"enabled": False})
        return out, list(calls), [dict(x) for x in stages._GATE.get("dropped", [])]
    return run


def _decided(strokes):
    """What the detection decides: which strokes, their contact, type, identity, side and confirmation."""
    return [(s["stroke_id"], s["impact_frame"], s["match_time_s"], s["stroke"], s.get("stroke_source"), s["side"],
             s.get("identity"), s.get("target"), s["impact_source"]) for s in strokes]


def test_detection_is_identical_with_the_measure_pass_on_and_off(window):
    """(1) The same strokes, contacts and confirmations, on windows with and without her pose at contact."""
    # no swing in the pose: her contacts come from the detector alone (a far stroke kept by the ball or the detector)
    lost = lambda: _without(_synth_pose(N, ()), *GAP)
    full = lambda: _synth_pose(N, ())
    for pose in (lost, full):
        off, _, drop_off = window("far", False, pose(), full())
        on, calls, drop_on = window("far", True, pose(), full())
        assert off and _decided(on) == _decided(off) and drop_on == drop_off
        main = [k for k in calls if not k.get("pose_only")]
        assert len(main) == 1 and "far_H" not in main[0] and "init_frame" not in main[0]    # far_refind stays off
    # two strokes in a window, one of them without her pose: still the same list
    two = lambda: _without(_synth_pose(N, ()), *GAP)
    off, _, _ = window("far", False, two(), _synth_pose(N, (CONTACT, 260)), (CONTACT, 260), (CONTACT, 260))
    on, calls, _ = window("far", True, two(), _synth_pose(N, (CONTACT, 260)), (CONTACT, 260), (CONTACT, 260))
    assert len(off) == 2 and _decided(on) == _decided(off)
    assert sum(bool(k.get("pose_only")) for k in calls) == 1          # the second pose once per window


def test_a_far_stroke_without_pose_at_contact_gets_its_position_from_the_second_pose(window):
    """(2) Lost around contact in the first pose: no position; the second pose (with the search) gives it."""
    from tennisbio.clip_pipeline import FAR_MEASURE_TAG
    lost = lambda: _without(_synth_pose(N, (CONTACT,)), *GAP)
    off, _, _ = window("far", False, lost(), _synth_pose(N, (CONTACT,)))
    assert off[0].get("court_pos_m") is None and "far_measure_source" not in off[0]
    on, calls, _ = window("far", True, lost(), _synth_pose(N, (CONTACT,)))
    s = on[0]
    assert s["court_pos_m"] is not None and s["far_measure_source"] == "refind"
    assert "court_pos_m" in s["far_measure_refind"] and "contact_height_pct" in s["far_measure_refind"]
    assert s["metrics"]["contact_height_pct"] is not None
    assert not {"stance", "stance_width_m", "stance_angle_deg"} & set(s)          # never at the far end
    m = [k for k in calls if k.get("pose_only")]
    assert len(m) == 1 and m[0]["follow_tag"] == FAR_MEASURE_TAG and m[0]["init_frame"] == 50
    assert m[0]["far_H"] is not None and m[0]["ball"] is None and m[0]["rackets"] is False
    # with her pose at contact nothing is asked for nor changed
    on, calls, _ = window("far", True, _synth_pose(N, ()), _synth_pose(N, ()))
    assert on and not any(k.get("pose_only") for k in calls) and "far_measure_source" not in on[0]


def test_the_second_pose_never_overwrites_and_finds_nothing_when_she_is_not_there(window):
    lost = lambda: _without(_synth_pose(N, (CONTACT,)), *GAP)
    on, calls, _ = window("far", True, lost(), lost())          # the search does not find her either
    assert on[0].get("court_pos_m") is None and "far_measure_source" not in on[0]
    assert sum(bool(k.get("pose_only")) for k in calls) == 1


def test_near_windows_untouched(window):
    """(3) The near end never runs the second pose, whatever the switch, and measures as before."""
    lost = lambda: _without(_synth_pose(N, (CONTACT,)), *GAP)
    off, calls_off, _ = window("near", False, lost())
    on, calls_on, _ = window("near", True, lost())
    assert not any(k.get("pose_only") or k.get("follow_tag") for k in calls_off + calls_on)
    assert len(calls_on) == len(calls_off) == 1
    assert _decided(on) == _decided(off) and all("far_measure_source" not in s for s in on)
    assert [s.get("court_pos_m") for s in on] == [s.get("court_pos_m") for s in off]


def test_the_switch_is_on_by_default_and_the_refind_off():
    from tennisbio.config import load_config
    fp = load_config().get("fine_pass") or {}
    assert fp.get("far_measure_refind") is True and fp.get("far_refind") is False


def test_pose_at_contact():
    from tennisbio.stages import pose_at_contact
    img = np.full((100, 17, 2), np.nan)
    run = SimpleNamespace(img=img, fps=50.0)
    assert not pose_at_contact(run, 50)
    img[66] = 1.0                                               # 16 frames = 0.32 s after: outside
    assert not pose_at_contact(run, 50)
    img[65] = 1.0                                               # 0.30 s: inside
    assert pose_at_contact(run, 50)
