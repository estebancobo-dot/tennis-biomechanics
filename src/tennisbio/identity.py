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


def _valid_sets(games) -> bool:
    """A possible tennis score: every finished set won 6-0..6-4, 7-5 or 7-6 (a match tie-break counts as 7-6 or 1-0),
    the current set at most 7-7. Rejects the statistics boxes the reader takes for games (09-11, Miami: «1ST SERVE PTS
    WON 10/18 9/10» read as sets [[1, 9], [0, 1], [1, 0]])."""
    try:
        sets = [(int(a), int(b)) for a, b in games]
    except (TypeError, ValueError):
        return False
    if not sets or len(sets) > 5:
        return False
    for a, b in sets[:-1]:
        hi, lo = max(a, b), min(a, b)
        if not ((hi == 6 and lo <= 4) or (hi == 7 and lo in (5, 6)) or (hi == 1 and lo == 0)):
            return False
    a, b = sets[-1]
    return 0 <= a <= 7 and 0 <= b <= 7


def clean_games(readings: list) -> list:
    """The scoreboard readings whose games can be trusted for counting end changes (09-11, Rybakina-Pegula: one misread
    flips the end of every run it covers, and with both players in white nothing else tells them apart). Kept: readings
    with a possible score whose (sets shown, total of games) is on the longest non-decreasing run of the match (games never go back:
    a reading that lost a set column, [[2, 6]] after [[2, 6], [2, 1]], or jumped ahead, is out). Readings without
    games are kept as they are (they say nothing about the ends)."""
    idx = [i for i, r in enumerate(readings) if r.get("games") and _valid_sets(r["games"])]
    # (sets shown, total games): a reading that lost a set column goes back even when its total ties another's
    tot = [(len(readings[i]["games"]), sum(int(a) + int(b) for a, b in readings[i]["games"])) for i in idx]
    # longest non-decreasing subsequence of the totals (patience sorting with predecessor links)
    import bisect
    tails, tail_i, prev = [], [], [-1] * len(tot)
    for k, v in enumerate(tot):
        j = bisect.bisect_right(tails, v)
        if j == len(tails):
            tails.append(v)
            tail_i.append(k)
        else:
            tails[j], tail_i[j] = v, k
        prev[k] = tail_i[j - 1] if j else -1
    keep, k = set(), tail_i[-1] if tail_i else -1
    while k >= 0:
        keep.add(idx[k])
        k = prev[k]
    return [r for i, r in enumerate(readings) if not r.get("games") or i in keep]


def fill_parities(parities: list, mids_s: list[float], max_gap_s: float = 240.0) -> list:
    """End changes for the runs where no scoreboard was read (11-11, Rybakina-Pegula: 62 of 320 runs undecided): a run
    takes its neighbours' number when the nearest read run before it and the nearest after it say the same and are at
    most max_gap_s apart (no change of ends fits in that time: it needs two games and the changeover). Otherwise it
    stays unknown. Read runs never change."""
    out = list(parities)
    known = [i for i, p in enumerate(parities) if p is not None]
    for i, p in enumerate(parities):
        if p is not None:
            continue
        before = [k for k in known if k < i]
        after = [k for k in known if k > i]
        if not before or not after:
            continue
        a, b = before[-1], after[0]
        if parities[a] == parities[b] and mids_s[b] - mids_s[a] <= max_gap_s:
            out[i] = parities[a]
    return out


def parity_between(readings: list, t: float, max_gap_s: float = 600.0) -> int | None:
    """End changes at time t from the scoreboard readings around it, however old (11-11, v12: runs far from any reading
    stayed undecided): the last reading with games before t and the first after it give the same number, and are at
    most max_gap_s apart (two changes of ends that cancel need at least two games and two changeovers). Else None."""
    before = after = None
    for r in readings:
        if not r.get("games"):
            continue
        if r["t"] <= t:
            before = r
        elif after is None:
            after = r
            break
    if before is None or after is None or after["t"] - before["t"] > max_gap_s:
        return None
    a = end_changes(before.get("games"), before.get("points"), before.get("tiebreak", False))
    b = end_changes(after.get("games"), after.get("points"), after.get("tiebreak", False))
    return a if a is not None and a == b else None


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


