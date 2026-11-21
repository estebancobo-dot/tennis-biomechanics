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

> **15-11:** las filas de bola, instante del golpe y pasada barata no recogían el banco de candidatos del PC del 07-11 (`pc-logs:bench_candidates.md`): WASB, F3ED, RF-DETR, RTMW, la pista de 14 puntos, el 3D de MotionAGFormer y los botes ya tenían su medida de calidad, que no depende de la máquina. Corregido abajo; solo su velocidad era del PC (B).

## Por componente

| Componente | Hoy | Cómo se decidió | Descartado o sin probar (y por qué) | Qué se hace |
|---|---|---|---|---|
| Pose 2D de la pasada fina | Híbrido: YOLO11m-pose (FP16) encuentra, RTMPose-x / RTMW-x (FP32) rehace con pies | PC, 6 clips de RacketVision, **13 golpes**: mismos golpes, −35 % de temblor, pies en el 99,7 % (A, muestra pequeña) | **Sapiens2** (Meta 2026, «inviable en la iGPU»: B); **RF-DETR / DEIMv2** («los DETR van mal en DirectML»: B); RTMPose en FP16 («más lento en DirectML»: B); YOLO26-pose (sin pies); ViTPose++, RTMO, BBoxMaskPose v2, ER-Pose (C) | **Reabrir**: candidatos con pies frente al híbrido, medidos por golpes y tipo en F3Set, temblor y pies vistos; buscar pose anotada de deporte (CVBW 2026) |
| Pose de la pasada barata | YOLO11m-pose 960 FP16 | Tiempo del PC (B); 640 px dio F1 0,71 frente a 0,64 con 13 golpes (ruido) | 640 px, YOLO26, RF-DETR (B/C) | **Reabrir** con F3Set (jugadoras vistas, identidad) **15-11 (corregido):** RF-DETR **medido** en el PC el 07-11 (`bench_candidates.md`): halla a la jugadora lejana en el 100 % frente al 90,3 % de YOLO11m-pose en la mitad lejana, pero a 0,5 frente a 1,3 fotogramas/s en el PC (B): **reabrir su velocidad con CUDA** (calidad mejor medida). |
| Cuerpo 3D (rotaciones) | RTMW3D-x y MotionAGFormer | PC (B) | **GVHMR y WHAM** («solo CUDA»: B, la nube tiene CUDA); **SAM 3D Body** («muy pesado»: B); TRAM, OnlineHMR, PVA-Net 2026 (C) | **Reabrir**: consistencia de las rotaciones entre golpes casi iguales |
| Bola | TrackNetV3 (RacketVision) | A: golpes con la bola, precisión 0,73 y recall 0,84 (validación del 10-10) | **TOTNet** («pesado»: B); WASB (sin medir: C); TrackNetV4 (sin pesos; una reproducción no confirmó la mejora); BlurBall (C) | **Medido en GPU (15-11, `medir_bola_totnet_gpu`, A):** en los 30 clips de prueba de RacketVision, TOTNet F1 0,792 (precisión 0,808, recall 0,777) frente a TrackNetV3 0,911 (0,951 y 0,874), y 518 ms por fotograma frente a 57: **se aparta** por la regla escrita antes (F1 ≥ TrackNetV3 − 0,02). **Se queda TrackNetV3**; la bola del partido, decodificando en un hilo (v32: el detector de 222,6 a 186,8 s, mismo resultado) |
| Raqueta (5 puntos) | RTMPose-m de RacketVision; FP16 | A (el modelo de RacketVision); FP16 por tiempo del PC (B) | Nada mejor encontrado | **Medido en la nube (15-11)**: precisión completa +16,8 % de tiempo sin prueba de medir mejor: se queda FP16. La cara salta 180° con cambios mínimos: R50 |
| Instante y tipo de golpe | Detector propio entrenado con F3Set, con la bola | A: F3Set (466 de 517 golpes, 90 %; tipo 97 %) | **F3ED** (el método de los autores de F3Set), UMEG-Net, E2E-Spot, T-DEED (C) | **Medir** en F3Set (precisión, recall, error de instante) **15-11 (corregido):** F3ED **sí estaba medido** en el PC el 07-11 (`bench_candidates.md`, puntos de prueba de F3Set): F1 0,994 frente a 0,997 del detector propio y 5 veces más lento: **descartado** por calidad (no mejora). |
| Bote | Modelo propio (GBDT) | A: F1 0,884 frente a 0,594 de la regla, en partidos no vistos | — | Se queda |
| Pista | TennisCourtDetector 14 puntos + refinado | Banco del PC (`bench_candidates`): calidad y tiempo (A/B) | — | Comprobar la calidad en la nube con las pruebas de 10 min |
| Cortes de plano | TransNetV2 | Sustituyó al detector propio (A parcial) | AutoShot, OmniShotCut 2026 (C) | **Medir** con una muestra anotada |
| Marcador | RapidOCR (PP-OCR) en la CPU | Lecturas en los partidos reales (A) | Lectura en la GPU de la nube (solo se activaba con DirectML: B); un modelo de visión y lenguaje para casos difíciles (C) | **Medir** el OCR en la GPU; el de visión y lenguaje, solo si hay fallos **15-11 (v28 frente a v26, Kaggle):** con CUDA, resultado idéntico y la etapa 110 → 61 s (−44 %): **adoptado** (`score.ocr_gpu`, encendido por defecto, solo con GPU NVIDIA) |
| Seguimiento e identidad | Propio (lado y ropa) + el clic | A: la identidad del 98 % en Pegula | SAM 3 + Deep-EIoU (86,8 HOTA en SportsMOT, 2026: C) | **Medir** en los cambios de lado de los 6 partidos |
| Sonido (impactos) | Onsets de librosa (señal secundaria) | A: la bola decide; el sonido llega 2-4 fotogramas tarde | Detectores entrenados (TennisExpert 2026: C) | Bajo impacto: después |
| Ejecución de modelos | ONNX Runtime CUDA, FP16 donde se decidió en el PC | Medido en la nube: CUDA FP32 1,9-10,5 ms por imagen (T6); TensorRT no arranca | TensorRT (no arranca), torch.compile (C) | FP16 frente a FP32: en medida (v21) |
| Decodificar vídeo | ffmpeg en la CPU | **Medido en la nube** (T7): gana la CPU | PyNvVideoCodec, TorchCodec con los fotogramas en la GPU (C) | Con T24 (la arquitectura) |
| Arquitectura de ejecución | **Por partes (15-11, adoptado):** el principio (cortes, pista, audio) y el final (vistas, recortes, cámara lenta) en sesiones de **CPU** de Kaggle, que no gastan horas de GPU; el medio en GPU; cada parte sobre lo que hizo la anterior (R55-R57) | **Medido (A):** la prueba de 10 min de Gauff por partes (v31) frente a entera (v26): **equivalente** (28 de 28 golpes con las mismas medidas, temblor ×1,00; distintos solo los ficheros de audio, vistas y cámara lenta, sin efecto en los golpes) con **0,28 h de GPU frente a 0,45 h** (−38 %) | Ray Data, Modal `.map`, vídeo nativo de GPU (C); PySpark y Dask no encajan (motivo en `nube_nativa.md`) | **Hecho** lo de las partes; **adoptada** la bola decodificando en un hilo (pieza 2; v32 frente a v26: mismos golpes con las mismas medidas, `spotting` igual y de 222,6 a 186,8 s, −16 %); el reparto por ventanas entre sesiones (T19) después: baja el tiempo de reloj, no las horas de GPU |

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

