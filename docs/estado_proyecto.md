# Estado del proyecto y contexto para continuar

Este fichero lo mantiene Claude: resume lo hecho, lo decidido con el usuario y lo pendiente, para que
cualquier sesión (en la nube o en el PC) continúe sin perder nada. Los requisitos del usuario y el
plan están en `CLAUDE.md`; la taxonomía en `docs/matriz_cobertura.md`; las validaciones en
`docs/validacion.md`; la revisión de errores en `docs/revision_completa.md`.

## Cómo se trabaja (acordado con el usuario)
- El usuario **no revisa datos, no lee documentos, no copia registros**: todo automático.
- En el PC solo hace doble clic en `1_instalar.bat`, `2_prueba_rapida.bat`, `3_analisis_completo.bat`.
- **Registros del PC → Claude, automáticos:** cada script sube al terminar (o al fallar) sus
  registros a la rama **`pc-logs`** del repositorio (carpeta local `C:\tenis\registros`):
  `instalacion.log`, `prueba_rapida.log`, `analisis_completo.log`, `equipo.txt` (CPU, gráfica,
  RAM, disco) y `partidos/<id>.log` + manifiestos y errores de cada partido.
  Para leerlos desde cualquier sesión: `git fetch origin pc-logs && git show origin/pc-logs:instalacion.log`
  (o `git log origin/pc-logs` para ver cuándo se subieron).
- Código y documentación se desarrollan en la rama `claude/tennis-biomech-setup-jggqb0`. En el PC el
  proyecto está clonado con Git en `C:\tenis\tennis-biomech` y `1_instalar.bat` hace `git pull`.
- El partido completo (los 4 partidos) se ejecuta **una sola vez, al final**, cuando todo funcione.
- Móvil y nube: al final, después de que el PC funcione.

## 19-10: la ropa vuelve a contar en la identidad (etapa `identity` v5)
- Problema (partidos completos): la ropa no decidía nunca (`by_clothes` = 0 en los 4; confianzas 0,50-0,64).
  La apariencia era el histograma de la caja entera (casi todo pista) y el k-means se sembraba con los dos
  planos más raros.
- Ahora (`tennisbio.clothes`): la etapa vuelve a leer del vídeo hasta 6 fotogramas por plano (los más quietos,
  con el torso visto) y mide solo la **camiseta** (hombros-caderas) y el **pantalón/falda** (caderas-muslos),
  quitando los colores de la pista que la rodea; tono para lo que tiene color y claridad relativa a la pista
  para blanco/gris/negro (robusto a sol/sombra). Por plano, mediana de los fotogramas. Reparto en dos personas
  con 2-medoides exhaustivo (sin semillas atípicas) y margen por plano; la jugadora lejana, cuando el detector
  la ve en los mismos fotogramas, entra como pareja «no puede ser la misma».
- Fusión con los cambios de lado: de acuerdo → «ropa y cambios de lado»; en desacuerdo gana el saque visto en
  ese plano, si no la ropa con margen claro («ropa (corrige el marcador)»: un juego mal leído), si no «dudoso»
  (fuera de comparativas, no se borra). Resumen: `agree`, `ends_only`, `clothes_only`, `ends_won`,
  `clothes_won`, `doubtful`, comprobaciones (`clothes.same_game_same`, `clothes.far_opposite`, `separation`).
  Sin vídeo, vuelve a la apariencia antigua de la caja entera.
- Comprobado en 20 clips reales de RacketVision: misma persona (dos mitades del clip) mediana 0,11 frente a
  0,53 con la jugadora del otro lado. Pendiente: ver los números en los 4 partidos (`identity` se recalcula sola).

## 17-10: decisiones y orden de trabajo (leer primero)

- **Nada en la nube y nada de pago** (decisión del usuario). La aplicación profesional es local: `docs/arquitectura_producto.md`, sección «Decisión del usuario». El móvil recibe una copia del informe autocontenido, sin servidor.
- **No lanzar los 4 partidos** hasta que el usuario lo pida.
- **Orden pedido:**
  1. Rehacer «Sus pies en este golpe» (fotogramas reales) y la estroboscópica («El recorrido del brazo», plegada como extra). Hecho el 17-10.
  2. Huecos 1-6 de la guía de Ivanovic que aplican: `docs/comparacion_guia_ivanovic.md`, sección 3.
  3. Higiene de la aplicación: huella del vídeo por contenido, huella de código en todas las etapas, CI, liberar `_poc*`.
