"""Clothes: a within-match identity cue that does not depend on the scoreboard.

The appearance of the whole person box is mostly court (a near player covers a third of her box), so
two players on the same court looked alike: on 19-10 the clothes never decided a run in the four
matches (identity confidences 0.50-0.64). Here the clothing code uses only the shirt
(shoulders–hips) and the shorts/skirt (hips–thighs), leaves out the pixels of the court colours
around her, and is lighting-robust: hue for coloured pixels, lightness relative to the court's own
lightness for white/grey/black ones. The runs are split into two people by exhaustive 2-medoids
(outliers cannot be the seeds), with the near and far player of the same frames as cannot-link pairs,
and each run gets a margin. `fuse` combines that split with the end-change chain of the scoreboard.
"""
import numpy as np

HUE_BINS = 12
GREY_BINS = 3                      # dark / mid / light, relative to the court's lightness
REGION_DIM = HUE_BINS + GREY_BINS
CLOTHES_DIM = 2 * REGION_DIM       # torso, then shorts/skirt
REGION_WEIGHTS = (0.65, 0.35)
CHROMA_LO, CHROMA_HI = 8.0, 16.0   # Lab chroma (8-bit a, b centred on 128): grey below, coloured above
HUE_SMOOTH = 0.0                   # share of each hue bin spread to its neighbours (0.5 on 20 RacketVision clips
                                   # brought the near and the far player closer, 0.53 → 0.43: off)
COURT_TOL = 16.0                   # Lab distance (lightness at half weight) of a pixel to a court colour


def _lab(bgr: np.ndarray) -> np.ndarray:
    import cv2

    px = np.ascontiguousarray(np.asarray(bgr).reshape(-1, 1, 3), np.uint8)
    return cv2.cvtColor(px, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)


def _ldist(px: np.ndarray, c: np.ndarray) -> np.ndarray:
    d = px - c
    return np.sqrt((0.5 * d[:, 0]) ** 2 + d[:, 1] ** 2 + d[:, 2] ** 2)


