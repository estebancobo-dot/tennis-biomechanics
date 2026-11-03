"""The stroke videos' encoder is chosen by configuration (B5, 03-11) and times its own waiting."""
import shutil

import numpy as np
import pytest

from tennisbio import export as E


def test_default_encoder_is_libx264_and_every_encoder_has_its_arguments():
    assert E.encoder_name() == "libx264"
    assert set(E.ENCODERS) >= {"libx264", "h264_amf"}
    assert all(a[0] == "-c:v" for a in E.ENCODERS.values())


def test_unknown_configured_encoder_falls_back(monkeypatch):
    import tennisbio.config as C
    monkeypatch.setattr(C, "load_config", lambda: {"export": {"encoder": "nope"}})
    assert E.encoder_name() == "libx264"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg")
def test_encoder_writes_a_video_and_counts_its_wait(tmp_path):
    out = tmp_path / "a.mp4"
    enc = E.Encoder(out, size=(64, 48), codec="libx264")
    for i in range(10):
        enc.write(np.full((48, 64, 3), i * 20, np.uint8))
    enc.close()
    assert out.exists() and out.stat().st_size > 0 and enc.waited >= 0
