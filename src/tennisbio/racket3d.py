"""3D racket orientation (where the strings face) from a single broadcast camera.

The racket is a known rigid object: total length ≈ 0.685 m, head ≈ 0.33 × 0.26 m. From its
image outline we measure the 2D axis direction, how foreshortened the racket is and how wide
the head looks. Under a (weak-perspective) camera that is behind the court and pitched down,
each frame then allows up to 8 orientations (axis toward/away from the camera × head tilted
one way or the other × which face is the hitting face). The ambiguity is resolved over the
whole stroke:

- at contact the hitting face points roughly where the ball goes (towards the net / target);
- the racket cannot turn abruptly between consecutive frames.

A Viterbi search picks the most consistent sequence. Frames where an alternative sequence is
almost as good are flagged as ambiguous instead of being trusted.

World frame (metres): X to the right of the image, Y towards the net (away from the camera),
Z up. "Face normal" n is the outward normal of the hitting face.
"""
from dataclasses import dataclass

import numpy as np

RACKET_LENGTH = 0.685     # m, butt → tip
GRIP_TO_TIP = 0.60        # m, from the wrist (hand on the grip) to the tip
HEAD_WIDTH = 0.26         # m, outer width of the head


@dataclass
class Camera:
    pitch_deg: float = 20.0          # how much the main broadcast camera looks down

    @property
    def basis(self):
        t = np.radians(self.pitch_deg)
        right = np.array([1.0, 0, 0])
        fwd = np.array([0, np.cos(t), -np.sin(t)])     # viewing direction
        up = np.cross(right, fwd)
        return right, up, fwd

    def project_dir(self, v: np.ndarray) -> np.ndarray:
        """Direction in image coordinates (x right, y down) of a 3D vector, orthographic."""
        r, u, _ = self.basis
        return np.array([v @ r, -(v @ u)])

    def image_dir_to_3d(self, d2: np.ndarray) -> np.ndarray:
        r, u, _ = self.basis
        return d2[0] * r - d2[1] * u


@dataclass
class Observation:
    axis2d: np.ndarray       # unit vector butt→tip in the image (x right, y down)
    length_ratio: float      # apparent / expected length (1 = racket parallel to the image plane)
    width_ratio: float       # apparent / expected head width (1 = face seen square-on)


def _unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v


def candidates(obs: Observation, cam: Camera) -> list[tuple[np.ndarray, np.ndarray]]:
    """All (axis a, face normal n) pairs compatible with one observation (≤ 8)."""
    _, _, f = cam.basis
    e = _unit(cam.image_dir_to_3d(_unit(obs.axis2d)))
    s = np.sqrt(max(0.0, 1 - min(1.0, obs.length_ratio) ** 2))      # |a·f|
    out = []
    for sa in ((s, -s) if s > 1e-3 else (0.0,)):
        a = _unit(np.sqrt(1 - sa ** 2) * e + sa * f)
        fp = f - (f @ a) * a
        if np.linalg.norm(fp) < 1e-6:
            continue
        b1 = _unit(fp)
        b2 = np.cross(a, b1)
        c = np.sqrt(max(0.0, 1 - min(1.0, obs.width_ratio) ** 2))    # |w·f|
        cphi = np.clip(c / np.linalg.norm(fp), -1, 1)
        phis = {np.arccos(cphi), -np.arccos(cphi)}
        for phi in phis:
            w = np.cos(phi) * b1 + np.sin(phi) * b2                 # width direction of the head
            n = _unit(np.cross(a, w))
            out += [(a, n), (a, -n)]
    return out


def _ang(u, v):
    return float(np.degrees(np.arccos(np.clip(u @ v, -1, 1))))


def smooth_observations(obs: list[Observation | None], window=7) -> list[Observation | None]:
    """Temporal smoothing of the foreshortening ratios (their per-frame noise dominates the error).

    Each continuous run of observed frames is filtered separately so gaps (blur) are not bridged.
    """
    from scipy.signal import savgol_filter

    out = list(obs)
    t, T = 0, len(obs)
    while t < T:
        if obs[t] is None:
            t += 1
            continue
        e = t
        while e < T and obs[e] is not None:
            e += 1
        if e - t >= window:
            L = savgol_filter([o.length_ratio for o in obs[t:e]], window, 2)
            W = savgol_filter([o.width_ratio for o in obs[t:e]], window, 2)
            for k in range(t, e):
                out[k] = Observation(obs[k].axis2d, float(np.clip(L[k - t], 0, 1.05)), float(np.clip(W[k - t], 0, 1.05)))
        t = e
    return out


def _rot(a, n):
    from scipy.spatial.transform import Rotation
    return Rotation.from_matrix(np.c_[a, np.cross(n, a), n])


