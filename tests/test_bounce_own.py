"""Our own learned bounce (request 199): features, split by game, training on a toy set, the configuration switch."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _v_path(n=40, bounce=20):
    t = np.arange(n)
    x = 100 + 5.0 * t
    y = np.where(t <= bounce, 200 + 8.0 * t, 200 + 8.0 * bounce - 6.0 * (t - bounce))
    return np.stack([x, y], 1)


def toy_clip(rng, shots=4, noise=1.0):
    """A rally in the image (y down): each shot falls to its bounce, rises, and is hit back (x and y turn)."""
    pts, gt = [], []
    x, dx = 300.0, 6.0
    for _ in range(shots):
        y, vy = 150.0 + rng.uniform(-20, 20), rng.uniform(2, 4)
        for _ in range(int(rng.integers(12, 20))):           # falling, faster and faster
            pts.append((x, y))
            x, y, vy = x + dx, y + vy, vy + 1.2
        gt.append(len(pts))
        vy = -0.6 * vy                                        # bounce: up again, slower
        for _ in range(int(rng.integers(8, 14))):
            pts.append((x, y))
            x, y, vy = x + dx, y + vy, vy + 0.4
        dx = -dx                                              # hit: back the other way
    tr = np.asarray(pts) + rng.normal(0, noise, (len(pts), 2))
    return tr, gt


def toy_clips(n_games=4, per_game=3, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for g in range(n_games):
        for c in range(per_game):
            tr, gt = toy_clip(rng)
            out.append({"key": f"game{g + 1}_Clip{c + 1}", "group": f"game{g + 1}", "tracked": tr, "frame_h": 720,
                        "annotated": tr, "hits": [], "gt": gt})
    return out


def test_track_features_shape_step_and_scale():
    from tennisbio.candidates.bounce_own import track_features

    f, fr = track_features(_v_path(), smooth_track=False)
    assert f.shape == (len(fr), 12) and f.dtype == np.float32 and fr[0] == 2 and fr[-1] == 37
    f2, fr2 = track_features(_v_path() * 2, frame_h=1440, smooth_track=False)     # a 1440-row image: same features
    assert np.allclose(f, f2) and (fr == fr2).all()
    full = np.repeat(_v_path(), 2, axis=0)                                       # 60 fps read at 30
    f3, fr3 = track_features(full, step=2, smooth_track=False)
    assert (fr3 == fr * 2).all() and np.allclose(f3, f)
    e, efr = track_features(np.zeros((0, 2)))
    assert e.shape == (0, 12) and len(efr) == 0


def test_labels_within_tolerance():
    from tennisbio.candidates.bounce_own import labels

    assert labels(np.arange(10), [5]).tolist() == [0, 0, 0, 0, 1, 1, 1, 0, 0, 0]
    assert labels(np.arange(4), []).tolist() == [0, 0, 0, 0]


def test_group_folds_never_mix_a_game():
    from tennisbio.candidates.bounce_own import group_folds

    games = [f"game{i}" for i in range(1, 11)]
    folds = group_folds(games * 3, 5)
    assert len(folds) == 5
    held_all = [g for _, held in folds for g in held]
    assert sorted(held_all) == sorted(games)                                     # every game held out exactly once
    for tr, held in folds:
        assert not set(tr) & set(held) and set(tr) | set(held) == set(games)
    assert len(group_folds(["a", "b"], 5)) == 2


def test_evaluate_trains_without_the_held_out_game(monkeypatch):
    import train_bounce as T

    clips = toy_clips(n_games=3, per_game=2)
    seen = []
    real_fit = T.fit

    def spy(cl, train_on=("tracked",), seed=0):
        seen.append({c["group"] for c in cl})
        return real_fit(cl, train_on, seed)
    monkeypatch.setattr(T, "fit", spy)
    monkeypatch.setattr(T, "choose_threshold", lambda *a, **k: 0.5)
    ev = T.evaluate(clips, folds=3, rule=lambda c: [])
    assert len(seen) == 3 and all(len(s) == 2 for s in seen)                     # each fold: the two other games
    assert set(ev["thresholds"]) == {"game1", "game2", "game3"}
    assert ev["bounces"] == sum(len(c["gt"]) for c in clips)


def test_training_on_a_toy_set_finds_the_bounces(tmp_path):
    import train_bounce as T
    from tennisbio.candidates.bounce_own import OwnBounce

    clips = toy_clips()
    ev = T.evaluate(clips, folds=4, rule=lambda c: [])
    own, rule = ev["per_model"]["own"], ev["per_model"]["rule"]
    assert own["f1"] >= 0.9 and rule["f1"] == 0.0
    v = T.decide(own["f1"], rule["f1"], ev["bounces"])
    assert v["adopt"] is True
    assert T.decide(0.62, 0.581, 100)["adopt"] is False                          # not above the rule + 0.05
    assert T.decide(0.9, 0.5, 5)["insufficient"]                                 # too few bounces to tell
    model = OwnBounce(T.fit(clips), 0.5, {"x": 1})
    p = model.save(tmp_path / "m.pkl")
    again = OwnBounce.load(p)
    tr, gt = toy_clip(np.random.default_rng(42))
    found = again.bounces(tr)
    assert len(found) == len(gt) and all(min(abs(f - g) for g in gt) <= 2 for f in found)


def test_before_and_after_keep_the_rule_stretch_and_band():
    import train_bounce as T
    from tennisbio.candidates.bounce_own import OwnBounce

    clips = toy_clips(n_games=2)
    m = OwnBounce(T.fit(clips), 0.5)
    tr, gt = toy_clip(np.random.default_rng(7), shots=3)
    fps = 30.0
    hit = gt[1] + 5                                             # her hit after the second bounce
    b = m.before(tr, hit, fps, prev_hit=gt[0] + 4)
    assert b is not None and abs(b.frame - gt[1]) <= 2 and np.isclose(b.x, tr[b.frame, 0])
    assert m.before(tr, hit, fps, prev_hit=gt[0] + 4, min_y=10_000) is None      # outside the image band
    after = m.after(tr, gt[0] - 10, fps)
    assert after and abs(after[0].frame - gt[0]) <= 2 and len(after) <= 4


def test_switch_off_keeps_the_rule(tmp_path):
    from tennisbio.candidates.bounce_own import configured, setting
    from tennisbio.config import load_config
    from tennisbio.stages import _fine_settings

    cfg = load_config()
    assert (cfg.get("bounce_model") or {}).get("use") == "own"                    # adopted 07-11 (request 131)
    rule = {**cfg, "bounce_model": {"use": "rule"}}
    assert configured(rule) is None and configured({}) is None and setting(rule) == {}
    assert "bounce_model" not in _fine_settings(rule)                             # fingerprint as it was
    missing = {**cfg, "bounce_model": {"use": "own", "path": str(tmp_path / "none.pkl")}}
    assert configured(missing) is None and setting(missing) == {}                 # no file: the rule, and it says so
    assert "bounce_model" not in _fine_settings(missing)
    import train_bounce as T
    from tennisbio.candidates.bounce_own import OwnBounce
    p = OwnBounce(T.fit(toy_clips(n_games=2, per_game=1)), 0.5).save(tmp_path / "own.pkl")
    on = {**cfg, "bounce_model": {"use": "own", "path": str(p)}}
    assert isinstance(configured(on), OwnBounce)
    assert _fine_settings(on)["bounce_model"][0] == "own"


def test_bench_candidates_measures_the_own_model_only_on_request():
    import bench_candidates as B

    assert "bounce_own" in B.TRAINED and "bounce_own" not in B.CANDIDATES
    rep = {"generated": "x", "device": "cpu", "results": {"bounce_own": {
        "baseline": "regla", "accuracy": "F1 0.7 / 0.58", "speed": "1 / 1",
        "verdict": {"adopt": True, "reason": "supera"}, "notes": ["propio"]}}}
    md = B.to_markdown(rep)
    assert "| bounce_own |" in md and "**sí**" in md and "propio" in md
    assert "| bounce_own |" not in B.to_markdown({"generated": "x", "device": "cpu", "results": {}})


def test_report_markdown():
    import train_bounce as T

    rep = {"generated": "x", "per_model": {"own": {"f1": 0.7, "precision": 0.8, "recall": 0.6, "tp": 6, "fp": 1, "fn": 4},
                                           "rule": {"f1": 0.58, "precision": 0.6, "recall": 0.5, "tp": 5, "fp": 3, "fn": 5}},
           "verdict": {"adopt": True, "reason": "supera"}, "clips": 3, "games": ["game1"], "bounces": 10, "folds": 5,
           "thresholds": {"game1": 0.5}, "tol_frames": 3, "train_on": ["tracked"], "final_threshold": 0.5,
           "model": "models/bounce_own.pkl", "seconds_per_hour": {"own": 1.0, "rule": 0.5}}
    md = T.to_markdown(rep)
    assert "**sí**" in md and "| propio" in md and "0.05" in md
