"""13-11: the diagnosis of the runs where the clothes (with the user's click) and the end changes disagree."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("diag_identity", Path(__file__).resolve().parents[1] / "scripts" / "diag_identity.py")
D = importlib.util.module_from_spec(spec)
spec.loader.exec_module(D)


def test_conflicts_are_the_runs_where_clothes_and_end_changes_disagree():
    runs = [{"start": 0, "end": 10, "cluster": 0, "clothes_margin": 0.5, "end_changes": 0},     # hers, parity 0
            {"start": 10, "end": 20, "cluster": 1, "clothes_margin": 0.5, "end_changes": 1},    # the other, parity 1
            {"start": 20, "end": 30, "cluster": 0, "clothes_margin": 0.5, "end_changes": 2},    # hers, parity 0
            {"start": 30, "end": 40, "cluster": 1, "clothes_margin": 0.4, "end_changes": 2},    # clothes: other; ends: hers
            {"start": 40, "end": 50, "cluster": 0, "clothes_margin": 0.5, "end_changes": None}]  # no end changes
    idx, cf = D.conflicts({"fps": 1.0, "runs": runs, "click_by": "clothes"}, {"t": 5.0, "near_is_her": True})
    assert idx == [3] and cf["her_parity"] == 0 and cf["en_desacuerdo"] == 1 and cf["con_cambios"] == 4
    row = cf["runs"][0]
    assert row["decision_ella_cerca"] is False and row["cambios_dicen_ella_cerca"] is True and row["t"] == 30
