"""Speed of the fine pass without changing what it measures (14-10):

- pose_prefetch: the pose model's input prepared in a reader thread and the appearance histograms in
  another (as the cheap pass): the same output as one frame at a time.
- racket_near_candidates: the racket outline (slow model) only where a stroke that can be kept reads
  it: the kept strokes see exactly the same outlines.
- pose_ranges: the pose only on the frames a possible stroke uses (fine_gate.possible_impacts and
  pose_keep); every impact the full pass can confirm lies inside them.
- ball.static_batch: the ball model with a fixed batch (DirectML compiles it once): the same track.
"""
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from tennisbio.ball import ball_hits, clean_track
from tennisbio.fine_gate import CONFIRM_TOL_S, gate_window, pose_keep, possible_impacts
from tennisbio.impacts import fuse, fuse_with_ball

FPS, FW, FH = 50.0, 1920, 1080


# ---- possible impacts and the frames kept for the pose ---------------------------------------------

def _path(waypoints, n):
    f = [w[0] for w in waypoints]
    t = np.full((n, 3), np.nan)
    idx = np.arange(f[0], f[-1] + 1)
    t[idx, 0] = np.interp(idx, f, [w[1] for w in waypoints])
    t[idx, 1] = np.interp(idx, f, [w[2] for w in waypoints])
    t[idx, 2] = 1.0
    return t


@pytest.mark.parametrize("side", ["near", "far"])
def test_every_impact_the_full_pass_confirms_is_inside_a_possible_range(side):
    """The real confirmation logic on random windows (as test_fine_gate): the gate passes exactly when
    there are possible impacts, and every impact that confirms a candidate lies inside one of them, so
    the frames posed around them (pose_keep) always contain it."""
    rng = np.random.default_rng(3 if side == "near" else 5)
    n, box, checked = 250, np.array([0, 0, FW, FH], float), 0
    for _ in range(400):
        k = rng.integers(2, 6)
        fr = np.sort(rng.choice(np.arange(1, n - 1), k, replace=False))
        wp = [(0, *rng.uniform([100, 100], [1800, 1000]))] + \
             [(int(f), *rng.uniform([100, 100], [1800, 1000])) for f in fr] + [(n - 1, *rng.uniform([100, 100], [1800, 1000]))]
        tr = _path(wp, n)
        for _ in range(rng.integers(0, 4)):
            a = rng.integers(0, n)
            tr[a:a + rng.integers(1, 40)] = np.nan
        tr[rng.random(n) < 0.15] = np.nan
        swings = np.sort(rng.choice(np.arange(n), rng.integers(0, 5), replace=False))
        onsets = np.sort(rng.uniform(0, n / FPS, rng.integers(0, 6)))
        ct = clean_track(tr, width=FW)
        impacts = fuse_with_ball(fuse(swings, FPS, onsets), FPS, ball_hits(ct, FH, FPS), ~np.isnan(ct[:, 0]), [box] * n,
                                 wrist_speed=rng.uniform(0, 4, n), side=side)
        if side == "far":
            impacts = [i for i in impacts if "ball" in i.source]
        cands = list(rng.uniform(0, n, 3))
        pos = possible_impacts(tr, FW, FH, FPS, cands, side, 0.0)
        d = gate_window(tr, FW, FH, FPS, cands, side, margin_s=0.0)
        assert d["passed"] == bool(pos)
        keep = pose_keep(n, pos, FPS)
        for i in impacts:
            if any(abs(i.frame - c) <= CONFIRM_TOL_S * FPS for c in cands):
                checked += 1
                assert any(p[0] <= i.frame <= p[1] for p in pos), (side, i, pos)
                assert keep is None or keep[i.frame]
    assert checked > 20


def test_gate_reasons_unchanged():
    """Same decisions and log fields as before the enumeration of possible impacts."""
    near = _path([(0, 900, 250), (150, 1000, 820), (190, 1050, 300), (299, 1060, 280)], 300)
    d = gate_window(near, FW, FH, FPS, [140.0], "near")
    assert d["passed"] and d["reason"] == "golpe_de_bola" and abs(d["hit_s"] - 3.0) <= 0.06
    assert d["possible"] and all(p[2] == "golpe_de_bola" for p in d["possible"])
    straight = _path([(0, 200, 300), (299, 1700, 900)], 300)
    assert gate_window(straight, FW, FH, FPS, [150.0], "near") == {"passed": False, "reason": "sin_golpe", "hits": 0}
    straight[130:175] = np.nan
    d = gate_window(straight, FW, FH, FPS, [150.0], "near")
    assert d["reason"] == "bola_no_vista" and d["at_s"] == round(130 / FPS, 2)
    lo, hi, why = d["possible"][0]
    assert why == "bola_no_vista" and lo <= 150 <= hi


