"""R22 (13-11): the diagnosis of play_mask's filled court gaps describes the case suspected in F3Set (the court found in
the first frames of a shot, while it still dissolves from the previous one, then lost for seconds)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import diag_play_mask as D  # noqa: E402


def _folder(tmp_path: Path) -> Path:
    d = tmp_path / "recall_x_azaren"
    d.mkdir()
    sc = {"fps": 10.0, "shots": [{"start": 0, "end": 100, "main_camera": True},
                                  {"start": 100, "end": 200, "main_camera": True}]}
    # shot 2: the court in its first 3 frames (the dissolve), lost for 5 s, found again
    court = {"shots": [{"start": 0, "end": 100, "H": [[1]]}, {"start": 100, "end": 103, "H": [[1]]},
                       {"start": 103, "end": 153, "H": None}, {"start": 153, "end": 200, "H": [[1]]}]}
    ident = {"fps": 10.0, "runs": [{"start": 100, "end": 200, "near_is_target": False, "method": "ropa",
                                    "clothes_margin": 0.28}]}
    for name, obj in (("scenes.json", sc), ("court.json", court), ("identity.json", ident)):
        (d / name).write_text(json.dumps(obj), encoding="utf-8")
    return d


def test_the_dissolve_case_is_described(tmp_path):
    r = D.report(_folder(tmp_path), [("azaren", 9.5, 16.0)])
    (g,) = r["filled_gaps"]
    assert g["t0"] == 10.3 and g["len_s"] == 5.0 and g["court_frames_before"] == 3
    assert g["first_court_frame_from_shot_start"] == 0 and g["from_shot_start_s"] == 0.3
    assert r["summary"]["with_at_most_3_court_frames_before"] == 1
    w = r["windows"][0]
    assert w["court"].startswith("11111|111") and w["identity_runs"][0]["near_is_target"] is False


def test_a_folder_without_scenes_says_so(tmp_path):
    assert "error" in D.report(tmp_path, [])
