"""The learned spotter in the pipeline (stage `spotting`, candidates with `spotter.enabled`): a tiny ONNX model
written here byte by byte (no onnx/torch needed), synthetic cheap-pass outputs, and the old behaviour with it off."""
import json
import struct

import numpy as np
import pytest

from tennisbio import pipeline, spotting as S, stages
from tennisbio.catalog import Match, Player


# ---------------------------------------------------------------- a minimal ONNX writer (protobuf by hand)

def _varint(n: int) -> bytes:
    out = b""
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out += bytes([b | 0x80])
        else:
            return out + bytes([b])


def _key(field: int, wire: int) -> bytes:
    return _varint(field << 3 | wire)


def _int(field: int, v: int) -> bytes:
    return _key(field, 0) + _varint(v)


def _bytes(field: int, v) -> bytes:
    v = v.encode() if isinstance(v, str) else v
    return _key(field, 2) + _varint(len(v)) + v


def _tensor(name: str, arr: np.ndarray) -> bytes:
    arr = np.ascontiguousarray(arr, np.float32)
    return b"".join(_int(1, d) for d in arr.shape) + _int(2, 1) + _bytes(8, name) + _bytes(9, arr.tobytes())


def _value_info(name: str, dims: list) -> bytes:
    shape = b"".join(_bytes(1, _int(1, d) if isinstance(d, int) else _bytes(2, d)) for d in dims)
    tensor_type = _int(1, 1) + _bytes(2, shape)
    return _bytes(1, name) + _bytes(2, _bytes(1, tensor_type))


def _node(op: str, ins: list, outs: list, attrs: bytes = b"") -> bytes:
    return b"".join(_bytes(1, i) for i in ins) + b"".join(_bytes(2, o) for o in outs) + _bytes(4, op) + attrs


def linear_softmax_onnx(path, W: np.ndarray, b: np.ndarray):
    """prob = softmax(features @ W + b) over the classes; input "features" (1, frames, F), output "prob"."""
    F, C = W.shape
    axis = _bytes(5, _bytes(1, "axis") + _int(3, (1 << 64) - 1) + _int(20, 2))       # axis = -1 (INT)
    graph = (_bytes(1, _node("MatMul", ["features", "W"], ["z"])) + _bytes(1, _node("Add", ["z", "b"], ["l"]))
             + _bytes(1, _node("Softmax", ["l"], ["prob"], axis)) + _bytes(2, "g")
             + _bytes(5, _tensor("W", W)) + _bytes(5, _tensor("b", b))
             + _bytes(11, _value_info("features", [1, "frames", F])) + _bytes(12, _value_info("prob", [1, "frames", C])))
    model = _int(1, 8) + _bytes(8, _bytes(1, "") + _int(2, 17)) + _bytes(7, graph)
    path.write_bytes(model)


# ---------------------------------------------------------------- the synthetic match

N, FPS = 100, 10.0
ONSET_NEAR, ONSET_FAR = 2.0, 7.0          # near player seen in frames 0-49 only: the far stroke is at 7 s


def spotter_model(tmp_path, feature_dim=S.FEATURE_DIM - 1, fps=FPS, threshold=0.5):
    """A near forehand where there is an impact sound and the near player is seen, a far backhand where there
    is a sound and she is not (column 2*PERSON_DIM: transients in the frame; PERSON_DIM-1: near player seen)."""
    C = len(S.CLASSES)
    W = np.zeros((feature_dim, C), np.float32)
    b = np.zeros(C, np.float32)
    b[0] = 6.0
    on, seen = 2 * S.PERSON_DIM, S.PERSON_DIM - 1
    nf, fb = S.CLASSES.index("near_forehand"), S.CLASSES.index("far_backhand")
    W[on, nf], W[seen, nf], b[nf] = 10.0, 10.0, -10.0
    W[on, fb], W[seen, fb] = 10.0, -10.0
    onnx = tmp_path / "models" / "spotting.onnx"
    onnx.parent.mkdir(parents=True, exist_ok=True)
    linear_softmax_onnx(onnx, W, b)
    onnx.with_suffix(".json").write_text(json.dumps({"classes": list(S.CLASSES), "feature_dim": feature_dim, "fps": fps,
                                                     "threshold": threshold}))
    return onnx


