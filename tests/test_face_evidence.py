"""R50 on strokes already analysed: the face is shown only where its phase had the 3D hand (read-side, no recompute)."""
import json

from tennisbio.face_evidence import NO_HAND, hide_unreliable_faces, unreliable_phases


def _stroke():
    return {"stroke": "forehand",
            "face": {"loaded": {"tilt_deg": 12.0, "yaw_deg": 5.0, "points_to": "red", "hand_evidence": True},
                     "finish": {"tilt_deg": -60.0, "yaw_deg": 170.0, "points_to": "cielo", "hand_evidence": False},
                     "impact": None,
                     "ready": {"tilt_deg": None, "yaw_deg": None, "points_to": None, "hand_evidence": False,
                               "no_medible": "ya marcado"}},
            "technique": {"phases": {"loaded": {"face_tilt": 12.0, "elbow": 100},
                                     "finish": {"face_tilt": -60.0, "face_yaw": 170.0, "face_points_to": "cielo",
                                                "elbow": 150}},
                          "jitter": {"finish.face_yaw": 40.0, "loaded.face_yaw": 2.0, "finish.elbow": 3.0}}}


def test_only_phases_without_the_hand_lose_their_face():
    s = _stroke()
    assert unreliable_phases(s) == {"finish"}
    assert hide_unreliable_faces(s) == 1
    assert s["face"]["finish"]["tilt_deg"] is None and s["face"]["finish"]["no_medible"] == NO_HAND
    assert s["technique"]["phases"]["finish"] == {"elbow": 150}
    assert s["technique"]["phases"]["loaded"]["face_tilt"] == 12.0                   # with the hand: kept
    assert s["technique"]["jitter"] == {"loaded.face_yaw": 2.0, "finish.elbow": 3.0}
    assert hide_unreliable_faces(s) == 0                                              # idempotent


def test_the_report_reads_strokes_through_it(tmp_path):
    from types import SimpleNamespace

    from tennisbio import report
    d = tmp_path / "m"
    d.mkdir()
    (d / "strokes.json").write_text(json.dumps([_stroke()]), encoding="utf-8")
    src = __import__("inspect").getsource(report.collect)
    assert "hide_unreliable_faces(s)" in src
