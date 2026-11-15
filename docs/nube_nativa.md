# Nube nativa: rehacer lo que se decidió para el PC (#287, 14-11)

**El fallo (del usuario, 14-11):** al pasar a la nube solo cambió dónde corren los modelos. Todo lo demás sigue decidido
para el PC: un único Beelink con una iGPU AMD sin CUDA, 16 hilos y Windows. Ejemplos:

- **ONNX Runtime pensado para DirectML.** En la nube se «traduce» a CUDA con un parche al arrancar (`nube_gpu`), y la
  configuración sigue diciendo `device: dml`.
- **El vídeo se decodifica en la CPU con ffmpeg por tubería.** Las T4 tienen decodificador propio (NVDEC) y no se usa.
- **«La bola en paralelo en la CPU».** Ayudaba con 16 hilos libres; en Kaggle ahogaba sus 4 núcleos.
- **Una sola tarjeta.** Kaggle da dos T4 y una queda parada.
- **Inferencia de una en una o en lotes pequeños y en FP32/FP16 «de DirectML».** Sin TensorRT, que es lo que
  aprovecha una GPU NVIDIA.
- **Los modelos elegidos en octubre** por funcionar en la iGPU (RTMPose/YOLO, TrackNetV3, RTMPose-m de raqueta,
  TransNetV2, RapidOCR, RTMW3D), sin compararlos de nuevo con lo mejor de hoy para una GPU NVIDIA.

