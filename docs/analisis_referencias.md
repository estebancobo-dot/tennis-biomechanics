# Análisis: qué adoptar de «Claude as a Tennis Coach» y otros proyectos de 2026 (02-11)

Hecho antes de tocar código, a petición del usuario («usa su código y los modelos que sirvan, sigue con el plan»).
Fuentes leídas:
- El artículo (offpolicyinc.com/work/claude-tennis-coach, 22-10-2026).
- Su código: github.com/offpolicyinc/deep-sports-analysis, licencia MIT, commit 2d742ad del 27-10. Leídos `docs/PIPELINE.md`, `gpu/models.py`, `gpu/strokes.py`, `measure/technique.py` y `measure/profiles.py`.
- Una búsqueda de proyectos y artículos de 2026.

Cada fila de este documento termina en una decisión con su criterio automático. Nada se adopta sin medirlo en nuestros datos.

## 1. Su sistema frente al nuestro, pieza a pieza

| Pieza | Ellos | Nosotros (medido) | Decisión | Criterio automático |
|---|---|---|---|---|
| Juego en directo | PySceneDetect + detector de pista (pista entera) | TransNetV2 + líneas + tipos de toma; 41 retransmisiones sin pérdidas; tomas < 15 min | **Mantener** | — |
| Repeticiones | Fotogramas repetidos; golpes a > 2,5 s dentro de un punto | Marcador ausente, recorrido repetido más lento, sin sonido | **Añadir** su regla de 2,5 s entre golpes como señal más (B-11) | Recall F3Set sin bajar precisión |
| Golpes | F3ED (modelo publicado de F3Set). Avisan: a 50/60 fps pierde la mitad, ve solo el 56 % central del fotograma | Detector propio entrenado con F3Set + bola; recall 80 % | **Probar** F3ED a 25 fps en ONNX frente al nuestro (B-6/#204) | Recall y precisión F3Set; tiempo en la iGPU |
| Personas | RF-DETR M: jugador lejano 100 % (YOLO11m 98,5 %), 0,025 s/fotograma en una L4 | YOLO; lejano por recorte que la sigue; recall lejano 64 % | **Probar** RF-DETR (tiene exportación oficial a ONNX) en el lado lejano | Recall lejano F3Set; tiempo |
| Bola | WASB (HRNet, 3 fotogramas, F1 0,886 a 4 px) | TrackNetV3 (RacketVision) en fp16, 25 fotogramas/s; es lo más lento de un partido nuevo | **Probar** WASB a ONNX (B-7): precisión y **velocidad** | Golpes y botes en RacketVision; fotogramas/s en el PC |
| Pista | TennisCourtDetector, 14 puntos (95,6 % a 7 px) | Líneas propias + homografía | **Probar** donde la nuestra falla (B-9) | Tramos con pista; error de reproyección |
| Esqueleto | RTMW-x, 65 puntos con pies y manos (OKS 0,855; pies 0,833) | YOLO11m-pose + RTMPose-x para los pies (dos modelos); RTMW3D-x aparte para la mano | **Probar** RTMW-x 2D como modelo único: puede quitar un modelo de la pasada fina (B-4) | Mismos golpes; ruido de las medidas ≤ el actual; tiempo |
| Seguimiento | ByteTrack | Propio con apariencia | **Mantener** | — |
| Quién es quién | Color de la ropa + Opus nombra a los jugadores | Ropa + un clic por partido | **Mantener**: la aplicación no debe depender de un servicio de pago | — |
| Medidas | 22 de golpe + 11 de saque, en largos de torso; filtro de golpes de rutina (profundidad, carrera, muñeca de abajo arriba) | Más de 60, en % de altura y cm | **Añadir** las que no tenemos (§3) y su **filtro de rutina** para comparar | Que la cámara explique < 10 % (§2) |
| Cámara | Zoom, ángulo, inclinación, línea de fondo y calidad restados dentro de cada jugador; la medida se descarta si la cámara explica ≥ 10 % de su variación | Tabla de fiabilidad escrita a mano en CLAUDE.md | **Adoptar**: cálculo automático y prueba en la auditoría (§2) | El % de cada medida en cada ejecución |
| Estadística | Welch + Holm por jugador, diferencia ≥ 0,4 desviaciones | Estadística propia con comparaciones múltiples | **Añadir** su resta de la cámara a nuestra estadística | Mismos hallazgos o menos falsos |
| Consejos | Opus lee las medidas y redacta | Frases y lecciones calculadas | Opcional y al final: la aplicación debe funcionar sin Claude | — |
| Hardware | NVIDIA L40S/L4 en la nube; unos 50 min de GPU por 26 min de vídeo | iGPU Radeon 780M | Sus modelos en PyTorch/CUDA hay que pasarlos a ONNX, como se hizo con RacketVision | — |

## 2. La regla de la cámara aplicada ya a nuestros datos (sin el PC)

Hecho con las 193 derechas del lado cercano de los 4 partidos (`referencia_forehand.zip`):
- **Variables de la cámara**, sacadas de la homografía de cada golpe: zoom, ángulo, inclinación, posición de la línea de fondo, altura de la jugadora en píxeles e inclinación de la cámara.
- **Método:** se restan dentro de cada partido y se mide qué parte de la variación entre golpes explican.
- **Umbral de azar:** lo que explican las mismas variables con los golpes barajados al azar (percentil 95).

| Medida | La cámara explica | Azar | Veredicto |
|---|---|---|---|
| Lecturas 3D del tronco | 47,6 % | 15,8 % | Depende de la cámara |
| Giro de hombros 3D | 20,5 % | 17,2 % | No fiable |
| Hueco de bola antes del golpe | 18,2 % | 9,2 % | Depende de la cámara (lo pequeña que se ve la bola) |
| Altura de la muñeca al terminar | 8,4 % | 6,9 % | Algo por encima del azar, bajo el 10 % |
| Todas las medidas 2D restantes (giros, codo, apoyo, base, altura del impacto, tiempos, cabeza, X-factor 2D) | 0,6-6 % | 6-8 % | Dentro del azar |

**Límites, dichos claramente:**
- Son 4 partidos del mismo torneo, con cámaras muy parecidas. La prueba tiene poca potencia, así que «dentro del azar» no demuestra que esas medidas no dependan de la cámara.
- Cuando entren partidos de otros torneos y cadenas, la misma prueba será concluyente. Por eso pasa a la auditoría y se repite en cada ejecución.
- Ya confirma lo que decía la revisión: **el 3D (RTMW3D) no sirve para las rotaciones**.

## 3. Medidas suyas que no tenemos

Las añadimos calculadas desde nuestras series, sin modelos nuevos:
- **Duración del swing**: del final del armado (la muñeca en su punto más lento) al impacto.
- **Hombros abiertos en el impacto y al terminar**: 0 de lado, 90 de frente a la red.
- **Armado hacia fuera**: la muñeca respecto a la cadera al final del armado, en largos de torso.
- **Brazo en la terminación**: ángulo del brazo vista desde atrás, por encima del hombro o cruzado.
- **Ángulo de apoyo con signo**: el pie delantero cruzado o abierto, en la pista.
- **Largos de torso como segunda escala**, junto a la altura. No depende de la altura registrada de la jugadora, que en un jugador nuevo puede faltar.

Medidas que ellos descartan desde atrás y que nosotros mostramos con fiabilidad media: el codo en el impacto, la separación cadera-hombros 2D, las rodillas, los pies en profundidad y la velocidad de la muñeca. Con nuestros datos de hoy no pasan del azar. Se deciden con la prueba del §2 cuando haya partidos de otras cámaras. Hasta entonces siguen marcadas como fiabilidad media; no se borran.

## 4. Otros proyectos y datos encontrados (búsqueda del 02-11)

- **philippdubach/tennis-vision**: retransmisiones con F3ED + OCR del marcador + conciliación por cambios de tanteo. Revisar su conciliación para el resultado del punto (P1, hoy «no creíble»).
- **JustinSongXh/tennisvision**: bola, botes, cortes en puntos, pose y golpes. Revisar su detector de botes (B-10).
- **CalTennis** (arXiv 2606.20542): vídeo de tenis desde varias cámaras a la vez. Permite **validar de forma automática** las rotaciones y los pies frente a una referencia multivista. Es la validación automática que faltaba para B-6.
- **Capture4D** (Sensors 26-1411): con una sola cámara se conserva el orden temporal de la cadena cinética. Coincide con nuestro enfoque, que juzga el orden y no los valores.
- explainx.ai/roboflow (iPhone + RF-DETR + MediaPipe): sin código ni medidas de precisión. No aplicable.

## 5. Orden de ejecución

Encaja en el bloque 1 (Base) de `plan_maestro.md`. Cada paso termina con su medida antes del siguiente.

1. **B-15a, en la nube, ya.** La prueba de la cámara del §2 como módulo (`tennisbio.camera_share`), con la auditoría mostrando el % de cada medida. Prueba automática.
2. **B-15b, en la nube.** Las medidas del §3 desde las series, con pruebas. Después, la prueba de la cámara sobre ellas.
3. **B-4, en el PC, en curso.** Peticiones 70-71, velocidad de un partido nuevo con todo en fp16.
4. **B-15c, en la nube y el PC.** Pasar a ONNX los modelos de sus pruebas: WASB, RTMW-x 2D, RF-DETR, TennisCourtDetector y F3ED. Medir cada uno en el PC con `scripts/model_trials.py` frente al nuestro, en precisión y en fotogramas/s. Adoptar solo los que mejoren sin empeorar el tiempo de un partido nuevo. Orden por impacto: primero WASB y RTMW-x, que afectan a lo más lento (la bola de todo el juego y la pose de la pasada fina); luego RF-DETR para el lado lejano, TennisCourtDetector y F3ED.
5. **B-15d.** Su regla de repeticiones (golpes a > 2,5 s) en B-11, y la conciliación del marcador de tennis-vision en P1.
6. **B-6 con CalTennis**: validación automática del 3D, o retirarlo de la cadena si no la pasa.
