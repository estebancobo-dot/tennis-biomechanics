"""Our own learned ball bounce (request 199): a gradient-boosting classifier (scikit-learn's
HistGradientBoostingClassifier) on the same 12 features per frame as the CatBoost model of TennisProject
(tennisbio.candidates.bounce_ctb.features, after its smooth), trained by scripts/train_bounce.py on the annotated
bounces of the TrackNet dataset with the ball of OUR detector. TennisProject's model has no licence, so it is only a
reference; this one is ours.

Same task as tennisbio.ball's bounce rule (a (T, ≥2) image track, NaN where the ball was not seen). Before the
features the track is read at ~25 fps (`step`, as the ball tracker reads 50-60 fps video) and scaled to 720 image
rows (the TrackNet frames): the features are pixel differences.

Used by the fine pass only with `bounce_model: {use: own}` in the configuration (off by default: the rule), and only
after scripts/train_bounce.py has measured it better than the rule (held-out F1 > rule's F1 + 0.05)."""
from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np

from .bounce_ctb import features, peaks, smooth

VERSION = 1
REF_H = 720.0              # image rows of the TrackNet frames the model is trained on
LABEL_TOL = 1              # a feature row within this many frames of an annotated bounce is a positive
GRID = tuple(round(t, 2) for t in np.arange(0.10, 0.91, 0.05))   # thresholds tried on the training data


def track_features(track: np.ndarray, frame_h: float = REF_H, step: int = 1,
                   smooth_track: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """(features (n, 12), their frames in the full track) of an image track (T, ≥2), NaN where not seen."""
    step = max(1, int(step))
    if not len(track):
        return np.zeros((0, 12), np.float32), np.zeros(0, int)
    t = np.asarray(track, float).reshape(len(track), -1)[::step, :2] * (REF_H / float(frame_h or REF_H))
    x, y = smooth(t[:, 0], t[:, 1]) if smooth_track else (t[:, 0], t[:, 1])
    f, fr = features(x, y)
    return f, fr * step


def labels(frames: np.ndarray, bounces, tol: int = LABEL_TOL) -> np.ndarray:
    """1 for the rows whose frame is within tol frames of an annotated bounce, else 0."""
    frames = np.asarray(frames, int)
    b = np.asarray(sorted(int(v) for v in bounces), int)
    if not len(b) or not len(frames):
        return np.zeros(len(frames), np.int8)
    return (np.abs(frames[:, None] - b[None, :]).min(1) <= tol).astype(np.int8)


def group_folds(groups, k: int = 5) -> list[tuple[list, list]]:
    """k splits BY GROUP (a TrackNet game: one match, so one video): every clip of a game falls on the same side,
    so no frame of a held-out match is seen in training. [(training groups, held-out groups)], deterministic."""
    g = sorted(set(groups))
    k = max(2, min(int(k), len(g)))
    folds = [[x for i, x in enumerate(g) if i % k == f] for f in range(k)]
    return [([x for x in g if x not in held], held) for held in folds]


def new_classifier(seed: int = 0):
    from sklearn.ensemble import HistGradientBoostingClassifier

    # no early stopping (it would hold out frames at random, across clips): a fixed, modest model
    return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=20,
                                          l2_regularization=1.0, early_stopping=False, random_state=seed)


def detect(frames: np.ndarray, scores: np.ndarray, threshold: float) -> list[int]:
    """Bounce frames from per-row scores: rows above the threshold, the best of each run of consecutive rows
    (as bounce_ctb.peaks)."""
    s = np.asarray(scores, float)
    rows = np.flatnonzero(s > threshold)
    return sorted(int(frames[r]) for r in peaks(rows, s)) if len(rows) else []


