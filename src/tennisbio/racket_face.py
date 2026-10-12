"""Where the strings face through a stroke: silhouette + contact anchor + 3D hand/forearm."""
import numpy as np

from .racket import pick_racket
from .racket3d import Camera, describe_face, hand_prior, observe_keypoints, observe_polygon, refine, solve_sequence


def face_track(frames: dict, boxes: list, img_kp: np.ndarray, rackets: list, sk, height_px: float,
               height_m: float, impact: int, a: int, b: int, wb3d=None, cam: Camera = Camera(),
               grip_close_deg=15.0, fps: float = 30.0, racket_kps: dict | None = None,
               hitting_face="palm") -> list[dict]:
    """Per frame in [a, b): hitting-face direction and angles.

    frames: {frame_index: BGR image} (needed only for the 3D hand model); boxes: tracked box per frame;
    img_kp: cleaned 2D keypoints (T, K, 2) in image px; rackets: outlines per frame;
    racket_kps: {frame: (5, 2) keypoints} from the racket pose model, preferred over the outline.
    """
    ppm = height_px / height_m
    obs, priors = [], []
    for f in range(a, b):
        wrist = img_kp[f, sk["dom_wrist"]]
        poly = pick_racket(rackets[f], wrist, 0.3 * height_px) if rackets[f] is not None else None
        if racket_kps is not None and f in racket_kps:
            obs.append(observe_keypoints(racket_kps[f], ppm))
        else:
            obs.append(observe_polygon(poly, wrist, ppm) if poly is not None else None)
        pr = None
        if wb3d is not None and boxes[f] is not None and f in frames:
            k3, sc, _ = wb3d(frames[f], boxes[f])
            pr = hand_prior(k3, sc, cam, sk.hand, grip_close_deg, hitting_face=hitting_face, height_m=height_m)
        priors.append(pr)
    i = impact - a
    # the outline is unreliable around contact (motion blur): ignore it within ~80 ms and let the
    # contact anchor and continuity decide there
    blur = max(1, int(round(0.08 * fps)))
    for k in range(max(0, i - blur), min(len(obs), i + blur + 1)):
        obs[k] = None
    axes, normals, amb = solve_sequence(obs, cam, i, priors=priors)
    if all(n is None for n in normals):
        return [dict(frame=f, face=None) for f in range(a, b)]
    axes, normals = refine(axes, normals, obs, cam, i, priors=priors)
    out = []
    for k, f in enumerate(range(a, b)):
        d = describe_face(normals[k], sk.hand)
        out.append(dict(frame=f, face=normals[k].tolist(), axis=axes[k].tolist(), observed=obs[k] is not None,
                        hand_evidence=priors[k] is not None and priors[k].face is not None,
                        ambiguous=bool(amb[k]), **d))
    return out
