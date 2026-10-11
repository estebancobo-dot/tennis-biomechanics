"""Who is the near player in each main-camera run (players change ends every two games).

Fully automatic: the near player's clothing (colour histogram) splits the runs into two people;
each run where the near player serves at the start of the point is matched with the scoreboard's
serve marker (who serves this game), which says whether that person is the target player. The
majority vote of each appearance cluster decides; runs without enough evidence stay uncertain.
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


def near_serves(kps: np.ndarray, conf: np.ndarray, fps: float, height_px: float, within_s=4.0) -> int | None:
    """Frame (within the first `within_s` of a run) where the near player serves: a wrist well
    above the head (either hand: the opponent may be left-handed), or None."""
    n = min(len(kps), int(within_s * fps))
    for t in range(n):
        k, c = kps[t], conf[t]
        if np.isnan(k).any() or c[0] < 0.3:
            continue
        wy = min(k[9, 1] if c[9] > 0.3 else np.inf, k[10, 1] if c[10] > 0.3 else np.inf)
        if wy < k[0, 1] - 0.12 * height_px:
            return t
    return None
