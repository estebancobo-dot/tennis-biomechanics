"""Video access through ffmpeg: metadata and streaming of decoded frames."""
import json
import os
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
                             capture_output=True, text=True, check=True, encoding="utf-8", errors="replace").stdout
    except FileNotFoundError:
        raise VideoError("No se encuentra ffprobe/ffmpeg: ejecuta 1_instalar.bat") from None
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


def timeline(path: str | Path) -> dict:
    """Timestamps of the video packets: jumps (recorded broadcasts in .ts restart or skip their
    clock) and a variable frame rate (phones, some screen recordings). Reads the whole file once
    (packet headers only, no decoding)."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=dts_time",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
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
