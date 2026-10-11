# tennis-biomech

Análisis biomecánico **cinemático 2D** de golpes de tenis a partir de retransmisiones de TV.
Centrado en **1 jugador y 1 tipo de golpe** por análisis, parametrizable.
Primer caso: **derecha de Elena Rybakina** en 4 partidos completos.
Después: revés, saque, volea y otros jugadores.

## Rutas (Windows, fuera del repo)
- Vídeos: `C:\tenis\videos\` (~5 GB por partido, retransmisión completa). **Nunca a git.**
- Salidas (datos extraídos, recortes, informes): `C:\tenis\output\`.
- Repo: `C:\tenis\tennis-biomech\` — solo código y configuración.
- Las rutas se leen de `config/local.yaml` (no versionado); nada de rutas absolutas en el código.

## Equipo y restricciones técnicas
- Beelink SER5 MAX: Ryzen 7 7735U (8C/16T), 24 GB RAM, SSD 500 GB, iGPU Radeon 680M. Windows 11.
- **Sin NVIDIA / sin CUDA / sin WSL.** Inferencia con ONNX Runtime: `onnxruntime-directml`
  (iGPU) o CPU. Todo el código debe funcionar nativo en Windows (ojo con rutas, `multiprocessing` con `spawn`).
- Python 3.11 gestionado con `uv`. ffmpeg en el PATH.
- Librerías base: OpenCV, numpy, pandas, librosa, onnxruntime(-directml).
- Pose: RTMPose (o YOLO-pose) exportado a ONNX. Detección de personas ligera (YOLO/RTMDet ONNX).
- Disco limitado (500 GB): no extraer fotogramas del partido entero; guardar solo clips/ventanas.

## Estrategia: dos pasadas (NO pasar pose por el partido entero)
1. **Pasada barata** (todo el partido, baja resolución/fps):
   - Cortes de plano → quedarse solo con la cámara principal (fuera repeticiones y primeros planos).
   - Impactos de bola por **audio** (onsets/transitorios).
   - Detección ligera de jugadores → lado de pista y quién golpea.
   - Se registran **todos los impactos de ambos jugadores** (no solo el golpe objetivo):
     así otro golpe u otro jugador del mismo vídeo no exige repetir esta pasada.
   - El usuario confirma **con un clic** quién es la jugadora al inicio de cada partido;
     el seguimiento tiene en cuenta los cambios de lado.
   - (Fase 3) OCR del marcador de TV: set/juego/tanteo, situaciones de presión.
2. **Pasada fina**: pose a máxima calidad y fps completos solo en ventanas de **±1 s**
   alrededor de cada golpe de la jugadora objetivo.

## Procesado incremental
- Catálogo `config/matches.yaml`: una entrada por vídeo (jugadores, rival, torneo, fecha,
  superficie, ronda). Añadir un partido = añadir su vídeo y su entrada.
- Cada partido tiene su carpeta `C:\tenis\output\<match_id>\` con un fichero por etapa
  (cortes, impactos, jugadores, golpes, pose, métricas). Cada fichero registra la huella
  de sus entradas: vídeo (tamaño + fecha), configuración relevante y versión de la etapa.
- `tennisbio run --all` ejecuta solo lo que falta o cuyas entradas cambiaron:
  - vídeo nuevo → todas las etapas;
  - cambia una fórmula de métrica → solo métricas, desde la pose guardada;
  - cambia el modelo de pose → solo la pasada fina y lo que depende de ella.
- Los agregados e informes se recalculan siempre juntando todos los partidos (es barato).
- Las revisiones manuales (identificación de la jugadora, golpes confirmados/descartados)
  se guardan en ficheros propios y **nunca** se sobrescriben al recalcular.

## Métricas por golpe (derecha)
- Tipo de apoyo (abierto / semiabierto / cerrado), anchura de la base, flexión de rodillas.
- Rotación de cadera y hombros y su separación (X-factor).
- Ángulo del codo; punto de impacto respecto al cuerpo.
- Secuencia de la cadena cinética (orden de los picos de velocidad angular/lineal).
- Posición en pista (homografía a partir de las líneas).
- Fases: preparación, armado, aceleración, impacto, terminación.
- Agregados: por partido/set, inicio vs final (fatiga), ganadores vs errores, presión.
- Salida: **informe HTML** con gráficos y fotogramas con el esqueleto dibujado.

## Métricas ampliadas (como los sistemas profesionales, dentro de lo medible en TV)
**Cuerpo:** además de las anteriores, altura del impacto (% de altura), inclinación lateral del
tronco en el impacto, extensión del brazo no dominante en el armado, estabilidad de la cabeza
(±50 ms del impacto), tipo de terminación (sobre el hombro / limpiaparabrisas).

**Raqueta** (modelo de 5 keypoints: empuñadura, garganta, punta, dos laterales del cabezal;
base pública: RacketVision, AAAI 2026, entrenado con RTMPose → encaja en el stack; afinar
con ~300-500 fotogramas propios etiquetados). Curvas a lo largo de todo el golpe:
- Altura de la cabeza respecto a la muñeca (armado: por encima; caída antes de acelerar).
- Ángulo de la cara (abierta/cerrada) a partir de la elipse del cabezal (ambigüedad de signo
  resuelta con la continuidad temporal).
- Trayectoria bajo → alto en los ~60 ms previos al impacto; ángulo antebrazo–raqueta (lag);
  altura de la terminación.
- **Fiabilidad por fase:** buena en espera, preparación, armado y terminación; **baja en
  aceleración e impacto** (a 25-50 fps la cabeza recorre 40-70 cm por fotograma y sale
  borrosa). La cara en el impacto es una estimación interpolada y se marca como tal.

**Pies y equilibrio:** split step (aterrizaje respecto al impacto del rival, audio + tobillos),
tiempo de reacción (primer movimiento), pasos de ajuste, tiempo y distancia de recuperación.

**No medible desde TV** (lo tienen Hawk-Eye/laboratorio): velocidad de cabeza de raqueta absoluta,
efecto (rpm), velocidad de bola, altura sobre la red, fuerzas. Seguimiento de bola (TrackNet)
daría dirección y profundidad aproximadas (fase 3-4).

**Vídeos de YouTube**: enlaces de referencia en el informe (no se descargan). Si el usuario
aporta clips propios en cámara lenta (p. ej. entrenamientos a pie de pista), pueden servir como
fuente secundaria con mejor visibilidad de la raqueta; uso bajo su responsabilidad.

## Fiabilidad de cada métrica según la cámara
Fuente: cámara principal de TV, detrás del fondo y elevada. La jugadora del lado cercano
se ve de espaldas y desde arriba. No hay vistas laterales ni frontales sincronizadas
(las repeticiones con otros ángulos se descartan). Cada métrica lleva su nivel de fiabilidad
y el informe lo muestra.

| Métrica | Fiabilidad | Nota |
|---|---|---|
| Tipo de apoyo, anchura de la base | Buena | Pies en el plano de la pista (homografía) |
| Posición en pista, desplazamiento | Buena | Ídem |
| Punto de impacto lateral (separación del cuerpo) | Buena | |
| Rotación hombros/cadera, X-factor | Media | Ambigüedad de profundidad; candidata a 3D monocular |
| Ángulo del codo | Media | Depende de la orientación del brazo |
| Orden de la cadena cinética | Media | El orden de los picos es más fiable que sus valores |
| Flexión de rodillas | Media-mala | Escorzo; preferir medidas relativas (descenso de cadera) |
| Impacto delante/detrás del cuerpo | Mala | Eje de profundidad; solo con 3D estimado |

Una cámara lateral propia solo tendría sentido con vídeos grabados por el usuario (ampliación futura).

## Situación del golpe (para comparar golpes equivalentes)
Toda comparativa (fatiga, presión, partidos) se hace **dentro de situaciones equivalentes**;
si no, un cambio de técnica se confunde con un cambio en la bola recibida.
La bola no se mide directamente (pequeña y borrosa en TV); se deduce indirectamente:

| Situación | Indicador |
|---|---|
| Bola rápida / lenta (tiempo disponible) | Intervalo entre el impacto del rival y el suyo (audio) |
| Bola centrada / abierta | Distancia y dirección recorridas entre ambos impactos (pies + homografía) |
| Bola corta / profunda | Posición en pista en el impacto |
| Bola baja / media / alta | Altura del impacto respecto al cuerpo (rodilla, cadera, hombro) |
| Ataque / neutra / defensa | Combinación de lo anterior |
| Apoyo | Abierto / semiabierto / cerrado, en carrera, en salto |

- Media volea: solo "candidata" (impacto muy bajo justo tras el bote) → cola de revisión.
- No fiable sin seguimiento de bola: efecto (liftado/cortado) y dirección exacta del golpe.
  Seguimiento de bola tipo TrackNet = ampliación opcional en fase 3-4.

## Informe y salida visual
- Usuario del informe: el propio autor del proyecto (técnico; vocabulario biomecánico con glosario).
- Maqueta de referencia del diseño: `docs/maqueta-informe.html` (datos inventados).
- HTML offline en 5 pantallas: resumen con conclusiones en frases (y su confianza), derecha típica,
  explorador de golpes con filtros y comparación lado a lado, comparativas por situación,
  mapa de pista. Cada número enlaza a sus clips. Herramienta de revisión aparte.
- **Secuencia de 8 fotogramas clave por golpe** (recorte ampliado de la jugadora, esqueleto y valores):
  1 espera/split step (impacto del rival, audio) · 2 inicio de preparación (empiezan a girar
  los hombros) · 3 armado completo (máxima rotación de hombros) · 4 inicio de aceleración
  (empieza a girar la cadera; punto más bajo de la muñeca) · 5 impacto (audio) ·
  6 extensión (~40-60 ms después) · 7 terminación (muñeca en su punto más alto) ·
  8 recuperación (primer paso de vuelta). Los momentos salen de eventos de la pose y del
  audio; se pueden corregir en la revisión. Además: imagen estroboscópica (esqueletos
  superpuestos y trayectoria de la muñeca) y tira de contactos.
- **Galerías por tipo de golpe y situación** (apoyo, bola, presión, resultado), ordenadas por:
  calidad de captura (confianza de la pose, sin oclusión ni desenfoque), representatividad
  (cercanía a la mediana de la jugadora) y resultado del punto. **No** hay una puntuación de
  "mejor técnica" absoluta: no está validada para vídeo de TV.

## Limitaciones asumidas (no "arreglarlas" con falsa precisión)
- 2D desde una sola cámara; cualquier 3D es estimación.
- Desenfoque en el impacto a 25-50 fps: velocidades absolutas no fiables, **comparaciones relativas sí**.
- La jugadora del fondo sale pequeña: prioridad a los golpes del **lado cercano**.
- Solo cinemática, no fuerzas.
- Modo **semiautomático**: el usuario revisa los golpes dudosos (umbral de confianza → cola de revisión).

## Validación y posicionamiento
- No competimos en precisión con sistemas multicámara (Hawk-Eye SkeleTRACK, laboratorios):
  el valor está en escala (muchos golpes de la misma jugadora), contexto del partido
  (marcador, presión, fatiga) y acceso (vídeo público).
- **Fiabilidad de cada métrica**: anotar a mano ~30 golpes y medir la variabilidad
  entre golpes casi idénticos (ruido de medida). Una diferencia entre condiciones solo
  se reporta si supera ese ruido. El informe muestra siempre la incertidumbre.
- **3D monocular** (tipo MotionBERT / DreamPose3D) se probará en la fase 2 solo para las
  rotaciones de cadera y hombros, que es donde el 2D es más ambiguo.

## Ampliación a otros golpes y jugadores
Lo común (cortes, audio, detección, pose, homografía, OCR, situación, informe) se escribe una vez;
lo específico vive en configuración.

- `config/players/<nombre>.yaml`: `name`, `hand` (right/left), `backhand` (one_handed/two_handed),
  `height_m`. Zurdos: se reflejan las coordenadas para que las métricas sean comparables.
  Distancias normalizadas por la altura corporal para comparar entre jugadores.
  El rival de cada partido está en los mismos vídeos: se analiza sin pasada barata nueva.
  Dobles: fuera de alcance.
- `config/strokes/<golpe>.yaml`: cómo se reconoce, sus fases y qué métricas aplica
  (funciones reutilizables de un registro común + alguna propia del golpe).

| Golpe | Reconocimiento | Métricas propias | Dificultad |
|---|---|---|---|
| Revés | Impacto en el lado no dominante (pose) | 2 manos: ambos brazos; 1 mano: extensión, hombro trasero | Baja |
| Resto | Primer golpe del que no saca | Como derecha/revés + situación "resto" | Baja |
| Saque | Primer impacto tras silencio, en la línea de fondo, brazo levantado | Trofeo, rodillas, inclinación de hombros, altura de impacto, aterrizaje | Media (se ve muy bien) |
| Volea | Cerca de la red, sin bote, swing corto | Split step, amplitud del swing, altura de impacto | Media-alta (pocos casos) |
| Smash | Impacto por encima de la cabeza fuera del saque | Como el saque | Media (pocos casos) |
| Cortado | Trayectoria de la muñeca de arriba abajo | | Media |

Orden previsto: revés de Rybakina → rival de cada partido → saque → volea/smash → lado lejano
(siempre con menos detalle: tipo de golpe, posición, apoyo aproximado).

**Regla de código desde la fase 1:** nada de "brazo derecho" o "pie izquierdo" en las métricas;
se usa "brazo dominante", "pie adelantado", etc., resueltos con la configuración del jugador.

## Fases del proyecto
0. Entorno + medir fps reales de inferencia en este equipo (`scripts/benchmark.py`).
1. Prototipo 1 partido, solo lado cercano: lista de derechas con vídeo y pose, con la
   estructura incremental por partido desde el principio.
2. Métricas, situación del golpe e informe básico + validación de fiabilidad + prueba de 3D monocular.
3. Los 4 partidos + OCR de marcador y contexto: comparativas, fatiga, presión.
4. Otros golpes y jugadores (orden de la sección de ampliación); lado lejano con menos detalle;
   opcional: seguimiento de bola.

## Stack decidido (fase 0)
- `uv` con `pyproject.toml` y `uv.lock`. En Windows se instala `onnxruntime-directml`
  (override de la dependencia `onnxruntime` de rtmlib); en el resto, `onnxruntime`.
- Pose con **rtmlib** (YOLOX + RTMPose en ONNX), formato **Halpe26** (incluye pies).
  `tennisbio.pose.estimator` crea las sesiones en `dml`, `cpu` u `openvino`.
- Vídeo con ffmpeg por tubería (`tennisbio.io.video.read_frames`). Si la fuente es
  entrelazada: a resolución completa se desentrelaza a un fotograma por campo
  (`yadif=1`); en lecturas reducidas no se desentrelaza.
- Tests: `uv run pytest`.

## Convenciones
- Código en inglés (nombres, docstrings); comunicación y docs para el usuario en español.
- Cada etapa del pipeline es un comando CLI idempotente que lee/escribe en
  `C:\tenis\output\<match_id>\` (parquet/JSON), para poder relanzar etapas sueltas.
- Jugador y golpe son parámetros (`config/players/*.yaml`, `config/strokes/*.yaml`), nunca constantes.
- Antes de escribir mucho código, enseñar el plan y esperar confirmación.
