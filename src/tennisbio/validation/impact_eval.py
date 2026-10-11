"""Compare detected strokes with F3Set-Tennis ground truth (frame-exact contacts).

F3Set labels look like "near_deuce_stroke_fh_gs_CC_-_in":
side (near/far) · court position · shot (serve/return/stroke) · hand (fh/bh/-) · technique
(gs = groundstroke, slice, volley, smash, drop, lob) · direction · approach · outcome.
"""
from dataclasses import dataclass

import numpy as np


@dataclass
class GTEvent:
    frame: int
    side: str        # near / far
    shot: str        # serve / return / stroke
    hand: str        # fh / bh / -
    technique: str   # gs / slice / volley / smash / drop / lob / -


def parse_label(frame: int, label: str) -> GTEvent:
    p = label.split("_")
    return GTEvent(frame=int(frame), side=p[0], shot=p[2], hand=p[3], technique=p[4])


def clip_bounds(video_field: str) -> tuple[str, int, int]:
    """'<video name>_<start>_<end>' -> (video name, start frame, end frame) in the full video."""
    name, a, b = video_field.rsplit("_", 2)
    return name, int(a), int(b)


@dataclass
class Pred:
    frame: int
    hand: str        # fh / bh


def match(preds: list[Pred], gts: list[GTEvent], tol: int) -> tuple[list, list, list]:
    """Greedy one-to-one matching by time within ±tol frames.

    Returns (pairs [(pred, gt)], unmatched preds, unmatched gts)."""
    pairs, used = [], set()
    for p in sorted(preds, key=lambda x: x.frame):
        cands = [(abs(g.frame - p.frame), k) for k, g in enumerate(gts) if k not in used and abs(g.frame - p.frame) <= tol]
        if cands:
            _, k = min(cands)
            used.add(k)
            pairs.append((p, gts[k]))
    fp = [p for p in preds if all(p is not q for q, _ in pairs)]
    fn = [g for k, g in enumerate(gts) if k not in used]
    return pairs, fp, fn


def summarize(pairs, fp, fn, fps_list=None) -> dict:
    tp = len(pairs)
    prec = tp / max(1, tp + len(fp))
    rec = tp / max(1, tp + len(fn))
    dt = np.array([p.frame - g.frame for p, g in pairs], float)
    hand_pairs = [(p, g) for p, g in pairs if g.hand in ("fh", "bh")]
    out = dict(
        gt=tp + len(fn), detected=tp + len(fp), true_positives=tp,
        precision=round(prec, 3), recall=round(rec, 3), f1=round(2 * prec * rec / max(1e-9, prec + rec), 3),
        timing_err_frames_median=None if not tp else round(float(np.median(np.abs(dt))), 2),
        timing_bias_frames=None if not tp else round(float(np.mean(dt)), 2),
        fh_bh_accuracy=None if not hand_pairs else round(float(np.mean([p.hand == g.hand for p, g in hand_pairs])), 3),
    )
    by_tech = {}
    for g in [g for _, g in pairs] + fn:
        by_tech.setdefault(g.technique, [0, 0])
        by_tech[g.technique][1] += 1
    for _, g in pairs:
        by_tech[g.technique][0] += 1
    out["recall_by_technique"] = {k: f"{a}/{b}" for k, (a, b) in sorted(by_tech.items())}
    return out
