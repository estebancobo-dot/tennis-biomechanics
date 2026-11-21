"""#307 (21-11): Sapiens2 pose (Meta; the user allowed its licence) to ONNX, for the fine pass's refiner
(tennisbio.pose.sapiens2): the 0.4B at 512x384 input, chosen by measure (docs/registro_decisiones.md: the body shakes
36 % less than the hybrid's, the feet are seen in every frame, 136 ms per crop on a T4).

The weights come from Hugging Face (facebook/sapiens2-pose-0.4b, transformers ≥ 5.23); only the network goes to ONNX
(pixels in, 308 heatmaps out): its crop and its heatmap decoding are numpy in tennisbio.pose.sapiens2, checked against
the transformers processor. The weights are never put in the repository (licence: Sapiens2 License).

    python scripts/export_sapiens2.py --salida models/sapiens2_pose_0.4b_512x384.onnx [--comprobar]
"""
from __future__ import annotations

import argparse
from pathlib import Path

MODEL = "facebook/sapiens2-pose-0.4b"
SIZE = (512, 384)                      # height, width (4:3, as the model was trained)


def export(out: Path, name: str = MODEL, size: tuple[int, int] = SIZE) -> Path:
    import torch
    from transformers import Sapiens2ForPoseEstimation

    # eager attention: the exporter does not take SDPA with grouped key/value heads (the same arithmetic)
    model = Sapiens2ForPoseEstimation.from_pretrained(name, attn_implementation="eager").eval()

    class Heatmaps(torch.nn.Module):
        def __init__(self, m):
            super().__init__()
            self.m = m

        def forward(self, pixel_values):
            return self.m(pixel_values=pixel_values).heatmaps

    import onnx

    x = torch.zeros(1, 3, *size)
    out.parent.mkdir(parents=True, exist_ok=True)
    work = out.parent / (out.stem + "_exportando")
    work.mkdir(exist_ok=True)
    with torch.no_grad():
        # torch.export (dynamo): the older exporter loses the channels before the head's instance norm. A fixed batch
        # of one crop: the fine pass poses one or two people per frame (tennisbio.pose.sapiens2 loops over them)
        torch.onnx.export(Heatmaps(model), (x,), str(work / "m.onnx"), input_names=["input"], output_names=["heatmaps"],
                          opset_version=18, dynamo=True)
    # one file (1.7 GB, under protobuf's 2 GB): the exporter leaves the weights apart; the volume and the model's
    # fingerprint (config.model_state) see one file
    m = onnx.load(str(work / "m.onnx"), load_external_data=True)
    tmp = out.with_name(out.name + ".part")
    onnx.save_model(m, str(tmp), save_as_external_data=False)
    tmp.replace(out)
    for f in work.iterdir():
        f.unlink()
    work.rmdir()
    return out


def check(onnx_path: Path, name: str = MODEL, size: tuple[int, int] = SIZE) -> float:
    """Largest difference between the ONNX heatmaps and PyTorch's on a random input (0 means the same network)."""
    import numpy as np
    import onnxruntime as ort
    import torch
    from transformers import Sapiens2ForPoseEstimation

    x = torch.randn(1, 3, *size)
    with torch.no_grad():
        ref = Sapiens2ForPoseEstimation.from_pretrained(name).eval()(pixel_values=x).heatmaps.numpy()
    got = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"]).run(None, {"input": x.numpy()})[0]
    return float(np.abs(got - ref).max())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", type=Path, required=True)
    ap.add_argument("--modelo", default=MODEL)
    ap.add_argument("--comprobar", action="store_true", help="compara la salida de ONNX con la de PyTorch")
    a = ap.parse_args(argv)
    p = export(a.salida, a.modelo)
    print(f"{p}: {p.stat().st_size / 1e9:.2f} GB")
    if a.comprobar:
        print(f"diferencia máxima con PyTorch: {check(p, a.modelo):.2e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
