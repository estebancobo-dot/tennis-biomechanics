import json

import pytest

from tennisbio import pipeline
from tennisbio.catalog import Match, Player, load_matches


@pytest.fixture
def fake_stages(monkeypatch):
    calls = []
    reg = {}
    monkeypatch.setattr(pipeline, "STAGES", reg)

    @pipeline.stage("a", "1", settings=lambda c: {"x": c["x"]})
    def a(ctx):
        calls.append("a"); ctx.path("a.txt").write_text("a")

    @pipeline.stage("b", "1", deps=("a",))
    def b(ctx):
        calls.append("b"); ctx.path("b.txt").write_text("b")
    return calls


def make_ctx(tmp_path, x=1):
    video = tmp_path / "v.mp4"
    if not video.exists():
        video.write_bytes(b"0" * 10)
    return pipeline.Context(Match("m1", video, Player("p", "P")), {"x": x}, tmp_path / "out", log=lambda *_: None)


def test_incremental_runs_only_what_changed(tmp_path, fake_stages):
    assert pipeline.run(make_ctx(tmp_path)) == ["a", "b"]
    assert pipeline.run(make_ctx(tmp_path)) == []                       # nothing changed
    assert pipeline.status(make_ctx(tmp_path)) == {"a": "ok", "b": "ok"}
    assert pipeline.status(make_ctx(tmp_path, x=2)) == {"a": "stale", "b": "stale"}
    assert pipeline.run(make_ctx(tmp_path, x=2)) == ["a", "b"]          # a's settings changed → b too
    pipeline.STAGES["b"].version = "2"
    assert pipeline.run(make_ctx(tmp_path, x=2)) == ["b"]                # only b's code changed
    m = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert m["b"]["version"] == "2"


def test_new_video_reruns_everything(tmp_path, fake_stages):
    pipeline.run(make_ctx(tmp_path))
    (tmp_path / "v.mp4").write_bytes(b"1" * 20)
    assert pipeline.run(make_ctx(tmp_path)) == ["a", "b"]


def test_catalog(tmp_path):
    (tmp_path / "players").mkdir()
    (tmp_path / "players" / "ryba.yaml").write_text("name: E. R.\nhand: right\nheight_m: 1.84\n")
    (tmp_path / "matches.yaml").write_text("matches:\n  - id: m1\n    video: a.mp4\n    player: ryba\n    surface: hard\n")
    m = load_matches({"paths": {"videos": "/v"}}, tmp_path)[0]
    assert m.id == "m1" and m.player.height_m == 1.84 and m.surface == "hard" and m.video.name == "a.mp4"


def test_force_reruns_only_requested(tmp_path, fake_stages):
    pipeline.run(make_ctx(tmp_path))
    assert pipeline.run(make_ctx(tmp_path), ["b"], force=True) == ["b"]


def test_without_upstream_stale_dependencies_are_kept(tmp_path, fake_stages):
    """recompute_measures.py: b re-runs on a's outputs, a stays stale for the next normal run."""
    pipeline.run(make_ctx(tmp_path))
    assert pipeline.run(make_ctx(tmp_path, x=2), ["b"], force=True, upstream=False) == ["b"]
    assert fake_stages == ["a", "b", "b"]
    assert pipeline.status(make_ctx(tmp_path, x=2))["a"] == "stale"
    assert pipeline.run(make_ctx(tmp_path, x=2)) == ["a", "b"]


def test_point_won_from_the_next_scoreboard_change():
    from tennisbio.stages import point_won
    sc = {"readings": [
        {"t": 0, "games": [[2, 3]], "points": ["15", "30"]},
        {"t": 20, "games": [[2, 3]], "points": ["15", "30"]},
        {"t": 30, "games": [[2, 3]], "points": ["30", "30"]},       # she won the point played at t=25
        {"t": 60, "games": [[2, 3]], "points": ["30", "40"]},       # she lost the next one
        {"t": 90, "games": [[2, 4]], "points": ["0", "0"]},         # and the game
    ]}
    assert point_won(sc, 25) is True
    assert point_won(sc, 45) is False
    assert point_won(sc, 75) is False
    assert point_won({"readings": []}, 5) is None


