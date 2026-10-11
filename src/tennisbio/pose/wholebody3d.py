"""RTMW3D: 133 whole-body keypoints (body, feet, both hands) with depth, from a person box.

Used only in the frames around each stroke, for the hand/forearm evidence of the racket face.
Model: RTMW3D-x (ONNX, 384×288), downloaded on first use by rtmlib.
"""
import numpy as np

from .estimator import _ort_session

RTMW3D_URL = ("https://huggingface.co/Soykaf/RTMW3D-x/resolve/main/onnx/"
              "rtmw3d-x_8xb64_cocktail14-384x288-b0a0eab7_20240626.onnx")


class WholeBody3D:
    def __init__(self, model: str = RTMW3D_URL, device: str = "cpu"):
        from rtmlib import RTMPose3d

        backend = "openvino" if device == "openvino" else "onnxruntime"
        self.model = RTMPose3d(model, model_input_size=(288, 384), backend=backend, device="cpu")
        if device == "dml":
            self.model.session = _ort_session(self.model.onnx_model, device)

    def __call__(self, frame: np.ndarray, box: np.ndarray):
        """(kp3d (133, 3): x, y in model-crop pixels, z depth (+ away from camera); scores (133,); kp2d (133, 2))."""
        k3, sc, _, k2 = self.model(frame, bboxes=[list(box)])
        return k3[0], sc[0], k2[0]
