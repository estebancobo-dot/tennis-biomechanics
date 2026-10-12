"""The ball's height around a stroke, from one broadcast camera.

The court lines give the camera (focal length, rotation and position: court.focal_and_rotation).
One camera cannot tell "coming closer" from "going up" along its line of sight, and behind the
baseline a ball coming to the player and rising after the bounce moves almost along that line: a
free 3D fit of the image track is ambiguous (tests: 1.5 m found for a 0.7 m ball). Three things are
known well instead, and they fix the flight:

- the bounce is on the ground: its court position is exact (homography);
- at contact the ball is at her hand: its height is her wrist height (measured on her body, scaled
  by her real height), so the line of sight at contact gives the contact point on the court;
- on the court the ball goes in a straight line between the bounce and the contact (no drag or
  spin effect worth the image error over ~0.2-0.8 s).

Each frame between bounce and contact then gives the ball's height (its line of sight cut at the
known court position), and a gravity parabola fitted to those heights gives the top of the bounce
and whether she takes the ball rising, at the top or dropping. Before the bounce, the ball's court
path from the opponent's contact (line of sight cut at ~1 m high) to the bounce places the net
crossing. Anything that does not follow the ball seen in the image is discarded, not shown.
"""
from __future__ import annotations

import numpy as np

G = 9.81
NET_Y = 11.885


def camera(H_court_to_img: np.ndarray, frame_shape) -> np.ndarray | None:
    """3x4 projection of court points (x, y on the ground in m, z up in m) to image px."""
    from .court import CourtFit, focal_and_rotation

    h, w = frame_shape[:2]
    Hc = np.asarray(H_court_to_img, float)
    f, r1, r2 = focal_and_rotation(CourtFit(Hc, 1.0), frame_shape)
    T = np.array([[1, 0, -w / 2], [0, 1, -h / 2], [0, 0, 1.0]])
    Gm = T @ Hc                                     # = λ K' [r1 r2 t] with the principal point at 0
    K = np.array([[f, 0, w / 2], [0, f, h / 2], [0, 0, 1.0]])
    Kinv = np.diag([1 / f, 1 / f, 1.0])
    s = 1.0 / np.linalg.norm(Kinv @ Gm[:, 0])       # the same scale and sign as focal_and_rotation
    if (Kinv @ Gm[:, 1])[2] * s < 0:
        s = -s
    t = Kinv @ Gm[:, 2] * s
    r3 = np.cross(r1, r2)
    P = K @ np.column_stack([r1, r2, r3, t])
    a, b = project(P, np.array([[0, 11.885, 0.0], [0, 11.885, 1.0]]))
    if not (np.isfinite(a).all() and np.isfinite(b).all()):
        return None
    if b[1] > a[1]:                                  # "up" must go up in the image
        P = K @ np.column_stack([r1, r2, -r3, t])
    pts = np.array([[-4.0, 0, 0], [4.0, 0, 0], [0, 23.77, 0]])
    hp = np.c_[pts[:, :2], np.ones(3)] @ Hc.T
    hp = hp[:, :2] / hp[:, 2:]
    if np.max(np.linalg.norm(project(P, pts) - hp, axis=1)) > 0.02 * w:
        return None
    return P


def project(P: np.ndarray, X: np.ndarray) -> np.ndarray:
    q = np.c_[X, np.ones(len(X))] @ P.T
    return q[:, :2] / q[:, 2:3]


def _path(anchor: np.ndarray, v: np.ndarray, t: np.ndarray) -> np.ndarray:
    return anchor[None] + v[None] * t[:, None] + np.c_[np.zeros_like(t), np.zeros_like(t), -0.5 * G * t ** 2]


def _ray(P: np.ndarray, uv) -> tuple[np.ndarray, np.ndarray]:
    """Camera centre and direction of the line of sight through image point uv (court frame)."""
    M, p4 = P[:, :3], P[:, 3]
    C = -np.linalg.solve(M, p4)
    d = np.linalg.solve(M, np.array([uv[0], uv[1], 1.0]))
    return C, d / np.linalg.norm(d)


def _at_y(P, uv, y):
    """Point of the line of sight through uv whose court y is y."""
    C, d = _ray(P, uv)
    if abs(d[1]) < 1e-9:
        return None
    return C + d * (y - C[1]) / d[1]


