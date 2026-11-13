"""CalTennis (Demler et al., arXiv 2606.20542; CC BY-NC 4.0): the multi-view reference for the 3D trunk candidates
(request #206; scripts/bench_candidates.py, candidate `mag3d`).

The dataset (https://huggingface.co/datasets/demalenk/caltennis, not gated) has tennis practice and match play
filmed by 2-6 phones on tripods at 60 Hz, each video with its camera calibration in the court frame (K, R, t; world
z up) and its frame times. It has no 3D labels: the authors measure monocular models by how much the views disagree.
Here two calibrated views of the same half court give a reference made by triangulating the 2D keypoints (our 2D pose
in both views): the direction of the shoulder line and of the hip line about the vertical, which is what the trunk
turn reads. The reference depends on the 2D pose but not on any depth estimate; each monocular 3D model (RTMW3D,
MotionAGFormer) is read in one view and compared with it.

Synchronisation: a video's file name gives its start to the second (iPhone wall clock); the rest (up to ±1 s, as the
paper says) is the offset that makes the two views' keypoints triangulate best (smallest reprojection error), found
for each fetched segment (it also absorbs where the decoder started the segment).

The cameras are ~1.7 m high at 13-17 m from the players; the TV camera is higher and behind the baseline. A model
that reads the turn here is not shown to read it from the TV view: this measure can reject a model, not prove the
broadcast measure."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

BASE = "https://huggingface.co/datasets/demalenk/caltennis/resolve/main"
FPS = 60.0
COCO_TRUNK = (5, 6, 11, 12)          # left/right shoulder, left/right hip
COCO_BODY = tuple(range(5, 17))      # shoulders to ankles (the face points are not used to sync)
SEG_TIMEOUT_S = 900
MAX_REPROJ = 5.0                     # px: calibrations worse than this are not used


@dataclass
class Camera:
    K: np.ndarray
    R_c2w: np.ndarray
    C: np.ndarray                       # centre in the world (m)
    size: tuple[int, int]               # (w, h)

    @classmethod
    def from_json(cls, d: dict) -> "Camera | None":
        """The calibration file's camera (both of its formats carry Rt_c2w = [R_c2w | C]); None for a camera that
        is not a plain pinhole one well calibrated (fisheye or distortion terms, reprojection error over MAX_REPROJ
        px: some sessions have both)."""
        if (d.get("camera_model") or "pinhole") != "pinhole" or d.get("dist_coeffs") is not None \
                or float(d.get("reprojection_error") or 0) > MAX_REPROJ:
            return None
        rt = np.asarray(d["Rt_c2w"], float)
        sh = d.get("image_shape") or {}
        return cls(np.asarray(d["K"], float), rt[:, :3], rt[:, 3], (int(sh.get("width", 1920)), int(sh.get("height", 1080))))

    @property
    def R_w2c(self) -> np.ndarray:
        return self.R_c2w.T

    @property
    def t_w2c(self) -> np.ndarray:
        return -self.R_w2c @ self.C

    @property
    def P(self) -> np.ndarray:
        return self.K @ np.hstack([self.R_w2c, self.t_w2c[:, None]])

    def to_cam(self, X: np.ndarray) -> np.ndarray:
        return np.asarray(X, float) @ self.R_w2c.T + self.t_w2c

    def project(self, X: np.ndarray) -> np.ndarray:
        x = np.asarray(X, float) @ self.P[:, :3].T + self.P[:, 3]
        return x[..., :2] / x[..., 2:3]

    @property
    def view_dir(self) -> np.ndarray:
        """Horizontal viewing direction (unit, world x-y)."""
        d = self.R_c2w[:, 2][:2]
        return d / (np.linalg.norm(d) or 1.0)


def start_time(video_id: str) -> float | None:
    """Start of a video (POSIX seconds, local wall clock) from its name: MM_DD_YYYY_HH_MM_SS_mmm_…; None when the
    name does not say it (the overhead cameras: «…_court5_overhead»)."""
    try:
        mo, d, y, hh, mi, ss, ms = (int(x) for x in video_id.split("_")[:7])
        return datetime(y, mo, d, hh, mi, ss).timestamp() + ms / 1000.0
    except ValueError:  # esperado: a name without the date: unknown
        return None


def view_pair(a: Camera, b: Camera, min_deg=30.0, max_deg=150.0, max_m=30.0):
    """(angle between the two horizontal viewing directions in degrees, the world x-y point both look at) when the
    two cameras look at the same place from different enough directions; None otherwise."""
    da, db = a.view_dir, b.view_dir
    ang = float(np.degrees(np.arccos(np.clip(da @ db, -1, 1))))
    if not min_deg <= ang <= max_deg:
        return None
    A = np.stack([da, -db], 1)
    s, t = np.linalg.solve(A, b.C[:2] - a.C[:2])
    if s <= 0 or t <= 0 or s > max_m or t > max_m:
        return None
    return ang, a.C[:2] + s * da


def triangulate(Pa: np.ndarray, Pb: np.ndarray, xa: np.ndarray, xb: np.ndarray) -> np.ndarray:
    """Linear (DLT) triangulation of matching image points (…, 2) of two views → world points (…, 3)."""
    xa, xb = np.asarray(xa, float), np.asarray(xb, float)
    shp = xa.shape[:-1]
    xa, xb = xa.reshape(-1, 2), xb.reshape(-1, 2)
    rows = np.stack([xa[:, :1] * Pa[2] - Pa[0], xa[:, 1:] * Pa[2] - Pa[1],
                     xb[:, :1] * Pb[2] - Pb[0], xb[:, 1:] * Pb[2] - Pb[1]], 1)          # (n, 4, 4)
    ok = np.isfinite(rows).all((1, 2))
    out = np.full((len(xa), 3), np.nan)
    if ok.any():
        _, _, vt = np.linalg.svd(rows[ok])
        X = vt[:, -1]
        out[ok] = X[:, :3] / X[:, 3:4]
    return out.reshape(*shp, 3)


def reproj_error(a: Camera, b: Camera, xa, xb, X) -> np.ndarray:
    """Mean of the two views' reprojection errors (px) of each triangulated point."""
    return (np.linalg.norm(a.project(X) - xa, axis=-1) + np.linalg.norm(b.project(X) - xb, axis=-1)) / 2


