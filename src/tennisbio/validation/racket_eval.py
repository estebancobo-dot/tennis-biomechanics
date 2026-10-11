"""Compare racket estimates with RacketVision ground-truth keypoints."""
from dataclasses import asdict, dataclass

import numpy as np

from ..racket import racket_from_polygon

TIP, THROAT, BUTT, SIDE_A, SIDE_B = range(5)


@dataclass
class RacketMatch:
    length_px: float              # ground-truth butt→tip length
    detected: bool
    axis_err_deg: float | None    # undirected axis error (0-90)
    head_correct: bool | None     # head/handle ends identified the right way round
    elevation_err_deg: float | None
    head_err_rel: float | None    # head-centre error / racket length


HEAD_FRACTION = 0.56   # tip→throat / tip→butt, median over RacketVision tennis annotations


def gt_geometry(kps: np.ndarray):
    """(butt, head centre, length, elevation) from annotated keypoints, or None if unusable.

    Invisible keypoints come as (0, 0) with visibility 0; the butt is hidden in about half of
    the annotations (inside the hand), so the axis uses throat→tip and the butt is extrapolated.
    """
    k = np.asarray(kps, float)
    vis = (k[:, 2] > 0) & ~(k[:, :2] == 0).all(1)
    if not (vis[TIP] and vis[THROAT]):
        return None
    tip, throat = k[TIP, :2], k[THROAT, :2]
    head = (tip + throat) / 2
    length = float(np.linalg.norm(tip - throat)) / HEAD_FRACTION
    butt = k[BUTT, :2] if vis[BUTT] else tip + (throat - tip) / HEAD_FRACTION
    d = tip - throat
    return butt, head, length, float(np.degrees(np.arctan2(-d[1], abs(d[0]))))


def box_iou(a, b):
    """IoU of two xyxy boxes."""
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter + 1e-9)


def match_racket(gt_kps, gt_bbox_xywh, polys: list, wrists: np.ndarray) -> RacketMatch | None:
    """Evaluate the best-overlapping predicted outline against one annotated racket.

    wrists: (N, 2) wrist positions of all detected people; the one closest to the true butt is
    used to orient the racket, as the pipeline would with the tracked player's wrist.
    Returns None when the annotation lacks the tip or throat.
    """
    geo = gt_geometry(gt_kps)
    if geo is None:
        return None
    butt, head, length, elev = geo
    x, y, w, h = gt_bbox_xywh
    gb = [x, y, x + w, y + h]
    best, best_iou = None, 0.05
    for p in polys:
        if len(p) < 3:
            continue
        pb = [*p.min(0), *p.max(0)]
        v = box_iou(gb, pb)
        if v > best_iou:
            best, best_iou = p, v
    if best is None:
        return RacketMatch(length, False, None, None, None, None)
    wrist = None
    if len(wrists):
        d = np.linalg.norm(wrists - butt, axis=1)
        if d.min() < 1.5 * length:
            wrist = wrists[int(np.argmin(d))]
    if wrist is None:                     # no usable wrist: orient by the end nearer the true butt's side
        wrist = butt + (butt - head) * 0.3
    obs = racket_from_polygon(best, wrist)
    if obs is None:
        return RacketMatch(length, False, None, None, None, None)
    gd, pd = head - butt, obs.head - obs.butt
    ang = abs(np.degrees(np.arctan2(gd[1], gd[0]) - np.arctan2(pd[1], pd[0]))) % 360
    ang = min(ang, 360 - ang)
    return RacketMatch(
        length_px=length, detected=True, axis_err_deg=float(min(ang, 180 - ang)), head_correct=bool(ang < 90),
        elevation_err_deg=float(obs.elevation_deg - elev),
        head_err_rel=float(np.linalg.norm(obs.head - head) / length))


def summarize(matches: list[RacketMatch], min_len=0.0) -> dict:
    m = [x for x in matches if x.length_px >= min_len]
    det = [x for x in m if x.detected]
    q = lambda vals, p: None if not vals else round(float(np.percentile(vals, p)), 2)
    ax = [x.axis_err_deg for x in det]
    el = [abs(x.elevation_err_deg) for x in det if x.head_correct]
    he = [x.head_err_rel for x in det if x.head_correct]
    return dict(
        rackets=len(m), detected=len(det), recall=round(len(det) / max(1, len(m)), 3),
        axis_err_deg_median=q(ax, 50), axis_err_deg_p90=q(ax, 90),
        axis_within_15deg=round(float(np.mean(np.array(ax) <= 15)), 3) if ax else None,
        head_end_correct=round(float(np.mean([x.head_correct for x in det])), 3) if det else None,
        elevation_err_deg_median=q(el, 50), head_err_rel_median=q(he, 50),
    )


def to_rows(matches):
    return [asdict(x) for x in matches]