def solve_sequence(obs: list[Observation | None], cam: Camera, impact: int | None,
                   shot_dir=np.array([0.0, 1.0, 0.15]), impact_tol_deg=35.0,
                   max_turn_deg_per_frame=25.0, max_accel_deg_per_frame2=12.0):
    """Most consistent orientation per frame. Returns (axes, normals, ambiguous) lists.

    Second-order Viterbi over pairs of consecutive observed frames: besides small rotations
    between frames, it prefers a steady angular velocity. At configurations where two mirror
    solutions touch (racket parallel to the image plane), the true one keeps turning the same
    way while the mirror one would have to reverse, so momentum picks the right branch.
    The contact anchor applies to the observed frames nearest to the impact (blur hides it).
    Frames without an observation are filled by interpolation.
    """
    shot = _unit(np.asarray(shot_dir, float))
    T = len(obs)
    obs = smooth_observations(obs)
    allc = {t: candidates(obs[t], cam) for t in range(T) if obs[t] is not None}
    idx = [t for t, c in allc.items() if c]          # frames with at least one valid solution
    if not idx:
        return [None] * T, [None] * T, [False] * T
    C = [allc[t] for t in idx]
    R = [[_rot(a, n) for a, n in cs] for cs in C]

    def unary(k):
        t = idx[k]
        if impact is None or abs(t - impact) > 6:
            return np.zeros(len(C[k]))
        tol = impact_tol_deg + 8.0 * abs(t - impact)
        return np.array([(_ang(n, shot) / tol) ** 2 for _, n in C[k]])

    def vel(k):  # rotation vectors from frame k-1 to k, per frame: shape (n_k, n_{k-1}, 3)
        gap = idx[k] - idx[k - 1]
        return np.array([[(R[k][i] * R[k - 1][j].inv()).as_rotvec() / gap for j in range(len(C[k - 1]))]
                         for i in range(len(C[k]))])

    sv = np.radians(max_turn_deg_per_frame)
    sa = np.radians(max_accel_deg_per_frame2)
    K = len(idx)
    u0 = unary(0)
    if K == 1:
        best_path = [int(np.argmin(u0))]
        margin = np.inf
    else:
        V1 = vel(1)                                          # (n1, n0, 3)
        cost = u0[None, :] + unary(1)[:, None] + (np.linalg.norm(V1, axis=2) / sv) ** 2   # (n1, n0)
        backs = []
        Vprev = V1
        for k in range(2, K):
            Vk = vel(k)                                      # (nk, n_{k-1}, 3)
            # new[i, j] = min_m cost[j, m] + accel(Vk[i,j], Vprev[j,m]) + speed(Vk[i,j])
            acc = np.linalg.norm(Vk[:, :, None, :] - Vprev[None, :, :, :], axis=3) / sa       # (nk, n_{k-1}, n_{k-2})
            tot = cost[None, :, :] + acc ** 2
            bp = tot.argmin(2)
            new = tot.min(2) + (np.linalg.norm(Vk, axis=2) / sv) ** 2 + unary(k)[:, None]
            backs.append(bp)
            cost, Vprev = new, Vk
        flat = np.sort(cost.ravel())
        margin = float(flat[1] - flat[0]) if len(flat) > 1 else np.inf
        i, j = np.unravel_index(int(np.argmin(cost)), cost.shape)
        best_path = [int(j), int(i)]
        for bp in reversed(backs):
            m = int(bp[best_path[1], best_path[0]])   # best frame k-2 for the pair (k, k-1)
            best_path.insert(0, m)
        # best_path holds candidate indices for idx[0..K-1]
    axes, normals, amb = [None] * T, [None] * T, [False] * T
    for k, c in enumerate(best_path):
        axes[idx[k]], normals[idx[k]] = C[k][c]
    if margin < 1.0:
        amb = [t in allc for t in range(T)]
    known = idx
    for t in range(T):
        if normals[t] is None:
            lo = max([q for q in known if q < t], default=None)
            hi = min([q for q in known if q > t], default=None)
            if lo is not None and hi is not None:
                w = (t - lo) / (hi - lo)
                axes[t] = _unit((1 - w) * axes[lo] + w * axes[hi])
                normals[t] = _unit((1 - w) * normals[lo] + w * normals[hi])
            else:
                q = lo if lo is not None else hi
                axes[t], normals[t] = axes[q], normals[q]
    return axes, normals, amb


def _predict(Rm: np.ndarray, cam: Camera):
    """Observation predicted by rotation matrices (K, 3, 3): (axis2d angle, length ratio, width ratio)."""
    r, u, f = cam.basis
    a, w = Rm[:, :, 0], Rm[:, :, 1]
    ang = np.arctan2(-(a @ u), a @ r)
    lr = np.sqrt(np.clip(1 - (a @ f) ** 2, 0, 1))
    wr = np.sqrt(np.clip(1 - (w @ f) ** 2, 0, 1))
    return ang, lr, wr


