"""A hidden scoreboard alone is not a replay (03-11, F3Set: 62 live strokes dropped, 52 in the Australian Open)."""
import numpy as np

from tennisbio.stages import confirmed_without_board


def test_live_play_without_scoreboard_is_kept():
    spans = [(10.0, 25.0), (40.0, 50.0), (60.0, 70.0), (80.0, 85.0)]
    hits = np.array([11.0, 12.1, 13.2, 14.4,          # live rally: hits ~1.1 s apart, with sound
                     41.0, 44.5, 48.0,                 # slow motion: 3.5 s apart, with sound
                     62.0, 63.0,                       # live, but no sound at all in the span → replay
                     81.0])                            # one hit with sound → live
    onsets = np.array([11.0, 12.1, 13.2, 14.4, 41.2, 44.7, 81.0])
    assert confirmed_without_board(spans, hits, onsets) == [(40.0, 50.0), (60.0, 70.0)]
    assert confirmed_without_board([], hits, onsets) == []


def test_the_validation_uses_the_stage_rule(monkeypatch):
    """03-11: the recall validation had its own copy of the replay rule; now it asks the stage's, with the reason."""
    from tennisbio import stages
    from tennisbio.validation import recall_eval

    seen = {}

    def fake(d, sk, runs, court, onsets, score, hits=None):
        seen["hits"] = hits
        return ["sin_marcador", None], []
    monkeypatch.setattr(stages, "near_runs", lambda d, sk, court: iter([]))
    monkeypatch.setattr(stages, "run_replay_reasons", fake)
    assert recall_eval.replay_runs({}, None, {}, np.zeros(0), {}, np.array([1.0])) == ["sin_marcador", None]
    assert seen["hits"] is not None
    assert "repeticion_sin_marcador" in recall_eval.STEPS and "repeticion_lenta" in recall_eval.STEPS


def test_a_rally_that_retraces_a_path_a_little_slower_is_live(monkeypatch):
    """03-11, F3Set: all 61 live strokes lost "as replays" were runs retracing a baseline path a bit slower."""
    from types import SimpleNamespace

    from tennisbio import stages

    fps = 25.0
    t = np.arange(0, 125) / fps
    x = np.sin(t)                                             # side to side along the baseline
    img = np.zeros((len(t), 17, 2))
    sk = {"left_ankle": 15, "right_ankle": 16}
    runs = []
    for k, (start, slow) in enumerate([(0, 1.0), (10, 0.8), (20, 0.4)]):
        frames_k = np.arange(len(t)) + int(start * fps)
        runs.append((frames_k, img, None, None, None))
    d = {"fps": fps, "frames": np.arange(0, 2000)}
    monkeypatch.setattr(stages, "court_at", lambda court, t0: (np.eye(3), None))
    paths = iter([np.column_stack([x, np.zeros_like(x)]), np.column_stack([x * 0.8, np.zeros_like(x)]),
                  np.column_stack([np.sin(t * 0.4), np.zeros_like(x)])])
    monkeypatch.setattr("tennisbio.court_metrics.to_court", lambda H, feet: next(paths))
    onsets = np.arange(0, 30, 1.2)                            # hits heard all along: live play
    hits = np.arange(0, 30, 1.2)
    reasons, _ = stages.run_replay_reasons(d, sk, runs, {}, onsets, {}, hits)
    assert reasons[1] is None                                 # a little slower, with its hits heard: live
    assert stages.REPLAY_SLOW_RATIO == 0.5
