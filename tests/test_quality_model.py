"""The quality model, the «cube» (11-11, request #256)."""
import json

from tennisbio import quality_model as Q


def test_every_audit_area_has_its_cell_and_unmeasured_cells_are_gaps(tmp_path):
    from tennisbio import audit
    import inspect, re
    src = inspect.getsource(audit)
    areas = set(re.findall(r'_item\(\s*\d+\s*,\s*"([^"]+)"', src))
    m = Q.load_model()
    missing = sorted(a for a in areas if a not in (m.get("areas") or {}))
    assert not missing, missing                                   # every area the audit writes is in a cell
    items = [{"area": "Golpes", "name": "a", "status": "ok"}, {"area": "Golpes", "name": "b", "status": "aviso"},
             {"area": "Taxonomía", "name": "c", "status": "pocos datos"}, {"area": "Peticiones", "name": "d", "status": "falta"}]
    r = Q.score(items, m)
    g = r["cells"][("golpes", "funcional", "pc")]
    assert g["ok"] == 1 and g["n"] == 2 and g["score"] == 0.5 and not g["accepted"] and g["fallan"] == ["b"]
    assert r["cells"][("taxonomia", "funcional", "pc")]["score"] is None                 # only «pocos datos»
    assert r["cells"][("pantallas", "portabilidad", "pantallas")].get("unmeasured")      # expected, nothing measures it
    assert r["total"]["n"] == 2                                                         # «Peticiones» is an aggregate
    f = tmp_path / "a.json"
    f.write_text(json.dumps({"items": items}), encoding="utf-8")
    Q.run(f, tmp_path / "out")
    md = (tmp_path / "out" / "calidad.md").read_text(encoding="utf-8")
    assert "SIN MEDIR" in md and "Por característica" in md
