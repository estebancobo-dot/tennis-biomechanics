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


def test_a_stage_can_be_profiled_without_changing_it(tmp_path, monkeypatch):
    """14-11: `perfil: [stage]` runs that stage under cProfile and writes its top functions beside the manifest;
    the stage's summary is the same."""
    from types import SimpleNamespace

    from tennisbio import pipeline
    lines = []
    c = SimpleNamespace(cfg={"perfil": ["x"]}, log=lines.append, match=SimpleNamespace(id="m"),
                        path=lambda name: tmp_path / name)
    monkeypatch.setitem(pipeline.STAGES, "x", SimpleNamespace(run=lambda ctx: {"n": sum(range(1000))}))
    assert pipeline._profiled("x", c) == {"n": 499500}
    txt = (tmp_path / "perfil_x.txt").read_text(encoding="utf-8")
    assert "tottime" in txt and "cumulative" in txt and lines


def test_angles_are_compared_on_the_circle():
    """R50 (15-11): 340° and 29° are 49° apart, and 359.8° and 0.1° are the same; a face that turns 180° is still a
    difference (the real R50)."""
    assert eq._diff(340.0, 29.0, "stance_angle") == 49.0
    assert eq._close(359.8, 0.1, "face.loaded.yaw_deg") and not eq._close(359.8, 0.1, "elbow_px")
    assert eq._diff(10.0, 190.0, "face.finish.yaw_deg") == 180.0
    a = [{"match_time_s": 1.0, "stroke": "forehand", "face": {"yaw_deg": 359.9}}]
    b = [{"match_time_s": 1.0, "stroke": "forehand", "face": {"yaw_deg": 0.2}}]
    assert eq.compare_strokes(a, b)["medidas_distintas"] == {}


def test_jumps_are_listed_with_their_ambiguity():
    """R50: an angle that changes > 90° between two runs is listed per stroke with its phase's «ambiguous» flag."""
    a = [{"match_time_s": 5.0, "stroke": "forehand", "face": {"loaded": {"yaw_deg": 10.0, "ambiguous": True}}}]
    b = [{"match_time_s": 5.0, "stroke": "forehand", "face": {"loaded": {"yaw_deg": 189.0, "ambiguous": False}}}]
    g = eq.compare_strokes(a, b)
    assert g["golpes_con_saltos"] == 1
    assert g["saltos"] == [{"t": 5.0, "medida": "face.loaded.yaw_deg", "a": 10.0, "b": 189.0,
                            "ambigua_a": True, "ambigua_b": False, "mano_a": None, "mano_b": None}]


def test_two_models_are_compared_by_their_shake():
    """T25 (15-11, RTMW-x against RTMPose-x): the frame-to-frame shake of the same measures of the same strokes, the
    racket face left out (its sign flips, R50, are not shake)."""
    def stroke(t, knee, hip, face):
        return {"match_time_s": t, "stroke": "forehand",
                "technique": {"jitter": {"loaded.knee_dom": knee, "impact.hip_turn": hip, "impact.face_tilt": face}}}
    a = [stroke(1.0, 4.0, 2.0, 1.0), stroke(2.0, 6.0, 0.0, 1.0)]
    b = [stroke(1.0, 2.0, 1.0, 90.0), stroke(2.0, 3.0, 5.0, 90.0)]
    sh = eq.compare_strokes(a, b)["temblor"]
    assert sh == {"n": 3, "cociente_mediano_b_a": 0.5, "b_tiembla_menos": 1.0, "b_tiembla_mas": 0.0}
    assert eq.compare_strokes(a, a)["temblor"]["cociente_mediano_b_a"] == 1.0
    assert eq.shake_summary([]) == {"n": 0}
    assert "temblor de b frente a a ×0.50" in eq.summary(eq.compare({}, {}, {"strokes.json": a}, {"strokes.json": b}))


def test_the_shake_is_also_given_by_family_of_measure():
    """21-11 (#307): Sapiens2 shook 36 % less on the body's points and ×1.00 over all the measures of the strokes: the
    shake by family (racket, feet, wrists, arms, trunk, legs) says where a pose model changes it."""
    assert [eq.shake_family(k) for k in ("impact.racket_tip_height", "loaded.wrist_dom_height", "ready.base_width",
                                         "loaded.front_foot_angle_deg", "impact.elbow_dom", "loaded.x_factor",
                                         "ready.head_over_base", "ready.knee_dom", "impact.hip_height",
                                         "stroke.tempo_ratio")] == \
        ["raqueta", "muñecas", "pies", "pies", "brazos", "tronco", "tronco", "piernas", "piernas", "otras"]

    def stroke(t, knee, racket):
        return {"match_time_s": t, "stroke": "forehand",
                "technique": {"jitter": {"loaded.knee_dom": knee, "impact.racket_tip_height": racket}}}
    a = [stroke(1.0, 4.0, 2.0), stroke(2.0, 6.0, 2.0)]
    b = [stroke(1.0, 2.0, 2.0), stroke(2.0, 3.0, 2.0)]
    g = eq.compare_strokes(a, b)
    assert g["temblor_por_familia"]["piernas"]["cociente_mediano_b_a"] == 0.5
    assert g["temblor_por_familia"]["raqueta"]["cociente_mediano_b_a"] == 1.0
    assert "temblor por familias: piernas ×0.50, raqueta ×1.00" in \
        eq.summary(eq.compare({}, {}, {"strokes.json": a}, {"strokes.json": b}))
