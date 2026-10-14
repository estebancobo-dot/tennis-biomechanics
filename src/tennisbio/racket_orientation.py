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


# rtmlib decodes RTMW3D's depth with the image height of the model input (384 px), but the model's
# depth axis has the width's bins (288 px: its simcc_z output has 576 = 2 × 288 bins, as in mmpose's
# SimCC3DLabel with input_size (288, 384, 288)); depth differences come out × 288/384.
RTMLIB_Z_SCALE = 384 / 288
# a 3D shoulder/hip segment shorter than this share of its own length in the stroke has lost its
# depth (see trunk_rotation_3d): the reading is not a 3D measurement
RIGID_MIN = 0.8


def trunk_rotation_3d(k3: np.ndarray, sc: np.ndarray, cam: Camera, hand="right", min_score=0.4, height_m: float = 1.8):
    """(shoulder turn, hip turn, shoulder length m, hip length m) about the vertical, from RTMW3D keypoints.

    0 = line square to the net; + = dominant shoulder/hip turned back (towards the camera), as in
    the backswing of a forehand; −180..180 (the joints are labelled, so a line turned past side-on
    is not folded back). Same world frame as the racket solver (Camera basis): image x along the
    camera's right, image y down along −up, model depth (+ away from the camera) along the viewing
    direction, which is pitched down by cam.pitch_deg.

    Scale: image px per metre from her height — nose to the lowest ankle is ≈ 0.93 of it in the
    world vertical, which the pitched camera sees × cos(pitch). Depth: RTMW3D's, in metres, with
    rtmlib's decoding undone (RTMLIB_Z_SCALE).

    The segment lengths are returned because they test the depth: a rigid shoulder (hip) segment
    keeps its length whatever the turn. On the broadcast view from behind and above, RTMW3D's
    depth between the two shoulders stays within ~0.1 m at every turn (measured on the US Open
    final: 0.00-0.09 m at the loaded frame, where the line is near side-on), so the 3D segment
    shrinks with the turn just like the image width (0.12-0.20 m there against 0.35-0.49 m square-on)
    and the angle is read almost only from the image-y offset × sin(pitch): ~10-30° for a line
    near side-on. trunk_at drops such readings."""
    if min(sc[[L_SH, R_SH, L_HIP, R_HIP]]) < min_score:
        return None
    r, u, f = cam.basis
    cos_p = float(np.cos(np.radians(cam.pitch_deg)))
    px_per_m = (max(k3[15, 1], k3[16, 1]) - k3[0, 1]) / (0.93 * height_m * cos_p)   # her own height
    if px_per_m <= 0:
        return None
    to_w = lambda p: (p[0] / px_per_m) * r - (p[1] / px_per_m) * u + p[2] * RTMLIB_Z_SCALE * f
    dom = 1 if hand == "right" else -1
    out, lens = [], []
    for a, b in ((L_SH, R_SH), (L_HIP, R_HIP)):
        d = to_w(k3[b]) - to_w(k3[a])                     # left → right in world (x right, y to the net)
        # back turn: the right joint goes towards the camera (−y) for a right-hander and away from it
        # (the left one comes back) for a left-hander. (The former atan2(d1, d0·dom) read a square-on
        # left-hander as 180°, which the old fold to ±90° hid.)
        out.append(float(-dom * np.degrees(np.arctan2(d[1], d[0]))))
        lens.append(float(np.hypot(d[0], d[1])))
    return (*out, *lens)


def _wrap(a: float) -> float:
    """An angle to (-180, 180]. The shoulders are labelled left/right, so a line has a direction:
    the former fold to (-90, 90] turned a 120° coil into −60°."""
    return 180.0 - (180.0 - a) % 360.0


def trunk_at(rot: dict, frame: int | None, half_window: int, max_xf=80.0, max_mad=15.0) -> dict:
    """Shoulder/hip turn and X-factor around one frame from the monocular 3D readings within
    ±half_window: median, and only when the readings agree (median absolute deviation of both
    turns ≤ max_mad); monocular depth from behind is unstable, so disagreement means no value.

    rot: frame → (shoulder turn, hip turn[, shoulder length, hip length]) (trunk_rotation_3d). With
    the lengths, a reading counts only when both segments keep ≥ RIGID_MIN of their length in the
    stroke (90th percentile of all its readings, where she is square-on): a shorter one has lost
    its depth and only repeats the 2D width. When the readings near the frame all fail that, the
    trunk is "trunk3d_unobservable" (not measurable in 3D from this view), not a value; a value
    that passes is marked "trunk3d_rigid" (the reliability check compares only those)."""
    if frame is None:
        return {}
    near = [v for f, v in rot.items() if abs(f - frame) <= half_window]
    rigid = len(rot) > 0 and all(len(v) >= 4 for v in rot.values())
    if rigid:
        ref = np.percentile(np.array([v[2:4] for v in rot.values()], float), 90, axis=0)
        kept = [v for v in near if v[2] >= RIGID_MIN * ref[0] and v[3] >= RIGID_MIN * ref[1]]
        if len(near) >= 2 and len(kept) < 2:
            return {"trunk3d_unobservable": True}
        near = kept
    vals = np.array([(_wrap(v[0]), _wrap(v[1])) for v in near])
    if len(vals) < 2:
        return {}
    med = np.median(vals, axis=0)
    mad = np.median(np.abs(vals - med), axis=0)
    xf = _wrap(med[0] - med[1])
    if mad.max() > max_mad or abs(xf) > max_xf:
        return {"trunk3d_unstable": True}
    out = {"shoulder_turn_3d_deg": round(float(med[0]), 1), "hip_turn_3d_deg": round(float(med[1]), 1),
           "x_factor_3d_deg": round(float(xf), 1), "trunk3d_readings": int(len(vals))}
    if rigid:
        out["trunk3d_rigid"] = True
    return out


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


from .clip_pipeline import READY_HALF  # noqa: E402  (the racket is searched around the wait the same width)


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
    if ready is not None and 0 <= ready - READY_HALF < a:
        a = ready - READY_HALF
    elif ready is not None and ready - READY_HALF < 0 <= ready - 1 < a:
        a = 0
    frames = read_frames(video, a, b)
    sk, wrist_k = run.sk, run.sk["dom_wrist"]
    rkps = {}
    if rpose is not None:
        todo = []
        for f, fr in frames.items():
            polys = run.rackets[f] if f < len(run.rackets) else None
            poly = pick_racket(polys, run.img[f, wrist_k], 0.3 * run.height_px) if polys is not None else None
            if poly is not None:
                todo.append((f, fr, [*poly.min(0), *poly.max(0)]))
        if hasattr(rpose, "many"):       # all the window's rackets in a few model runs
            kp_all, _ = rpose.many([(fr, box) for _, fr, box in todo])
            rkps = {f: k for (f, _, _), k in zip(todo, kp_all)}
        else:
            rkps = {f: rpose(fr, [box])[0][0] for f, fr, box in todo}
    hand_frames = ({f: fr for f, fr in frames.items()
                    if (f >= a0 and (f - a0) % max(1, hand3d_step) == 0) or (ready is not None and abs(f - ready) <= READY_HALF)}
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
        "rot3d": {str(f): [round(v, 1) for v in rt[:2]] + [round(v, 3) for v in rt[2:]] for f, rt in rot.items()},
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