def test_pose_keep_ranges_join_and_whole_window():
    n = 1000
    keep = pose_keep(n, [(100, 100, "golpe_de_bola")], FPS, pre_s=1.0, post_s=1.0)
    assert keep[50] and keep[150] and not keep[49] and not keep[151] and keep.sum() == 101
    # two stretches closer than join_s become one
    keep = pose_keep(n, [(100, 100, "x"), (230, 230, "x")], FPS, pre_s=1.0, post_s=1.0, join_s=1.0)
    assert keep[50:281].all() and keep.sum() == 231
    keep = pose_keep(n, [(100, 100, "x"), (400, 400, "x")], FPS, pre_s=1.0, post_s=1.0, join_s=1.0)
    assert not keep[200] and keep.sum() == 202
    # covering most of the window: the whole window, as without ranges
    assert pose_keep(260, [(150, 150, "x")], FPS, pre_s=2.8, post_s=2.0) is None
    assert pose_keep(n, [], FPS) is None
    # candidate whose ball is unseen: the whole span where a swing could stand, plus the margins
    keep = pose_keep(n, [(480, 520, "bola_no_vista")], FPS, pre_s=1.0, post_s=1.0)
    assert keep[430] and keep[570] and not keep[429] and not keep[571]


# ---- pose extraction: prefetch and kept frames -------------------------------------------------------

class _Model:
    """Deterministic fake pose model: the people depend only on the image it is given."""

    def __init__(self):
        self.calls = 0

    def prepare(self, img):
        return ("prep", float(img.mean()), img.shape)

    def predict(self, img, conf=0.3, prepared=None):
        self.calls += 1
        v = float(img.mean())
        assert prepared is None or prepared == ("prep", v, img.shape)
        k = int(v) % 3
        b = np.array([[5 + i * 20, 5, 20 + i * 20, 40] for i in range(k)], np.float32).reshape(k, 4)
        return b, np.full((k, 17, 2), v, np.float32), np.full((k, 17), 0.5, np.float32)


def _old_extract(frames, model, roi=None, every=1):
    """extract() as it was (one frame at a time, everything in this thread)."""
    from tennisbio.pose.yolo import appearance
    boxes, kps, confs, feats = [], [], [], []
    for i, frame in enumerate(frames):
        if i % every:
            continue
        ox = oy = 0
        src = frame
        if roi is not None:
            x0, y0, x1, y1 = (int(v) for v in roi)
            src, ox, oy = frame[y0:y1, x0:x1], x0, y0
        b, k, c = model.predict(src, conf=0.3)
        b = b + [ox, oy, ox, oy] if len(b) else np.zeros((0, 4))
        boxes.append(b.astype(np.float32))
        kps.append(k.astype(np.float32) + [ox, oy] if len(b) else np.zeros((0, 17, 2), np.float32))
        confs.append(c.astype(np.float32) if len(b) else np.zeros((0, 17), np.float32))
        feats.append(np.array([appearance(frame, bb) for bb in b], np.float32).reshape(len(b), 32))
    return boxes, kps, confs, feats


@pytest.fixture
def fake_video(monkeypatch):
    from tennisbio.io import video as vio
    from tennisbio.pose import backend, yolo

    rng = np.random.default_rng(2)
    frames = [rng.integers(0, 255, (48, 64, 3), np.uint8) for _ in range(40)]
    model = _Model()
    monkeypatch.setattr(vio, "capture_frames", lambda p, prefetch=4: iter([f.copy() for f in frames]))
    monkeypatch.setattr(backend, "pose_model", lambda *a, **k: model)
    monkeypatch.setattr(yolo, "_fps", lambda v: FPS)
    return frames, model


@pytest.mark.parametrize("roi,every", [(None, 1), ((8, 4, 56, 40), 1), (None, 2)])
def test_extract_with_prefetch_is_the_same_as_one_frame_at_a_time(tmp_path, fake_video, roi, every):
    from tennisbio.pose.yolo import extract
    frames, model = fake_video
    ref = _old_extract(frames, model, roi, every)
    for prefetch in (True, False):
        out = extract("v.mp4", tmp_path / f"p{prefetch}.npz", progress=False, roi=roi, every=every, prefetch=prefetch)
        with np.load(out, allow_pickle=True) as z:
            for key, r in zip(("boxes", "kps", "confs", "feats"), ref):
                assert len(z[key]) == len(r) and all(np.array_equal(x, y) for x, y in zip(z[key], r))