def test_rally_position_counts_her_hits_of_the_point():
    from tennisbio.stages import _rally_position
    scenes = {"fps": 10, "shots": [{"start": 0, "end": 200, "main_camera": True},
                                   {"start": 200, "end": 260, "main_camera": True}]}
    cands = [{"t": 3.0}, {"t": 6.0}, {"t": 9.0}, {"t": 20.3}, {"t": 23.0}]
    strokes = [{"match_time_s": 6.0, "technique": {"classes": {"play": "inicio del punto"}}},
               {"match_time_s": 9.0, "technique": {"classes": {}}},
               {"match_time_s": 23.0}]                 # its shot starts 0.3 s before the first hit: unknown
    _rally_position(strokes, cands, scenes)
    assert (strokes[0]["shot_in_point"], strokes[0]["shots_in_point"]) == (2, 3)
    assert strokes[0]["technique"]["classes"]["play"] == "inicio del punto"
    assert strokes[1]["technique"]["classes"]["play"] == "peloteo"
    assert "shot_in_point" not in strokes[2]


def test_low_disk_stops_before_a_stage(tmp_path, monkeypatch, fake_stages):
    import shutil
    from collections import namedtuple
    U = namedtuple("U", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda p: U(1e12, 1e12, 1e9))
    with pytest.raises(pipeline.DiskFull):
        pipeline.run(make_ctx(tmp_path))
    assert fake_stages == []


def test_ctx_video_is_the_clean_copy_only_when_recorded(tmp_path):
    ctx = make_ctx(tmp_path)
    ctx.dir.mkdir(parents=True)
    (ctx.dir / "source.mkv").write_bytes(b"x")
    assert ctx.video == ctx.match.video            # no source.json: a half-written copy is never used
    (ctx.dir / "source.json").write_text("{}")
    assert ctx.video == ctx.dir / "source.mkv"


def test_orphan_windows_and_series_are_deleted(tmp_path):
    from tennisbio.stages import _drop_orphans
    ctx = make_ctx(tmp_path)
    (ctx.dir / "windows").mkdir(parents=True)
    (ctx.dir / "series").mkdir()
    for n in ("w000010000_4000.mp4", "w000010000_4000_ab12cd34.npz", "w000090000_4000.mp4"):
        (ctx.dir / "windows" / n).write_bytes(b"x")
    for n in ("w000010000_4000_near_120.json", "w000090000_4000_near_100.json"):
        (ctx.dir / "series" / n).write_text("{}")
    strokes = [{"series": "series/w000010000_4000_near_120.json"}]
    _drop_orphans(ctx, [{"t": 12.0}], strokes, [])
    assert sorted(f.name for f in (ctx.dir / "windows").iterdir()) == ["w000010000_4000.mp4", "w000010000_4000_ab12cd34.npz"]
    assert [f.name for f in (ctx.dir / "series").iterdir()] == ["w000010000_4000_near_120.json"]


def test_superseded_windows_are_deleted_but_not_the_other_pass(tmp_path):
    from tennisbio.stages import _drop_orphans
    ctx = make_ctx(tmp_path)
    (ctx.dir / "windows").mkdir(parents=True)
    names = ("w000000000_3600.mp4",       # old single-stroke window, now inside a grouped one
             "w000000000_9225.mp4",       # this pass's grouped window
             "w000020000_3600.mp4")       # the opponent's candidate (not analysed by this pass)
    for n in names:
        (ctx.dir / "windows" / n).write_bytes(b"x")
    cands = [{"t": 2.0}, {"t": 5.0}, {"t": 21.0}]
    _drop_orphans(ctx, cands, [], [], {"w000000000_9225"}, cands[:2])
    assert sorted(f.name for f in (ctx.dir / "windows").iterdir()) == ["w000000000_9225.mp4", "w000020000_3600.mp4"]
