import importlib.util
import json
import zipfile
from pathlib import Path

_f = Path(__file__).resolve().parents[1] / "scripts" / "pack_reference.py"
_spec = importlib.util.spec_from_file_location("pack_reference", _f)
pr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pr)


def test_only_her_near_forehands_and_their_series(tmp_path):
    d = tmp_path / "m"
    (d / "series").mkdir(parents=True)
    rows = [{"stroke": "forehand", "side": "near", "series": "series/a.json"},
            {"stroke": "forehand", "side": "far", "series": "series/b.json"},
            {"stroke": "backhand", "side": "near", "series": "series/c.json"},
            {"stroke": "forehand", "series": "series/missing.json"}]
    (d / "strokes.json").write_text(json.dumps(rows))
    for n in "abc":
        (d / "series" / f"{n}.json").write_text("{}")
    st = pr.pack([("m1", d)], tmp_path / "r.zip")
    assert st["golpes"] == 2 and st["series"] == 1
    names = zipfile.ZipFile(tmp_path / "r.zip").namelist()
    assert sorted(names) == ["m1/series/a.json", "m1/strokes.json"]
