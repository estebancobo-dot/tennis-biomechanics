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
    direction: str = "-"     # CC cross, DL down the line, DM middle, IO inside-out, II inside-in
    approach: bool = False
    outcome: str = "-"       # in / winner / forced-err / unforced-err
    position: str = "-"      # deuce / middle / ad


def parse_label(frame: int, label: str) -> GTEvent:
    p = label.split("_")
    return GTEvent(frame=int(frame), side=p[0], shot=p[2], hand=p[3], technique=p[4],
                   direction=p[5] if len(p) > 5 else "-", approach=len(p) > 6 and p[6] == "approach",
                   outcome=p[7] if len(p) > 7 else "-", position=p[1])


def clip_bounds(video_field: str) -> tuple[str, int, int]:
    """'<video name>_<start>_<end>' -> (video name, start frame, end frame) in the full video."""
    name, a, b = video_field.rsplit("_", 2)
    return name, int(a), int(b)


@dataclass
class Pred:
    frame: int
    hand: str        # fh / bh
    direction: str = "-"     # same codes as GTEvent (from where her ball bounced)
    approach: bool | None = None
    error: bool | None = None  # her ball out (None: unknown)


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
    # direction of her shot (where it bounced): accuracy over matched strokes with both labels
    dp = [(p.direction, g.direction) for p, g in pairs if p.direction != "-" and g.direction not in ("-", "")]
    out["direction_n"] = len(dp)
    out["direction_accuracy"] = None if not dp else round(float(np.mean([a == b for a, b in dp])), 3)
    out["direction_confusion"] = {f"{b}->{a}": sum(1 for x, y in dp if x == a and y == b) for b in ("CC", "DL", "DM", "IO", "II")
                                  for a in ("CC", "DL", "DM", "IO", "II") if any(x == a and y == b for x, y in dp)}
    ap = [(p.approach, g.approach) for p, g in pairs if p.approach is not None]
    out["approach_accuracy"] = None if not ap else round(float(np.mean([a == b for a, b in ap])), 3)
    ep = [(p.error, g.outcome in ("forced-err", "unforced-err")) for p, g in pairs if p.error is not None and g.outcome != "-"]
    if ep:
        tp_e = sum(1 for a, b in ep if a and b)
        out["error_precision"] = round(tp_e / max(1, sum(1 for a, _ in ep if a)), 3)
        out["error_recall"] = round(tp_e / max(1, sum(1 for _, b in ep if b)), 3)
    return out