def test_extract_runs_the_model_only_on_kept_frames(tmp_path, fake_video):
    from tennisbio.pose.yolo import extract
    frames, model = fake_video
    keep = np.zeros(len(frames), bool)
    keep[5:12] = keep[30:33] = True
    model.calls = 0
    stats = {}
    out = extract("v.mp4", tmp_path / "k.npz", progress=False, keep=keep, stats=stats)
    ref = _old_extract(frames, _Model())
    assert model.calls == keep.sum() == stats["frames"]
    with np.load(out, allow_pickle=True) as z:
        assert len(z["boxes"]) == len(frames)
        for i in range(len(frames)):
            if keep[i]:
                assert np.array_equal(z["boxes"][i], ref[0][i]) and np.array_equal(z["feats"][i], ref[3][i])
            else:
                assert len(z["boxes"][i]) == 0 and z["kps"][i].shape == (0, 17, 2) and z["feats"][i].shape == (0, 32)


class _FollowModel:
    """Fake model for the follow crop: one person in the middle of whatever crop it sees."""

    def __init__(self):
        self.crops = []

    def predict(self, crop, conf=0.25, prepared=None):
        self.crops.append(crop.shape)
        h, w = crop.shape[:2]
        b = np.array([[w * 0.45, h * 0.4, w * 0.55, h * 0.6]], np.float32)
        return b, np.full((1, 17, 2), w / 2, np.float32), np.full((1, 17), 0.9, np.float32)


def test_extract_follow_prefetch_same_and_restarts_at_each_stretch(tmp_path, monkeypatch):
    from tennisbio.io import video as vio
    from tennisbio.pose import backend, yolo

    rng = np.random.default_rng(4)
    frames = [rng.integers(0, 255, (400, 600, 3), np.uint8) for _ in range(30)]
    monkeypatch.setattr(vio, "capture_frames", lambda p, prefetch=4: iter(frames))
    monkeypatch.setattr(yolo, "_fps", lambda v: FPS)
    outs = []
    for prefetch in (False, True):
        m = _FollowModel()
        monkeypatch.setattr(backend, "pose_model", lambda *a, _m=m, **k: _m)
        p = yolo.extract_follow("v.mp4", tmp_path / f"f{prefetch}.npz", [100, 100, 120, 140], prefetch=prefetch)
        outs.append(np.load(p, allow_pickle=True))
    for key in ("boxes", "kps", "confs", "feats"):
        assert all(np.array_equal(x, y) for x, y in zip(outs[0][key], outs[1][key]))
    # kept stretches: the model only there, and each stretch starts from its own box
    m = _FollowModel()
    monkeypatch.setattr(backend, "pose_model", lambda *a, **k: m)
    keep = np.zeros(30, bool)
    keep[3:10] = keep[20:25] = True
    stats = {}
    p = yolo.extract_follow("v.mp4", tmp_path / "k.npz", [100, 100, 120, 140], keep=keep,
                            inits={3: [100, 100, 120, 140], 20: [400, 200, 440, 280]}, stats=stats)
    z = np.load(p, allow_pickle=True)
    assert len(m.crops) == keep.sum() == stats["frames"] and len(z["boxes"]) == 30
    assert all(len(z["boxes"][i]) == 0 for i in range(30) if not keep[i])
    b20 = z["boxes"][20][0]
    assert abs((b20[0] + b20[2]) / 2 - 420) < 40 and abs((b20[1] + b20[3]) / 2 - 240) < 60     # restarted at her new box


def test_find_far_players_one_reading_many_starts(tmp_path, monkeypatch):
    from tennisbio.pose import yolo
    import tennisbio.court_metrics as cm

    p = tmp_path / "v.avi"
    w = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"MJPG"), 25, (64, 48))
    for i in range(200):
        w.write(np.full((48, 64, 3), i % 250, np.uint8))
    w.release()
    seen = []

    def fake_detect(frame, roi=None, **k):
        v = float(frame.mean())                       # the frame number (± the JPEG rounding)
        seen.append(v)
        t = next((t for t in (10, 70, 75, 160) if abs(v - t) <= 1.5), None)
        return np.array([[t, 0, t + 1, 1]], float) if t is not None else np.zeros((0, 4))
    monkeypatch.setattr(yolo, "detect_people", fake_detect)
    monkeypatch.setattr(cm, "far_roi", lambda H, shape: None)
    monkeypatch.setattr(cm, "pick_far_player", lambda boxes, H: boxes[0] if len(boxes) else None)
    got = yolo.find_far_players(p, np.eye(3), [0, 60, 120], search_s=2.0, step=5)
    assert got[0][0] == 10 and got[60][0] == 70 and got[120][0] == 160
    assert yolo.find_far_player(p, np.eye(3))[0] == 10
    # never past search_s after its start: a start whose player appears later is not found
    seen.clear()
    assert yolo.find_far_players(p, np.eye(3), [100], search_s=1.0, step=5)[100] is None
    assert max(seen) <= 125


