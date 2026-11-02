"""Shared by the export scripts of the candidate models (scripts/export_wasb.py, export_court_tcd.py,
export_rfdetr.py, export_f3ed.py, export_rtmw.py): a download with a time limit that never leaves half a file,
and the check that the ONNX model gives what PyTorch gives (onnxruntime on the CPU, random input)."""
from __future__ import annotations

import time
import urllib.request
from pathlib import Path

TIMEOUT_S = 60            # per read of the connection; a stalled download fails instead of hanging
MAX_S = 3600              # a whole file


def download(url: str, dest: Path, timeout: float = TIMEOUT_S, max_s: float = MAX_S) -> Path:
    """dest, downloaded from url when it is not there yet (written to .part and renamed when complete).
    Google Drive's large files answer with an HTML warning page instead of the file: that is an error here."""
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    print(f"descargando {url}", flush=True)
    t0 = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 tennisbio"})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(tmp, "wb") as f:
        if "text/html" in (r.headers.get("Content-Type") or ""):
            raise RuntimeError(f"{url} devolvió una página web, no el fichero (enlace caducado o cuota de Google Drive)")
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            if time.time() - t0 > max_s:
                raise TimeoutError(f"la descarga de {url} tarda más de {max_s / 60:.0f} min")
    tmp.replace(dest)
    return dest


def check_onnx(model, onnx_path: str | Path, inputs: list, outputs: list[int] | None = None) -> float:
    """Largest absolute difference between the PyTorch model and its ONNX export (onnxruntime, CPU) on `inputs`
    (torch tensors, one per model input). outputs: which outputs to compare (all by default)."""
    import numpy as np
    import onnxruntime as ort
    import torch

    with torch.no_grad():
        ref = model(*inputs)
    ref = [ref] if torch.is_tensor(ref) else list(ref)
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    got = sess.run(None, {i.name: x.numpy() for i, x in zip(sess.get_inputs(), inputs)})
    idx = outputs if outputs is not None else range(len(ref))
    return max(float(np.abs(ref[k].float().numpy() - got[k]).max()) for k in idx)
