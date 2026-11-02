"""Export the RF-DETR Medium person detector (Roboflow, Apache 2.0; COCO) to ONNX, at the resolution used in the
reference project (1152 px: far player found in 100 % of its annotated frames, against 98.5 % for YOLO11m).

Candidate of docs/plan_maestro.md, "Plan a corto plazo (02-11)", paso 2 (B-15c, far player): measured on the PC
against our far-player search (YOLO11m-pose on the far half, tennisbio.pose.yolo.detect_people) with
scripts/bench_candidates.py; not used by any stage.

RF-DETR has its own ONNX exporter in the `rfdetr` package, which is not a dependency of this project: run it in a
throw-away environment on top of ours (torch comes from the `yolo` extra):

    uv run --with rfdetr==1.11.2 python scripts/export_rfdetr.py [--resolution 1152] [--out models/rfdetr_medium_1152.onnx]

Input: the frame resized to resolution x resolution (bilinear, no antialias), RGB, /255, ImageNet-normalised.
Outputs: `dets` (n, 300, 4) boxes cx, cy, w, h normalised to the input, and `labels` (n, 300, 91) class logits
(COCO; person = 1). Post-processing: tennisbio.candidates.rfdetr.

Weights: https://storage.googleapis.com/rfdetr/medium_coco/checkpoint_best_regular.pth (the URL the rfdetr package
itself uses for "rf-detr-medium.pth"; md5 7223f764a87b863f02eb8d52bf0ce2ee).
"""
import argparse
import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _candidate_export import download  # noqa: E402

URL = "https://storage.googleapis.com/rfdetr/medium_coco/checkpoint_best_regular.pth"
MD5 = "7223f764a87b863f02eb8d52bf0ce2ee"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="models/rf-detr-medium.pth")
    ap.add_argument("--resolution", type=int, default=1152, help="lado de la entrada (múltiplo de 32)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    if args.resolution % 32:
        sys.exit("--resolution debe ser múltiplo de 32 (parche 16 × 2 ventanas)")
    out = Path(args.out or f"models/rfdetr_medium_{args.resolution}.onnx")
    try:
        import numpy as np
        import onnxruntime as ort
        import torch
        from rfdetr import RFDETRMedium
    except ImportError as e:
        sys.exit(f"falta {e.name}: ejecútalo con `uv run --with rfdetr==1.11.2 python scripts/export_rfdetr.py`")

    ckpt = download(URL, Path(args.ckpt))
    if hashlib.md5(ckpt.read_bytes()).hexdigest() != MD5:
        ckpt.unlink()
        sys.exit("los pesos descargados no son los publicados (md5 distinto); se han borrado")
    model = RFDETRMedium(resolution=args.resolution, pretrain_weights=str(ckpt), device="cpu")
    with tempfile.TemporaryDirectory() as tmp:
        p = model.export(output_dir=tmp, opset_version=17, dynamic_batch=True, verbose=False,
                         shape=(args.resolution, args.resolution))
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p), out)
    net = model.model.model.eval()
    x = torch.randn(1, 3, args.resolution, args.resolution)
    with torch.no_grad():
        ref = net(x)
    sess = ort.InferenceSession(str(out), providers=["CPUExecutionProvider"])
    got = dict(zip([o.name for o in sess.get_outputs()], sess.run(None, {sess.get_inputs()[0].name: x.numpy()})))
    diff = max(float(np.abs(got["dets"] - ref["pred_boxes"].numpy()).max()),
               float(np.abs(got["labels"] - ref["pred_logits"].numpy()).max()))
    print(f"guardado {out}; diferencia máxima ONNX frente a PyTorch: {diff:.2e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
