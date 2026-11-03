"""PP-OCRv5 text detector and recogniser (mobile) for the scoreboard candidate (paso 2.5, B3, request #201).

Measured on the PC against our rapidocr-onnxruntime 1.4 (PP-OCRv4) with scripts/bench_candidates.py; not used by
any stage. The models are already ONNX: RapidAI converted PaddleOCR's PP-OCRv5 mobile models and lists them, with
their SHA256, in rapidocr 3.10.0's `default_models.yaml` (tennisbio.candidates.ocr5.MODELS):

    https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.10.0/onnx/PP-OCRv5/det/ch_PP-OCRv5_det_mobile.onnx
    https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.10.0/onnx/PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile.onnx

This script downloads them to models/ppocrv5/ and checks their SHA256 (the recogniser carries its character list
inside). PaddleOCR has no PyTorch version; RapidAI publishes one for its torch engine (same folder, `torch/`, .pth),
converted separately from the same Paddle weights. With --check the two conversions are compared on a random input
(largest absolute difference of the detector's probability map and of the recogniser's character probabilities),
which needs rapidocr 3.x and torch:

    uv run python scripts/export_ppocrv5.py [--out models/ppocrv5/ch_PP-OCRv5_rec_mobile.onnx]
    uv run --with rapidocr==3.10.0 python scripts/export_ppocrv5.py --check      (torch: uv sync --extra yolo)
"""
import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from _candidate_export import download  # noqa: E402

from tennisbio.candidates.ocr5 import MODELS, TORCH  # noqa: E402

CHECK_SHAPES = {"det": (1, 3, 320, 480), "rec": (2, 3, 48, 320)}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(entry, folder: Path) -> Path:
    name, url, digest = entry
    p = download(url, folder / name)
    got = sha256(p)
    if got != digest:
        p.unlink()
        raise SystemExit(f"{name}: SHA256 {got} no es el publicado ({digest}); borrado")
    return p


def check(onnx_path: Path, pth: Path, shape) -> float:
    """Largest absolute difference between the ONNX model (onnxruntime CPU) and rapidocr's PyTorch network built
    from the .pth (its own ModelLoader and arch_config.yaml) on a random input."""
    import numpy as np
    import onnxruntime as ort
    import torch
    from rapidocr.inference_engine.pytorch.networks.main import ModelLoader

    net = ModelLoader({"model_path": str(pth)}, torch.device("cpu")).predictor
    x = np.random.default_rng(0).uniform(-1, 1, shape).astype(np.float32)        # inputs are (img/255 - 0.5)/0.5
    with torch.no_grad():
        ref = net(torch.from_numpy(x))
    ref = (ref if torch.is_tensor(ref) else ref[0]).numpy()
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    got = sess.run(None, {sess.get_inputs()[0].name: x})[0]
    if got.shape != ref.shape:
        raise SystemExit(f"{onnx_path.name}: forma {got.shape} frente a {ref.shape}")
    return float(np.abs(ref - got).max())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path("models") / "ppocrv5" / MODELS["rec"][0]),
                    help="the recogniser's path (the detector goes next to it)")
    ap.add_argument("--check", action="store_true", help="compare with RapidAI's PyTorch version (rapidocr 3.x + torch)")
    a = ap.parse_args()
    folder = Path(a.out).parent
    paths = {k: fetch(v, folder) for k, v in MODELS.items()}
    print("modelos:", ", ".join(f"{k} {p} ({p.stat().st_size} bytes, SHA256 correcto)" for k, p in paths.items()))
    if a.check:
        for k in ("det", "rec"):
            pth = fetch(TORCH[k], folder / "torch")
            print(f"{k}: diferencia máxima ONNX frente a PyTorch: {check(paths[k], pth, CHECK_SHAPES[k]):.2e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
