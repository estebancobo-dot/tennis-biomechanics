"""Extraction with Ultralytics YOLO: people (pose) on every frame, rackets (segmentation) on demand.

Optional backend (`uv sync --extra yolo`). Everything detected is cached, so tracking, stroke
detection and racket analysis can be re-run without inference. Rackets are segmented only in
the frames around each stroke (same idea as the two-pass pipeline).
"""
from pathlib import Path

import cv2

import numpy as np

from ..io.video import open_capture
from ..pipeline import savez_atomic

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


def _fps(video) -> float:
    cap = open_capture(video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    return fps


def extract(video: str | Path, out: str | Path, pose_model="yolo11m-pose.pt", imgsz=960, every=1, progress=True,
            roi: tuple | None = None, frames=None) -> Path:
    """Run pose on every `every`-th frame and save all people (boxes, keypoints, appearance) to .npz.

    roi: (x0, y0, x1, y1) — run only on that region (e.g. the far half of the court, where the far
    player is too small for the full frame); coordinates are returned in the full frame.
    frames: the video's decoded frames when the caller already reads them (one decode shared with
    the ball model); by default they are read here, decoded ahead in a background thread."""
    from ..io.video import capture_frames
    from .backend import pose_model as _pm

    pose = _pm(pose_model, imgsz)
    fps = _fps(video) / every
    boxes, kps, confs, feats = [], [], [], []
    i = 0
    for frame in (capture_frames(video) if frames is None else frames):
        if i % every:
            i += 1
            continue
        ox = oy = 0
        src = frame
        if roi is not None:
            x0, y0, x1, y1 = (int(v) for v in roi)
            src, ox, oy = frame[y0:y1, x0:x1], x0, y0
        b, k, c = pose.predict(src, conf=0.3)
        b = b + [ox, oy, ox, oy] if len(b) else np.zeros((0, 4))
        boxes.append(b.astype(np.float32))
        kps.append(k.astype(np.float32) + [ox, oy] if len(b) else np.zeros((0, 17, 2), np.float32))
        confs.append(c.astype(np.float32) if len(b) else np.zeros((0, 17), np.float32))
        feats.append(np.array([appearance(frame, bb) for bb in b], np.float32).reshape(len(b), 32))
        i += 1
        if progress and len(boxes) % 100 == 0:
            print(f"{len(boxes)} frames", flush=True)
    out = Path(out)
    savez_atomic(out, fps=fps, n=len(boxes),
                        boxes=_objects(boxes), kps=_objects(kps), confs=_objects(confs),
                        feats=_objects(feats))
    return out


def extract_rackets(video: str | Path, frames, out: str | Path, seg_model="yolo11m-seg.pt", imgsz=960) -> Path:
    """Racket outlines (segmentation) only for the given frame indices, saved to .npz.

    On the iGPU (DirectML, ~5x faster than the CPU) it runs in a separate process: a driver crash
    there (it happened on the user's PC: access violation, which no Python code can catch) only
    loses that attempt; it is then done on the CPU here, and the iGPU is not tried again
    (models/seg_gpu_falla.txt). That process stays open between windows (SegWorker), so the model
    is loaded on the iGPU once per run, not once per window."""
    from .backend import DEFAULT_DEVICE
    from .yolo_onnx import MODELS_DIR

    flag = MODELS_DIR / "seg_gpu_falla.txt"
    if DEFAULT_DEVICE != "cpu" and not flag.exists():
        w = seg_worker(seg_model, imgsz, DEFAULT_DEVICE)
        ok, code, err = w.run(video, frames, out)
        if ok and Path(out).exists():
            return Path(out)
        close_seg_worker()
        flag.write_text(f"codigo {code}\n{(err or '')[-1500:]}", encoding="utf-8")
        print(f"AVISO: la gráfica falló al segmentar la raqueta (código {code}); se hace en la CPU desde ahora")
    return _extract_rackets(video, frames, out, seg_model, imgsz, "cpu")


_SEG_MODELS: dict = {}


def _seg_model(seg_model="yolo11m-seg.pt", imgsz=960, device="cpu"):
    """frame → racket polygons; the model is loaded once per (model, size, device) in a process."""
    key = (str(seg_model), int(imgsz), device)
    if key in _SEG_MODELS:
        return _SEG_MODELS[key]
    from .yolo_onnx import MODELS_DIR, YoloOnnx, export_onnx

    name = Path(seg_model).stem
    onnx = MODELS_DIR / f"{name}_{imgsz}.onnx"
    if not onnx.exists():
        try:
            onnx = export_onnx(name, imgsz)
        except Exception:
            onnx = None
    seg_onnx = YoloOnnx(onnx, device) if onnx is not None and onnx.exists() else None
    if seg_onnx is not None:
        def fn(frame):
            return seg_onnx.segment(frame, RACKET_CLASS, conf=0.15)
    else:
        from ultralytics import YOLO
        # a bare name lives in models/ (downloaded there the first time), never in the current directory
        seg = YOLO(str(MODELS_DIR / seg_model) if Path(seg_model).name == str(seg_model) else seg_model)

        def fn(frame):
            s = seg.predict(frame, imgsz=imgsz, conf=0.15, classes=[RACKET_CLASS], verbose=False)[0]
            return [p.astype(np.float32) for p in (s.masks.xy if s.masks is not None else [])]
    _SEG_MODELS[key] = fn
    return fn


def _extract_rackets(video, frames, out, seg_model="yolo11m-seg.pt", imgsz=960, device="cpu", segment=None) -> Path:
    segment = segment or _seg_model(seg_model, imgsz, device)
    cap = open_capture(video)
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
        polys.append(segment(frame))
    cap.release()
    out = Path(out)
    savez_atomic(out, frames=np.array(frames), polys=_objects(polys))
    return out


# ---- persistent worker process (racket segmentation on the iGPU) --------------------------------
# Protocol: one JSON object per line, ASCII only (json.dumps escapes accents in paths, so Windows
# code pages never matter). Request {"video", "frames", "out"}; reply {"ok": true} or
# {"ok": false, "error": "..."}. Replies go to the process's original stdout; anything else the
# worker or its libraries print goes to stderr, so it never corrupts the protocol. End of input
# (stdin closed) ends the worker.

def serve(handler, inp, out):
    """Worker loop: each request line → handler(job dict) → reply line. A Python error in a job is
    a reply ({"ok": false}); the worker keeps serving."""
    import json
    import traceback

    for line in inp:
        line = line.strip()
        if not line:
            continue
        try:
            handler(json.loads(line))
            reply = {"ok": True}
        except Exception as e:
            reply = {"ok": False, "error": f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1200:]}"}
        out.write((json.dumps(reply) + "\n").encode("ascii"))
        out.flush()


