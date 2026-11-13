"""N0 (13-11, #273): loaded by Python at start-up in the cloud's container through an «import nube_gpu» line of the
tennisbio_nube.pth file (cloud/nube.py pth_text), so also in the fine pass's worker processes (spawn). With
TENNISBIO_DML_IS_CUDA=1 the device the configuration calls «dml» puts its ONNX sessions on CUDA: every code path stays
the PC's (cloud/nube.py). Without the variable it does nothing.

13-11: first a sitecustomize.py, which the container's Python never loaded (the image has its own: «comprobar» saw the
DirectML providers in a new process); a .pth import line runs in every case. It imports nothing at start-up: a hook on
the import system patches tennisbio.pose.estimator right after it is loaded, in the processes that load it."""
import importlib.machinery
import os
import sys

TARGET = "tennisbio.pose.estimator"
# 13-11: Pegula's 10-minute test: the fine pass's two workers each open several CUDA sessions (pose 640 and 960, RTMPose-x,
# RTMW3D-x, ball, racket); with ONNX Runtime's defaults (an arena that doubles, cuDNN's exhaustive search with the
# largest workspace) the T4's 15 GB filled up and the next sessions failed («CUBLAS_STATUS_ALLOC_FAILED») and went to
# the CPU: the same points, many times slower. Each session takes only what it asks for; cuDNN picks its algorithm by
# heuristics within a small workspace.
CUDA_OPTIONS = {"arena_extend_strategy": "kSameAsRequested", "cudnn_conv_algo_search": "HEURISTIC",
                "cudnn_conv_use_max_workspace": "0"}
SHRINK = True                              # give back the GPU memory a run no longer needs (CudaSession.run)


def provider_options(providers) -> list | None:
    """ONNX Runtime's provider_options for a providers list of names: CUDA_OPTIONS for CUDA, none for the rest."""
    names = [p if isinstance(p, str) else p[0] for p in (providers or [])]
    if "CUDAExecutionProvider" not in names or any(not isinstance(p, str) for p in providers):
        return None
    return [dict(CUDA_OPTIONS) if p == "CUDAExecutionProvider" else {} for p in names]


def _patch(est) -> None:
    try:
        import onnxruntime as ort
        try:
            ort.preload_dlls()          # the CUDA and cuDNN libraries of the onnxruntime-gpu[cuda,cudnn] wheels
        except Exception as e:  # noqa: BLE001 — older wheels: the system libraries are used
            print(f"AVISO nube: preload_dlls ({e})")
        est.ORT_PROVIDERS["dml"] = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        base = ort.InferenceSession
        if not getattr(base, "_nube", False):

            class CudaSession(base):
                """ONNX Runtime's session with CUDA_OPTIONS whenever it is put on CUDA by name, and (13-11, Osaka's
                4th test: 14.6 of 15 GB, 14 of 58 windows failed «Failed to allocate memory») the GPU memory a run
                no longer needs given back after every run: idle sessions (the cheap pass's, still loaded in the
                main process) keep only their weights, so the fine pass's workers have the rest."""
                _nube = True

                def __init__(self, path_or_bytes, sess_options=None, providers=None, provider_options=None, **kw):
                    if provider_options is None:
                        provider_options = globals()["provider_options"](providers)
                    super().__init__(path_or_bytes, sess_options, providers, provider_options, **kw)
                    self._shrink = None
                    if SHRINK and "CUDAExecutionProvider" in self.get_providers():
                        self._shrink = ort.RunOptions()
                        self._shrink.add_run_config_entry("memory.enable_memory_arena_shrinkage", "gpu:0")

                def run(self, output_names, input_feed, run_options=None):
                    return super().run(output_names, input_feed, run_options if run_options is not None
                                       else self._shrink)
            ort.InferenceSession = CudaSession
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
