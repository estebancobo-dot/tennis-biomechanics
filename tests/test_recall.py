"""Stroke recall benchmark (validation.recall_eval) and the scoreboard count of the audit (point_count)."""
import json

from tennisbio.point_count import clean_states, count_points, expected_strokes, recall_verdict, remaining_min
from tennisbio.validation import recall_eval as R


def rd(t, games, pts, server=0, tb=False, flags=()):
    return {"t": t, "games": games, "points": pts, "server": server, "tiebreak": tb, "flags": list(flags)}


def game(t0, games, seq, server):
    return [rd(t0 + 20 * i, games, p, server) for i, p in enumerate(seq)]


# --------------------------------------------------------------------------------------- point_count

def test_remaining_min():
    assert remaining_min((0, 0), 0) == 4
    assert remaining_min((2, 1), 0) == 2
    assert remaining_min((0, 3), 0) == 5          # to deuce (3) and two more
    assert remaining_min((3, 3), 1) == 2
    assert remaining_min((4, 3), 0) == 1
    assert remaining_min((4, 3), 1) == 3
    assert remaining_min((6, 5), 0, tiebreak=True) == 1
    assert remaining_min((6, 6), 1, tiebreak=True) == 2


def test_count_simple_games_and_her_serve():
    r = game(0, [[0, 0]], [[None, None], ["15", None], ["30", None], ["40", None]], 0)       # she holds to love
    r += game(100, [[1, 0]], [[None, None], [None, "15"], ["15", "15"], ["15", "30"], ["15", "40"]], 1)
    r += [rd(220, [[1, 1]], [None, None], 0)]
    c = count_points(r)
    assert c["points"] == 4 + 5 and c["points_high"] == 9        # 4-0 and 1-4
    assert c["her_service_points"] == 4
    assert c["games_seen"] == 3 and c["games_unread"] == 0


def test_count_deuce_and_noise():
    seq = [["30", "30"], ["40", "30"], ["40", "40"], ["AD", "40"], ["40", "40"], ["40", "AD"]]
    r = game(0, [[2, 2]], seq, 1)
    r.insert(2, rd(25, [[0, 0]], ["15", None], 0))               # another match's scoreboard
    r.insert(3, rd(26, [[2, 2], [9, 9]], ["15", "15"], 0, flags=["columns_mismatch"]))
    r.append(rd(200, [[2, 3]], [None, None], 0))                  # the opponent won her serve
    c = count_points(r)
    # 30-30 → … → 40-AD is 1+1+1+1+1 = 5 points, then 1 to finish
    assert c["points"] == 6 and c["points_high"] == 8
    assert c["her_service_points"] == 0
    assert len(clean_states(r)) == 7


def test_unread_games_widen_the_range():
    r = [rd(0, [[0, 0]], [None, None], 0), rd(30, [[0, 0]], ["15", None], 0), rd(400, [[2, 1]], [None, None], 1)]
    c = count_points(r)
    assert c["games_unread"] == 2
    assert c["points"] == 1 + 3 + 8 and c["points_high"] == 1 + 3 + 20
    assert 0 < c["unknown_server"] or c["her_service_points"] > 1


def test_tiebreak_points_are_numbers():
    r = [rd(0, [[6, 6]], ["0", "0"], 0, tb=True), rd(10, [[6, 6]], ["3", "2"], 1, tb=True),
         rd(60, [[6, 6]], ["6", "5"], 0, tb=True), rd(90, [[7, 6], [0, 0]], [None, None], 1)]
    c = count_points(r)
    assert c["points"] == 12 and c["her_service_points"] == 6


def test_verdict_red_when_far_too_few():
    counts = {"points": 180, "points_high": 200, "her_service_points": 85.0, "her_service_points_high": 92.0,
              "games_seen": 28, "games_unread": 0}
    ex = expected_strokes(counts)
    assert ex["serves"] == [85, 184] and ex["all_typical"][0] == 288
    st, det = recall_verdict(80, 10, counts)
    assert st == "falta" and "puntos jugados" in det
    assert recall_verdict(300, 90, counts)[0] == "ok"
    assert recall_verdict(250, 90, counts)[0] == "aviso"
    assert recall_verdict(5, 0, {**counts, "points": 6})[0] == "pocos datos"


