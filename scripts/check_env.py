"""Fase 0: comprueba el entorno y hace ffprobe de un vídeo.

Uso (Windows):  python scripts\\check_env.py "C:\\tenis\\videos\\partido1.mp4"
Solo usa la biblioteca estándar, así que funciona antes de instalar nada.
"""
import importlib
import json
import os
import platform
import shutil
import subprocess
import sys

PACKAGES = ["numpy", "pandas", "cv2", "librosa", "onnxruntime", "ultralytics", "rapidocr_onnxruntime"]
MODELS = ["balltrack.onnx", "racketpose.onnx", "rtmw3d-x.onnx", "yolo11m-pose_960.onnx", "yolo11m-pose_1280.onnx"]


def check_tools():
    print(f"Python   {sys.version.split()[0]}  ({platform.platform()})")
    print(f"CPUs     {os.cpu_count()}")
    for tool in ["ffmpeg", "ffprobe", "git", "uv"]:
        print(f"{tool:8} {shutil.which(tool) or 'NO ENCONTRADO'}")
    for name in PACKAGES:
        try:
            mod = importlib.import_module(name)
            print(f"{name:12} {getattr(mod, '__version__', '?')}")
        except ImportError:
            print(f"{name:12} no instalado")
    try:
        import onnxruntime as ort
        print("ORT providers:", ort.get_available_providers())
    except ImportError:
        pass
    models = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
    for m in MODELS:
        p = os.path.join(models, m)
        print(f"{m:18} {'OK' if os.path.exists(p) else 'falta (uv run python scripts/setup_models.py)'}")


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", path],
        capture_output=True, text=True, check=True, encoding="utf-8", errors="replace",
    ).stdout
    info = json.loads(out)
    fmt = info["format"]
    print(f"\n{path}")
    print(f"  contenedor {fmt.get('format_name')}  duración {float(fmt['duration']) / 60:.1f} min  "
          f"tamaño {int(fmt['size']) / 1e9:.2f} GB  bitrate {int(fmt.get('bit_rate', 0)) / 1e6:.1f} Mb/s")
    for s in info["streams"]:
        if s["codec_type"] == "video":
            print(f"  vídeo  {s['codec_name']} {s['width']}x{s['height']}  "
                  f"r_frame_rate={s['r_frame_rate']} avg_frame_rate={s['avg_frame_rate']}  "
                  f"field_order={s.get('field_order', '?')}  pix_fmt={s.get('pix_fmt')}")
        elif s["codec_type"] == "audio":
            print(f"  audio  {s['codec_name']} {s.get('sample_rate')} Hz  {s.get('channels')} canales")


if __name__ == "__main__":
    check_tools()
    for p in sys.argv[1:]:
        probe(p)
