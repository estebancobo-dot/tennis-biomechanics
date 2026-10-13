# tennis-biomech

Análisis biomecánico **cinemático 2D** de golpes de tenis a partir de retransmisiones de TV.
Centrado en **1 jugador y 1 tipo de golpe** por análisis, parametrizable.
Primer caso: **derecha de Elena Rybakina** en 4 partidos completos.
Después: revés, saque, volea y otros jugadores.

## Requisitos del usuario (vinculantes; resumen de todo lo pedido)
1. **Objetivo del producto:** a partir solo de retransmisiones de TV de la jugadora, responder de forma
   profesional a "¿qué hay que hacer para pegar una derecha como X?", con **todas sus variantes**
   (bola rápida/lenta, alta/baja, corta/profunda, en carrera/parada/salto, cada apoyo, dirección,
   ataque/defensa) y **toda la taxonomía del golpe**: espera, empuñadura (en espera y al golpear, si
   se puede ver), split step, primer paso, pasos y juego de pies, preparación, armado, aceleración,
   impacto, terminación, recuperación, ritmo. Que cualquiera pueda usar el golpe analizado como base.
2. **Información, no tablas:** cada pantalla dice qué hace y cómo, con vídeo real como prueba.
   Nivel de las apps profesionales (Hawk-Eye/TennisViz, Sportsbox, SwingVision): vídeo primero,
   pocos números bien elegidos. Nada de "trabajo de instituto" ni PDF enormes.
3. **Nada inventado:** todo sale de sus golpes medidos; si no hay datos suficientes o la medida no
   es fiable, no se muestra o se dice "no medible desde la tele". Las diferencias solo si superan
   el error de medida.
4. **Cuerdas / orientación de la cara de la raqueta**: obligatorio (honesto donde es estimación).
5. **100 % automático:** el usuario no revisa datos, no lee documentos, no anota, no edita
   configuración. Instalación, prueba y análisis completo con scripts de doble clic.
6. **Sin fuentes externas:** nada de vídeos del usuario, de entrenadores ni de otras jugadoras.
   **Excepción (12-10):** vídeos de entrenamiento de la propia jugadora en YouTube, filmados de lado,
   en un apartado aparte y marcado del informe («Vista lateral (entreno)», `scripts/practice_videos.py`,
   `tennisbio.practice`): solo lo que la tele no ve; nunca se mezcla con los datos de partido.
7. **Partido completo solo cuando la aplicación tenga todas las funciones:** se ejecuta una vez,
   al final. Antes, todo se construye y valida aquí con clips públicos (RacketVision, F3Set).
8. **Cobertura de casos:** nominales, límite, esquina y error en fuentes, algoritmos, modelos IA,
   procesado, rendimiento/velocidad e informe.
9. **Rendimiento:** viable en el Beelink (iGPU, sin CUDA); un partido en horas, no días.
10. **Orden:** primero la base completa de la derecha (no otros golpes); exportación hecha;
    **móvil/nube al final**, cuando todo funcione en el PC. El PC no puede ser servidor.

**Referencia de completitud:** `docs/matriz_cobertura.md` (taxonomía de la derecha con fuentes:
ITF/Elliott-Reid-Crespo, Landlinger, Knudson, Tennis Australia, estudios de pies, sistemas
profesionales). Toda medida nueva sale de ella y se marca allí; los huecos medibles se cierran.

**Estado y contexto para continuar:** `docs/estado_proyecto.md` (leerlo al empezar cualquier sesión).
**Registros del PC:** los scripts de Windows los suben solos a la rama `pc-logs`
(`git fetch origin pc-logs && git show origin/pc-logs:instalacion.log`). Nunca pedir al usuario
que copie registros. **Ciclo automático** (tarea de Windows cada 10 min, `ciclo_automatico.ps1`): trae
el código nuevo de la rama, ejecuta lo necesario (`scripts/auto_cycle.py decide`: medidas desde la caché,
solo informe o nada), revisa frente a la ejecución anterior (`revision_automatica.md`: OK / REGRESIÓN /
ERROR) y lo sube a `pc-logs`. No pedir al usuario que lance 2c/2d tras cada cambio.

