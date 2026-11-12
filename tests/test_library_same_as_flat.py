"""#264, R20 (12-11): the same stage gives the same in a library match folder (the cheap pass in etapas/) as in a flat
one. F3Set validates flat folders and the real matches run in the library: R17 (the match's ball read outside etapas/,
so empty in every real match for three weeks) passed every test because none ran the library layout."""
import json
import shutil

import numpy as np

from tennisbio import ball_features as BF, match_files as mf, pipeline, spotting as S, stages
from tennisbio.catalog import Match, Player
from test_spotting_stage import FPS, on_cfg, spotter_model, write_match


def _fake_ball(video, sc, court, tracker, fps, log=None):
    """A ball over every main-camera shot it is given (none when it is given no shots, as R17 did)."""
    rows = []
    for s in sc.get("shots", []):
        t = np.arange(s["start"] / fps, s["end"] / fps, 1 / BF.BALL_FPS)
        rows.append(np.column_stack([t, 0.3 + 0.1 * np.sin(t), 0.5 + 0.1 * np.cos(t), np.ones_like(t)]))
    return np.concatenate(rows).astype(np.float32) if rows else np.zeros((0, 4), np.float32)


def _run(tmp_path, name, library, onnx, monkeypatch):
    d = tmp_path / name
    write_match(d)
    if library:                                   # the library's split: cheap pass in etapas/, record at the root
        (d / "etapas").mkdir()
        for f in list(d.iterdir()):
            if f.name in mf.CHEAP_FILES:
                shutil.move(str(f), str(d / "etapas" / f.name))
        (d / "partido.json").write_text(json.dumps({"jugadora": "p"}))
        assert mf.is_library(d)
    ctx = pipeline.Context(Match("m1", tmp_path / "v.mp4", Player("p", "P")), on_cfg(onnx), d, log=lambda *_: None)
    monkeypatch.setattr(S, "sound_flux_stream", lambda v, fps, n, **k: np.zeros(n, np.float32))
    monkeypatch.setattr(BF, "track_play", _fake_ball)
    monkeypatch.setattr(stages, "_ball_tracker", lambda ctx: None)
    sp = stages.st_spotting(ctx)
    cand = stages.st_candidates(ctx)
    read = lambda n: json.loads(ctx.path(n).read_text())
    with np.load(ctx.path("ball_track.npz")) as z:
        track = z["track"]
    sp.pop("seconds")
    return {"spotting": sp, "candidates": cand, "spotting.json": read("spotting.json"),
            "candidates.json": read("candidates.json")}, track


def test_spotting_and_candidates_are_the_same_in_the_library_and_in_a_flat_folder(tmp_path, monkeypatch):
    onnx = spotter_model(tmp_path, feature_dim=S.FEATURE_DIM + BF.BALL_DIM)
    flat, tf = _run(tmp_path, "flat", False, onnx, monkeypatch)
    lib, tl = _run(tmp_path, "lib", True, onnx, monkeypatch)
    assert len(tf) > 0 and np.array_equal(tf, tl)            # the same ball, followed over the same shots
    assert flat == lib
    assert flat["spotting"]["ball"]["min"] > 0 and flat["spotting"]["inputs"]["near_seen"] > 0
