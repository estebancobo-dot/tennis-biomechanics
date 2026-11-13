"""12-11 (B4): a short stretch without the court found inside a main-camera shot that has it is play (a graphic over
the court hid Rybakina's serve for the match on Osaka – Rybakina); a shot where the court is never found is not."""
from tennisbio.stages import COURT_GAP_FILL_S, play_mask


def _sc(shots, fps=10.0):
    return {"fps": fps, "shots": [{"start": a, "end": b, "main_camera": m} for a, b, m in shots]}


def test_a_graphic_over_the_court_inside_a_main_camera_shot_is_play():
    # 64:14-64:26 of Osaka: the court found for 1.1 s, lost for 4.8 s (the banner), found again
    sc = _sc([(0, 120, True)])
    court = {"shots": [{"start": 0, "end": 11, "H": [[1]]}, {"start": 11, "end": 59, "H": None},
                       {"start": 59, "end": 120, "H": [[1]]}]}
    assert play_mask(sc, court).all()


def test_the_end_of_a_short_shot_without_the_court_is_play():
    # 33:03-33:06: a 2.6 s shot, the court found in its first 1.5 s
    sc = _sc([(0, 26, True)])
    court = {"shots": [{"start": 0, "end": 15, "H": [[1]]}, {"start": 15, "end": 26, "H": None}]}
    assert play_mask(sc, court).sum() == 26


def test_long_stretches_and_shots_without_the_court_stay_out():
    fill = int(COURT_GAP_FILL_S * 10)
    sc = _sc([(0, 200, True), (200, 260, True), (260, 300, False)])
    court = {"shots": [{"start": 0, "end": 50, "H": [[1]]}, {"start": 50, "end": 50 + fill + 1, "H": None},
                       {"start": 50 + fill + 1, "end": 200, "H": [[1]]},
                       {"start": 200, "end": 260, "H": None},                 # never found: a ceremony, not play
                       {"start": 260, "end": 300, "H": [[1]]}]}              # not the main camera
    m = play_mask(sc, court)
    assert not m[50:50 + fill + 1].any() and m[:50].all() and m[50 + fill + 1:200].all()
    assert not m[200:].any()


def test_without_court_json_the_main_camera_as_before():
    sc = _sc([(0, 10, True), (10, 20, False)])
    assert play_mask(sc, None).tolist() == [True] * 10 + [False] * 10


def test_the_start_of_a_shot_before_the_court_appears_is_never_filled():
    """13-11 (R22): the first seconds of a shot without the court are still the dissolve from the shot before; filled,
    its people joined the near player's run (F3Set, Azarenka: a point given to the other player)."""
    sc = _sc([(0, 100, True)])
    court = {"shots": [{"start": 0, "end": 40, "H": None}, {"start": 40, "end": 100, "H": [[1]]}]}
    m = play_mask(sc, court)
    assert not m[:40].any() and m[40:].all()
    # a gap after the court was found, and the end of the shot, are still filled
    court = {"shots": [{"start": 0, "end": 30, "H": None}, {"start": 30, "end": 50, "H": [[1]]},
                       {"start": 50, "end": 70, "H": None}, {"start": 70, "end": 90, "H": [[1]]},
                       {"start": 90, "end": 100, "H": None}]}
    m = play_mask(sc, court)
    assert not m[:30].any() and m[30:].all()
