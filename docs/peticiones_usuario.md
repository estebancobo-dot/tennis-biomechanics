# Peticiones del usuario frente al código y a la web

**Revisión:** 13-10-2026 (tarde; filas 76, 98, 101-112 y 118-125 al día), antes commit `a330935` (rama `claude/tennis-biomech-setup-jggqb0`).
**Fuentes revisadas:** los 147 mensajes del chat (10-10 a 13-10; sin contar los resúmenes de contexto, los
registros ni los informes de subagentes pegados), `docs/aprendido_entrenadores.md` (las 15 mejoras),
`docs/matriz_cobertura.md` §6 (la matriz de 15 secciones, 59 filas) y la revisión anterior de este documento.
**Datos reales usados:** la última ejecución del PC (`origin/pc-logs`, 13-10 08:24, ya con `a330935`):
27 golpes, de ellos **10 derechas del lado cercano**, 4 golpes con error, 10 de 14 «con dudas».
También la auditoría (`auditoria_prueba.md`) y las capturas de las 10 pantallas (`capturas_prueba/`).
Las horas de los mensajes van en UTC.

**Criterio.** HECHO solo si está en el código, se llega a ello en la web (o es un script o proceso que
existe) y los datos reales no lo contradicen. PARCIAL si está hecho pero no se ve o no sirve con los datos
reales, o si está a medias. NO si no está. Se mantiene la numeración 1-63 de la revisión anterior, porque
`audit.PETITIONS` la usa. Las filas 64-113 son nuevas y todavía **no tienen regla en `audit.PETITIONS`**:
la auditoría las marcará «sin comprobación automática asignada».

| Estado | Nº |
|---|---|
| HECHO | 73 |
| PARCIAL | 42 |
| NO | 6 |
| NO APLICA | 4 |
| **Total** | **125** |

**Al día (13-10, tarde).** Web en 2 vistas («Cópiala», «Sus golpes») y «Más»; cada medida validada sola
(técnica, ruido o sesgo); ciclo automático en el PC con revisión OK/REGRESIÓN/ERROR; golpes dudosos 1 de 10.
Lo que sigue limitando: 10 derechas (casi todo provisional) y la velocidad (≈ 15 h por partido).

**Resumen honesto (de la revisión anterior).** El conocimiento del chat **sí está en la web**, pero solo en una pantalla: «Aprende su
derecha» (`learn.py` + `renderLearn`). Es la pestaña de entrada. Tiene 8 fases más los pies; cada punto lleva
el valor de ella, «Cómo hacerlo tú», el error típico y un ejercicio. Las condiciones se pueden combinar y cada
punto de la matriz tiene su sitio.

Con los datos reales, en cambio, **casi todo es provisional**:
- Hay 10 derechas, y la pantalla necesita 12 golpes para dar un valor firme.
- Al combinar condiciones, la pantalla relaja todas las condiciones y vuelve a usar las 10 derechas.
- «Qué cambia» es texto genérico de entrenador, no lo que ella cambia.
- «Su derecha» sale vacía.
- 0 de las 2.992 combinaciones de medida y nivel de situación se muestran.

La velocidad (5 h para 10 derechas) y los golpes dudosos (71 %) siguen sin resolver.

## Tabla de peticiones

Abreviaturas: Aprende = «Aprende su derecha» · SuD = «Su derecha» · AG = «Análisis de golpe» · VL = «Vista
lateral (entreno)» · ≥12 = solo se muestra con 12 golpes o más (`model.MIN_N`, `A_MIN`).