def interp(times: np.ndarray, values: np.ndarray, t: np.ndarray) -> np.ndarray:
    """values (n, …) known at ascending `times`, linearly interpolated at `t` (NaN outside or next to a NaN)."""
    times, values, t = np.asarray(times, float), np.asarray(values, float), np.asarray(t, float)
    i = np.clip(np.searchsorted(times, t) - 1, 0, len(times) - 2)
    w = (t - times[i]) / np.where(times[i + 1] > times[i], times[i + 1] - times[i], 1.0)
    w = w.reshape((-1,) + (1,) * (values.ndim - 1))
    out = values[i] * (1 - w) + values[i + 1] * w
    out[(t < times[0]) | (t > times[-1])] = np.nan
    return out


def best_offset(a: Camera, b: Camera, ta, ka, ca, tb, kb, cb, offsets, joints=COCO_BODY, min_conf=0.5):
    """(offset s, median reprojection error px): the time shift of view b (b's clock + offset = a's clock) that
    makes the person's keypoints (ka (n, 17, 2) at times ta, kb at tb; confidences ca, cb) triangulate best."""
    j = list(joints)
    best = (None, np.inf)
    for off in offsets:
        kbi = interp(np.asarray(tb) + off, kb[:, j], ta)
        cbi = interp(np.asarray(tb) + off, cb[:, j], ta)
        good = (ca[:, j] >= min_conf) & (cbi >= min_conf)
        if good.sum() < 20:
            continue
        X = triangulate(a.P, b.P, ka[:, j][good], kbi[good])
        e = float(np.median(reproj_error(a, b, ka[:, j][good], kbi[good], X)))
        if e < best[1]:
            best = (float(off), e)
    return best


