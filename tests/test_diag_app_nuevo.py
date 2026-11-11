import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "diag_app_nuevo", Path(__file__).resolve().parents[1] / "scripts" / "diag_app_nuevo.py")
dg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dg)


def test_lists_only_the_checks_that_are_not_ok(tmp_path):
    f = tmp_path / "auditoria.json"
    f.write_text(json.dumps({"items": [{"status": "ok", "name": "a"}, {"status": "falta", "area": "X", "name": "b",
                                                                      "detail": "d"}]}), encoding="utf-8")
    assert dg.failing(f) == [{"estado": "falta", "area": "X", "nombre": "b", "detalle": "d"}]
    assert dg.failing(tmp_path / "no.json") == []