| # | Petición (paráfrasis, fecha del mensaje) | Estado | Dónde está (código) | Dónde se ve en la web | Cómo se valida solo | Qué falta |
|---|---|---|---|---|---|---|
| 1 | Derecha de Rybakina en sus 4 partidos completos, una vez y al final (10-10 17:27; 11-10 19:37) | NO (pendiente por diseño) | `3_analisis_completo.bat` → `analisis_completo.ps1` | — | `audit` tras el análisis completo | Ningún partido completo analizado. |
| 2 | Ver informe y salidas en el móvil (11-10 18:21, 18:29, 18:33) | NO (aplazado por el usuario) | `viewport` y `@media` en `report_template.html` | — | — | Nada lleva el informe al móvil. |
| 3 | Nube / OneDrive sin usar el PC como servidor (11-10 18:26-19:01) | NO (aplazado por el usuario) | — | — | — | Se hará al final. |
| 4 | Responder de forma profesional a «¿qué hay que hacer para pegar como X?», con todas las posibilidades y como base para cualquiera (11-10 19:23) | PARCIAL | `learn.PHASES`, `FEET`, `CONDITIONS`; `renderLearn`; `explain.copy_cue`/`COACH`/`PHASE_FOCUS` (SuD) | Aprende §1-6 (pantalla de entrada); SuD | `learn_check.check_page`: 677 combinaciones y 31.819 puntos de control; ítem «Aprende su derecha» | Valores de 1 a 10 golpes, todos «provisional». SuD, `copy_cue` y `COACH` no se ven (≥12). |
| 5 | Taxonomía completa con todas las variantes (bola rápida/lenta, alta/baja, corta/profunda, carrera/parada/salto, apoyo, dirección, ataque/defensa) (10-10 18:05; 11-10 19:23, 19:48; 12-10 06:32) | PARCIAL | `technique.DESCRIPTORS`/`classes`; `model.FACTORS`; `learn.CONDITIONS` (10 condiciones) | Chips de Aprende §1 con recuento por nivel | Auditoría §1: «cada medida en cada nivel» | 0 de 2.992 combinaciones con ≥12. Niveles vacíos: parada 0, paralela 0, rodilla 0, en el aire 0. |
| 6 | Juego de pies: split step, primer paso, ajuste, reacción, recuperación (11-10 08:22, 19:23) | PARCIAL | `footwork.py`; `learn.FEET` y fase 8 | AG «Sus pies en este golpe» (9 líneas y mapa); tarjeta «Pies» de Aprende | Auditoría §1 «3. Pies…» y «Sus pies en este golpe» | Pasos medidos en el 40 % de los golpes. El golpe capturado dice «no medible» en el primer paso, el ajuste y tras golpear. |
| 7 | Empuñadura en la espera y al golpear (11-10 19:23) | PARCIAL | `explain.grip_compatible`; `class.ready_hands` | Aprende fase 1 «Manos en la espera»; la «compatibilidad» solo en SuD (≥12) | Auditoría §3 (no medible dicho) | El bisel no se mide. `ready_hands` da «mano libre separada» en el 100 % (7 golpes) y en revés a dos manos, contra R2 de los entrenadores: medida dudosa. La lista no medible de Aprende no nombra la empuñadura. |
| 8 | Cuerdas y cara (suelo, valla lateral o trasera, ángulos, cierre muñeca–raqueta) en todas las fases. Obligatorio (11-10 07:34-09:58) | PARCIAL | `racket3d.describe_face`, `racket_face.face_track`, `stroke_faces` | AG «Raqueta por fase» y HUD «CUERDAS → RED»; Panel (conclusiones); Aprende solo `impact.face_tilt` | Auditoría §4: cara en el 50-100 % según la fase | En el impacto es interpolada («red» en el 100 %). Aprende no dice adónde apuntan las cuerdas en el armado ni en la caída. |
| 9 | Información, no tablas; profesional, «con sentido humano», nivel de las apps punteras (10-10 18:09-18:47; 11-10 18:06-19:23; 12-10 16:22-17:21) | PARCIAL | `learn.py`; frases en AG, Comparar, Explorador y Comparativas | Aprende (23.684 caracteres, 11 frases) | `screens.py` (frases, tablas, gráficas de muchas líneas) | SuD vacía. Comparativas: 8 «Sin datos…». Explorador: 41 «—». El 13-10 05:48 el usuario dice que «no vale para nada». |
| 10 | Ver los cambios en la prueba rápida, sin 1 h (12-10 17:32, 17:40) | PARCIAL | `2c_solo_informe.bat` (2 min 26 s) | Toda la web | `solo_informe.ps1` → auditoría y capturas | Una medida nueva exige volver a analizar el vídeo: la prueba media dura 5 h 02 min. La prueba rápida deja unas 5 derechas. |
| 11 | Validar solo que las salidas reales tienen todo lo pedido y todos los casos del modelo y la taxonomía (12-10 13:14, 16:36, 17:10; 13-10 05:48 p1-2) | PARCIAL | `audit.py` (11 apartados), `learn_check.py`, `screens.py` | — (sale en `auditoria.md` en `pc-logs`) | 164 ✔ · 1 ✘ · 154 «sin golpes suficientes» | Comprueba que la estructura existe, no que el valor sea correcto. Las peticiones 64-113 no tienen regla. |
| 12 | Validar cada medida con clips públicos anotados; el usuario no valida a mano (11-10 09:05, 09:12) | PARCIAL | `validate_f3set.py`, `validate_rv_strokes.py`, `validate_racket.py` | — | F3Set: P 0,917 / R 0,647; derecha/revés 0,969; dirección 0,885 | Ninguna medida corporal (codo, rodillas, pasos, apoyo, fases) está validada. |
| 13 | Casos nominales, límite, esquina y error en fuentes, algoritmos, IA, procesado, rendimiento e informe (11-10 19:23) | PARCIAL | `tests/` (117 pasan y 1 se salta en el PC: la prueba del navegador) | — | `pruebas.log` en `pc-logs` | Ningún partido completo. En la última ejecución, la etapa `fine` falló en 4 golpes. |
| 14 | Rendimiento: un partido en horas, no días (12-10 13:09) | NO | ONNX/DirectML, `progreso.json` | — | Auditoría §9 (aviso) | Medido: 251 min para 35 min de vídeo, unas **25 h por partido**. |
| 15 | Bajar y analizar vídeos de entrenadores de YouTube para aprender y encontrar huecos (12-10 16:30-17:51) | PARCIAL | `scripts/youtube_research.py`; `docs/aprendido_entrenadores.md` | Aprende (consignas, errores, ejercicios); capa «Líneas» en AG | Auditoría §6: 24 vídeos, 16 con texto | 6 de las 15 mejoras siguen en NO o a medias (filas 99-113). |
| 16 | Distinguir por contexto (derecha junto a la red o volea) y cubrir las medias voleas (10-10 18:05; 11-10 09:02) | PARCIAL | `class.contact_type` (media volea, volea) | Aprende, condición «Contacto» | Auditoría «Botepronto», «Volea» | Ningún caso en los datos (0 y 0). La volea no tiene técnica propia. |
| 17 | Una entrada que se entienda sola: «no entiendo nada ni cómo usarla» (12-10 16:22) | PARCIAL | `showTab` → `aprende` por defecto | Aprende (pasos 1-6) | Ítem «Pantalla «Aprende su derecha»» | La segunda pestaña (SuD) está vacía. Aprende y SuD se solapan. Las «Novedades» están en SuD. |
| 18 | Herramienta Python cinemática 2D, 1 jugador y 1 golpe, parametrizable (10-10 17:27) | HECHO | `config/players`, `config/strokes`, `cli.py` | Cabecera «Diestra · revés a 2 manos» | «golpes analizados» | |
| 19 | Vídeos y salidas fuera del repo, rutas por configuración (10-10 17:27) | HECHO | `config/local.yaml`, `config.py` | — | «Cada golpe tiene su vídeo» | |
| 20 | Windows nativo sin NVIDIA ni WSL, ONNX en CPU o DirectML (10-10 17:27) | HECHO | `pose/yolo_onnx.py`, `estimator.py` | — | `instalacion.log` (DmlExecutionProvider) | La lentitud está en la fila 14. |
| 21 | Dos pasadas, barata y fina de ±1 s (10-10 17:27) | HECHO | `stages.py` | — | Ficheros de etapa | |
| 22 | Solo la cámara principal, sin repeticiones ni primeros planos (10-10 17:27) | HECHO | `scenes.py`, `replays.py` | — | `tests/test_scenes.py`, `test_replays.py` | |
| 23 | Seguir a la jugadora en los cambios de lado (10-10 17:27) | HECHO | `identity.py`, `st_identity` | — | `test_identity.py` | Sin validar con datos anotados. |
| 24 | OCR del marcador y presión (10-10 17:27) | HECHO | `scoreboard.py` | Ficha de AG «2 · 5-5 30-30»; filtro de presión | «Presión, set, fatiga» | |
| 25 | Métricas por derecha: apoyo, base, rodillas, cadera, hombros, X-factor, codo, impacto, cadena, pista (10-10 17:27) | HECHO | `technique.py`, `court_metrics.py`, `phases.py` | AG «Métricas»; Aprende | Auditoría §1 | X-factor 2D: mediana de 1° en Aprende, sospechoso (fila 113). |
| 26 | Fases y cadena completa, del salto inicial a la terminación (10-10 17:27; 11-10 08:22) | HECHO | `technique.PHASES` (8) | AG, tira de 8 fotogramas; Aprende, 8 fichas | «Fotograma clave» en el 100 % de los golpes | |
| 27 | Agregados por partido y set, fatiga, ganadores y errores, presión (10-10 17:27) | HECHO | `findings._pairs`, `model.py` | Panel: «Hallazgos», «Evolución durante el partido» | «Presión, set, fatiga» | Con 1 partido y 10 golpes, todo «No concluyente». |
| 28 | Informe HTML con gráficos y esqueleto (10-10 17:27) | HECHO | `report.py`, plantilla | AG | «Cada golpe tiene su esqueleto» 10/10 | |
| 29 | Fase 0: entorno y fps reales, con YOLO (10-10 17:27; 11-10 08:49) | HECHO | `check_env.py`, `benchmark.py` | — | `instalacion.log` | |
| 30 | Estado del arte: igual, mejor o peor que otras apps (10-10 17:40; 11-10 09:05, 18:06) | HECHO | `docs/comparativa_apps.md` | — | (documento) | La profundidad se discute en la fila 74. |
| 31 | Procesado incremental al añadir vídeos (10-10 18:05) | HECHO | `pipeline.py` (huellas), `auto_catalog.py` | — | `test_pipeline.py` | |
| 32 | Ampliable a otros golpes y jugadores (10-10 18:07) | HECHO | `config/strokes/*` | — | (configuración) | |
| 33 | Capturas de los mejores golpes de cada tipo y N imágenes de un golpe (10-10 18:12) | HECHO | 8 fotogramas clave, estroboscópica, orden de la videoteca | AG, Videoteca | «Fotograma clave» | |
| 34 | Maqueta con datos inventados, con apoyos (10-10 18:13; 12-10 17:21) | HECHO | `docs/maqueta-informe.html` (filtro y mapa de apoyo) | — | (documento) | |
| 35 | Medidas de la raqueta (altura, ángulos) en todo el golpe; qué miden los profesionales (11-10 07:34) | HECHO | `racket_head_vs_wrist`, `racket_angle`, `racket_track` | AG «Raqueta durante el golpe» y «Raqueta por fase» | Auditoría §4 | Impacto borroso (se marca). |
| 36 | Mano y antebrazo, cierre de la muñeca (11-10 09:56, 10:19) | PARCIAL | `acceleration.racket_forearm`, `hand_on_handle` | Aprende «Retraso de la raqueta» | «Retraso de la muñeca (lag)» | El lag sale en el 40 % de los golpes y Aprende lo da con **1 golpe**. |
| 37 | Prueba en local sin procesar 20 GB (11-10 09:02) | HECHO | `2_prueba_rapida.bat`, `2b_prueba_media.bat` | — | Auditoría tras la prueba | |
| 38 | Dirección y profundidad del golpe (11-10 17:24) | HECHO | `court_metrics.shot_landing` | AG ficha (bote, dirección); Pista «Destino» | «Dirección…» 70 %, «Bote» 90 % | |
| 39 | Lado del fondo de la pista (11-10 17:32-17:33) | HECHO | `extract_follow`, `report.FAR_OK` | Cabecera «4 desde el fondo» | «golpes analizados» | |
| 40 | Scripts de instalación, uso rápido y completo, sin leer nada (11-10 18:06, 18:21) | HECHO | `1_instalar.bat`, `2_*.bat`, `2b`, `2c`, `3_*.bat` | — | `instalacion.log` | |
| 41 | Exportación: cómo se ven y se graban (11-10 18:06; 19:01 «haz el punto 4») | HECHO | `export.py` | — | «Exportación: resumen PDF y un vídeo por golpe» (14 vídeos, 8 montajes) | |
| 42 | Un golpe no son 8 pantallazos: vídeo y más (11-10 18:21) | HECHO | Vídeo con capas, curvas, «La bola y ella», Comparar | AG, Comparar | «Reproducir…» 5/5 | |
| 43 | El PC no es servidor (11-10 18:27) | HECHO | HTML sin servidor | — | (arquitectura) | |
| 44 | Sin vídeos del usuario, de entrenadores ni de otras jugadoras (11-10 19:37), salvo su entrenamiento (12-10) | HECHO | Sin entradas externas; entrenamiento en `practice.py` | VL, aparte y marcada | «Enlaces externos» 0 | |
| 45 | Todo automático y completo: el usuario no revisa nada (11-10 09:05, 19:38; 12-10 11:41) | PARCIAL | Identidad automática, `auto_catalog.py` | Chip «con dudas» | «Nada pide revisión manual» ✔; **«Etapas con errores: fine» ✘** | 4 golpes fallaron (`strokes_errores.json`) y nadie los recupera. |
| 46 | Sin PDF enorme y sin inventar datos (11-10 19:40) | HECHO | `limits.py`, «—» si falta el dato | PDF de 6 páginas (0,8 MB) | «Resumen PDF», «Valores dentro de límites» | |
| 47 | Modelo técnico con fuentes; cómo saber si está completo (12-10 06:32) | HECHO | `docs/matriz_cobertura.md`, `audit.parse_matrix` | — | Auditoría §1 | |
| 48 | Posición de la cabeza y altura del cuerpo al inicio y al final (11-10 19:48) | HECHO | `head_motion_cm`, `body_height`, curvas | AG «Alturas durante el golpe» y capa «Alturas» | «Curvas de altura», «Cabeza estable» | Cabeza quieta: 2 golpes en Aprende. |
| 49 | No perder contexto ni sesión; registros automáticos (12-10 11:39-11:45) | HECHO | `comun.ps1` → `pc-logs`; `estado_proyecto.md` | — | (proceso) | |
| 50 | Progreso y monitorización visibles (12-10 14:37, 14:43) | HECHO | `progreso.json`, salida sin búfer | — | Registros con hora | |
| 51 | El código de la prueba es el de los casos reales (12-10 14:37) | HECHO | Las mismas etapas sobre `_smoke` | — | (proceso) | |
| 52 | Brave, no instalar Edge (12-10 16:48) | HECHO | `screens.py:52-71` (Brave primero, nunca descarga) | — | Capturas con el navegador instalado | |
| 53 | No pasar de 100 a 0: conservar lo anterior (12-10 17:21) | HECHO | 10 pestañas | Todas | «Pantallas» | |
| 54 | Qué hace ella cuando la rival golpea, la bola cruza la red, bota y llega arriba (12-10 17:40) | HECHO | `report.ball_moments`, `renderBallMoments` | AG «La bola y ella» (4 tarjetas) | Ítem «La bola y ella» | Bola vista en el 80 % de los golpes. |
| 55 | Ver una bola cerca de la red y un apoyo cerrado con golpe paralelo (12-10 17:40) | PARCIAL | Filtros `LIBF`, chips de Aprende | Videoteca y Aprende | «Filtros combinables» | En sus datos hay 0 paralelas y 1 cerrado más «invertida paralela»: el ejemplo no se puede ver. |
| 56 | Barras horizontales con la diferencia de altura de la cabeza (12-10 17:40) | HECHO | `heightBars()` | AG, capa «Alturas» («cabeza +2 cm») | «Barras de altura» | |
| 57 | Nada de gráficas de muchas líneas ni tablas sin frases (12-10 17:10) | HECHO | Frases sobre cada tabla; detalles técnicos plegados | AG, Explorador, Comparativas, Comparar | «más de 4 líneas», «Tablas a la vista» | |
| 58 | La IA más moderna posible (11-10 09:05) | HECHO | YOLO11-pose, TrackNetV3, RTMPose de raqueta, RTMW3D | — | (elección) | |
| 59 | Diferencias solo por encima del error y en situaciones equivalentes (10-10 18:05) | HECHO | `model.py` (OLS, Benjamini-Hochberg) | Panel «Hallazgos» con el ruido | «Valores posibles», «Cada frase lleva…» | |
| 60 | Confirmar con un clic quién es Rybakina (10-10 17:27) | NO APLICA | Sustituido por «todo automático» | — | — | |
| 61 | Semiautomático: el usuario revisa los dudosos (10-10 17:27) | NO APLICA | Sustituido (11-10 19:38) | — | — | |
| 62 | Vídeos de YouTube de análisis en el informe (11-10 07:34) | NO APLICA | Sustituido por el requisito 6 | — | — | |
| 63 | Descargar el resumen de YouTube como ejemplo (11-10 09:21) | NO APLICA | El usuario subió los clips | — | — | |
| 64 | Todos los tipos de desplazamiento, del split step a la recuperación, con cada tipo de paso; «hay que hacer la inversa» (12-10 18:03, 18:06; 13-10 05:48 p4) | PARCIAL | `footwork.steps`, `step_kinds`, `recovery_*` | AG «Sus pies en este golpe»; Aprende «Pies» y fase 8 | Auditoría §1 «3. Pies…» (27 ok) | El paso cruzado no aparece en ningún golpe. El primer paso y el ajuste salen «no medible» si los tobillos se ven quietos menos del 40 % del tiempo. |
| 65 | El play del vídeo funciona (no solo un fotograma) (12-10 18:14, 21:03, 21:14) | HECHO | `startPlay` y bucle de vídeo | AG, Comparar, Videoteca, SuD, Panel | «Reproducir: …» 5/5, también sin animaciones | |
| 66 | Fechas y duración en los registros (12-10 18:25) | HECHO | `comun.ps1` | — | «Empezado … duracion total» | |
| 67 | No borrar el trabajo hecho: lo complejo como extra (12-10 22:35; 13-10 05:48 p6) | HECHO | 10 pestañas; tablas debajo de las frases | Todas | «Pantallas» | |
| 68 | La meta: mejorar mi derecha tomando la de X como base (12-10 22:25; 13-10 05:48 p5) | PARCIAL | `learn.py` | Aprende (valor de ella, cómo hacerlo, error, ejercicio, plan) | `learn_check` | Valores provisionales de 1-10 golpes. Sin progresión ni prioridad (qué copiar primero según lo que la distingue). |
| 69 | Ejemplo: «derecha paralela, apoyo cerrado, parada, bola plana, lado derecho» (cómo lo hace ella y cómo replicarlo) (13-10 05:48 p8) | PARCIAL | `learn_check.USER_EXAMPLE`; `aResolve` | Aprende §1-4 | Combinación comprobada en el navegador | Con sus datos hay 0 golpes exactos: se quitan las 5 condiciones y se ven las 10 derechas. «Qué cambia» es texto general, no lo que hace ella. |
| 70 | Las 2000 y pico combinaciones, usables y validadas (13-10 05:48 p2; 06:00) | PARCIAL | `learn_check.combos` (ninguna, una y parejas) | Chips de Aprende | 677 combinaciones, 176 con golpes exactos | Combinaciones de medida y nivel: 0 de 2.992 visibles. Solo se prueba un trío o más (el ejemplo del usuario). |
| 71 | El conocimiento de los vídeos de entrenadores en la web (12-10 21:31; 13-10 05:48 p3) | PARCIAL | `learn.py` (cue/mistake/drill), `explain.COACH`, capa «Líneas» | Aprende; AG «Líneas» | Auditoría §3 (R1-R23) | La fuente es una etiqueta genérica. Falta «Lo que la distingue» (mejora 12). El examen R no sale en la web (decisión de diseño). |
| 72 | El conocimiento del chat (modelo técnico, taxonomía, matriz) implementado en la web, no solo en documentos (13-10 06:00, 06:30) | PARCIAL | `learn.PHASES`/`FEET` (47 puntos), `CONDITIONS`, `NOT_FROM_TV` | Aprende | «Cada punto de la matriz tiene su sitio» 59/59 | Está en la web, pero con 10 golpes casi nada se puede afirmar. SuD (fases, `copy_cue`) no se ve. |
| 73 | Revisar la web de arriba abajo para que aporte valor (13-10 05:48 p6) | PARCIAL | 10 pantallas | Todas | `screens.py` | SuD vacía, Comparativas con 8 «Sin datos», Explorador con 41 «—». Panel dice 14 derechas y Aprende 10 (cuenta las lejanas). |
| 74 | ¿El análisis de las apps de pago y libres fue profundo o superficial? (13-10 05:48 p7) | PARCIAL | `docs/comparativa_apps.md` (100 líneas) | — | — | Solo documental: sin contrastar pantalla a pantalla. Aprende imita las posiciones P de Sportsbox. |
| 75 | Velocidad: «10 golpes en 5 horas es absurdo» (13-10 05:48 p10) | NO | — | — | Auditoría §9 | Prueba media: 5 h 02 min para 35 min de vídeo. |
| 76 | «Un 50 % de golpes dudosos» (13-10 05:48 p10) | HECHO | Banderas de `review` | Chip «10 con dudas» | «Nada pide revisión manual» | Solo cuentan las dudas sobre el golpe; raqueta no vista, espera o recuperación no encontradas y valores descartados son «medidas que faltan». PC 13-10: 1 de 10. |
| 77 | No lanzar pruebas de 6 h para validar (13-10 06:01) | PARCIAL | `2c_solo_informe.bat` (2 min) | — | La auditoría corre sola | Validar el análisis exige la prueba media (5 h). |
| 78 | No depender de que al usuario se le ocurran funciones (13-10 06:09) | PARCIAL | Matriz con fuentes, `aprendido_entrenadores.md` | — | — | Quedan sin hacer 4 mejoras propuestas por Claude (filas 102, 106, 110, 112). |
| 79 | Vídeos de entrenamiento con otras cámaras, en un apartado aparte y marcado (12-10 21:31, 21:32) | PARCIAL | `practice.py`, `scripts/practice_videos.py` | VL (marcada «Fuente aparte») | «Vídeos de entrenamiento analizados»: 5 vídeos, 91 golpes | Solo 3 derechas de lado medidas (de 23 laterales), así que no hay resumen. En Aprende, «— menos de 12» aunque haya 13 estimaciones 3D. |
| 80 | Encadenar solo la prueba y las comprobaciones; que Claude lo monitorice (12-10 22:43) | HECHO | `prueba_rapida.ps1`, `solo_informe.ps1` → audit, capturas, `pc-logs` | — | (proceso) | |
| 81 | Tamaño de la salida; comprobación sin gastar tokens (12-10 22:40) | HECHO | `tamanos.txt`, `audit.py` en Python | — | `tamanos.txt` (≈1,9 GB `_smoke`) | |
| 82 | Dónde se graban las salidas, qué va a git, qué se reutiliza (12-10 22:47) | HECHO | `output/_smoke`, `pc-logs`, caché por etapas | — | (proceso) | |
| 83 | Árbol de ficheros generados y validados (12-10 22:25) | HECHO | `audit.file_tree_items` | — | «Partido …: salida de cada etapa» (27 ventanas y series) | |
| 84 | Matriz §1 Cadena cinética (suelo → pelvis → separación → tronco → codo → muñeca) (12-10 21:14) | PARCIAL | `hip_rise`, `hip_turn`, `x_factor`, `chain`, `racket_forearm` | Aprende fases 3-4; AG «Detalles técnicos» | Auditoría §1 «6. Matriz…» | Fuerza contra el suelo, pronación y snap: solo «no medible». X-factor 1°. Lag con 1 golpe. |
| 85 | Matriz §2 Cuerpo (cabeza, brazos, tronco, piernas, pie de arrastre) | PARCIAL | `head_motion_cm`, `class.arm`, `elbow_non`, `wrist_non_lateral`, `trunk_tilt`, `drag_foot` | Aprende fases 1-7 y «Pies» | Ídem | Mirada y core: no medibles. Cabeza quieta: 2 golpes. Rodillas desde detrás: escorzo; la rodilla de lado sale «—». |
| 86 | Matriz §3 Raqueta (bucle, caída, cara, trayectoria) | PARCIAL | `class.takeback`, `wrist_drop`, `face_tilt`, `swing_low_to_high` | Aprende fases 2-5; AG «Raqueta…» | Ídem y §4 | Caída bajo la bola solo de lado («—»). Dentro-fuera: no medible. Cara en el impacto estimada. |
| 87 | Matriz §4 Apoyos (abierto, semiabierto, neutro o cerrado, salto, abierto extremo) | HECHO | `class.stance_*`, `stance_role`, `movement` | Aprende fases 3 y «Pies»; AG ficha; Videoteca | «Apoyos…», «Apoyo en suspensión» | Salto: 0 casos en sus datos. |
| 88 | Matriz §5 Pies (split, ajuste, cruzado, paso de ataque, recuperación) | PARCIAL | `footwork.py` | Aprende «Pies» y fase 8; AG «Sus pies» | Ídem | El paso cruzado nunca aparece. Pasos en 4 de 10 golpes. |
| 89 | Matriz §6 Modalidades (plano, liftado, cortado, botepronto, volea, 3 terminaciones) | PARCIAL | `class.swing` (trayectoria de la mano), `contact_type`, `class.finish` | Aprende §1 «Efecto», «Contacto»; fase 7 | Ídem | «Plano» = trayectoria, no efecto: 0 casos. Botepronto y volea: 0. Terminaciones: sí. |
| 90 | Matriz §7 Adaptación a la bola (rápida, corta, alta, lateral) | PARCIAL | `CONDITIONS` (velocidad, altura, profundidad, lado) | Aprende §1 y §3 | Auditoría «Bola rápida/lenta…» | Ningún nivel llega a 12 golpes. «Qué cambia» es texto genérico, no su cambio medido. |
| 91 | Matriz §8 Dirección (cruzado, paralelo, dentro-fuera, dentro-dentro) | PARCIAL | `class.shot_type` | Aprende §1 «Dirección»; Pista «Destino» | «Dirección…» 70 % | Paralela 0, invertida cruzada 0. |
| 92 | Matriz §9 Control (zona de impacto, relajación, equilibrio) | PARCIAL | `wrist_dom_vs_hip`, `wrist_dom_lateral`, `head_over_base` | Aprende fases 5 y 7 | Ídem | «Delante de la cadera» solo de lado o en 3D: en Aprende «—». Equilibrio: 1 golpe. |
| 93 | Matriz §10 Propiedades de la raqueta | HECHO (como «no medible») | `learn.NOT_FROM_TV` | Aprende §6 | «no observable … el informe lo dice» | |
| 94 | Matriz §11 Cinemática cuantitativa (velocidad de raqueta, °/s, fuerza, rpm) | HECHO (como «no medible») | `NOT_FROM_TV`; `racket_speed_rel`, `chain` (orden) | Aprende §6; AG métricas | Ídem | Solo comparación relativa y velocidad media de la bola. |
| 95 | Matriz §12 Neuro y visión (latencia, mirada, EMG) | PARCIAL | `split_landing_vs_opp_s`, `first_step_s` | Aprende fase 1 y «Pies» | Ídem | Latencia con 4 golpes. Mirada y EMG: no medibles. |
| 96 | Matriz §13 Microbiomecánica (muñeca, codo, hombro) | HECHO (como «no medible») | `NOT_FROM_TV` | Aprende §6 | Ídem | |
| 97 | Matriz §14 Fugas de energía (apertura prematura, casting, vector) | PARCIAL | `shoulders_open_first`, `racket_forearm`, `swing_low_to_high` | Aprende fase 4 | Ídem | Casting solo de lado (3 golpes, «—»). |
| 98 | Matriz §15 Contexto y ambiente (superficie, aerodinámica) | HECHO | `catalog.Match.surface` | Aprende §1 «Superficie de sus partidos: —» | «Superficie de la pista»: no está en los datos | Superficie del torneo o del nombre del vídeo (`catalog.surface_of`, también cirílico): «dura» en la prueba. |
| 99 | Mejora 1 (entrenadores): líneas dibujadas sobre el fotograma | HECHO | `coachLines()` | AG, capa «Líneas» y fotogramas clave | Capturas | |
| 100 | Mejora 2: raqueta al lado del cuerpo o detrás de la espalda, y adónde apunta la punta | PARCIAL | `racket_head_lateral`, `class.racket_plane` | Aprende fase 3 | «no aparece en los datos de ningún golpe» | Sale «—» en sus 10 golpes. `tip_points_to` no existe. |
| 101 | Mejora 3: altura y separación del codo | HECHO | `elbow_dom_vs_shoulder`, `elbow_dom_lateral` | Solo SuD (≥12): no se ve | «Altura y separación del codo» | En Cópiala (armado): altura y separación del codo. |
| 102 | Mejora 4: punta de la raqueta respecto a la cabeza en el armado | HECHO | — | — | — | `loaded.racket_tip_vs_head` en Cópiala; se ve en 2 de 10 (la raqueta casi no se detecta en el armado). |
| 103 | Mejora 5: transferencia de peso en una frase | HECHO | `stroke.weight_shift` | Solo SuD (≥12) | «Transferencia de peso» (40 %) | En Cópiala (aceleración). |
| 104 | Mejora 6: empuje de piernas («bajar y subir») | HECHO | `stroke.hip_rise` | Aprende fase 4 (3,8 %) | «Empuje de piernas» | |
| 105 | Mejora 7: ritmo con la bola (caída al subir la bola) | HECHO | `acceleration_vs_bounce` | Aprende solo `loaded_vs_bounce`; la caída, solo en SuD | «Inicio de la aceleración respecto al bote» | `acceleration_vs_bounce` en Cópiala (aceleración). |
| 106 | Mejora 8: frenado de los hombros antes del contacto | HECHO | — | — | — | `stroke.shoulder_brake`; hereda el sesgo del giro 2D de hombros: la web dice por qué no se da. |
| 107 | Mejora 9: caída por debajo de la bola | PARCIAL | `practice.racket_drop_below_contact_cm` | Aprende fase 4 (solo de lado) | VL, 3 golpes | Desde la tele no existe. |
| 108 | Mejora 10: «gira mientras corre» | HECHO | `takeback_vs_first_step` | Aprende fase 2 (0,34 s, 3 golpes) | — | |
| 109 | Mejora 11: frases con datos existentes (mano libre, terminación, base al terminar, desplazarse bajo) | PARCIAL | `extension.wrist_non_lateral` (catch) | Aprende fase 6 | — | Faltan la mano libre en el armado, `finish.elbow_non`, la base al terminar y la cadera durante el desplazamiento. |
| 110 | Mejora 12: «Lo que la distingue» (2-3 rasgos frente a la literatura, con vídeo) | HECHO | — | — | — | «Su firma» en Cópiala: lo que repite en ≥ 75 % de sus golpes, solo medidas fiables, con vídeo (sin comparar con otras jugadoras: sin fuentes externas). |
| 111 | Mejora 13: consigna «para imitarla» y error que evita, por fase | HECHO | `learn.cp(cue, mistake, drill)`; `explain.copy_cue` | Aprende, cada punto | `learn_check` (las 3 rellenas) | Las consignas son genéricas. «Ella:» solo antepone su valor. |
| 112 | Mejora 14: clase descriptiva de estilo (`fh_style`) | HECHO | — | — | — | «Estilo de su derecha» en una frase (solo lo que hace en ≥ 50 %; si no, «variable»). |
| 113 | Mejora 15: examen interno con las afirmaciones de entrenadores (R1-R25) | PARCIAL | `audit` §3 | — (nunca en la web, por diseño) | 16 ítems R, todos «pocos datos» | Nada confirmado ni refutado. R2 apunta a un fallo de `ready_hands` (100 % «mano libre separada»). |
| 114 | Cuerpo respecto a la bola en cada momento (golpe rival, cruza la red, cae, bota, sube, golpe): fotogramas y medidas reales, no gráficas (12-10 17:40; 13-10 11:50) | HECHO | `report.ball_moments` (+ «cae»), `measuresAt` | AG «La bola y ella»: cada fotograma con cadera en cm respecto a la espera, pies en m y recorrido desde el golpe rival | «La bola y ella: medidas reales…» | |
| 115 | Cuánto baja y sube el cuerpo, con fotogramas y barras horizontales: de la espera al punto más bajo y del más bajo al más alto tras golpear (12-10; 13-10 11:50) | HECHO | `technique.body_moves` (`hip_drop_cm`, `hip_rise_after_cm`), `renderBody` | AG «Bajar y subir» (3 fotogramas con las barras), Aprende fases 4 y 7 | «Bajar y subir: 3 fotogramas…»; fiabilidad por medida | Cadera de la curva corregida de perspectiva; fuera de 38-58 % de su altura no se mide. |
| 116 | Distancia entre las piernas en los golpes: base y estabilidad (13-10 11:50) | HECHO | `body_moves` (`base_court_m` en armado, impacto y terminación; `feet_move_m`) | AG «Base» (barra entre los pies, m en la pista), Aprende fases 3, 5 y 7 | «Base: fotogramas…» | En metros sobre la pista (homografía). |
| 117 | Hacia dónde mira el tronco al terminar (valla lateral, de frente, girado) según el golpe (13-10 11:50) | HECHO | `body_moves` (`class.finish_trunk`) | AG «Tronco al terminar», Aprende fase 7 (por condición) | «Tronco al terminar…» | Desde detrás: anchura de los hombros y hombro adelantado; la fiabilidad la juzga el cambio al mover las fases. |
| 118 | Validar cada medida de forma automática, no a mano: ¿técnica o ruido? (13-10 08:40-10:30) | HECHO | `tennisbio.reliability` (repetibilidad con fases movidas, segundo método 2D/3D, medidas derivadas) | Cópiala (no se da o «medida ruidosa»), Más › Fiabilidad de las medidas | «Cada medida comprobada: técnica o ruido» | Valida ruido y coherencia entre métodos, no la exactitud frente a una referencia real. |
| 119 | Automatizar todo el ciclo en el PC: el usuario no lanza pruebas ni avisa (13-10 10:40, 11:20) | HECHO | `ciclo_automatico.ps1`, `ciclo_bucle.ps1`, `scripts/auto_cycle.py` | — (proceso) | `revision_automatica.md` en pc-logs (OK / REGRESIÓN / ERROR) | |
| 120 | Vídeo a pantalla completa (13-10 12:00) | HECHO | `toggleFull`, `fitCanvases` | Análisis de golpe y Comparar (⛶, F, doble clic) | prueba `test_layer_groups_and_full_screen` | |
| 121 | Ver lo que se pinta por separado, por grupos o una a una (13-10 12:00) | HECHO | `LPRESET`, `setLayers` | Análisis de golpe: «Ver: Solo vídeo · Cuerpo · Raqueta y bola · Alturas · Líneas · Pista · Todo» | prueba `test_layer_groups_and_full_screen` | |
| 122 | Web en 2 vistas principales y el resto en «Más», en dos grupos (funcional y técnico), sin perder datos (13-10 12:15-13:00) | HECHO | `nav`, `TAB_ALIAS`, `setLibMode`, `renderData`, `renderReliability` | Cópiala, Sus golpes; Más › Para practicar / Técnico | pruebas `test_two_main_views_and_more`, `test_merged_views_keep_every_piece`; auditoría abre las 9 pantallas | |
| 123 | Lo que se aprende en una sesión: plan de 3 prioridades en orden, foco externo por fase, detalle plegado (13-10 13:20) | HECHO | `learn.PLAN`, `focus` por fase | Cópiala § «Tu plan» y «Foco» en cada fase | `learn_check` (plan ≤ 3, foco en cada fase) | |
| 124 | Hacia dónde mira el tronco y las manos en la espera, medidas fiables (13-10 13:00) | PARCIAL | `body_moves` (fotograma más girado, comprobación con la mano), `ready_hands` en toda la espera (±4 fotogramas de raqueta) | Cópiala, Análisis de golpe | fiabilidad por medida | Manos en la espera solo en 3 de 10 golpes (la raqueta casi no se ve en la espera). |
| 125 | Velocidad, rendimiento y algoritmia antes del tramo largo nocturno (13-10 13:05) | NO | — | — | Auditoría «Tiempo» (≈ 15 h por partido) | Decisión del usuario: primero esto, después más golpes. |