def court_colours(frame: np.ndarray, box: np.ndarray, max_colours=3, min_share=0.15) -> np.ndarray:
    """The dominant colours (Lab, (K, 3)) of the ground around a person's box: the court surface(s),
    sampled beside and below the box; white lines and small things are not dominant. Deterministic:
    the median of what is left, refined twice on its neighbourhood, then removed, up to max_colours."""
    H, W = frame.shape[:2]
    x0, y0, x1, y1 = [float(v) for v in box[:4]]
    w, h = max(x1 - x0, 1.0), max(y1 - y0, 1.0)
    ox0, ox1 = int(max(0, x0 - 0.6 * w)), int(min(W, x1 + 0.6 * w))
    oy0, oy1 = int(max(0, y0 + 0.3 * h)), int(min(H, y1 + 0.25 * h))
    if ox1 <= ox0 or oy1 <= oy0:
        return np.zeros((0, 3), np.float32)
    mask = np.ones((oy1 - oy0, ox1 - ox0), bool)
    ix0, ix1 = int(max(ox0, x0 - 0.1 * w)) - ox0, int(min(ox1, x1 + 0.1 * w)) - ox0
    iy0, iy1 = int(max(oy0, y0)) - oy0, int(min(oy1, y1 + 0.05 * h)) - oy0
    mask[max(iy0, 0):max(iy1, 0), max(ix0, 0):max(ix1, 0)] = False
    px = frame[oy0:oy1, ox0:ox1][mask]
    if len(px) < 30:
        return np.zeros((0, 3), np.float32)
    if len(px) > 4000:
        px = px[:: len(px) // 4000 + 1]
    lab = _lab(px)
    n0, out, rest = len(lab), [], lab
    for _ in range(max_colours):
        if len(rest) < min_share * n0:
            break
        c = np.median(rest, axis=0)
        for _ in range(2):
            near = rest[_ldist(rest, c) < 2 * COURT_TOL]
            if len(near):
                c = np.median(near, axis=0)
        close = _ldist(rest, c) < COURT_TOL
        if close.sum() < min_share * n0:
            break
        out.append(c)
        rest = rest[~close]
    return np.array(out, np.float32).reshape(-1, 3)


def _poly_pixels(frame: np.ndarray, poly: np.ndarray) -> np.ndarray:
    import cv2

    m = np.zeros(frame.shape[:2], np.uint8)
    cv2.fillPoly(m, [np.round(poly).astype(np.int32)], 1)
    return frame[m.astype(bool)]


def _rect_pixels(frame: np.ndarray, x0, y0, x1, y1) -> np.ndarray:
    H, W = frame.shape[:2]
    x0, x1 = int(np.clip(x0, 0, W)), int(np.clip(x1, 0, W))
    y0, y1 = int(np.clip(y0, 0, H)), int(np.clip(y1, 0, H))
    return frame[y0:y1, x0:x1].reshape(-1, 3)


def colour_code(lab: np.ndarray, court: np.ndarray | None = None) -> np.ndarray | None:
    """Normalised (REGION_DIM,) code of clothing pixels (Lab): soft hue bins weighted by how coloured
    each pixel is, and soft lightness bins (relative to the court's lightness, so a cloud or the
    evening light moves her and the court together) for the grey ones. Pixels of the court colours
    are left out, unless nearly everything is court-coloured (then her clothes are)."""
    if lab is None or len(lab) < 12:
        return None
    if court is not None and len(court):
        keep = np.ones(len(lab), bool)
        for c in court:
            keep &= _ldist(lab, c) >= COURT_TOL
        if keep.sum() >= max(12, 0.15 * len(lab)):
            lab = lab[keep]
    a, b = lab[:, 1] - 128.0, lab[:, 2] - 128.0
    wc = np.clip((np.hypot(a, b) - CHROMA_LO) / (CHROMA_HI - CHROMA_LO), 0, 1)
    hist = np.zeros(REGION_DIM, np.float64)
    hue = (np.arctan2(b, a) % (2 * np.pi)) / (2 * np.pi) * HUE_BINS - 0.5
    lo = np.floor(hue).astype(int)
    fr = hue - lo
    np.add.at(hist, lo % HUE_BINS, wc * (1 - fr))
    np.add.at(hist, (lo + 1) % HUE_BINS, wc * fr)
    if HUE_SMOOTH:                                  # a hue shifted by light or white balance stays close
        h = hist[:HUE_BINS].copy()
        hist[:HUE_BINS] = (1 - HUE_SMOOTH) * h + HUE_SMOOTH / 2 * (np.roll(h, 1) + np.roll(h, -1))
    ref = float(np.median(court[:, 0])) if court is not None and len(court) else 128.0
    g = np.interp(lab[:, 0] / max(ref, 20.0), [0.35, 0.9, 1.6], [0.0, 1.0, 2.0])   # dark / mid / light
    gl = np.floor(np.minimum(g, 1.999)).astype(int)
    gf = g - gl
    np.add.at(hist, HUE_BINS + gl, (1 - wc) * (1 - gf))
    np.add.at(hist, HUE_BINS + gl + 1, (1 - wc) * gf)
    s = hist.sum()
    return (hist / s).astype(np.float32) if s > 0 else None


def clothing_feature(frame: np.ndarray, kps: np.ndarray | None, conf: np.ndarray | None, box: np.ndarray,
                     court: np.ndarray | None = None, min_conf=0.3) -> np.ndarray:
    """(CLOTHES_DIM,) clothing code of one person in one frame (NaN for a region not seen).

    Torso: the shoulders–hips quadrilateral (COCO 5, 6, 12, 11) shrunk towards its centre (arms and
    background off its edges); without those points, the upper-middle part of the box.
    Shorts/skirt: from the hips 45 % of the way to the knees; without them, the middle of the box."""
    if court is None:
        court = court_colours(frame, box)
    x0, y0, x1, y1 = [float(v) for v in box[:4]]
    w, h = x1 - x0, y1 - y0

    def ok(*i):
        return kps is not None and conf is not None and all(conf[j] > min_conf and np.isfinite(kps[j]).all() for j in i)

    out = np.full(CLOTHES_DIM, np.nan, np.float32)
    if ok(5, 6, 11, 12):
        q = kps[[5, 6, 12, 11]].astype(np.float64)
        torso = _poly_pixels(frame, q.mean(0) + 0.75 * (q - q.mean(0)))
    else:
        torso = _rect_pixels(frame, x0 + 0.3 * w, y0 + 0.2 * h, x1 - 0.3 * w, y0 + 0.45 * h)
    if ok(11, 12):
        hip = kps[[11, 12]].astype(np.float64)
        knee = kps[[13, 14]].astype(np.float64) if ok(13, 14) else hip + [0.0, 0.25 * h]
        low = hip + 0.45 * (knee - hip)
        q = np.array([hip[0], hip[1], low[1], low[0]])
        c = q.mean(0)
        lower = _poly_pixels(frame, c + np.array([[1.15, 1.0]]) * (q - c))       # a skirt is wider than the hips
    else:
        lower = _rect_pixels(frame, x0 + 0.25 * w, y0 + 0.47 * h, x1 - 0.25 * w, y0 + 0.62 * h)
    for r, px in enumerate((torso, lower)):
        code = colour_code(_lab(px), court) if len(px) else None
        if code is not None:
            out[r * REGION_DIM:(r + 1) * REGION_DIM] = code
    return out


def aggregate(codes) -> np.ndarray:
    """Robust per-run code: per region, the element-wise median over the frames that saw it,
    renormalised (an occlusion, a ball kid crossing or a blurred frame does not move it)."""
    X = np.asarray(codes, np.float32).reshape(-1, CLOTHES_DIM)
    out = np.full(CLOTHES_DIM, np.nan, np.float32)
    for r in range(2):
        sl = slice(r * REGION_DIM, (r + 1) * REGION_DIM)
        seen = np.isfinite(X[:, sl]).all(axis=1)
        if seen.any():
            m = np.median(X[seen, sl], axis=0)
            if m.sum() > 0:
                out[sl] = m / m.sum()
    return out


def clothes_distances(A: np.ndarray, B: np.ndarray | None = None) -> np.ndarray:
    """Pairwise distances between clothing codes (rows of A and B): Hellinger per region, weighted
    over the regions both codes have; NaN when they share none."""
    B = A if B is None else B
    num = np.zeros((len(A), len(B)))
    den = np.zeros((len(A), len(B)))
    for r, wt in enumerate(REGION_WEIGHTS):
        sl = slice(r * REGION_DIM, (r + 1) * REGION_DIM)
        a, b = A[:, sl], B[:, sl]
        both = np.isfinite(a).all(1)[:, None] & np.isfinite(b).all(1)[None]
        bc = np.sqrt(np.clip(np.nan_to_num(a), 0, None)) @ np.sqrt(np.clip(np.nan_to_num(b), 0, None)).T
        d = np.sqrt(np.clip(1 - bc, 0, None))
        num += np.where(both, wt * d, 0)
        den += np.where(both, wt, 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / den, np.nan)


def hist_distances(F: np.ndarray) -> np.ndarray:
    """Hellinger distances between whole-box appearance histograms (the players stage's; the fallback
    when the video cannot be read again)."""
    X = np.sqrt(np.clip(np.nan_to_num(np.asarray(F, np.float64)), 0, None))
    X = X / np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-9)
    return np.sqrt(np.clip(1 - X @ X.T, 0, None))


