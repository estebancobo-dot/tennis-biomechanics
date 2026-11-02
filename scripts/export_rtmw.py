"""RTMW-x 2D whole-body pose (OpenMMLab MMPose, Apache 2.0; COCO-WholeBody 133 points, 384x288) as ONNX.

Candidate of docs/plan_maestro.md, "Plan a corto plazo (02-11)", paso 2 (B-15c, esqueleto): measured on the PC
against our pose (YOLO11m-pose + RTMPose-x Halpe26 on the big people, tennisbio.pose.hybrid) with
scripts/bench_candidates.py; not used by any stage. The reference project measured it at OKS 0.855 (feet 0.833).

OpenMMLab already publishes it in ONNX (the same file rtmlib downloads), so nothing is re-declared: this script
downloads the zip with a time limit, keeps its `end2end.onnx` as models/rtmw-x_384x288.onnx and checks that
onnxruntime (CPU) runs it with a batch of crops (outputs SimCC x (n, 133, 576) and y (n, 133, 768)). There is no
PyTorch model to compare with.

    uv run python scripts/export_rtmw.py [--out models/rtmw-x_384x288.onnx]
"""
import argparse
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _candidate_export import download  # noqa: E402

URL = ("https://download.openmmlab.com/mmpose/v1/projects/rtmw/onnx_sdk/"
       "rtmw-dw-x-l_simcc-cocktail14_270e-384x288_20231122.zip")
KEYPOINTS, W, H, SPLIT = 133, 288, 384, 2.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", default="models/rtmw-x_384x288.zip")
    ap.add_argument("--out", default="models/rtmw-x_384x288.onnx")
    args = ap.parse_args()
    import numpy as np
    import onnxruntime as ort

    out = Path(args.out)
    if not out.exists():
        z = download(URL, Path(args.zip))
        with zipfile.ZipFile(z) as zf:
            name = next(n for n in zf.namelist() if n.endswith("end2end.onnx"))
            tmp = out.with_name(out.name + ".part")
            tmp.write_bytes(zf.read(name))
            tmp.replace(out)
    sess = ort.InferenceSession(str(out), providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0]
    n = 2 if not isinstance(inp.shape[0], int) else inp.shape[0]
    x = np.random.default_rng(0).standard_normal((n, 3, H, W)).astype(np.float32)
    sx, sy = sess.run(None, {inp.name: x})
    ok = sx.shape == (n, KEYPOINTS, int(W * SPLIT)) and sy.shape == (n, KEYPOINTS, int(H * SPLIT))
    print(f"guardado {out}; entrada {inp.shape}; salidas {sx.shape} {sy.shape}; "
          + ("forma correcta" if ok else "FORMA INESPERADA") + "; sin modelo PyTorch con el que comparar (ONNX oficial)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
