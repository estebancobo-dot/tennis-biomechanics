"""Synthetic validation of the 3D racket-orientation solver.

Random but smooth racket rotations around a forehand contact (known ground truth) are turned
into the image measurements the solver sees, with measurement noise, blurred frames around
contact and a camera pitch the solver does not know exactly. Then we measure how well the
face direction is recovered.
"""
import numpy as np
from scipy.spatial.transform import Rotation, Slerp

from ..racket3d import Camera, HandPrior, Observation, describe_face, refine, solve_sequence, synthetic_observation


def random_stroke(rng, T=60, impact=36, fps=50):
    """Axis/normal sequences: contact pose near 'face to the net', smooth random swing around it."""
    a_imp = np.array([1.0, rng.normal(0.2, 0.2), rng.normal(0.0, 0.15)])
    a_imp /= np.linalg.norm(a_imp)
    n_imp = np.array([0.0, 1.0, rng.normal(0.0, 0.2)])
    n_imp -= (n_imp @ a_imp) * a_imp
    n_imp /= np.linalg.norm(n_imp)
    R_imp = Rotation.from_matrix(np.c_[a_imp, np.cross(n_imp, a_imp), n_imp])
    key_t = [0, 12, 24, impact, 46, T - 1]
    rots = []
    for t in key_t:
        if t == impact:
            rots.append(R_imp)
        else:
            mag = np.radians(min(160, abs(t - impact) * rng.uniform(3, 6)))
            v = rng.normal(size=3)
            rots.append(Rotation.from_rotvec(v / np.linalg.norm(v) * mag) * R_imp)
    sl = Slerp(key_t, Rotation.concatenate(rots))
    R = sl(np.arange(T))
    m = R.as_matrix()
    return m[:, :, 0], m[:, :, 2], impact


def noisy(obs: Observation, rng, axis_deg=3.0, ratio_sd=0.05) -> Observation:
    ang = np.radians(rng.normal(0, axis_deg))
    c, s = np.cos(ang), np.sin(ang)
    d = np.array([c * obs.axis2d[0] - s * obs.axis2d[1], s * obs.axis2d[0] + c * obs.axis2d[1]])
    return Observation(d, float(np.clip(obs.length_ratio + rng.normal(0, ratio_sd), 0, 1.05)),
                       float(np.clip(obs.width_ratio + rng.normal(0, ratio_sd), 0, 1.05)))


def perturb(v, rng, sd_deg):
    """Unit vector v rotated by a random angle with standard deviation sd_deg."""
    axis = rng.normal(size=3)
    axis -= (axis @ v) * v
    axis /= np.linalg.norm(axis)
    ang = np.radians(rng.normal(0, sd_deg))
    return v * np.cos(ang) + np.cross(axis, v) * np.sin(ang)


def run(n_strokes=200, seed=0, blur_frames=2, pitch_true=(15, 25), solver_pitch=20.0, use_refine=True,
        hand_sd_deg=None, hand_coverage=0.8, **noise):
    rng = np.random.default_rng(seed)
    errs, errs_out, label_ok, amb = [], [], [], []
    for _ in range(n_strokes):
        A, N, imp = random_stroke(rng)
        cam_true = Camera(rng.uniform(*pitch_true))
        obs = [noisy(synthetic_observation(a, n, cam_true), rng, **noise) for a, n in zip(A, N)]
        if blur_frames:
            for k in range(imp - blur_frames, imp + blur_frames + 1):
                obs[k] = None
        priors = None
        if hand_sd_deg is not None:   # simulated hand/forearm evidence with its own error
            priors = [HandPrior(face=perturb(n, rng, hand_sd_deg), face_sd_deg=max(hand_sd_deg, 15.0),
                                forearm=perturb(a, rng, 30.0)) if rng.random() < hand_coverage else None
                      for a, n in zip(A, N)]
        axes, normals, ambiguous = solve_sequence(obs, Camera(solver_pitch), imp, priors=priors)
        if use_refine:
            axes, normals = refine(axes, normals, obs, Camera(solver_pitch), imp, priors=priors)
        for t in range(len(A)):
            e = float(np.degrees(np.arccos(np.clip(normals[t] @ N[t], -1, 1))))
            errs.append(e)
            if abs(t - imp) > blur_frames:
                errs_out.append(e)
            label_ok.append(describe_face(normals[t])["points_to"] == describe_face(N[t])["points_to"])
            amb.append(ambiguous[t])
    e, eo = np.array(errs), np.array(errs_out)
    return dict(
        strokes=n_strokes,
        face_err_deg_median=round(float(np.median(e)), 1), face_err_deg_p90=round(float(np.percentile(e, 90)), 1),
        within_15deg=round(float(np.mean(e <= 15)), 3), within_30deg=round(float(np.mean(e <= 30)), 3),
        outside_blur_err_median=round(float(np.median(eo)), 1),
        points_to_accuracy=round(float(np.mean(label_ok)), 3), flagged_ambiguous=round(float(np.mean(amb)), 3),
    )
