"""Validation of «pausa arriba» (technique.loaded_pause): references and synthetic checks.

Reference: the racket head (silhouette, or the hand-annotated RacketVision keypoints), relative to
her hips and in body heights, must be (almost) still for the hand's pause to be a real pause.
A continuous loop moves the head even when the hand moves little.
"""
import numpy as np

from ..technique import LOOP_PAUSE_S, loaded_pause

# a pause = the racket head stays inside a disc this wide (body heights, ≈ 13 cm for a 1.84 m
# player): about 3× the frame-to-frame scatter of the silhouette's head centre (7 % of the racket
# length, docs/validacion.md); a continuous loop at ≥ 1 body height / s leaves it in < 0.07 s.
HEAD_STILL_D = 0.07


def _rel(p: np.ndarray, hips: np.ndarray, scale: np.ndarray) -> np.ndarray:
    return (p - hips) / scale[:, None]


def dwell(pos: np.ndarray, fps: float, centre: int, lo: int, hi: int, diameter: float, near: int,
          min_seen: float = 0.6) -> float | None:
    """Seconds of the longest stretch [i, j] inside [lo, hi) where every seen point of `pos` (T, 2)
    lies within `diameter` of every other, that reaches within `near` frames of `centre`
    (0 = no stretch longer than one frame). None when `pos` is mostly unseen there."""
    lo, hi = max(0, lo), min(len(pos), hi)
    ok = np.isfinite(pos).all(1)
    if hi - lo < 2 or ok[lo:hi].mean() < min_seen:
        return None
    best = 0
    for i in range(lo, hi):
        if not ok[i] or i > centre + near:
            continue
        pts = [pos[i]]
        last = i
        for j in range(i + 1, hi):
            if ok[j]:
                if max(np.linalg.norm(q - pos[j]) for q in pts) > diameter:
                    break
                pts.append(pos[j])
                last = j
        if last >= centre - near and ok[i:last + 1].mean() >= min_seen:
            best = max(best, last - i)
    return best / fps


