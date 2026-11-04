"""Request #83 (the tree of generated files, checked): every stage's output, window and series is looked for where
the stages write it. 04-11 on the PC: the 4 library matches (etapas/ + golpes/<jugadora>/) were all reported
without probe.json, scenes.json… because the check looked beside the folder."""
import json

from tennisbio import match_files as _mf
from tennisbio import stages  # noqa: F401  (registers the stages)
from tennisbio.audit import file_tree_items
from tennisbio.pipeline import STAGES


def _full_match(d, library: bool):
    if library:
        (d / "etapas").mkdir(parents=True)
        (d / "partido.json").write_text(json.dumps({"jugadora": "rybakina"}), encoding="utf-8")
    else:
        d.mkdir(parents=True)
    for st in STAGES.values():
        for o in st.outputs:
            f = _mf.at(d, o)
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("[]" if o.endswith(".json") else "x", encoding="utf-8")
    strokes = [{"stroke_id": "g1", "window": "g1.mp4", "series": "series/g1.json"}]
    _mf.at(d, "strokes.json").write_text(json.dumps(strokes), encoding="utf-8")
    for rel in ("windows/g1.mp4", "series/g1.json"):
        f = _mf.at(d, rel)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x", encoding="utf-8")


def _item(items, d):
    return next(i for i in items if i["name"] == f"Partido {d.name}: salida de cada etapa, ventanas y series")


def test_library_match_with_every_file_in_its_place_is_ok(tmp_path):
    d = tmp_path / "biblioteca" / "partidos" / "sin-fecha" / "sin-fecha_f43dd2_rybakina"
    _full_match(d, library=True)
    assert (d / "etapas" / "probe.json").exists() and (d / "golpes" / "rybakina" / "strokes.json").exists()
    it = _item(file_tree_items([d], None, tmp_path / "output"), d)
    assert it["status"] == "ok", it["detail"]


def test_flat_match_still_checked_beside_the_folder(tmp_path):
    d = tmp_path / "output" / "m1"
    _full_match(d, library=False)
    assert _item(file_tree_items([d], None, tmp_path / "output"), d)["status"] == "ok"


def test_a_missing_or_empty_file_is_still_reported(tmp_path):
    d = tmp_path / "biblioteca" / "partidos" / "sin-fecha" / "sin-fecha_x_rybakina"
    _full_match(d, library=True)
    (d / "etapas" / "scenes.json").unlink()
    _mf.at(d, "series/g1.json").write_text("", encoding="utf-8")            # empty counts as missing
    it = _item(file_tree_items([d], None, tmp_path / "output"), d)
    assert it["status"] == "falta" and "scenes/scenes.json" in it["detail"] and "serie de g1" in it["detail"]
    assert "probe/probe.json" not in it["detail"]
