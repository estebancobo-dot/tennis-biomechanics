import cv2
import numpy as np

from tennisbio.court import LINES, camera_pitch_deg, fit_court


def broadcast_H(pitch=20.0, f=1400.0, w=1920, h=1080, cam=(0.0, -12.0, 7.5)):
    """Ground (x, y) → image homography of a pinhole camera behind the near baseline."""
    t = np.radians(pitch)
    right, fwd = np.array([1.0, 0, 0]), np.array([0, np.cos(t), -np.sin(t)])
    up = np.cross(right, fwd)
    R = np.stack([right, -up, fwd])
    K = np.array([[f, 0, w / 2], [0, f, h / 2], [0, 0, 1]])
    C = np.array(cam)
    return K @ np.c_[R[:, 0], R[:, 1], -R @ C]


def render(H, w=1920, h=1080, seed=0):
    rng = np.random.default_rng(seed)
    img = np.full((h, w, 3), (60, 110, 50), np.uint8)
    court = np.array([[-6.5, -3], [6.5, -3], [6.5, 27], [-6.5, 27]], float)
    pc = (np.c_[court, np.ones(4)] @ H.T)
    cv2.fillPoly(img, [(pc[:, :2] / pc[:, 2:]).astype(np.int32)], (150, 95, 45))
    for p, q in LINES.values():
        a, b = (H @ [*p, 1]), (H @ [*q, 1])
        cv2.line(img, tuple((a[:2] / a[2]).astype(int)), tuple((b[:2] / b[2]).astype(int)), (245, 245, 245), 4)
    cv2.rectangle(img, (900, 700), (1000, 1000), (40, 40, 200), -1)          # a player occluding lines
    noise = rng.normal(0, 6, img.shape)
    return np.clip(img + noise, 0, 255).astype(np.uint8)


def test_fit_recovers_court_and_pitch():
    H = broadcast_H(20.0)
    fit = fit_court(render(H))
    assert fit is not None and fit.score > 0.6
    corners = np.array([[-5.485, 0], [5.485, 0], [-5.485, 23.77], [5.485, 23.77]])
    true = np.c_[corners, np.ones(4)] @ H.T
    true = true[:, :2] / true[:, 2:]
    assert np.abs(fit.to_image(corners) - true).max() < 6        # pixels
    assert abs(camera_pitch_deg(fit, (1080, 1920)) - 20.0) < 2.5
