import numpy as np

from tennisbio.outcome import crossed_net, shot_outcome


def test_outcomes():
    on = np.array([10.0, 11.4])                                   # her hit, opponent's return
    assert shot_outcome(10.0, True, 10.8, None, on, 30.0, True) == "rally"
    assert shot_outcome(10.0, False, 10.8, None, on, 30.0, True) == "out"
    quiet = np.array([10.0, 10.8])                                # only her hit and her ball's bounce
    assert shot_outcome(10.0, True, 10.8, None, quiet, 13.0, True) == "winner"
    assert shot_outcome(10.0, None, None, None, quiet, 12.0, False) == "net"
    assert shot_outcome(10.0, None, None, None, on, 30.0, True) == "rally"
    assert shot_outcome(10.0, True, 10.8, 11.4, quiet, 13.0, True) == "rally"


def test_crossed_net():
    ball = np.full((40, 2), np.nan)
    ball[:, 1] = np.linspace(800, 0, 40)                        # goes up the image past the net row 400
    assert crossed_net(ball, 5, 25, 400) is True
    ball[:, 1] = np.linspace(800, 450, 40)
    assert crossed_net(ball, 5, 25, 400) is False
    assert crossed_net(None, 5, 25, 400) is None
