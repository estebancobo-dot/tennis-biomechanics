"""scripts/diag_saques.py (12-11): the points of her serve without her serve, as the audit counts them, each described
with what every stage saw in it."""
import importlib.util
import json
import sys
from pathlib import Path

from tennisbio.audit import serve_coverage
from test_serve_coverage import _match  # tests/ is on the path (rootdir conftest)

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "diag_saques.py"


def _mod():
    spec = importlib.util.spec_from_file_location("diag_saques", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_same_points_as_the_audit_and_each_gap_described(tmp_path, monkeypatch):
    m = _mod()
    d = _match(tmp_path / "partido_osaka")
    (d / "spotting.json").write_text(json.dumps([{"t": 60.0, "side": "far", "kind": "serve", "score": 0.9}]))
    out = tmp_path / "out"
    monkeypatch.setattr(m, "load_config", lambda: {"paths": {"output": str(out)}})
    monkeypatch.setattr(m, "match_dir", lambda cfg, needle: d if needle == "osaka" else None)
    monkeypatch.setattr(sys, "argv", ["diag_saques.py", "--match", "osaka"])
    m.main()
    rep = json.loads((out / "capturas_diag" / "diag_saques.json").read_text(encoding="utf-8"))
    c = serve_coverage(d)
    assert rep["puntos_de_su_saque"] == c["points"] and rep["con_saque"] == c["found"] and rep["no_vistos"] == c["unseen"]
    gaps = rep["huecos"]
    # as the audit: the point off the main camera stays, the one nobody plays on the main camera is left out
    assert [g["cause"] for g in gaps] == ["sin_saque", "sin_camara"]
    g = gaps[0]
    assert g["golpes_suyos"][0]["golpe"] == "forehand"
    assert g["detector"] == [{"t": 60.0, "side": "far", "kind": "serve", "score": 0.9}]   # the opponent's side spotted
    assert g["marcador"] and all({"t", "pts", "saca"} <= set(s) for s in g["marcador"])
    assert g["hoja"] is None                                       # no video: no sheet, and no failure
    assert [s["t"] for s in rep["sus_saques"]] == [20.0] and rep["sus_saques"][0]["antes"]["saca"] == 0


def test_no_match_is_said(tmp_path, monkeypatch):
    m = _mod()
    out = tmp_path / "out"
    monkeypatch.setattr(m, "load_config", lambda: {"paths": {"output": str(out)}})
    monkeypatch.setattr(m, "match_dir", lambda cfg, needle: None)
    monkeypatch.setattr(sys, "argv", ["diag_saques.py", "--match", "nada"])
    m.main()
    assert "error" in json.loads((out / "capturas_diag" / "diag_saques.json").read_text(encoding="utf-8"))
