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


def test_first_stroke_of_a_point_without_serve_is_described():
    readings = [_r(0, (0, 0)), _r(40, (15, 0))]
    strokes = [{"stroke": "backhand", "stroke_source": "pose", "stroke_pose": "backhand", "side": "near",
                "court_pos_m": [1.0, -0.3], "match_time_s": 25}]
    g = serve_gaps(readings, strokes, [(20, 60)])
    fw = g["first_strokes_without_serve"]
    assert fw["n"] == 1 and fw["type"] == {"backhand/pose": 1} and fw["behind_baseline"] == 1


def test_her_first_stroke_behind_the_baseline_in_a_point_of_her_serve_becomes_her_serve():
    from tennisbio.point_count import SERVE_RULE, serves_by_rule
    readings = [_r(0, (0, 0)), _r(40, (15, 0)), _r(80, (30, 0)), _r(120, (40, 0)),
                _r(160, (40, 0), server=1, games=((3, 1),)), _r(200, (40, 15), server=1, games=((3, 1),))]
    strokes = [
        {"stroke": "forehand", "match_time_s": 8, "court_pos_m": [1.0, -0.2],
         "metrics": {"contact_height_pct": 130}},                                 # point 1: first, behind, hand high → serve
        {"stroke": "backhand", "match_time_s": 12, "court_pos_m": [0.5, 1.0]},     # its rally: unchanged
        {"stroke": "overhead", "match_time_s": 45, "court_pos_m": [1.0, -0.3]},    # point 2: serve already found
        {"stroke": "forehand", "match_time_s": 50, "court_pos_m": [1.0, -0.3]},
        {"stroke": "forehand", "match_time_s": 95, "court_pos_m": [1.0, 2.5]},     # point 3: inside the court: not a serve
        {"stroke": "forehand", "match_time_s": 170, "court_pos_m": [1.0, -0.3]},   # opponent's serve: never
    ]
    n = serves_by_rule(strokes, readings, [(0, 300)])
    assert n == 1
    assert strokes[0]["stroke"] == "overhead" and strokes[0]["stroke_before"] == "forehand" and strokes[0]["stroke_rule"] == SERVE_RULE
    assert [s["stroke"] for s in strokes[1:]] == ["backhand", "overhead", "forehand", "forehand", "forehand"]


def test_a_first_stroke_long_after_the_camera_returns_is_not_taken_for_the_serve():
    from tennisbio.point_count import serves_by_rule
    readings = [_r(0, (0, 0)), _r(60, (15, 0))]
    strokes = [{"stroke": "forehand", "match_time_s": 40, "court_pos_m": [1.0, -0.2], "metrics": {"contact_height_pct": 130}}]
    assert serves_by_rule(strokes, readings, [(10, 100)]) == 0                    # 30 s after the camera came back


def test_a_groundstroke_height_contact_is_never_taken_for_the_serve():
    """Request 104: the rule alone made serves of 31 forehands and backhands in F3Set."""
    from tennisbio.point_count import serves_by_rule
    readings = [_r(0, (0, 0)), _r(40, (15, 0))]
    low = [{"stroke": "forehand", "match_time_s": 8, "court_pos_m": [1.0, -0.2], "metrics": {"contact_height_pct": 60}}]
    none = [{"stroke": "forehand", "match_time_s": 8, "court_pos_m": [1.0, -0.2], "metrics": {}}]
    assert serves_by_rule(low, readings, [(0, 300)]) == 0 and serves_by_rule(none, readings, [(0, 300)]) == 0


def test_the_toss_hand_above_the_head_also_marks_the_serve():
    from tennisbio.point_count import serves_by_rule
    readings = [_r(0, (0, 0)), _r(40, (15, 0))]
    toss = [{"stroke": "forehand", "match_time_s": 8, "court_pos_m": [1.0, -0.2],
             "metrics": {"contact_height_pct": 60, "toss_above_head_bh": 0.2}}]
    flat = [{"stroke": "forehand", "match_time_s": 8, "court_pos_m": [1.0, -0.2],
             "metrics": {"contact_height_pct": 60, "toss_above_head_bh": -0.3}}]
    assert serves_by_rule(toss, readings, [(0, 300)]) == 1 and serves_by_rule(flat, readings, [(0, 300)]) == 0


def test_what_the_spotter_saw_before_her_first_stroke():
    readings = [_r(0, (0, 0)), _r(40, (15, 0)), _r(80, (30, 0))]
    strokes = [{"stroke": "forehand", "side": "near", "match_time_s": 12},
               {"stroke": "forehand", "side": "near", "match_time_s": 55}]
    spotted = [{"t": 9.0, "side": "far", "kind": "forehand"},      # point 1: the opponent's return first
               {"t": 50.0, "side": "near", "kind": "serve"}]       # point 2: her serve spotted, lost later
    g = serve_gaps(readings, strokes, [(0, 300)], spotted=spotted)
    sb = g["spotter_before_first"]
    assert sb["golpe_de_la_rival_antes"] == 1 and sb["saque_suyo_visto_y_perdido"] == 1


def test_a_serve_candidate_is_added_before_the_opponents_return_when_hers_was_not_seen(monkeypatch):
    import tennisbio.stages as S
    readings = [_r(0, (0, 0)), _r(40, (15, 0)), _r(80, (30, 0))]
    cands = [{"t": 20.0, "target": False, "side": "far", "source": "spotter"},      # point 1: the return only
             {"t": 21.5, "target": True, "side": "near", "source": "spotter"},
             {"t": 50.0, "target": True, "side": "near", "source": "spotter", "kind": "serve"},   # point 2: her serve seen
             {"t": 50.9, "target": False, "side": "far", "source": "spotter"}]
    monkeypatch.setattr(S, "near_is_target", lambda identity, frame: True)
    n = S.add_serve_candidates(cands, {"readings": readings}, {"fps": 25}, 25.0)
    assert n == 1
    new = [c for c in cands if c["source"] == "marcador"]
    assert new == [{"t": 19.2, "audio": False, "side": "near", "identity": True, "target": True, "kind": "serve",
                    "score": None, "source": "marcador"}]


def test_a_scoreboard_serve_candidate_is_named_serve_in_the_fine_pass():
    from tennisbio.stages import stroke_from_spotter
    from tennisbio.stroke_analysis import StrokeResult
    r = StrokeResult(impact_frame=10, impact_source="spotter", stroke="backhand")
    stroke_from_spotter(r, {"source": "marcador", "kind": "serve"})
    assert r.stroke == "overhead"