def write_match(d, near_is_target=True):
    kp = np.zeros((17, 2), np.float32)
    kp[:, 0] = 900 + np.arange(17)
    kp[:, 1] = np.linspace(600, 900, 17)
    obj = lambda xs: np.array(xs + [None], dtype=object)[:-1]
    boxes, kps, confs, feats = [], [], [], []
    for i in range(N):
        near = i < 50
        bx = [[880, 580, 940, 910, 0.9]] if near else []
        bx.append([950, 200, 970, 260, 0.8])
        boxes.append(np.array(bx, np.float32))
        kps.append(np.stack(([kp] if near else []) + [kp * 0.2 + [800, 100]]).astype(np.float32))
        confs.append(np.ones((len(bx), 17), np.float32))
        feats.append(np.ones((len(bx), 32), np.float32))
    d.mkdir(parents=True, exist_ok=True)
    np.savez(d / "players.npz", fps=FPS, frames=np.arange(N), height=1080, boxes=obj(boxes), kps=obj(kps),
             confs=obj(confs), feats=obj(feats))
    (d / "scenes.json").write_text(json.dumps({"fps": FPS, "shots": [{"start": 0, "end": N, "main_camera": True}]}))
    (d / "audio_onsets.json").write_text(json.dumps({"t": [ONSET_NEAR, ONSET_FAR]}))
    (d / "court.json").write_text(json.dumps({"fps": FPS, "shots": []}))
    (d / "score.json").write_text(json.dumps({"shots": []}))
    (d / "identity.json").write_text(json.dumps({"fps": FPS, "runs": [{"start": 0, "end": N, "near_is_target": near_is_target}]}))


def ctx_for(tmp_path, cfg):
    return pipeline.Context(Match("m1", tmp_path / "v.mp4", Player("p", "P")), cfg, tmp_path / "out", log=lambda *_: None)


def on_cfg(onnx, **kw):
    return {"cheap_pass": {"fps": FPS}, "spotter": {"enabled": True, "onnx": str(onnx), **kw}}


# ---------------------------------------------------------------- tests

def test_fake_model_runs_in_onnxruntime_and_in_pieces(tmp_path):
    rng = np.random.default_rng(0)
    onnx = tmp_path / "m.onnx"
    linear_softmax_onnx(onnx, rng.normal(size=(5, len(S.CLASSES))), rng.normal(size=len(S.CLASSES)))
    X = rng.normal(size=(300, 5)).astype(np.float32)
    whole = S.predict_onnx(onnx, X, chunk=4096)
    assert whole.shape == (300, len(S.CLASSES)) and np.allclose(whole.sum(1), 1, atol=1e-5)
    assert np.allclose(S.predict_onnx(onnx, X, chunk=37, overlap=5), whole, atol=1e-6)


def test_fit_features_drops_the_sound_flux_for_older_models():
    X = np.arange(2 * S.FEATURE_DIM, dtype=np.float32).reshape(2, -1)
    assert S.fit_features(X, S.FEATURE_DIM) is X
    old = S.fit_features(X, S.FEATURE_DIM - 1)
    assert old.shape == (2, S.FEATURE_DIM - 1) and 2 * S.PERSON_DIM + 2 not in old[0]
    with pytest.raises(ValueError, match="volver a entrenarlo"):
        S.fit_features(X, 50)


def test_spotting_stage_writes_both_ends(tmp_path):
    onnx = spotter_model(tmp_path)
    ctx = ctx_for(tmp_path, on_cfg(onnx))
    write_match(ctx.dir)
    res = stages.st_spotting(ctx)
    sp = json.loads((ctx.dir / "spotting.json").read_text())
    assert [(e["side"], e["kind"]) for e in sp] == [("near", "forehand"), ("far", "backhand")]
    assert abs(sp[0]["t"] - ONSET_NEAR) <= 0.1 and abs(sp[1]["t"] - ONSET_FAR) <= 0.1
    assert all(set(e) == {"t", "side", "kind", "score"} and e["score"] > 0.9 for e in sp)
    assert res["enabled"] and res["near"] == 1 and res["far"] == 1 and res["feature_dim"] == S.FEATURE_DIM - 1


def test_spotting_stage_warns_when_the_fps_differ(tmp_path):
    onnx = spotter_model(tmp_path, fps=25.0)
    logs = []
    ctx = ctx_for(tmp_path, on_cfg(onnx))
    ctx.log = logs.append
    write_match(ctx.dir)
    stages.st_spotting(ctx)
    assert any("AVISO" in m and "25 fps" in m for m in logs)
    assert len(json.loads((ctx.dir / "spotting.json").read_text())) == 2         # it still runs


