"""Extraction with Ultralytics YOLO: people (pose) on every frame, rackets (segmentation) on demand.

Optional backend (`uv sync --extra yolo`). Everything detected is cached, so tracking, stroke
detection and racket analysis can be re-run without inference. Rackets are segmented only in
the frames around each stroke (same idea as the two-pass pipeline).
"""
from pathlib import Path

import cv2
import numpy as np

RACKET_CLASS = 38  # "tennis racket" in COCO


def _objects(items: list) -> np.ndarray:
    """1-D object array (np.array would merge equally shaped items into one block)."""
    arr = np.empty(len(items), dtype=object)
    arr[:] = items
    return arr


def appearance(frame: np.ndarray, box: np.ndarray, bins=(8, 4)) -> np.ndarray:
    """Normalised hue/saturation histogram of a person's box, for re-identification."""
    x0, y0, x1, y1 = np.clip(box, 0, [frame.shape[1], frame.shape[0]] * 2).astype(int)
    patch = frame[y0:y1, x0:x1]
    if patch.size == 0:
        return np.zeros(bins[0] * bins[1], np.float32)
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0, 1], None, list(bins), [0, 180, 0, 256]).ravel()
    return (h / (h.sum() + 1e-9)).astype(np.float32)


def extract(video: str | Path, out: str | Path, pose_model="yolo11m-pose.pt", imgsz=960, every=1, progress=True,
            roi: tuple | None = None) -> Path:
    """Run pose on every `every`-th frame and save all people (boxes, keypoints, appearance) to .npz.

    roi: (x0, y0, x1, y1) — run only on that region (e.g. the far half of the court, where the far
    player is too small for the full frame); coordinates are returned in the full frame."""
    from ultralytics import YOLO

    pose = YOLO(pose_model)
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) / every
    boxes, kps, confs, feats = [], [], [], []
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % every:
            i += 1
            continue
        ox = oy = 0
        src = frame
        if roi is not None:
            x0, y0, x1, y1 = (int(v) for v in roi)
            src, ox, oy = frame[y0:y1, x0:x1], x0, y0
        r = pose.predict(src, imgsz=imgsz, conf=0.3, verbose=False)[0]
        b = r.boxes.xyxy.cpu().numpy() + [ox, oy, ox, oy] if len(r.boxes) else np.zeros((0, 4))
        boxes.append(b.astype(np.float32))
        kps.append(r.keypoints.xy.cpu().numpy().astype(np.float32) + [ox, oy] if len(b) else np.zeros((0, 17, 2), np.float32))
        confs.append(r.keypoints.conf.cpu().numpy().astype(np.float32) if len(b) else np.zeros((0, 17), np.float32))
        feats.append(np.array([appearance(frame, bb) for bb in b], np.float32).reshape(len(b), 32))
        i += 1
        if progress and len(boxes) % 100 == 0:
            print(f"{len(boxes)} frames", flush=True)
    out = Path(out)
    np.savez_compressed(out, fps=fps, n=len(boxes),
                        boxes=_objects(boxes), kps=_objects(kps), confs=_objects(confs),
                        feats=_objects(feats))
    return out


def extract_rackets(video: str | Path, frames, out: str | Path, seg_model="yolo11m-seg.pt", imgsz=960) -> Path:
    """Racket outlines (segmentation) only for the given frame indices, saved to .npz."""
    from ultralytics import YOLO

    seg = YOLO(seg_model)
    cap = cv2.VideoCapture(str(video))
    frames = sorted(set(int(f) for f in frames))
    polys, pos = [], -1
    for f in frames:
        if f != pos + 1:
            cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, frame = cap.read()
        pos = f
        if not ok:
            polys.append([])
            continue
        s = seg.predict(frame, imgsz=imgsz, conf=0.15, classes=[RACKET_CLASS], verbose=False)[0]
        polys.append([p.astype(np.float32) for p in (s.masks.xy if s.masks is not None else [])])
    out = Path(out)
    np.savez_compressed(out, frames=np.array(frames), polys=_objects(polys))
    return out