## Lo más grave que falta (por impacto en «copiar su derecha»)

1. **No hay golpes suficientes para afirmar nada.** Aprende funciona, pero todo sale de 1-10 golpes
   «provisional», SuD está vacía y 0 de 2.992 combinaciones son visibles.
   *Arreglo:* analizar **un partido completo** en cuanto la velocidad lo permita (punto 2). En Aprende, dar
   también el intervalo con su incertidumbre cuando n < 12, en vez de solo «provisional».
2. **La velocidad hace inviable lo anterior.** 251 min para 35 min de vídeo, unas 25 h por partido.
   *Arreglo:* perfilar la etapa `fine` por golpe (pose 1280, raqueta, RTMW3D con `hand3d_step`, TrackNet).
   Desactivar la mano 3D salvo en el armado y el impacto, y reducir la ventana a lo que piden las fases.
   Todo en DirectML. Objetivo: ≤ 1 h por partido, medido en `progreso.json`.
3. **Combinar condiciones no da «cómo lo hace ella».** `aResolve` quita todas las condiciones cuando hay
   menos de 12 golpes, y «Qué cambia» es texto fijo de entrenador.
   *Arreglo:* ordenar los golpes por número de condiciones que cumplen y mostrar siempre los exactos y los más
   cercanos con vídeo. En «Qué cambia», poner primero la diferencia medida de ella en ese nivel frente a su
   habitual (de `model.py`, con su ruido), y el texto del entrenador después.
