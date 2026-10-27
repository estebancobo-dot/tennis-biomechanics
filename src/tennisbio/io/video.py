"""Video access through ffmpeg: metadata and streaming of decoded frames."""
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Iterator

import numpy as np


@dataclass
class VideoInfo:
    path: Path
    width: int
    height: int
    fps: float
    duration: float
    codec: str
    interlaced: bool
    audio_rate: int | None
    audio_channels: int | None
    vfr: bool = False
    audio_tracks: int = 0
    start_time: float = 0.0


class VideoError(RuntimeError):
    """A video that cannot be read; the message is for the user (Spanish)."""


def _rate(s: dict) -> float:
    for key in ("avg_frame_rate", "r_frame_rate"):
        try:
            v = float(Fraction(s.get(key) or "0/1"))
        except (ZeroDivisionError, ValueError):
            v = 0.0
        if 1.0 < v < 400.0:
            return v
    return 0.0


def _float(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def probe(path: str | Path) -> VideoInfo:
    path = Path(path)
    if not path.exists():
        raise VideoError(f"No existe el vídeo {path}")
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
                             capture_output=True, text=True, check=True, encoding="utf-8", errors="replace", timeout=120).stdout
    except FileNotFoundError:
        raise VideoError("No se encuentra ffprobe/ffmpeg: ejecuta 1_instalar.bat") from None
    except subprocess.TimeoutExpired:
        raise VideoError(f"ffprobe no responde con {path.name} (más de 2 min): vídeo dañado o disco lento") from None
    except subprocess.CalledProcessError as e:
        raise VideoError(f"El vídeo {path.name} está dañado o incompleto ({(e.stderr or '').strip()[:200]})") from None
    info = json.loads(out or "{}")
    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video" and s.get("disposition", {}).get("attached_pic") != 1), None)
    if video is None:
        raise VideoError(f"{path.name} no tiene pista de vídeo")
    audios = [s for s in streams if s.get("codec_type") == "audio"]
    audio = audios[0] if audios else None
    fps = _rate(video)
    if not fps:
        raise VideoError(f"No se puede saber los fotogramas por segundo de {path.name}")
    dur = 0.0
    for v in ((info.get("format") or {}).get("duration"), video.get("duration")):
        try:
            dur = float(v)
            break
        except (TypeError, ValueError):
            continue
    if dur <= 0 and video.get("nb_frames"):
        dur = int(video["nb_frames"]) / fps
    if dur <= 0:
        raise VideoError(f"No se puede saber la duración de {path.name} (fichero incompleto)")
    # variable frame rate: the two rates disagree clearly
    try:
        r, a = float(Fraction(video.get("r_frame_rate", "0/1"))), float(Fraction(video.get("avg_frame_rate", "0/1")))
    except (ZeroDivisionError, ValueError):
        r = a = 0.0
    return VideoInfo(
        path=path,
        width=int(video["width"]),
        height=int(video["height"]),
        fps=fps,
        duration=dur,
        codec=video.get("codec_name", "?"),
        interlaced=video.get("field_order", "progressive") not in ("progressive", "unknown"),
        audio_rate=int(audio["sample_rate"]) if audio and audio.get("sample_rate") else None,
        audio_channels=int(audio["channels"]) if audio and audio.get("channels") else None,
        vfr=bool(r and a and abs(r - a) / max(r, a) > 0.02),
        audio_tracks=len(audios),
        start_time=_float(video.get("start_time")),
    )


_HW: dict = {}


def auto_hwaccel() -> str | None:
    """The GPU video decoder when it works here (d3d11va on Windows: the Radeon decodes H.264/HEVC
    and frees the CPU for the pose), else None (software). Tested once per run; ffmpeg falls back
    to software by itself when a particular file cannot be decoded on the GPU."""
    if "v" not in _HW:
        _HW["v"] = None
        if os.name == "nt":
            with tempfile.TemporaryDirectory() as d:
                f = str(Path(d) / "t.mp4")
                try:
                    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=duration=0.4:size=640x360:rate=25",
                                    "-c:v", "libx264", "-pix_fmt", "yuv420p", f], capture_output=True, timeout=60)
                    # frames kept on the GPU: fails instead of silently falling back to the CPU
                    r = subprocess.run(["ffmpeg", "-v", "error", "-hwaccel", "d3d11va", "-hwaccel_output_format", "d3d11",
                                        "-i", f, "-f", "null", "-"], capture_output=True, timeout=60)
                except subprocess.TimeoutExpired:       # a driver that hangs: decode on the CPU
                    r = None
                if r is not None and r.returncode == 0 and Path(f).exists():
                    _HW["v"] = "d3d11va"
    return _HW["v"]


