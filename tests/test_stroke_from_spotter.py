"""The learned spotter names the stroke type in the fine pass (04-11): the pose vote called most forehands and
serves «backhand» on F3Set."""
from tennisbio.stages import stroke_from_spotter
from tennisbio.stroke_analysis import StrokeResult


def _r(stroke):
    return StrokeResult(impact_frame=10, impact_source="spotter", stroke=stroke)


def test_spotter_kind_wins_and_the_pose_answer_is_kept():
    r = _r("backhand")
    stroke_from_spotter(r, {"source": "spotter", "kind": "forehand"})
    assert (r.stroke, r.stroke_pose, r.stroke_source) == ("forehand", "backhand", "detector")
    r = _r("backhand")
    stroke_from_spotter(r, {"source": "spotter", "kind": "serve"})
    assert r.stroke == "overhead" and r.to_dict()["stroke_pose"] == "backhand"


def test_other_kinds_and_rule_candidates_keep_the_pose_vote():
    r = _r("forehand")
    stroke_from_spotter(r, {"source": "spotter", "kind": "other"})
    assert (r.stroke, r.stroke_source) == ("forehand", "pose")
    r = _r("backhand")
    stroke_from_spotter(r, {"kind": "forehand"})               # a candidate of the rules: no spotter kind
    assert (r.stroke, r.stroke_source) == ("backhand", "pose")