## Plan vigente (en orden)
1. Corregir los fallos graves de `docs/revision_completa.md` (identidad, cara en el impacto,
   cadena cinética, medidas con escala por fotograma, ventana previa, entrelazado, robustez,
   cachés, informes).
2. Medir lo que falta de la taxonomía (sección 3 de la revisión), lo que permita la tele.
3. Estadística única en Python (ajuste por situación y partido, comparaciones múltiples).
4. Pantalla "Su derecha": selector de situación, 8 fases con fotograma real + esqueleto medio +
   claves medidas, pies, cambios respecto a lo habitual; cada dato enlaza a sus vídeos.
5. Validación automática de cada medida con clips públicos anotados.
6. Velocidad: pose en la iGPU (ONNX/DirectML), menos trabajo repetido.
7. Ejecución de los 4 partidos en el PC (una vez). 8. Móvil/nube.

## Rutas (Windows, fuera del repo)
- Vídeos: `C:\tenis\videos\` (~5 GB por partido, retransmisión completa). **Nunca a git.**
- Salidas (datos extraídos, recortes, informes): `C:\tenis\output\`.
- Repo: `C:\tenis\tennis-biomech\` — solo código y configuración.
- Las rutas se leen de `config/local.yaml` (no versionado); nada de rutas absolutas en el código.

## Equipo y restricciones técnicas
- PC (según su propio registro, `pc-logs:equipo.txt`): Ryzen 7 8745HS (8C/16T), 20 GB RAM visibles, iGPU Radeon 780M,
  Windows 11 (PowerShell 5.1), ~300 GB libres en C:.
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
   - Identidad **automática** (el usuario no revisa vídeo): la ropa del jugador cercano agrupa
     los planos en dos personas; cuando el cercano saca al empezar el punto, el icono de saque del
     marcador dice si es la jugadora objetivo (etapa `identity`). Así se siguen los cambios de lado.
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

**Vídeos de YouTube**: nunca en el informe ni como datos de partido de la jugadora (sin fuentes externas),
salvo la vista lateral de sus entrenamientos (requisito 6, apartado aparte y marcado). Solo
para que Claude aprenda cómo analizan y explican los entrenadores (`scripts/youtube_research.py`,
en el PC, una vez). Tampoco se usan clips propios del usuario (decisión del usuario).

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
  mapa de pista. Cada número enlaza a sus clips. Sin herramienta de revisión manual (100 % automático).
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

## Lecciones del primer clip real (entrenamiento US Open, móvil, 30 fps, 42 s)
- La pose (YOLO11-pose) es muy buena con la jugadora grande en imagen; la raqueta se ve
  nítida en el armado y **borrosa en el impacto**, como se esperaba.
- **Identidad**: al cambiar de plano el seguimiento saltó al entrenador → hace falta
  seguimiento por identidad (tracker + apariencia) y confirmación, no "la persona más grande".
- **Cortes y fundidos**: el clip editado tiene fundidos encadenados (dos imágenes mezcladas);
  la detección de cortes debe cubrir fundidos, no solo cortes secos.
- **Audio**: solo 4 de 18 golpes tenían un impacto de audio a ≤120 ms; el sonido estaba lleno
  de transitorios ajenos. Regla: el impacto se decide **fusionando** audio + pico de
  velocidad de la muñeca **relativo al cuerpo** (y bola cerca de la raqueta cuando se vea);
  si no coinciden, el golpe va a la cola de revisión.
- **Tipo de golpe por contexto**: el clip eran sobre todo voleas junto a la red; la
  clasificación debe usar la posición en pista además de la pose.

## Lecciones de la validación automática (RacketVision, final del US Open)
- **El golpe se decide con la bola**: solo con el pico de muñeca (sin audio) la detección daba
  F1 ≈ 0,3 (las carreras parecen golpes). Con la bola (TrackNetV3 de RacketVision) + pose:
  precisión 0,73, recall 0,84, error de instante de 1 fotograma (ver `docs/validacion.md`).
  Golpe = giro más brusco de la trayectoria tras el cual la bola se aleja (el bote gira menos y,
  en el lado cercano, la bola sigue viniendo hacia la cámara). Un giro de bola sin movimiento de
  brazo no es golpe.
- Con emisiones a 50-60 fps la bola se procesa a ~25 fps (como se entrenó el modelo).
- El audio llega 2-4 fotogramas tarde respecto al contacto visible; la bola es más precisa.
- **Repeticiones** (12-10): las de la cámara de fondo se descartan si el marcador desaparece o si sus pies
  repiten en la pista un recorrido de los últimos 90 s más despacio (cámara lenta) o sin sonido de impactos
  (`tennisbio.replays`). Las tomas de otras cámaras (laterales, frontales, primeros planos) se descartan por
  la pista visible; usarlas como vista lateral enlazada a su golpe en directo es una ampliación pendiente.
- Dobles: se detectan por homografía (dos personas dentro de la mitad cercana) y se excluyen.
- **Lado lejano**: YOLO sobre el fotograma entero (ni sobre la mitad lejana) no ve a la jugadora
  lejana (~60-90 px). Se busca en la mitad lejana ampliada y se sigue con un **recorte que la
  sigue** (4× su altura, ampliado a 640 px). Sus golpes se confirman con la bola; el análisis
  refleja la imagen (está de frente) y la pista se expresa en su propio marco (su fondo en y = 0).
  Del lado lejano solo se usan las métricas fiables a esa distancia (posición, desplazamiento,
  altura del impacto, destino del golpe); nada de cuerdas, rotaciones, apoyo ni anchura de base
  (los tobillos de una jugadora de ~70 px salen demasiado imprecisos).
- Las fases se calculan sobre la velocidad suavizada de la muñeca (a 60 fps el ruido creaba
  armados falsos a 3 fotogramas del impacto).
- Derecha/revés por votación (lado de la muñeca en el armado, dirección del swing, lado en el
  impacto): un solo fotograma de impacto desplazado invertía la clasificación.

## Limitaciones asumidas (no "arreglarlas" con falsa precisión)
- 2D desde una sola cámara; cualquier 3D es estimación.
- Desenfoque en el impacto a 25-50 fps: velocidades absolutas no fiables, **comparaciones relativas sí**.
- La jugadora del fondo sale pequeña: prioridad a los golpes del **lado cercano**.
- Solo cinemática, no fuerzas.
- **100 % automático** (decisión del usuario): nadie revisa golpes; los dudosos se marcan en el informe, no se piden.

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
- Bola y raqueta con los pesos oficiales de **RacketVision** (MIT), reimplementados en PyTorch
  puro y exportados a ONNX: `scripts/export_balltrack.py` (TrackNetV3, bola) y
  `scripts/export_racketpose.py` (RTMPose-m, 5 puntos de la raqueta). Sin mmpose/mmcv.
- Homografía de la pista desde las líneas (`tennisbio.court`): da la inclinación de la cámara
  y las posiciones en metros (apoyo, anchura de base, desplazamiento, posición en el impacto).
- Marcador de TV con OCR (`rapidocr-onnxruntime`, extra `ocr`; `tennisbio.scoreboard`): sets,
  juegos, puntos y presión (30-40, 40-30, iguales, ventaja, tie-break, rótulos "BREAK POINT").
- Rotación 3D de hombros/cadera (X-factor 3D) con RTMW3D, reutilizando la pasada de la mano.
- Etapas: probe → scenes → audio → players → candidates → court → score → fine. La pasada fina
  guarda por golpe `strokes.json` y series fotograma a fotograma (`series/`) para el informe.
- Informe: `tennisbio report` → `<output>/informe/index.html` (diseño de la maqueta, vídeo real
  de cada ventana con el esqueleto superpuesto; los datos que faltan se muestran como "—").
- Tests: `uv run pytest`.

## Convenciones
- Código en inglés (nombres, docstrings); comunicación y docs para el usuario en español.
- Cada etapa del pipeline es un comando CLI idempotente que lee/escribe en
  `C:\tenis\output\<match_id>\` (parquet/JSON), para poder relanzar etapas sueltas.
- Jugador y golpe son parámetros (`config/players/*.yaml`, `config/strokes/*.yaml`), nunca constantes.
- Antes de escribir mucho código, enseñar el plan y esperar confirmación.
- **Nunca borrar trabajo hecho** (vistas, medidas, pantallas): lo complejo se queda como extra y lo
  nuevo se añade encima (decisión del usuario, 13-10).
