import shutil
import subprocess

import cv2
import numpy as np
import pytest

from tennisbio.audit import export_videos_item
from tennisbio.export import SKC

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="sin ffmpeg")


def _video(path, seconds=4.0, skeleton=True, codec="libx264"):
    frames = path.parent / f"{path.stem}_f"
    frames.mkdir(parents=True)
    for i in range(int(seconds * 10)):
        img = np.full((180, 320, 3), 60, np.uint8)
        if skeleton:
            cv2.line(img, (100, 40), (100, 140), SKC["l"], 4)
            cv2.line(img, (200, 40), (200, 140), SKC["r"], 4)
        cv2.imwrite(str(frames / f"{i:04d}.png"), img)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "10", "-i", str(frames / "%04d.png"), "-c:v", codec,
                    "-pix_fmt", "yuv420p", str(path)], check=True, timeout=60)


def test_playable_videos_with_their_skeleton_pass(tmp_path):
    for k in range(3):
        _video(tmp_path / "exportar_derecha" / "golpes" / f"g{k}.mp4")
    it = export_videos_item(tmp_path / "exportar_derecha")
    assert it["status"] == "ok" and "3 con el esqueleto" in it["detail"], it


def test_a_video_without_skeleton_or_too_short_fails(tmp_path):
    _video(tmp_path / "exportar_reves" / "golpes" / "g0.mp4", skeleton=False)
    _video(tmp_path / "exportar_reves" / "golpes" / "g1.mp4", seconds=1.0)
    it = export_videos_item(tmp_path / "exportar_reves")
    assert it["status"] == "falta" and "g1.mp4: dura" in it["detail"]
    assert export_videos_item(tmp_path / "vacia") is None
