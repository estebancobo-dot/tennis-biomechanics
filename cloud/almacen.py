"""The Modal volume as an adapter of the storage port (tennisbio.infra.storage, #289 T4), from outside Modal: Kaggle's
sessions (cloud/kaggle/correr.py) and the queue in GitHub Actions (cloud/cola.py). Inside a Modal container the volume
is mounted and the core's LocalStorage is used instead. It passes the same contract as every adapter
(tests/test_storage.py, with a volume double).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tennisbio.infra.storage import Storage  # noqa: E402

VOLUME = "tennisbio-datos"


class ModalStorage(Storage):
    """`vol`: a modal.Volume (or a double with read_file and batch_upload); `get` uses Modal's command line, which
    brings whole folders (the CLI keeps the last name: /models → local_dir/models)."""

    def __init__(self, vol, volume_name: str = VOLUME, run=subprocess.run):
        self.vol, self.name, self._run = vol, volume_name, run

    def read_bytes(self, path: str) -> bytes | None:
        try:
            return b"".join(self.vol.read_file(str(path).lstrip("/")))
        except Exception as e:  # noqa: BLE001 — not there (Modal's own NotFound or a FileNotFoundError)
            self.last_error = f"{type(e).__name__}: {str(e)[:200]}"
            return None

    def put_files(self, files: list[Path], local_root: Path, remote_root: str) -> None:
        if not files:
            return
        with self.vol.batch_upload(force=True) as b:
            for f in files:
                b.put_file(str(f), f"{remote_root.rstrip('/')}/{Path(f).relative_to(local_root).as_posix()}")

    def get(self, remote: str, local_dir: Path) -> None:
        local_dir.mkdir(parents=True, exist_ok=True)
        cmd = ["modal", "volume", "get", "--force", self.name, remote, str(local_dir) + "/"]
        print("$", " ".join(cmd), flush=True)
        self._run(cmd, check=True)
