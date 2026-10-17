"""The identity of a match's video survives moving or copying it (no 4.5 h recomputation), keeps the
value of folders analysed before, and changes with a different video."""
import os
import shutil

from tennisbio.pipeline import video_fingerprint


def test_moved_or_copied_video_keeps_its_identity(tmp_path):
    v = tmp_path / "a.mp4"
    v.write_bytes(os.urandom(3 << 20))
    d = tmp_path / "out"
    legacy = video_fingerprint(v)                       # what the manifests of before were built with
    assert video_fingerprint(v, d) == legacy            # adopting it changes nothing
    w = tmp_path / "moved" / "a.mp4"
    w.parent.mkdir()
    shutil.copy(v, w)
    os.utime(w, (1_700_000_000, 1_700_000_000))         # a copy gets a new date
    assert video_fingerprint(w) != legacy and video_fingerprint(w, d) == legacy
    assert video_fingerprint(w, d) == legacy            # and the new date is remembered
    x = tmp_path / "other.mp4"
    x.write_bytes(os.urandom(3 << 20))
    os.utime(x, (1_700_000_100, 1_700_000_100))
    assert video_fingerprint(x, d) != legacy            # another video of the same size: new identity