- **«Cópiala» como lección** (17-10, aprobado por el usuario sobre `docs/maqueta_leccion_armado.html`): pasos de 8 fases + pies; su vídeo en bucle de la fase con las marcas (`learn.LESSON`: hand / lines / heights / base); como mucho 3 claves fiables por fase con su valor, «Tu objetivo», cambio por velocidad de bola (solo si supera dispersión y error), cómo, ejercicio y «Cómo comprobarlo» (`learn.CHECKS`). La lista completa de medidas sigue, plegada («4 · Todas las medidas»).
  **Lista de comprobación (la valida Claude, no el usuario):** vídeo primero; ≤ 3 claves por fase, cada una con valor suyo y nº de golpes (nunca ruido/sesgo); cómo + ejercicio + comprobación; diferencias solo sobre el error; la lección ≤ 1400 px a 1280×900 y sin scroll lateral a 390 px; nada borrado; sin errores de página. Automático en `tests/test_learn_web.py::test_lesson_meets_the_requirements` y en el PC (`learn_check.check_lesson` → auditoría: «La lección…» y «La lección enseña su vídeo de cada fase»). Después, revisar la captura real `capturas_prueba/pantalla_1_aprende.jpg`.
- **El ciclo del PC se lanza sin ventanas** (`oculto.vbs`, ciclo v4): antes aparecía un terminal cada 10 min.

## Lo último (13-10, tarde): leer primero
- **Vídeo entero (`_poc9_largo`, 15-10; pasada fina v16):** 210 min, 129 golpes confirmados, 69 derechas (55 cercanas).
  La auditoría daba 18 «no cumplidos» por 4 causas, corregidas en origen:
  1. *Superficie*: el partido la sabía («dura» por el nombre del vídeo) pero no se guardaba en los golpes. Ahora cada
     golpe lleva `surface` (pantalla del golpe: «Pista»); las pruebas toman rival/torneo/superficie de la entrada de
     `config/matches.yaml` de su vídeo (`catalog.trial_match`; se recuerda en `<partido>/partido.json`) o de
     `--surface` (`prueba_rapida.ps1 -Superficie`).
  2. *Dirección del golpe / bola subiendo*: «Su derecha» solo enseñaba un factor con **dos** niveles de ≥ 12 golpes
     (hacía falta algo con qué comparar). «al centro» (15) y «bola subiendo» (27) eran los únicos: ahora un nivel con
     ≥ 12 golpes se describe siempre; si es el único, se marca «no comparado» (`compared: false`) y no se buscan efectos.
  3. *763 km/h*: el bote de una derecha estaba 8,7 m delante de ella 3 fotogramas antes del impacto (no era el bote de
     la bola que recibe) y el golpe de la rival, cortado a 1 m, caía muy detrás de la pista. `ball3d.flights` ya no mide
     nada de un bote imposible de alcanzar a tiempo, exige el golpe rival dentro de su zona y deja sin medir la velocidad
     fuera de 15–240 km/h (`limits.BALL_INCOMING_KMH`, el mismo límite que la auditoría).
  4. Petición nueva `accion: informe` + `carpeta: _poc9_largo` (`ciclo_automatico.ps1`): medidas desde las cachés,
     informe y auditoría de esa carpeta (`recompute_measures.py --out-name`), registro en
     `output\prueba_poc9_largo_informe.log`.
- **Velocidad cerrada (decisión del usuario, 14-10 noche):** prueba 7 (`_poc7_35`): pasada fina 46,3 min (antes
  62,5) con la bola en la CPU en paralelo; 61 min de etapas para 35 min de vídeo ≈ **6 h por partido** (13-10: ~25 h).
  Lo que queda (pose más ligera, raqueta FP16, menos resolución o sin golpes del lado lejano) pierde calidad:
  **no se toca**. Modelos de partida: TransNetV2 + cámara por líneas, YOLO11m-pose FP16, híbrido con RTMPose-x,
  TrackNetV3 (iGPU + CPU), raqueta de RacketVision FP32. Petición 9 (`accion: largo`; la 8 la ignoró el ciclo, que aún corría con su script anterior): el vídeo entero en
  `_poc9_largo` (una noche) para tener golpes suficientes por situación y el tiempo real de un partido.