# ---- run_clip on a synthetic player: racket only near candidates, pose ranges ------------------------

def _synth_video(path, n, size=(640, 480)):
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), int(FPS), size)
    for _ in range(n):
        w.write(np.zeros((size[1], size[0], 3), np.uint8))
    w.release()
    return path


def _synth_pose(n, swings, keep=None):
    """One standing player 216 px tall whose right wrist swings fast at the given frames."""
    from tennisbio.pose.yolo import _objects
    base = np.array([[300, 150], [295, 145], [305, 145], [290, 150], [310, 150], [280, 180], [320, 180],
                     [270, 220], [330, 220], [265, 255], [335, 255], [285, 260], [315, 260],
                     [285, 310], [315, 310], [285, 350], [315, 350]], np.float32)
    boxes, kps, confs, feats = [], [], [], []
    for t in range(n):
        if keep is not None and not keep[t]:
            boxes.append(np.zeros((0, 4), np.float32)); kps.append(np.zeros((0, 17, 2), np.float32))
            confs.append(np.zeros((0, 17), np.float32)); feats.append(np.zeros((0, 32), np.float32))
            continue
        k = base.copy()
        jit = np.random.default_rng(t).normal(0, 0.6, k.shape)       # the same jitter in every run of frame t
        k += jit.astype(np.float32)
        for s in swings:
            k[10, 0] += 150 * np.exp(-((t - s) / 4.0) ** 2)
            k[10, 1] -= 60 * np.exp(-((t - s - 3) / 5.0) ** 2)
        boxes.append(np.array([[255, 135, 345, 355]], np.float32)); kps.append(k[None])
        confs.append(np.full((1, 17), 0.9, np.float32)); feats.append(np.full((1, 32), 1 / 32, np.float32))
    return dict(fps=FPS, n=n, boxes=_objects(boxes), kps=_objects(kps), confs=_objects(confs), feats=_objects(feats))


@pytest.fixture
def synth_clip(tmp_path, monkeypatch):
    from tennisbio.pose import yolo
    n, swings = 300, (60, 150, 240)
    video = _synth_video(tmp_path / "w.avi", n)
    asked = []

    def fake_rackets(video_, frames, out, imgsz=960, **k):          # an outline above the wrist of each frame
        from tennisbio.pipeline import savez_atomic
        frames = sorted(set(int(f) for f in frames))
        asked.append(frames)
        kp = _synth_pose(n, swings)["kps"]
        polys = []
        for f in frames:
            wx, wy = kp[f][0, 10]
            polys.append([np.array([[wx - 8, wy - 70], [wx + 8, wy - 70], [wx + 8, wy - 6], [wx - 8, wy - 6]], np.float32)])
        savez_atomic(out, frames=np.array(frames), polys=yolo._objects(polys))
        return out
    monkeypatch.setattr(yolo, "extract_rackets", fake_rackets)
    return SimpleNamespace(n=n, swings=swings, video=video, asked=asked, dir=tmp_path)


def _stroke_at(run, frame):
    return min(run.strokes, key=lambda s: abs(s.impact_frame - frame))


