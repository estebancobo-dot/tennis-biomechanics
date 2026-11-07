"""Request #30 (07-11): docs/comparativa_apps.md is checked against the measured state (audit.comparison_doc_item):
the models it names, its stroke-detection figures against the latest F3Set recall and its date."""
import json

import tennisbio.audit as A
from tennisbio import real_status

CURRENT = """# TennisBio frente a aplicaciones reales

Estado: 07-11-2026. Fuentes al final.

| Aspecto | SwingVision | **TennisBio** |
|---|---|---|
| Detección automática de golpes | ✔ | ✔ (P 0,95 / R 0,89 con el detector de golpes entrenado con F3Set; 13-10: P 0,73 / R 0,84) |

Modelos: TrackNetV3 para la bola, MotionAGFormer para el giro 3D, modelo propio de bote; CatBoost solo medido.
"""
STALE = """# TennisBio frente a aplicaciones reales

Estado: octubre 2026. Fuentes al final.

| Detección automática de golpes | ✔ | ✔ (P 0,73 / R 0,84 sin audio, lado cercano) |

Modelos: TrackNetV3 para la bola, RF-DETR para la lejana.
"""

ITEMS = [{"req": 12, "area": "Modelos", "name": "Modelo en uso: bola (TrackNetV3 de RacketVision)", "status": "ok", "detail": ""},
         {"req": 12, "area": "Modelos", "name": "Modelo en uso: detector de golpes aprendido (F3Set)", "status": "ok", "detail": ""},
         {"req": 12, "area": "Modelos", "name": "Modelo en uso: giro 3D del tronco (MotionAGFormer)", "status": "aviso",
          "detail": "elegido pero sin su fichero"}]


def _outputs(tmp_path, generated="2026-11-07 15:46", rfdetr=False):
    out = tmp_path / "output"
    out.mkdir()
    res = {"mag3d": {"verdict": {"adopt": True, "reason": "mejor"}},
           "bounce": {"verdict": {"adopt": True, "reason": "mejor"}},
           "bounce_own": {"verdict": {"adopt": True, "reason": "F1 0.884 frente a 0.594"}}}
    if rfdetr:
        res["rfdetr"] = {"verdict": {"adopt": False, "reason": "más lento"}}
    (out / "bench_candidates.json").write_text(json.dumps({"generated": generated, "results": res}), encoding="utf-8")
    rd = tmp_path / "datasets" / "reports"            # where validate_recall.py writes it, next to the output
    rd.mkdir(parents=True)
    rec = {"summary": {"total": {"gt": 648, "found": 461, "recall": 0.711}, "precision": {"precision": 0.88}},
           "summary_valid": {"total": {"gt": 517, "found": 460, "recall": 0.89}, "precision": {"precision": 0.947}}}
    (rd / "recall_validation_detector.json").write_text(json.dumps(rec), encoding="utf-8")
    return out


def _doc(tmp_path, text):
    f = tmp_path / "comparativa_apps.md"
    f.write_text(text, encoding="utf-8")
    return f


def _sub(tmp_path, name):
    d = tmp_path / name
    d.mkdir()
    return d


def test_current_document_is_ok(tmp_path):
    it = A.comparison_doc_item(ITEMS, _outputs(tmp_path), _doc(tmp_path, CURRENT))
    assert it["name"] == A.COMPARISON_ITEM and it["status"] == "ok", it["detail"]
    # MotionAGFormer's item warns, but its measure in bench_candidates.json backs it
    assert "5 modelos" in it["detail"] and "P 0.95 / R 0.89" in it["detail"] and "460 de 517" in it["detail"]


def test_stale_document_says_what_is_stale(tmp_path):
    it = A.comparison_doc_item(ITEMS, _outputs(tmp_path), _doc(tmp_path, STALE))
    assert it["status"] == "aviso"
    d = it["detail"]
    assert "RF-DETR" in d                                   # named, neither in use nor measured
    assert "cifras de detección desfasadas: P 0.73 / R 0.84" in d
    assert "01-10-2026, 37 días anterior" in d              # «octubre 2026» against the measure of 07-11
    # never the words that keep a request at level 1
    assert "sin comprobación automática" not in d and "no se comprueba en las salidas" not in d


def test_each_part_alone_makes_it_stale(tmp_path):
    # only the date: a model measure 20 days after the document
    t = _sub(tmp_path, "a")
    it = A.comparison_doc_item(ITEMS, _outputs(t, generated="2026-11-27 10:00"), _doc(t, CURRENT))
    assert it["status"] == "aviso" and "20 días anterior" in it["detail"]
    # only a model: measured → fine; the same document without its measure → stale
    rf = CURRENT.replace("CatBoost solo medido", "RF-DETR solo medido")
    t = _sub(tmp_path, "b")
    assert A.comparison_doc_item(ITEMS, _outputs(t, rfdetr=True), _doc(t, rf))["status"] == "ok"
    t = _sub(tmp_path, "c")
    it = A.comparison_doc_item(ITEMS, _outputs(t), _doc(t, rf))
    assert it["status"] == "aviso" and "RF-DETR" in it["detail"]
    # only the figures: within the tolerance it holds, beyond it does not
    t = _sub(tmp_path, "d")
    out = _outputs(t)
    assert A.comparison_doc_item(ITEMS, out, _doc(t, CURRENT.replace("R 0,89", "R 0,87")))["status"] == "ok"
    assert A.comparison_doc_item(ITEMS, out, _doc(t, CURRENT.replace("R 0,89", "R 0,80")))["status"] == "aviso"


def test_without_measures_it_warns(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    it = A.comparison_doc_item([], out, _doc(tmp_path, CURRENT))
    assert it["status"] == "aviso" and "sin recuento de F3Set" in it["detail"]
    assert "detector de golpes aprendido" in it["detail"]       # named, its item missing: said in words, not a regex


def test_base_items_include_it(tmp_path):
    items = A.base_items([], tmp_path, cfg={})
    assert any(i["name"] == A.COMPARISON_ITEM for i in items)


def test_request_30_reads_the_item_and_its_level():
    assert not isinstance(A.PETITIONS[30], A.Note)
    ok = {"req": 12, "area": "Modelos", "name": A.COMPARISON_ITEM, "status": "ok", "detail": "al día"}
    pet = {int(i["name"].split(" ")[0][1:]): i for i in A.petition_items([ok])}
    state = {rid: st for rid, _, st in real_status.registry()}[30]
    assert real_status.level(state, pet[30], 30) == 3
    bad = {**ok, "status": "aviso", "detail": "DESFASADO: fecha"}
    pet = {int(i["name"].split(" ")[0][1:]): i for i in A.petition_items([bad])}
    assert real_status.level(state, pet[30], 30) == 2


def test_the_repository_document_parses():
    text = A.COMPARISON_DOC.read_text(encoding="utf-8")
    assert A._doc_date(text) is not None
    row = next(ln for ln in text.splitlines() if "Detección automática de golpes" in ln)
    assert "P 0,95 / R 0,89" in row