- **Orientación del pie: causa y método nuevo (14-10, noche; pasada fina v15):** las lecturas imposibles (20-44 %) se agrupan en −90° (8 de 13 pies de delante en el armado): la punta, tapada por el talón y la pierna al verla por detrás, la dibuja el modelo del lado de la cámara. La homografía con el talón unos cm sobre la pista solo resta 8-25° (haría falta un talón 11-17 cm más alto que la punta). Ahora (`footpoints.foot_reading`): talón bajado a la pista antes de la homografía, longitud del pie según su altura, mediana de ±0,04 s y rechazo de la punta detrás del talón («punta_oculta»; `technique.feet_check` dice por qué falta cada una). La fiabilidad cuenta los rechazos como lecturas imposibles (si pasan del 15 % sigue «sesgo», es decir, «no fiable desde la tele»). Las series guardan los puntos de los pies (`feet`, `feet_conf`): con la próxima ejecución se ve cuántos golpes quedan medidos.
- **Umbrales nuevos con golpes reales (14-10, prueba 6: `_poc6_35` frente a `_poc5_35`/`_poc4`, y `_smoke` recalculado):**
  - *Giro de hombros al empezar la preparación* («ruido» ±3,4° en la revisión): no es un fallo. Cambia por la escala
    de altura por la pista: la anterior seguía el largo del tronco en la imagen (variaba ±9 % dentro de una ventana
    con la postura) y repartía los golpes (26-67°, ±10,5° entre golpes); con la pista (±2 %) 7 de 10 derechas leen
    19-23° (±1,8°) y mover el instante 1-2 fotogramas lo cambia ±3,4° (en ese instante el giro empieza). Sus golpes
    no difieren más que el instante: «ruido» es honesto (con los 13 golpes de la prueba 6 sale «fiable»; lo
    decidirán más golpes). El giro en el armado sigue fiable (prueba 6: ±2,4° entre fotogramas frente a ±7° entre golpes). Umbral sin cambios.
  - *Pies:* el pivote (talón de atrás) tomaba la referencia en el armado; las 6 derechas con armado 0,36-0,6 s antes
    del impacto (en carrera, pasos de ajuste después) daban «no» y 5 de las 6 con armado a 0,14 s daban «sí».
    Ahora la referencia es como mucho 0,2 s antes del impacto (`footpoints.PIVOT_REF_S`; los pivotes medidos van de
    −0,06 a +0,02 s). La orientación del pie apunta hacia su propia valla (< −45°, imposible con el pie apoyado) en
    el 20-44 % de las lecturas (armado y impacto) y en 7 de 8 pies de delante del revés: la fiabilidad la daba
    «fiable» porque la dispersión es enorme (±41-52°). Ahora una medida con más del 15 % de lecturas imposibles es
    «sesgo» (`reliability.PLAUSIBLE`) y no se da ni en «Aprende» ni en «Su derecha» (que tampoco daba como suyas
    las medidas de ruido o sesgo: ahora dice «no fiable desde la tele»). Pasada fina v14.
  - *Cámara principal por líneas:* 11,4 min (antes 30,3) pero la pista pasa de 9,5 a 9,2 min: lo perdido son 14 s
    en 8 planos cortos con un ajuste de pista flojo (0,47-0,59; el juego da ~0,8); los 29 golpes de antes siguen
    (31 ahora), mismos candidatos cercanos (73). Sin cambios.
  - *Escala de altura:* las medidas en % bajan un 10-15 % (la anterior daba su altura en el 80-87 %); el tronco y
    las piernas confirman la de la pista (0,94-1,08). Impacto al 53 % de su altura (≈ 0,97 m, cintura; IQR
    49-64 %), cadera en la espera 44 % y en el armado 42 %. Las clases de altura de bola (rodilla < 35 %, cadera
    < 50 %…) se pensaron para la altura real: ahora encajan. Los objetivos de «Cópiala» siguen teniendo sentido.
- **Bola en paralelo (14-10, tras la prueba 5):** la bola de las ventanas se calcula en la CPU en un hilo aparte
  (desde la última ventana hacia atrás) mientras la pose usa la iGPU (`fine_speed.ball_ahead`, `fine_ahead.py`);
  esperado 10-20 min menos en la prueba de 35 min. Solapes de ventanas: 0 s en la prueba 5 (no se implementa).
  La raqueta «el doble» en la prueba 5 no es del código: la 4 reutilizó cachés de `_poc4`. Detalle en
  `docs/pruebas_velocidad.md`.
