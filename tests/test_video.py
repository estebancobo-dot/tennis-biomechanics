import subprocess

import pytest

from tennisbio.io.video import probe, read_frames


@pytest.fixture(scope="module")
def interlaced_video(tmp_path_factory):
    path = tmp_path_factory.mktemp("video") / "inter.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=640x360:rate=25",
         # setfield (not -top, removed in ffmpeg 9): top field first, encoded as interlaced
         "-f", "lavfi", "-i", "sine=d=2", "-shortest", "-vf", "setfield=tff", "-flags", "+ildct+ilme",
         "-c:v", "libx264", "-c:a", "aac", str(path)],
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


def test_choose_audio_track_prefers_the_one_sounding_with_the_swings():
    import numpy as np
    from tennisbio.stages import choose_audio_track
    rng = np.random.default_rng(0)
    peaks = np.sort(rng.uniform(0, 600, 80))
    ambient = {"t": list(peaks + rng.normal(0.05, 0.03, 80)) + list(rng.uniform(0, 600, 40))}
    commentary = {"t": list(np.arange(0, 600, 0.6))}        # dense onsets: many matches by chance
    assert choose_audio_track([commentary, ambient], peaks, 0.35, 600) == 1
    assert choose_audio_track([ambient, commentary], peaks, 0.35, 600) == 0


def _ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def test_timeline_finds_clock_jumps_and_variable_rate(tmp_path):
    from tennisbio.io.video import timeline
    src = ["-f", "lavfi", "-i", "testsrc=duration=2:size=160x120:rate=25"]
    _ff(*src, "-c:v", "libx264", "-f", "mpegts", str(tmp_path / "a.ts"))
    _ff(*src, "-c:v", "libx264", "-output_ts_offset", "500", "-f", "mpegts", str(tmp_path / "b.ts"))
    (tmp_path / "j.ts").write_bytes((tmp_path / "a.ts").read_bytes() + (tmp_path / "b.ts").read_bytes())
    assert timeline(tmp_path / "j.ts")["jumps"] >= 1
    assert timeline(tmp_path / "a.ts") ["jumps"] == 0
    _ff(*src, "-vf", "select='not(eq(mod(n\\,4)\\,1))'", "-fps_mode", "vfr", "-c:v", "libx264", str(tmp_path / "v.mp4"))
    assert timeline(tmp_path / "v.mp4")["vfr"]
    assert not timeline(tmp_path / "a.ts")["vfr"]


def test_probe_errors_are_for_the_user(tmp_path):
    from tennisbio.io.video import VideoError
    (tmp_path / "x.mp4").write_text("hola")
    with pytest.raises(VideoError, match="dañado"):
        probe(tmp_path / "x.mp4")
    _ff("-f", "lavfi", "-i", "sine=d=1", str(tmp_path / "a.mp4"))
    with pytest.raises(VideoError, match="no tiene pista de vídeo"):
        probe(tmp_path / "a.mp4")
    with pytest.raises(VideoError, match="No existe"):
        probe(tmp_path / "nada.mp4")


def test_audio_tracks_counted(tmp_path):
    _ff("-f", "lavfi", "-i", "testsrc=duration=1:size=160x120:rate=25", "-f", "lavfi", "-i", "sine=d=1",
        "-f", "lavfi", "-i", "anoisesrc=d=1", "-map", "0", "-map", "1", "-map", "2", str(tmp_path / "t.mkv"))
    assert probe(tmp_path / "t.mkv").audio_tracks == 2