def split_two(D: np.ndarray, links=(), n_core: int | None = None, max_candidates=500,
              link_weight: float | None = None) -> dict:
    """Two-person split of the points of a distance matrix D (N, N) by exhaustive 2-medoids: the
    global optimum of the summed distances, so two outliers cannot become the seeds (as with k-means
    seeded by the two most different runs). Distances are capped at their 90th percentile (an outlier
    pulls no more than an ordinary far point).

    links: cannot-link pairs (i, j): two people seen at once (the near and the far player of the same
    frames) are not the same person; each pair left together costs `link_weight` (default: half the
    median distance). n_core: only the first n_core points may be medoids (the near-player runs; the
    far player's codes are small and noisy and only constrain the split).

    Returns {"labels": (N,) 0/1 (-1 without distances), "margins": (N,) in [-1, 1] — (median distance
    to the other group − to its own) / their sum —, "separation": median distance between groups /
    within groups, "links": n, "links_ok": share of cannot-link pairs split}."""
    N = len(D)
    lab, mar = np.full(N, -1), np.zeros(N)
    out = {"labels": lab, "margins": mar, "separation": None, "links": len(links), "links_ok": None}
    if N < 2:
        return out
    idx = np.flatnonzero(np.isfinite(D).sum(1) > 1)
    if len(idx) < 2:
        return out
    Dv = D[np.ix_(idx, idx)]
    off = ~np.eye(len(idx), dtype=bool)
    finite = Dv[np.isfinite(Dv) & off]
    if not len(finite):
        return out
    cap = float(np.quantile(finite, 0.9))
    C = np.where(np.isfinite(Dv), np.minimum(Dv, cap), cap)
    np.fill_diagonal(C, 0.0)
    pos = {int(g): k for k, g in enumerate(idx)}
    L = np.array([(pos[i], pos[j]) for i, j in links if i in pos and j in pos], int).reshape(-1, 2)
    lw = 0.5 * float(np.median(finite)) if link_weight is None else link_weight
    core = np.array([k for k, g in enumerate(idx) if n_core is None or g < n_core], int)
    if len(core) < 2:
        core = np.arange(len(idx))
    if len(core) > max_candidates:                      # deterministic thinning for huge inputs
        core = core[np.linspace(0, len(core) - 1, max_candidates).round().astype(int)]
    best = (np.inf, int(core[0]), int(core[1]))
    for a_i in range(len(core) - 1):
        i, J = core[a_i], core[a_i + 1:]
        di, dj = C[:, i][:, None], C[:, J]
        cost = np.minimum(di, dj).sum(0)
        if len(L):
            to_j = dj < di
            cost = cost + lw * (to_j[L[:, 0]] == to_j[L[:, 1]]).sum(0)
        k = int(np.argmin(cost))
        if cost[k] < best[0] - 1e-12:
            best = (float(cost[k]), int(i), int(J[k]))
    _, i, j = best
    lv = (C[:, j] < C[:, i]).astype(int)
    mv = np.zeros(len(idx))
    for p in range(len(idx)):
        own, oth = lv == lv[p], lv != lv[p]
        own[p] = False
        if own.any() and oth.any():
            do, dt = np.median(C[p, own]), np.median(C[p, oth])
            mv[p] = (dt - do) / (dt + do + 1e-9)
    lab[idx], mar[idx] = lv, mv
    same = lv[:, None] == lv[None]
    if (same & off).any() and (~same).any():
        out["separation"] = round(float(np.median(C[~same]) / max(np.median(C[same & off]), 1e-6)), 2)
    if len(L):
        out["links_ok"] = round(float(np.mean(lv[L[:, 0]] != lv[L[:, 1]])), 2)
    return out