- **Pasada fina en cascada (14-10):** antes de la pose, la bola de la ventana (que ya hacía falta y queda en
  caché) decide si puede haber un golpe confirmado de la jugadora (`tennisbio.fine_gate`): sin golpe de bola en
  su lado a ±0,4 s de algún candidato y, en el lado cercano, con la bola bien vista ahí, la ventana se descarta
  sin pose, raqueta ni 3D. Es condición necesaria de la confirmación actual (`fuse_with_ball`): los golpes
  confirmados son los mismos. Registro por ventana y `gate` en el resumen de `fine` (etapa versión 9).
- **Velocidad (13-10, noche):** pista (homografías reutilizadas, búsqueda vectorizada; ×3,7 en la búsqueda),
  marcador (OCR solo cuando cambia; ×3), pasada fina (proceso de raqueta persistente, lotes, una decodificación)
  y pose YOLO en FP16 (validada en el PC con `scripts/model_trials.py`: ×2,2, mismos golpes, 0,25 px). Prueba de
  velocidad pedida al PC con `config/peticion_pc.txt` (id 1, «poc»: 4 min en `_poc4` y 35 min en `_poc`, sin
  tocar `_smoke`). Prueba de modelos: RTMPose-x tiembla 2,6× menos y ve los pies. **Híbrido YOLO+RTMPose-x activado en la pasada fina (14-10)**, lado cercano
  (`fine_pass.pose_model: hybrid`, etapa `fine` v11): mismos golpes, −35 % de temblor, pies en el 99,7 %, ≈ 2× el
  tiempo de pose en esas ventanas. Los pies de la jugadora seguida llegan al análisis como `run.feet` /
  `run.feet_conf` (aún sin medidas que los usen); el lado lejano sigue con YOLO.
  tocar `_smoke`). Prueba de modelos: RTMPose-x tiembla 2,6× menos y ve los pies (híbrido YOLO+RTMPose-x en curso).
- **Pies con talones y puntas (14-10):** cuando el golpe trae `run.feet` / `run.feet_conf` (pose híbrida), el apoyo
  (abierto…cerrado), la base en la pista, los pasos y la posición salen del apoyo talón–punta (`footpoints.ground_track`;
  en fotogramas sin pies, el tobillo corregido por su desfase); nuevas medidas: orientación de cada pie en armado e
  impacto (`front_foot_angle_deg`, `back_foot_angle_deg`) y pivote sobre la punta del pie de atrás
  (`footwork.back_heel_lift`, `back_heel_lift_s`), en Cópiala (fases 3 y 5), «Su derecha» y el panel de pies. Sin
  pies todo sale igual que antes (test `tests/test_foot_metrics.py`) y Cópiala dice «sin talones ni puntas».
- **Cópiala para alguien que empieza** (13-10, 14 h): guía «Empieza aquí» (se oculta y vuelve), «Tu objetivo»
  con su número en cada medida fiable (`learn.TARGETS`; nunca de ruido o sesgo; en cm del usuario si pone su
  altura, guardada solo en su navegador), glosario (`learn.GLOSSARY`, palabras subrayadas y lista al final).
  La hoja de sesión la descartó el usuario. Siguiente: velocidad, rendimiento y algoritmia (antes del tramo largo).
- **Ciclo automático en el PC** (`scripts/windows/ciclo_automatico.ps1`, bucle `ciclo_bucle.ps1` al iniciar
  sesión + tarea de Windows de respaldo, cada 10 min): trae el código nuevo de la rama, decide qué recalcular
  (`scripts/auto_cycle.py decide`: medidas desde la caché ~20 min, informe ~2 min, o nada), revisa contra la
  ejecución anterior y sube `revision_automatica.md` (OK / REGRESIÓN / ERROR), `ciclo_arranque.txt`
  (cada arranque y por qué no hizo nada), `ciclo_vivo.txt` (señal horaria) y `ciclo_tarea.txt` a `pc-logs`.
  **No pedir al usuario que lance 2c/2d.** Tras subir código, programar un aviso (send_later ~30 min) y leer la revisión.
