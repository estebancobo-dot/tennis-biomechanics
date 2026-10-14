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
# shots; then lines tinted by the surface (clay); last, lines in the shade (a stand's shadow over
# part of the court, late afternoon, overcast): a white line at half the light is darker than the
# absolute bars above but still stands out from its surroundings (top-hat) and stays unsaturated
LINE_PARAMS = [(25, 70, 150), (15, 70, 130), (20, 115, 140), (20, 70, 60)]


def _line_features(frame: np.ndarray):
    """Top-hat contrast, saturation and brightness of a frame (shared by all line-mask settings)."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15)))
    return tophat, hsv[..., 1], hsv[..., 2]


def _threshold(features, tophat_min, max_sat, min_val) -> np.ndarray:
    tophat, sat, val = features
    return ((tophat > tophat_min) & (sat < max_sat) & (val > min_val)).astype(np.uint8)


def white_lines(frame: np.ndarray, tophat_min=25, max_sat=70, min_val=150) -> np.ndarray:
    """Binary mask of thin bright low-saturation structures (court lines)."""
    return _threshold(_line_features(frame), tophat_min, max_sat, min_val)


class LineMasks:
    """The line masks of one frame for each LINE_PARAMS setting, computed once on demand and
    shared by the check of known homographies and the full search: (mask, dilated, integral of
    the dilated mask)."""

    def __init__(self, frame: np.ndarray):
        self.shape = frame.shape[:2]
        self._frame, self._features, self._m = frame, None, {}

    def __len__(self):
        return len(LINE_PARAMS)

    def __getitem__(self, i: int):
        if i not in self._m:
            if self._features is None:
                self._features = _line_features(self._frame)
            mask = _threshold(self._features, *LINE_PARAMS[i])
            dil = dilate_lines(mask)
            self._m[i] = (mask, dil, cv2.integral(dil))
        return self._m[i]


def _intersect(l1, l2):
    p = np.cross(l1, l2)
    return None if abs(p[2]) < 1e-9 else p[:2] / p[2]


def _merge(segs, kind):
    """Group collinear segments (same angle and offset) into infinite lines, longest first."""
    segs = np.asarray(segs, float).reshape(-1, 4)
    if not len(segs):
        return []
    x0, y0, x1, y1 = segs.T
    a, b = y1 - y0, x0 - x1
    n = np.hypot(a, b)
    Ls = np.c_[a / n, b / n, -(a * x0 + b * y0) / n]                  # a x + b y + c = 0 per segment
    flip = (Ls[:, 1] < 0) | ((np.abs(Ls[:, 1]) < 1e-9) & (Ls[:, 0] < 0))
    Ls[flip] = -Ls[flip]
    lengths = np.hypot(x1 - x0, y1 - y0)
    angs = np.arctan2(Ls[:, 1], Ls[:, 0])
    tol = np.radians(2)
    # greedy grouping in segment order: a segment joins the first group (by its founding line)
    # of the same angle and offset; the inner comparison is vectorised over the groups
    g_idx, g_len = np.empty(len(segs), int), np.empty(len(segs))
    k = 0
    for i in range(len(segs)):
        if k:
            m = np.flatnonzero((np.abs(angs[i] - angs[g_idx[:k]]) < tol) & (np.abs(Ls[i, 2] - Ls[g_idx[:k], 2]) < 8))
            if len(m):
                g_len[m[0]] += lengths[i]
                continue
        g_idx[k], g_len[k] = i, lengths[i]
        k += 1
    order = sorted(range(k), key=lambda j: -g_len[j])                # stable, as list.sort
    return [Ls[g_idx[j]] for j in order]


def _model_samples(samples=60) -> np.ndarray:
    t = np.linspace(0, 1, samples)[:, None]
    return np.vstack([np.c_[(1 - t) * np.array(p) + t * np.array(q), np.ones(samples)] for p, q in LINES.values()])


MODEL_PTS = _model_samples()


def dilate_lines(mask: np.ndarray) -> np.ndarray:
    return cv2.dilate(mask, np.ones((5, 5), np.uint8))


def score_homography(H_court_to_img: np.ndarray, mask: np.ndarray, dilated: np.ndarray | None = None,
                     integral: np.ndarray | None = None) -> float:
    """Fraction of points sampled along all model lines that fall on (dilated) white pixels,
    minus the share of white pixels of the area those points cover (on crowd, logos or a
    textured surface almost any line "hits", which says nothing)."""
    dil = dilate_lines(mask) if dilated is None else dilated
    return float(score_many(np.asarray(H_court_to_img, float)[None], dil, integral)[0])


def score_many(Hs: np.ndarray, dilated: np.ndarray, integral: np.ndarray | None = None) -> np.ndarray:
    """score_homography of K homographies (K, 3, 3) at once on one dilated line mask. The white
    share of each bounding box comes from the integral image (one lookup instead of averaging
    the box), so the result is the same as averaging the pixels."""
    dil = dilated
    h, w = dil.shape
    integ = cv2.integral(dil) if integral is None else integral
    Hs = np.asarray(Hs, float).reshape(-1, 3, 3)
    out = np.zeros(len(Hs))
    if not len(Hs):
        return out
    img = np.einsum("nj,kij->kni", MODEL_PTS, Hs)                     # (K, N, 3)
    front = (img[..., 2] > 0).all(1)                                  # any point behind the camera → 0
    with np.errstate(divide="ignore", invalid="ignore"):
        xy = img[..., :2] / img[..., 2:]
    inside = front[:, None] & (xy[..., 0] >= 0) & (xy[..., 0] < w) & (xy[..., 1] >= 0) & (xy[..., 1] < h)
    xi = np.where(inside, xy[..., 0], 0).astype(int)                 # inside ⇒ ≥ 0: int() truncation = floor
    yi = np.where(inside, xy[..., 1], 0).astype(int)
    hits = (dil[yi, xi] * inside).sum(1) / MODEL_PTS.shape[0]
    n_in = inside.sum(1)
    big = np.iinfo(np.int64).max
    x0 = np.where(inside, xi, big).min(1)
    y0 = np.where(inside, yi, big).min(1)
    x1 = np.where(inside, xi, -1).max(1) + 1
    y1 = np.where(inside, yi, -1).max(1) + 1
    box = n_in >= 3
    x0, y0, x1, y1 = (np.where(box, v, 0) for v in (x0, y0, x1, y1))
    s = (integ[y1, x1] - integ[y0, x1] - integ[y1, x0] + integ[y0, x0]).astype(float)
    area = np.maximum((x1 - x0) * (y1 - y0), 1)
    density = np.where(box, s / area, 0.0)                            # white share of the court's bounding box
    return np.where(front, hits - density, 0.0)


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


_CORNERS = np.array([[-W_DOUBLES / 2, 0, 1], [W_DOUBLES / 2, 0, 1],
                     [W_DOUBLES / 2, LENGTH, 1], [-W_DOUBLES / 2, LENGTH, 1]])


def _maybe_plausible(Hs: np.ndarray, shape) -> np.ndarray:
    """Vectorised necessary conditions of `plausible` (all but convexity and area) for (K, 3, 3)
    homographies: a cheap early reject; the survivors still go through `plausible` itself."""
    h, w = shape[:2]
    c = np.einsum("nj,kij->kni", _CORNERS, Hs)
    ok = (c[..., 2] > 0).all(1)
    with np.errstate(divide="ignore", invalid="ignore"):
        q = c[..., :2] / c[..., 2:]
    x, y = q[..., 0], q[..., 1]
    ok &= ~((x < -0.3 * w) | (x > 1.3 * w) | (y < -0.2 * h) | (y > 1.25 * h)).any(1)
    ok &= np.linalg.norm(q - np.roll(q, 1, axis=1), axis=2).min(1) >= 0.08 * min(w, h)
    near_y, far_y = y[:, :2].mean(1), y[:, 2:].mean(1)
    near_w, far_w = np.abs(x[:, 1] - x[:, 0]), np.abs(x[:, 2] - x[:, 3])
    ok &= ((near_y > far_y + 0.1 * h) & (x[:, 1] > x[:, 0]) & (0.15 * near_w < far_w) & (far_w < 0.95 * near_w)
           & (near_w > 0.25 * w) & (far_y > -0.05 * h) & (near_y > 0.45 * h))
    return ok & np.isfinite(q).all((1, 2))


def _perspective_many(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """cv2.getPerspectiveTransform for many 4-point pairs at once: (K, 4, 2) × (K, 4, 2) → (K, 3, 3)
    (same 8×8 linear system, h33 = 1)."""
    K = len(src)
    A = np.zeros((K, 8, 8))
    b = np.zeros((K, 8))
    X, Y = src[..., 0], src[..., 1]
    u, v = dst[..., 0], dst[..., 1]
    A[:, :4, 0], A[:, :4, 1], A[:, :4, 2] = X, Y, 1
    A[:, :4, 6], A[:, :4, 7] = -X * u, -Y * u
    A[:, 4:, 3], A[:, 4:, 4], A[:, 4:, 5] = X, Y, 1
    A[:, 4:, 6], A[:, 4:, 7] = -X * v, -Y * v
    b[:, :4], b[:, 4:] = u, v
    H = np.ones((K, 9))
    good = np.abs(np.linalg.det(A)) > 1e-12
    if good.any():
        H[good, :8] = np.linalg.solve(A[good], b[good][..., None])[..., 0]
    H[~good] = np.nan
    return H.reshape(K, 3, 3)


# the court rectangles a pair of image "horizontal" lines × a pair of sidelines may be: 6 × 6, in
# the order of the original nested search (near line, far line) × (left line, right line)
_MODEL_QUADS = np.array([[[xl, yn], [xr, yn], [xl, yf], [xr, yf]]
                         for (_, yn), (_, yf) in combinations(sorted(HORIZONTAL.items(), key=lambda kv: kv[1]), 2)
                         for (_, xl), (_, xr) in combinations(sorted(SIDELINES.items(), key=lambda kv: kv[1]), 2)], float)


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


def fit_court(frame: np.ndarray, max_lines=6, good=0.8, min_score=0.5, masks: LineMasks | None = None) -> CourtFit | None:
    """Best court homography; tries stricter line masks first, then more permissive ones."""
    masks = LineMasks(frame) if masks is None else masks
    best = None
    for i in range(len(masks)):
        mask, dil, integ = masks[i]
        fit = _fit_with(frame, mask, max_lines, dil, integ)
        if fit is not None and (best is None or fit.score > best.score):
            best = fit
        if best is not None and best.score >= good:
            break
    return best if best is not None and best.score >= min_score else None


def match_known(frame: np.ndarray, known, min_score=0.5, masks: LineMasks | None = None) -> CourtFit | None:
    """The best of the homographies already found in this video (a broadcast uses a few camera
    presets) when it fits this frame as well as a fresh fit must (score ≥ min_score on one of the
    line masks fit_court tries, in the same order); None when none does and a full search is needed."""
    Hs = np.array([np.asarray(getattr(k, "H", k), float) for k in known]).reshape(-1, 3, 3)
    if not len(Hs):
        return None
    masks = LineMasks(frame) if masks is None else masks
    Hs = Hs[[plausible(H, masks.shape) for H in Hs]]
    if not len(Hs):
        return None
    for i in range(len(masks)):
        _, dil, integ = masks[i]
        sc = score_many(Hs, dil, integ)
        j = int(np.argmax(sc))
        if sc[j] >= min_score:
            return CourtFit(Hs[j].copy(), float(sc[j]))
    return None


def _fit_with(frame: np.ndarray, mask: np.ndarray, max_lines=6, dil: np.ndarray | None = None,
              integ: np.ndarray | None = None) -> CourtFit | None:
    dil = dilate_lines(mask) if dil is None else dil
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
    quads = []
    for h2 in combinations(horiz, 2):
        h2 = sorted(h2, key=lambda L: -(-L[2] / L[1]))            # lower line in the image first (nearer)
        for s2 in combinations(sides, 2):
            pts = [_intersect(hl, sl) for hl in h2 for sl in s2]
            if any(p is None for p in pts):
                continue
            pts = np.array(pts)
            if pts[0, 0] > pts[1, 0]:                                # left sideline first
                pts = pts[[1, 0, 3, 2]]
            quads.append(pts)
    if not quads:
        return None
    # every image quadrilateral × every court rectangle, in the order of the former nested loops
    # (the first of equal scores wins, as before); solved, pre-filtered and scored in batches
    n_m = len(_MODEL_QUADS)
    img_q = np.repeat(np.array(quads, np.float32).astype(float), n_m, axis=0)
    court_q = np.tile(_MODEL_QUADS.astype(np.float32).astype(float), (len(quads), 1, 1))
    Hs = _perspective_many(court_q, img_q)
    cand = np.flatnonzero(_maybe_plausible(Hs, (h, w)))
    cand = cand[[plausible(Hs[k], (h, w)) for k in cand]] if len(cand) else cand
    if not len(cand):
        return None
    sc = score_many(Hs[cand], dil, integ)
    j = int(np.argmax(sc))
    return CourtFit(Hs[cand[j]], float(sc[j]))


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
