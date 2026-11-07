import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import bench_candidates as B  # noqa: E402


def _zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Dataset/game1/Clip1/Label.csv", "file name,visibility\n0000.jpg,0\n" * 2000)
    return buf.getvalue()


class _Resp:
    def __init__(self, data: bytes, status: int, cut: bool):
        self.data, self.status, self.cut, self.pos = data, status, cut, 0

    def read(self, n):
        if self.cut and self.pos >= len(self.data) // 2:
            raise OSError("connection reset")
        b = self.data[self.pos:self.pos + min(n, 1000)]
        self.pos += len(b)
        return b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_a_cut_download_resumes_where_it_stopped(tmp_path, monkeypatch):
    """Request 125: the TrackNet zip died at 2.3 of 2.6 GB and the bounce measure was lost; the next try goes on."""
    data, calls = _zip_bytes(), []
    monkeypatch.setattr("time.sleep", lambda s: None)

    def opener(req, timeout=None):
        rng = req.headers.get("Range")
        calls.append(rng)
        start = int(rng.split("=")[1].rstrip("-")) if rng else 0
        return _Resp(data[start:], 206 if rng else 200, cut=not calls[1:])

    z = B.tracknet_download(tmp_path, url="http://x", opener=opener)
    assert z.namelist() == ["Dataset/game1/Clip1/Label.csv"]
    assert calls[0] is None and calls[1].startswith("bytes=") and calls[1] != "bytes=0-"
    assert (tmp_path / "tracknet" / "Dataset.zip").exists() and not (tmp_path / "tracknet" / "Dataset.part").exists()


def test_the_zip_the_user_saved_in_a_folder_dataset_is_used(tmp_path):
    """07-11: the user downloaded it by hand to C:\\tenis\\dataset\\tracknet (not «datasets»)."""
    root = tmp_path / "datasets"
    root.mkdir()
    (tmp_path / "dataset" / "tracknet").mkdir(parents=True)
    (tmp_path / "dataset" / "tracknet" / "Dataset.zip").write_bytes(_zip_bytes())
    assert B.tracknet_local(root) == tmp_path / "dataset" / "tracknet" / "Dataset.zip"
    assert B.tracknet_download(root, url="http://never", opener=None).namelist() == ["Dataset/game1/Clip1/Label.csv"]
