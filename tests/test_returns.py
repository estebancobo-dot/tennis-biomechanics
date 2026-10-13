"""The return of serve: recognised from the scoreboard and her first hit, with its variants."""
from tennisbio.returns import apply, points_played, return_of_serve, serve_box, serve_number, side_from_score


def stroke(**kw):
    d = {"match_time_s": 100.0, "side": "near", "metrics": {"time_available_s": 1.0},
         "score": {"server": 1, "points": ["15", "30"], "tiebreak": False, "banner": ""},
         "bounce_court_m": [3.6, 8.0], "pos_at_opp_m": [2.0, -1.8], "court_pos_m": [3.0, -0.9],
         "technique": {"classes": {"play": "inicio del punto"}, "stroke": {}}}
    d.update(kw)
    return d


def test_points_and_side():
    assert points_played(["15", "30"]) == 3 and side_from_score({"points": ["15", "30"]}) == "ventaja"
    assert points_played(["40", "40"]) == 6 and side_from_score({"points": ["40", "40"]}) == "iguales"
    assert points_played(["AD", "40"]) == 7
    assert points_played([None, "15"]) == 1
    assert points_played(["3", "2"], tiebreak=True) == 5
    assert points_played([None, None]) is None and points_played(["x", "15"]) is None


def test_serve_box_thirds_and_side():
    assert serve_box([0.5, 9.0]) == ("iguales", "a la T")
    assert serve_box([-2.0, 9.0]) == ("ventaja", "al cuerpo")
    assert serve_box([3.9, 6.0]) == ("iguales", "abierto")
    assert serve_box([2.0, 3.0]) is None                     # not in a service box
    assert serve_box(None) is None


def test_second_serve_from_an_earlier_fault_in_the_shot():
    cands = [{"t": 80.0, "side": "far"}, {"t": 99.0, "side": "far"}]
    assert serve_number(99.0, (75.0, 120.0), cands, "near") == "segundo saque"
    assert serve_number(99.0, (95.0, 120.0), cands, "near") == "primer saque"
    # a rally in between: it was another point, not a fault
    cands2 = cands + [{"t": 82.0, "side": "near"}]
    assert serve_number(99.0, (75.0, 120.0), cands2, "near") == "primer saque"
    assert serve_number(99.0, None, [], "near", banner="2ND SERVE") == "segundo saque"
    assert serve_number(99.0, (98.5, 120.0), [], "near") is None   # the shot starts too late to know


def test_return_classes_and_values():
    r = return_of_serve(stroke(), 1, (95.0, 120.0), [{"t": 99.0, "side": "far"}])
    assert r["is_return"] and r["classes"]["play"] == "resto"
    assert r["classes"]["serve_dir"] == "abierto" and r["classes"]["serve_number"] == "primer saque"
    # score says advantage court (3 points) but the serve bounced in the deuce box: side not given
    assert "return_side" not in r["classes"]
    assert r["values"] == {"return_ready_depth_m": -1.8, "return_step_in_m": 0.9}
    ok = return_of_serve(stroke(score={"server": 1, "points": ["15", "15"]}), 1, None, [])
    assert ok["classes"]["return_side"] == "iguales"


def test_not_a_return():
    assert return_of_serve(stroke(score={"server": 0, "points": ["0", "0"]}), 1, None, [])["is_return"] is False
    assert return_of_serve(stroke(), 2, None, [])["is_return"] is False
    assert return_of_serve(stroke(score={}), None, None, []) == {}
    # no scoreboard: the audio rule of the fine pass stands
    assert return_of_serve(stroke(score={}, is_return=True), None, None, [])["is_return"] is True


def test_apply_writes_and_clears():
    d = stroke()
    apply(d, 1, (95.0, 120.0), [])
    t = d["technique"]
    assert d["is_return"] and t["classes"]["play"] == "resto" and t["stroke"]["return_step_in_m"] == 0.9
    d["score"]["server"] = 0                          # recomputed: she served, so it is no return
    apply(d, 1, (95.0, 120.0), [])
    assert not d["is_return"] and t["classes"]["play"] == "inicio del punto"
    assert "serve_dir" not in t["classes"] and "return_step_in_m" not in t["stroke"]
