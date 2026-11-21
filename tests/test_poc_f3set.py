"""F3Set on Kaggle (21-11, #295): today's whole analysis against the cloud's reference run, with the same script and
the rule written before measuring (not worse than what a different device can move)."""
import json
import sys
from pathlib import Path

from tennisbio.infra import poc_f3set as pf

ROOT = Path(__file__).resolve().parents[1]


def _rep(found, prec, dts=(0.02, 0.04)):
    return {"summary": {"total": {"found": found, "gt": 517, "recall": found / 517}, "precision": {"precision": prec},
                        "false": [1, 2]}, "strokes": [{"dt": d} for d in dts], "minutes": 260}


def test_the_rule_and_its_limits_are_the_clouds():
    sys.path.insert(0, str(ROOT / "cloud"))
    import nube
    assert pf.MAX_FOUND_DIFF == nube.MAX_FOUND_DIFF and pf.MAX_PRECISION_DIFF == nube.MAX_PRECISION_DIFF
    assert pf.totals(_rep(469, 0.94)) == nube._totals(_rep(469, 0.94))
    ref = _rep(469, 0.94)
    assert pf.decide(ref, _rep(468, 0.938))["resultado"] == "igual"
    assert pf.decide(ref, _rep(475, 0.945))["resultado"] == "mejor"
    bad = pf.decide(ref, _rep(466, 0.94))
    assert bad["pasa"] is False and bad["resultado"] == "peor" and "(-3)" in bad["motivo"]
    assert pf.decide(ref, _rep(469, 0.93))["pasa"] is False
    assert pf.decide({}, ref)["pasa"] is False


def test_kaggle_brings_her_clips_and_the_reference_and_streams_the_log():
    sys.path.insert(0, str(ROOT / "cloud" / "kaggle"))
    sys.path.insert(0, str(ROOT / "cloud"))
    import cola
    import correr
    j = correr.parse_job('{"accion": "medir", "prueba": "f3set"}')
    args = correr.poc_args(j, Path("/d/models/models"), None)
    assert args == ["--raiz", "/d/models/datasets", "--referencia", f"/d/models/referencia/{correr.F3SET_REFERENCE}",
                    "--tag", "kaggle_f3"]
    src = (ROOT / "cloud" / "kaggle" / "correr.py").read_text(encoding="utf-8")
    assert 'modal_get("/datasets/f3set/recall/videos"' in src and "f3set" in correr.STREAMED
    assert cola.estimate_h({"id": "x", "accion": "medir", "prueba": "f3set", "horas": 5}) == 5.0
    assert cola.estimate_h({"id": "x", "accion": "medir", "prueba": "f3set"}) == cola.KAGGLE_H["medir"]


def test_the_validation_writes_the_tagged_report_it_reads():
    src = (ROOT / "scripts" / "validate_recall.py").read_text(encoding="utf-8")
    assert 'name = "recall_validation_detector" if args.spotter else "recall_validation"' in src
    assert 'name += f"_{args.tag}"' in src
    json.dumps({})


def test_the_strokes_lost_and_won_are_said_with_the_step_where_they_stayed():
    ref = {"strokes": [{"match": "m", "point": 1, "label": "fh", "t_clip": 1.0, "side": "far", "step": "encontrado"},
                       {"match": "m", "point": 2, "label": "fh", "t_clip": 2.0, "side": "near", "step": "encontrado"},
                       {"match": "m", "point": 3, "label": "bh", "t_clip": 3.0, "side": "near", "step": "no_candidato"}]}
    new = {"strokes": [{"match": "m", "point": 1, "label": "fh", "t_clip": 1.0, "side": "far", "step": "lejana_no_encontrada"},
                       {"match": "m", "point": 2, "label": "fh", "t_clip": 2.0, "side": "near", "step": "encontrado"},
                       {"match": "m", "point": 3, "label": "bh", "t_clip": 3.0, "side": "near", "step": "encontrado"}]}
    d = pf.stroke_diff(ref, new)
    assert d["perdidos"] == 1 and d["ganados"] == 1 and d["perdidos_por_paso"] == {"lejana_no_encontrada": 1}
    assert d["perdidos_detalle"][0]["lado"] == "far" and d["perdidos_detalle"][0]["paso_hoy"] == "lejana_no_encontrada"
    from tennisbio.validation.recall_eval import FOUND
    assert pf.FOUND == FOUND
    src = (ROOT / "cloud" / "kaggle" / "correr.py").read_text(encoding="utf-8")
    assert 'run.glob("recall_validation_detector*.json")' in src
