"""#263 (12-11): nothing of an analysis made with other code is reused. The caches of each window (pose, ball, racket)
were keyed by the models and settings only, and the match's ball track (ball_track.npz) had no key at all: once
written it was reused whatever model or code came later."""
import numpy as np

from tennisbio import pipeline, stages
from tennisbio.ball_features import cached_track


def _mdir(tmp_path):
    d = tmp_path / "m"
    d.mkdir()
    np.savez(d / "players.npz", fps=25.0)
    (d / "scenes.json").write_text('{"shots": [{"start": 0, "end": 100, "main_camera": true}]}')
    return d


def test_ball_track_made_by_other_code_is_computed_again(tmp_path, monkeypatch):
    d = _mdir(tmp_path)
    calls = []
    monkeypatch.setattr("tennisbio.ball_features.track_play",
                        lambda *a, **k: calls.append(1) or np.full((5, 4), float(len(calls)), np.float32))
    a = cached_track(d, tmp_path / "v.mp4", lambda: None, key="code-A")
    assert len(calls) == 1 and np.load(d / "ball_track.npz")["key"] == "code-A"
    assert np.array_equal(cached_track(d, tmp_path / "v.mp4", lambda: None, key="code-A"), a)   # same code: reused
    assert len(calls) == 1
    b = cached_track(d, tmp_path / "v.mp4", lambda: None, key="code-B")                          # other code: again
    assert len(calls) == 2 and not np.array_equal(a, b)


def test_ball_track_written_before_keys_existed_is_computed_again(tmp_path, monkeypatch):
    d = _mdir(tmp_path)
    np.savez_compressed(d / "ball_track.npz", track=np.zeros((3, 4), np.float32))          # the old file: no key
    monkeypatch.setattr("tennisbio.ball_features.track_play", lambda *a, **k: np.ones((3, 4), np.float32))
    assert cached_track(d, tmp_path / "v.mp4", lambda: None, key="k").sum() == 12


def test_window_caches_change_key_with_the_code_that_makes_them(monkeypatch):
    cfg = {}
    base = stages.window_cache_key(cfg)
    real = pipeline.code_fingerprint
    monkeypatch.setattr(pipeline, "code_fingerprint",
                        lambda mods, entry=None: "other" if tuple(mods) == stages.WINDOW_CODE else real(mods, entry))
    assert stages.window_cache_key(cfg) != base
    assert {"pose.hybrid", "pose.yolo", "ball", "racket_pose", "io.video"} <= set(stages.WINDOW_CODE)


def test_ball_track_key_follows_its_function_not_the_whole_module(monkeypatch):
    base = stages.ball_track_key({})
    real = pipeline.function_fingerprint
    monkeypatch.setattr(pipeline, "function_fingerprint",
                        lambda m, e: "other" if (m, e) == ("ball_features", "track_play") else real(m, e))
    assert stages.ball_track_key({}) != base


def test_function_fingerprint_counts_what_the_function_reaches():
    fp = pipeline.function_fingerprint("ball_features", "track_play")
    assert fp and fp != pipeline.function_fingerprint("ball_features", "features")
