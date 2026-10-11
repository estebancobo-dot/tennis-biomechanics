"""Court line detection and image↔court homography for the main broadcast camera.

Court frame (metres): x across the court (0 = centre line, + to the right of the image),
y along the court from the near baseline (0) to the far baseline (23.77), on the ground plane.

Method: white-line pixels → Hough segments → the two longest near-horizontal families give
baseline / service-line candidates and the converging families give sideline candidates; each
combination of 2 "horizontal" × 2 "sideline" lines is mapped to the court model and scored by
how many projected model lines land on white pixels. The best homography wins.
"""
from dataclasses import dataclass
from itertools import combinations

import cv2
import numpy as np

W_DOUBLES, W_SINGLES = 10.97, 8.23
LENGTH, SERVICE = 23.77, 6.40          # service line distance from the net
NET_Y = LENGTH / 2

# model lines as pairs of court points (x, y)
LINES = {
    "near_baseline": ((-W_DOUBLES / 2, 0), (W_DOUBLES / 2, 0)),
    "far_baseline": ((-W_DOUBLES / 2, LENGTH), (W_DOUBLES / 2, LENGTH)),
    "near_service": ((-W_SINGLES / 2, NET_Y - SERVICE), (W_SINGLES / 2, NET_Y - SERVICE)),
    "far_service": ((-W_SINGLES / 2, NET_Y + SERVICE), (W_SINGLES / 2, NET_Y + SERVICE)),
    "left_doubles": ((-W_DOUBLES / 2, 0), (-W_DOUBLES / 2, LENGTH)),
    "right_doubles": ((W_DOUBLES / 2, 0), (W_DOUBLES / 2, LENGTH)),
    "left_singles": ((-W_SINGLES / 2, 0), (-W_SINGLES / 2, LENGTH)),
    "right_singles": ((W_SINGLES / 2, 0), (W_SINGLES / 2, LENGTH)),
    "centre_service": ((0, NET_Y - SERVICE), (0, NET_Y + SERVICE)),
}
HORIZONTAL = {"near_baseline": 0.0, "near_service": NET_Y - SERVICE, "far_service": NET_Y + SERVICE, "far_baseline": LENGTH}
SIDELINES = {"left_doubles": -W_DOUBLES / 2, "left_singles": -W_SINGLES / 2,
             "right_singles": W_SINGLES / 2, "right_doubles": W_DOUBLES / 2}


# (top-hat contrast, max saturation, min brightness): strict first; then faint thin lines in wide
# shots; then lines tinted by the surface (clay)
LINE_PARAMS = [(25, 70, 150), (15, 70, 130), (20, 115, 140)]


