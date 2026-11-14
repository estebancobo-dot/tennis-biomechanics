"""T9 (#288, #289): two runs of the same clip compared (tennisbio.infra.equivalence) and the declared equivalence of a
code change that keeps a stage's fingerprint (tennisbio.pipeline.equivalent_code)."""
import json

from tennisbio.infra import equivalence as eq
from tennisbio.pipeline import equivalent_code


def _s(t, kind="forehand", elbow=120.0, **kw):
    return {"match_time_s": t, "stroke": kind, "metrics": {"elbow_deg": elbow, "stance": "open"}, "series": "x.json", **kw}


def test_identical_equivalent_and_different():
    man = {"fine": {"out_hash": "h1"}, "court": {"out_hash": "h2"}}
    a = {"strokes.json": [_s(10.0), _s(14.0, "backhand")]}
    assert eq.compare(man, dict(man), a, a)["veredicto"] == "idéntica"
    other = {"fine": {"out_hash": "h9"}, "court": {"out_hash": "h2"}}
    b = {"strokes.json": [_s(10.02, elbow=120.3, series="y.json"), _s(14.0, "backhand")]}     # GPU rounding
    c = eq.compare(man, other, a, b)
    assert c["veredicto"] == "equivalente" and c["etapas_distintas"] == ["fine"] and c["etapas_iguales"] == ["court"]
    d = eq.compare(man, other, a, {"strokes.json": [_s(10.0, elbow=131.0), _s(15.0, "backhand")]})
    g = d["golpes"]["strokes.json"]
    assert d["veredicto"] == "distinta" and g["solo_a"] == [14.0] and g["solo_b"] == [15.0]
    assert g["medidas_distintas"] == {"metrics.elbow_deg": 1} and g["mayor_diferencia"]["metrics.elbow_deg"] == 11.0
    k = eq.compare(man, other, a, {"strokes.json": [_s(10.0, "backhand"), _s(14.0, "backhand")]})
    assert k["veredicto"] == "distinta" and k["golpes"]["strokes.json"]["tipo_distinto"] == [10.0]
    assert "distinta" in eq.summary(d) and "1 de 2/2" in eq.summary(d)
    assert eq.compare({}, {}, {}, {})["veredicto"] == "distinta"                 # nothing to compare is not «same»
    assert eq.compare_strokes({"strokes": [_s(1.0)]}, [_s(1.0)])["pares"] == 1    # a {"strokes": [...]} file


def test_compare_dirs(tmp_path):
    for d in ("a", "b"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "manifest.json").write_text(json.dumps({"fine": {"out_hash": "h"}}), encoding="utf-8")
        (tmp_path / d / "strokes.json").write_text(json.dumps([_s(3.0)]), encoding="utf-8")
    assert eq.compare_dirs(tmp_path / "a", tmp_path / "b")["veredicto"] == "idéntica"


def test_declared_equivalence_only_once_checked(tmp_path):
    f = tmp_path / "eq.json"
    f.write_text(json.dumps({"fine": {"new": {"igual_a": "old", "comprobado": False}}}), encoding="utf-8")
    assert equivalent_code("fine", "new", f) == "new"                        # not checked yet: new code is new
    g = tmp_path / "eq2.json"
    g.write_text(json.dumps({"_nota": "x", "fine": {"newer": {"igual_a": "new", "comprobado": True},
                                                    "new": {"igual_a": "old", "comprobado": True},
                                                    "loop": {"igual_a": "loop", "comprobado": True}}}), encoding="utf-8")
    assert equivalent_code("fine", "newer", g) == "old"                      # chains are followed
    assert equivalent_code("fine", "loop", g) == "loop" and equivalent_code("fine_opponent", "newer", g) == "newer"
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    assert equivalent_code("fine", "x", bad) == "x"


def test_the_repository_file_is_valid():
    from pathlib import Path
    reg = json.loads((Path(__file__).resolve().parents[1] / "config" / "codigo_equivalente.json").read_text(encoding="utf-8"))
    for stage, entries in reg.items():
        if stage.startswith("_"):
            continue
        for new, e in entries.items():
            assert e["igual_a"] != new and isinstance(e["comprobado"], bool) and e.get("prueba") and e.get("motivo")


def test_a_file_read_on_one_side_is_never_same():
    """14-11, the first comparison in the cloud: identical stage hashes but the new run's strokes.json unread said
    «idéntica»; now it is «incompleta» and names the file. Strokes are matched by their match time."""
    man = {"fine": {"out_hash": "h"}}
    c = eq.compare(man, dict(man), {"strokes.json": [_s(10.0)]}, {})
    assert c["veredicto"] == "incompleta" and c["ficheros_de_un_solo_lado"] == ["strokes.json"]
    assert "un solo lado: strokes.json" in eq.summary(c)
    assert eq.stroke_time({"match_time_s": 3.5, "t": 1.0}) == 3.5 and eq.stroke_time({"t": 1.0}) == 1.0
    g = eq.compare_strokes([_s(10.0), _s(20.0)], [_s(20.01), _s(10.0)])
    assert g["pares"] == 2 and not g["solo_a"]
