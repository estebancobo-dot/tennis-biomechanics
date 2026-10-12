"""Who is the near player in each main-camera run (players change ends every two games).

Fully automatic, from two independent cues:
- the rule of tennis: players change ends after every odd game and every 6 tie-break points, so
  the scoreboard's games say how many changes there have been; a single run where we know who is
  near (she serves and the scoreboard's serve marker says who serves) fixes every other run;
- the near player's clothing (colour histogram) splits the runs into two people, and the serve
  votes say which one is the target.
When both are available and disagree on a run, that run stays undecided.
"""
import numpy as np


def cluster_two(feats: np.ndarray, iters=20, seed=0) -> np.ndarray:
    """Labels 0/1 for appearance histograms (N, D) — k-means with k=2 on √hist (Hellinger)."""
    X = np.sqrt(np.clip(feats, 0, None))
    if len(X) < 2:
        return np.zeros(len(X), int)
    d = np.linalg.norm(X[:, None] - X[None], axis=-1)
    i, j = np.unravel_index(np.argmax(d), d.shape)           # the two most different runs as seeds
    C = X[[i, j]].copy()
    lab = np.zeros(len(X), int)
    for _ in range(iters):
        lab = np.argmin(np.linalg.norm(X[:, None] - C[None], axis=-1), axis=1)
        for k in (0, 1):
            if (lab == k).any():
                C[k] = X[lab == k].mean(0)
    return lab


def assign(labels: np.ndarray, votes: list[tuple[int, bool]], min_votes=2, min_share=0.7) -> dict:
    """Which cluster is the target from votes (run index, near player is target).

    Returns {"target_cluster": 0/1/None, "confidence": share of agreeing votes, "votes": n}."""
    score = {0: [0, 0], 1: [0, 0]}                 # per cluster: [target votes, opponent votes]
    for run, is_target in votes:
        score[int(labels[run])][0 if is_target else 1] += 1
    # cluster c is the target if its target votes plus the other's opponent votes dominate
    t0 = score[0][0] + score[1][1]
    t1 = score[1][0] + score[0][1]
    n = t0 + t1
    if n < min_votes:
        return {"target_cluster": None, "confidence": 0.0, "votes": n}
    best, share = (0, t0 / n) if t0 >= t1 else (1, t1 / n)
    if share < min_share:
        return {"target_cluster": None, "confidence": round(share, 2), "votes": n}
    return {"target_cluster": best, "confidence": round(share, 2), "votes": n}


def end_changes(games: list, points=None, tiebreak: bool = False) -> int | None:
    """How many times the players have changed ends so far, from the scoreboard.

    Rules of tennis: ends change after the 1st, 3rd, 5th… game of every set (so after a set with an
    odd number of games too), and every 6 points inside a tie-break. games: [[a, b], …] one pair per
    set, the last one being the current set."""
    if not games:
        return None
    try:
        done = sum((int(a) + int(b) + 1) // 2 for a, b in games[:-1])
        a, b = games[-1]
        cur = (int(a) + int(b) + 1) // 2
    except (TypeError, ValueError):
        return None
    tb = 0
    if tiebreak and points:
        try:
            tb = (int(points[0]) + int(points[1])) // 6
        except (TypeError, ValueError):
            tb = 0
    return done + cur + tb


def decide_by_ends(parities: list, votes: list[tuple[int, bool]], min_share=0.75) -> bool | None:
    """Is the near player the target at an even number of end changes? One consistent vote is
    enough (the rule is exact); conflicting votes need a clear majority."""
    est = [is_t ^ bool(parities[i] % 2) for i, is_t in votes if parities[i] is not None]
    if not est:
        return None
    share = max(est.count(True), est.count(False)) / len(est)
    if share < min_share:
        return None
    return est.count(True) >= est.count(False)


def near_serves(kps: np.ndarray, conf: np.ndarray, fps: float, height_px: float, within_s=4.0,
                feet_y: np.ndarray | None = None, min_swing=1.5, swing_within_s=1.5) -> int | None:
    """Frame (within the first `within_s` of a run) where the near player serves, or None: a wrist
    well above the head (either hand: the opponent may be left-handed), followed by a fast arm
    swing (raised arms in a celebration or a stretch move slowly), standing at the baseline when
    the court is known (feet_y: court y of the feet per frame, m from her baseline)."""
    n = min(len(kps), int(within_s * fps))
    wr = kps[:, [9, 10]]
    v = np.linalg.norm(np.diff(wr, axis=0), axis=-1) * fps / max(height_px, 1.0)      # heights/s
    v = np.r_[np.full((1, 2), np.nan), v]
    for t in range(n):
        k, c = kps[t], conf[t]
        if np.isnan(k[0]).any() or c[0] < 0.3:
            continue
        wy = min(k[9, 1] if c[9] > 0.3 else np.inf, k[10, 1] if c[10] > 0.3 else np.inf)
        if not wy < k[0, 1] - 0.12 * height_px:
            continue
        w = v[t + 1:t + 1 + int(swing_within_s * fps)]
        if not (np.isfinite(w).any() and np.nanmax(w) >= min_swing):
            continue
        if feet_y is not None and np.isfinite(feet_y[t]) and not -3.0 <= feet_y[t] <= 1.0:
            continue
        return t
    return None
