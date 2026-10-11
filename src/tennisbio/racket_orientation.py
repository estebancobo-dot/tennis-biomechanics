"""Strings orientation through one stroke, for the match pipeline (fine pass).

Combines the racket keypoints (RacketVision RTMPose, racket_pose), the outline as a fallback, the
optional 3D hand/forearm (RTMW3D) and the camera pitch from the court homography; the 3D solver
is tennisbio.racket_face.face_track.
"""
from pathlib import Path

import cv2
import numpy as np

from .racket import pick_racket
from .racket3d import Camera
from .racket_face import face_track


def read_frames(video: Path, a: int, b: int) -> dict:
    cap = cv2.VideoCapture(str(video))
    cap.set(cv2.CAP_PROP_POS_FRAMES, a)
    out = {}
    for f in range(a, b):
        ok, fr = cap.read()
        if not ok:
            break
        out[f] = fr
    cap.release()
    return out


def stroke_faces(video: Path, run, stroke, height_m: float, pitch_deg: float | None = None, rpose=None,
                 wb3d=None, hand3d_step: int = 2, grip_close_deg: float = 15.0, window=(1.0, 0.8)) -> dict:
    """{"phases": {phase: face summary}, "frames": [first, ...per-frame tilt/yaw/label/observed]}."""
    fps, i = run.fps, stroke.impact_frame
    a = max(0, i - int(round(window[0] * fps)))
    b = min(len(run.img), i + int(round(window[1] * fps)) + 1)
    frames = read_frames(video, a, b)
    sk, wrist_k = run.sk, run.sk["dom_wrist"]
    rkps = {}
    if rpose is not None:
        for f, fr in frames.items():
            polys = run.rackets[f] if f < len(run.rackets) else None
            poly = pick_racket(polys, run.img[f, wrist_k], 0.3 * run.height_px) if polys is not None else None
            if poly is not None:
                rkps[f] = rpose(fr, [[*poly.min(0), *poly.max(0)]])[0][0]
    hand_frames = {f: fr for f, fr in frames.items() if (f - a) % max(1, hand3d_step) == 0} if wb3d is not None else {}
    track = face_track(hand_frames, run.boxes, run.img, run.rackets, sk, run.height_px, height_m, i, a, b,
                       wb3d, Camera(pitch_deg if pitch_deg is not None else 20.0), grip_close_deg, fps=fps,
                       racket_kps=rkps if rpose is not None else None)
    by_f = {t["frame"]: t for t in track}
    phases = {}
    for name, p in stroke.phases.items():
        t = by_f.get(p.get("frame"))
        if t is None or t.get("face") is None:
            phases[name] = None
            continue
        phases[name] = {k: t[k] for k in ("points_to", "tilt_deg", "yaw_deg", "observed", "hand_evidence", "ambiguous")}
    per = [by_f.get(f) or {} for f in range(a, b)]
    return {
        "phases": phases,
        "first": a,
        "tilt": [t.get("tilt_deg") for t in per],
        "yaw": [t.get("yaw_deg") for t in per],
        "label": [t.get("points_to") for t in per],
        "observed": [bool(t.get("observed")) for t in per],
        "keypoints": {str(f): np.round(k, 1).tolist() for f, k in rkps.items()},
        "source": "5 puntos" if rpose is not None else "silueta",
        "hand3d": wb3d is not None,
    }