def test_audit_item_reads_match_folder(tmp_path):
    from tennisbio.audit import recall_items

    d = tmp_path / "m"
    d.mkdir()
    r = []
    for g in range(20):
        r += game(200 * g, [[g // 2 + g % 2, g // 2]], [[None, None], ["15", None], ["30", None], ["40", None]], g % 2)
    (d / "score.json").write_text(json.dumps({"readings": r}))
    (d / "strokes.json").write_text(json.dumps([{"stroke": "forehand", "side": "near"}] * 10))
    it = recall_items([d])
    assert len(it) == 1 and it[0]["status"] == "falta" and it[0]["found"] == 10


# --------------------------------------------------------------------------------------- recall_eval

def clip(video, a, b, events, near="Elena Rybakina", far="Victoria Azarenka"):
    return {"video": f"{video}_{a}_{b}", "fps": 25.0, "near_name": near, "far_name": far,
            "events": [{"frame": f, "label": lab} for f, lab in events]}


def test_player_points_and_kinds():
    cl = [clip("M", 1000, 1200, [(10, "near_deuce_serve_-_-_W_-_in"), (40, "far_ad_return_bh_gs_CC_-_in"),
                                 (70, "near_ad_stroke_fh_gs_DL_-_in"), (100, "far_ad_stroke_fh_volley_DL_approach_winner")]),
          clip("M", 3000, 3100, [(5, "near_deuce_serve_-_-_W_-_in"), (30, "far_ad_return_fh_gs_CC_-_in")],
               near="Victoria Azarenka", far="Elena Rybakina"),
          clip("X", 0, 50, [(5, "near_deuce_serve_-_-_W_-_in")], near="A B", far="C D")]
    pts = R.player_points(cl, "Rybakina")
    assert len(pts) == 2
    ev = pts[0]["events"]
    assert [e["who"] for e in ev] == ["target", "opponent", "target", "opponent"]
    assert [e["kind"] for e in ev] == ["serve", "backhand", "forehand", "volley_other"]
    assert pts[1]["events"][1]["who"] == "target" and pts[1]["events"][1]["side"] == "far"
    assert pts[1]["opponent"] == "Victoria Azarenka"


def test_segments_join_close_points_and_place_events():
    cl = [clip("M", 1000, 1100, [(10, "near_deuce_serve_-_-_W_-_in")]),
          clip("M", 1150, 1250, [(20, "near_deuce_serve_-_-_W_-_in")]),
          clip("M", 5000, 5100, [(30, "near_deuce_serve_-_-_W_-_in")])]
    pts = R.player_points(cl, "Rybakina")
    segs = R.plan_segments(pts, pre_s=6, post_s=3)
    assert len(segs) == 2 and len(segs[0]["points"]) == 2
    off = 0.0
    for s in segs:
        s["offset"] = off
        off += s["src_t1"] - s["src_t0"]
    ev, spans = R.place_events(pts, segs)
    assert abs(ev[0]["t"] - 6.4) < 1e-6                     # 1010/25 − (1000/25 − 6)
    assert abs(ev[1]["t"] - (1170 / 25 - 34)) < 1e-6
    assert abs(ev[2]["t"] - (segs[1]["offset"] + 6 + 30 / 25)) < 1e-6
    assert len(spans) == 3 and spans[0][0] < ev[0]["t"] < spans[0][1]


def test_parse_window_log():
    lines = ["2026-10-19 01:00:34   ventana w000434507_10189 (far, 4 candidatos): pasa · golpe de bola en su lado a 2.44 s",
             "x   ventana w000434507_10189: pose yolo en 509 de 509 fotogramas (92 s)",
             "x   ventana w000413801_4941 (far, 2 candidatos): descartada sin pose · ningún golpe de bola en su lado a ±0.4 s",
             "x   [fine] ventana w000500000_3000 (far, 1 candidatos): pasa · golpe de bola en su lado a 1.0 s",
             "x   ventana w000600000_3000 (near, 1 candidatos): pasa · bola no vista cerca de un candidato (1.2 s): puede haber golpe"]
    w = R.parse_window_log(lines)
    assert [x["passed"] for x in w] == [True, False, True, True]
    assert w[0]["t0"] == 434.507 and w[0]["dur"] == 10.189 and not w[0].get("far_not_found")
    assert w[1]["reason"] == "sin_golpe"
    assert w[2].get("far_not_found") and w[3]["reason"] == "bola_no_vista"


def _ev(t, side="near", kind="forehand", who="target"):
    return {"t": t, "side": side, "kind": kind, "who": who, "point": "p", "label": "x"}


def test_attribute_each_step():
    runs = [{"t0": 0, "t1": 20, "near_is_target": True, "method": "cambios de lado"},
            {"t0": 20, "t1": 30, "near_is_target": True, "method": "cambios de lado", "replay": True},
            {"t0": 30, "t1": 40, "near_is_target": None, "method": None},
            {"t0": 40, "t1": 50, "near_is_target": True, "method": "cambios de lado"},       # she is near
            {"t0": 60, "t1": 100, "near_is_target": True, "method": "ropa"}]
    out = R.Outputs(main_shots=[(0, 55), (60, 100)], runs=runs,
                    cands=[{"t": 2.05, "side": "near", "target": True}, {"t": 62.0, "side": "near", "target": True},
                           {"t": 66.0, "side": "near", "target": True}, {"t": 70.0, "side": "near", "target": True},
                           {"t": 74.0, "side": "near", "target": True}, {"t": 78.0, "side": "near", "target": True}],
                    windows=[{"id": "a", "t0": 60, "dur": 3, "side": "near", "passed": False, "reason": "sin_golpe"},
                             {"id": "b", "t0": 65, "dur": 6, "side": "near", "passed": True, "reason": "golpe_de_bola"},
                             {"id": "c", "t0": 73, "dur": 3, "side": "near", "passed": True, "reason": "golpe_de_bola"}],
                    errors=[78.0], strokes=[{"t": 2.1, "side": "near", "stroke": "forehand"}],
                    ball_seen=lambda w, t: 0.2 if w["id"] == "b" else 0.9)
    evs = [_ev(2.0), _ev(25.0), _ev(35.0), _ev(45.0, side="far"), _ev(57.0), _ev(10.0), _ev(62.0), _ev(66.0),
           _ev(70.0), _ev(74.0), _ev(78.0), _ev(15.0, who="opponent")]
    steps = [a["step"] for a in R.attribute(evs, out)]
    assert steps == ["encontrado", "repeticion", "identidad_sin_decidir", "identidad_equivocada", "fuera_de_camara",
                     "no_candidato", "criba_sin_golpe", "bola_no_vista", "bola_no_vista", "no_confirmado", "error"]


def test_summary_precision_and_identity():
    evs = [_ev(1.0), _ev(5.0, kind="serve"), _ev(9.0, side="far", kind="backhand"), _ev(3.0, who="opponent", side="far")]
    runs = [{"t0": 0, "t1": 8, "near_is_target": True, "method": "cambios de lado", "serve_vote": True},
            {"t0": 8, "t1": 12, "near_is_target": True, "method": "cambios de lado"}]
    out = R.Outputs(main_shots=[(0, 12)], runs=runs,
                    strokes=[{"t": 1.05, "side": "near", "stroke": "forehand"}, {"t": 3.0, "side": "far", "stroke": "forehand"},
                             {"t": 30.0, "side": "near", "stroke": "forehand"}])
    attr = R.attribute(evs, out)
    s = R.summarize(attr, evs, out.strokes, [(0, 10)], 0.2, runs,
                    [{"t0": 0, "t1": 7, "near_is_target": True}, {"t0": 8.5, "t1": 10, "near_is_target": False}])
    assert s["total"] == {"gt": 3, "found": 1, "recall": 0.333, "found_doubtful": 0, "recall_any": 0.333}
    assert s["by_side"]["far"]["gt"] == 1 and s["by_kind"]["serve"]["found"] == 0
    assert s["precision"]["predicted_in_points"] == 2 and s["precision"]["opponent_strokes"] == 1
    assert s["steps"]["identidad_equivocada"] == 1
    idn = s["identity"]
    assert idn["strokes"]["right"] == 2 and idn["strokes"]["wrong"] == 1 and idn["strokes"]["lost_by_identity"] == 1
    assert idn["runs_by_cue"]["cambios de lado"] == {"runs": 2, "right": 1, "wrong": 1, "undecided": 0,
                                                       "serve_vote": 1, "return_vote": 0}
    md = R.to_markdown({"player": "Rybakina", "tol_s": 0.2, "points": 2, "matches": ["M"], "summary": s})
    assert "identidad equivocada" in md and "Recall por lado y tipo" in md


def test_doubtful_strokes_are_found_but_kept_apart():
    """19-10: a stroke of a run whose identity is undecided is analysed (strokes_doubtful.json): it counts
    as found-but-doubtful, never as hers and never as lost."""
    evs = [_ev(1.0), _ev(5.0)]
    runs = [{"t0": 0, "t1": 8, "near_is_target": None, "method": None}]
    out = R.Outputs(main_shots=[(0, 8)], runs=runs, doubtful=[{"t": 5.02, "side": "near", "stroke": "forehand"}])
    attr = R.attribute(evs, out)
    assert [a["step"] for a in attr] == ["identidad_sin_decidir", "encontrado_dudoso"]
    s = R.summarize(attr, evs, out.strokes, [(0, 8)], 0.2, runs, [])
    assert s["total"]["found"] == 0 and s["total"]["found_doubtful"] == 1 and s["total"]["recall_any"] == 0.5
    assert "encontrado_dudoso" not in R.LOST
