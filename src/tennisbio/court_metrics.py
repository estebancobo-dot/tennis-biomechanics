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


SINGLES_HALF, DOUBLES_HALF, LENGTH, NET = 4.115, 5.485, 23.77, 11.885


def shot_landing(H: np.ndarray, candidates: list, contact_x: float | None, fps: float, impact_frame: int) -> dict:
    """Where the player's shot bounced on the far court and what that means.

    candidates: [[x_px, y_px, frame], ...] sharpest first (ball.bounce_after). The first one that
    maps onto the far half (with up to 1.5 m for long balls: the opponent's hit, a ball in the air,
    projects further back) is the bounce. Returns depth from the far baseline, side (thirds of the
    singles court, x + = to her right), direction relative to where she hit from, and whether it
    was in."""
    for x, y, f in candidates or []:
        cx, cy = to_court(H, np.array([[x, y]]))[0]
        if NET - 0.3 <= cy <= LENGTH + 1.5 and abs(cx) <= DOUBLES_HALF + 1.5:
            out = {"shot_bounce_m": [round(float(cx), 2), round(float(cy), 2)],
                   "shot_depth_m": round(float(LENGTH - cy), 2),               # from the far baseline (− = long)
                   "shot_in": bool(abs(cx) <= SINGLES_HALF + 0.03 and NET <= cy <= LENGTH + 0.03),
                   "impact_to_shot_bounce_s": round((f - impact_frame) / fps, 3)}
            side = "centro" if abs(cx) <= SINGLES_HALF / 3 else ("derecha" if cx > 0 else "izquierda")
            out["shot_side"] = side
            if contact_x is not None and abs(contact_x) > 1.0 and side != "centro":
                # from her forehand/backhand corner: same side of the court = down the line
                out["shot_direction"] = "paralela" if (cx > 0) == (contact_x > 0) else "cruzada"
            elif side == "centro":
                out["shot_direction"] = "al centro"
            return out
    return {}


def net_row(H: np.ndarray, x: float = 0.0) -> float:
    """Image row of the net line at court x (feet of the far player are always above it)."""
    p = np.array([x, NET, 1.0]) @ H.T
    return float(p[1] / p[2])


def pick_far_player(boxes: np.ndarray, H: np.ndarray) -> np.ndarray | None:
    """The person standing in the far half (feet mapped by the homography), nearest the centre line."""
    if not len(boxes):
        return None
    feet = to_court(H, np.c_[(boxes[:, 0] + boxes[:, 2]) / 2, boxes[:, 3]])
    ok = (feet[:, 1] > NET + 0.5) & (feet[:, 1] < LENGTH + 8) & (np.abs(feet[:, 0]) < DOUBLES_HALF + 2.5)
    if not ok.any():
        return None
    idx = np.flatnonzero(ok)
    return boxes[idx[np.argmin(np.abs(feet[idx, 0]))]]


def far_roi(H: np.ndarray, frame_shape, behind_m=7.0, side_m=4.0, player_px_frac=0.14) -> tuple:
    """Image region of the far half of the court plus where the far player can stand (behind the
    baseline, out wide) and her height above her feet. Points that project behind the camera are
    ignored; if the region degenerates, the band above the net row is used."""
    h, w = frame_shape[:2]
    pts = np.array([[-DOUBLES_HALF - side_m, NET], [DOUBLES_HALF + side_m, NET],
                    [-DOUBLES_HALF - side_m, LENGTH + behind_m], [DOUBLES_HALF + side_m, LENGTH + behind_m],
                    [-DOUBLES_HALF - side_m, LENGTH], [DOUBLES_HALF + side_m, LENGTH]])
    p = np.c_[pts, np.ones(len(pts))] @ H.T
    ok = p[:, 2] > 1e-9
    xy = p[ok, :2] / p[ok, 2:]
    row = min(float(h), net_row(H) + 0.03 * h)
    if len(xy) >= 3:
        x0, x1 = np.clip([xy[:, 0].min(), xy[:, 0].max()], 0, w)
        y0 = max(0.0, xy[:, 1].min() - player_px_frac * h)
        if x1 - x0 > 0.2 * w and row - y0 > 0.1 * h:
            return int(x0), int(y0), int(x1), int(row)
    return 0, 0, int(w), int(row)


def player_frame_H(H: np.ndarray, side: str) -> np.ndarray:
    """Homography from the player's own court frame (her baseline at y = 0, x + = her right) to
    the image. For the far player (facing the camera) both axes are flipped, so every court metric
    (stance, position, bounce, where her shot lands) reads the same at either end."""
    if side != "far":
        return H
    M = np.array([[-1.0, 0, 0], [0, -1.0, LENGTH], [0, 0, 1.0]])
    return H @ M
