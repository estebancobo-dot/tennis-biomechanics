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
    cands = [{"t": 5.0, "target": True, "side": "near", "source": "spotter"},       # the previous point's last stroke
             {"t": 20.0, "target": False, "side": "far", "source": "spotter"},      # point 1: the return only
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


def test_the_previous_points_last_stroke_is_not_taken_for_the_return(monkeypatch):
    """Request 118: the window opened on the previous point's last strokes and invented serves (F3Set 94.5 → 87.3 %)."""
    import tennisbio.stages as S
    readings = [_r(0, (0, 0)), _r(40, (15, 0))]
    cands = [{"t": 0.5, "target": False, "side": "far"},          # the previous point's rally
             {"t": 1.2, "target": True, "side": "near"},
             {"t": 2.0, "target": False, "side": "far"},          # the previous point's last stroke
             {"t": 18.0, "target": True, "side": "near"},         # her serve, seen
             {"t": 18.8, "target": False, "side": "far"}]         # the return
    monkeypatch.setattr(S, "near_is_target", lambda identity, frame: True)
    assert S.add_serve_candidates(cands, {"readings": readings}, {"fps": 25}, 25.0) == 0


def test_a_return_after_a_pause_with_her_serve_unseen_gets_one(monkeypatch):
    import tennisbio.stages as S
    readings = [_r(0, (0, 0)), _r(40, (15, 0))]
    cands = [{"t": 0.5, "target": False, "side": "far"}, {"t": 1.2, "target": True, "side": "near"},
             {"t": 2.0, "target": False, "side": "far"},
             {"t": 18.8, "target": False, "side": "far"}, {"t": 20.0, "target": True, "side": "near"}]
    monkeypatch.setattr(S, "near_is_target", lambda identity, frame: True)
    assert S.add_serve_candidates(cands, {"readings": readings}, {"fps": 25}, 25.0) == 1
    assert any(c.get("source") == "marcador" and abs(c["t"] - 18.0) < 1e-6 for c in cands)


def test_no_serve_is_added_when_the_opponents_first_stroke_is_her_own_serve(monkeypatch):
    """Request 120: the scoreboard's server misread; the opponent served (the spotter says so) and a false serve of
    hers was added before it (F3Set: 17 and 39 added where her serves were already found)."""
    import tennisbio.stages as S
    readings = [_r(0, (0, 0)), _r(40, (15, 0))]
    cands = [{"t": 0.5, "target": False, "side": "far"}, {"t": 1.2, "target": True, "side": "near"},
             {"t": 18.8, "target": False, "side": "far", "kind": "serve"},
             {"t": 19.6, "target": True, "side": "near", "kind": "forehand"}]
    monkeypatch.setattr(S, "near_is_target", lambda identity, frame: True)
    assert S.add_serve_candidates(cands, {"readings": readings}, {"fps": 25}, 25.0) == 0


def test_points_without_her_strokes_say_whether_anybody_played_in_them():
    from tennisbio.point_count import serve_gaps
    readings = [_r(0, (0, 0)), _r(40, (15, 0)), _r(80, (30, 0))]
    spotted = [{"t": 20.0, "side": "far", "kind": "forehand"}]            # point 1: only the opponent seen
    g = serve_gaps(readings, [], [(0.0, 30.0), (60.0, 70.0)], spotted=spotted)   # point 2: nobody
    assert g["by_cause"]["sin_golpes"] == 2
    assert g["no_strokes_points"]["golpes_de_alguien"] == 1 and g["no_strokes_points"]["nadie_golpea"] == 1
    assert g["no_strokes_points"]["camara_principal_s_mediana"] in (10.0, 30.0)


def test_points_without_her_strokes_say_whose_the_candidates_were():
    from tennisbio.point_count import serve_gaps
    readings = [_r(0, (0, 0)), _r(40, (15, 0)), _r(80, (30, 0)), _r(120, (40, 0)), _r(160, (40, 15))]
    cands = [{"t": 20.0, "target": True}, {"t": 60.0, "target": False}, {"t": 100.0, "target": None}]
    g = serve_gaps(readings, [], [(0.0, 160.0)], spotted=[], candidates=cands)
    assert g["no_strokes_points"]["candidatos"] == {"suyos_perdidos_despues": 1, "solo_de_la_rival": 1,
                                                   "identidad_sin_decidir": 1, "sin_candidatos": 1}


def test_points_nobody_plays_in_are_unseen_and_lost_strokes_say_where_they_went():
    from tennisbio.point_count import serve_gaps
    readings = [_r(0, (0, 0)), _r(40, (15, 0)), _r(80, (30, 0)), _r(120, (40, 0))]
    cands = [{"t": 20.0, "target": True}, {"t": 60.0, "target": True}]
    doubtful = [{"match_time_s": 61.0}]
    g = serve_gaps(readings, [], [(0.0, 120.0)], spotted=[{"t": 20.0, "side": "near"}], candidates=cands,
                   doubtful=doubtful)
    assert g["unseen"] == 1                                    # point 3: nobody, nothing
    assert g["no_strokes_points"]["suyos_perdidos"] == {"de_identidad_dudosa": 1, "descartados_en_la_pasada_fina": 1}


def test_lost_strokes_say_why_the_fine_pass_dropped_them():
    from tennisbio.point_count import serve_gaps
    readings = [_r(0, (0, 0)), _r(40, (15, 0)), _r(80, (30, 0))]
    cands = [{"t": 20.0, "target": True}, {"t": 60.0, "target": True}]
    dropped = [{"t": 20.0, "target": True, "why": "cribado_por_la_bola"}]
    g = serve_gaps(readings, [], [(0.0, 80.0)], spotted=[], candidates=cands, doubtful=[], dropped=dropped)
    assert g["no_strokes_points"]["motivos_descarte"] == {"cribado_por_la_bola": 1, "sin_registro": 1}


def test_the_fine_pass_records_why_it_dropped_a_candidate():
    import tennisbio.stages as S
    S._GATE.clear()
    S._GATE.update(passed=0, gated=0, off=0, reasons={}, seconds_gated=0.0, dropped=[])
    S._drop([{"t": 12.3456, "side": "near", "target": True, "source": "marcador", "kind": "serve"}], "cribado_por_la_bola")
    assert S._GATE["dropped"] == [{"t": 12.346, "why": "cribado_por_la_bola", "side": "near", "target": True,
                                   "source": "marcador", "kind": "serve"}]
    r = {"times": {}, "counts": {}, "gate": {"passed": 0, "gated": 1, "off": 0, "seconds_gated": 0.0, "reasons": {},
                                             "dropped": [{"t": 1.0, "why": "x"}]}}
    S._merge_fine_stats(r)
    assert len(S._GATE["dropped"]) == 2


def test_a_scoreboard_serve_window_is_not_ruled_out_by_the_ball(monkeypatch, tmp_path):
    """Request 135: 8 of her 10 strokes lost in points of her serve were ruled out by the ball alone."""
    from types import SimpleNamespace
    import numpy as np
    import tennisbio.stages as S
    import tennisbio.clip_pipeline as CP
    import tennisbio.fine_gate as FG

    monkeypatch.setattr(CP, "window_ball", lambda clip, cache, ball: (np.zeros((50, 3)), 0.0, 1280, 720, 25.0))
    monkeypatch.setattr(FG, "gate_window", lambda *a, **k: {"passed": False, "reason": "sin_golpe", "possible": []})
    S._GATE.clear()
    S._GATE.update(passed=0, gated=0, off=0, reasons={}, seconds_gated=0.0, dropped=[])
    ctx = SimpleNamespace(cfg={"fine_pass": {}}, log=lambda *a: None)
    swing = [{"t": 10.0, "source": None, "side": "near"}]
    assert S._gate_passes(ctx, swing, 9.0, "w1", tmp_path / "w1.mp4", None, "near", object(), 0.0) == {}
    board = [{"t": 10.0, "source": "marcador", "kind": "serve", "side": "near"}]
    dec = S._gate_passes(ctx, board, 9.0, "w2", tmp_path / "w2.mp4", None, "near", object(), 0.0)
    assert dec["passed"] and dec["reason"] == "detector"


def test_a_far_first_stroke_after_a_pause_is_her_serve():
    """Request 137: at the far end her hands are not measured; the first stroke after a pause, behind her baseline, in
    a point of her serve, is her serve; with a stroke of anybody just before it, it is not."""
    from tennisbio.point_count import serves_by_rule
    readings = [_r(0, (0, 0)), _r(40, (15, 0))]
    far = lambda: [{"match_time_s": 20.0, "stroke": "backhand", "side": "far", "court_pos_m": [1.0, -0.5], "metrics": {}}]
    s = far()
    assert serves_by_rule(s, readings, [(10.0, 39.0)], others=[2.0, 20.0, 21.0]) == 1 and s[0]["stroke"] == "overhead"
    s = far()
    assert serves_by_rule(s, readings, [(10.0, 39.0)], others=[18.5, 20.0]) == 0           # a stroke 1.5 s before
    s = far()
    assert serves_by_rule(s, readings, [(10.0, 39.0)]) == 0                                # nothing known: as before
    s = far()
    s[0]["side"], s[0]["metrics"] = "near", {"contact_height_pct": 60.0}
    assert serves_by_rule(s, readings, [(10.0, 39.0)], others=[2.0]) == 0                 # near: the hand decides
    s = far()
    s[0]["side"] = "near"                                                                 # near, no hand measure
    assert serves_by_rule(s, readings, [(10.0, 39.0)], others=[2.0]) == 1


def test_the_server_is_known_the_first_serve_of_a_point_of_hers_is_hers():
    """Request 139: points of her serve lost her serve because the identity was undecided."""
    import tennisbio.stages as S
    readings = [_r(0, (0, 0)), _r(40, (15, 0))]
    cands = [{"t": 1.0, "target": False, "side": "far"},
             {"t": 18.0, "target": None, "side": "near", "kind": "serve"},      # first after a pause: hers
             {"t": 19.0, "target": None, "side": "far", "kind": "forehand"},    # the return: left as it is
             {"t": 21.0, "target": None, "side": "near", "kind": "serve"}]      # not after a pause
    assert S.serve_identity(cands, {"readings": readings}) == 1
    assert cands[1]["target"] is True and cands[1]["identity"] is True and cands[1]["identity_source"] == "marcador_saque"
    assert cands[2]["target"] is None and cands[3]["target"] is None


def test_a_scoreboard_serve_is_confirmed_in_a_wider_span_and_its_drops_are_counted():
    from types import SimpleNamespace
    import tennisbio.stages as S
    from tennisbio.audit import _board_drops

    run = SimpleNamespace(fps=25.0, strokes=[SimpleNamespace(impact_frame=25 + 13)])      # 0.52 s after the guess
    c = {"t": 11.0, "source": "spotter"}
    assert S._fine_stroke(None, None, c, 10.0, "w", None, "near", run, set(), *[None] * 7) is None
    assert S.SERVE_BOARD_TOL_S >= 0.5
    assert _board_drops([{"source": "marcador", "why": "sin_impacto_cerca"}, {"source": "spotter", "why": "x"}]) == \
        {"sin_impacto_cerca": 1}
