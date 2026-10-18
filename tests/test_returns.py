"""The return of serve: recognised from the scoreboard and her first hit, with its variants."""
from tennisbio.returns import (apply, points_played, return_of_serve, return_type, serve_box, serve_number,
                               side_from_score)


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


def tech(takeback="compacta", finish="limpiaparabrisas", fin_h=-10.0, swing="liftado (de abajo arriba)", jit=None):
    return {"classes": {"takeback": takeback, "finish": finish, "swing": swing},
            "phases": {"finish": {"wrist_dom_vs_shoulder": fin_h}}, "stroke": {},
            "jitter": {"class.takeback": 0.0, "class.finish": 0.0, "finish.wrist_dom_vs_shoulder": 1.0} if jit is None else jit}


def test_return_type_from_existing_classes():
    # compact preparation + the hand ends in front of her, below the shoulder: a block
    assert return_type(tech()) == ("bloqueo", 0.0)
    # compact preparation, full finish (over the shoulder, or around the body even if low)
    assert return_type(tech(finish="sobre el hombro", fin_h=5.0))[0] == "armado corto"
    assert return_type(tech(finish="alrededor del cuerpo (cintura contraria)", fin_h=-10.0))[0] == "armado corto"
    # a wiper finish that comes up to the shoulder is not short
    assert return_type(tech(fin_h=-2.0))[0] == "armado corto"
    assert return_type(tech(takeback="amplia", finish="sobre el hombro", fin_h=8.0))[0] == "swing completo"
    assert return_type(tech(takeback="en bucle alto", finish="látigo (sobre el mismo hombro)", fin_h=12.0))[0] == "swing completo"
    # a wide preparation with a short finish is none of the kinds coaches name: not given
    assert return_type(tech(takeback="amplia")) == (None, None)
    # the hand path high → low before contact (class swing) is a sliced return, whatever the rest
    assert return_type(tech(takeback="amplia", swing="cortado (de arriba abajo)"))[0] == "cortado"
    # missing parts: nothing invented
    assert return_type(tech(takeback=None)) == (None, None)
    t = tech()
    del t["phases"]["finish"]
    assert return_type(t) == (None, None)


def test_return_type_flip_from_its_parts():
    # the flips of its classes add up; a finish height within its own frame-to-frame change of the
    # boundary counts as a flip
    assert return_type(tech(jit={"class.takeback": 0.1, "class.finish": 0.05, "finish.wrist_dom_vs_shoulder": 0.5}))[1] == 0.15
    assert return_type(tech(fin_h=-3.5, jit={"class.takeback": 0.0, "finish.wrist_dom_vs_shoulder": 1.0}))[1] == 1.0
    # without the takeback's own repeatability the class is not judged (sin juzgar)
    assert return_type(tech(jit={}))[1] is None


def test_apply_return_type_only_on_near_forehand_returns():
    d = stroke(technique=tech())
    apply(d, 1, (95.0, 120.0), [])
    assert d["technique"]["classes"]["return_type"] == "bloqueo"
    assert d["technique"]["jitter"]["class.return_type"] == 0.0
    d["score"]["server"] = 0                          # she served: no return, the class goes
    apply(d, 1, (95.0, 120.0), [])
    assert "return_type" not in d["technique"]["classes"] and "class.return_type" not in d["technique"]["jitter"]
    far = stroke(side="far", technique=tech())
    apply(far, 1, (95.0, 120.0), [])
    assert far["is_return"] and "return_type" not in far["technique"]["classes"]
    bh = stroke(stroke="backhand", technique=tech())
    apply(bh, 1, (95.0, 120.0), [])
    assert "return_type" not in bh["technique"]["classes"]
    rally = stroke(technique=tech())
    apply(rally, 3, (95.0, 120.0), [])                # not her first hit: not a return
    assert "return_type" not in rally["technique"]["classes"]


def test_return_type_is_a_learn_condition_with_its_source():
    from tennisbio.audit import planned_keys
    from tennisbio.explain import COACH
    from tennisbio.learn import CONDITIONS, RELAX_ORDER
    from tennisbio.model import CLASS_KEYS
    from tennisbio.returns import RETURN_TYPES

    name, levels = CONDITIONS["return_type"]
    assert name == "Tipo de resto" and set(levels) == set(RETURN_TYPES)
    assert all(len(t) == 3 and all(x for x in t) for t in levels.values())     # what changes, cue, drill
    assert "return_type" in RELAX_ORDER and RELAX_ORDER.index("return_type") > RELAX_ORDER.index("serve_number")
    assert "Ivanovic" in COACH["class.return_type"][1] and "class.return_type" in planned_keys()
    assert "return_type" in CLASS_KEYS


def _report_rows(flip):
    rows = []
    for i in range(12):
        t = tech(takeback="compacta" if i % 2 else "amplia", finish="limpiaparabrisas" if i % 2 else "sobre el hombro",
                 fin_h=-10.0 if i % 2 else 8.0)
        t["classes"]["return_type"] = return_type(t)[0]
        t["jitter"]["class.return_type"] = flip
        rows.append({"stroke": "forehand", "match_time_s": 10.0 + i, "impact_source": "audio+ball+swing", "review": [],
                     "metrics": {"contact_height_pct": 55.0}, "phases": {"impact": {"t_rel": 0.0}, "ready": {"t_rel": -0.6}},
                     "technique": t, "court_pos_m": [1.0, -1.0], "is_return": True})
    return rows


def test_report_gates_the_return_type_by_its_reliability(tmp_path):
    import json

    from tennisbio.audit import report_data
    from tennisbio.catalog import Match, Player
    from tennisbio.report import build

    for flip, kept in ((0.05, True), (0.6, False)):
        root = tmp_path / str(flip)
        (root / "m1").mkdir(parents=True)
        (root / "m1" / "strokes.json").write_text(json.dumps(_report_rows(flip)), encoding="utf-8")
        data = report_data(build([Match("m1", None, Player("p", "P"))], root))
        assert data["reliability"]["class.return_type"]["verdict"] == ("fiable" if kept else "ruido")
        got = {r["cl"].get("return_type") for r in data["strokes"]}
        assert got == ({"bloqueo", "swing completo"} if kept else {None})
