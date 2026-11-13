"""N0 (13-11, #273): imported by Python at start-up in the cloud's container (cloud/site is on PYTHONPATH there), also in
the fine pass's worker processes (spawn). With TENNISBIO_DML_IS_CUDA=1 the device the configuration calls «dml» puts its
ONNX sessions on CUDA: every code path stays the PC's (cloud/nube.py). Without the variable it does nothing."""
import os

if os.environ.get("TENNISBIO_DML_IS_CUDA") == "1":
    try:
        import onnxruntime as _ort
        try:
            _ort.preload_dlls()          # the CUDA and cuDNN libraries of the onnxruntime-gpu[cuda,cudnn] wheels
        except Exception as _e:  # noqa: BLE001 — older wheels: the system libraries are used
            print(f"AVISO nube: preload_dlls ({_e})")
        from tennisbio.pose import estimator as _est
        _est.ORT_PROVIDERS["dml"] = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    except Exception as _e:  # noqa: BLE001 — said loudly: the run then is on the CPU, and «comprobar» shows it
        print(f"AVISO nube: no se pudo poner la GPU de la nube ({_e})")
