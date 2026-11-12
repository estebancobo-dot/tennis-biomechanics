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
                        lambda m, e: "other" if (m, e) == ("ball_features", "cached_track") else real(m, e))
    assert stages.ball_track_key({}) != base


def test_function_fingerprint_counts_what_the_function_reaches():
    fp = pipeline.function_fingerprint("ball_features", "track_play")
    assert fp and fp != pipeline.function_fingerprint("ball_features", "features")


def test_cached_track_reaches_track_play():
    """The key follows cached_track and what it calls: a change in track_play changes it too."""
    from tennisbio.pipeline import _reachable_src
    src = (pipeline.Path(pipeline.__file__).parent / "ball_features.py").read_text(encoding="utf-8")
    reached = _reachable_src(src, "cached_track")
    assert "FunctionDef('track_play'" in reached and "FunctionDef('play_segments'" in reached


def _library(tmp_path):
    """A library match folder: the cheap pass (scenes, court, players) in etapas/, nothing at the root."""
    d = tmp_path / "lib"
    (d / "etapas").mkdir(parents=True)
    (d / "partido.json").write_text('{"jugadora": "rybakina"}')
    np.savez(d / "etapas" / "players.npz", fps=25.0)
    (d / "etapas" / "scenes.json").write_text('{"shots": [{"start": 0, "end": 100, "main_camera": true}]}')
    (d / "etapas" / "court.json").write_text('{"shots": []}')
    return d


def test_ball_track_of_a_library_match_reads_its_scenes(tmp_path, monkeypatch):
    """12-11: in a library folder scenes.json lives in etapas/; it was read at the root, so the track was always empty
    and the spotter of every real match ran without the ball."""
    d = _library(tmp_path)
    seen = []
    monkeypatch.setattr("tennisbio.ball_features.track_play",
                        lambda v, sc, court, tr, fps, log=None: seen.append((sc, court)) or np.ones((4, 4), np.float32))
    tr = cached_track(d, tmp_path / "v.mp4", lambda: None, key="k")
    assert len(tr) == 4 and seen and seen[0][0]["shots"] and seen[0][1] == {"shots": []}
    assert (d / "etapas" / "ball_track.npz").exists()


def test_an_empty_ball_track_is_never_reused(tmp_path, monkeypatch):
    d = _library(tmp_path)
    np.savez_compressed(d / "etapas" / "ball_track.npz", track=np.zeros((0, 4), np.float32), key=np.array("k"))
    monkeypatch.setattr("tennisbio.ball_features.track_play", lambda *a, **k: np.ones((3, 4), np.float32))
    assert len(cached_track(d, tmp_path / "v.mp4", lambda: None, key="k")) == 3


def test_ball_track_without_scenes_is_an_error(tmp_path):
    import pytest
    d = _library(tmp_path)
    (d / "etapas" / "scenes.json").unlink()
    with pytest.raises(FileNotFoundError):
        cached_track(d, tmp_path / "v.mp4", lambda: None, key="k")


def test_coverage_says_how_much_ball_there_was():
    from tennisbio.ball_features import BALL_FPS, coverage
    tr = np.zeros((int(BALL_FPS * 60), 4), np.float32)
    tr[::2, 1:3] = np.nan
    assert coverage(tr) == {"min": 1.0, "seen": 0.5} and coverage(np.zeros((0, 4))) == {"min": 0.0, "seen": 0.0}
