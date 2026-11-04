"""Points on her serve with no serve found, and why (B4, 04-11)."""
from tennisbio.point_count import serve_gaps


def _r(t, pts, server=0, games=((2, 1),)):
    return {"t": t, "games": [list(g) for g in games], "points": list(pts), "server": server}


def test_each_point_on_her_serve_is_found_or_given_its_cause():
    readings = [_r(0, (0, 0)), _r(40, (15, 0)), _r(80, (30, 0)), _r(120, (40, 0)), _r(160, (40, 15))]
    strokes = [{"stroke": "overhead", "match_time_s": 20},                 # point 1: her serve found
               {"stroke": "forehand", "match_time_s": 70}]                 # point 2: a stroke, no serve
    main = [(0, 74), (130, 170)]                                           # point 3 (75-120): not on the main camera
    g = serve_gaps(readings, strokes, main)
    assert g["points"] == 4 and g["found"] == 1
    assert [x["cause"] for x in g["gaps"]] == ["sin_saque", "sin_camara", "sin_golpes"]


def test_points_on_her_opponents_serve_are_not_counted():
    readings = [_r(0, (0, 0), server=1), _r(40, (15, 0), server=1)]
    assert serve_gaps(readings, [], [(0, 100)])["points"] == 0


def test_no_main_camera_is_its_own_cause():
    readings = [_r(100, (0, 0)), _r(140, (15, 0))]
    g = serve_gaps(readings, [], [(0, 50)])
    assert g["gaps"] == [{"t0": 95.0, "t1": 140.0, "cause": "sin_camara"}]


def test_serves_found_are_placed_in_her_points_the_opponents_or_none():
    readings = [_r(0, (0, 0)), _r(40, (15, 0)), _r(60, (15, 0), server=1, games=((2, 2),)),
                _r(100, (15, 0), server=1, games=((2, 2),)), _r(140, (15, 15), server=1, games=((2, 2),))]
    strokes = [{"stroke": "overhead", "match_time_s": t} for t in (10, 120, 400)]
    g = serve_gaps(readings, strokes, [(0, 500)])
    assert g["serves_at"] == {"her_points": 1, "opponent_points": 1, "elsewhere": 1}


def test_gaps_say_when_her_first_stroke_comes_after_the_main_camera_returns():
    readings = [_r(0, (0, 0)), _r(40, (15, 0))]
    strokes = [{"stroke": "forehand", "match_time_s": 30}]
    g = serve_gaps(readings, strokes, [(20, 60)])          # the main camera comes back at 20 s
    assert g["gaps"][0]["shot_start"] == 20 and g["gaps"][0]["first_stroke_after_s"] == 10
    assert g["first_stroke_after_shot_start_s"] == {"median": 10, "n": 1, "under_3": 0}
