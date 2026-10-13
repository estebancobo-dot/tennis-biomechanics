# Estado del arte de modelos, algoritmia y captura de datos (13-10-2026)

Revisión hecha antes de trabajar la velocidad: qué hay gratis y mejor (2025-2026) para Python en
Windows 11 con la iGPU Radeon 780M (sin CUDA) y nuestro caso (tele, jugadora de espaldas y desde arriba).
Fuentes: búsquedas web del 13-10 (artículos y repositorios citados abajo) y lectura del código.

## Hallazgos sobre lo que de verdad se ejecuta
- **Pose del cuerpo: YOLO11m-pose a 960 px sobre el fotograma entero** (`pose/backend.py`, `pose/yolo.py`),
  17 puntos COCO, **sin talones ni puntas de los pies**. RTMPose-x Halpe26 (`pose/estimator.py`, rtmlib) está
  en el código y en `config/default.yaml` pero las etapas no lo usan. La pose «players» del partido entero
  también es YOLO11m-pose a 960 (no el YOLOX-tiny de la configuración).
- **El 8745HS no tiene NPU** (es el 8845HS con la NPU desactivada): la vía Ryzen AI / VitisAI no aplica.
- **DirectML** sigue funcionando pero está en mantenimiento; Microsoft empuja Windows ML (elige DirectML o
  MIGraphX de AMD). MIGraphX en iGPU 780M no está confirmado: solo como prueba.
- Tiempos del PC (35 min de vídeo): fine 103 min, players 48, candidates 31, identity 30, score 19,
  court 17, scenes 2,4. identity y candidates ya están corregidos (`7201941`, leían `players.npz` en cada
  fotograma). Total ≈ 4,2 h → ≈ 25 h por partido.

## Por componente: mantener o cambiar
| Componente | Hoy | Mejor gratis 2025-26 | Decisión |
|---|---|---|---|
| Pose 2D | YOLO11m-pose 960, fotograma entero | RTMPose-x / RTMW-x (MMPose, Apache-2.0) sobre el recorte de la jugadora; con pies (Halpe26/wholebody). Sapiens2 (Meta, 2026) mejor pero inviable en iGPU. YOLO26-pose sin pies | **Cambiar** a RTMPose-x Halpe26 sobre recorte, en lotes, FP16 (más rápido y con pies); comparar A/B con lo actual |
| Detección de personas | YOLO11m-pose 960 | YOLO26 (sin NMS), RF-DETR/DEIMv2 (los DETR van mal en DirectML) | 640 px sobre la zona de pista, lotes, FP16; YOLO26 opcional |
| 3D del tronco | RTMW3D-x | MotionAGFormer/TCPFormer (pequeños, ONNX), SAM 3D Body (muy pesado), GVHMR/WHAM (CUDA) | Mantener; prueba A/B con MotionAGFormer |
| Bola | TrackNetV3 (RacketVision) | WASB (MIT, pesos de tenis), TrackNetV4/V5 sin pesos, TOTNet (pesado) | Mantener; probar WASB en los clips de RacketVision |
| Raqueta | RacketVision RTMPose-m 5 puntos | Nada abierto mejor | Mantener |
| Golpe (instante) | giro de la bola + muñeca + audio | E2E-Spot / F3ED entrenados en F3Set (tenis de tele) | Mantener; luego un clasificador aprendido con F3Set |
| Bote | heurística | GBDT/CatBoost sobre la trayectoria (≈ 0,95 precisión) | Cambiar (barato) |
| Pista | líneas + homografía propias (82 de 162 tramos) | TennisCourtDetector (14 puntos, ≈ 2 px) + refinado por líneas | Cambiar a puntos + nuestro refinado; reutilizar homografías |
| Cortes de plano | detector propio de cortes y fundidos | TransNetV2 (ONNX, muy barato) | Añadir junto al propio |
| Marcador | rapidocr-onnxruntime 1.x | rapidocr 3.x con PP-OCRv5 | Cambiar; OCR solo cuando cambia el recorte |
| Audio | onsets de librosa | detectores entrenados (TennisExpert 2026) | Mantener como señal secundaria |
| Ejecución | ORT DirectML, lote 1, FP32 | lotes 4-8, FP16, sesiones persistentes, grafo optimizado guardado | Cambiar |
| Decodificación | un ffmpeg por etapa y por fotograma suelto | una sola decodificación d3d11va con escalado en ffmpeg y varios consumidores | Cambiar |

