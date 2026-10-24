import numpy as np

from tennisbio import ball_features as BF


def _track(seconds=2.0, hit_at=1.0):
    """Ball coming towards the camera (y grows), hit at hit_at, then going away (y shrinks)."""
    t = np.arange(0, seconds, 1 / BF.BALL_FPS)
    y = np.where(t < hit_at, 0.3 + 0.4 * t / hit_at, 0.7 - 0.4 * (t - hit_at) / hit_at)
    x = np.full_like(t, 0.5)
    return np.column_stack([t, x, y, np.ones_like(t)])


def test_features_mark_the_turn_of_a_hit():
    f = BF.features(_track(), n=20, fps=10.0)
    assert f.shape == (20, BF.BALL_DIM)
    assert np.allclose(f[:, 0], 1.0)                      # ball seen in every bin
    hit_bin = 10
    assert f[hit_bin - 1:hit_bin + 1, 7].max() == 1.0     # vertical direction flips at the hit
    assert f[hit_bin - 1:hit_bin + 1, 6].max() > 0.9      # ~180° turn
    assert f[3, 7] == 0 and f[16, 7] == 0                 # no flip far from it
    assert f[3, 4] > 0 > f[16, 4]                         # towards the camera, then away


def test_features_unseen_and_empty():
    tr = _track()
    tr[:, 1:3] = np.nan
    f = BF.features(tr, n=20, fps=10.0)
    assert not f.any()
    assert not BF.features(np.zeros((0, 4)), n=5, fps=10.0).any()


def test_play_segments_are_cut_and_short_ones_dropped():
    fps = 10.0
    sc = {"shots": [{"start": 0, "end": 5, "main_camera": True},            # 0.5 s: too short
                    {"start": 5, "end": 100, "main_camera": False},
                    {"start": 100, "end": 800, "main_camera": True}]}      # 70 s: 30 + 30 + 10
    segs = BF.play_segments(sc, None, fps)
    assert [(round(a), round(b)) for a, b in segs] == [(10, 40), (40, 70), (70, 80)]