4. **Golpes dudosos y fallidos.** 71 % con dudas, 4 con error en `fine` (✘ en la auditoría).
   *Arreglo:* corregir las causas de `strokes_errores.json`. Revisar qué banderas de `review` marcan casi todo.
   Que la auditoría falle si los dudosos pasan del 30 %.
5. **Medidas sin validar y valores sospechosos.** X-factor de 1°. `ready_hands` da «mano libre separada» en
   el 100 %, también en revés a dos manos, contra R2. La cara en el impacto es la estimación.
   *Arreglo:* contrastar cada medida 2D de la tele con la vista lateral y la 3D (los mismos golpes de
   entrenamiento en las dos vistas). Corregir el umbral de `hands_apart` con un test. Pruebas de coherencia en
   la auditoría (revés a dos manos ⇒ dos manos).
6. **Pies del split step a la recuperación.** Pasos medidos en el 40 %, el paso cruzado nunca, y el golpe de
   ejemplo dice «no medible» en el primer paso y el ajuste.
   *Arreglo:* para el lado cercano, recorte que siga los pies (como `extract_follow`) a más resolución,
   confianza por paso en lugar del umbral global `STEPS_MIN_STILL`, y validación con clips anotados.
7. **Vista lateral y 3D desconectadas de Aprende.** Hay 13 estimaciones 3D y 91 golpes de entrenamiento, pero
   Aprende pone «— menos de 12». Solo 3 derechas de lado tienen el impacto confirmado por el sonido.
   *Arreglo:* usar en Aprende las estimaciones 3D (marcadas como estimación) cuando la vista de lado tenga
   menos de 12. Confirmar el impacto por la pose o la bola cuando no hay sonido.
