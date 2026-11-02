"""B-15a: how much of each measure the camera explains (docs/analisis_referencias.md §2)."""
import numpy as np

from tennisbio.camera_share import camera_of, shares


def H_for(zoom=100.0, tilt=0.0):
    # player's court metres -> image px: x across, y away; a simple projective camera
    return [[zoom, 0, 960], [0, -zoom * 0.3 - tilt, 900], [0, 0.03, 1]]


def test_camera_of_reads_the_homography():
    c = camera_of(H_for(100), 200, 18)
    assert c["zoom"] > 0 and 0 < c["angle"] < 1 and c["height_px"] == 200 and c["pitch"] == 18
    assert camera_of(None) is None


def test_a_measure_made_by_the_zoom_is_found_and_a_real_one_is_not():
    rng = np.random.default_rng(1)
    rows = []
    for m in range(4):
        for _ in range(40):
            z = 80 + 40 * rng.random()
            cam = camera_of(H_for(z), 150 + 50 * rng.random(), 15 + 5 * rng.random())
            rows.append((f"m{m}", cam, {"metrics.from_zoom": 0.05 * z + rng.normal(0, 0.3),
                                        "metrics.her_own": rng.normal(10, 2), "match_time_s": 3.0}))
    res = {e["measure"]: e for e in shares(rows, shuffles=100)}
    assert res["metrics.from_zoom"]["camera_dependent"] and res["metrics.from_zoom"]["share"] > 0.5
    assert not res["metrics.her_own"]["camera_dependent"]
    assert "match_time_s" not in res                         # not a measure


def test_too_few_strokes_give_nothing():
    cam = camera_of(H_for(), 150, 15)
    assert shares([("m", cam, {"metrics.a": 1.0})] * 10) == []
