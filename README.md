# tennis-biomech

Análisis biomecánico cinemático de golpes de tenis a partir de retransmisiones de TV.
Contexto completo y decisiones de diseño en [CLAUDE.md](CLAUDE.md).

## Instalación (Windows 11)

```powershell
winget install --id Gyan.FFmpeg          # ffmpeg + ffprobe en el PATH
winget install --id astral-sh.uv
cd C:\tenis\tennis-biomech
uv python install 3.11
uv sync                                   # crea .venv con onnxruntime-directml
uv sync --extra openvino --extra yolo --extra viz   # OpenVINO en CPU, YOLO (pose/raqueta) y gráficos
copy config\local.example.yaml config\local.yaml
```

## Fase 0: comprobar el entorno y medir la velocidad

```powershell
uv run python scripts\check_env.py "C:\tenis\videos\partido1.mp4"
uv run python scripts\benchmark.py "C:\tenis\videos\partido1.mp4" --start 1800 --devices dml cpu openvino
```

También mide YOLO11-pose (640 y 960) y YOLO11-seg exportados a ONNX (`--yolo` para elegir;
la primera vez exporta a `models/`). `--start` es un segundo del vídeo con la cámara principal en juego. La primera vez se
descargan los modelos (~400 MB) a `%USERPROFILE%\.cache\rtmlib`. El benchmark guarda
`results.json` y fotogramas con el esqueleto en `C:\tenis\output\benchmark\`.

## Analizar un clip corto

```powershell
uv run python scripts\analyze_clip.py "C:\tenis\videos\clip.mp4" --out C:\tenis\output\clip1
```
Pose en todos los fotogramas (solo para clips), 8 momentos por golpe, raqueta y curvas.

## Tests

```powershell
uv sync --extra dev
uv run pytest
```
