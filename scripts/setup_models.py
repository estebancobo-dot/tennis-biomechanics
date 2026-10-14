"""Deja listos todos los modelos en models/ (un solo comando, se puede repetir).

    uv sync --extra yolo --extra ocr
    uv run python scripts/setup_models.py

- balltrack.onnx    bola (RacketVision TrackNetV3, MIT) — exportado desde los pesos oficiales
- racketpose.onnx   5 puntos de la raqueta (RacketVision RTMPose-m, MIT)
- transnetv2.onnx   cortes de plano (TransNetV2, MIT) — exportado desde los pesos oficiales
- rtmw3d-x.onnx     cuerpo y manos en 3D (RTMW3D) para la orientación de las cuerdas
- yolo11m-pose.pt / yolo11m-seg.pt  personas y silueta de la raqueta (Ultralytics los descarga solos)
- yolo11m-pose_<tamaño>.onnx  la pose exportada a ONNX para la iGPU (DirectML), a cada tamaño usado
"""
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
sys.path.insert(0, str(ROOT / "src"))


POSE_SIZES = (640, 960, 1280, 1920)


def run(script: str, *args: str):
    subprocess.run([sys.executable, str(ROOT / "scripts" / script), *args], check=True, cwd=ROOT)


def main():
    MODELS.mkdir(exist_ok=True)
    if not (MODELS / "balltrack.onnx").exists():
        run("export_balltrack.py", "--ckpt", str(MODELS / "balltrack_best.pth"), "--out", str(MODELS / "balltrack.onnx"))
    if not (MODELS / "racketpose.onnx").exists():
        run("export_racketpose.py", "--ckpt", str(MODELS / "racketpose.pth"), "--out", str(MODELS / "racketpose.onnx"))
    if not (MODELS / "transnetv2.onnx").exists():
        try:
            run("export_transnetv2.py", "--cache", str(MODELS), "--out", str(MODELS / "transnetv2.onnx"))
        except subprocess.CalledProcessError:      # the cuts fall back to the colour histograms
            print("AVISO: no se pudo crear transnetv2.onnx; los cortes de plano se detectan sin él")
    w3d = MODELS / "rtmw3d-x.onnx"
    if not w3d.exists():
        from tennisbio.pose.wholebody3d import RTMW3D_URL
        print(f"descargando {RTMW3D_URL}")
        urllib.request.urlretrieve(RTMW3D_URL, w3d)
    try:
        from ultralytics import YOLO
        for m in ("yolo11m-pose.pt", "yolo11m-seg.pt"):
            YOLO(str(MODELS / m))          # downloaded into models/, where the pipeline looks
        from tennisbio.pose.yolo_onnx import export_onnx
        for size in POSE_SIZES:                 # cheap pass 960, fine 1280, far crop 640/960, far search 1920
            export_onnx("yolo11m-pose", size)
    except ImportError:
        print("falta ultralytics: uv sync --extra yolo")
    try:
        from rapidocr_onnxruntime import RapidOCR
        RapidOCR()
    except ImportError:
        print("falta el OCR del marcador: uv sync --extra ocr")
    for f in ("balltrack.onnx", "racketpose.onnx", "transnetv2.onnx", "rtmw3d-x.onnx", *[f"yolo11m-pose_{z}.onnx" for z in POSE_SIZES]):
        p = MODELS / f
        print(f"{f:18} {'OK ' + str(round(p.stat().st_size / 1e6)) + ' MB' if p.exists() else 'FALTA'}")


if __name__ == "__main__":
    main()