def white_lines(frame: np.ndarray, tophat_min=25, max_sat=70, min_val=150) -> np.ndarray:
    """Binary mask of thin bright low-saturation structures (court lines)."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15)))
    m = (tophat > tophat_min) & (hsv[..., 1] < max_sat) & (hsv[..., 2] > min_val)
    return m.astype(np.uint8)


def _line_params(seg):
    x0, y0, x1, y1 = seg
    a, b = y1 - y0, x0 - x1
    n = np.hypot(a, b)
    return np.array([a / n, b / n, -(a * x0 + b * y0) / n])     # a x + b y + c = 0


def _intersect(l1, l2):
    p = np.cross(l1, l2)
    return None if abs(p[2]) < 1e-9 else p[:2] / p[2]


def _merge(segs, kind):
    """Group collinear segments (same angle and offset) into infinite lines, longest first."""
    groups = []
    for s in segs:
        L = _line_params(s)
        if L[1] < 0 or (abs(L[1]) < 1e-9 and L[0] < 0):
            L = -L
        length = np.hypot(s[2] - s[0], s[3] - s[1])
        for g in groups:
            if abs(np.arctan2(L[1], L[0]) - np.arctan2(g["L"][1], g["L"][0])) < np.radians(2) and abs(L[2] - g["L"][2]) < 8:
                g["len"] += length
                break
        else:
            groups.append({"L": L, "len": length})
    groups.sort(key=lambda g: -g["len"])
    return [g["L"] for g in groups]


def _model_samples(samples=60) -> np.ndarray:
    t = np.linspace(0, 1, samples)[:, None]
    return np.vstack([np.c_[(1 - t) * np.array(p) + t * np.array(q), np.ones(samples)] for p, q in LINES.values()])


MODEL_PTS = _model_samples()


def dilate_lines(mask: np.ndarray) -> np.ndarray:
    return cv2.dilate(mask, np.ones((5, 5), np.uint8))


def score_homography(H_court_to_img: np.ndarray, mask: np.ndarray, dilated: np.ndarray | None = None) -> float:
    """Fraction of points sampled along all model lines that fall on (dilated) white pixels,
    minus the share of white pixels of the area those points cover (on crowd, logos or a
    textured surface almost any line "hits", which says nothing)."""
    dil = dilate_lines(mask) if dilated is None else dilated
    h, w = dil.shape
    img = MODEL_PTS @ H_court_to_img.T
    if np.any(img[:, 2] <= 0):
        return 0.0
    img = img[:, :2] / img[:, 2:]
    inside = (img[:, 0] >= 0) & (img[:, 0] < w) & (img[:, 1] >= 0) & (img[:, 1] < h)
    xy = img[inside].astype(int)
    hits = int(dil[xy[:, 1], xy[:, 0]].sum()) / len(MODEL_PTS)
    if len(xy) < 3:
        return hits
    x0, y0 = xy.min(0)
    x1, y1 = xy.max(0) + 1
    density = float(dil[y0:y1, x0:x1].mean())               # white share of the court's bounding box
    return hits - density


def plausible(H_court_to_img: np.ndarray, shape, min_area=0.04) -> bool:
    """Reject degenerate fits: the doubles court must project in front of the camera as a convex
    quadrilateral of reasonable size, with the near baseline lower and wider than the far one."""
    h, w = shape[:2]
    corners = np.array([[-W_DOUBLES / 2, 0, 1], [W_DOUBLES / 2, 0, 1],
                        [W_DOUBLES / 2, LENGTH, 1], [-W_DOUBLES / 2, LENGTH, 1]]) @ H_court_to_img.T
    if np.any(corners[:, 2] <= 0):
        return False
    q = corners[:, :2] / corners[:, 2:]
    if not cv2.isContourConvex(q.astype(np.float32)):
        return False
    # the whole doubles court stays near the frame (main camera), and no side collapses
    if (q[:, 0] < -0.3 * w).any() or (q[:, 0] > 1.3 * w).any() or (q[:, 1] < -0.2 * h).any() or (q[:, 1] > 1.25 * h).any():
        return False
    if min(np.linalg.norm(q - np.roll(q, 1, axis=0), axis=1)) < 0.08 * min(w, h):
        return False
    if cv2.contourArea(q.astype(np.float32)) < min_area * w * h:
        return False
    near_y, far_y = q[:2, 1].mean(), q[2:, 1].mean()
    near_w, far_w = abs(q[1, 0] - q[0, 0]), abs(q[2, 0] - q[3, 0])
    # broadcast perspective: the far baseline is 15-95 % of the near one, both reasonably wide
    return (near_y > far_y + 0.1 * h and q[1, 0] > q[0, 0] and 0.15 * near_w < far_w < 0.95 * near_w
            and near_w > 0.25 * w and far_y > -0.05 * h and near_y > 0.45 * h)


@dataclass
class CourtFit:
    H: np.ndarray            # court (x, y, 1) → image
    score: float

    @property
    def H_inv(self):
        return np.linalg.inv(self.H)

    def to_court(self, pts_img: np.ndarray) -> np.ndarray:
        p = np.c_[pts_img, np.ones(len(pts_img))] @ self.H_inv.T
        return p[:, :2] / p[:, 2:]

    def to_image(self, pts_court: np.ndarray) -> np.ndarray:
        p = np.c_[pts_court, np.ones(len(pts_court))] @ self.H.T
        return p[:, :2] / p[:, 2:]


def fit_court(frame: np.ndarray, max_lines=6, good=0.8, min_score=0.5) -> CourtFit | None:
    """Best court homography; tries stricter line masks first, then more permissive ones."""
    best = None
    for params in LINE_PARAMS:
        fit = _fit_with(frame, white_lines(frame, *params), max_lines)
        if fit is not None and (best is None or fit.score > best.score):
            best = fit
        if best is not None and best.score >= good:
            break
    return best if best is not None and best.score >= min_score else None


def _fit_with(frame: np.ndarray, mask: np.ndarray, max_lines=6) -> CourtFit | None:
    dil = dilate_lines(mask)
    h, w = mask.shape
    segs = cv2.HoughLinesP(mask * 255, 1, np.pi / 360, threshold=60, minLineLength=w // 12, maxLineGap=10)
    if segs is None:
        return None
    segs = segs.reshape(-1, 4).astype(float)        # (N, 1, 4) or (N, 4) depending on the OpenCV version
    ang = np.degrees(np.arctan2(segs[:, 3] - segs[:, 1], segs[:, 2] - segs[:, 0])) % 180
    # broadcast cameras have no roll: court "horizontal" lines are horizontal in the image; the
    # sidelines may be shallow from a low camera, so everything else is a sideline candidate
    horiz = _merge(segs[(ang < 4) | (ang > 176)], "h")[:max_lines]
    sides = _merge(segs[(ang > 6) & (ang < 174)], "s")[:max_lines]
    best = None
    for h2 in combinations(horiz, 2):
        h2 = sorted(h2, key=lambda L: -(-L[2] / L[1]))            # lower line in the image first (nearer)
        for s2 in combinations(sides, 2):
            pts = [_intersect(hl, sl) for hl in h2 for sl in s2]
            if any(p is None for p in pts):
                continue
            pts = np.array(pts)
            if pts[0, 0] > pts[1, 0]:                                # left sideline first
                pts = pts[[1, 0, 3, 2]]
            for (hn, yn), (hf, yf) in combinations(sorted(HORIZONTAL.items(), key=lambda kv: kv[1]), 2):
                for (sl, xl), (sr, xr) in combinations(sorted(SIDELINES.items(), key=lambda kv: kv[1]), 2):
                    court = np.array([[xl, yn], [xr, yn], [xl, yf], [xr, yf]], np.float32)
                    H = cv2.getPerspectiveTransform(court, pts.astype(np.float32))
                    if not plausible(H, (h, w)):
                        continue
                    sc = score_homography(H, mask, dil)
                    if best is None or sc > best.score:
                        best = CourtFit(H, sc)
    return best


def focal_and_rotation(fit: CourtFit, frame_shape, f_default=None):
    """Focal length (px) and the first two rotation columns (court x, court y in camera axes:
    x right, y down, z forward) from the homography, principal point at the image centre.

    Uses the rotation constraints r1·r2 = 0 and |r1| = |r2|; whichever is better conditioned
    (a camera with no roll or yaw makes the first one degenerate)."""
    h, w = frame_shape[:2]
    T = np.array([[1, 0, -w / 2], [0, 1, -h / 2], [0, 0, 1.0]])
    G = T @ fit.H
    g1, g2 = G[:, 0], G[:, 1]
    cands = []
    den = g1[2] * g2[2]
    if abs(den) > 1e-12:
        cands.append((abs(den), -(g1[0] * g2[0] + g1[1] * g2[1]) / den))
    den = g2[2] ** 2 - g1[2] ** 2
    if abs(den) > 1e-12:
        cands.append((abs(den), (g1[0] ** 2 + g1[1] ** 2 - g2[0] ** 2 - g2[1] ** 2) / den))
    good = [c for c in cands if c[1] > 0]
    f = float(np.sqrt(max(good)[1])) if good else (f_default or 1.2 * max(w, h))
    Kinv = np.diag([1 / f, 1 / f, 1.0])
    r1, r2 = Kinv @ g1, Kinv @ g2
    s = 1.0 / np.linalg.norm(r1)
    if r2[2] * s < 0:
        s = -s
    return f, r1 * s, r2 * s


def camera_pitch_deg(fit: CourtFit, frame_shape) -> float:
    """Downward tilt of the camera (degrees) from the court homography."""
    _, _, r2 = focal_and_rotation(fit, frame_shape)
    return float(np.degrees(np.arctan2(-r2[1], r2[2])))