def ref_pause(row: dict, diameter: float = HEAD_STILL_D) -> float | None:
    """Seconds the racket head (silhouette, relative to the hips) stays still around the end of the
    backswing: [loaded − 0.4 s, impact − 0.1 s], reaching within 0.1 s of it."""
    fps, ld, imp = row["fps"], row["phases"]["loaded"], row["impact"]
    s = lambda t: int(round(t * fps))
    rel = _rel(row["head"], row["hips"], row["scale"])
    # at 50-60 fps the racket is segmented one frame in two (clip_pipeline.run_clip): read those only
    seen = np.flatnonzero(np.isfinite(rel).all(1))
    par = np.bincount(seen % 2, minlength=2) if len(seen) else np.zeros(2)
    k = 2 if fps >= 40 and par.max() >= 0.9 * len(seen) else 1
    o = int(np.argmax(par)) if k == 2 else 0
    q = lambda f: (f - o) // k
    return dwell(rel[o::k], fps / k, q(ld), q(ld - s(0.4)), q(imp - s(0.1)), diameter, max(1, s(0.1) // k))


def annot_min_speed(row: dict) -> float | None:
    """Slowest hand-annotated racket-head movement (body heights / s) between consecutive annotated
    frames (≤ 0.25 s apart) around the end of the backswing: [loaded − 0.3 s, loaded + 0.2 s]."""
    fps, ld = row["fps"], row["phases"]["loaded"]
    fr = sorted(f for f in row["annot"] if ld - 0.3 * fps <= f <= ld + 0.2 * fps)
    best = None
    for a, b in zip(fr[:-1], fr[1:]):
        if (b - a) / fps > 0.25:
            continue
        ha = (row["annot"][a][0] + row["annot"][a][1]) / 2           # tip–throat midpoint: head centre
        hb = (row["annot"][b][0] + row["annot"][b][1]) / 2
        if not (np.isfinite(row["hips"][[a, b]]).all()):
            continue
        d = np.linalg.norm(_rel(hb[None], row["hips"][b][None], row["scale"][[b]]) -
                           _rel(ha[None], row["hips"][a][None], row["scale"][[a]]))
        sp = float(d / ((b - a) / fps))
        best = sp if best is None else min(best, sp)
    return best


def measure(row: dict, fn=loaded_pause, step: int = 1) -> float | None:
    """The measure on this stroke; step=2 subsamples the pose to half the frame rate (50 → 25 fps)."""
    ph = row["phases"]
    dw = row["dw"][::step]
    q = lambda f: None if f is None else int(round(f / step))
    return fn(dw, row["fps"] / step, q(ph["loaded"]), q(ph.get("takeback")), q(row["impact"]))


def loaded_pause_v1(dw: np.ndarray, fps: float, loaded: int, takeback: int | None, impact: int) -> float | None:
    """The former measure (until 18-10), kept to report «antes / ahora": still = under 30 % of the
    wrist's peak speed from the end of the backswing to contact, walking out from that end."""
    from ..kinematics import smooth, speed
    wv = smooth(speed(dw, fps), fps, 0.06)
    if not np.isfinite(wv[loaded:impact + 1]).any():
        return None
    thr = 0.3 * np.nanmax(wv[loaded:impact + 1])
    a = b = loaded
    lo_p = takeback if takeback is not None else max(0, loaded - int(0.4 * fps))
    while a - 1 >= lo_p and np.isfinite(wv[a - 1]) and wv[a - 1] < thr:
        a -= 1
    while b + 1 < impact and np.isfinite(wv[b + 1]) and wv[b + 1] < thr:
        b += 1
    if a > lo_p or takeback is not None:
        return round((b - a + 1) / fps, 3)
    return None


def _agree(pairs):
    tp = sum(m and r for m, r in pairs)
    fn_ = sum(r and not m for m, r in pairs)
    fp = sum(m and not r for m, r in pairs)
    tn = sum(not m and not r for m, r in pairs)
    return dict(n=len(pairs), ref_yes=tp + fn_, measure_yes=tp + fp, tp=tp, fn=fn_, fp=fp, tn=tn,
                sensitivity=round(tp / (tp + fn_), 2) if tp + fn_ else None,
                specificity=round(tn / (tn + fp), 2) if tn + fp else None)


def _rank_corr(x, y) -> float | None:
    if len(x) < 4:
        return None
    rx, ry = np.argsort(np.argsort(x)), np.argsort(np.argsort(y))
    return round(float(np.corrcoef(rx, ry)[0, 1]), 2)


def evaluate(strokes: list[dict], fn=loaded_pause) -> dict:
    """Agreement of the measure with the racket references on real strokes, and its change when the
    pose is read at half the frame rate (50-60 → 25-30 fps)."""
    rows, pairs, pairs_a, m_, r_, d25 = [], [], [], [], [], []
    for r in strokes:
        m = measure(r, fn)
        if m is None:
            continue
        ref = ref_pause(r)
        am = annot_min_speed(r)
        m25 = measure(r, fn, 2) if r["fps"] >= 45 else None
        rows.append(dict(clip=r["clip"], impact=r["impact"], fps=r["fps"], stroke=r["stroke"], pause=m, ref=ref,
                         annot_min_speed=None if am is None else round(am, 2), pause_half_fps=m25))
        if ref is not None:
            pairs.append((m >= LOOP_PAUSE_S, ref >= LOOP_PAUSE_S))
            m_.append(m)
            r_.append(ref)
        if am is not None:
            pairs_a.append((m >= LOOP_PAUSE_S, am * LOOP_PAUSE_S < HEAD_STILL_D))
        if m25 is not None:
            d25.append(m25 - m)
    pz = np.array([x["pause"] for x in rows]) if rows else np.zeros(0)
    e = np.asarray(m_) - np.asarray(r_)
    return dict(
        strokes=len(rows),
        pause_median_s=round(float(np.median(pz)), 3) if len(pz) else None,
        share_flagged=round(float(np.mean(pz >= LOOP_PAUSE_S)), 2) if len(pz) else None,
        vs_racket=_agree(pairs),
        err_median_s=round(float(np.median(e)), 3) if len(e) else None,
        err_abs_median_s=round(float(np.median(np.abs(e))), 3) if len(e) else None,
        rank_corr=_rank_corr(m_, r_),
        vs_annotations=_agree(pairs_a),
        half_fps_abs_diff_median_s=round(float(np.median(np.abs(d25))), 3) if d25 else None,
        half_fps_abs_diff_max_s=round(float(np.max(np.abs(d25))), 3) if d25 else None,
        rows=rows)


def injected(strokes: list[dict], fn=loaded_pause, pause_s: float = 0.2) -> dict:
    """A known stop of the hand put into each real stroke: the wrist held at the end of the backswing
    for pause_s (frames inserted; the end of the backswing and contact keep their places). The
    measure must grow by pause_s (± 40 ms)."""
    errs = []
    for r in strokes:
        ph, fps = r["phases"], r["fps"]
        m0 = measure(r, fn)
        if m0 is None:
            continue
        k = int(round(pause_s * fps))
        ld = ph["loaded"]
        dw = np.insert(r["dw"], ld, np.repeat(r["dw"][ld][None], k, 0), axis=0)
        tb = ph.get("takeback")
        m1 = fn(dw, fps, ld + k // 2, tb, r["impact"] + k)
        if m1 is not None:
            errs.append(m1 - m0 - k / fps)
    e = np.asarray(errs)
    return dict(n=len(e), err_median_s=round(float(np.median(e)), 3) if len(e) else None,
                within_40ms=round(float(np.mean(np.abs(e) <= 0.04 + 1e-9)), 2) if len(e) else None)


# ---------------------------------------------------------------- synthetic strokes
def synth_wrist(fps: float, pause_s: float = 0.0, loop_speed: float = 0.0, seed: int | None = 0,
                noise: float = 0.0) -> tuple[np.ndarray, int, int, int]:
    """Dominant wrist (body frame, body heights) of a forehand: wait, backswing (speed hump),
    top of the backswing (a stop of `pause_s`, or a continuous loop at `loop_speed` body heights/s
    lasting 0.2 s), forward swing (peak ≈ 6 body heights/s) and finish.
    Returns (dw (T, 2), takeback, true end of the backswing (start of the stop), impact)."""
    rng = np.random.default_rng(seed)
    dt = 1 / fps
    pts = [np.array([0.25, 0.0])]
    vel = []
    def go(v, dur):
        for _ in range(max(1, int(round(dur * fps)))):
            vel.append(np.asarray(v, float))
    go([0, 0], 0.3)                                  # waiting
    tb = len(vel)
    for k in range(int(round(0.35 * fps))):         # backswing: back and up, speed hump ≈ 1.6 h/s
        u = np.sin(np.pi * (k + 0.5) / (0.35 * fps))
        vel.append(1.6 * u * np.array([0.8, 0.6]))
    top = len(vel)
    if pause_s > 0:
        go([0, 0], pause_s)
    if loop_speed > 0:                               # continuous loop at the top: a half circle
        n = int(round(0.2 * fps))
        for k in range(n):
            a = np.pi * (k + 0.5) / n
            vel.append(loop_speed * np.array([np.cos(a), -np.sin(a)]))
    for k in range(int(round(0.25 * fps))):         # forward swing: drop then up, peak ≈ 6 h/s
        u = np.sin(np.pi * (k + 0.5) / (0.25 * fps)) ** 2
        vel.append(6.0 * u * np.array([-0.9, 0.3]))
    imp = len(vel) - int(round(0.06 * fps))
    go([-1.0, 1.5], 0.15)
    go([0, 0], 0.3)
    p = np.cumsum(np.vstack([pts[0], np.array(vel) * dt]), axis=0)
    if noise:
        p = p + rng.normal(0, noise, p.shape)
    return p, tb, top, imp


def _loaded_from(dw: np.ndarray, fps: float, impact: int) -> int | None:
    """The end of the backswing as the pipeline finds it (phases.detect_phases rule, wrist only)."""
    from ..phases import _argext, _smooth, _walk_down
    from ..kinematics import speed
    s = lambda t: int(round(t * fps))
    wv = _smooth(speed(dw, fps), max(1, s(0.06)))
    fwd = _argext(wv, impact - s(0.25), impact + 2, np.nanargmax)
    lo = max(0, impact - s(0.8))
    hi = max(lo + 1, min(fwd, impact - max(2, s(0.1))))
    slow = np.flatnonzero(wv[lo:hi] <= 0.35 * wv[fwd])
    return _walk_down(wv, lo + int(slow[-1]), lo) if len(slow) else _walk_down(wv, hi, lo)


def synthetic(fn=loaded_pause, fps_list=(25, 50), noise_list=(0.0, 0.004, 0.008), seeds=range(5)) -> dict:
    """Known pauses (0.08-0.4 s), no pause and slow continuous loops, at 25 and 50 fps, with the
    end of the backswing found as the pipeline finds it."""
    out = {}
    for fps in fps_list:
        for noise in noise_list:
            errs, none_, loops = [], [], []
            for seed in seeds:
                for p in (0.08, 0.12, 0.16, 0.2, 0.3, 0.4):
                    dw, tb, top, imp = synth_wrist(fps, pause_s=p, seed=seed, noise=noise)
                    ld = _loaded_from(dw, fps, imp)
                    m = fn(dw, fps, ld, tb, imp) if ld is not None else None
                    errs.append(np.nan if m is None else (m - p) * fps)
                dw, tb, top, imp = synth_wrist(fps, seed=seed, noise=noise)
                ld = _loaded_from(dw, fps, imp)
                none_.append(fn(dw, fps, ld, tb, imp) if ld is not None else None)
                for ls in (0.6, 1.0, 1.5):
                    dw, tb, top, imp = synth_wrist(fps, loop_speed=ls, seed=seed, noise=noise)
                    ld = _loaded_from(dw, fps, imp)
                    loops.append(fn(dw, fps, ld, tb, imp) if ld is not None else None)
            e = np.asarray(errs, float)
            out[f"{fps}fps_noise{noise}"] = dict(
                pause_err_frames_median=round(float(np.nanmedian(e)), 2),
                pause_within_1_frame=round(float(np.mean(np.abs(e) <= 1)), 2),
                pause_within_40ms=round(float(np.mean(np.abs(e) / fps <= 0.04 + 1e-9)), 2),
                no_pause_max_s=max((x or 0) for x in none_),
                loop_flagged=round(float(np.mean([(x or 0) >= LOOP_PAUSE_S for x in loops])), 2),
                loop_max_s=max((x or 0) for x in loops))
    return out
