"""Proof of concept T6 (docs/nube_nativa.md, #288): the racket model (40 % of the fine pass) with each inference option
on this machine's GPU: ONNX Runtime CUDA (today) against TensorRT in FP32 and FP16, in batches of 1 to 64. Same inputs
for all (fixed seed); each option's outputs are compared with CUDA FP32's (largest difference and keypoints moved), and
its time per image is measured. Read only: it changes nothing of the analysis.

    python -m tennisbio.infra.poc_raqueta --modelo models/racketpose.onnx --salida poc.json
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

OPTIONS = {
    "cuda_fp32": (["CUDAExecutionProvider"], {}),
    "tensorrt_fp32": (["TensorrtExecutionProvider", "CUDAExecutionProvider"], {"trt_fp16_enable": False}),
    "tensorrt_fp16": (["TensorrtExecutionProvider", "CUDAExecutionProvider"], {"trt_fp16_enable": True}),
}
BATCHES = (1, 8, 16, 32, 64)


def _session(model: str, providers: list, trt_opts: dict, cache: Path):
    import onnxruntime as ort

    provs = []
    for p in providers:
        if p == "TensorrtExecutionProvider":
            cache.mkdir(parents=True, exist_ok=True)
            provs.append((p, {**trt_opts, "trt_engine_cache_enable": True, "trt_engine_cache_path": str(cache)}))
        else:
            provs.append(p)
    return ort.InferenceSession(model, providers=provs)


def compare(ref: list[np.ndarray], out: list[np.ndarray]) -> dict:
    """Largest absolute difference of the outputs, and how many keypoints move (argmax of each SimCC row)."""
    diff = max(float(np.max(np.abs(a.astype(np.float32) - b.astype(np.float32)))) for a, b in zip(ref, out))
    moved = sum(int(np.sum(np.argmax(a, axis=-1) != np.argmax(b, axis=-1))) for a, b in zip(ref, out) if a.ndim == 3)
    total = sum(int(np.prod(a.shape[:-1])) for a in ref if a.ndim == 3)
    return {"max_diff": round(diff, 5), "puntos_movidos": moved, "puntos": total}


def run(model: str, work: Path, repeats: int = 20) -> dict:
    import onnxruntime as ort

    out = {"proveedores": ort.get_available_providers(), "opciones": {}}
    rng = np.random.default_rng(0)
    probe = ort.InferenceSession(model, providers=["CPUExecutionProvider"])
    inp = probe.get_inputs()[0]
    shape = [d if isinstance(d, int) else None for d in inp.shape]
    out["entrada"] = {"nombre": inp.name, "forma": [d if d is not None else "N" for d in shape]}
    batches = BATCHES if shape[0] is None else (shape[0],)
    data = {b: rng.standard_normal((b, *shape[1:])).astype(np.float32) for b in batches}
    ref: dict = {}
    for name, (provs, opts) in OPTIONS.items():
        res = {}
        try:
            sess = _session(model, provs, opts, work / f"trt_{name}")
            res["proveedor_usado"] = sess.get_providers()[0]
            t0 = time.time()
            sess.run(None, {inp.name: data[batches[0]]})        # build (TensorRT engines) and warm up
            res["primera_s"] = round(time.time() - t0, 1)
            for b in batches:
                for _ in range(3):
                    sess.run(None, {inp.name: data[b]})
                t0 = time.perf_counter()
                for _ in range(repeats):
                    y = sess.run(None, {inp.name: data[b]})
                ms = (time.perf_counter() - t0) / repeats * 1000
                res[f"lote_{b}"] = {"ms_por_imagen": round(ms / b, 3)}
                if name == "cuda_fp32":
                    ref[b] = y
                elif b in ref:
                    res[f"lote_{b}"].update(compare(ref[b], y))
        except Exception as e:  # esperado: an option this machine cannot run is reported, the others go on  # noqa: BLE001
            res["error"] = f"{type(e).__name__}: {str(e)[:300]}"
        out["opciones"][name] = res
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", required=True)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--repeticiones", type=int, default=20)
    a = ap.parse_args(argv)
    res = run(a.modelo, Path(a.salida).parent, a.repeticiones)
    Path(a.salida).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
