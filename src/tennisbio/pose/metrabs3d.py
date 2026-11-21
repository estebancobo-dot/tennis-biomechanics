"""MeTRAbs (Sárándi et al.; isarandi/metrabs, EfficientNetV2-L 384 px, 28 datasets): absolute 3D human pose from one
calibrated view (21-11, #309: on CalTennis' multi-view reference the trunk's turn within 15° in 77.8 % of 5104 frames
against MotionAGFormer's 36.8 %, medir_3d_metrabs_c; from the candidates to the pose for its integrated test,
`trunk3d.model: metrabs`, tennisbio.trunk3d; candidates.metrabs3d keeps the name for the bench). Its models are for non-commercial use only (the licences of its
training data), as this personal project is; no registration is needed (TensorFlow Hub).

It reads the camera's intrinsics and gives the joints in the camera's frame (mm): the shoulders and hips' directions
about the vertical come from them and the camera's rotation, with no depth guessed from the image size."""
from __future__ import annotations

import numpy as np

# the authors' own public download (where their short link «metrabs_l» points; 708 MB, a TensorFlow Hub module)
URL = "https://omnomnom.vision.rwth-aachen.de/data/metrabs/metrabs_eff2l_y4_384px_800k_28ds.tar.gz"
SKELETON = "coco_19"
TRUNK = ("lsho", "rsho", "lhip", "rhip")      # the order of candidates.caltennis.COCO_TRUNK (left/right shoulder, hip)


class Metrabs:
    def __init__(self, url: str = URL, num_aug: int = 1):
        import tensorflow as tf
        import tensorflow_hub as hub

        for g in tf.config.list_physical_devices("GPU"):   # beside ONNX Runtime on the same GPU: memory as needed
            try:
                tf.config.experimental.set_memory_growth(g, True)
            except (RuntimeError, ValueError):  # esperado: already set in this process (a second model)
                pass
        self.tf, self.m, self.num_aug = tf, hub.load(url), num_aug
        names = [n.decode() if isinstance(n, bytes) else str(n)
                 for n in self.m.per_skeleton_joint_names[SKELETON].numpy()]
        self.idx = [names.index(n) for n in TRUNK]

    def trunk(self, frame_bgr: np.ndarray, box_xyxy, K: np.ndarray) -> np.ndarray:
        """(4, 3): the left/right shoulder and hip in the camera's frame (mm), for the person in the box."""
        tf = self.tf
        x0, y0, x1, y1 = (float(v) for v in box_xyxy[:4])
        pred = self.m.estimate_poses(tf.convert_to_tensor(np.ascontiguousarray(frame_bgr[..., ::-1])),
                                     tf.constant([[x0, y0, x1 - x0, y1 - y0]], tf.float32),
                                     intrinsic_matrix=tf.constant(np.asarray(K, np.float32)), skeleton=SKELETON,
                                     num_aug=self.num_aug)
        return pred["poses3d"].numpy()[0][self.idx]
