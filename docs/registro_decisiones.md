# Registro de decisiones técnicas: en qué se basó cada una y qué se reabre (T25, #294, 15-11)

Pregunta del usuario (15-11): ¿hay que repetir el estado del arte desde cero?, ¿lo elegido es lo mejor?, ¿cómo se
asegura?, ¿se han desechado opciones que valen, antiguas o nuevas?

**Qué se puede asegurar y qué no.** «Lo mejor» en absoluto no se puede asegurar. Sí se puede asegurar, y comprobar, que:
1. ninguna opción está descartada por un motivo del PC (su iGPU, DirectML, su memoria, su tiempo);
2. cada elección tiene una medida **en la nube con datos anotados**, con una muestra que distinga mejoras del ruido;
3. la búsqueda de opciones nuevas se repite cada mes o antes de cada fase, con fecha.

**Clases de evidencia.**
- **A, calidad con datos anotados** (F3Set, RacketVision): vale en cualquier máquina; se reabre solo si aparece una
  opción nueva.
- **B, límite o tiempo del PC**: no vale para la nube; **se reabre**.
- **C, sin medir** (solo literatura o dato del proveedor): **se mide**.
- Muestra pequeña (p. ej. 13 golpes, donde ±0,07 de F1 es ruido): se repite con F3Set.

## Por componente

| Componente | Hoy | Cómo se decidió | Descartado o sin probar (y por qué) | Qué se hace |
|---|---|---|---|---|
| Pose 2D de la pasada fina | Híbrido: YOLO11m-pose (FP16) encuentra, RTMPose-x / RTMW-x (FP32) rehace con pies | PC, 6 clips de RacketVision, **13 golpes**: mismos golpes, −35 % de temblor, pies en el 99,7 % (A, muestra pequeña) | **Sapiens2** (Meta 2026, «inviable en la iGPU»: B); **RF-DETR / DEIMv2** («los DETR van mal en DirectML»: B); RTMPose en FP16 («más lento en DirectML»: B); YOLO26-pose (sin pies); ViTPose++, RTMO, BBoxMaskPose v2, ER-Pose (C) | **Reabrir**: candidatos con pies frente al híbrido, medidos por golpes y tipo en F3Set, temblor y pies vistos; buscar pose anotada de deporte (CVBW 2026) |
| Pose de la pasada barata | YOLO11m-pose 960 FP16 | Tiempo del PC (B); 640 px dio F1 0,71 frente a 0,64 con 13 golpes (ruido) | 640 px, YOLO26, RF-DETR (B/C) | **Reabrir** con F3Set (jugadoras vistas, identidad) |
| Cuerpo 3D (rotaciones) | RTMW3D-x y MotionAGFormer | PC (B) | **GVHMR y WHAM** («solo CUDA»: B, la nube tiene CUDA); **SAM 3D Body** («muy pesado»: B); TRAM, OnlineHMR, PVA-Net 2026 (C) | **Reabrir**: consistencia de las rotaciones entre golpes casi iguales |
| Bola | TrackNetV3 (RacketVision) | A: golpes con la bola, precisión 0,73 y recall 0,84 (validación del 10-10) | **TOTNet** («pesado»: B); WASB (sin medir: C); TrackNetV4 (sin pesos; una reproducción no confirmó la mejora); BlurBall (C) | **Reabrir** TOTNet y medir WASB con la bola anotada de RacketVision |
| Raqueta (5 puntos) | RTMPose-m de RacketVision; FP16 | A (el modelo de RacketVision); FP16 por tiempo del PC (B) | Nada mejor encontrado | **Medido en la nube (15-11)**: precisión completa +16,8 % de tiempo sin prueba de medir mejor: se queda FP16. La cara salta 180° con cambios mínimos: R50 |
| Instante y tipo de golpe | Detector propio entrenado con F3Set, con la bola | A: F3Set (466 de 517 golpes, 90 %; tipo 97 %) | **F3ED** (el método de los autores de F3Set), UMEG-Net, E2E-Spot, T-DEED (C) | **Medir** en F3Set (precisión, recall, error de instante) |
| Bote | Modelo propio (GBDT) | A: F1 0,884 frente a 0,594 de la regla, en partidos no vistos | — | Se queda |
| Pista | TennisCourtDetector 14 puntos + refinado | Banco del PC (`bench_candidates`): calidad y tiempo (A/B) | — | Comprobar la calidad en la nube con las pruebas de 10 min |
| Cortes de plano | TransNetV2 | Sustituyó al detector propio (A parcial) | AutoShot, OmniShotCut 2026 (C) | **Medir** con una muestra anotada |
| Marcador | RapidOCR (PP-OCR) en la CPU | Lecturas en los partidos reales (A) | Lectura en la GPU de la nube (solo se activaba con DirectML: B); un modelo de visión y lenguaje para casos difíciles (C) | **Medir** el OCR en la GPU; el de visión y lenguaje, solo si hay fallos |
| Seguimiento e identidad | Propio (lado y ropa) + el clic | A: la identidad del 98 % en Pegula | SAM 3 + Deep-EIoU (86,8 HOTA en SportsMOT, 2026: C) | **Medir** en los cambios de lado de los 6 partidos |
| Sonido (impactos) | Onsets de librosa (señal secundaria) | A: la bola decide; el sonido llega 2-4 fotogramas tarde | Detectores entrenados (TennisExpert 2026: C) | Bajo impacto: después |
| Ejecución de modelos | ONNX Runtime CUDA, FP16 donde se decidió en el PC | Medido en la nube: CUDA FP32 1,9-10,5 ms por imagen (T6); TensorRT no arranca | TensorRT (no arranca), torch.compile (C) | FP16 frente a FP32: en medida (v21) |
| Decodificar vídeo | ffmpeg en la CPU | **Medido en la nube** (T7): gana la CPU | PyNvVideoCodec, TorchCodec con los fotogramas en la GPU (C) | Con T24 (la arquitectura) |
| Arquitectura de ejecución | Un partido = un proceso en una máquina | Fase 0, para el PC (B) | Ray Data, Modal `.map`, vídeo nativo de GPU (C); PySpark y Dask no encajan (motivo en `nube_nativa.md`) | **Reabrir**: T24 |

## Cómo se decide (regla escrita antes de medir)

1. Los datos: F3Set (517 golpes en la validación; 11 584 clips en total) y RacketVision (bola y raqueta anotadas). Nunca
   decisiones con 13 golpes.
2. Primero la calidad: una opción solo entra si es igual o mejor en calidad con esos datos; entre iguales, la más
   barata en horas de GPU.
3. Si un modelo gana, los partidos ya analizados se rehacen con él (T16): la pasada barata se reutiliza, solo cambia lo
   que dependa del modelo.
4. Cada decisión queda en esta tabla, con su fecha y su medida.

## Orden

Las pruebas cuestan horas de GPU (Kaggle: 30 a la semana, compartidas con los partidos):
- Los partidos siguen en una sesión con los modelos de hoy; sus resultados son válidos, y se rehacen solo si un
  modelo gana.
- La otra sesión hace las pruebas, por orden de impacto en la derecha:
  1. Pose con pies (Sapiens2, RF-DETR, RTMPose FP16) frente al híbrido.
  2. Detector de golpes (F3ED) frente al propio.
  3. Cuerpo 3D (GVHMR, WHAM) para las rotaciones.
  4. Bola (TOTNet, WASB).
  5. Lo demás.
- Antes de cada prueba, comprobar que el candidato tiene pesos públicos, licencia válida y exportación a ONNX (o
  PyTorch en la nube).
