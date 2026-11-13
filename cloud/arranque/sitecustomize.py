"""N0 (13-11, #273): imported by Python at start-up in the cloud's container (cloud/arranque is on the path there, by a .pth file), also in
the fine pass's worker processes (spawn). With TENNISBIO_DML_IS_CUDA=1 the device the configuration calls «dml» puts its
ONNX sessions on CUDA: every code path stays the PC's (cloud/nube.py). Without the variable it does nothing.

13-11: it no longer imports anything at start-up (the container's own Python processes, Modal's included, start as
before): a hook on the import system patches tennisbio.pose.estimator right after it is loaded, in the processes that
load it."""
import importlib.machinery
import os
import sys

TARGET = "tennisbio.pose.estimator"


def _patch(est) -> None:
    try:
        import onnxruntime as ort
        try:
            ort.preload_dlls()          # the CUDA and cuDNN libraries of the onnxruntime-gpu[cuda,cudnn] wheels
        except Exception as e:  # noqa: BLE001 — older wheels: the system libraries are used
            print(f"AVISO nube: preload_dlls ({e})")
        est.ORT_PROVIDERS["dml"] = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    except Exception as e:  # noqa: BLE001 — said loudly: the run then is on the CPU, and «comprobar» shows it
        print(f"AVISO nube: no se pudo poner la GPU de la nube ({e})")


class _Hook:
    """Finds TARGET with the normal path finder and runs _patch on the module once it has been executed."""

    def find_spec(self, name, path=None, target=None):
        if name != TARGET:
            return None
        spec = importlib.machinery.PathFinder.find_spec(name, path)
        if spec is None or spec.loader is None:
            return spec
        run = spec.loader.exec_module

        def exec_module(module):
            run(module)
            _patch(module)
        spec.loader.exec_module = exec_module
        return spec


if os.environ.get("TENNISBIO_DML_IS_CUDA") == "1":
    sys.meta_path.insert(0, _Hook())