def iou(p: np.ndarray, q: np.ndarray) -> np.ndarray:
    """IoU of box p (4,) with boxes q (n, 4)."""
    q = np.asarray(q, float).reshape(-1, 4)
    x0, y0 = np.maximum(p[0], q[:, 0]), np.maximum(p[1], q[:, 1])
    x1, y1 = np.minimum(p[2], q[:, 2]), np.minimum(p[3], q[:, 3])
    inter = np.clip(x1 - x0, 0, None) * np.clip(y1 - y0, 0, None)
    area = lambda b: (b[..., 2] - b[..., 0]) * (b[..., 3] - b[..., 1])
    return inter / np.maximum(area(np.asarray(p, float)) + area(q) - inter, 1e-9)


def track(boxes: list, start: int, idx: int, min_iou=0.3) -> list[int | None]:
    """Index of the same person in each frame (None when lost: the track stops there), followed by box overlap from
    person `idx` of frame `start` forwards and backwards."""
    out: list[int | None] = [None] * len(boxes)
    out[start] = idx
    for rng in (range(start + 1, len(boxes)), range(start - 1, -1, -1)):
        prev = np.asarray(boxes[start][idx][:4], float)
        for f in rng:
            b = np.asarray(boxes[f], float)
            if not b.size:
                break
            b = b.reshape(len(b), -1)
            o = iou(prev, b[:, :4])
            k = int(np.argmax(o))
            if o[k] < min_iou:
                break
            out[f], prev = k, b[k, :4]
    return out


def match_people(a: Camera, b: Camera, ka: np.ndarray, ca: np.ndarray, kb: np.ndarray, cb: np.ndarray,
                 min_conf=0.5, max_px=80.0):
    """(i, j, error px) of the person i of view a and j of view b (keypoints (n, 17, 2), confidences (n, 17)) whose
    body points triangulate best, or None when no pair is within max_px (the views are synchronised only to ±1 s
    here, so the bound is loose)."""
    best = None
    j = list(COCO_BODY)
    for i in range(len(ka)):
        for m in range(len(kb)):
            good = (ca[i, j] >= min_conf) & (cb[m, j] >= min_conf)
            if good.sum() < 6:
                continue
            X = triangulate(a.P, b.P, ka[i, j][good], kb[m, j][good])
            e = float(np.median(reproj_error(a, b, ka[i, j][good], kb[m, j][good], X)))
            if e <= max_px and (best is None or e < best[2]):
                best = (i, m, e)
    return best


def wrap(a):
    return (np.asarray(a, float) + 180.0) % 360.0 - 180.0


def trunk_yaw_from_world(X: np.ndarray) -> np.ndarray:
    """(…, 2): directions (deg) about the world vertical of the left→right shoulder line and hip line, from world
    COCO points (…, 17, 3) or the trunk points in COCO_TRUNK order (…, 4, 3)."""
    X = np.asarray(X, float)
    ls, rs, lh, rh = (X[..., k, :] for k in (COCO_TRUNK if X.shape[-2] == 17 else range(4)))
    d = np.stack([rs - ls, rh - lh], -2)
    return np.degrees(np.arctan2(d[..., 1], d[..., 0]))


def angle_errors(mono: np.ndarray, ref: np.ndarray) -> dict:
    """Errors (deg) of monocular (n, 2) shoulder/hip directions against the reference (n, 2): pooled shoulder and
    hip readings, and the X-factor (shoulders − hips) that does not depend on the absolute direction."""
    mono, ref = np.asarray(mono, float).reshape(-1, 2), np.asarray(ref, float).reshape(-1, 2)
    ok = np.isfinite(mono).all(1) & np.isfinite(ref).all(1)
    e = np.abs(wrap(mono[ok] - ref[ok]))
    xf = np.abs(wrap((mono[ok, 0] - mono[ok, 1]) - (ref[ok, 0] - ref[ok, 1])))
    r = lambda v: None if v is None else round(float(v), 3)
    return {"frames": int(ok.sum()),
            "median_err_deg": r(np.median(e)) if ok.any() else None,
            "within_15deg": r(np.mean(e <= 15)) if ok.any() else None,
            "xfactor_median_err_deg": r(np.median(xf)) if ok.any() else None}


