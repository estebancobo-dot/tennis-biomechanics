"""Court values whose physical limit the fine pass does not apply when it measures them: the base width at contact
(court_metrics keeps any width over MIN_STANCE_WIDTH_M). 28-11 (informe_6, the cloud audit of the 6 matches): a foot
point misplaced by the court homography gave one of 426 forehands a base wider than 2.5 m.

Read-side only, like face_evidence (R50): strokes.json is never rewritten and nothing is recomputed. The limit inside
the fine pass (tennisbio.limits) would change its code fingerprint and redo the fine pass of every analysed match for
one value. A value outside its limit is not shown (nothing invented), nor the stance made from the same feet.
"""
from __future__ import annotations

READ_LIMITS = {"stance_width_m": (0.1, 2.5)}            # metres between the feet on the court
# what comes from the same measurement and goes with it
WITH = {"stance_width_m": ("stance", "stance_angle_deg")}


def hide_impossible(stroke: dict) -> list[str]:
    """Sets to None, in place, the values of `stroke` outside READ_LIMITS (and what goes with them); returns their
    names."""
    dropped = []
    for k, (lo, hi) in READ_LIMITS.items():
        v = stroke.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and not lo <= v <= hi:
            stroke[k] = None
            for w in WITH.get(k, ()):
                if w in stroke:
                    stroke[w] = None
            dropped.append(k)
    return dropped