def read_frames(
    info: VideoInfo,
    start: float = 0.0,
    duration: float | None = None,
    width: int | None = None,
    fps: float | None = None,
    hwaccel: str | None = None,
) -> Iterator[np.ndarray]:
    """Yield BGR frames decoded by ffmpeg, optionally resized and resampled.

    Interlaced sources read at full resolution are deinterlaced to one frame per
    field (yadif mode 1). Downscaled reads skip it: at low resolution the combing
    is negligible and yadif at full size would dominate the decoding cost.
    """
    filters = []
    downscale = bool(width) and width < info.width
    if info.interlaced and not downscale:
        filters.append("yadif=1")
    if fps:
        filters.append(f"fps={fps}")
    out_w, out_h = info.width, info.height
    if downscale:
        out_w = width
        out_h = round(info.height * width / info.width / 2) * 2
        filters.append(f"scale={out_w}:{out_h}")

    cmd = ["ffmpeg", "-v", "error", "-nostdin"]
    hwaccel = auto_hwaccel() if hwaccel == "auto" else hwaccel
    if hwaccel:
        cmd += ["-hwaccel", hwaccel]
    cmd += ["-ss", str(start), "-i", str(info.path)]
    if duration is not None:
        cmd += ["-t", str(duration)]
    if filters:
        cmd += ["-vf", ",".join(filters)]
    cmd += ["-an", "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1"]

    frame_bytes = out_w * out_h * 3
    # stderr goes to a temporary file: a pipe nobody reads fills up on broken streams and blocks ffmpeg
    err = tempfile.TemporaryFile()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err, bufsize=frame_bytes * 4)
    n = 0
    try:
        while True:
            buf = proc.stdout.read(frame_bytes)
            if len(buf) < frame_bytes:
                break
            n += 1
            yield np.frombuffer(buf, np.uint8).reshape(out_h, out_w, 3)
    finally:
        proc.stdout.close()
        proc.kill()
        proc.wait()
        err.seek(0)
        msg = err.read().decode(errors="replace").strip()
        err.close()
        # decoding warnings of a broadcast recording are normal; fail only when nothing came out
        if n == 0 and msg:
            raise VideoError(f"ffmpeg no pudo leer {Path(info.path).name}: {msg[-300:]}")


_SHOWINFO_TB = re.compile(r"config in time_base:\s*(\d+)/(\d+)")
_SHOWINFO_PTS = re.compile(r"\bn:\s*\d+\s+pts:\s*(-?\d+)")


def _frames_at_run(info: VideoInfo, targets: list[str], hwaccel: str | None) -> Iterator[np.ndarray | None]:
    """One ffmpeg process for a run of sorted target times (strings with 3 decimals, as `-ss` takes
    them): for each one, the first frame whose timestamp is >= it, or None when the video ends first."""
    import queue
    import threading

    t_ms = [round(float(t) * 1000) for t in targets]
    seek_s = max(0, t_ms[0] // 1000 - 1)        # whole seconds: the timestamp offset stays exact in any time base
    rel = [Fraction(m, 1000) - seek_s for m in t_ms]
    # first frame at or after each target, also across a timestamp gap: t >= T and the previous frame < T
    # (half a microsecond of slack: `-ss` rounds the target to microseconds the same way)
    expr = "+".join(f"gte(t\\,{float(r) - 5e-7:.7f})*not(gte(prev_t\\,{float(r) - 5e-7:.7f}))" for r in rel)
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-nostats", "-loglevel", "info"]
    hwaccel = auto_hwaccel() if hwaccel == "auto" else hwaccel
    if hwaccel:
        cmd += ["-hwaccel", hwaccel]
    if seek_s:
        cmd += ["-ss", str(seek_s)]
    cmd += ["-i", str(info.path), "-an", "-vf", f"select='{expr}',showinfo", "-fps_mode", "passthrough",
            "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1"]
    w, h = info.width, info.height
    frame_bytes = w * h * 3
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=frame_bytes)
    times: queue.Queue = queue.Queue()

    def drain():                                 # showinfo lines carry each selected frame's exact pts
        tb = None
        for raw in proc.stderr:
            line = raw.decode(errors="replace")
            m = _SHOWINFO_TB.search(line)
            if m and tb is None:
                tb = Fraction(int(m.group(1)), int(m.group(2)))
                continue
            m = _SHOWINFO_PTS.search(line)
            if m and tb is not None:
                times.put(int(m.group(1)) * tb)
        times.put(None)

    th = threading.Thread(target=drain, daemon=True)
    th.start()
    i = 0
    try:
        while i < len(rel):
            buf = proc.stdout.read(frame_bytes)
            if len(buf) < frame_bytes:
                break
            try:
                ft = times.get(timeout=120)
            except queue.Empty:
                ft = None
            if ft is None:
                break
            frame = np.frombuffer(buf, np.uint8).reshape(h, w, 3)
            # the frame answers every pending target at or before it (more than one only after a gap)
            while i < len(rel) and rel[i] <= ft + Fraction(1, 2_000_000):
                yield frame
                i += 1
    finally:
        proc.stdout.close()
        proc.kill()
        proc.wait()
        th.join(timeout=5)
        proc.stderr.close()
    # not reached by the stream (the video ended, or ffmpeg failed): one seek each, as before
    for t in targets[i:]:
        yield seek_frame(info, t)