def test_racket_only_near_candidates_keeps_the_kept_stroke_identical(synth_clip):
    from tennisbio.clip_pipeline import run_clip
    from tennisbio.pipeline import savez_atomic

    sc = synth_clip
    runs = {}
    for name, targets in (("all", None), ("one", [150 / FPS])):
        d = sc.dir / name
        d.mkdir()
        savez_atomic(d / "w.npz", **_synth_pose(sc.n, sc.swings))
        sc.asked.clear()
        runs[name] = (run_clip(sc.video, d / "w.npz", rackets=True, init_mode="near", log=lambda *_: None,
                               targets=targets, target_tol=CONFIRM_TOL_S), sorted({f for a in sc.asked for f in a}))
    (ra, fa), (rb, fb) = runs["all"], runs["one"]
    assert len(ra.impacts) == 3 and rb.stats["kept_impacts"] == 1 and ra.stats["kept_impacts"] == 3
    assert set(fb) < set(fa)                                    # fewer frames segmented...
    i0 = _stroke_at(rb, 150).impact_frame                      # only frames beyond the kept stroke's reach
    gone = set(fa) - set(fb)
    assert gone and all(f < i0 - 115 or f > i0 + 41 for f in gone) and 240 in gone
    x, y = _stroke_at(ra, 150), _stroke_at(rb, 150)             # ...and the kept stroke reads the same outlines
    assert x.impact_frame == y.impact_frame
    assert x.racket == y.racket and x.racket_track == y.racket_track and any(e[1] is not None for e in x.racket_track)
    assert x.metrics == y.metrics and x.phases == y.phases


def test_pose_ranges_measure_the_stroke_inside_as_the_whole_window(synth_clip):
    from tennisbio.clip_pipeline import keep_key, run_clip
    from tennisbio.pipeline import savez_atomic

    sc = synth_clip
    keep = pose_keep(sc.n, [(150, 150, "golpe_de_bola")], FPS, pre_s=2.8, post_s=1.2)
    assert keep is not None and not keep[240] and keep[150 - 140] and not keep[0]
    d = sc.dir / "r"
    d.mkdir()
    savez_atomic(d / "w.npz", **_synth_pose(sc.n, sc.swings))
    full = run_clip(sc.video, d / "w.npz", rackets=False, init_mode="near", log=lambda *_: None)
    # a window already posed whole (an earlier run) is reused as it is
    again = run_clip(sc.video, d / "w.npz", rackets=False, init_mode="near", log=lambda *_: None, keep=keep)
    assert again.stats["posed_frames"] == sc.n and _stroke_at(again, 150).metrics == _stroke_at(full, 150).metrics
    # otherwise the ranges run reads its own cache (named by the frames it keeps): the model ran only there
    d2 = sc.dir / "r2"
    d2.mkdir()
    savez_atomic(d2 / f"w_r{keep_key(keep)}.npz", **_synth_pose(sc.n, sc.swings, keep))
    part = run_clip(sc.video, d2 / "w.npz", rackets=False, init_mode="near", log=lambda *_: None, keep=keep)
    assert part.stats["posed_frames"] == keep.sum() and full.stats["posed_frames"] == sc.n
    assert np.isnan(part.img[~keep]).all() and np.isfinite(part.img[keep][:, 0]).all()
    assert [i.frame for i in part.impacts] == [i.frame for i in full.impacts if keep[i.frame]]
    x, y = _stroke_at(full, 150), _stroke_at(part, 150)
    assert x.impact_frame == y.impact_frame and x.phases == y.phases and x.chain == y.chain
    assert x.metrics.keys() == y.metrics.keys()
    # the same up to the body height of the clip, a median over the frames posed (as when a candidate
    # falls in a window of its own or in a longer one): far below the noise of any measure
    assert part.height_px == pytest.approx(full.height_px, rel=0.005)
    for k, v in x.metrics.items():
        if isinstance(v, float):
            assert v == pytest.approx(y.metrics[k], rel=0.01, abs=0.05), k
        else:
            assert v == y.metrics[k], k


def test_pose_ranges_with_fill_follow_her_through_the_window(synth_clip):
    """Default (pose_fill_every: 5): a frame in five posed outside the stretches; she is tracked as one
    clip from its first frame, short gaps are filled as before, and her height is the whole window's."""
    from tennisbio.clip_pipeline import keep_key, run_clip
    from tennisbio.pipeline import savez_atomic

    sc = synth_clip
    keep = pose_keep(sc.n, [(150, 150, "golpe_de_bola")], FPS, pre_s=2.8, post_s=1.2, fill_every=5)
    assert keep[0] and keep[245] and not keep[246] and keep[10:211].all() and keep.sum() < 0.85 * sc.n
    d = sc.dir / "f"
    d.mkdir()
    savez_atomic(d / "w.npz", **_synth_pose(sc.n, sc.swings))
    full = run_clip(sc.video, d / "w.npz", rackets=False, init_mode="near", log=lambda *_: None)
    d2 = sc.dir / "f2"
    d2.mkdir()
    savez_atomic(d2 / f"w_r{keep_key(keep)}.npz", **_synth_pose(sc.n, sc.swings, keep))
    part = run_clip(sc.video, d2 / "w.npz", rackets=False, init_mode="near", log=lambda *_: None, keep=keep, split=False)
    assert all(part.boxes[t] is not None for t in np.flatnonzero(keep))
    assert part.height_px == pytest.approx(full.height_px, rel=0.002)
    x, y = _stroke_at(full, 150), _stroke_at(part, 150)
    assert x.impact_frame == y.impact_frame and x.phases == y.phases
    for k, v in x.metrics.items():
        assert (v == pytest.approx(y.metrics[k], rel=0.005, abs=0.02)) if isinstance(v, float) else v == y.metrics[k], k


