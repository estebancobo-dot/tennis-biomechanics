import numpy as np

from tennisbio.clip_pipeline import near_person, refind_at_targets


def _frames(T=100, cut=21):
    giant = np.array([[409.0, 84.0, 1360.0, 905.0]])                    # a close-up before the main camera came back
    her = lambda t: np.array([[900.0 + t, 660.0, 1010.0 + t, 870.0]])   # her, 210 px, moving a little
    boxes = [giant if t < cut else her(t) for t in range(T)]
    feats = [np.ones((1, 32), np.float32) for _ in range(T)]
    return boxes, feats


def test_her_track_lost_after_a_close_up_is_found_again_at_the_contact():
    # 12-11 (R10): the final's strokes 0105506/0105738: one person at the impact, her track empty since a close-up
    boxes, feats = _frames()
    sel = np.full(100, -1)
    sel[:21] = 0                                                       # the track followed the close-up, then lost
    n = refind_at_targets(sel, boxes, feats, [80 / 50], 50.0, 1080, 100)
    assert n == 1 and (sel[21:] == 0).all() and (sel[:21] == 0).all()   # the gap filled, the tracked part untouched


def test_nothing_changes_when_she_is_tracked_or_only_close_ups_are_there():
    boxes, feats = _frames()
    sel = np.zeros(100, int)
    assert refind_at_targets(sel, boxes, feats, [80 / 50], 50.0, 1080, 100) == 0
    boxes = [np.array([[409.0, 84.0, 1360.0, 905.0]])] * 100           # only a close-up: no near player to take
    sel = np.full(100, -1)
    assert refind_at_targets(sel, boxes, feats, [80 / 50], 50.0, 1080, 100) == 0 and (sel == -1).all()
    assert near_person(np.zeros((0, 4)), 1080) is None
