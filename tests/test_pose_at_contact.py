import json

from tennisbio.audit import pose_at_contact_items


def _match(tmp_path, strokes):
    d = tmp_path / "m"
    (d / "series").mkdir(parents=True)
    out = []
    for i, (side, kind, has_pose) in enumerate(strokes):
        kp = [[1.0, 2.0] * 17 if has_pose else [None, None] * 17 for _ in range(50)]
        (d / "series" / f"s{i}.json").write_text(json.dumps({"fps": 50, "first": 0, "impact": 25, "n": 50, "kp": kp}),
                                                 encoding="utf-8")
        out.append({"side": side, "stroke": kind, "series": f"series/s{i}.json", "stroke_id": f"m-{i}"})
    (d / "strokes.json").write_text(json.dumps(out), encoding="utf-8")
    return d


def test_strokes_kept_without_her_pose_at_the_contact_fail(tmp_path):
    # 12-11: in the library analyses 41 % of her near serves had no keypoint at the contact and the audit called them valid
    d = _match(tmp_path, [("near", "overhead", False)] * 4 + [("near", "overhead", True)] * 6 + [("near", "forehand", True)] * 10
               + [("far", "forehand", False)] * 3)
    it = pose_at_contact_items([d])[0]
    assert it["status"] == "falta" and "cerca 16 de 20" in it["detail"] and "saques 6 de 10" in it["detail"]
    assert "lejos" in it["detail"]


def test_all_near_strokes_with_pose_pass(tmp_path):
    d = _match(tmp_path, [("near", "forehand", True)] * 20 + [("far", "backhand", False)] * 5)
    assert pose_at_contact_items([d])[0]["status"] == "ok"
