"""The racket and 3D model outputs of a window kept on disk (29-10, B-4: 60 % of a recompute): the second
measure of a stroke reads neither the video nor the models, and gives the same result."""
from types import SimpleNamespace

import numpy as np

from tennisbio import racket_orientation as ro


class Sk(dict):
    hand = "right"


def fake_run(T=40):
    poly = np.array([[10, 10], [20, 10], [20, 30], [10, 30]], float)
    img = np.zeros((T, 26, 2)); img[:, 0] = [15, 20]
    return SimpleNamespace(fps=25.0, img=img, sk=Sk(dom_wrist=0), rackets=[[poly]] * T, height_px=200.0,
                           boxes=[np.array([0, 0, 50, 100.0])] * T)


def setup(monkeypatch, calls):
    def read_frames(video, a, b):
        calls["read"] += 1
        return {f: np.full((4, 4, 3), f, np.uint8) for f in range(a, b)}

    def face_track(frames, boxes, img, rackets, sk, hpx, hm, i, a, b, wb3d=None, cam=None, *args, racket_kps=None, **kw):
        out = []
        for f in range(a, b):
            k3 = wb3d(frames[f], boxes[f])[0] if wb3d is not None and f in frames else None
            out.append({"frame": f, "face": None if k3 is None else float(k3.sum()) + float(racket_kps[f].sum()),
                        "points_to": "red", "tilt_deg": 1.0, "yaw_deg": 2.0, "observed": True,
                        "hand_evidence": k3 is not None, "ambiguous": False})
        return out
    monkeypatch.setattr(ro, "read_frames", read_frames)
    monkeypatch.setattr(ro, "face_track", face_track)
    monkeypatch.setattr(ro, "trunk_rotation_3d", lambda *a, **k: None)

    class RPose:
        def many(self, items):
            calls["racket"] += len(items)
            return np.array([np.full((5, 2), fr[0, 0, 0], float) + box[0] for fr, box in items]), None

    def wb3d(frame, box):
        calls["3d"] += 1
        return np.full((133, 3), float(frame[0, 0, 0])), np.ones(133), np.zeros((133, 2))
    return RPose(), wb3d


def test_second_measure_uses_the_memo(monkeypatch, tmp_path):
    calls = {"read": 0, "racket": 0, "3d": 0}
    rpose, wb3d = setup(monkeypatch, calls)
    run, stroke = fake_run(), SimpleNamespace(impact_frame=20, phases={"impact": {"frame": 20}}, stroke="forehand")
    path = tmp_path / "w1_2000_faces.pkl"
    first = ro.stroke_faces(tmp_path / "w1_2000.mp4", run, stroke, 1.8, None, rpose, wb3d, 2,
                            memo=ro.ModelMemo(path, "m:1"))
    assert calls["read"] == 1 and calls["racket"] > 0 and calls["3d"] > 0 and path.exists()
    before = dict(calls)
    again = ro.stroke_faces(tmp_path / "w1_2000.mp4", run, stroke, 1.8, None, rpose, wb3d, 2,
                            memo=ro.ModelMemo(path, "m:1"))
    assert calls == before                                    # no video, no model
    assert again == first
    plain = ro.stroke_faces(tmp_path / "w1_2000.mp4", run, stroke, 1.8, None, rpose, wb3d, 2)
    assert plain == first                                     # the same as without any memo


def test_other_models_start_afresh(monkeypatch, tmp_path):
    calls = {"read": 0, "racket": 0, "3d": 0}
    rpose, wb3d = setup(monkeypatch, calls)
    run, stroke = fake_run(), SimpleNamespace(impact_frame=20, phases={}, stroke="forehand")
    path = tmp_path / "w1_2000_faces.pkl"
    ro.stroke_faces(tmp_path / "v.mp4", run, stroke, 1.8, None, rpose, wb3d, 2, memo=ro.ModelMemo(path, "m:1"))
    ro.stroke_faces(tmp_path / "v.mp4", run, stroke, 1.8, None, rpose, wb3d, 2, memo=ro.ModelMemo(path, "m:2"))
    assert calls["read"] == 2
    path.write_bytes(b"damaged")
    assert ro.ModelMemo(path, "m:1").data == {}
