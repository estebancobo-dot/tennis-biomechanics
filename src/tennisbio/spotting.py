"""Learned stroke spotting (19-10, docs/plan_maestro.md block 1): the strokes of both players found by a small
temporal model trained on annotated broadcast strokes (F3Set), as the professional systems do, instead of the
hand-written rules of the candidates stage (audio + wrist peak + ball turn), which lost most strokes.

Hybrid: the PC runs the cheap pass (players.npz, court, audio) on F3Set compilations and exports, per
compilation, only numbers: the frame-by-frame features below and the annotated strokes (scripts/spotting_data.py).
They go to the pc-logs branch; the model is trained and measured in the cloud session (scripts/train_spotting.py)
and comes back as one small ONNX file in models/. No video frame leaves the PC.

Features, one row per frame of the cheap pass (10 fps; frames out of play are rows of zeros with play = 0):
- near player (the tracked person on the near half): 17 keypoints relative to the hip centre in body heights,
  their confidences, the body height over the frame height, the feet on the court (m), present flag;
- far player (tallest person on the far half, when the detector sees it): the same;
- audio: impact transients in the frame and the time to the nearest one;
- play flag.
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np

KINDS = ("serve", "forehand", "backhand", "other")
SIDES = ("near", "far")
CLASSES = ("none",) + tuple(f"{s}_{k}" for s in SIDES for k in KINDS)
PERSON_DIM = 17 * 2 + 17 + 1 + 2 + 1
FEATURE_DIM = 2 * PERSON_DIM + 2 + 1
KIND_OF = {"serve": "serve", "forehand": "forehand", "backhand": "backhand", "volley_other": "other"}


def _person(kp: np.ndarray, cf: np.ndarray, frame_h: float, feet_court) -> np.ndarray:
    """PERSON_DIM numbers of one person in one frame (zeros when not seen)."""
    out = np.zeros(PERSON_DIM, np.float32)
    if kp is None or not np.isfinite(kp).any():
        return out
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        hip = np.nanmean(kp[[11, 12]], axis=0)
        if not np.isfinite(hip).all():
            hip = np.nanmean(kp, axis=0)
        h = np.nanmax(kp[:, 1]) - np.nanmin(kp[:, 1])
    h = h if np.isfinite(h) and h > 1 else 1.0
    rel = np.nan_to_num((kp - hip) / h, nan=0.0)
    out[:34] = rel.reshape(-1)
    out[34:51] = np.nan_to_num(cf, nan=0.0)
    out[51] = h / max(frame_h, 1.0)
    if feet_court is not None and np.isfinite(feet_court).all():
        out[52:54] = np.clip(np.asarray(feet_court, np.float32) / np.array([6.0, 24.0], np.float32), -3, 3)
    out[54] = 1.0
    return out


def build_features(mdir: Path, hand: str = "right") -> dict:
    """Features of one analysed video (its stage outputs in mdir: players.npz, court.json, scenes.json,
    audio_onsets.json): {"t": (N,) seconds, "X": (N, FEATURE_DIM) float32, "fps": fps}."""
    from .court_metrics import to_court
    from .skeleton import Skeleton
    from .stages import _far_player, court_at, near_runs, play_mask

    mdir = Path(mdir)
    rd = lambda n: json.loads((mdir / n).read_text(encoding="utf-8")) if (mdir / n).exists() else None
    with np.load(mdir / "players.npz", allow_pickle=True) as z:
        d = {k: z[k] for k in z.files}
    fps, frames = float(d["fps"]), np.asarray(d["frames"], int)
    frame_h = float(d.get("height", 1080))
    court = rd("court.json")
    sc = rd("scenes.json") or {"shots": []}
    n = int(max(frames.max() + 1 if len(frames) else 0, max([s["end"] for s in sc.get("shots", [])] + [0])))
    X = np.zeros((n, FEATURE_DIM), np.float32)
    play = play_mask(sc, court) if sc.get("shots") else np.zeros(n, bool)
    X[:len(play), -1] = play[:n]
    sk = Skeleton("coco17", hand)
    pos = {int(f): i for i, f in enumerate(frames)}
    near_sel = {}
    for run, img, cf, _h, _app, sel in near_runs(d, sk, court, with_sel=True):
        for t, j in enumerate(sel):
            if j >= 0:
                near_sel[int(run[t])] = (int(j), img[t], cf[t])
    for f, i in pos.items():
        bx = d["boxes"][i]
        t = f / fps
        H = court_at(court, t)[0] if court else None
        j_near = -1
        if i in near_sel:
            j_near, kp, cf = near_sel[i]
            feet = None
            if H is not None:
                feet = to_court(H, np.array([[(bx[j_near, 0] + bx[j_near, 2]) / 2, bx[j_near, 3]]]))[0]
            X[f, :PERSON_DIM] = _person(kp, cf, frame_h, feet)
        if len(bx) and H is not None:
            # _far_player leaves out the near player's box; without one, a dummy last row stands in for it
            jf = (_far_player(bx, H, j_near) if j_near >= 0
                  else _far_player(np.vstack([bx[:, :4], [[0, 0, 0, 0]]]), H, len(bx)))
            if jf is not None:
                feet = to_court(H, np.array([[(bx[jf, 0] + bx[jf, 2]) / 2, bx[jf, 3]]]))[0]
                feet = np.array([feet[0], 23.77 - feet[1]])          # in her own frame: her baseline at 0
                X[f, PERSON_DIM:2 * PERSON_DIM] = _person(d["kps"][i][jf].astype(np.float64), d["confs"][i][jf],
                                                          frame_h, feet)
    onsets = _onsets(mdir)
    if len(onsets):
        idx = np.clip(np.round(onsets * fps).astype(int), 0, n - 1)
        np.add.at(X[:, 2 * PERSON_DIM], idx, 1.0)
        grid = np.arange(n) / fps
        k = np.searchsorted(onsets, grid)
        prev = np.abs(grid - onsets[np.clip(k - 1, 0, len(onsets) - 1)])
        nxt = np.abs(onsets[np.clip(k, 0, len(onsets) - 1)] - grid)
        X[:, 2 * PERSON_DIM + 1] = np.clip(np.minimum(prev, nxt), 0, 1.0)
    else:
        X[:, 2 * PERSON_DIM + 1] = 1.0
    return {"t": np.arange(n) / fps, "X": X, "fps": fps}


def _onsets(mdir: Path) -> np.ndarray:
    a = mdir / "audio_onsets.json"
    if not a.exists():
        return np.zeros(0)
    a = json.loads(a.read_text(encoding="utf-8"))
    tr = mdir / "audio_track.json"
    k = json.loads(tr.read_text(encoding="utf-8")).get("track", 0) if tr.exists() else 0
    tracks = a.get("tracks") or [a]
    return np.sort(np.asarray(tracks[k]["t"] if k < len(tracks) else a.get("t", []), float))


def labels_for(events: list[dict], n: int, fps: float) -> np.ndarray:
    """(n,) class index per frame: each annotated stroke on its nearest frame (and the frame each side,
    the contact falls between two frames at 10 fps); none elsewhere."""
    y = np.zeros(n, np.int64)
    for e in events:
        c = CLASSES.index(f"{e['side']}_{KIND_OF.get(e['kind'], 'other')}")
        f = int(round(e["t"] * fps))
        for g in (f - 1, f + 1, f):
            if 0 <= g < n:
                y[g] = c
    return y


def decode(prob: np.ndarray, fps: float, threshold: float = 0.5, min_gap_s: float = 0.6) -> list[dict]:
    """Strokes from per-frame class probabilities (N, len(CLASSES)): peaks of 1 - p(none) above the
    threshold, at least min_gap_s apart; each with its side and kind (the most likely stroke class)."""
    s = 1.0 - prob[:, 0]
    out, last = [], -1e9
    order = np.argsort(-s)
    taken = np.zeros(len(s), bool)
    gap = max(1, int(round(min_gap_s * fps)))
    for i in order:
        if s[i] < threshold:
            break
        if taken[max(0, i - gap):i + gap + 1].any():
            continue
        taken[i] = True
        # sub-frame time: centre of mass of the stroke score around the peak
        a, b = max(0, i - 1), min(len(s), i + 2)
        w = s[a:b]
        t = float(np.sum(np.arange(a, b) * w) / np.sum(w)) / fps
        c = int(np.argmax(prob[i, 1:])) + 1
        side, kind = CLASSES[c].split("_", 1)
        out.append({"t": round(t, 3), "side": side, "kind": kind, "score": round(float(s[i]), 3)})
    return sorted(out, key=lambda e: e["t"])


def evaluate(pred: list[dict], gt: list[dict], tol: float = 0.2) -> dict:
    """Recall / precision of the strokes (same side, ±tol s, one-to-one, closest first), by side and kind."""
    pairs = sorted((abs(p["t"] - g["t"]), i, j) for i, g in enumerate(gt) for j, p in enumerate(pred)
                   if p["side"] == g["side"] and abs(p["t"] - g["t"]) <= tol)
    ug, up, m = set(), set(), {}
    for _, i, j in pairs:
        if i not in ug and j not in up:
            ug.add(i)
            up.add(j)
            m[i] = j
    def rate(a, b):
        return None if not b else round(a / b, 3)
    res = {"gt": len(gt), "pred": len(pred), "found": len(m), "recall": rate(len(m), len(gt)),
           "precision": rate(len(m), len(pred))}
    for side in SIDES:
        g = [i for i, e in enumerate(gt) if e["side"] == side]
        res[side] = {"gt": len(g), "found": sum(i in m for i in g), "recall": rate(sum(i in m for i in g), len(g))}
        for k in KINDS:
            gk = [i for i in g if KIND_OF.get(gt[i]["kind"], "other") == k]
            res[side][k] = {"gt": len(gk), "found": sum(i in m for i in gk), "recall": rate(sum(i in m for i in gk), len(gk))}
    ok_kind = sum(KIND_OF.get(gt[i]["kind"], "other") == pred[j]["kind"] for i, j in m.items())
    res["kind_accuracy"] = rate(ok_kind, len(m))
    return res
