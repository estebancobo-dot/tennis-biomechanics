"""Video access through ffmpeg: metadata and streaming of decoded frames."""
import json
import subprocess
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


def probe(path: str | Path) -> VideoInfo:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    info = json.loads(out)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    audio = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    return VideoInfo(
        path=Path(path),
        width=int(video["width"]),
        height=int(video["height"]),
        fps=float(Fraction(video["avg_frame_rate"])),
        duration=float(info["format"]["duration"]),
        codec=video["codec_name"],
        interlaced=video.get("field_order", "progressive") not in ("progressive", "unknown"),
        audio_rate=int(audio["sample_rate"]) if audio else None,
        audio_channels=int(audio["channels"]) if audio else None,
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
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=frame_bytes * 4)
    try:
        while True:
            buf = proc.stdout.read(frame_bytes)
            if len(buf) < frame_bytes:
                break
            yield np.frombuffer(buf, np.uint8).reshape(out_h, out_w, 3)
    finally:
        proc.stdout.close()
        proc.kill()
        stderr = proc.stderr.read().decode(errors="replace").strip()
        proc.wait()
        if stderr:
            raise RuntimeError(f"ffmpeg: {stderr}")