# ---------------------------------------------------------------- data (only here and in the bench: downloads)

def fetch(url: str, dest: Path, timeout: float = 60) -> Path:
    """dest, downloaded once (a stalled connection fails after `timeout` s; written to .part, then renamed)."""
    import urllib.request

    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "tennisbio"}), timeout=timeout) as r, \
            open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    tmp.replace(dest)
    return dest


def metadata(root: Path, split: str = "mini") -> list[dict]:
    p = fetch(f"{BASE}/metadata_{split}.jsonl", Path(root) / "caltennis" / f"metadata_{split}.jsonl")
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def camera(root: Path, entry: dict) -> Camera | None:
    """The video's calibration; None when the dataset has none for it (some metadata rows name a file that is not
    published)."""
    import urllib.error

    try:
        p = fetch(f"{BASE}/{entry['calibration']}", Path(root) / "caltennis" / entry["calibration"])
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    return Camera.from_json(json.loads(p.read_text(encoding="utf-8")))


def frame_times(root: Path, entry: dict) -> np.ndarray:
    """The video's frame times (s from its start)."""
    return np.load(fetch(f"{BASE}/{entry['timestamps']}", Path(root) / "caltennis" / entry["timestamps"])) / 1000.0


def pairs(root: Path, entries: list[dict]) -> list[dict]:
    """Pairs of videos of one session that film the same half court from directions 30-150° apart and overlap in
    time, best angle (closest to 90°) first, at most one pair per session."""
    by: dict = {}
    cams = {}
    for e in entries:
        if start_time(e["video_id"]) is None:          # cannot be synchronised to the second
            continue
        cams[e["video_id"]] = camera(root, e)
        if cams[e["video_id"]] is not None:
            by.setdefault(e["session_id"], []).append(e)
    out = []
    for sess, es in sorted(by.items()):
        cands = []
        for i in range(len(es)):
            for j in range(i + 1, len(es)):
                ca, cb = cams[es[i]["video_id"]], cams[es[j]["video_id"]]
                vp = view_pair(ca, cb)
                if vp is None:
                    continue
                ta, tb = frame_times(root, es[i]), frame_times(root, es[j])
                sa, sb = start_time(es[i]["video_id"]), start_time(es[j]["video_id"])
                lo, hi = max(sa, sb), min(sa + ta[-1], sb + tb[-1])
                if hi - lo < 120:
                    continue
                cands.append({"session": sess, "a": es[i], "b": es[j], "angle": round(vp[0], 1),
                              "target": [round(float(x), 2) for x in vp[1]], "overlap": (lo, hi)})
        if cands:
            out.append(min(cands, key=lambda c: abs(c["angle"] - 90)))
    return sorted(out, key=lambda c: abs(c["angle"] - 90))


def fetch_segment(entry: dict, start_s: float, dur_s: float, dest: Path, timeout: float = SEG_TIMEOUT_S) -> Path:
    """dest: `dur_s` seconds of the video from `start_s` (its own clock), cut by ffmpeg straight from the dataset's
    URL (HTTP ranges: only that part is downloaded), re-encoded so the first frame is the one at start_s."""
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.stem + ".part" + dest.suffix)
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-y", "-rw_timeout", "60000000", "-ss", f"{max(0.0, start_s):.3f}",
           "-i", f"{BASE}/{entry['video']}", "-t", f"{dur_s:.3f}", "-an", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "16", "-pix_fmt", "yuv420p", str(tmp)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode or not tmp.exists():
        raise RuntimeError(f"ffmpeg no pudo cortar {entry['video']} en {start_s:.1f} s: {r.stderr.strip()[-300:]}")
    tmp.replace(dest)
    return dest