- **Fiabilidad de cada medida, automática** (`tennisbio.reliability`): repetibilidad con las fases movidas
  1-2 fotogramas (por fase y del golpe entero), segundo método independiente (2D frente a 3D del tronco:
  `sesgo`), medidas derivadas heredan el veredicto. Ruido o sesgo → no se da como valor suyo y la web dice por qué.
  Hoy: giro de hombros 2D (57°) frente a 3D (12°) = sesgo; cuerdas en el impacto = ruido.
- **Golpes dudosos** solo por dudas del golpe (raqueta no vista, valor descartado, espera/recuperación no
  encontradas = medidas que faltan): 1 de 10.
- **Aprende**: firma (lo que repite ≥ 75 %, solo medidas fiables), estilo en una frase (solo ≥ 50 %),
  ~65 puntos; validado en el navegador en 677 combinaciones (`learn_check`).
- **Vistas por golpe pedidas** (peticiones 114-117): la bola y ella con «cae» y medidas reales; bajar y subir
  (barras + cm, una sola curva corregida de perspectiva, cadera 38-58 %); base en la pista (m); tronco al
  terminar (en su fotograma más girado tras la terminación).
- Medidas nuevas: punta de la raqueta respecto a la cabeza, frenado de hombros (hereda el sesgo del giro),
  transferencia de peso, ritmo con la bola, codo en el armado, base al terminar, pasos cruzados
  (`footwork.crossover_steps`), máximo lag (`stroke.racket_lag_deg`), manos en la espera en toda la espera,
  raqueta a ±2 fotogramas, superficie del torneo o del nombre del vídeo.
- **Pendiente:** más golpes (un tramo largo; el usuario decide si el ciclo lo lanza de noche), velocidad
  (~15 h por partido), validar los giros del tronco con una referencia (vista lateral de entreno o clips
  anotados), los 4 partidos y móvil/nube al final.

## Estado (octubre de 2026)
Hecho y validado en la nube (ver `docs/validacion.md`):
- Pipeline completo por etapas con caché e idempotente; identidad automática (cambios de lado +
  ropa + saque); marcador por OCR; pista por homografía (comprobada cada ~8 s y en cada impacto).
- Detección de golpes con pose + bola: lado cercano P 0,73 / R 0,84; lado lejano P 0,67 / R 0,73.
- Modelo técnico completo (8 fases, ~200 descriptores, pies, ritmo, raqueta, clases y situaciones)
  con fuentes (`docs/matriz_cobertura.md`); estadística ajustada por situación y partido (OLS
  robusto + Benjamini-Hochberg); pantalla "Su derecha"; videoteca, comparar, exportación MP4/PDF.
- Casos límite de vídeo: sin audio, varias pistas, .ts con saltos, fps variables, 1080i, 4K,
  cortados, rutas con acentos, vacíos (todos probados).
- Escala: 2.400 derechas → informe en 47 s, 6 MB, carga en 2,7 s.

### Primera prueba rápida en el PC (12-10-2026)
- Equipo real: Ryzen 7 8745HS, Radeon 780M (DirectML disponible), 20 GB RAM, Windows 11, ffmpeg 9.0.2.
- Instalación: 88/88 pruebas pasan en Windows (tras arreglar ffmpeg 9, nombres en cirílico y UTF-8).
- **F3Set (Rybakina, Open de Australia 2023, 21 clips; 9 no se descargaron):** precisión 0,92,
  recall 0,65 (golpes de fondo 29/33 = 0,88; saques 1/15, no son el objetivo), derecha/revés 0,97,
  dirección 0,89, subida a la red 0,97, instante ±1 fotograma.
- **Su vídeo (final US Open 2026, retransmisión rusa, 1080p50, 210 min): 0 golpes analizados.**
  Marcador 0 lecturas (sin nombre del rival en el catálogo y el OCR no lo encontró), pista en 3 de
  11 tramos, identidad sin decidir → todo descartado; solo 2 candidatos en 4 min. **Bloqueante.**
  **Causa (imágenes de diagnóstico):** los 4 min elegidos (minuto 30) eran la previa: himno,
  bandera, entrenamientos y un resumen del partido anterior de Sabalenka contra Noskova; no había
  juego. El clasificador de planos tomaba esos planos por "cámara principal". Retransmisión de
  Eurosport con el marcador internacional (latino, legible). Arreglado: la prueba rápida busca
  sola un tramo con juego; jugadores y lectura del rival solo donde se ve la pista.
