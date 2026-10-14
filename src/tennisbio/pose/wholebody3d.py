"""RTMW3D: 133 whole-body keypoints (body, feet, both hands) with depth, from a person box.

Used only in the frames around each stroke, for the hand/forearm evidence of the racket face, the
3D trunk turn and the practice side-view 3D measures.
Model: RTMW3D-x (ONNX, 384×288), downloaded on first use by rtmlib.

Depth decoding. The model's three SimCC outputs have 2 bins per pixel (split ratio 2) along x
(width 288 → 576 bins), y (height 384 → 768) and z: depth has 576 bins, i.e. the width's 288 px
(mmpose's SimCC3DLabel with input_size (288, 384, 288), z_range 2.1744869). rtmlib's RTMPose3d
divides the depth location by half the model input *height* (192) instead of half the depth axis
(144), so its depth differences come out × 288/384 = × 0.75 (and offset). This module decodes
the raw outputs itself (decode_simcc3d), reading the bin counts from the outputs, so every user
of WholeBody3D gets depth in metres as the model was trained.
"""
import numpy as np

from .estimator import _ort_session

RTMW3D_URL = ("https://huggingface.co/Soykaf/RTMW3D-x/resolve/main/onnx/"
              "rtmw3d-x_8xb64_cocktail14-384x288-b0a0eab7_20240626.onnx")
Z_RANGE = 2.1744869      # m, RTMW3D's SimCC3DLabel z_range (mmpose config; rtmlib's default too)
SIMCC_SPLIT = 2.0        # SimCC bins per input pixel


def depth_m(z_px: np.ndarray, z_bins: int, z_range: float = Z_RANGE, split: float = SIMCC_SPLIT) -> np.ndarray:
    """Depth in metres (+ away from the camera, 0 = middle of the depth axis) from the SimCC depth
    location in model pixels (argmax / split) and the number of depth bins of the output."""
    half = z_bins / split / 2.0
    return (np.asarray(z_px, float) / half - 1.0) * z_range


def decode_simcc3d(simcc_x: np.ndarray, simcc_y: np.ndarray, simcc_z: np.ndarray, center=None, scale=None,
                   z_range: float = Z_RANGE, split: float = SIMCC_SPLIT):
    """Raw RTMW3D outputs (N, K, bins) → (kp3d (N, K, 3): x, y in model-crop px, z depth in m;
    scores (N, K); kp2d (N, K, 2) in image px when center/scale of the crop are given, else None).

    Same as rtmlib's RTMPose3d.postprocess (argmax per axis, score = min of the x/y maxima, x and y
    unchanged) except the depth, decoded with the depth axis's own bin count (depth_m)."""
    from rtmlib.tools.pose_estimation.post_processings import get_simcc_maximum3d

    locs, scores = get_simcc_maximum3d(simcc_x, simcc_y, simcc_z)
    k = locs / split
    k[..., 2] = depth_m(k[..., 2], simcc_z.shape[-1], z_range, split)
    k2 = None
    if center is not None and scale is not None:
        size = np.array([simcc_x.shape[-1], simcc_y.shape[-1]], float) / split    # model input (w, h)
        k2 = k[..., :2] / size * scale + center - 0.5 * scale
    return k, scores, k2


class WholeBody3D:
    def __init__(self, model: str = RTMW3D_URL, device: str = "cpu"):
        from rtmlib import RTMPose3d

        backend = "openvino" if device == "openvino" else "onnxruntime"
        self.model = RTMPose3d(model, model_input_size=(288, 384), backend=backend, device="cpu")
        if device == "dml":
            self.model.session = _ort_session(self.model.onnx_model, device)

    def __call__(self, frame: np.ndarray, box: np.ndarray):
        """(kp3d (133, 3): x, y in model-crop pixels, z depth in m (+ away from camera); scores (133,);
        kp2d (133, 2)). rtmlib's preprocessing and inference, our decoding (decode_simcc3d)."""
        img, center, scale = self.model.preprocess(frame, list(box))
        sx, sy, sz = self.model.inference(img)[:3]
        k3, sc, k2 = decode_simcc3d(sx, sy, sz, center, scale, self.model.z_range)
        return k3[0], sc[0], k2[0]