8. **Mejoras de entrenador sin hacer o sin llegar a Aprende.** Faltan «Lo que la distingue», la punta frente a
   la cabeza, el frenado de hombros y `fh_style`. El codo alto, la transferencia de peso y la aceleración
   respecto al bote solo están en SuD.
   *Arreglo:* añadir esos puntos a `learn.PHASES` y un bloque «Lo que la distingue» en Aprende (por ejemplo,
   su % de apoyo cerrado frente al 84 % abierto del circuito), cada uno con su vídeo.
9. **Las cuerdas, obligatorias, no están en Aprende por fase.** Solo sale la cara en el impacto (estimada).
   Adónde apuntan en el armado, la caída y la terminación (la parte fiable) solo se ve golpe a golpe en AG.
   *Arreglo:* un punto de control «Cuerdas hacia…» en las fases 1, 3, 4 y 7 de Aprende, con su % de golpes.
10. **La validación automática comprueba la forma, no el contenido.** Las peticiones 64-113 no tienen regla
    en `audit.PETITIONS`. La superficie nunca se rellena (`auto_catalog.py`). Los recuentos no cuadran
    (14 en el Panel, 10 en Aprende).
    *Arreglo:* reglas para las filas 64-113. Una comprobación de que «Qué cambia» usa los datos de ella. La
    superficie a partir del torneo. Una sola cuenta de golpes cercanos en todas las pantallas.
