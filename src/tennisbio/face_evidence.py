"""R50 on strokes already analysed (15-11, the Base in beta with the matches of these days): the racket face is a
number only where its phase had the 3D hand as evidence; elsewhere it becomes «not measurable from TV», the same as
the fine pass now does (tennisbio.racket_orientation.hand_near, stricter here: the phase's own frame, since the
neighbouring frames' evidence was not kept). Read-side only: strokes.json is never rewritten, nothing is recomputed.
"""
from __future__ import annotations

NO_HAND = "sin la mano en 3D: la cara no es medible desde la tele"
FACE_KEYS = ("face_tilt", "face_yaw", "face_points_to", "face_observed")


def unreliable_phases(stroke: dict) -> set[str]:
    """Phases whose face was given without 3D hand evidence at their frame (and not already marked by the fix)."""
    out = set()
    for phase, f in (stroke.get("face") or {}).items():
        if isinstance(f, dict) and f.get("hand_evidence") is not True and not f.get("no_medible"):
            out.add(phase)
    return out


def hide_unreliable_faces(stroke: dict) -> int:
    """Removes, in place, the face values of the phases without 3D hand evidence (the stroke's face summary, its
    technique phase values and their jitter); returns how many phases it hid."""
    bad = unreliable_phases(stroke)
    for phase in bad:
        f = stroke["face"][phase]
        f.update(points_to=None, tilt_deg=None, yaw_deg=None, no_medible=NO_HAND)
        tp = ((stroke.get("technique") or {}).get("phases") or {}).get(phase)
        if isinstance(tp, dict):
            for k in FACE_KEYS:
                tp.pop(k, None)
        jit = (stroke.get("technique") or {}).get("jitter")
        if isinstance(jit, dict):
            for k in FACE_KEYS:
                jit.pop(f"{phase}.{k}", None)
    return len(bad)