def seek_frame(info: VideoInfo, t: str | float) -> np.ndarray | None:
    """The first full-resolution frame at or after time t (`-ss t -frames:v 1`), or None."""
    t = t if isinstance(t, str) else f"{t:.3f}"
    try:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", t, "-i", str(info.path), "-frames:v", "1", "-an",
                              "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1"], capture_output=True, timeout=120).stdout
    except subprocess.TimeoutExpired:          # one frame that hangs: none, as one that is not there
        return None
    n = info.width * info.height * 3
    return np.frombuffer(raw[:n], np.uint8).reshape(info.height, info.width, 3) if len(raw) >= n else None


def _frames_at(info: VideoInfo, times: list[float], hwaccel, dense_s: float, max_run: int):
    runs, cur = [], []
    for t in times:
        if cur and (len(cur) >= max_run or t - cur[-1] > dense_s):
            runs.append(cur)
            cur = []
        cur.append(t)
    if cur:
        runs.append(cur)
    for run in runs:
        if len(run) == 1:
            yield run[0], seek_frame(info, run[0])
            continue
        for t, fr in zip(run, _frames_at_run(info, [f"{t:.3f}" for t in run], hwaccel)):
            yield t, fr


def frames_at(info: VideoInfo, times: list[float], hwaccel: str | None = None, dense_s: float = 1.5,
              max_run: int = 60, prefetch: int = 3) -> Iterator[tuple[float, np.ndarray | None]]:
    """(t, frame) for each of the ascending times: the same frame as `ffmpeg -ss t -frames:v 1` (the
    first one at or after t to the millisecond, full resolution, not deinterlaced), or None after the
    end, as raw BGR (no image encoding in between).

    Times closer than dense_s to the previous one are decoded sequentially by one ffmpeg process
    (up to max_run of them); isolated times get one seek each, which decodes far fewer frames (a
    seek decodes from the previous keyframe; a sequential read decodes everything in between: at
    1080p50 one seek costs about as much as decoding 1-1.5 s of video). The frames are fetched in
    a background thread, up to `prefetch` ahead, so decoding overlaps with whatever the caller does
    with each frame (OCR)."""
    import queue
    import threading

    if any(b < a for a, b in zip(times, times[1:])):
        raise ValueError("frames_at needs ascending times")
    if prefetch <= 0:
        yield from _frames_at(info, times, hwaccel, dense_s, max_run)
        return
    q: queue.Queue = queue.Queue(maxsize=prefetch)
    stop = threading.Event()
    done = object()

    def produce():
        gen = _frames_at(info, times, hwaccel, dense_s, max_run)
        try:
            for item in gen:
                while not stop.is_set():
                    try:
                        q.put(item, timeout=0.5)
                        break
                    except queue.Full:
                        continue
                if stop.is_set():
                    break
        except BaseException as e:          # handed to the caller
            item = e
        else:
            item = done
        finally:
            gen.close()                     # kills a running ffmpeg
        while not stop.is_set():
            try:
                q.put(item, timeout=0.5)
                break
            except queue.Full:
                continue

    th = threading.Thread(target=produce, daemon=True)
    th.start()
    try:
        while True:
            item = q.get()
            if item is done:
                break
            if isinstance(item, BaseException):
                raise item
            yield item
    finally:
        stop.set()
        th.join(timeout=10)


