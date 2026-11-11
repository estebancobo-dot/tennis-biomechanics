import numpy as np

from tennisbio.ball_reuse import window_from_play


def test_the_play_ball_is_resampled_to_the_window_frames():
    # the detector's ball at 25 fps over the play (fractions of the frame); a 50 fps window from t0 = 10.0 s
    t = 10.0 + np.arange(10) / 25.0
    track = np.column_stack([t, np.linspace(0.1, 0.5, 10), np.full(10, 0.5), np.full(10, 0.9)])
    track[5, 1:3] = np.nan                                   # unseen there
    w = window_from_play(track, 10.0, 18, 50.0, 1280, 720)
    assert w.shape == (18, 3)
    assert np.isclose(w[0, 0], 0.1 * 1280) and np.isclose(w[0, 1], 360) and np.isclose(w[0, 2], 0.9)
    assert np.isclose(w[1, 0], (0.1 + 0.4 / 9 / 2) * 1280)    # halfway between two samples
    assert np.isnan(w[9, 0]) and np.isnan(w[10, 0]) and np.isnan(w[11, 0])   # around the unseen sample: no ball
    assert np.isfinite(w[12, 0])


def test_no_play_track_gives_no_ball():
    assert np.isnan(window_from_play(np.zeros((0, 4)), 0.0, 5, 50.0, 1280, 720)).all()