- Segunda prueba (minuto 121, un juego al saque de Sabalenka desde el fondo): marcador 48 lecturas,
  13 candidatos, pero identidad sin decidir → 0 golpes. Causa: solo se votaba cuando la cercana
  sacaba. Arreglado: si saca la del fondo, la cercana es la que resta (voto de resto).
- Velocidad: YOLO 960 en la iGPU 112 ms/fotograma (CPU 479); decodificación 1080p50 27 fps (CPU),
  40 fps (d3d11va). Estimación lineal 5,6 h por partido sin la pasada fina → ~1 día los 4. La etapa
  de jugadores domina (277 s por 4 min).

- Tercera/cuarta prueba: 10 golpes confirmados (6 derechas), identidad decidida (voto de resto).
  Pasada fina 93 → 26 s por golpe (raqueta en la iGPU en proceso aparte: el controlador DirectML
  dio un 0xC0000005 en el proceso principal). Estimación ~5 h por partido (~2 h jugadores, ~2 h
  pasada fina). Progreso por etapa con % y tiempo restante; hojas de imágenes de cada golpe.
- Revisión a ojo de los 10 golpes: derecha/revés 10/10; apoyo razonable. Corregido: "en el aire"
  (10/10 por la perspectiva al avanzar), terminación de revés, "cómo llega" = velocidad antes del
  swing (en el contacto el cuerpo se mueve 2-3 m/s por el traslado de peso). Pasos uno a uno, apoyos
  y split step NO medibles en esta retransmisión (tobillos de ~190 px a 50 fps tiemblan 0,2-1 m/s):
  se ocultan por golpe cuando un pie no se ve quieto en ≥ 40 % de los fotogramas.

### Pedido por el usuario y pendiente (después de arreglar su retransmisión)
- ✔ Lo que hace respecto a la bola en cada momento (cruza la red, bota, punto más alto; golpea
  subiendo / arriba / cayendo; `ball3d.py`) y curvas de altura sincronizadas con el vídeo (cabeza,
  cadera, mano, raqueta) con su curva típica y su franja por situación (informe: «Análisis de golpe»
  y «Su derecha»). Falta verlo con golpes reales del PC (prueba rápida).
- ✔ Auditoría automática de requisitos (`tennisbio audit`, `docs` → `pc-logs:auditoria_prueba.md` y
  `capturas_prueba/`): corre al final de la prueba rápida y del análisis completo; capturas con Brave
  (el usuario no quiere Edge ni descargas). Primera auditoría en el PC (12-10): medido y no mostrado
  (3×90°, dirección del primer paso, velocidad relativa de la raqueta, mano en el mango), dirección
  del golpe no es situación, porcentajes de < 5 golpes, lista de "no medible" incompleta (13), 2
  valores fuera de rango (codo, base); imágenes de las 8 fases en negro con pocos golpes (arreglado:
  golpes mejor captados cuando no hay típico).
- ✔ Capa de interpretación (12-10): cada frase de «Su derecha» lleva qué significa y su fuente
  (`explain.COACH`), cada fase sus claves a la vista (`PRIMARY`) y el resto plegado, «Qué mirar»
  (`PHASE_FOCUS`), cuerdas por fase, cadena cinética, primer paso y pierna trasera; resumen sacado de
  las mismas frases; frase de entrada en cada pantalla; gráficas técnicas plegadas; sin YouTube
  (requisito 6); conclusiones del Panel con el mínimo de 12 golpes. La auditoría comprueba además
  frase de entrada, enlaces externos, gráficas de más de 4 líneas y que cada medida tenga su
  explicación. `2b_prueba_media.bat`: 35 min de partido para verlo con golpes suficientes.
- ✔ Vídeos de entrenadores (12-10): 16 transcripciones analizadas (`docs/aprendido_entrenadores.md`);
  hecho: capa «Líneas», «Para copiarla», codo, transferencia de peso, empuje de piernas, aceleración
  respecto al bote, girar mientras se mueve. Pendiente de esa lista: raqueta al lado/detrás del cuerpo
  (plano), punta vs cabeza, freno de hombros, «lo que la distingue», clase de estilo, y el examen de 25
  afirmaciones sobre su derecha como validación interna (nunca en el informe), con golpes suficientes.
- ✔ Prueba rápida del 12-10 23:34 en el PC: el play funciona en Brave (también con las animaciones de
  Windows desactivadas). Auditoría: 109 cumplidos, 5 huecos sin implementar y 91 «sin golpes
  suficientes» (solo 6 derechas en 4 min): hace falta la prueba media para confirmarlos.
