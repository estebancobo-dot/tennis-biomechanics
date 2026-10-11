"""Drawing: skeleton and racket overlays, and the 8-moment strip of a stroke."""
import cv2
import numpy as np

from .phases import LABELS_ES, PHASES
from .racket import RacketObs
from .skeleton import BONES, Skeleton

SIDE_BGR = {"left": (245, 176, 79), "right": (67, 159, 255), "center": (143, 216, 123)}
RACKET_BGR = (210, 95, 255)


def draw_pose(img: np.ndarray, kp: np.ndarray, sk: Skeleton, thickness=2) -> np.ndarray:
    for a, b, side in BONES:
        p, q = kp[sk[a]], kp[sk[b]]
        if np.isnan(p).any() or np.isnan(q).any():
            continue
        cv2.line(img, tuple(map(int, p)), tuple(map(int, q)), SIDE_BGR[side], thickness, cv2.LINE_AA)
    for j in range(len(kp)):
        if not np.isnan(kp[j]).any() and j >= 5:
            cv2.circle(img, tuple(map(int, kp[j])), thickness + 1, (20, 20, 20), -1, cv2.LINE_AA)
    return img


def draw_racket(img: np.ndarray, r: RacketObs, thickness=2) -> np.ndarray:
    cv2.line(img, tuple(map(int, r.butt)), tuple(map(int, r.head)), RACKET_BGR, thickness, cv2.LINE_AA)
    cv2.circle(img, tuple(map(int, r.head)), thickness + 3, RACKET_BGR, thickness, cv2.LINE_AA)
    return img


def crop_around(img: np.ndarray, box: np.ndarray, size=(260, 320), pad=0.35) -> np.ndarray:
    """Crop centred on a person box with padding, resized to `size` (w, h)."""
    x0, y0, x1, y1 = box
    h = (y1 - y0) * (1 + 2 * pad)
    w = h * size[0] / size[1]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    M = np.float32([[size[0] / w, 0, size[0] / 2 - cx * size[0] / w], [0, size[1] / h, size[1] / 2 - cy * size[1] / h]])
    return cv2.warpAffine(img, M, size, borderMode=cv2.BORDER_CONSTANT, borderValue=(16, 18, 22))


def label(img: np.ndarray, lines: list[str], top=True) -> np.ndarray:
    h = 18 * len(lines) + 8
    y0 = 0 if top else img.shape[0] - h
    over = img.copy()
    cv2.rectangle(over, (0, y0), (img.shape[1], y0 + h), (12, 14, 18), -1)
    img[:] = cv2.addWeighted(over, 0.75, img, 0.25, 0)
    for k, t in enumerate(lines):
        cv2.putText(img, t, (6, y0 + 18 + 18 * k), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (58, 240, 212) if k == 0 and top else (235, 238, 240), 1, cv2.LINE_AA)
    return img


def strip(tiles: list[np.ndarray], header: str) -> np.ndarray:
    row = np.hstack(tiles)
    bar = np.full((34, row.shape[1], 3), (12, 14, 18), np.uint8)
    cv2.putText(bar, header, (8, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (235, 238, 240), 1, cv2.LINE_AA)
    return np.vstack([bar, row])


PHASE_TITLES = [f"{k + 1} {LABELS_ES[p]}" for k, p in enumerate(PHASES)]
