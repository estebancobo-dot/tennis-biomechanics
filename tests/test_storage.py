"""The storage port (#289, T4): every adapter passes the same contract (tennisbio.infra.storage.contract)."""
import sys
from pathlib import Path

from tennisbio.infra.storage import LocalStorage, contract

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud"))
import almacen  # noqa: E402


class FakeVolume:
    """A Modal volume double: read_file and batch_upload as Modal's, the files in memory; `get` through a fake
    command line that copies from the same memory."""

    def __init__(self):
        self.files = {}

    def read_file(self, path):
        if path not in self.files:
            raise FileNotFoundError(path)
        return [self.files[path]]

    def batch_upload(self, force=False):
        vol = self

        class B:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def put_file(self, src, dst):
                assert force
                vol.files[dst.lstrip("/")] = Path(src).read_bytes()
        return B()

    def cli(self, cmd, check=True):
        remote, local = cmd[-2].lstrip("/"), Path(cmd[-1])
        name = remote.rstrip("/").split("/")[-1]
        for k, v in self.files.items():
            if k == remote or k.startswith(remote.rstrip("/") + "/"):
                rel = name if k == remote else name + "/" + k[len(remote.rstrip("/")) + 1:]
                (local / rel).parent.mkdir(parents=True, exist_ok=True)
                (local / rel).write_bytes(v)


def test_local_storage_contract(tmp_path):
    contract(LocalStorage(tmp_path / "almacen"), tmp_path)


def test_modal_storage_contract(tmp_path):
    vol = FakeVolume()
    contract(almacen.ModalStorage(vol, run=vol.cli), tmp_path)