class OwnBounce:
    """The trained model with its threshold (a pickle written by scripts/train_bounce.py, never in git)."""

    def __init__(self, model, threshold: float, meta: dict | None = None):
        self.model, self.threshold, self.meta = model, float(threshold), dict(meta or {})

    @classmethod
    def load(cls, path: str | Path) -> "OwnBounce":
        with open(path, "rb") as f:
            d = pickle.load(f)                  # our own file (scripts/train_bounce.py), not a downloaded one
        if d.get("version") != VERSION:
            raise ValueError(f"modelo de bote de otra versión ({d.get('version')} ≠ {VERSION}): vuelve a entrenarlo")
        return cls(d["model"], d["threshold"], d.get("meta"))

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "wb") as f:
            pickle.dump({"version": VERSION, "model": self.model, "threshold": self.threshold, "meta": self.meta}, f)
        tmp.replace(path)
        return path

    def scores(self, track: np.ndarray, frame_h: float = REF_H, step: int = 1) -> tuple[np.ndarray, np.ndarray]:
        """(frames of the full track that were scored, their bounce probability)."""
        f, fr = track_features(track, frame_h, step)
        if not len(fr):
            return fr, np.zeros(0)
        return fr, np.asarray(self.model.predict_proba(f)[:, 1], float)

    def bounces(self, track: np.ndarray, frame_h: float = REF_H, step: int = 1) -> list[int]:
        """Frames (of the full track) with a bounce, ascending."""
        fr, s = self.scores(track, frame_h, step)
        return detect(fr, s, self.threshold)

    def scored_bounces(self, track: np.ndarray, frame_h: float, fps: float) -> list[tuple[int, float]]:
        """[(frame, score)] of the bounces of a fine-pass track (read at ~25 fps, as the ball tracker)."""
        fr, s = self.scores(track, frame_h, max(1, round(fps / 25)))
        idx = {int(f): i for i, f in enumerate(fr)}
        return [(f, float(s[idx[f]])) for f in detect(fr, s, self.threshold)]

    def _in(self, track, lo, hi, fps, frame_h, min_y, max_y):
        from ..ball import Bounce

        out = []
        for f, sc in self.scored_bounces(track, frame_h, fps):
            if not lo <= f < hi or f >= len(track) or np.isnan(track[f, :2]).any():
                continue
            x, y = float(track[f, 0]), float(track[f, 1])
            if (min_y is not None and y < min_y) or (max_y is not None and y > max_y):
                continue
            out.append((sc, Bounce(f, x, y, float("nan"))))     # no turn angle: a learned bounce
        return [b for _, b in sorted(out, key=lambda o: -o[0])]

    def before(self, track: np.ndarray, hit_frame: int, fps: float, prev_hit: int | None = None,
               frame_h: float = REF_H, min_y: float | None = None, max_y: float | None = None):
        """As tennisbio.ball.bounce_before (same search stretch and image band): the best-scoring bounce, or None."""
        from ..ball import _bounce_search

        lo, hi = _bounce_search(hit_frame, fps, prev_hit)
        found = self._in(track, lo, hi, fps, frame_h, min_y, max_y)
        return found[0] if found else None

    def after(self, track: np.ndarray, hit_frame: int, fps: float, next_hit: int | None = None,
              frame_h: float = REF_H, max_y: float | None = None, min_y: float | None = None, max_s=1.6, guard_s=0.15):
        """As tennisbio.ball.bounce_after (same stretch): up to 4 candidates, best-scoring first."""
        lo = hit_frame + max(1, round(guard_s * fps))
        hi = (next_hit - max(1, round(0.05 * fps))) if next_hit is not None else hit_frame + round(max_s * fps)
        return self._in(track, lo, hi, fps, frame_h, min_y, max_y)[:4]


_LOADED: dict = {}


_WARNED: set = set()


def _own_path(cfg: dict):
    """The own model's file when it is asked for and exists, else None (warning once when asked for and missing)."""
    bm = (cfg or {}).get("bounce_model") or {}
    if str(bm.get("use", "rule")).lower() != "own":
        return None
    from ..config import resolve_path

    p = resolve_path(bm.get("path") or "models/bounce_own.pkl")
    if p is None or not p.exists():
        if str(p) not in _WARNED:
            _WARNED.add(str(p))
            print(f"  AVISO: bounce_model.use = own pero falta el modelo ({p}); se usa la regla "
                  "(scripts/train_bounce.py lo crea)", flush=True)
        return None
    return p


def configured(cfg: dict) -> OwnBounce | None:
    """The own bounce model when the configuration asks for it (`bounce_model: {use: own, path: ...}`), else None
    (the rule of tennisbio.ball). Asked for and missing (a machine where scripts/train_bounce.py never ran, 07-11:
    adopted by default after request 131): the rule, said once in the log, and the fingerprint says «rule» too
    (`setting`), so no result claims a model it did not use."""
    p = _own_path(cfg)
    if p is None:
        return None
    key = (str(p), p.stat().st_mtime)
    if key not in _LOADED:
        _LOADED[key] = OwnBounce.load(p)
    return _LOADED[key]


def setting(cfg: dict) -> dict:
    """The part of the fine pass's fingerprint: {} with the rule (fingerprints stay as they were), else the model."""
    p = _own_path(cfg)
    if p is None:
        return {}
    from ..config import model_state

    return {"bounce_model": ["own", model_state(str(p))]}
