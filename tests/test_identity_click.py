"""«¿Cuál es ella?»: the identity click of the application (19-10)."""
import json

from tennisbio.app import identity_click as ic
from tennisbio.identity import PICK_FILE


def test_click_state_and_save(tmp_path):
    assert ic.state(tmp_path) == {"possible": False, "done": False, "pick": None}
    (tmp_path / "identity.json").write_text(json.dumps({"fps": 10, "runs": [{"start": 0, "end": 5, "cluster": 0},
                                                                           {"start": 5, "end": 9, "cluster": 1}]}))
    assert ic.state(tmp_path)["possible"] and not ic.state(tmp_path)["done"]
    (tmp_path / PICK_FILE).write_text(json.dumps({"t": 1.0, "near_is_her": True, "simulated": True}))
    assert not ic.state(tmp_path)["done"]                 # the benchmark's simulated click is not the user's
    p = ic.save_pick(tmp_path, 2.345)
    assert p["t"] == 2.345 and p["near_is_her"] is True and ic.state(tmp_path)["done"]