def _serve_main(seg_model: str, imgsz: int, device: str):
    import os
    import sys

    out = os.fdopen(os.dup(sys.stdout.fileno()), "wb")
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())       # native and Python prints → stderr
    sys.stdout = sys.stderr
    segment = _seg_model(seg_model, imgsz, device)
    serve(lambda job: _extract_rackets(job["video"], job["frames"], job["out"], segment=segment),
          sys.stdin.buffer, out)


class SegWorker:
    """Client of one worker process. run() returns (ok, exit code or None, error text); when the
    process dies (driver crash) or a job fails, ok is False and the caller falls back."""

    def __init__(self, cmd: list[str], key=None):
        import subprocess
        import tempfile

        self.cmd, self.key = cmd, key
        self.log = tempfile.TemporaryFile()           # its stderr: never a pipe nobody reads (deadlock)
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log)

    @staticmethod
    def timeout_s(n_frames: int) -> float:
        return 120.0 + 2.0 * n_frames

    def alive(self) -> bool:
        return self.proc.poll() is None

    def _stderr(self) -> str:
        try:
            self.log.seek(0)
            return self.log.read().decode("utf-8", "replace")
        except Exception:
            return ""

    def run(self, video, frames, out) -> tuple[bool, int | None, str]:
        import json

        import threading

        job = {"video": str(video), "frames": sorted(set(int(f) for f in frames)), "out": str(out)}
        got: list = []
        try:
            self.proc.stdin.write((json.dumps(job) + "\n").encode("ascii"))
            self.proc.stdin.flush()
            # a driver that hangs without crashing must not stop the whole analysis: wait at most
            # 2 min + 2 s per frame, then kill the worker (the caller falls back as on a crash)
            rd = threading.Thread(target=lambda: got.append(self.proc.stdout.readline()), daemon=True)
            rd.start()
            rd.join(self.timeout_s(len(job["frames"])))
            if rd.is_alive():
                self.proc.kill()
                rd.join(10)
                return False, None, f"sin respuesta en {self.timeout_s(len(job['frames'])):.0f} s (colgado)\n{self._stderr()}"
            line = got[0] if got else b""
        except (OSError, ValueError):                 # broken pipe: it had already died
            line = b""
        if not line:                                  # died: crash in the driver, out of memory...
            try:
                code = self.proc.wait(timeout=10)
            except Exception:
                self.proc.kill()
                code = self.proc.wait()
            return False, code, self._stderr()
        try:
            reply = json.loads(line)
        except ValueError:
            return False, None, f"respuesta inesperada: {line[:200]!r}\n{self._stderr()}"
        if reply.get("ok"):
            return True, 0, ""
        return False, 1, (reply.get("error") or "") + "\n" + self._stderr()

    def close(self):
        try:
            if self.proc.stdin and not self.proc.stdin.closed:
                self.proc.stdin.close()
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()
            self.proc.wait()
        for f in (self.proc.stdout, self.log):
            try:
                f.close()
            except Exception:
                pass