## Plan de velocidad (sin bajar precisión; estimado para 35 min de vídeo)
0. Medir identity/candidates tras `7201941` (61 → < 1 min).
1. Pasada fina en cascada: bola + pose barata primero; pose a fps completos, raqueta y 3D solo en golpes
   probables; pose sobre el recorte de la jugadora (103 → 20-30 min).
2. Sesión persistente de raqueta, una decodificación por ventana, modelos en lotes (×2-3 más en fine).
3. Pista: reutilizar homografías, media resolución, vectorizar, no repetir fallos (17 → 1-2 min).
4. Marcador: OCR solo cuando cambia el recorte (19 → 1-2 min).
5. Jugadores: 640 px en la zona de pista, lotes, FP16 (48 → 8-12 min).
6. Una sola decodificación para scenes/court/score/players.
7. FP16 en todos los modelos de DirectML, comprobando puntos frente a FP32.
8. (Opcional) Windows ML con MIGraphX frente a DirectML.
Objetivo: ≈ 35-50 min por 35 min de vídeo → 3,5-5 h por partido; < 3 h con FP16.
Cada cambio se valida con los clips anotados (RacketVision, F3Set) y el ciclo automático (sin regresiones).

## Fuentes
RTMO https://arxiv.org/abs/2312.07526 · CIGPose https://arxiv.org/pdf/2603.09418 · YOLO26
https://docs.ultralytics.com/models/yolo26/ · Sapiens2 https://github.com/facebookresearch/sapiens2 ·
RF-DETR https://arxiv.org/pdf/2511.09554 · DEIMv2 https://arxiv.org/abs/2509.20787 · TCPFormer
https://arxiv.org/html/2501.01770v1 · SAM 3D Body https://arxiv.org/abs/2602.15989 · Windows ML EPs
https://learn.microsoft.com/en-us/windows/ai/new-windows-ml/supported-execution-providers · 8745HS sin NPU
https://www.club386.com/amd-may-be-working-on-an-npu-less-ryzen-7-8745hs · TrackNetV4
https://arxiv.org/abs/2409.14543 · WASB https://github.com/nttcom/WASB-SBDT · TOTNet
https://arxiv.org/abs/2508.09650 · BlurBall https://cogsys-tuebingen.github.io/blurball · RacketVision
https://github.com/OrcustD/RacketVision · F3Set https://github.com/F3Set/F3Set · Event spotting
https://arxiv.org/abs/2503.00147 · TennisCourtDetector https://github.com/yastrebksv/TennisCourtDetector ·
PnLCalib https://arxiv.org/abs/2404.08401 · RapidOCR https://pypi.org/project/rapidocr/ · TennisExpert
https://github.com/LZYAndy/TennisExpert · ORT DirectML
https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html

## Resultado de la prueba de modelos en el PC (13-10, 22:14; 6 clips de RacketVision, 13 golpes)
| Variante | ms/fotograma | F1 | Temblor | Pies |
|---|---|---|---|---|
| YOLO11m 960 (antes) | 280 | 0,64 | 0,73 | — |
| YOLO11m 960 FP16 (**ahora**) | 128 | 0,64 | 0,73 | — |
| YOLO11m 640 | 152 | 0,71 | 0,77 | — |
| RTMPose-x (+ YOLOX-m) | 720 | 0,64 | 0,28 | 89 % |
| RTMPose-x FP16 | 1807 | 0,64 | 0,28 | 89 % |
| RTMPose-m | 327 | 0,56 | 0,30 | 96 % |
| Híbrido YOLO FP16 + RTMPose-x | 305 | 0,67 | 0,48 | 99,7 % |
| Híbrido YOLO FP16 + RTMPose-x FP16 | 268 | 0,67 | 0,48 | 99,7 % |
| Bola TrackNetV3 / FP16 | 168 / 173 | 86 % / 86 % a ≤10 px | | |

Decisión: pasada barata (partido entero) con YOLO11m 960 FP16 (ya activo). Pasada fina: el híbrido (pies en
el 99,7 %, temblor −35 %, mismos golpes, 2× el coste de YOLO FP16 solo en las ventanas), después de medir la
prueba de velocidad con lo actual. RTMPose en FP16 va más lento en DirectML: no se usa. La bola en FP16 no
gana nada: sigue en FP32. Con 13 golpes, diferencias de F1 de ±0,07 son ruido.