## Viabilidad de cada candidato (15-11 05:30: pesos y licencia; uso personal, no comercial)

| Candidato | Pesos | Licencia | Para este proyecto |
|---|---|---|---|
| Sapiens2 (pose, Meta, ICLR 2026) | Públicos (Hugging Face, `facebook/sapiens2-pose-0.4b` / `-0.8b` / `-1b` / `-5b`; safetensors F32, ~1,6 GB el 0.4B; **sin ONNX**: habría que exportarlo) | **Leída (15-11, LICENSE.md oficial):** «Sapiens2 License», propia de Meta, gratuita y mundial; no tiene cláusula de uso no comercial ni permite el comercial de forma expresa. **Prohíbe** la vigilancia, el «procesamiento biométrico» (sin definirlo), identificar a personas de sus datos e inferir salud sin consentimiento; obliga a cumplir el RGPD y las leyes de datos biométricos. La pose de jugadoras identificadas (este proyecto) **podría** leerse como procesamiento biométrico: es una decisión del usuario, no técnica | **308 puntos con pies** (talón y dedos; «Foot» AP 78,4 el 0.4B y 81,0 el 1B), descendente (necesita detector), entrada 1024×768. Coste: el 0.4B son 1,26 TFLOP por recorte (unas 70 veces RTMPose-x); **sin medidas publicadas de velocidad** en ninguna GPU. **15-11 23:30, el usuario: «Puedes usar Sapiens2» (#307)**: se mide en Kaggle (`medir_sapiens2`, `tennisbio.infra.poc_sapiens`): el 0.4B y el 1B en los mismos recortes de la v26 que el híbrido, con la misma limpieza (`kinematics.clean`); comprobado en local que sus 308 puntos van bien a los 17 del cuerpo y los 6 de los pies. **Regla escrita antes de medir:** pasa a la prueba integrada (la pasada fina con Sapiens2, golpes frente a la v26) si tiembla al menos un 10 % menos en el cuerpo, no más en los pies y ve los pies al menos igual; su tiempo por recorte en la T4 dice las horas por partido; condiciones de la licencia respetadas: no identificar personas con él, no inferir salud, resultados privados, pesos nunca al repositorio, cita si se publica **21-11, medido (`medir_sapiens2_b`, T4, 23 golpes, 3.693 recortes, A):** temblor del cuerpo 0,00289 frente a 0,00481 del híbrido (−40 %), muñecas −28 %, pies −7 %, pies vistos 100 % frente a 96,6 %; a 1 % de su altura del híbrido. El 1B da lo mismo (0,00287) y es 3,3 veces más lento. **Pasa la regla, pero tarda 0,69 s por recorte**: un partido, unas 13 h de GPU más. Siguiente: el 0.4B a 768x576 y 512x384 (`medir_sapiens2_rapido`; en CPU, a 0,3 y 0,6 px de 1024x768 en una jugadora de 164 px), con la regla de quedarse el tamaño más pequeño que conserve la mejora. **21-11 02:30, medido (`medir_sapiens2_rapido`, A):** a 768x576, cuerpo −40 %, 349 ms por recorte; a **512x384**, cuerpo **−36 %** (0,00307 frente a 0,00481), muñecas −23 %, pies −7 %, pies vistos 100 %, **136 ms por recorte** (92 del modelo, el resto recorte y posprocesado en la CPU). **Elegido el 0.4B a 512x384.** Siguiente: la prueba integrada (en la pasada fina, en lugar de RTMPose-x para su pose con pies; golpes frente a la v26 y horas de GPU), con su plan enseñado al usuario antes de escribirla. **21-11 03:10 (el usuario: «sí, hazlo»):** integrado como `fine_pass.refine: sapiens2` (`tennisbio.pose.sapiens2`): la red en ONNX (`scripts/export_sapiens2.py`, exportador de torch.export con la atención «eager»; 1,7 GB, igual que PyTorch a 1e-6), el recorte y la decodificación del procesador portados a numpy (comprobado en un fotograma real: los mismos puntos a 0,000 px); por defecto sigue RTMPose-x (nada de lo analizado cambia). En cola `prueba_gauff_v33_sapiens2` frente a la v26, con su regla escrita antes (los mismos 28 golpes y el temblor de sus medidas ≤ 0,9 del de la v26). **21-11 04:00, la v33 no valió (`comparar_gauff_v26_v33`, A):** 26 de 28 golpes emparejados, temblor ×2,09, saltos en 20 golpes. **Causa:** en la GPU corría en media precisión y sus 97 normalizaciones RMS elevan al cuadrado valores de hasta ~600 (357 180, más que el máximo de fp16, 65 504): la media salía infinita y la capa, a cero. PyTorch las calcula en fp32 (por eso la medida de la PoC salió bien); en CPU no se ve (ONNX Runtime las pasa a fp32). Recorridos los 2 030 valores intermedios de la red en un recorte real: solo esos cuadrados pasan de 8 192. Dejar esas operaciones en fp32 con el conversor de ONNX Runtime daba un modelo erróneo (hasta 64 px, por las constantes compartidas); **arreglo:** cada normalización reescalada por 16 antes del cuadrado y la raíz multiplicada por 16 (la misma aritmética: idéntica bit a bit en fp32; el cuadrado, como mucho ~1 400) y, si un recorte se desborda aun así, ese recorte en precisión completa. En cola `prueba_gauff_v34_sapiens2` con la misma regla. |
| RF-DETR Keypoint (Roboflow) | Públicos | Apache 2.0 | **17 puntos COCO, sin pies**: no sustituye la pose de la pasada fina; candidato para la pasada barata (personas) |
| RTMW-x frente a RTMPose-x | En `models/` | Apache 2.0 | Elegido RTMPose-x **porque en el PC RTMW-x fue más lento** (B). **Medido en la nube (15-11)**: RTMW-x es un 6 % más lento, encuentra los mismos golpes y su temblor es ×0,988 (4944 medidas). Calidad igual, así que **se queda RTMPose-x** (A, un clip) |
| RTMPose-x en media precisión | — | — | **Medido en la nube (15-11, v27 frente a v26, misma prueba de 10 min en Kaggle)**: la pasada fina 507 → 489 s (−3,7 %), los 28 golpes emparejados, 1 cambia de tipo, temblor ×1,000 (5310 medidas). **No se adopta**: la ganancia es pequeña (~4 min por partido) y cambia medidas sin prueba de medir mejor (regla: igual calidad medida y menos tiempo). El ajuste `fine_pass.refine_fp16` queda, apagado |
| F3ED (detector de golpes de los autores de F3Set) | Código en github.com/F3Set/F3Set; pesos por confirmar | Por confirmar | Si no hay pesos, entrenarlo en una GPU con F3Set (el artículo dice que es rápido) |
| GVHMR / WHAM (cuerpo 3D) | Públicos | Investigación no comercial; **necesitan SMPL**, que exige registro personal en el Max Planck | Solo si el usuario se registra (no lo puede hacer Claude) |
| TOTNet (bola con oclusión) | **Públicos en su repositorio, también de tenis** (`weights/TOTNet_Tennis_…_best.pth`, 94 MB; comprobado el 15-11) | MIT | Corregido el 15-11: no solo de tenis de mesa. Exportado a ONNX (`scripts/export_totnet.py`, igual que PyTorch a 1e-7); ~6 s por fotograma en 4 núcleos de CPU. Medido frente a TrackNetV3 con `medir_bola_totnet` (`tennisbio.infra.poc_bola`) |
| WASB (bola) | Pesos de tenis en Google Drive (`MODEL_ZOO.md` de nttcom/WASB-SBDT) | Código MIT; los pesos no dicen licencia | Después de TOTNet, con la misma prueba |

Fuentes: [Sapiens2 en Hugging Face](https://huggingface.co/docs/transformers/model_doc/sapiens2),
[artículo de Sapiens2](https://arxiv.org/abs/2604.21681), [RF-DETR Keypoint](https://blog.roboflow.com/launch-rf-detr-keypoint-in-roboflow/),
[F3Set (ICLR 2025)](https://arxiv.org/html/2504.08222v2), [GVHMR](https://huggingface.co/ryanrudes/gvhmr),
[WHAM](https://github.com/yohanshin/WHAM), [licencias de SMPL](https://meshcapade.notion.site/The-SMPL-Model-Licenses-2144560e54388085af5eff111fcdf266),
[TOTNet](https://arxiv.org/html/2508.09650v1).

