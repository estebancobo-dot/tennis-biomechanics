"""How much of each measure the camera explains (docs/analisis_referencias.md §2, B-15a; the rule of
deep-sports-analysis, MIT, measure/profiles.py: a measure whose stroke-to-stroke spread the camera explains by
10 % or more is not her technique but the picture).

Per stroke, the camera from the court homography of its window (series "H": the player's court in metres →
image px): zoom (near baseline width), angle (far over near baseline width), tilt, where the near baseline sits,
plus her height in px and the camera pitch. Per measure: the share of its within-match spread that these explain
(least squares with one level per match, the camera centred within each match, so a match filmed differently
does not count as camera), against chance: the same with the cameras shuffled within each match (95th
percentile of `shuffles` draws). A measure is camera-dependent when its share is at least `limit` and the
camera's part is significant after correcting for the hundreds of measures tested at once (partial F test,
Benjamini-Hochberg at FDR 5 %: with 479 measures one in twenty would pass a plain 95 % chance line by luck);
with few matches of one tournament the test is weak, and the verdict says so.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import f as f_dist

CAMERA = ("zoom", "angle", "tilt", "baseline_y", "height_px", "pitch")
LIMIT = 0.10
FDR = 0.05
MIN_STROKES = 40
# identifiers, times of the match and phase frames: not measures of her technique
NOT_MEASURES = ("match_time_s", "window_start_s", "window_impact_s", "impact_frame", "shot_in_point",
                "shots_in_point", "camera_pitch_deg", "series", "window")
NOT_PREFIX = ("phase.", "tphase.", "class.", "curves.")


def camera_of(H, height_px=None, pitch=None) -> dict | None:
    """The camera of one stroke from its homography (player's court metres → image px), or None."""
    try:
        H = np.asarray(H, float).reshape(3, 3)

        def img(x, y):
            p = H @ np.array([x, y, 1.0])
            return p[:2] / p[2]
        nl, nr, fl, fr = img(-5.485, 0.0), img(5.485, 0.0), img(-5.485, 23.77), img(5.485, 23.77)
    except (TypeError, ValueError):
        return None
    nw, fw = float(np.linalg.norm(nr - nl)), float(np.linalg.norm(fr - fl))
    if not np.isfinite([nw, fw]).all() or nw <= 0:
        return None
    return {"zoom": nw, "angle": fw / nw, "tilt": float((nl[1] + nr[1]) - (fl[1] + fr[1])) / 2 / nw,
            "baseline_y": float(nl[1] + nr[1]) / 2,
            "height_px": float(height_px) if height_px is not None else np.nan,
            "pitch": float(pitch) if pitch is not None else np.nan}


def is_measure(key: str, v) -> bool:
    return (isinstance(v, (int, float)) and not isinstance(v, bool) and np.isfinite(v)
            and key not in NOT_MEASURES and not key.startswith(NOT_PREFIX))


def _resid(y: np.ndarray, X: np.ndarray) -> np.ndarray:
    return y - X @ np.linalg.lstsq(X, y, rcond=None)[0]


def shares(rows: list[tuple[str, dict, dict]], limit: float = LIMIT, min_strokes: int = MIN_STROKES,
           shuffles: int = 200, seed: int = 0) -> list[dict]:
    """rows: (match id, camera dict, {measure: value}). One entry per measure with enough strokes:
    {measure, n, matches, share, chance, camera_dependent}, the most camera-dependent first."""
    rng = np.random.default_rng(seed)
    names = sorted({k for _, _, m in rows for k, v in m.items() if is_measure(k, v)})
    out = []
    for k in names:
        sel = [(mid, cam, m[k]) for mid, cam, m in rows
               if is_measure(k, m.get(k)) and cam and all(np.isfinite(cam.get(c, np.nan)) for c in CAMERA)]
        if len(sel) < min_strokes:
            continue
        y = np.array([v for _, _, v in sel], float)
        mids = sorted({mid for mid, _, _ in sel})
        G = np.array([[mid == x for x in mids] for mid, _, _ in sel], float)
        C = np.array([[cam[c] for c in CAMERA] for _, cam, _ in sel], float)
        groups = [np.flatnonzero(G[:, j] > 0) for j in range(len(mids))]
        for i in groups:
            C[i] -= C[i].mean(0)
        sd = C.std(0)
        C = C[:, sd > 1e-12] / sd[sd > 1e-12]
        r0 = _resid(y, G)
        base = float(r0 @ r0)
        if base <= 0 or not C.shape[1]:
            continue
        share = 1 - float(_resid(y, np.column_stack([G, C])) @ _resid(y, np.column_stack([G, C]))) / base
        null = []
        for _ in range(shuffles):
            Cp = C.copy()
            for i in groups:
                Cp[i] = C[rng.permutation(i)]
            r = _resid(y, np.column_stack([G, Cp]))
            null.append(1 - float(r @ r) / base)
        chance = float(np.percentile(null, 95)) if null else 0.0
        q, dof = C.shape[1], len(y) - G.shape[1] - C.shape[1]
        p = float(f_dist.sf((share / q) / ((1 - share) / dof), q, dof)) if dof > 0 and share < 1 else 0.0
        out.append({"measure": k, "n": len(sel), "matches": len(mids), "share": round(share, 4),
                    "chance": round(chance, 4), "p": p})
    # Benjamini-Hochberg over all the measures tested
    order = sorted(range(len(out)), key=lambda i: out[i]["p"])
    passed, m = set(), len(out)
    for rank, i in enumerate(order, 1):
        if out[i]["p"] <= FDR * rank / m:
            passed = set(order[:rank])
    for i, e in enumerate(out):
        e["camera_dependent"] = bool(i in passed and e["share"] >= limit and e["share"] > e["chance"])
    return sorted(out, key=lambda e: -e["share"])
