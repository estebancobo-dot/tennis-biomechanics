import numpy as np

from tennisbio.validation.impact_eval import GTEvent, Pred, clip_bounds, match, parse_label, summarize
from tennisbio.validation.racket_eval import match_racket, summarize as rsummary


def test_parse_f3set_label():
    g = parse_label(103, "near_ad_return_bh_gs_DM_-_in")
    assert (g.side, g.shot, g.hand, g.technique) == ("near", "return", "bh", "gs")
    assert clip_bounds("20210909-W-US_Open-SF-Emma_Raducanu-Maria_Sakkari_1993_2403") == \
        ("20210909-W-US_Open-SF-Emma_Raducanu-Maria_Sakkari", 1993, 2403)


def test_match_and_summary():
    gts = [GTEvent(100, "near", "stroke", "fh", "gs"), GTEvent(200, "near", "stroke", "bh", "slice")]
    preds = [Pred(102, "fh"), Pred(150, "fh"), Pred(199, "fh")]
    pairs, fp, fn = match(preds, gts, tol=3)
    s = summarize(pairs, fp, fn)
    assert (s["true_positives"], len(fp), len(fn)) == (2, 1, 0)
    assert s["precision"] == round(2 / 3, 3) and s["recall"] == 1.0
    assert s["fh_bh_accuracy"] == 0.5


def test_racket_eval_on_a_perfect_outline():
    # ground truth: butt at (100, 300), tip at (160, 200); outline = thin quad along that axis
    kps = np.array([[160, 200, 1], [145, 225, 1], [100, 300, 1], [150, 210, 1], [168, 222, 1]], float)
    poly = np.array([[98, 302], [102, 298], [166, 196], [158, 204]], float)
    m = match_racket(kps, [95, 195, 75, 110], [poly], wrists=np.array([[97.0, 305.0]]))
    assert m.detected and m.head_correct
    assert m.axis_err_deg < 5
    s = rsummary([m])
    assert s["recall"] == 1.0 and s["axis_within_15deg"] == 1.0


def test_racket_eval_counts_misses():
    kps = np.array([[160, 200, 1], [145, 225, 1], [100, 300, 1], [150, 210, 1], [168, 222, 1]], float)
    m = match_racket(kps, [95, 195, 75, 110], [], wrists=np.zeros((0, 2)))
    assert not m.detected and rsummary([m])["recall"] == 0.0
