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
