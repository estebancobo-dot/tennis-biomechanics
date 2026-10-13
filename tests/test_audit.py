import json

from tennisbio.audit import _matches, audit, parse_matrix, to_markdown


def test_matrix_rows_and_names():
    rows = parse_matrix()
    assert len(rows) > 60 and {r["status"] for r in rows} <= {"✔", "◐", "○", "✘"}
    assert any("hip_height" in r["ids"] for r in rows)
    assert _matches("hip_height", "ready.hip_height") and _matches("knee_*", "loaded.knee_dom")
    assert not _matches("hip", "ready.hip_height")


def test_audit_of_a_tiny_run(tmp_path):
    d = tmp_path / "m1"
    d.mkdir()
    s = {"stroke": "forehand", "side": "near", "phases": {"impact": {"frame": 50}, "ready": {"frame": None}},
         "metrics": {"contact_height_pct": 300.0},       # impossible: must be caught
         "technique": {"classes": {"ball_speed": "lenta"}, "phases": {"impact": {"hip_height": 50.0}}, "stroke": {}},
         "face": {"loaded": {"tilt_deg": 10}}}
    (d / "strokes.json").write_text(json.dumps([s]), encoding="utf-8")
    (d / "manifest.json").write_text(json.dumps({"probe": {"seconds": 60, "summary": {"duration_min": 4}}}), encoding="utf-8")
    res = audit([d], None)
    by = {i["name"]: i for i in res["items"]}
    assert by["Valores dentro de límites físicos"]["status"] == "falta"
    assert by["Dirección del golpe"]["status"] == "pocos datos"       # a situation now; one stroke is not enough
    assert by["Fotograma clave: espera / split step"]["status"] == "falta"
    assert by["Bola rápida / lenta"]["status"] == "pocos datos"
    assert "Auditoría" in to_markdown(res)


def test_matrix_ids_are_measures_not_broken_code_refs():
    """A matrix id written as module.name is read as a code reference: it must exist, or the measure is
    never matched (it happened with footwork.crossover_steps)."""
    from tennisbio.audit import _code_ref, parse_matrix
    bad = [(r["element"], i) for r in parse_matrix() for i in r["ids"] if _code_ref(i) is False]
    assert not bad, bad