def refine(axes, normals, obs: list[Observation | None], cam: Camera, impact: int | None,
           shot_dir=np.array([0.0, 1.0, 0.15]), sd_axis_deg=3.0, sd_ratio=0.05, sd_acc_deg=6.0, impact_tol_deg=35.0):
    """Maximum a posteriori refinement of a whole stroke, starting from the Viterbi sequence.

    Unknowns: one rotation per frame (including blurred frames). Terms: reproduce each observed
    axis direction and foreshortening, small angular acceleration, contact anchor.
    """
    from scipy.optimize import least_squares
    from scipy.spatial.transform import Rotation

    T = len(obs)
    R0 = Rotation.from_matrix(np.stack([np.c_[a, np.cross(n, a), n] for a, n in zip(axes, normals)]))
    ref = R0                                            # optimise small corrections around R0
    shot = _unit(np.asarray(shot_dir, float))
    o_idx = [t for t in range(T) if obs[t] is not None]
    o_ang = np.array([np.arctan2(obs[t].axis2d[1], obs[t].axis2d[0]) for t in o_idx])   # same convention as _predict
    o_lr = np.array([obs[t].length_ratio for t in o_idx])
    o_wr = np.array([obs[t].width_ratio for t in o_idx])
    sa, sr, sacc = np.radians(sd_axis_deg), sd_ratio, np.radians(sd_acc_deg)

    def rots(x):
        return Rotation.from_rotvec(x.reshape(T, 3)) * ref

    def resid(x):
        Rt = rots(x)
        M = Rt.as_matrix()
        ang, lr, wr = _predict(M[o_idx], cam)
        da = np.angle(np.exp(1j * (ang - o_ang)))
        res = [da / sa, (np.minimum(lr, 1.0) - np.minimum(o_lr, 1.0)) / sr, (np.minimum(wr, 1.0) - np.minimum(o_wr, 1.0)) / sr]
        if T >= 3:
            rel = (Rt[1:] * Rt[:-1].inv()).as_rotvec()
            res.append((rel[1:] - rel[:-1]).ravel() / sacc)
        if impact is not None:
            n = M[impact, :, 2]
            res.append(np.array([_ang(n, shot) / impact_tol_deg]))
        return np.concatenate(res)

    # sparsity: frame t only touches its own observation, three acceleration terms and the anchor
    from scipy.sparse import lil_matrix

    n_obs = 3 * len(o_idx)
    n_acc = 3 * max(0, T - 2)
    J = lil_matrix((n_obs + n_acc + (impact is not None), 3 * T), dtype=int)
    pos = {t: k for k, t in enumerate(o_idx)}
    for t in range(T):
        cols = slice(3 * t, 3 * t + 3)
        if t in pos:
            for blk in range(3):
                J[blk * len(o_idx) + pos[t], cols] = 1
        for j in (t - 2, t - 1, t):
            if 0 <= j < T - 2:
                J[n_obs + 3 * j:n_obs + 3 * j + 3, cols] = 1
        if impact is not None and t == impact:
            J[n_obs + n_acc, cols] = 1
    sol = least_squares(resid, np.zeros(3 * T), method="trf", x_scale=0.1, max_nfev=60, jac_sparsity=J)
    M = rots(sol.x).as_matrix()
    return [M[t, :, 0] for t in range(T)], [M[t, :, 2] for t in range(T)]


FACE_LABELS_ES = {"down": "suelo", "up": "cielo", "back": "valla trasera", "front": "red",
                  "left": "valla izquierda", "right": "valla derecha"}


def describe_face(n: np.ndarray, hand="right") -> dict:
    """Where the hitting face points, plus angles: tilt (closed + / open −) and yaw.

    tilt_deg: angle of the face normal below the horizontal; + = closed (strings to the ground).
    yaw_deg: horizontal direction of the normal, 0 = towards the net, + = to the player's
    dominant side, ±180 = back fence.
    """
    x, y, z = n
    dom = 1 if hand == "right" else -1
    axis = int(np.argmax(np.abs(n)))
    label = [("right" if x > 0 else "left"), ("front" if y > 0 else "back"), ("up" if z > 0 else "down")][axis]
    return dict(points_to=FACE_LABELS_ES[label],
                tilt_deg=round(float(-np.degrees(np.arcsin(np.clip(z, -1, 1)))), 1),
                yaw_deg=round(float(np.degrees(np.arctan2(dom * x, y))), 1))


def observe(head_px: np.ndarray, tip_px: np.ndarray, wrist_px: np.ndarray, head_width_px: float,
            px_per_m: float) -> Observation:
    """Observation from image measurements: wrist (hand on the grip), tip and head width."""
    d = tip_px - wrist_px
    return Observation(axis2d=_unit(d), length_ratio=float(np.linalg.norm(d) / (GRIP_TO_TIP * px_per_m)),
                       width_ratio=float(head_width_px / (HEAD_WIDTH * px_per_m)))


def synthetic_observation(a: np.ndarray, n: np.ndarray, cam: Camera) -> Observation:
    """Exact observation produced by a racket with axis a and face normal n (for validation)."""
    _, _, f = cam.basis
    w = _unit(np.cross(n, a))
    d2 = cam.project_dir(a)
    return Observation(axis2d=_unit(d2), length_ratio=float(np.sqrt(max(0, 1 - (a @ f) ** 2))),
                       width_ratio=float(np.sqrt(max(0, 1 - (w @ f) ** 2))))