def test_pose_ranges_fall_back_to_the_whole_window_when_her_height_is_not_seen(synth_clip):
    """Seen from behind her face is rarely found (RacketVision match120: 5 frames of 600 give her
    height); when none of the posed frames has it, the whole window is posed, as before."""
    from tennisbio.clip_pipeline import keep_key, run_clip
    from tennisbio.pipeline import savez_atomic

    sc = synth_clip
    keep = pose_keep(sc.n, [(150, 150, "golpe_de_bola")], FPS, pre_s=2.8, post_s=1.2, fill_every=5)
    whole = _synth_pose(sc.n, sc.swings)
    for t in range(sc.n):
        if keep[t]:
            whole["confs"][t] = whole["confs"][t].copy()
            whole["confs"][t][0, 0] = 0.05                 # nose not found where the ranges pose
    part = _synth_pose(sc.n, sc.swings, keep)
    for t in np.flatnonzero(keep):
        part["confs"][t] = whole["confs"][t]
    d = sc.dir / "h"
    d.mkdir()
    savez_atomic(d / f"w_r{keep_key(keep)}.npz", **part)
    savez_atomic(d / "w_whole.npz", **whole)

    def fake_extract(video, out, *a, **k):              # the whole window posed now (no cache yet)
        assert k.get("keep") is None
        import shutil
        shutil.copy(d / "w_whole.npz", out)
    import tennisbio.pose.yolo as yolo
    orig, yolo.extract = yolo.extract, fake_extract
    try:
        run = run_clip(sc.video, d / "w.npz", rackets=False, init_mode="near", log=lambda *_: None, keep=keep, split=False)
    finally:
        yolo.extract = orig
    assert np.isfinite(run.height_px) and run.stats["whole_window_again"] == 1
    assert any(abs(s.impact_frame - 150) <= 4 for s in run.strokes)


def test_pose_ranges_track_each_stretch_on_its_own(synth_clip):
    """Two stretches: the second starts with her elsewhere (a cut, or she ran): it is tracked from its
    own first frame, not lost because the last box of the first stretch is far away."""
    from tennisbio.clip_pipeline import keep_key, run_clip
    from tennisbio.pipeline import savez_atomic

    sc = synth_clip
    keep = np.zeros(sc.n, bool)
    keep[20:110] = keep[190:290] = True
    pose = _synth_pose(sc.n, sc.swings, keep)
    for t in range(190, 290):                       # second stretch: she is 250 px to the right
        pose["boxes"][t] = pose["boxes"][t] + np.float32([250, 0, 250, 0])
        pose["kps"][t] = pose["kps"][t] + np.float32([250, 0])
    d = sc.dir / "t"
    d.mkdir()
    savez_atomic(d / f"w_r{keep_key(keep)}.npz", **pose)
    run = run_clip(sc.video, d / "w.npz", rackets=False, init_mode="near", log=lambda *_: None, keep=keep)
    assert all(run.boxes[t] is not None for t in range(190, 290)) and all(run.boxes[t] is not None for t in range(20, 110))
    assert sorted(i.frame for i in run.impacts) == [pytest.approx(60, abs=3), pytest.approx(240, abs=3)]