_WORKER: dict = {}


def seg_worker(seg_model: str, imgsz: int, device: str) -> SegWorker:
    """The open worker for these settings, started the first time (and again if it ended)."""
    import atexit
    import sys

    key = (str(seg_model), int(imgsz), device)
    w = _WORKER.get("w")
    if w is not None and (w.key != key or not w.alive()):
        close_seg_worker()
        w = None
    if w is None:
        w = SegWorker([sys.executable, "-m", "tennisbio.pose.yolo", "--serve", str(seg_model), str(imgsz), device], key)
        _WORKER["w"] = w
        if not _WORKER.get("atexit"):
            atexit.register(close_seg_worker)
            _WORKER["atexit"] = True
    return w


def close_seg_worker():
    w = _WORKER.pop("w", None)
    if w is not None:
        w.close()


def extract_follow(video: str | Path, out: str | Path, init_box, pose_model="yolo11m-pose.pt", imgsz=640,
                   context=4.0, min_side=256, progress=False, max_bottom: float | None = None, frames=None) -> Path:
    """Pose of a small, distant player: every frame, a square crop centred on her last position
    (side = context × her height) is enlarged to `imgsz` for the model, so she is seen 2-3× bigger
    than in the full frame. Same output format as `extract` (full-frame coordinates; only the
    people inside the crop). The followed box is the detection nearest to the last one.
    frames: as in extract."""
    from ..io.video import capture_frames
    from .backend import pose_model as _pm

    fps = _fps(video)
    last = np.asarray(init_box, float)
    misses = 0                      # frames in a row without her: the crop grows to find her again
    boxes, kps, confs, feats = [], [], [], []
    for frame in (capture_frames(video) if frames is None else frames):
        H, W = frame.shape[:2]
        cx, cy = (last[0] + last[2]) / 2, (last[1] + last[3]) / 2
        side = min(max(H, W), max(min_side, context * (last[3] - last[1])) * (1 + 0.5 * min(misses, 6)))
        x0, y0 = int(np.clip(cx - side / 2, 0, max(0, W - side))), int(np.clip(cy - side / 2, 0, max(0, H - side)))
        crop = frame[y0:y0 + int(side), x0:x0 + int(side)]
        b, k, c = _pm(pose_model, imgsz if misses < 2 else max(imgsz, 960)).predict(crop, conf=0.25)
        if len(b):
            b = b + [x0, y0, x0, y0]
            k = k + [x0, y0]
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
    savez_atomic(out, fps=fps, n=len(boxes), boxes=_objects(boxes), kps=_objects(kps), confs=_objects(confs),
                        feats=_objects(feats))
    return out


def detect_people(frame: np.ndarray, roi=None, pose_model="yolo11m-pose.pt", imgsz=1920, conf=0.25) -> np.ndarray:
    """Person boxes (N, 4) in full-frame coordinates, optionally only inside roi (enlarged)."""
    from .backend import pose_model as _pm

    x0, y0 = 0, 0
    src = frame
    if roi is not None:
        x0, y0, x1, y1 = (int(v) for v in roi)
        src = frame[y0:y1, x0:x1]
    b, _, _ = _pm(pose_model, imgsz).predict(src, conf=conf)
    return b + [x0, y0, x0, y0] if len(b) else np.zeros((0, 4))


def find_far_player(video: str | Path, H: np.ndarray, search_s=2.0, step=5):
    """First box of the far player within the first `search_s` of a video (every `step` frames);
    the box is returned for the first frame of the video (the follow crop starts there and
    re-centres on her within a few frames). None when she is not found."""
    from ..court_metrics import far_roi, pick_far_player

    cap = open_capture(video)
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


if __name__ == "__main__":            # worker of extract_rackets: --serve model imgsz device
    import sys

    if sys.argv[1:2] == ["--serve"]:
        _serve_main(sys.argv[2], int(sys.argv[3]), sys.argv[4])
