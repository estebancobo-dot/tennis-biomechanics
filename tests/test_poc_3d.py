"""#309 (21-11): the trunk's turn in 3D measured on CalTennis' multi-view reference with the PC's own measure; MeTRAbs
(one calibrated view, the joints in the camera's frame) against MotionAGFormer, with the rule written before measuring."""
import json
import sys
import types
from pathlib import Path

import numpy as np

from tennisbio.infra import poc_3d

ROOT = Path(__file__).resolve().parents[1]


def test_the_rule():
    base = {"frames": 900, "within_15deg": 0.58, "xfactor_median_err_deg": 9.0}
    assert poc_3d.decide({"mag3d-xs": base, "metrabs": {"frames": 900, "within_15deg": 0.66, "xfactor_median_err_deg": 8.0}})["pasa"]
    assert not poc_3d.decide({"mag3d-xs": base, "metrabs": {"frames": 900, "within_15deg": 0.62, "xfactor_median_err_deg": 8.0}})["pasa"]
    assert not poc_3d.decide({"mag3d-xs": base, "metrabs": {"frames": 900, "within_15deg": 0.7, "xfactor_median_err_deg": 9.5}})["pasa"]
    assert "pocos" in poc_3d.decide({"mag3d-xs": base, "metrabs": {"frames": 50}})["motivo"]


def test_a_model_in_the_cameras_frame_is_read_as_the_reference_is(tmp_path):
    """mono3d_yaw: the trunk's 4 points in the camera's frame, rotated to the world, give the lines' directions about
    the vertical as the triangulated reference does (candidates.caltennis.trunk_yaw_from_world)."""
    import cv2
    b = poc_3d.bench()
    v = tmp_path / "v.mp4"
    w = cv2.VideoWriter(str(v), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
    for _ in range(5):
        w.write(np.zeros((48, 64, 3), np.uint8))
    w.release()

    class M:
        def trunk(self, frame, box, K):                      # shoulders along x, hips along x (camera = world here)
            return np.array([[0, 0, 0], [400, 0, 0], [0, 0, 500], [400, 0, 500]], float)
    cam = types.SimpleNamespace(K=np.eye(3), R_c2w=np.eye(3))
    y, ms = b.mono3d_yaw(v, [None, [0, 0, 10, 10], [0, 0, 10, 10], None, [0, 0, 10, 10]], cam, M())
    assert np.isnan(y[0]).all() and np.allclose(y[1], [0.0, 0.0]) and len(ms) == 3


def test_metrabs_reads_its_trunk_by_name():
    from tennisbio.candidates import metrabs3d as m3
    mb = object.__new__(m3.Metrabs)
    names = ["neck", "nose", "pelv", "lsho", "lelb", "lwri", "lhip", "lkne", "lank", "rsho", "relb", "rwri", "rhip",
             "rkne", "rank", "leye", "lear", "reye", "rear"]
    mb.idx = [names.index(n) for n in m3.TRUNK]

    class T:
        def __init__(self, a): self.a = a
        def numpy(self): return self.a
    poses = np.arange(19 * 3, dtype=float).reshape(1, 19, 3)
    mb.tf = types.SimpleNamespace(convert_to_tensor=lambda x: x, constant=lambda x, *_: x, float32=None)
    seen = {}
    mb.m = types.SimpleNamespace(estimate_poses=lambda img, boxes, **k: seen.update(boxes=boxes, **k) or {"poses3d": T(poses)})
    mb.num_aug = 1
    got = mb.trunk(np.zeros((10, 10, 3), np.uint8), [2, 3, 12, 23], np.eye(3))
    assert got.tolist() == poses[0][[3, 9, 6, 12]].tolist()
    assert seen["boxes"] == [[2.0, 3.0, 10.0, 20.0]] and seen["skeleton"] == "coco_19" and seen["num_aug"] == 1


def test_kaggle_installs_tensorflow_and_measures(tmp_path, monkeypatch):
    sys.path.insert(0, str(ROOT / "cloud" / "kaggle"))
    sys.path.insert(0, str(ROOT / "cloud"))
    import correr
    j = correr.parse_job('{"accion": "medir", "prueba": "3d"}')
    assert correr.poc_args(j, Path("/d/models/models"), None) == ["--datos", "/d/models/datasets", "--dispositivo", "cuda"]
    assert "3d" in correr.STREAMED and any(x.startswith("tensorflow-hub") for x in correr.METRABS_TF)
    src = (ROOT / "scripts" / "bench_candidates.py").read_text(encoding="utf-8")
    assert "extra: dict | None = None" in src and "for name, md in extra.items():" in src

    class B:
        @staticmethod
        def metrabs_model():
            return "M"

        @staticmethod
        def bench_mag3d(root, device, cfg, n_pairs, n_segments, seg_s, extra=None, lifter_names=()):
            assert extra == {"metrabs": "M"} and lifter_names == ("mag3d",) and (n_pairs, n_segments, seg_s) == (3, 5, 4.0)
            return {"per_model": {"mag3d-xs": {"frames": 500, "within_15deg": 0.5, "xfactor_median_err_deg": 10},
                                  "metrabs": {"frames": 500, "within_15deg": 0.6, "xfactor_median_err_deg": 9}}}
    monkeypatch.setattr(poc_3d, "bench", lambda: B)
    out = tmp_path / "p.json"
    assert poc_3d.main(["--datos", str(tmp_path), "--salida", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["regla"]["pasa"] is True
