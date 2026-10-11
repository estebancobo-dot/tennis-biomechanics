"""Metrics on the court plane (metres): feet position, stance type, displacement.

Court frame as in tennisbio.court: x across (+ = right of the image), y from the near baseline
towards the net. Valid for the near player of the main camera.
"""
import numpy as np

from .skeleton import Skeleton

# stance from the angle of the back→front foot line with the baseline (0° = feet side by side)
OPEN_MAX_DEG, SEMI_MAX_DEG = 20.0, 55.0


def to_court(H_court_to_img: np.ndarray, pts_img: np.ndarray) -> np.ndarray:
    p = np.c_[np.asarray(pts_img, float), np.ones(len(pts_img))] @ np.linalg.inv(H_court_to_img).T
    return p[:, :2] / p[:, 2:]


def feet_on_court(img_kp: np.ndarray, frame: int, sk: Skeleton, H: np.ndarray):
    """(dominant-side foot, non-dominant-side foot) in court metres, or None."""
    if frame is None or not 0 <= frame < len(img_kp):
        return None
    pts = img_kp[frame, [sk["dom_ankle"], sk["non_ankle"]]]
    if np.isnan(pts).any():
        return None
    q = to_court(H, pts)
    return q[0], q[1]


def stance(dom_foot: np.ndarray, non_foot: np.ndarray, stroke: str) -> tuple[str, float]:
    """('abierto' | 'semiabierto' | 'cerrado', angle in degrees).

    The front foot is the non-dominant one on a forehand and the dominant one on a backhand.
    The angle is how far the front foot is ahead (towards the net) of the back foot, relative to
    the feet line: 0° side by side (open), 90° one behind the other (closed); negative when the
    "front" foot is actually behind (very open)."""
    front, back = (non_foot, dom_foot) if stroke == "forehand" else (dom_foot, non_foot)
    d = front - back
    ang = float(np.degrees(np.arctan2(d[1], abs(d[0]))))
    kind = "abierto" if ang < OPEN_MAX_DEG else "semiabierto" if ang < SEMI_MAX_DEG else "cerrado"
    return kind, ang


def court_metrics(img_kp: np.ndarray, sk: Skeleton, H: np.ndarray, stroke: str, impact: int,
                  opponent_hit: int | None = None) -> dict:
    """Position, base width and stance at contact; displacement since the opponent's hit."""
    out = {}
    f = feet_on_court(img_kp, impact, sk, H)
    if f is None:
        return out
    dom, non = f
    mid = (dom + non) / 2
    kind, ang = stance(dom, non, stroke)
    out.update(court_pos_m=[round(float(v), 2) for v in mid], stance_width_m=round(float(np.linalg.norm(dom - non)), 2),
               stance=kind, stance_angle_deg=round(ang, 1))
    g = feet_on_court(img_kp, opponent_hit, sk, H)
    if g is not None:
        out["displacement_m"] = round(float(np.linalg.norm(mid - (g[0] + g[1]) / 2)), 2)
    return out