def test_pose_ranges_start_from_the_person_the_ball_leaves(synth_clip):
    """A ball kid crouched lower in the image at the start of a stretch (RacketVision match104: the
    stretch was tracked on him): with the ball hit as anchor she is followed both ways from it."""
    from tennisbio.clip_pipeline import keep_key, run_clip
    from tennisbio.pipeline import savez_atomic

    sc = synth_clip
    keep = np.zeros(sc.n, bool)
    keep[60:250] = True
    pose = _synth_pose(sc.n, sc.swings, keep)
    kid = np.float32([30, 300, 110, 430])                   # 130 px tall (≥ half of her), feet lower
    for t in range(60, 250):
        if t < 120:                                         # he walks off after a second
            pose["boxes"][t] = np.vstack([pose["boxes"][t], kid[None]])
            pose["kps"][t] = np.vstack([pose["kps"][t], np.full((1, 17, 2), [70, 360], np.float32)])
            pose["confs"][t] = np.vstack([pose["confs"][t], np.full((1, 17), 0.9, np.float32)])
            pose["feats"][t] = np.vstack([pose["feats"][t], np.zeros((1, 32), np.float32)])
    d = sc.dir / "a"
    d.mkdir()
    savez_atomic(d / f"w_r{keep_key(keep)}.npz", **pose)
    lost = run_clip(sc.video, d / "w.npz", rackets=False, init_mode="near", log=lambda *_: None, keep=keep)
    assert lost.boxes[150] is None or lost.boxes[150][0] < 200          # without the anchor: the kid
    wx, wy = _synth_pose(sc.n, sc.swings)["kps"][150][0, 10]
    run = run_clip(sc.video, d / "w.npz", rackets=False, init_mode="near", log=lambda *_: None, keep=keep,
                   anchors=[(150, float(wx) - 80, float(wy) - 30)])         # the ball at her racket
    assert all(run.boxes[t] is not None and run.boxes[t][0] > 200 for t in range(60, 250))
    assert any(abs(s.impact_frame - 150) <= 4 for s in run.strokes)


# ---- the stage: switches and the far end -------------------------------------------------------------

def _ctx(tmp_path, **fp):
    logs = []
    cfg = {"fine_pass": {"window_s": 1.0, "gate": True, **fp}, "device": "cpu"}
    return SimpleNamespace(cfg=cfg, log=logs.append, path=lambda n: tmp_path / n, video=tmp_path / "v.mp4"), logs


def _rally(n=600, hit=300):
    return _path([(0, 900, 250), (hit, 1000, 820), (hit + 40, 1050, 300), (n - 1, 1060, 280)], n)


@pytest.mark.parametrize("ranges,side,found,fill", [(False, "near", True, 5), (True, "near", True, 0), (True, "far", True, 0),
                                                     (True, "far", False, 0), (True, "near", True, 5), (True, "far", True, 5),
                                                     ("far", "near", True, 5), ("far", "far", True, 5)])
def test_fine_one_passes_ranges_targets_and_far_starts(tmp_path, monkeypatch, ranges, side, found, fill):
    from tennisbio import clip_pipeline, stages
    from tennisbio.pose import yolo

    ctx, logs = _ctx(tmp_path, pose_ranges=ranges, pose_fill_every=fill)
    clip = tmp_path / "windows" / "w000010000_12000.mp4"
    monkeypatch.setattr(stages, "cut_window", lambda *a, **k: clip)
    tr = _rally() if side == "near" else _path([(0, 900, 800), (300, 950, 260), (340, 900, 700), (599, 880, 900)], 600)
    monkeypatch.setattr(clip_pipeline, "window_ball", lambda v, c, b: (tr, 0.5, FW, FH, FPS))
    monkeypatch.setattr(stages, "far_start", lambda clip, H: dict(roi="follow", init_box=[1, 2, 3, 4], max_bottom=500.0))
    monkeypatch.setattr(stages, "court_at", lambda court, t, s=1.0: (np.eye(3), 20.0))
    monkeypatch.setattr(yolo, "find_far_players", lambda v, H, starts, *a, **k: {s: ([5, 6, 7, 8] if found else None) for s in starts})
    calls = []

    def fake_run_clip(*a, **k):
        calls.append(k)
        return SimpleNamespace(timing={"pose": 1.0}, strokes=[], fps=FPS, stats={"frames": 600, "posed_frames": 300})
    monkeypatch.setattr(clip_pipeline, "run_clip", fake_run_clip)
    monkeypatch.setattr("tennisbio.pose.backend.set_device", lambda *a: None)
    stages._TIMES.clear(); stages._COUNTS.clear(); stages._GATE.clear()
    stages._GATE.update(passed=0, gated=0, off=0, reasons={}, seconds_gated=0.0)
    group = [{"t": 10.0 + 296 / FPS, "side": side}]
    stages._fine_one(ctx, SimpleNamespace(hand="right", height_m=1.84), group, 296 / FPS, 3.2, False, "abc",
                     [], [], np.zeros(0), {"fps": 1, "shots": []}, object(), None, None, {})
    assert len(calls) == 1
    k = calls[0]
    assert k["prefetch"] is True and k["targets"] == [pytest.approx(296 / FPS)] and k["target_tol"] == CONFIRM_TOL_S
    if not (ranges is True or ranges == side) or (side == "far" and not found and not fill):
        assert k["keep"] is None and "inits" not in k                      # the whole window, as before
    elif fill:            # a frame in `fill` posed between the stretches, tracked as one clip: no new starts
        assert k["keep"] is not None and 0 < k["keep"].sum() < 600 and k["keep"][300] and k["keep"][::fill].all()
        assert k["split"] is False and "inits" not in k and "anchors" not in k
    else:
        assert k["keep"] is not None and 0 < k["keep"].sum() < 600 and k["keep"][300]
        if side == "far":
            assert set(k["inits"]) == {a for a, _ in clip_pipeline.keep_runs(k["keep"])} and "anchors" not in k
        else:
            assert k["anchors"] and abs(k["anchors"][0][0] - 300) <= 3       # the ball hit, with its position
    assert any("pose en" in m for m in logs)
    assert stages._COUNTS["frames"] == 600


