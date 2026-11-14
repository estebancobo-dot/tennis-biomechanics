# Estado del arte por capas, para la nube (#287, #289; 14-11, primera vuelta)

Estado: **primera vuelta (14-11 16:00), 11 búsquedas.** Cada capa da lo hallado (con fuentes), los candidatos, la
prueba de concepto que decide y lo que falta por buscar. **No es exhaustiva:** cada «falta» es trabajo pendiente y se
completa antes de decidir esa capa. Nada se adopta sin su prueba de concepto medida (#288).

**Leer junto con `docs/analisis_nube.md` §6 (13-11).** Trae lo que esta vuelta no encontró:
- **Sapiens2** (Meta, ICLR 2026, 0,4-5 mil millones de parámetros). Esta vuelta dijo «no confirmado»: sí existe.
- **CIGPose** (CVPR 2026, 67,0 AP en COCO-WholeBody).
- **SAM 3D Body** (Meta, 19-11-2025) y **SAM-Body4D** (diciembre de 2025).
- **TOTNet** (bola con oclusión).
- **CalTennis**, multivista, para validar 3D y pies.

## 1. Dónde se calcula (infraestructura)

- **Gratis hoy:**
  - **Kaggle:** ~30 h de GPU por semana, que se renuevan el sábado a las 00:00 UTC (medido: 21-11). Dos T4 por
    sesión, sesiones de hasta 12 h y **como mucho 2 sesiones de GPU a la vez** (mensaje de Kaggle, 14-11).
  - **Modal:** 30 $ al mes.
  - **Lightning AI:** ~15 créditos al mes (~22 h de T4; las fuentes no coinciden); el estudio gratuito se reinicia cada
    4 h.
  - **Colab gratis:** poco previsible y pensado para uso interactivo.
  - **Hugging Face ZeroGPU:** solo para demos, minutos al día.
  - **Paperspace:** sesiones de 6 h, sujetas a disponibilidad.
- **Abstracción multinube:** **SkyPilot** lanza el mismo trabajo en más de 20 nubes, Kubernetes y Slurm, eligiendo la
  más barata con capacidad y con recuperación automática. No cubre Kaggle ni Modal, pero sí RunPod, Lambda y las nubes
  grandes, para cuando haya presupuesto. Ray y Dask sirven para repartir dentro de una máquina o un clúster.
- **Para este proyecto:** un puerto «Cálculo» propio con adaptadores (PC, Modal, Kaggle, nube de Claude solo CPU) y,
  más adelante, uno de SkyPilot para el resto de nubes.
- **Prueba de concepto:** la misma prueba de 10 min en cada adaptador da los mismos golpes (contrato y equivalencia).
- **Falta:** las condiciones exactas de Lightning AI por API (¿se puede lanzar sin interfaz?) y de SageMaker Studio Lab.

## 2. Orquestación de trabajos

- **Hallado:**
  - Temporal: ejecución duradera.
  - Prefect: Python nativo.
  - Dagster: linaje de datos; Prefect anunció su compra en julio de 2026.
  - Flyte: GPU por tarea, pero sobre Kubernetes.
- **Para este proyecto:** las etapas ya son un grafo con cachés por huella (como Dagster o Hamilton) y la cola de la
  nube es el planificador. Una herramienta externa añade servidor y coste sin resolver nada que hoy falte. Se queda la
  propia, con estado duradero en `nube-logs`.
- **Prueba de concepto:** no hace falta mientras no aparezca una necesidad (reintentos o dependencias que la cola no
  cubra).
- **Falta:** Hamilton (grafos de funciones en Python, sin servidor), por si simplifica `stages.py`.

## 3. Vídeo en la GPU

- **Hallado:**
  - TorchCodec en CUDA: lo más simple; los fotogramas quedan en la tarjeta como tensores.
  - PyNvVideoCodec: control fino de contexto y flujos.
  - DALI: sustituye al cargador de datos; con DALI Proxy, solo una parte.
  - DeepStream y Savant: tuberías completas sobre GStreamer. Un caso real se quedó en el 52 % de la GPU por el
    Python de cada fotograma.
  - Patrón común: decodificar, agrupar e inferir en la GPU, sin pasar por la CPU.
- **Para este proyecto:** un puerto «Vídeo» con adaptadores ffmpeg-CPU (hoy), NVDEC (TorchCodec o PyNvVideoCodec) y
  d3d11va (PC).
- **Prueba de concepto:** recortar las ventanas de la prueba de 10 min con cada uno: mismos fotogramas (diferencia de
  píxel mínima) y tiempo.
- **Falta:** el desentrelazado en la GPU (yadif_cuda o bwdif) y los .ts dañados (Osaka) con NVDEC.

## 4. Ejecución de modelos

- **Hallado:**
  - TensorRT FP16 frente a ONNX FP16: 1,85-2,55 × en 19 GPU (Ultralytics, lote 1); sin datos de la T4.
  - El proveedor TensorRT de ONNX Runtime trae FP16 desactivado por defecto.
  - Los motores van ligados al tipo de tarjeta.
- **Candidatos:** ONNX Runtime CUDA (hoy), ONNX Runtime TensorRT, TensorRT directo, torch.compile; Triton solo si se
  sirvieran modelos.
- **Prueba de concepto:** la raqueta (el 40 % del tiempo) con cada uno, en lotes de 1, 8, 32 y 64; igualdad de salidas
  (tolerancia de FP16) y fotogramas por segundo en la T4.
- **Falta:** el coste de construir motores en cada sesión de Kaggle, que no guarda nada (¿guardarlos en Modal?).

## 5. Modelos por tarea

| Tarea | Actual | Hallado 2025-2026 | Prueba de concepto (datos) |
|---|---|---|---|
| Golpes (instante y tipo) | Detector propio con F3Set | F3ED (ICLR 2025, método del propio F3Set); con pocos ejemplos, UMEG-Net y la destilación esqueleto → píxeles (abril de 2026); E2E-Spot y T-DEED sin resultados en F3Set | F3Set: precisión, recall y error de instante |
| Bola | TrackNetV3 | TrackNetV4 (una reproducción no confirmó su mejora); WASB (HRNet); BlurBall (bola y desenfoque, mesa); TOTNet (oclusión) | RacketVision (bola anotada) y golpes F3Set por la bola |
| Pose 2D | YOLO11-pose + RTMPose | YOLO26-pose; RF-DETR Keypoint (dice superar a YOLO26x; dato del vendedor); ViTPose++; Sapiens (0.3B: 79,6 AP; 2B: 82,2); RTMO; BBoxMaskPose v2; ER-Pose | Sin pose anotada de tenis: medir por su efecto en golpes y tipo (F3Set) y por la estabilidad entre fotogramas; buscar un conjunto de pose deportiva |
| Cuerpo 3D | RTMW3D / MotionAGFormer (rotaciones) | GVHMR (mundo con gravedad, 2024), WHAM, TRAM, OnlineHMR (2026), PVA-Net (2026, dinámica) | Rotaciones de cadera y hombros: consistencia entre golpes casi iguales (ruido de medida) |
| Personas (seguimiento) | Propio (lado de pista y ropa) | SAM 3 + Deep-EIoU: 86,8 HOTA en SportsMOT (junio de 2026); BoT-SORT es la base común | Cambios de lado e identidad en los 6 partidos |
| Cortes de plano | TransNetV2 | AutoShot (+1-4 F1 en sus pruebas; Cosmos los ve parejos); OmniShotCut (2026, incluye deporte) | Cortes de las pruebas de 10 min (anotar una muestra) |
| Marcador | RapidOCR (PP-OCR) | PP-OCRv5 tras un detector de la zona; un modelo de visión y lenguaje (Qwen2.5-VL, Florence-2) solo para casos difíciles | Lecturas frente al marcador anotado de una muestra |
| Raqueta | RTMPose-m de RacketVision | Sin novedades encontradas | RacketVision (raqueta anotada) |

**Datos de tenis:** RacketVision (1672 clips con bola y raqueta); F3Set (11 584 clips, 114 partidos); THETIS
(golpes); un conjunto 2026 del US Open 2024 con pose 3D y velocidad de saque (CVBW 2026). **Falta:** si este último es
público y sirve para validar la pose.

## 6. Datos, cachés y almacenamiento

- **Hoy:** claves por huella de código, entradas y modelos, en Parquet y NPY por partido.
- **Para este proyecto:** fsspec, para que el mismo código lea y escriba en el disco del PC, el volumen de Modal o un
  almacenamiento de objetos sin cambios.
- **Falta:** si conviene Arrow o Zarr para las series por fotograma.

## 7. Configuración y extensiones

- **Hallado:** puertos y adaptadores (Cockburn): rinde cuando se cambia de infraestructura y hay varias entradas
  (línea de órdenes, trabajador, web). Plugins con los puntos de entrada de Python o pluggy, y un gestor que separa
  descubrir, cargar y validar, y registrar.
- **Para este proyecto:** un registro por puerto con descubrimiento de capacidades y la configuración validada con
  pydantic.
- **Falta:** patrones de negociación de capacidades en tuberías de aprendizaje automático (no encontrados).

## 8. Observabilidad

Métricas por etapa (CPU, cada GPU, memoria, decodificador) en Modal y Kaggle, en el mismo formato. Visibles en
`nube-logs`. **Falta:** decidir si basta el JSON propio o merece OpenTelemetry (probablemente no, a esta escala).

## 9. Pruebas

Contrato por adaptador, equivalencia entre infraestructuras (el mismo clip) y regresión con clips de referencia. La
calidad, con datos anotados (F3Set, RacketVision).

## Fuentes

[Kaggle y otras GPU gratis](https://aimultiple.com/free-cloud-gpu) · [SkyPilot](https://sky.cs.berkeley.edu/project/skypilot/) ·
[orquestadores 2026](https://www.gmicloud.ai/en/blog/temporal-vs-prefect-vs-dagster) · [Flyte y otros](https://www.zenml.io/blog/dagster-alternatives) ·
[TorchCodec CUDA](https://docs.pytorch.org/torchcodec/0.4/generated_examples/basic_cuda_example.html) · [PyNvVideoCodec](https://docs.nvidia.com/video-technologies/pynvvideocodec/read-me/running-samples.html) ·
[DALI](https://developer.nvidia.com/blog/unlock-efficient-data-processing-with-the-latest-from-nvidia-dali) · [tuberías de vídeo, caso real](https://arxiv.org/pdf/2512.07009) ·
[DeepStream, uso de GPU](https://forums.developer.nvidia.com/t/gpu-utilization-bottleneck-single-process-with-8-streams-vs-multi-process-with-1-stream-each-deepstream-7-1-pyservicemaker/372258) ·
[ONNX frente a TensorRT](https://www.ultralytics.com/blog/onnx-vs-tensorrt) · [TensorRT en ONNX Runtime](https://github.com/microsoft/onnxruntime/blob/717d1da14874cd8f6fd7ede97f4369510e2452ca/docs/execution_providers/TensorRT-ExecutionProvider.md) ·
[F3Set con pocos ejemplos](https://arxiv.org/pdf/2604.22839) · [UMEG-Net](https://arxiv.org/pdf/2511.14186) · [TrackNetV4](https://arxiv.org/pdf/2409.14543) · [BlurBall](https://arxiv.org/pdf/2509.18387) ·
[RTMO](https://arxiv.org/pdf/2312.07526) · [RF-DETR Keypoint](https://roboflow.com/blog/real-time-keypoint-detection-with-rf-detr) · [COCO keypoints](https://hyper.ai/en/sota/tasks/keypoint-detection/benchmark/keypoint-detection-on-coco) ·
[GVHMR](https://arxiv.org/html/2409.06662v1) · [WHAM](https://ar5iv.labs.arxiv.org/html/2312.07531) · [PVA-Net](https://www.alphaxiv.org/abs/2605.26879) ·
[SAM 3 + Deep-EIoU](https://arxiv.org/html/2606.13033) · [AutoShot](https://arxiv.org/pdf/2304.06116) · [Cosmos (cortes)](https://arxiv.org/pdf/2501.03575) · [OmniShotCut](https://www.alphaxiv.org/overview/2604.24762) ·
[OCR de marcadores](https://arxiv.org/pdf/2411.00862) · [OCR: patrón detector + lector](https://roboflow.com/blog/best-ocr-models-text-recognition) ·
[RacketVision](https://arxiv.org/html/2511.17045v3) · [tenis 2026: biomecánica multitarea](https://arxiv.org/html/2606.15992) ·
[puertos y adaptadores](https://archman.dev/docs/architectural-styles/hexagonal-ports-and-adapters) · [plugins en Python](https://oneuptime.com/blog/post/2026-01-30-python-plugin-systems/markdown)