def near_receives(kps: np.ndarray, conf: np.ndarray, fps: float, height_px: float, onsets_k: list,
                  feet_y: np.ndarray | None = None, within_s=5.0) -> int | None:
    """Frame of the opponent's serve while the near player waits to return it, or None.

    The serve is the first impact sound of the run (onsets_k: frame indices of the run); the near
    player is receiving when, in the 1.5 s before it, neither wrist rises above her shoulders (no
    toss, no trophy position), she stands at or behind her baseline, and she swings (the return)
    0.3-2 s after it. A serve she does not touch (an ace) gives no answer."""
    n = min(len(kps), int(within_s * fps))
    wr = kps[:, [9, 10]]
    v = np.linalg.norm(np.diff(wr, axis=0), axis=-1) * fps / max(height_px, 1.0)
    v = np.r_[np.full((1, 2), np.nan), v]
    for k in onsets_k:
        if not int(0.5 * fps) <= k < n:
            continue
        a = max(0, k - int(1.5 * fps))
        seg, c = kps[a:k + 1], conf[a:k + 1]
        sh = np.nanmin(seg[:, [5, 6], 1], axis=1)                      # higher shoulder (image y)
        ok = (c[:, [9, 10]] > 0.3) & np.isfinite(seg[:, [9, 10], 1])
        if not ok.any():
            return None
        if np.any((seg[:, [9, 10], 1] < sh[:, None] - 0.03 * height_px) & ok):
            return None                                                # an arm up: she may be serving
        if feet_y is not None and np.isfinite(feet_y[k]) and not -6.0 <= feet_y[k] <= 1.0:
            return None
        after = v[k + int(0.3 * fps):k + int(2.0 * fps)]
        if np.isfinite(after).any() and np.nanmax(after) >= 1.5:
            return k
        return None
    return None


PICK_FILE = "identidad_clic.json"


def apply_pick(identity: dict, pick: dict | None, weak: float = 0.08) -> tuple[dict, dict]:
    """The user's one click per match (19-10): pick = {"t": seconds, "near_is_her": bool} says who is the near
    player at that moment. Her clothes group is the group of the run there; every run whose clothes are
    clear (margin ≥ weak) is then decided by its group alone («ropa + clic»); the others keep their answer.
    Returns (identity with the runs updated, summary). Without a usable pick nothing changes."""
    runs = [dict(r) for r in identity.get("runs", [])]
    out = {**identity, "runs": runs}
    if not pick or "t" not in pick:
        return out, {"pick": None}
    fps = identity.get("fps") or 1.0
    f = float(pick["t"]) * fps
    at = next((r for r in runs if r["start"] <= f < r["end"]), None)
    # 09-11 (request 167): when the clothes groups are not two people (both in white) the photos are of the two
    # ends (even / odd number of end changes on the scoreboard) and the click names her end; with neither, no click
    # (a click says who is near at its moment, whatever photos it was made on: the grouping the evidence trusts is used)
    by = "ends" if "ends" in (pick.get("by"), identity.get("click_by")) else identity.get("click_by", "clothes")
    if by == "ends":
        if at is None or at.get("end_changes") is None:
            return out, {"pick": "sin cambios de lado leídos en ese momento"}
        hers = at["end_changes"] % 2 if pick.get("near_is_her", True) else 1 - at["end_changes"] % 2
        changed = 0
        for r in runs:
            if r.get("end_changes") is not None:
                v = r["end_changes"] % 2 == hers
                changed += r.get("near_is_target") != v
                r["near_is_target"], r["method"] = v, "cambios de lado + clic"
        out["target_parity"] = hers
        return out, {"pick": "aplicado", "by": "ends", "her_parity": hers, "changed": changed,
                     "by_click": sum(r.get("method") == "cambios de lado + clic" for r in runs)}
    if by != "clothes":
        return out, {"pick": "no aplicable: las dos jugadoras no se distinguen por la ropa ni por los cambios de lado"}
    if at is None or at.get("cluster", -1) < 0:
        return out, {"pick": "sin grupo de ropa en ese momento"}
    hers = at["cluster"] if pick.get("near_is_her", True) else 1 - at["cluster"]
    changed = 0
    for r in runs:
        if r.get("cluster", -1) >= 0 and (r.get("clothes_margin") or 0) >= weak or r is at:
            v = r["cluster"] == hers
            changed += r.get("near_is_target") != v
            r["near_is_target"], r["method"] = v, "ropa + clic"
    out["target_cluster"] = hers
    return out, {"pick": "aplicado", "her_cluster": hers, "changed": changed,
                 "by_click": sum(r.get("method") == "ropa + clic" for r in runs)}