def test_spotting_stage_needs_the_flux_only_for_a_model_trained_with_it(tmp_path, monkeypatch):
    onnx = spotter_model(tmp_path, feature_dim=S.FEATURE_DIM)
    ctx = ctx_for(tmp_path, on_cfg(onnx))
    write_match(ctx.dir)
    asked = []
    monkeypatch.setattr(S, "sound_flux_stream", lambda v, fps, n, **k: asked.append(n) or np.zeros(n, np.float32))
    stages.st_spotting(ctx)
    assert asked == [N]
    asked.clear()
    spotter_model(tmp_path, feature_dim=S.FEATURE_DIM - 1)
    stages.st_spotting(ctx)
    assert asked == []


def test_spotting_stage_off_computes_nothing(tmp_path):
    ctx = ctx_for(tmp_path, {"cheap_pass": {"fps": FPS}, "spotter": {"enabled": False}})
    ctx.dir.mkdir(parents=True)
    assert stages.st_spotting(ctx) == {"enabled": False}
    assert json.loads((ctx.dir / "spotting.json").read_text()) == []


@pytest.mark.parametrize("who", [True, False, None])
def test_candidates_from_the_spotter_carry_the_identity(tmp_path, who):
    onnx = spotter_model(tmp_path)
    ctx = ctx_for(tmp_path, on_cfg(onnx))
    write_match(ctx.dir, near_is_target=who)
    stages.st_spotting(ctx)
    res = stages.st_candidates(ctx)
    cands = json.loads((ctx.dir / "candidates.json").read_text())
    near, far = cands
    assert near["side"] == "near" and near["identity"] is who and near["target"] is who
    assert far["side"] == "far" and far["identity"] is who and far["target"] is (None if who is None else not who)
    assert near["audio"] and far["audio"] and near["source"] == "spotter" and near["kind"] == "forehand"
    assert res["source"] == "spotter" and res["candidates"] == 2 and res["far"] == 1
    # what the fine passes take: hers (fine), the opponent's (fine_opponent) and the undecided (fine_doubtful)
    keep_fine = lambda c: (c.get("target", c.get("identity")) is True)
    assert sum(map(keep_fine, cands)) == (0 if who is None else 1)
    assert sum(c["target"] is None for c in cands) == (2 if who is None else 0)


def test_candidates_apply_the_users_click_with_the_spotter(tmp_path, monkeypatch):
    onnx = spotter_model(tmp_path)
    ctx = ctx_for(tmp_path, on_cfg(onnx))
    write_match(ctx.dir, near_is_target=None)
    stages.st_spotting(ctx)
    from tennisbio import identity as I
    (ctx.dir / I.PICK_FILE).write_text("{}")
    monkeypatch.setattr(I, "apply_pick", lambda ident, pick: (
        {**ident, "runs": [{**r, "near_is_target": True} for r in ident["runs"]]}, "simulado"))
    stages.st_candidates(ctx)
    near, far = json.loads((ctx.dir / "candidates.json").read_text())
    assert near["target"] is True and far["target"] is False


def test_spotter_candidates_leave_replays_out():
    spotted = [{"t": 2.0, "side": "near", "kind": "serve", "score": 0.9},
               {"t": 12.0, "side": "far", "kind": "forehand", "score": 0.8},
               {"t": 30.0, "side": "near", "kind": "backhand", "score": 0.7},
               {"t": 40.0, "side": "far", "kind": "backhand", "score": 0.7}]
    ident = {"fps": 10.0, "runs": [{"start": 0, "end": 50, "near_is_target": True}]}
    runs = [(0.0, 4.9, False), (10.0, 14.9, True)]                        # the second run is a replay
    cands, info = stages.spotter_candidates(spotted, ident, 10.0, runs, [(29.0, 31.0)], np.array([2.05]))
    assert [c["t"] for c in cands] == [2.0, 40.0] and info["replays"] == 2
    assert cands[0]["audio"] and not cands[1]["audio"] and cands[1]["target"] is None     # no run: undecided


def test_off_the_candidates_and_their_fingerprints_stay_as_before(tmp_path):
    """Off (or without the key): the rules' candidates, and the fingerprints of candidates and of the fine
    passes identical to a config without the spotter at all; on: they change (and depend on spotting)."""
    onnx = spotter_model(tmp_path)
    base = {"cheap_pass": {"fps": FPS}}
    off = {**base, "spotter": {"enabled": False, "onnx": str(onnx)}}
    outs = []
    for cfg in (base, off):
        ctx = ctx_for(tmp_path, cfg)
        write_match(ctx.dir)
        stages.st_spotting(ctx)
        stages.st_candidates(ctx)
        outs.append((ctx.dir / "candidates.json").read_text())
    assert outs[0] == outs[1]
    assert all(c.get("source") != "spotter" for c in json.loads(outs[0]))
    manifest = {n: {"fingerprint": f"fp-{n}"} for n in pipeline.STAGES}
    fps_ = {}
    (tmp_path / "v.mp4").write_bytes(b"x")
    for name, cfg in (("base", base), ("off", off), ("on", on_cfg(onnx))):
        ctx = ctx_for(tmp_path, cfg)
        fps_[name] = pipeline.fingerprint("candidates", ctx, manifest)
        assert pipeline.STAGES["candidates"].all_deps(cfg) == (pipeline.STAGES["candidates"].deps
                                                              + (("spotting",) if name == "on" else ()))
    assert fps_["base"] == fps_["off"] != fps_["on"]


