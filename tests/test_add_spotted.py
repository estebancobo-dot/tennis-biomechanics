import numpy as np

from tennisbio.impacts import Impact, add_spotted


class _Hit:
    def __init__(self, frame, side):
        self.frame, self.side = frame, side


def test_a_spotted_stroke_the_rules_missed_is_added():
    speed = np.zeros(200)
    speed[104] = 3.0
    out = add_spotted([], 50.0, [2.0], [], speed, 200, 0.4)
    assert [(i.frame, i.source) for i in out] == [(104, "spotter")]        # timed at the wrist's peak


def test_snapped_to_her_ball_hit_and_not_doubled():
    hits = [_Hit(97, "near"), _Hit(100, "far")]
    out = add_spotted([], 50.0, [2.0], hits, None, 200, 0.4)
    assert [(i.frame, i.source) for i in out] == [(97, "spotter+ball")]
    rules = [Impact(110, 2.2, "ball+swing", None, 0.95)]
    assert add_spotted(rules, 50.0, [2.0], hits, None, 200, 0.4) == rules   # the rules already have it


def test_outside_the_clip_is_ignored():
    assert add_spotted([], 50.0, [10.0, -1.0], [], None, 200, 0.4) == []
