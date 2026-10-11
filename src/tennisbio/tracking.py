"""Follow one player through the detections of every frame.

Frame to frame the target is the detection that best overlaps the previous box. After a cut,
when nothing overlaps, it is re-acquired only by appearance (colour histogram) similar to the
reference; otherwise the frame is left without target rather than jumping to someone else.
"""
import numpy as np


def iou(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """IoU between one box a (4,) and boxes b (N, 4), xyxy."""
    x0 = np.maximum(a[0], b[:, 0]); y0 = np.maximum(a[1], b[:, 1])
    x1 = np.minimum(a[2], b[:, 2]); y1 = np.minimum(a[3], b[:, 3])
    inter = np.clip(x1 - x0, 0, None) * np.clip(y1 - y0, 0, None)
    area = lambda r: (r[..., 2] - r[..., 0]) * (r[..., 3] - r[..., 1])
    return inter / (area(a) + area(b) - inter + 1e-9)


def hist_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Bhattacharyya coefficient between histogram a (D,) and histograms b (N, D)."""
    return np.sum(np.sqrt(np.clip(a, 0, None) * np.clip(b, 0, None)), axis=-1)


def track_target(boxes: list[np.ndarray], feats: list[np.ndarray], init_box: np.ndarray,
                 min_iou=0.3, min_sim=0.8, ref_frames=15) -> np.ndarray:
    """Index of the target detection in each frame (-1 when absent or uncertain)."""
    out = np.full(len(boxes), -1)
    last, ref, ref_n = np.asarray(init_box, float), None, 0
    for t, (b, f) in enumerate(zip(boxes, feats)):
        if len(b) == 0:
            continue
        ov = iou(last, b)
        j = int(np.argmax(ov))
        if ov[j] >= min_iou:
            ok = ref is None or hist_similarity(ref / ref_n, f[j:j + 1])[0] >= min_sim - 0.15
        else:  # lost (cut or occlusion): re-acquire by appearance and similar size only
            if ref is None:
                continue
            sim = hist_similarity(ref / ref_n, f)
            h_last = last[3] - last[1]
            size_ok = np.abs((b[:, 3] - b[:, 1]) / h_last - 1) < 0.5
            cand = np.flatnonzero((sim >= min_sim) & size_ok)
            if not len(cand):
                continue
            j = int(cand[np.argmax(sim[cand])])
            ok = True
        if ok:
            out[t], last = j, b[j]
            if ref_n < ref_frames:
                ref = f[j].copy() if ref is None else ref + f[j]
                ref_n += 1
    return out
