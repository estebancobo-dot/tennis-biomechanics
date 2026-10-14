"""The cascade of the fine pass (fine_gate): windows the ball alone rules out skip the pose, and a
window with a stroke the full pass would confirm is never ruled out."""
from types import SimpleNamespace

import numpy as np
import pytest

from tennisbio.ball import ball_hits, clean_track
from tennisbio.fine_gate import CONFIRM_TOL_S, gate_window
from tennisbio.impacts import fuse, fuse_with_ball

FPS, FW, FH = 50.0, 1920, 1080


def path(waypoints, n):
    """(n, 3) ball track through (frame, x, y) waypoints, linear in between, confidence 1."""
    f = [w[0] for w in waypoints]
    t = np.full((n, 3), np.nan)
    idx = np.arange(f[0], f[-1] + 1)
    t[idx, 0] = np.interp(idx, f, [w[1] for w in waypoints])
    t[idx, 1] = np.interp(idx, f, [w[2] for w in waypoints])
    t[idx, 2] = 1.0
    return t


def near_rally(n=300, hit=150):
    """The opponent's ball comes down the image to the near player, who sends it back up."""
    return path([(0, 900, 250), (hit, 1000, 820), (hit + 40, 1050, 300), (n - 1, 1060, 280)], n)


def test_near_hit_is_found_like_the_full_pass():
    tr = near_rally()
    hits = [h for h in ball_hits(clean_track(tr, width=FW), FH, FPS) if h.side == "near"]
    assert hits and abs(hits[0].frame - 150) <= 2


def test_window_without_stroke_is_gated():
    # the ball well seen, flying straight across the court: no turn, so no hit of hers can be confirmed
    tr = path([(0, 200, 300), (299, 1700, 900)], 300)
    d = gate_window(tr, FW, FH, FPS, [150.0], "near")
    assert d == {"passed": False, "reason": "sin_golpe", "hits": 0}


def test_window_with_stroke_passes():
    d = gate_window(near_rally(), FW, FH, FPS, [140.0], "near")
    assert d["passed"] and d["reason"] == "golpe_de_bola"


def test_candidate_far_from_the_hit_is_gated_and_borderline_passes():
    tr = near_rally()
    far_off = 150 + (CONFIRM_TOL_S + 0.1) * FPS + 3            # beyond tolerance + margin
    assert not gate_window(tr, FW, FH, FPS, [far_off], "near")["passed"]
    edge = 150 + (CONFIRM_TOL_S + 0.1) * FPS - 1               # just inside tolerance + margin
    assert gate_window(tr, FW, FH, FPS, [edge], "near")["passed"]
    # one of several candidates of the window is enough
    assert gate_window(tr, FW, FH, FPS, [far_off, 152.0], "near")["passed"]


def test_ball_unseen_near_candidate_passes_near_but_not_far():
    tr = path([(0, 200, 300), (299, 1700, 900)], 300)
    tr[130:175] = np.nan                                       # occluded / blurred around her swing
    d = gate_window(tr, FW, FH, FPS, [150.0], "near")
    assert d["passed"] and d["reason"] == "bola_no_vista"
    # far strokes count only when the ball confirms them: an unseen ball cannot hold one
    assert not gate_window(tr, FW, FH, FPS, [150.0], "far")["passed"]


def test_no_data_passes():
    assert gate_window(np.zeros((0, 3)), FW, FH, FPS, [10.0])["passed"]
    assert gate_window(None, FW, FH, FPS, [10.0])["passed"]
    # a candidate beyond the end of the track cannot be checked
    tr = path([(0, 200, 300), (99, 1700, 900)], 100)
    assert gate_window(tr, FW, FH, FPS, [110.0], "near")["passed"]


def test_far_hit_passes_far_window():
    # far player: the ball goes up the image to her and comes back down
    tr = path([(0, 900, 800), (150, 950, 260), (190, 900, 700), (299, 880, 900)], 300)
    hits = ball_hits(clean_track(tr, width=FW), FH, FPS)
    assert any(h.side == "far" for h in hits)
    assert gate_window(tr, FW, FH, FPS, [150.0], "far")["passed"]
    assert not gate_window(tr, FW, FH, FPS, [150.0], "near")["passed"]