- ◐ Vista lateral de entrenamiento (12-10, decisión del usuario): `scripts/practice_videos.py` baja en el
  PC vídeos de entrenamiento de la jugadora (YouTube), los corta en planos, la sigue (persona más grande),
  detecta sus golpes, decide la cámara de cada uno (`practice.camera_view`) y mide en las derechas de lado
  lo que la tele no ve (`practice.side_metrics`): impacto delante de la cadera, ángulo real del swing,
  rodillas, tronco, caída de la raqueta bajo el impacto y ángulo antebrazo–raqueta (lag / casting).
  Pantalla propia y marcada en el informe («Vista lateral (entreno)»); resumen solo con ≥ 12 derechas de
  lado. Prueba rápida: 2 vídeos × 90 s; prueba media: 8 × 300 s (incremental). Falta verlo en el PC.
- ✔ Repeticiones de la cámara de fondo con el marcador visible (normales o a cámara lenta): se detectan
  porque sus pies repiten un recorrido reciente más despacio o sin sonido de impactos (`replays.py`,
  etapa candidates v7). Pendiente: usar las repeticiones de otras cámaras (laterales, frontales) de la
  propia retransmisión como vista lateral, enlazadas a su golpe en directo (así la identidad y el
  instante salen del directo y solo se miden ángulos, que no dependen de la cámara lenta).
- ✔ Vista lateral: lista elegida a mano (`config/practice_videos.yaml`) tras mirar tres fotogramas de cada
  vídeo; fuera los grabados por detrás y los de cámara lenta sin factor conocido. Clasificador de cámara
  por el cambio de anchura de hombros entre espera y armado; golpes con valores imposibles descartados.
- ✔ Auditoría (12-10): combinaciones medida × situación, cada petición del chat (sección 11), validación
  F3Set, tablas a la vista y examen interno con las afirmaciones de entrenadores.
- ✔ Prueba rápida del 13-10 00:21: vista lateral bajada y analizada sola (2 vídeos, 31 golpes), pero solo 1
  derecha medible de lado (los vídeos están más en diagonal) y las derechas de frente salían como revés.
  Arreglado: análisis reflejado cuando se le ve la cara (`practice.faces_camera`) y estimación 3D en su propio
  marco del cuerpo (RTMW3D, `practice.metrics_3d`) para lado, diagonal y frente, marcada como estimación.
  Auditoría: además, el árbol de ficheros de cada ejecución (`audit.file_tree_items`).
- ✔ Profundidad de RTMW3D (14-10): rtmlib la decodificaba con los 384 px de alto en vez de los 288 del eje de
  profundidad (salida de 576 = 2 × 288), así que las diferencias de profundidad salían × 0,75. Ahora se
  decodifica en un solo sitio (`pose.wholebody3d.decode_simcc3d`) para todo: giro 3D del tronco, mano/antebrazo
  de las cuerdas y medidas 3D de la vista lateral. Se vuelven a calcular la pasada fina (versión 12) y los
  vídeos de entreno (versión 5).
- ✔ Regla del usuario (13-10): **nunca borrar trabajo hecho**; las vistas complejas se quedan como extra y
  lo nuevo se añade. Las 4 tablas (raqueta por fase, Comparar, Explorador, Comparativas) siguen igual,
  ahora con frases encima que dicen lo importante («Tabla completa» debajo, abierta). La auditoría
  comprueba que haya frases en esas pantallas y solo avisa de tablas sin frases.
- Prueba media del 13-10 (00:49-05:52, 5 h): 35 min de partido en 251 min (≈ 25 h por partido de 3,5 h:
  players 48 min, identity 30, candidates 31, court 17, score 19, fine 103 = pose 64 + bola 27). Solo 10,6 min
  de juego en el tramo (minuto 121) → 27 golpes, 14 derechas (10 cercanas). 4 ventanas sin nadie hacían
  fallar la pasada fina (arreglado). Vista lateral: 15 derechas de lado y 33 en 3D, pero las detectadas solo
  por la muñeca caen en el armado (impacto mal situado): ahora solo se miden las confirmadas por el sonido.
  Siguiente: velocidad (prioridad) y elegir un tramo con más juego.
