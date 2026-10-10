import subprocess

import pytest

from tennisbio.io.video import probe, read_frames


@pytest.fixture(scope="module")
def interlaced_video(tmp_path_factory):
    path = tmp_path_factory.mktemp("video") / "inter.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=640x360:rate=25",
         "-f", "lavfi", "-i", "sine=d=2", "-shortest", "-flags", "+ildct+ilme", "-top", "1", str(path)],
        check=True,
    )
    return path


def test_probe(interlaced_video):
    info = probe(interlaced_video)
    assert (info.width, info.height, info.fps) == (640, 360, 25.0)
    assert info.interlaced
    assert info.audio_rate == 44100


def test_full_resolution_is_deinterlaced_per_field(interlaced_video):
    frames = list(read_frames(probe(interlaced_video), start=0, duration=1))
    assert len(frames) == 50
    assert frames[0].shape == (360, 640, 3)


def test_downscaled_and_resampled(interlaced_video):
    frames = list(read_frames(probe(interlaced_video), start=0, duration=1, width=320, fps=5))
    assert len(frames) == 5
    assert frames[0].shape == (180, 320, 3)