**Regla (la del proyecto):** calidad antes que velocidad (#248). Un cambio entra solo si da lo mismo o mejor con datos
anotados y, además, es más rápido o más barato; si no, no entra. Todo medido, en la nube, a 0 €.

**Ya analizado el 13-11 (`docs/analisis_nube.md`) e integrado aquí el 14-11 (T17).** No se había reutilizado hoy:
- **§2:** requisitos en la nube; el 9 pasa a «viable en el PC **y** en la nube».
- **§6:** modelos con GPU de verdad: Sapiens2 (ICLR 2026), CIGPose (CVPR 2026), SAM 3D Body y SAM-Body4D, GVHMR,
  PromptHMR-Vid, SAMURAI y SAM 3, TrackNetV4, TOTNet, F3ED, T-DEED y UMEG-Net; el conjunto multivista CalTennis para
  validar 3D y pies; reentrenar el detector con la jugadora lejana (R27).
- **§7:** qué cambia en el código.
- **§8:** fases N0-N6 con su aceptación calculada; N2 = repartir la pasada fina por ventanas.
- **§9:** riesgos: derechos, privacidad, licencias, equivalencia de decimales.

El orden de §6 por lo que pesa en la Base sigue valiendo: detector con la lejana, seguimiento por máscara, 3D, bola,
pose grande.

## Cómo se decide (#288) y arquitectura híbrida (#289)

**Decidir con pruebas de concepto, no con aprobaciones.** Cada opción se prueba en la nube con los mismos clips de
referencia (las pruebas de 10 min de Gauff y de la final) y con datos anotados (F3Set, RacketVision). Gana la que da
igual o mejor calidad con menos tiempo o coste. El resultado queda en la tabla de este documento.

**Una sola aplicación, N infraestructuras (puertos y adaptadores).** El código del análisis es común. Cada
infraestructura (el PC, la nube de Claude, Modal, Kaggle, otras) es un adaptador que se elige por configuración y por
descubrimiento de sus capacidades:

| Puerto | Qué decide | Adaptadores |
|---|---|---|
| Cálculo | Dónde corre un trabajo: lanzar, estado, registros, cancelar; capacidades (GPU y cuántas, núcleos, memoria, decodificador, cuota y coste) | PC (cola local), Modal, Kaggle, la nube de Claude (solo CPU, para pruebas y código), otros (RunPod, Lightning…) |
| Almacenamiento | Dónde están vídeos, modelos, cachés y resultados | Disco del PC, volumen de Modal, sesión de Kaggle, almacenamiento de objetos (fsspec) |
| Vídeo | Cómo se decodifica | ffmpeg en la CPU, NVDEC en la GPU (TorchCodec o PyNvVideoCodec), d3d11va en el PC |
| Inferencia | Con qué se ejecuta cada modelo | ONNX Runtime (DirectML en el PC, CUDA, TensorRT, OpenVINO, CPU), TensorRT directo |
| Modelos | Qué modelo hace cada tarea | Un registro por tarea (golpes, bola, pose, raqueta, cortes, marcador, 3D) con sus variantes medidas |
| Cola | Qué se lanza, dónde y cuándo | `cloud/cola.py`, que pasa a elegir por capacidades y no por nombres fijos |

El **descubrimiento** mira al arrancar qué hay: vendedor y número de GPU, CUDA y TensorRT, NVDEC, núcleos, memoria y
disco. Con eso elige el adaptador de vídeo y de inferencia y los tamaños de lote. Hoy, en cambio, está fijado
`device: dml` y se parchea. Cada adaptador pasa las mismas **pruebas de contrato**, y una **prueba de equivalencia**
(el mismo clip en cada infraestructura) garantiza que todas dan lo mismo.

**Revisión del estado del arte, por capas (pendiente: la del 14-11 fue superficial, 5 búsquedas).** Capas:

1. Abstracción de cálculo multinube (SkyPilot, Ray, Dask) y sus límites con las capas gratuitas.
2. Orquestación de flujos (Prefect, Dagster, Temporal, Flyte).
3. Vídeo en la GPU (NVDEC, TorchCodec, PyNvVideoCodec, DALI).
4. Ejecución de modelos (TensorRT, ONNX Runtime, torch.compile, Triton).
5. Modelos por tarea (detección de golpes, bola, pose 2D, cuerpo y malla 3D desde una cámara, raqueta, cortes,
   marcador, seguimiento de personas).
6. Datos y cachés (Arrow/Parquet, claves por contenido, fsspec).
7. Configuración y extensiones (pydantic-settings, registros de plugins).
8. Observabilidad (métricas por etapa, OpenTelemetry).
9. Pruebas (contrato, equivalencia, regresión con clips de referencia).

Cada capa queda con sus candidatos, fuentes y la prueba de concepto que lo decide.

## Dónde va el tiempo hoy (medido, 10 min de Gauff, la misma T4)

| Parte de la pasada fina | Modal (s) | Kaggle (s) | Nota |
|---|---|---|---|
| Raqueta (RTMPose-m de RacketVision) | 920 | 3986 | Lo que más pesa en las dos |
| Pose (YOLO + RTMPose híbrido) | 745 | 454 | |
| Bola (TrackNetV3) | 241 | 196 (+2808 en la CPU) | |
| Pose de la lejana | 140 | 110 | |
| Cuerdas y 3D (RTMW3D) | 130 | 132 | |
| Recorte de ventanas (decodificar en la CPU) | 55 | 170 | 3 × más lento con 4 núcleos |

Pasada barata del mismo clip: cortes 29 s / 122 s; detector de golpes 193 s / 212 s (casi todo la bola); marcador
31 s / 101 s; jugadoras 77 s / 78 s.

## Fase A: medir con detalle (sin cambiar nada)

1. **Perfil por función en Kaggle y en Modal:** CPU, cada GPU, memoria, decodificación y espera, minuto a minuto
   (`recursos.jsonl` también en Kaggle).
2. **Comprobación de auditoría «Uso de la nube por etapa»** (criterio nuevo de B1) y **«Cola de la nube»** (criterio
   nuevo de B7 y B8).

## Fase B: infraestructura nativa de GPU (los mismos modelos y los mismos resultados)

Cada punto se acepta solo si los golpes y las medidas de la prueba de 10 min salen iguales (o con diferencias del
orden de los decimales del modelo) y el tiempo baja.

1. **Decodificar en la GPU (NVDEC)** directamente a tensores en la tarjeta: TorchCodec (lo más simple con PyTorch) o
   PyNvVideoCodec (control fino). Hoy: ffmpeg en la CPU por tubería.
2. **TensorRT en FP16**, con el proveedor TensorRT de ONNX Runtime (ya disponible en Kaggle) o TensorRT directo. Los
   motores se construyen una vez por tipo de tarjeta y se guardan. Las medidas públicas dan 1,9-2,6 × frente a ONNX
   FP16, pero no hay datos de la T4: hay que medirlo.
3. **Inferencia por lotes de verdad:** raqueta, pose y bola por lotes de fotogramas en la GPU, no fotograma a
   fotograma.
4. **Las dos T4 de Kaggle:** pose en una, raqueta y bola en la otra (o dos ventanas a la vez).
5. **Fuera lo del PC:** `device: cuda` de verdad (sin el parche `dml`→CUDA), la bola en la CPU, los dos procesos de la
   iGPU, el desentrelazado en la CPU donde la GPU lo haga.

## Fase C: modelos, frente al estado del arte de hoy

Cada candidato se mide frente al actual con datos anotados: **F3Set** para golpes y tipo (ya está en Modal) y
**RacketVision** para bola y raqueta (a subir si no está). Se mide en precisión, recall y error de instante, y en
velocidad en la T4. Se cambia solo si gana.

| Pieza | Actual | Candidatos a medir (2025-2026) |
|---|---|---|
| Detector de golpes | El propio, entrenado con F3Set | F3ED (el método del artículo de F3Set, ICLR 2025), E2E-Spot, T-DEED; con pocos ejemplos, UMEG-Net y la destilación esqueleto → píxeles (2026) |
| Bola | TrackNetV3 (RacketVision) | TrackNetV4 (mapas de atención al movimiento; una reproducción independiente no la vio mejor), WASB (HRNet), la idea de BlurBall (bola y desenfoque juntos) |
| Pose | YOLO11-pose + RTMPose (híbrido) | RTMO (una sola pasada, rápido con varias personas), ViTPose++, Sapiens (el más preciso; pesado), RTMW (cuerpo entero) |
| Raqueta | RTMPose-m de RacketVision | El mismo con más capacidad (RTMPose-l/x afinado) y su versión TensorRT |
| Cortes de plano | TransNetV2 | AutoShot |
| Marcador | RapidOCR (PP-OCR) | PP-OCRv5; un modelo de visión y lenguaje pequeño para leer el marcador entero |
| 3D (rotaciones) | RTMW3D / MotionAGFormer | Los de 2025-2026 que mejoren las rotaciones de cadera y hombros |

Cada medida es un trabajo de la cola en Kaggle, gratis (cuota semanal). Sus resultados van a una tabla en este
documento y a las comprobaciones de B3 («Modelo candidato medido»).

## Orden y lo que se hace en paralelo

- **Ya (Claude, sin GPU):** Fase A2 (las dos comprobaciones nuevas), Fase B5 (fuera lo del PC) y el arnés de
  medida de la Fase C.
- **Kaggle (cuota de la semana):** la prueba de Gauff con el marcador v16; después, las medidas de la Fase B
  (decodificar en la GPU, TensorRT, las 2 T4) con la prueba de 10 min como referencia.
- **Partidos enteros:** recomendación de Claude: **después de la Fase B**, que puede dividir el tiempo por partido. Con
  el código de hoy, cada partido gasta de 3 a 4 veces más cuota de Kaggle de lo necesario. Las medidas de modelos
  (Fase C) siguen en paralelo; si un modelo gana, los 6 partidos se rehacen con él.

Fuentes: [RTMO](https://arxiv.org/pdf/2312.07526), [RTMPose](https://arxiv.org/pdf/2303.07399),
[comparativa de pose 2026](https://hrcak.srce.hr/en/350091), [TrackNetV4](https://arxiv.org/pdf/2409.14543),
[BlurBall](https://arxiv.org/pdf/2509.18387), [TorchCodec en CUDA](https://docs.pytorch.org/torchcodec/0.4/generated_examples/basic_cuda_example.html),
[PyNvVideoCodec](https://docs.nvidia.com/video-technologies/pynvvideocodec/read-me/running-samples.html),
[ONNX frente a TensorRT](https://www.ultralytics.com/blog/onnx-vs-tensorrt),
[TensorRT en ONNX Runtime](https://github.com/microsoft/onnxruntime/blob/717d1da14874cd8f6fd7ede97f4369510e2452ca/docs/execution_providers/TensorRT-ExecutionProvider.md),
[F3Set con pocos ejemplos, 2026](https://arxiv.org/pdf/2604.22839), [UMEG-Net](https://arxiv.org/pdf/2511.14186).

## Arquitectura de ejecución en la nube (T24, #293, 15-11)

**Qué es del PC y qué no.** Las etapas (cortes, sonido, jugadoras, candidatos, identidad, pista, marcador, pasada fina…)
son el análisis: no dependen de la máquina. Lo que se diseñó para el PC (fase 0, octubre) es **cómo** corren: un
partido = un proceso en una máquina, etapas en serie, disco local. Al pasar a la nube (13-11) se movió tal cual; el plan
de nube nativa comparó infraestructura y modelos, **no la arquitectura de ejecución**. Es un hueco: este apartado.

**Lo que se queda (medido, no heredado):** las dos pasadas. Poner la pose solo en ±1 s alrededor de cada golpe (~10 % de
los fotogramas) es ~10 veces menos cálculo en cualquier infraestructura, y en la nube cálculo = cuota. Y el grafo de
etapas con huellas (cachés, recálculo incremental), el mismo patrón que Dagster (activos) o Hamilton.

**Alternativas de ejecución (estado del arte):**
- **Ray Data**: flujo por lotes en streaming, etapas de CPU (decodificar) y de GPU (modelos) escaladas por separado; la
  opción más citada para inferencia por lotes con GPU y vídeo (el equipo de Ray mide 2,5-12× frente a lotes clásicos;
  Anyscale, 2× frente a Spark en imágenes; datos del propio proveedor). Encaja dentro de una máquina; entre sesiones
  de Kaggle no hay red, así que no forma un clúster.
- **Modal `.map()`**: reparte un trabajo en N contenedores con GPU a la vez; un partido troceado acaba en minutos; el
  coste en segundos de GPU es el mismo (el límite es el crédito de 30 $/mes).
- **PySpark / Spark**: hecho para ETL de tablas en clústeres de la JVM; trata la GPU como añadido; sin clúster con GPU
  gratis. **No encaja** con vídeo y modelos en GPU a 0 €. **Dask**: bueno para escalar pandas; flojo con GPU y actores.
- **Vídeo nativo de GPU** (DeepStream/Savant, PyNvVideoCodec sin copias): lo más rápido, pero rehace el análisis;
  candidato más adelante.

**El límite real a 0 €:** las horas de GPU gratis (Kaggle 30 h por semana, 2 sesiones; Modal 30 $/mes). Repartir baja el
tiempo de reloj y usa todos los proveedores a la vez, pero no crea horas; la eficiencia sí (R48 casi divide el tiempo
por 2). Por eso, primero eficiencia y después reparto.

**Propuesta, a decidir con pruebas de concepto (#288):**
1. **Plano de datos repartido**: cada partido en unidades independientes (tramos de planos para la pasada barata,
   grupos de ventanas para la fina) en una cola de tareas sobre el almacenamiento (el volumen de Modal); cualquier
   trabajador (2 sesiones de Kaggle, contenedores de Modal, el PC si volviera) toma unidades por capacidad y el
   resultado se junta siempre igual (comprobado con `comparar`). Generaliza T19. Prueba: la prueba de 10 min con 2
   sesiones a la vez, el mismo resultado y su tiempo de reloj.
2. **Dentro de cada máquina, en streaming**: decodificar en hilos de CPU mientras la GPU procesa lotes (Ray Data frente
   a nuestro propio encadenado). Prueba: la pasada fina de la prueba de 10 min.
3. Fuentes: [Ray Data, modelo de lotes en streaming](https://arxiv.org/html/2501.12407v5),
   [Anyscale: Ray, Spark y SageMaker](https://www.anyscale.com/blog/offline-batch-inference-comparing-ray-apache-spark-and-sagemaker),
   [Anyscale: CPU y GPU en streaming](https://www.anyscale.com/blog/streaming-distributed-execution-across-cpus-and-gpus),
   [ByteDance con Ray Data](https://www.zenml.io/mlops-database/bytedance-large-scale-offline-inference-platform-ray-data-pipeline-parallel-offline-inference-for-multimodal-llm-embeddi),
   [Modal](https://modal.com/?via=aigregator), [comparativa de cómputo distribuido](https://medium.com/@adnanmasood/scaling-ai-workloads-the-distributed-compute-choice-bb986c4ec0ee).