@pytest.mark.parametrize("side", ["near", "far"])
def test_gate_never_drops_what_the_full_pass_confirms(side):
    """Random windows run through the real confirmation logic (fuse → fuse_with_ball → match within
    CONFIRM_TOL_S, far strokes only with the ball): whenever a candidate would be confirmed, the gate
    passes its window, even with no margin. The pose can only remove impacts, so every swing,
    onset and wrist speed is drawn at random and the player box covers the whole image."""
    rng = np.random.default_rng(7 if side == "near" else 11)
    n, gated, confirmed = 250, 0, 0
    box = np.array([0, 0, FW, FH], float)
    for _ in range(400):
        k = rng.integers(2, 6)
        fr = np.sort(rng.choice(np.arange(1, n - 1), k, replace=False))
        wp = [(0, *rng.uniform([100, 100], [1800, 1000]))] + \
             [(int(f), *rng.uniform([100, 100], [1800, 1000])) for f in fr] + [(n - 1, *rng.uniform([100, 100], [1800, 1000]))]
        tr = path(wp, n)
        for _ in range(rng.integers(0, 4)):                 # occlusions and misses
            a = rng.integers(0, n)
            tr[a:a + rng.integers(1, 40)] = np.nan
        tr[rng.random(n) < 0.15] = np.nan
        swings = np.sort(rng.choice(np.arange(n), rng.integers(0, 5), replace=False))
        onsets = np.sort(rng.uniform(0, n / FPS, rng.integers(0, 6)))
        impacts = fuse(swings, FPS, onsets)
        ct = clean_track(tr, width=FW)
        hits = ball_hits(ct, FH, FPS)
        impacts = fuse_with_ball(impacts, FPS, hits, ~np.isnan(ct[:, 0]), [box] * n,
                                 wrist_speed=rng.uniform(0, 4, n), side=side)
        if side == "far":
            impacts = [i for i in impacts if "ball" in i.source]
        cands = list(rng.uniform(0, n, 3))
        conf = any(abs(i.frame - c) <= CONFIRM_TOL_S * FPS for i in impacts for c in cands)
        d = gate_window(tr, FW, FH, FPS, cands, side, margin_s=0.0)
        confirmed += conf
        gated += not d["passed"]
        assert d["passed"] or not conf, (side, cands, [(i.frame, i.source) for i in impacts])
    assert confirmed > 20 and gated > 20          # both outcomes were exercised


# ---- the stage: a gated window runs no pose, a passed one runs it as before ------------------------

def _ctx(tmp_path, gate=True):
    logs = []
    cfg = {"fine_pass": {"window_s": 1.0, "gate": gate}, "device": "cpu"}
    return SimpleNamespace(cfg=cfg, log=logs.append, path=lambda n: tmp_path / n, video=tmp_path / "v.mp4"), logs


@pytest.mark.parametrize("ball_kind,expect_pose", [("straight", False), ("rally", True), ("none", True)])
def test_fine_one_skips_pose_only_when_gated(tmp_path, monkeypatch, ball_kind, expect_pose):
    from tennisbio import clip_pipeline, stages

    ctx, logs = _ctx(tmp_path)
    clip = tmp_path / "windows" / "w000010000_6000.mp4"
    monkeypatch.setattr(stages, "cut_window", lambda *a, **k: clip)
    tr = near_rally() if ball_kind == "rally" else path([(0, 200, 300), (299, 1700, 900)], 300)
    monkeypatch.setattr(clip_pipeline, "window_ball", lambda v, c, b: (tr, 0.5, FW, FH, FPS))
    calls = []

    def fake_run_clip(*a, **k):
        calls.append(a)
        return SimpleNamespace(timing={"pose": 1.0}, strokes=[], fps=FPS)
    monkeypatch.setattr(clip_pipeline, "run_clip", fake_run_clip)
    monkeypatch.setattr("tennisbio.pose.backend.set_device", lambda *a: None)
    stages._TIMES.clear()
    stages._GATE.clear()
    stages._GATE.update(passed=0, gated=0, off=0, reasons={}, seconds_gated=0.0)
    group = [{"t": 10.0 + 140 / FPS, "side": "near"}]          # the candidate 0.2 s before the hit
    ball = None if ball_kind == "none" else object()
    out = stages._fine_one(ctx, SimpleNamespace(hand="right", height_m=1.84), group, 140 / FPS, 3.2, False, "abc",
                           [], [], np.zeros(0), {"fps": 1, "shots": []}, ball, None, None, {})
    assert out == []
    assert bool(calls) == expect_pose
    if ball_kind == "straight":
        assert stages._GATE["gated"] == 1 and any("descartada sin pose" in m for m in logs)
    elif ball_kind == "rally":
        assert stages._GATE["passed"] == 1 and any("pasa" in m for m in logs)
    else:
        assert stages._GATE["off"] == 1


@pytest.fixture(scope="module")
def tiny_video(tmp_path_factory):
    import cv2
    p = tmp_path_factory.mktemp("v") / "t.avi"
    w = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"MJPG"), 50, (64, 48))
    for i in range(12):
        w.write(np.full((48, 64, 3), i * 10, np.uint8))
    w.release()
    return p


def test_window_ball_cached_where_run_clip_reads_it(tmp_path, monkeypatch, tiny_video):
    from tennisbio import clip_pipeline

    class FakeBall:
        n = 0

        def track(self, frames, step=1):
            FakeBall.n += 1
            return np.arange(3 * len(list(frames)), dtype=float).reshape(-1, 3)
    cache = tmp_path / "w_abc.npz"
    t1, took1, fw, fh, fps = clip_pipeline.window_ball(tiny_video, cache, FakeBall())
    t2, took2, *_ = clip_pipeline.window_ball(tiny_video, cache, FakeBall())
    assert FakeBall.n == 1 and took2 == 0.0 and np.array_equal(t1, t2) and fw > 0 and fh > 0 and fps > 0
    assert clip_pipeline.ball_cache_path(cache) == clip_pipeline.ball_cache_path(tmp_path / "w_abc_far.npz")
    assert clip_pipeline.ball_cache_path(cache).exists()