def fuse(labels, margins, ends: list, direct: list, votes=(), weak=0.08, strong=0.2, min_share=0.7,
         strong_share=0.8, min_votes=2) -> tuple[list[dict], dict]:
    """Who is near in each run, from the clothes and the end-change chain together.

    labels, margins: the clothes split (split_two; label -1 = no clothes code). ends: per run, the
    end-change chain's answer (True near is the target / False / None). direct: per run, the run's own
    serve/return vote (True / False / None). votes: (run, is_target) serve/return votes, used to name
    her clothes when the chain says nothing.

    Which group of clothes is hers: the runs with a clear clothes label and the chain's answer (or,
    without it, the run's own serve/return vote) vote; it needs `min_share` of them. Then per run:
    - both cues agree → «ropa y cambios de lado»;
    - they disagree → the run's own serve/return backs the chain («cambios de lado»); else clear
      clothes (margin ≥ strong, groups named with ≥ strong_share) win: a misread game on the
      scoreboard flips the chain's parity, not her clothes («ropa (corrige el marcador)»); else
      «dudoso» (out of the comparisons, never deleted);
    - one cue alone decides («cambios de lado» / «ropa», clothes only with margin ≥ weak).
    Returns (per run {near_is_target, method, clothes}, summary)."""
    n = len(labels)
    ev = {0: [0, 0], 1: [0, 0]}                   # per clothes group: [near is her, near is not]
    for i in range(n):
        t = ends[i] if ends[i] is not None else direct[i]
        if labels[i] >= 0 and margins[i] >= weak and t is not None:
            ev[int(labels[i])][0 if t else 1] += 1
    used = sum(map(sum, ev.values()))
    if used < min_votes and votes:                # no chain: the serve/return votes alone
        ev = {0: [0, 0], 1: [0, 0]}
        for i, t in votes:
            if labels[i] >= 0:
                ev[int(labels[i])][0 if t else 1] += 1
        used = sum(map(sum, ev.values()))
    t0, t1 = ev[0][0] + ev[1][1], ev[1][0] + ev[0][1]
    share = max(t0, t1) / used if used else 0.0
    target = (0 if t0 >= t1 else 1) if used >= min_votes and share >= min_share else None
    counts = dict.fromkeys(("agree", "ends_only", "clothes_only", "ends_won", "clothes_won", "doubtful", "none"), 0)
    out = []
    for i in range(n):
        lab, m = int(labels[i]), float(margins[i])
        a_cl = None if target is None or lab < 0 or m < weak else bool(lab == target)
        a_end = ends[i]
        if a_cl is not None and a_end is not None:
            if a_cl == a_end:
                r, meth, key = a_end, "ropa y cambios de lado", "agree"
            elif direct[i] is not None and direct[i] == a_end:
                r, meth, key = a_end, "cambios de lado", "ends_won"
            elif m >= strong and share >= strong_share:
                r, meth, key = a_cl, "ropa (corrige el marcador)", "clothes_won"
            else:
                r, meth, key = None, "dudoso", "doubtful"
        elif a_end is not None:
            r, meth, key = a_end, "cambios de lado", "ends_only"
        elif a_cl is not None:
            r, meth, key = a_cl, "ropa", "clothes_only"
        else:
            r, meth, key = None, None, "none"
        counts[key] += 1
        out.append({"near_is_target": r, "method": meth,
                    "clothes": None if lab < 0 else {"group": lab, "margin": round(m, 2), "says": a_cl}})
    return out, {"target_cluster": target, "confidence": round(share, 2), "votes": used, **counts}