- ✔ Cámara principal por las líneas (14-10, etapa `scenes` v3): con TransNetV2 salían 303 planos pero 248
  «principales» (30,3 min de 35; pista solo en 9,5). El color no basta: la pared azul de fondo tiene el color de
  la pista. Ahora un plano es principal si en suficientes fotogramas (1/10 del plano, como mucho 1 s) se ven dos
  laterales que convergen hacia arriba y una línea que las cruza, sobre una superficie limpia (no público), o si
  se parece a una vista ya confirmada así. Si una retransmisión no deja ver las líneas, decide el color como
  antes. Calibrado: las 26 imágenes de `pc-logs:diag/` separadas sin error; 41 retransmisiones de
  RacketVision y el resumen de la final, todo conservado. Esperado en el tramo de 35 min: ~10-14 min de cámara
  principal (pista en 9,5). En el PC: `main_camera_min` frente a `main_camera_min_colour` y `main_rule`.
- ✔ Pista (14-10, etapa `court` v4): de los 32,7 min de «cámara principal» solo 10,6 tenían pista. Causa
  (imágenes de `pc-logs:diag/`): la pista se ajustaba bien en todos los planos de juego; los planos sin pista
  eran primeros planos (jugadora sobre el fondo azul, público) que `scenes` da por cámara principal porque no
  ve el corte (mismos colores azul/verde): 159 planos en 35 min, 127 «principales». Con un solo fotograma cada
  ~8 s, un plano que mezcla punto y primer plano perdía el punto si el fotograma caía en el primer plano (y los
  límites iban ±4 s). Ahora: un fotograma cada 2 s, el cambio pista/sin pista se sitúa por bisección a 0,5 s, un
  fotograma sin pista pero con la misma vista que su vecino (línea tapada, desenfoque) conserva la pista si aún
  puntúa ≥ 0,3, y una máscara de líneas en sombra (antes: sombra parcial → homografía 17 px desviada; sombra
  total → sin pista). Búsqueda completa como mucho cada 8 s de plano (coste parecido). El resumen de la etapa da
  `court_min` / `court_share` para comprobarlo en el PC.
- ✔ «Aprende su derecha» (13-10), pantalla principal nueva (nada borrado): eliges el golpe combinando
  condiciones (dirección, apoyo, cómo llega, efecto, lado, altura, velocidad, profundidad, contacto) → sus
  golpes exactos (o, si son pocos, los más parecidos diciendo qué condición se quita) → 8 fases + pies con
  47 puntos de control: su valor (con cuántos golpes lo respaldan) y su patrón, cómo hacerlo tú, error típico,
  ejercicio, «Ver en vídeo» en el instante de la fase; qué cambia en cada condición; plan; lo no medible.
  Contenido en `learn.py` (conocimiento de entrenadores, marcado). Los 59 puntos de la matriz del usuario
  tienen sitio (`learn.matrix_places`, auditado). Validación automática en navegador (`learn_check.py`):
  677 combinaciones (cada condición, cada pareja, el ejemplo del usuario) × 9 fichas; detecta cada rotura
  probada; en los tests (400 golpes sintéticos) y en la auditoría del PC. `2c_solo_informe.bat` (1-2 min)
  rehace web + auditoría sin analizar vídeo.
- Pendiente de la auditoría (pedido el 12-10): comprobar cada combinación medida × situación, convertir
  las 63 peticiones del chat (`docs/peticiones_usuario.md`) y las 25 afirmaciones de entrenadores en
  comprobaciones automáticas, y validar la exactitud de más medidas con clips anotados.
- El usuario no entiende el informe (12-10): rehacer la entrada con una sola pantalla que se explique
  sola, con vídeo y frases; después, aprender de vídeos de análisis de entrenadores (subtítulos e
  imágenes bajados en el PC) cómo explicarlo.

Pendiente que **solo puede hacerse en el PC**:
1. Instalación (falló la primera vez; ver `pc-logs:instalacion.log`).
2. `2_prueba_rapida.bat`: velocidad real en la iGPU (DirectML) y validación F3Set (30 puntos de
   Rybakina; YouTube bloquea la descarga desde la nube).
3. Ajustes según esos resultados; después los 4 partidos (una vez).

Limitaciones asumidas (no se "arreglan" con falsa precisión): empuñadura exacta, ruido de medida
real (sale de sus golpes en los partidos), apoyo sin validación con datos anotados (ningún conjunto
público lo anota), velocidad absoluta de la raqueta, efecto de la bola.