def _at_z(P, uv, z):
    """Point of the line of sight through uv at height z."""
    C, d = _ray(P, uv)
    if abs(d[2]) < 1e-9:
        return None
    return C + d * (z - C[2]) / d[2]


def flights(track: np.ndarray, fps: float, H_img: np.ndarray, frame_shape, bounce_frame: int | None,
            impact_frame: int, opp_frame: int | None, contact_z_m: float | None,
            player_y_m: float | None = None, max_rms_m=0.25) -> dict:
    """Moments of the ball around one stroke (frames of the window) and the ball at contact.

    track: (T, ≥2) ball in image px (NaN unseen); H_img: court→image of the window (her baseline at
    y = 0); contact_z_m: height of her hand at contact (m); player_y_m: court y of her feet at
    contact (sanity check of the contact point). Keys, only those measured reliably:
    contact_phase ('subiendo' | 'arriba' | 'cayendo'), apex_frame, apex_height_m, contact_height_m,
    rise_speed_mps, bounce_to_apex_s, fit_rms_m, net_frame, incoming_speed_kmh."""
    out: dict = {}
    if bounce_frame is None or H_img is None or not 0 <= bounce_frame < impact_frame < len(track):
        return out
    P = camera(H_img, frame_shape)
    if P is None:
        return out
    b_uv = track[bounce_frame, :2]
    if not np.isfinite(b_uv).all():
        return out
    B = _at_z(P, b_uv, 0.0)
    if B is None:
        return out
    # after the bounce: the contact point from her hand height, then heights frame by frame
    if contact_z_m is not None and 0.1 < contact_z_m < 3.0:
        seen = [k for k in range(impact_frame, max(bounce_frame, impact_frame - 4), -1) if np.isfinite(track[k, :2]).all()]
        if seen:
            kc = seen[0]
            Cp = _at_z(P, track[kc, :2], contact_z_m)
            ok_c = Cp is not None and (player_y_m is None or -1.5 <= Cp[1] - player_y_m <= 2.5)
            tc_seen = (kc - bounce_frame) / fps
            if ok_c and tc_seen > 0.06:
                ts, zs = [], []
                for k in range(bounce_frame + 1, kc + 1):
                    if not np.isfinite(track[k, :2]).all():
                        continue
                    t = (k - bounce_frame) / fps
                    y = B[1] + (Cp[1] - B[1]) * t / tc_seen          # straight on the court
                    X = _at_y(P, track[k, :2], y)
                    if X is not None:
                        ts.append(t)
                        zs.append(X[2])
                ts, zs = np.array(ts), np.array(zs)
                if len(ts) >= 4:
                    vz = float(np.sum(ts * (zs + 0.5 * G * ts ** 2)) / np.sum(ts ** 2))   # z = vz t - g t²/2
                    rms = float(np.sqrt(np.mean((zs - (vz * ts - 0.5 * G * ts ** 2)) ** 2)))
                    if rms <= max_rms_m and 0.5 <= vz <= 12.0:
                        t_apex = vz / G
                        tc = (impact_frame - bounce_frame) / fps
                        margin = max(0.05, 0.15 * t_apex)
                        out.update(fit_rms_m=round(rms, 2), rise_speed_mps=round(vz, 2),
                                   apex_frame=int(round(bounce_frame + t_apex * fps)),
                                   apex_height_m=round(vz ** 2 / (2 * G), 2), bounce_to_apex_s=round(t_apex, 3),
                                   contact_height_m=round(float(contact_z_m), 2),
                                   contact_phase=("subiendo" if tc < t_apex - margin else "cayendo" if tc > t_apex + margin
                                                  else "arriba"))
    # before the bounce: the opponent's contact (~1 m high) to the bounce, straight on the court
    if opp_frame is not None and 0 <= opp_frame < bounce_frame:
        so = [k for k in range(opp_frame, min(bounce_frame, opp_frame + 4)) if np.isfinite(track[k, :2]).all()]
        if so:
            S = _at_z(P, track[so[0], :2], 1.0)
            ts_ = (so[0] - bounce_frame) / fps
            if S is not None and S[1] > NET_Y + 2.0 and ts_ < -0.2:
                tn = ts_ * (NET_Y - B[1]) / (S[1] - B[1])           # Y(t) linear from S (t = ts_) to B (t = 0)
                out["net_frame"] = int(round(bounce_frame + tn * fps))
                out["incoming_speed_kmh"] = round(float(np.linalg.norm((B - S)[:2]) / -ts_ * 3.6))
    return out
