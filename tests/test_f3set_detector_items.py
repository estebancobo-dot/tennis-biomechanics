import json

from tennisbio.audit import F3SET_KIND_ITEM, F3SET_RECALL_ITEM, f3set_detector_items

# the PC's recount of 11-11 (recall_validation_detector.json, summary): types right for 327 of 336 forehands and
# backhands and 129 of 130 serves
CONF = {"backhand->backhand": 147, "backhand->forehand": 2, "forehand->backhand": 5, "forehand->forehand": 180,
        "forehand->overhead": 2, "serve->backhand": 1, "serve->overhead": 129, "volley_other->backhand": 1}


def _write(tmp_path, summary):
    (tmp_path / "recall_validation_detector.json").write_text(json.dumps({"summary_valid": summary}), encoding="utf-8")
    return {i["name"]: i for i in f3set_detector_items(tmp_path)}


def test_the_detector_and_the_kinds_against_f3set_pass_with_the_pc_numbers(tmp_path):
    by = _write(tmp_path, {"total": {"recall": 0.90, "found": 466, "gt": 517}, "kind_confusion": CONF})
    assert by[F3SET_RECALL_ITEM]["status"] == "ok" and "466 de 517" in by[F3SET_RECALL_ITEM]["detail"]
    assert by[F3SET_KIND_ITEM]["status"] == "ok" and "327 de 336" in by[F3SET_KIND_ITEM]["detail"]


def test_few_strokes_found_or_kinds_mixed_up_fail(tmp_path):
    mixed = {**CONF, "forehand->backhand": 40}
    by = _write(tmp_path, {"total": {"recall": 0.70, "found": 362, "gt": 517}, "kind_confusion": mixed})
    assert by[F3SET_RECALL_ITEM]["status"] == "falta"
    assert by[F3SET_KIND_ITEM]["status"] == "falta" and "forehand→backhand 40" in by[F3SET_KIND_ITEM]["detail"]
    by = _write(tmp_path, {"total": {"recall": 0.9}})
    assert by[F3SET_KIND_ITEM]["status"] == "aviso"                     # no confusion measured: not a pass


def test_without_a_recount_nothing_passes(tmp_path):
    assert {i["status"] for i in f3set_detector_items(tmp_path / "nada")} == {"aviso"}
