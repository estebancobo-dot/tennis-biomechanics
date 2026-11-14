"""The storage port (#289, task T4): where the analysis's results and the queue's state live, by adapter.

The core defines the port and its local adapter (the PC's disk, a mounted Modal volume, the tests); the cloud's own
adapters live with the cloud's code (cloud/almacen.py: the Modal volume from outside, for Kaggle and the queue), so the
analysis never imports a cloud library. Every adapter passes the same contract (`contract`), run by
tests/test_storage.py against each of them.

Paths are POSIX strings relative to the storage's root (a leading «/» is allowed and ignored).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path


class Storage:
    """The port: read a file, write files under a folder, bring a file or folder to the machine."""

    def read_bytes(self, path: str) -> bytes | None:          # None when it is not there
        raise NotImplementedError

    def put_files(self, files: list[Path], local_root: Path, remote_root: str) -> None:
        """Each file at remote_root/<its path relative to local_root>, replacing what was there."""
        raise NotImplementedError

    def get(self, remote: str, local_dir: Path) -> None:
        """A file or a folder into local_dir, keeping its last name (remote /a/b → local_dir/b)."""
        raise NotImplementedError

    def read_json(self, path: str):
        data = self.read_bytes(path)
        if data is None:
            return None
        try:
            return json.loads(data.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):  # esperado: not JSON: the same as not there, for the caller
            return None


class LocalStorage(Storage):
    """A folder of this machine as the storage (the PC, a Modal container with the volume mounted, the tests)."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def _at(self, path: str) -> Path:
        return self.root / str(path).lstrip("/")

    def read_bytes(self, path: str) -> bytes | None:
        f = self._at(path)
        return f.read_bytes() if f.is_file() else None

    def put_files(self, files: list[Path], local_root: Path, remote_root: str) -> None:
        for f in files:
            dst = self._at(f"{remote_root.rstrip('/')}/{Path(f).relative_to(local_root).as_posix()}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_name(dst.name + ".tmp")
            shutil.copyfile(f, tmp)
            tmp.replace(dst)                                   # never half a file for a reader

    def get(self, remote: str, local_dir: Path) -> None:
        src = self._at(remote)
        local_dir.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, local_dir / src.name, dirs_exist_ok=True)
        elif src.is_file():
            shutil.copy2(src, local_dir / src.name)
        else:
            raise FileNotFoundError(remote)


def contract(storage: Storage, work: Path) -> None:
    """What every adapter must do (raises AssertionError otherwise): files written are read back the same, a file
    written again replaces the old one, a missing file reads as None, a folder comes back with its files."""
    src = work / "contrato_local"
    (src / "sub").mkdir(parents=True, exist_ok=True)
    (src / "a.json").write_text('{"x": 1}', encoding="utf-8")
    (src / "sub" / "b.bin").write_bytes(b"\x00\x01")
    storage.put_files([src / "a.json", src / "sub" / "b.bin"], src, "/contrato/r")
    assert storage.read_json("/contrato/r/a.json") == {"x": 1}
    assert storage.read_bytes("contrato/r/sub/b.bin") == b"\x00\x01"
    (src / "a.json").write_text('{"x": 2}', encoding="utf-8")
    storage.put_files([src / "a.json"], src, "/contrato/r")
    assert storage.read_json("/contrato/r/a.json") == {"x": 2}
    assert storage.read_bytes("/contrato/r/nada.json") is None and storage.read_json("/contrato/r/nada.json") is None
    out = work / "contrato_traido"
    storage.get("/contrato/r", out)
    assert (out / "r" / "a.json").read_text(encoding="utf-8") == '{"x": 2}' and (out / "r" / "sub" / "b.bin").exists()
