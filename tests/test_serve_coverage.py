"""B4 (08-11): the serve report says how much of her serves it covers, with the numbers of serve_gaps, and the audit
checks it (item «Cobertura del saque dicha en el informe»)."""
import json

from tennisbio.audit import audit, recall_items, serve_coverage, serve_coverage_item, serve_coverage_text
from tennisbio.catalog import Match, Player
from tennisbio.point_count import NO_SCOREBOARD, serve_coverage_sentence
from tennisbio.report import build


def _r(t, pts, server=0, games=((2, 1),)):
    return {"t": t, "games": [list(g) for g in games], "points": list(pts), "server": server}


def _match(d, with_score=True):
    """Four points on her serve: one serve found, one with a forehand only, one off the main camera and one with
    nobody playing on the main camera (no candidate, nothing spotted: the TV did not show it)."""
    d.mkdir()
    readings = [_r(0, (0, 0)), _r(40, (15, 0)), _r(80, (30, 0)), _r(120, (40, 0)), _r(160, (40, 15))]
    if with_score:
        (d / "score.json").write_text(json.dumps({"readings": readings}))
    strokes = [{"stroke": "overhead", "match_time_s": 20, "side": "near"},
               {"stroke": "forehand", "match_time_s": 70, "side": "near"}]
    (d / "strokes.json").write_text(json.dumps(strokes))
    (d / "scenes.json").write_text(json.dumps({"fps": 1.0, "shots": [{"start": 0, "end": 74, "main_camera": True},
                                                                     {"start": 130, "end": 170, "main_camera": True}]}))
    (d / "spotting.json").write_text(json.dumps([]))
    (d / "candidates.json").write_text(json.dumps({"candidates": []}))
    return d


def test_sentence():
    assert serve_coverage_sentence(3, 4) == "Saques analizados: 3 de los ~4 puntos de su saque que enseña la tele (75 %)"
    assert serve_coverage_sentence(0, 0) == "Saques analizados: 0 de los ~0 puntos de su saque que enseña la tele"


def test_same_numbers_as_the_recall_item(tmp_path):
    d = _match(tmp_path / "m1")
    c = serve_coverage(d)
    g = next(i for i in recall_items([d]) if i["name"].startswith("Saques por punto"))["serve_gaps"]
    assert c == {"found": g["found"], "points": g["points"], "unseen": g["unseen"], "shown": g["points"] - g["unseen"]}
    assert c["points"] == 4 and c["unseen"] == 1 and c["shown"] == 3 and c["found"] == 1


def test_text_per_match_total_and_no_scoreboard(tmp_path):
    a, b = _match(tmp_path / "a"), _match(tmp_path / "b", with_score=False)
    t = serve_coverage_text([("a", a), ("b", b)])
    assert t["matches"][0]["text"] == serve_coverage_sentence(1, 3)
    assert t["matches"][1]["text"] == NO_SCOREBOARD
    assert t["total"] == serve_coverage_sentence(1, 3) + " (solo los partidos con marcador)"
    assert serve_coverage_text([("b", b)])["total"] == NO_SCOREBOARD


def test_serve_report_says_it_and_the_audit_checks_it(tmp_path):
    d = _match(tmp_path / "m1")
    out = build([Match("m1", None, Player("p", "P"))], tmp_path, tmp_path / "informe_saque", stroke="overhead")
    html = out.read_text(encoding="utf-8")
    assert serve_coverage_sentence(1, 3) in html and "Cuántos de sus saques cubre" in html
    it = serve_coverage_item([d], out)
    assert it["name"] == "Cobertura del saque dicha en el informe" and it["status"] == "ok", it
    # the forehand audit finds the serve report next to its own report
    names = {i["name"]: i["status"] for i in audit([d], tmp_path / "informe_derecha")["items"]}
    assert names["Cobertura del saque dicha en el informe"] == "ok"


def test_forehand_report_does_not_carry_it(tmp_path):
    _match(tmp_path / "m1")
    out = build([Match("m1", None, Player("p", "P"))], tmp_path, tmp_path / "informe_derecha")
    assert "Saques analizados:" not in out.read_text(encoding="utf-8")


def test_audit_warns_when_numbers_differ_or_report_missing(tmp_path):
    d = _match(tmp_path / "m1")
    html = tmp_path / "index.html"
    html.write_text("Saques analizados: 2 de los ~3 puntos de su saque que enseña la tele (67 %)", encoding="utf-8")
    it = serve_coverage_item([d], html)
    assert it["status"] == "aviso" and "m1" in it["detail"]
    assert serve_coverage_item([d], tmp_path / "no" / "index.html")["status"] == "aviso"
    html.write_text(f"m1: {NO_SCOREBOARD}", encoding="utf-8")
    e = tmp_path / "e"
    e.mkdir()
    assert serve_coverage_item([e], html)["status"] == "ok"
