"""NMS that keeps nothing (Gauff, 28-10: a stroke lost to IndexError) gives no people, not an error."""
import numpy as np

from tennisbio.pose import yolo_onnx


def test_pose_with_empty_nms(monkeypatch):
    m = yolo_onnx.YoloOnnx.__new__(yolo_onnx.YoloOnnx)
    m.size = 64
    anchor = np.zeros((56, 1), np.float32)
    anchor[:5, 0] = [32, 32, 10, 20, 0.9]
    m.infer = lambda x: [anchor[None]]
    monkeypatch.setattr(yolo_onnx.cv2.dnn, "NMSBoxes", lambda *a: ())
    b, s, k, c = m.pose(np.zeros((64, 64, 3), np.uint8))
    assert b.shape == (0, 4) and len(s) == 0 and k.shape == (0, 17, 2) and c.shape == (0, 17)
