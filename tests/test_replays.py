import numpy as np

from tennisbio.replays import Run, find_replays, matches, path_speed

FPS = 25.0


def run_along(t0, xs, ys, speed=1.0, impacts=2):
    """A run following the polyline (xs, ys) at `speed` × normal pace (0.25 = 4× slow motion)."""
    n = int(len(xs) / speed)
    s = np.linspace(0, len(xs) - 1, n)
    p = np.stack([np.interp(s, np.arange(len(xs)), xs), np.interp(s, np.arange(len(ys)), ys)], 1)
    return Run(t0, t0 + n / FPS, p, FPS, impacts)


LIVE = (np.linspace(0, 4, 60), np.full(60, 1.0))            # 4 m sideways along the baseline in 2.4 s


def test_slow_motion_replay_is_found_and_live_points_are_kept():
    live = run_along(0, *LIVE)
    other = run_along(20, np.linspace(0, -3, 60), np.linspace(1, 3, 60))   # next point: a different path
    replay = run_along(10, *LIVE, speed=0.25, impacts=0)                    # same path, 4× slower
    assert path_speed(replay.path, FPS) < 0.5 * path_speed(live.path, FPS)
    assert find_replays([live, replay, other]) == [1]


def test_same_path_live_with_sound_and_speed_is_not_a_replay():
    a = run_along(0, *LIVE)
    b = run_along(15, *LIVE)                                   # she repeats the pattern in the next point
    assert matches(b, a) and find_replays([a, b]) == []


def test_normal_speed_replay_without_impact_sounds():
    assert find_replays([run_along(0, *LIVE), run_along(8, *LIVE, impacts=0)]) == [1]


def test_standing_still_or_unseen_never_decides():
    still = run_along(0, np.full(60, 1.0), np.full(60, 1.0))
    assert not matches(run_along(5, np.full(60, 1.0), np.full(60, 1.0), speed=0.25, impacts=0), still)
    blind = Run(5, 9, np.full((80, 2), np.nan), FPS, 0)
    assert find_replays([run_along(0, *LIVE), blind]) == []
    assert find_replays([run_along(0, *LIVE), run_along(200, *LIVE, speed=0.25, impacts=0)]) == []   # too late