def identity_from_cues(codes, far, feats, ends: list, direct: list, votes=(), games: list | None = None,
                       weak=0.08, **kw) -> tuple[list[dict], dict]:
    """The identity stage's decision from its cues (pure: the stage reads the video and the scoreboard).

    codes: (R, CLOTHES_DIM) clothing code per run, or None without video; far: [(run, far player's
    code)], the cannot-link pairs; feats: (R, D) whole-box histograms of the players stage, the
    fallback without codes; ends, direct, votes: as in `fuse`; games: per run the games read on the
    scoreboard (any comparable value), for the check that the clothes stay the same inside a game.
    Returns (per run, summary): the summary keeps the stage's former keys (runs decided by the end
    changes / by the clothes, conflicts left undecided, decided) and adds the counts by cue and checks."""
    n = len(ends)
    links: list = []
    if codes is not None and len(codes) and np.isfinite(codes).any():
        X = np.asarray(codes, np.float32)
        if far:
            X = np.vstack([X, np.array([c for _, c in far], np.float32)])
            links = [(i, n + k) for k, (i, _) in enumerate(far)]
        D, source = clothes_distances(X), "ropa (torso y pantalón o falda, sin la pista)"
    elif feats is not None and len(feats):
        D, source = hist_distances(feats), "caja entera (sin vídeo)"
    else:
        D, source = np.full((n, n), np.nan), "ninguna"
    sp = split_two(D, links, n_core=n)
    labels, margins = sp["labels"][:n], sp["margins"][:n]
    per, summ = fuse(labels, margins, ends, direct, votes, weak=weak, **kw)
    same = [bool(labels[i] == labels[i + 1]) for i in range(n - 1)
            if games and games[i] is not None and games[i] == games[i + 1]
            and min(labels[i], labels[i + 1]) >= 0 and min(margins[i], margins[i + 1]) >= weak]
    clear = margins[labels >= 0]
    summ.update({
        "by_end_changes": summ["agree"] + summ["ends_only"] + summ["ends_won"],
        "by_clothes": summ["agree"] + summ["clothes_only"] + summ["clothes_won"],
        "conflicts": summ["doubtful"], "conflicts_resolved": summ["ends_won"] + summ["clothes_won"],
        "decided": sum(p["near_is_target"] is not None for p in per),
        "clothes": {"source": source, "runs": int((labels >= 0).sum()), "clear": int((clear >= weak).sum()),
                    "margin_median": round(float(np.median(clear)), 2) if len(clear) else None,
                    "separation": sp["separation"], "far_pairs": len(links), "far_opposite": sp["links_ok"],
                    "same_game_pairs": len(same), "same_game_same": round(float(np.mean(same)), 2) if same else None}})
    return per, summ
