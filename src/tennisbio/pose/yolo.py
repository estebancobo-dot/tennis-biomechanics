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
            roi: tuple | None = None, frames=None, prefetch: bool = True, keep=None, stats: dict | None = None,
            model=None) -> Path:
    """Run pose on every `every`-th frame and save all people (boxes, keypoints, appearance) to .npz.

    roi: (x0, y0, x1, y1) — run only on that region (e.g. the far half of the court, where the far
    player is too small for the full frame); coordinates are returned in the full frame.
    frames: the video's decoded frames when the caller already reads them (one decode shared with
    the ball model); by default they are read here, decoded ahead in a background thread.
    prefetch: the model's input (letterbox) of the next frames is prepared in a reader thread and the
    appearance histograms in another, while the model runs on the current frame (the same inputs,
    so the same output as one frame at a time; as the cheap pass does).
    keep: optional (T,) bool, the frames to run the model on; the others are saved with nobody
    (fine_pass.pose_ranges: frames no possible stroke uses).
    stats: when given, "frames" (model runs) and "model_s" (seconds in the model) are added to it.
    model: the pose model to use instead of backend.pose_model(pose_model, imgsz) (same contract:
    predict(img, conf, prepared=...) and optionally prepare(img)). A model with predict_feet (the hybrid
    one, pose.hybrid.HybridPose) also fills `feet` (per frame (N, 6, 2)) and `feet_confs` ((N, 6)) in
    the cache: the 6 Halpe26 foot points, in full-frame coordinates."""
    from concurrent.futures import ThreadPoolExecutor
    from time import perf_counter

    from ..io.video import capture_frames, read_ahead
    from .backend import pose_model as _pm

    pose = model if model is not None else _pm(pose_model, imgsz)
    with_feet = hasattr(pose, "predict_feet")
    fps = _fps(video) / every
    boxes, kps, confs, feats, feet, feet_c = [], [], [], [], [], []
    x0 = y0 = 0
    if roi is not None:
        x0, y0, x1, y1 = (int(v) for v in roi)

    def items():
        """(frame, region the model sees, its prepared input or None) of every frame to keep; None for
        the frames skipped (every / keep)."""
        for i, frame in enumerate(capture_frames(video) if frames is None else frames):
            if i % every:
                continue
            if keep is not None and not (i < len(keep) and keep[i]):
                yield None
                continue
            src = frame if roi is None else frame[y0:y1, x0:x1]
            prep = getattr(pose, "prepare", None) if prefetch else None
            yield frame, src, (prep(src) if prep is not None else None)

    empty = (np.zeros((0, 4), np.float32), np.zeros((0, 17, 2), np.float32), np.zeros((0, 17), np.float32),
             np.zeros((0, 32), np.float32))
    n_model, t_model = 0, 0.0
    with ThreadPoolExecutor(max_workers=1) as pool:
        for it in (read_ahead(items, prefetch=4) if prefetch else items()):
            if it is None:
                boxes.append(empty[0]); kps.append(empty[1]); confs.append(empty[2]); feats.append(empty[3])
                if with_feet:
                    feet.append(np.zeros((0, 6, 2), np.float32)); feet_c.append(np.zeros((0, 6), np.float32))
                continue
            frame, src, prep = it
            t_ = perf_counter()
            fn = pose.predict_feet if with_feet else pose.predict
            out_ = fn(src, conf=0.3, prepared=prep) if prep is not None else fn(src, conf=0.3)
            t_model += perf_counter() - t_
            n_model += 1
            b, k, c = out_[:3]
            if with_feet:
                fk, fc = out_[3], out_[4]
                feet.append(np.asarray(fk, np.float32).reshape(-1, 6, 2) + np.float32([x0, y0]) if len(b)
                            else np.zeros((0, 6, 2), np.float32))
                feet_c.append(np.asarray(fc, np.float32).reshape(-1, 6) if len(b) else np.zeros((0, 6), np.float32))
            b = b + [x0, y0, x0, y0] if len(b) else np.zeros((0, 4))
            boxes.append(b.astype(np.float32))
            kps.append(k.astype(np.float32) + [x0, y0] if len(b) else np.zeros((0, 17, 2), np.float32))
            confs.append(c.astype(np.float32) if len(b) else np.zeros((0, 17), np.float32))
            app = lambda fr=frame, bb=b: np.array([appearance(fr, x) for x in bb], np.float32).reshape(len(bb), 32)
            feats.append(pool.submit(app) if prefetch else app())
            if progress and len(boxes) % 100 == 0:
                print(f"{len(boxes)} frames", flush=True)
        feats = [f.result() if hasattr(f, "result") else f for f in feats]
    if stats is not None:
        stats["frames"] = stats.get("frames", 0) + n_model
        stats["model_s"] = stats.get("model_s", 0.0) + t_model
    out = Path(out)
    extra = dict(feet=_objects(feet), feet_confs=_objects(feet_c)) if with_feet else {}
    savez_atomic(out, fps=fps, n=len(boxes),
                        boxes=_objects(boxes), kps=_objects(kps), confs=_objects(confs),
                        feats=_objects(feats), **extra)
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
                try:
                    self.proc.wait(timeout=10)            # reaped: alive() is False from here on
                except Exception:
                    pass
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
                   context=4.0, min_side=256, progress=False, max_bottom: float | None = None, frames=None,
                   prefetch: bool = True, keep=None, inits: dict | None = None, stats: dict | None = None) -> Path:
    """Pose of a small, distant player: every frame, a square crop centred on her last position
    (side = context × her height) is enlarged to `imgsz` for the model, so she is seen 2-3× bigger
    than in the full frame. Same output format as `extract` (full-frame coordinates; only the
    people inside the crop). The followed box is the detection nearest to the last one.
    frames: as in extract. prefetch: appearance histograms in another thread (same output).
    keep: optional (T,) bool, the frames to run the model on (others saved with nobody); inits:
    {frame: box} where the follow starts again (the first frame of each stretch of `keep`, where
    she was searched for: fine_pass.pose_ranges)."""
    from concurrent.futures import ThreadPoolExecutor
    from time import perf_counter

    from ..io.video import capture_frames
    from .backend import pose_model as _pm

    fps = _fps(video)
    last = np.asarray(init_box, float)
    misses = 0                      # frames in a row without her: the crop grows to find her again
    boxes, kps, confs, feats = [], [], [], []
    n_model, n_big, t_model = 0, 0, 0.0
    pool = ThreadPoolExecutor(max_workers=1) if prefetch else None
    try:
        for i, frame in enumerate(capture_frames(video) if frames is None else frames):
            if keep is not None and not (i < len(keep) and keep[i]):
                boxes.append(np.zeros((0, 4), np.float32)); kps.append(np.zeros((0, 17, 2), np.float32))
                confs.append(np.zeros((0, 17), np.float32)); feats.append(np.zeros((0, 32), np.float32))
                continue
            if inits and i in inits:
                last, misses = np.asarray(inits[i], float), 0
            H, W = frame.shape[:2]
            cx, cy = (last[0] + last[2]) / 2, (last[1] + last[3]) / 2
            side = min(max(H, W), max(min_side, context * (last[3] - last[1])) * (1 + 0.5 * min(misses, 6)))
            x0, y0 = int(np.clip(cx - side / 2, 0, max(0, W - side))), int(np.clip(cy - side / 2, 0, max(0, H - side)))
            crop = frame[y0:y0 + int(side), x0:x0 + int(side)]
            t_ = perf_counter()
            b, k, c = _pm(pose_model, imgsz if misses < 2 else max(imgsz, 960)).predict(crop, conf=0.25)
            t_model += perf_counter() - t_
            n_model += 1
            n_big += misses >= 2
            if len(b):
                b = b + [x0, y0, x0, y0]
                k = k + [x0, y0]
                if max_bottom is not None:
                    keep_b = b[:, 3] <= max_bottom
                    b, k, c = b[keep_b], k[keep_b], c[keep_b]
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
            app = lambda fr=frame, bb=b: np.array([appearance(fr, x) for x in bb], np.float32).reshape(len(bb), 32)
            feats.append(pool.submit(app) if pool is not None else app())
            if progress and len(boxes) % 100 == 0:
                print(f"{len(boxes)} frames", flush=True)
        feats = [f.result() if hasattr(f, "result") else f for f in feats]
    finally:
        if pool is not None:
            pool.shutdown(wait=True)
    if stats is not None:
        stats["frames"] = stats.get("frames", 0) + n_model
        stats["model_s"] = stats.get("model_s", 0.0) + t_model
        stats["frames_960"] = stats.get("frames_960", 0) + n_big      # she was lost: bigger crop at 960 px
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
    return find_far_players(video, H, [0], search_s, step)[0]


def find_far_players(video: str | Path, H: np.ndarray, starts, search_s=2.0, step=5) -> dict:
    """find_far_player from each of several start frames, in one reading of the video:
    {start: box or None}. The search from a start never looks past `search_s` after it."""
    from ..court_metrics import far_roi, pick_far_player

    starts = sorted({int(s) for s in starts})
    found = {s: None for s in starts}
    if not starts:
        return found
    cap = open_capture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    last = max(starts) + int(search_s * fps)
    i = 0
    try:
        while i <= last:
            todo = [s for s in starts if found[s] is None and s <= i <= s + search_s * fps and (i - s) % step == 0]
            done = all(found[s] is not None or i > s + search_s * fps for s in starts)
            if done:
                break
            ok, frame = cap.read()
            if not ok:
                break
            if todo:
                box = pick_far_player(detect_people(frame, far_roi(H, frame.shape)), H)
                if box is not None:
                    for s in todo:
                        found[s] = box
            i += 1
    finally:
        cap.release()
    return found


if __name__ == "__main__":            # worker of extract_rackets: --serve model imgsz device
    import sys

    if sys.argv[1:2] == ["--serve"]:
        _serve_main(sys.argv[2], int(sys.argv[3]), sys.argv[4])
