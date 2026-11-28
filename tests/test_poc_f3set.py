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
    assert args == ["--raiz", str(Path("/d/models/datasets")), "--referencia",
                    str(Path("/d/models/referencia") / correr.F3SET_REFERENCE), "--tag", "kaggle_f3"]
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



def test_a_stroke_without_a_fine_window_is_not_called_far_player_not_found():
    """22-11: two far strokes of Dubai 2020 had their candidate but no window of the fine pass (it went to the doubtful
    pass); the evaluation said «far player not found», which pointed at RF-DETR when it was not that."""
    src = (ROOT / "src" / "tennisbio" / "validation" / "recall_eval.py").read_text(encoding="utf-8")
    block = src[src.index("elif w is None:"):src.index("elif not w[\"passed\"]:")]
    assert 'step = "sin_ventana"' in block and "lejana_no_encontrada" not in block.split("step =", 1)[1]


def test_one_compilation_is_compared_stroke_by_stroke_with_the_same_part_of_the_reference(tmp_path, monkeypatch):
    """28-11 (B4): the far-side loss is looked at in the Dubai 2020 compilation alone: the run is limited to it
    (validate_recall --matches), its strokes against the same compilation of the reference (not the whole report's
    total, which would count every other compilation as lost)."""
    st = lambda m, step: {"match": m, "point": "p", "label": f"{m}-{step}", "t_clip": 1.0, "step": step, "side": "far"}  # noqa: E731
    ref = {"strokes": [st("20200218-W-Dubai-R32-X", "encontrado"), st("2023-AO-SF", "encontrado")]}
    part = pf.subset(ref, "dubai")
    assert part["anotados"] == 1 and part["encontrados"] == 1 and part["strokes"][0]["match"].startswith("20200218")
    calls = []

    class R:
        returncode = 0
    monkeypatch.setattr(pf.subprocess, "run", lambda cmd, **k: calls.append(cmd) or R())
    rep = tmp_path / "datos" / "reports"
    rep.mkdir(parents=True)
    new = {"strokes": [{**st("20200218-W-Dubai-R32-X", "encontrado"), "label": "20200218-W-Dubai-R32-X-encontrado"}]}
    (rep / "recall_validation_detector_t.json").write_text(json.dumps(new), encoding="utf-8")
    (tmp_path / "ref.json").write_text(json.dumps(ref), encoding="utf-8")
    out = tmp_path / "poc.json"
    assert pf.main(["--raiz", str(tmp_path / "datos"), "--referencia", str(tmp_path / "ref.json"), "--tag", "t",
                    "--partidos", "Dubai", "--salida", str(out)]) == 0
    assert calls[0][-2:] == ["--matches", "Dubai"]
    res = json.loads(out.read_text(encoding="utf-8"))
    assert res["regla"]["pasa"] is None and "1 de 1 frente a 1 de 1" in res["regla"]["motivo"]
    assert res["diferencias"]["perdidos"] == 0                       # the AO compilation is not counted as lost