def extract_follow(video: str | Path, out: str | Path, init_box, pose_model="yolo11m-pose.pt", imgsz=640,
                   context=4.0, min_side=256, progress=False, max_bottom: float | None = None) -> Path:
    """Pose of a small, distant player: every frame, a square crop centred on her last position
    (side = context × her height) is enlarged to `imgsz` for the model, so she is seen 2-3× bigger
    than in the full frame. Same output format as `extract` (full-frame coordinates; only the
    people inside the crop). The followed box is the detection nearest to the last one."""
    from ultralytics import YOLO

    pose = YOLO(pose_model)
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    last = np.asarray(init_box, float)
    misses = 0                      # frames in a row without her: the crop grows to find her again
    boxes, kps, confs, feats = [], [], [], []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        H, W = frame.shape[:2]
        cx, cy = (last[0] + last[2]) / 2, (last[1] + last[3]) / 2
        side = min(max(H, W), max(min_side, context * (last[3] - last[1])) * (1 + 0.5 * min(misses, 6)))
        x0, y0 = int(np.clip(cx - side / 2, 0, max(0, W - side))), int(np.clip(cy - side / 2, 0, max(0, H - side)))
        crop = frame[y0:y0 + int(side), x0:x0 + int(side)]
        r = pose.predict(crop, imgsz=imgsz if misses < 2 else max(imgsz, 960), conf=0.25, verbose=False)[0]
        if len(r.boxes):
            b = r.boxes.xyxy.cpu().numpy() + [x0, y0, x0, y0]
            k = r.keypoints.xy.cpu().numpy() + [x0, y0]
            c = r.keypoints.conf.cpu().numpy()
            if max_bottom is not None:
                keep = b[:, 3] <= max_bottom
                b, k, c = b[keep], k[keep], c[keep]
        else:
            b, k, c = np.zeros((0, 4)), np.zeros((0, 17, 2)), np.zeros((0, 17))
        if len(b):
            d = np.hypot((b[:, 0] + b[:, 2]) / 2 - cx, (b[:, 1] + b[:, 3]) / 2 - cy)
            j = int(np.argmin(d))
            if d[j] < (1.5 + 0.5 * min(misses, 6)) * (last[3] - last[1]):
                last = b[j].astype(float)
                misses = 0
            else:
                misses += 1
        else:
            misses += 1
        boxes.append(b.astype(np.float32))
        kps.append(k.astype(np.float32))
        confs.append(c.astype(np.float32))
        feats.append(np.array([appearance(frame, bb) for bb in b], np.float32).reshape(len(b), 32))
        if progress and len(boxes) % 100 == 0:
            print(f"{len(boxes)} frames", flush=True)
    out = Path(out)
    np.savez_compressed(out, fps=fps, n=len(boxes), boxes=_objects(boxes), kps=_objects(kps), confs=_objects(confs),
                        feats=_objects(feats))
    return out


def detect_people(frame: np.ndarray, roi=None, pose_model="yolo11m-pose.pt", imgsz=1920, conf=0.25) -> np.ndarray:
    """Person boxes (N, 4) in full-frame coordinates, optionally only inside roi (enlarged)."""
    from ultralytics import YOLO

    x0, y0 = 0, 0
    src = frame
    if roi is not None:
        x0, y0, x1, y1 = (int(v) for v in roi)
        src = frame[y0:y1, x0:x1]
    r = YOLO(pose_model).predict(src, imgsz=imgsz, conf=conf, verbose=False)[0]
    return r.boxes.xyxy.cpu().numpy() + [x0, y0, x0, y0] if len(r.boxes) else np.zeros((0, 4))


def find_far_player(video: str | Path, H: np.ndarray, search_s=2.0, step=5):
    """First box of the far player within the first `search_s` of a video (every `step` frames);
    the box is returned for the first frame of the video (the follow crop starts there and
    re-centres on her within a few frames). None when she is not found."""
    from ..court_metrics import far_roi, pick_far_player

    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    i, box = 0, None
    while i <= search_s * fps:
        ok, frame = cap.read()
        if not ok:
            break
        if i % step == 0:
            box = pick_far_player(detect_people(frame, far_roi(H, frame.shape)), H)
            if box is not None:
                break
        i += 1
    cap.release()
    return box