def test_switches_off_give_the_old_calls(tmp_path, monkeypatch):
    from tennisbio import clip_pipeline, stages

    ctx, _ = _ctx(tmp_path, pose_prefetch=False, racket_near_candidates=False)
    clip = tmp_path / "windows" / "w000010000_12000.mp4"
    monkeypatch.setattr(stages, "cut_window", lambda *a, **k: clip)
    monkeypatch.setattr(clip_pipeline, "window_ball", lambda v, c, b: (_rally(), 0.5, FW, FH, FPS))
    calls = []
    monkeypatch.setattr(clip_pipeline, "run_clip",
                        lambda *a, **k: calls.append(k) or SimpleNamespace(timing={}, strokes=[], fps=FPS, stats={}))
    monkeypatch.setattr("tennisbio.pose.backend.set_device", lambda *a: None)
    stages._TIMES.clear(); stages._COUNTS.clear(); stages._GATE.clear()
    stages._GATE.update(passed=0, gated=0, off=0, reasons={}, seconds_gated=0.0)
    stages._fine_one(ctx, SimpleNamespace(hand="right", height_m=1.84), [{"t": 10.0 + 296 / FPS, "side": "near"}],
                     296 / FPS, 3.2, False, "abc", [], [], np.zeros(0), {"fps": 1, "shots": []}, object(), None, None, {})
    assert calls[0]["prefetch"] is False and calls[0]["targets"] is None and calls[0]["keep"] is None


# ---- ball model with a fixed batch (ball.static_batch, for DirectML) ---------------------------------

def test_ball_static_batch_pads_the_last_batch_and_gives_the_same_track():
    from tennisbio.ball import BallTracker

    class FakeSess:
        def __init__(self):
            self.batches = []

        def get_inputs(self):
            return [type("I", (), {"name": "frames"})()]

        def run(self, _, feed):
            x = feed["frames"]
            self.batches.append(len(x))
            hm = np.zeros((len(x), 1, 288, 512), np.float32)
            for n in range(len(x)):
                c = int(x[n, -3:].mean() * 400) + 20
                hm[n, 0, 100:104, c:c + 4] = 0.9
            return [hm]

    rng = np.random.default_rng(5)
    frames = [rng.integers(0, 255, (108, 192, 3), np.uint8) for _ in range(21)]
    out = []
    for static in (False, True):
        bt = BallTracker.__new__(BallTracker)
        bt.sess, bt.threshold, bt.batch, bt.static = FakeSess(), 0.5, 4, static
        out.append(bt.track(iter(frames), step=2))
        assert bt.sess.batches == ([4, 4, 3] if not static else [4, 4, 4])
    assert np.array_equal(out[0], out[1], equal_nan=True)


@pytest.mark.skipif(not (Path(__file__).resolve().parents[1] / "models" / "balltrack.onnx").exists(),
                    reason="sin models/balltrack.onnx")
def test_ball_static_batch_on_the_real_model_cpu():
    from tennisbio.ball import BallTracker

    path = Path(__file__).resolve().parents[1] / "models" / "balltrack.onnx"
    rng = np.random.default_rng(6)
    frames = [cv2.GaussianBlur(rng.integers(0, 255, (288, 512, 3), np.uint8), (9, 9), 3) for _ in range(11)]
    for f in frames[4:8]:
        cv2.circle(f, (200, 150), 4, (255, 255, 255), -1)
    a = BallTracker(path, "cpu").track(iter(frames))
    b = BallTracker(path, "cpu", static_batch=True).track(iter(frames))
    assert np.allclose(a, b, equal_nan=True, atol=1e-3)
