"""R30 (13-11): the diagnosis of other matches inside a broadcast finds her strokes and identity runs in main-camera
shots where the scoreboard was never read with the two players' names."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import diag_otros_partidos as D  # noqa: E402


def test_strokes_and_runs_in_shots_without_her_scoreboard_are_listed(tmp_path):
    score = {"names": ["Rybakina", "Zheng"],
             "shots": [{"start": 0, "end": 100, "tried": 20, "read": 18},
                       {"start": 4600, "end": 4700, "tried": 12, "read": 0},       # Shelton – Alcaraz
                       {"start": 4700, "end": 4710, "tried": 1, "read": 0}]}       # too few tries to say
    strokes = [{"t": 50.0, "side": "near"}, {"t": 4628.3, "side": "near", "stroke": "forehand"}, {"t": 4705, "side": "far"}]
    ident = {"fps": 10.0, "runs": [{"start": 46200, "end": 46400, "near_is_target": True, "method": "ropa + clic",
                                    "clothes_margin": 0.08}, {"start": 0, "end": 900, "near_is_target": True}]}
    for name, obj in (("score.json", score), ("strokes.json", strokes), ("identity.json", ident)):
        (tmp_path / name).write_text(json.dumps(obj), encoding="utf-8")
    r = D.report(tmp_path, [4628])
    assert r["unread_shots"] == 1 and r["unread_min"] == 1.7
    assert r["strokes_in_unread"] == [{"t": 4628.3, "side": "near", "stroke": "forehand"}]
    assert r["runs_in_unread"] == [{"t0": 4620.0, "t1": 4640.0, "near_is_target": True, "method": "ropa + clic",
                                    "clothes_margin": 0.08}]
    assert r["probes"][0]["shot"]["read"] == 0 and len(r["probes"][0]["strokes_within_15s"]) == 1


def test_without_score_json_it_says_so(tmp_path):
    assert "error" in D.report(tmp_path, [])


def test_a_person_unlike_both_players_is_the_farthest_run():
    import numpy as np

    from tennisbio.clothes import CLOTHES_DIM, REGION_DIM
    rng = np.random.default_rng(0)

    def code(colour):
        c = np.full(CLOTHES_DIM, 0.01, np.float32)
        for r in range(2):
            c[r * REGION_DIM + colour] = 1.0
            c[r * REGION_DIM:(r + 1) * REGION_DIM] /= c[r * REGION_DIM:(r + 1) * REGION_DIM].sum()
        return c
    runs = []
    for k in range(10):                                           # her (colour 0) and the opponent (colour 1)
        g = k % 2
        c = code(g) + rng.uniform(0, 0.002, CLOTHES_DIM).astype(np.float32)
        runs.append({"start": k * 100, "end": k * 100 + 50, "cluster": g, "clothes_margin": 0.6,
                     "clothes_code": [float(v) for v in c], "near_is_target": g == 0})
    runs.append({"start": 46200, "end": 46400, "cluster": 0, "clothes_margin": 0.08,          # another match
                 "clothes_code": [float(v) for v in code(5)], "near_is_target": True})
    r = D.clothes_outliers({"fps": 10.0, "runs": runs})
    assert r["farthest"][0]["t0"] == 4620.0 and r["farthest"][0]["d_min"] > 3 * r["own_distance_clear_runs"]["p99"]