def test_run_orders_spotting_before_candidates_only_when_on(tmp_path):
    onnx = spotter_model(tmp_path)
    full_on = pipeline.order(["candidates"], on_cfg(onnx))
    assert "spotting" in full_on and full_on.index("spotting") < full_on.index("candidates")
    assert "spotting" not in pipeline.order(["candidates"], {"cheap_pass": {"fps": FPS}})


def test_default_config_has_the_spotter_on():
    from pathlib import Path
    from tennisbio.config import load_config
    cfg = load_config()         # on since 26-10: end-to-end recall 64 % against 4 % with the rules
    assert cfg["spotter"]["enabled"] is True and cfg["spotter"]["onnx"] == "models/spotting.onnx"
    assert stages.spotter_on(cfg) and (Path(__file__).resolve().parents[1] / "models" / "spotting.onnx").exists()


def test_validate_recall_switches_the_spotter_on():
    import importlib.util
    from pathlib import Path
    f = Path(__file__).resolve().parents[1] / "scripts" / "validate_recall.py"
    spec = importlib.util.spec_from_file_location("validate_recall_t", f)
    V = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(V)
    cfg = {"spotter": {"enabled": False, "onnx": "x.onnx"}, "a": 1}
    assert V.spotter_cfg(cfg, False) is cfg
    on = V.spotter_cfg(cfg, True)
    assert on["spotter"] == {"enabled": True, "onnx": "x.onnx"} and cfg["spotter"]["enabled"] is False


def test_sound_flux_stream_equals_sound_flux(tmp_path):
    import shutil
    import wave
    if shutil.which("ffmpeg") is None:
        pytest.skip("sin ffmpeg")
    sr = 22050
    rng = np.random.default_rng(0)
    y = rng.normal(0, 0.02, sr * 6 + 777).astype(np.float32)
    for t in (1.0, 3.3, 5.2):
        y[int(t * sr):int(t * sr) + 200] += 0.8 * np.sin(np.arange(200) * 0.9)
    f = tmp_path / "a.wav"
    with wave.open(str(f), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())
    a = S.sound_flux(f, 10.0, 70)
    for block in (60.0, 0.37):
        assert np.allclose(S.sound_flux_stream(f, 10.0, 70, block_s=block), a, atol=1e-4)
    assert a.max() > 1


def test_the_shipped_model_gives_the_same_in_pieces():
    """models/spotting.onnx sees ±24 frames: pieces with 64 frames of context give what the whole video gives."""
    from pathlib import Path
    onnx = Path(__file__).resolve().parents[1] / "models" / "spotting.onnx"
    if not onnx.exists():
        pytest.skip("sin models/spotting.onnx")
    F = S.model_meta(onnx)["feature_dim"]
    X = np.random.default_rng(0).normal(size=(1500, F)).astype(np.float32)
    assert np.allclose(S.predict_onnx(onnx, X, chunk=10 ** 6), S.predict_onnx(onnx, X, chunk=400, overlap=64), atol=1e-5)


def test_spotting_stage_adds_the_ball_for_a_model_trained_with_it(tmp_path, monkeypatch):
    from tennisbio import ball_features as BF
    onnx = spotter_model(tmp_path, feature_dim=S.FEATURE_DIM + BF.BALL_DIM)
    ctx = ctx_for(tmp_path, on_cfg(onnx))
    write_match(ctx.dir)
    monkeypatch.setattr(S, "sound_flux_stream", lambda v, fps, n, **k: np.zeros(n, np.float32))
    asked = []
    monkeypatch.setattr(BF, "cached_track", lambda d, v, factory, log=None: asked.append(d) or np.zeros((0, 4)))
    res = stages.st_spotting(ctx)
    assert asked == [ctx.dir] and res["feature_dim"] == S.FEATURE_DIM + BF.BALL_DIM
    assert len(json.loads((ctx.dir / "spotting.json").read_text())) == 2         # same strokes: the ball adds columns
