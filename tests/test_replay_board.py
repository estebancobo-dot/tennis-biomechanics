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
