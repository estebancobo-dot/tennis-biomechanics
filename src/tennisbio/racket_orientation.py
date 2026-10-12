"""Strings orientation through one stroke, for the match pipeline (fine pass).

Combines the racket keypoints (RacketVision RTMPose, racket_pose), the outline as a fallback, the
optional 3D hand/forearm (RTMW3D) and the camera pitch from the court homography; the 3D solver
is tennisbio.racket_face.face_track.
"""
from pathlib import Path

import cv2

import numpy as np

from .io.video import open_capture
from .racket import pick_racket
from .racket3d import Camera
from .racket_face import face_track

L_SH, R_SH, L_HIP, R_HIP = 5, 6, 11, 12          # COCO-WholeBody indices (RTMW3D)


class _Recorder:
    """Wraps the 3D whole-body model to keep its outputs (reused for 3D trunk rotation)."""

    def __init__(self, model, frames: dict):
        self.model, self.by_id, self.out = model, {id(fr): f for f, fr in frames.items()}, {}

    def __call__(self, frame, box):
        res = self.model(frame, box)
        self.out[self.by_id.get(id(frame))] = res
        return res


def trunk_rotation_3d(k3: np.ndarray, sc: np.ndarray, cam: Camera, hand="right", min_score=0.4, height_m: float = 1.8):
    """(shoulder turn, hip turn) in degrees about the vertical, from RTMW3D keypoints.

    0 = line square to the net; + = dominant shoulder/hip turned back (towards the camera), as in
    the backswing of a forehand. Same world frame as the racket solver (Camera basis)."""
    if min(sc[[L_SH, R_SH, L_HIP, R_HIP]]) < min_score:
        return None
    r, u, f = cam.basis
    px_per_m = (max(k3[15, 1], k3[16, 1]) - k3[0, 1]) / (0.93 * height_m)        # her own height, not a 1.8 m person
    if px_per_m <= 0:
        return None
    to_w = lambda p: (p[0] / px_per_m) * r - (p[1] / px_per_m) * u + p[2] * f
    dom = 1 if hand == "right" else -1
    out = []
    for a, b in ((L_SH, R_SH), (L_HIP, R_HIP)):
        d = to_w(k3[b]) - to_w(k3[a])                     # left → right in world (x right, y to the net)
        out.append(float(-dom * np.degrees(np.arctan2(d[1], d[0] * dom))))
    return tuple(out)


def _fold(a: float) -> float:
    """A line has no direction: fold to (-90, 90]."""
    return (a + 90.0) % 180.0 - 90.0


def trunk_at(rot: dict, frame: int | None, half_window: int, max_xf=80.0, max_mad=15.0) -> dict:
    """Shoulder/hip turn and X-factor around one frame from the monocular 3D readings within
    ±half_window: median, and only when the readings agree (median absolute deviation of both
    turns ≤ max_mad); monocular depth from behind is unstable, so disagreement means no value."""
    if frame is None:
        return {}
    vals = np.array([(_fold(sh), _fold(hp)) for f, (sh, hp) in rot.items() if abs(f - frame) <= half_window])
    if len(vals) < 2:
        return {}
    med = np.median(vals, axis=0)
    mad = np.median(np.abs(vals - med), axis=0)
    xf = _fold(med[0] - med[1])
    if mad.max() > max_mad or abs(xf) > max_xf:
        return {"trunk3d_unstable": True}
    return {"shoulder_turn_3d_deg": round(float(med[0]), 1), "hip_turn_3d_deg": round(float(med[1]), 1),
            "x_factor_3d_deg": round(float(xf), 1), "trunk3d_readings": int(len(vals))}


def read_frames(video: Path, a: int, b: int) -> dict:
    cap = open_capture(video)
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
                 wb3d=None, hand3d_step: int = 2, grip_close_deg: float = 15.0, window=(1.0, 0.8),
                 hitting_face: str | None = None, shot_dir=None) -> dict:
    """{"phases": {phase: face summary}, "frames": [first, ...per-frame tilt/yaw/label/observed]}."""
    fps, i = run.fps, stroke.impact_frame
    a = max(0, i - int(round(window[0] * fps)))
    b = min(len(run.img), i + int(round(window[1] * fps)) + 1)
    # the wait (split step) often comes before the window: reach back to it, with the 3D hand only
    # around it (the frames in between keep the continuity of the face, no extra 3D)
    ready = (stroke.phases.get("ready") or {}).get("frame")
    a0 = a
    if ready is not None and 0 <= ready - 1 < a:
        a = ready - 1
    frames = read_frames(video, a, b)
    sk, wrist_k = run.sk, run.sk["dom_wrist"]
    rkps = {}
    if rpose is not None:
        for f, fr in frames.items():
            polys = run.rackets[f] if f < len(run.rackets) else None
            poly = pick_racket(polys, run.img[f, wrist_k], 0.3 * run.height_px) if polys is not None else None
            if poly is not None:
                rkps[f] = rpose(fr, [[*poly.min(0), *poly.max(0)]])[0][0]
    hand_frames = ({f: fr for f, fr in frames.items()
                    if (f >= a0 and (f - a0) % max(1, hand3d_step) == 0) or (ready is not None and abs(f - ready) <= 1)}
                   if wb3d is not None else {})
    cam = Camera(pitch_deg if pitch_deg is not None else 20.0)
    rec = _Recorder(wb3d, hand_frames) if wb3d is not None else None
    if hitting_face is None:      # forehand: palm side of the dominant hand; backhand: back of the hand
        hitting_face = "back" if stroke.stroke == "backhand" else "palm"
    track = face_track(hand_frames, run.boxes, run.img, run.rackets, sk, run.height_px, height_m, i, a, b,
                       rec, cam, grip_close_deg, fps=fps, racket_kps=rkps if rpose is not None else None,
                       hitting_face=hitting_face, shot_dir=shot_dir)
    rot = {}
    if rec is not None:
        for f, res in rec.out.items():
            if f is not None and res is not None:
                rt = trunk_rotation_3d(res[0], res[1], cam, sk.hand, height_m=height_m)
                if rt is not None:
                    rot[f] = rt
    by_f = {t["frame"]: t for t in track}
    phases = {}
    for name, p in stroke.phases.items():
        t = by_f.get(p.get("frame"))
        if t is None or t.get("face") is None:
            phases[name] = None
            continue
        phases[name] = {k: t[k] for k in ("points_to", "tilt_deg", "yaw_deg", "observed", "hand_evidence", "ambiguous")}
    per = [by_f.get(f) or {} for f in range(a, b)]
    trunk = trunk_at(rot, (stroke.phases.get("loaded") or {}).get("frame"), 3 * max(1, hand3d_step))
    return {
        "trunk3d": trunk,
        "rot3d": {str(f): [round(v, 1) for v in rt] for f, rt in rot.items()},
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