def timeline(path: str | Path) -> dict:
    """Timestamps of the video packets: jumps (recorded broadcasts in .ts restart or skip their
    clock) and a variable frame rate (phones, some screen recordings). Reads the whole file once
    (packet headers only, no decoding)."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=dts_time",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600).stdout
    t = []
    for line in out.splitlines():
        try:
            t.append(float(line.strip().strip(",")))
        except ValueError:
            continue
    t = np.array(t)
    if len(t) < 3:
        return {"packets": len(t), "jumps": 0, "vfr": False}
    d = np.diff(t)
    jumps = int(np.sum((d > 1.0) | (d < -0.5)))
    reg = d[(d > 0) & (d <= 1.0)]
    vfr = bool(len(reg) > 10 and np.mean(np.abs(reg - np.median(reg)) > 0.25 * np.median(reg)) > 0.01)
    return {"packets": len(t), "jumps": jumps, "vfr": vfr}


def capture_path(path: str | Path) -> str:
    """Path string OpenCV can open. On Windows OpenCV's video reader does not accept non-ASCII
    paths (accents in a folder name): the short 8.3 form of the path is used then."""
    s = str(path)
    if os.name != "nt" or s.isascii():
        return s
    import ctypes

    buf = ctypes.create_unicode_buffer(1024)
    n = ctypes.windll.kernel32.GetShortPathNameW(s, buf, 1024)
    return buf.value if 0 < n < 1024 and buf.value.isascii() else s


def open_capture(path: str | Path):
    import cv2

    return cv2.VideoCapture(capture_path(path))


def capture_frames(path: str | Path, prefetch: int = 4) -> Iterator[np.ndarray]:
    """Every frame of a video with OpenCV, in order (the same frames as a cap.read() loop), decoded
    in a background thread up to `prefetch` frames ahead: decoding the next frames overlaps with the
    model working on the current one (OpenCV and ONNX Runtime release the GIL). Stopping early
    (break, exception) stops the thread."""
    import queue
    import threading

    q: queue.Queue = queue.Queue(maxsize=max(1, prefetch))
    stop = threading.Event()
    end = object()

    def put(item) -> bool:
        while not stop.is_set():
            try:
                q.put(item, timeout=0.1)
                return True
            except queue.Full:
                continue
        return False

    def reader():
        cap = open_capture(path)
        try:
            while not stop.is_set():
                ok, frame = cap.read()
                if not ok or not put(frame):
                    break
        except BaseException as e:            # handed to the consumer, never lost in the thread
            put(e)
        finally:
            cap.release()
            put(end)

    th = threading.Thread(target=reader, daemon=True)
    th.start()
    try:
        while True:
            item = q.get()
            if item is end:
                break
            if isinstance(item, BaseException):
                raise item
            yield item
    finally:
        stop.set()
        th.join(timeout=5)


def read_ahead(source, prefetch: int = 4, stats: dict | None = None) -> Iterator:
    """The items of the iterator `source()` makes, produced in a background thread up to `prefetch`
    ahead, in order: decoding (ffmpeg pipe) and any per-item preparation done inside `source` overlap
    with what the caller does with each item (the pose model on the iGPU; numpy, OpenCV and ONNX Runtime
    release the GIL). An error in the thread is raised in the caller; stopping early (break, exception)
    stops the thread and closes `source`'s iterator (which kills its ffmpeg).
    stats: when given, stats["busy_s"] adds up the thread's time producing the items."""
    import queue
    import threading
    import time

    q: queue.Queue = queue.Queue(maxsize=max(1, prefetch))
    stop = threading.Event()
    end = object()
    if stats is not None:
        stats.setdefault("busy_s", 0.0)

    def put(item) -> bool:
        while not stop.is_set():
            try:
                q.put(item, timeout=0.1)
                return True
            except queue.Full:
                continue
        return False

    def produce():
        it = None
        try:
            it = iter(source())
            while not stop.is_set():
                t0 = time.perf_counter()
                try:
                    item = next(it)
                except StopIteration:
                    break
                finally:
                    if stats is not None:
                        stats["busy_s"] += time.perf_counter() - t0
                if not put(item):
                    break
        except BaseException as e:            # handed to the consumer, never lost in the thread
            put(e)
        finally:
            close = getattr(it, "close", None)
            if close is not None:
                close()
            put(end)

    th = threading.Thread(target=produce, name="read_ahead", daemon=True)
    th.start()
    try:
        while True:
            item = q.get()
            if item is end:
                break
            if isinstance(item, BaseException):
                raise item
            yield item
    finally:
        stop.set()
        th.join(timeout=10)
