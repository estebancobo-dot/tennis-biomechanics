"""Learned stroke spotting (tennisbio.spotting): features, labels, decoding and the evaluation."""
import json

import numpy as np

from tennisbio import spotting as S


def test_labels_decode_and_evaluate_round_trip():
    fps, n = 10.0, 200
    ev = [{"t": 3.02, "side": "near", "kind": "serve"}, {"t": 4.5, "side": "far", "kind": "forehand"},
          {"t": 6.0, "side": "near", "kind": "volley_other"}]
    y = S.labels_for(ev, n, fps)
    assert y[30] == S.CLASSES.index("near_serve") and y[45] == S.CLASSES.index("far_forehand")
    assert y[60] == S.CLASSES.index("near_other") and (y > 0).sum() == 9
    prob = np.full((n, len(S.CLASSES)), 0.01)
    prob[:, 0] = 0.95
    for i, c in ((30, "near_serve"), (45, "far_forehand"), (60, "near_other"), (150, "near_backhand")):
        prob[i, 0], prob[i, S.CLASSES.index(c)] = 0.1, 0.85
    pred = S.decode(prob, fps)
    assert [(p["side"], p["kind"]) for p in pred] == [("near", "serve"), ("far", "forehand"), ("near", "other"),
                                                      ("near", "backhand")]
    r = S.evaluate(pred, ev)
    assert r["found"] == 3 and r["recall"] == 1.0 and r["precision"] == 0.75 and r["kind_accuracy"] == 1.0
    assert r["near"]["serve"] == {"gt": 1, "found": 1, "recall": 1.0}


def test_decode_keeps_strokes_apart():
    fps = 10.0
    prob = np.zeros((50, len(S.CLASSES)))
    prob[:, 0] = 1.0
    for i in (20, 21, 23):               # one stroke spread over three frames: one detection
        prob[i, 0], prob[i, 1] = 0.2, 0.8
    assert len(S.decode(prob, fps)) == 1


def test_features_of_a_tiny_video(tmp_path):
    """Two people (near and far), 30 frames at 10 fps, one transient: the features have the near player,
    the audio and the play flag in the right places (no court: no far player, no feet)."""
    n = 30
    kp = np.zeros((17, 2), np.float32)
    kp[:, 0] = 900 + np.arange(17)
    kp[:, 1] = np.linspace(600, 900, 17)
    boxes, kps, confs, feats = [], [], [], []
    for i in range(n):
        boxes.append(np.array([[880, 580, 940, 910, 0.9], [950, 200, 970, 260, 0.8]], np.float32))
        kps.append(np.stack([kp, kp * 0.2 + [800, 100]]).astype(np.float32))
        confs.append(np.ones((2, 17), np.float32))
        feats.append(np.ones((2, 32), np.float32))
    obj = lambda xs: np.array(xs + [None], dtype=object)[:-1]
    np.savez(tmp_path / "players.npz", fps=10.0, frames=np.arange(n), height=1080, boxes=obj(boxes), kps=obj(kps),
             confs=obj(confs), feats=obj(feats))
    (tmp_path / "scenes.json").write_text(json.dumps({"fps": 10.0, "shots": [{"start": 0, "end": n, "main_camera": True}]}))
    (tmp_path / "audio_onsets.json").write_text(json.dumps({"t": [1.5]}))
    f = S.build_features(tmp_path)
    X = f["X"]
    assert X.shape == (n, S.FEATURE_DIM) and f["fps"] == 10.0
    assert X[:, -1].all()                                       # play
    assert X[5, S.PERSON_DIM - 1] == 1.0                        # near player present
    assert X[15, 2 * S.PERSON_DIM] == 1.0 and X[15, 2 * S.PERSON_DIM + 1] == 0.0
    assert abs(X[10, 2 * S.PERSON_DIM + 1] - 0.5) < 1e-6
