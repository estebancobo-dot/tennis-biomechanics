# Revisión independiente de todas las peticiones (19-10)

**Por qué.** El 19-10 el usuario vio que faltaban cosas que había pedido varias veces: el «golpe angulado» (10-10 18:05: «laterales, ángulos, cortas, half volleys»), la «bola corta baja / alta cerca de la red» y la «volea a media pista con golpe de fondo». El registro `docs/peticiones_usuario.md` lo escribió Claude y resumía mensajes enteros en una fila. Así esas peticiones se perdieron, mientras se decía que todo estaba cubierto.

**Cómo se ha hecho.**
- Se han leído los 238 mensajes escritos por el usuario desde el 10-10. La transcripción tiene 361 entradas de usuario; el resto son imágenes, avisos del sistema e informes de subagentes. Se incluyen las listas largas que pegó: la matriz de 15 secciones (12-10 21:14 y 13-10 05:53/05:57), los 11 puntos (13-10 05:48) y la lista numerada del 12-10 21:14.
- También se han revisado `CLAUDE.md`, `docs/matriz_cobertura.md` (literatura y sistemas profesionales), lo aprendido de YouTube, la guía de Ivanovic, el estado del arte, la comparativa con apps, la revisión completa y las auditorías del 17-10.
- Cada estado sale del código (fichero y función) o de dónde se ve en la web. **No** sale de lo que decía el registro. Si no hay prueba, no cuenta como HECHO.
- «Lista de 15 puntos» = la matriz de 15 secciones que pegó el usuario. Sus 59 elementos están en `docs/matriz_cobertura.md` §6, y se ha comprobado que cada clave de código que citan existe y se muestra.

**Estados:**
- **HECHO**: está en el código y se ve en la web o en el proceso.
- **PARCIAL**: falta algo, y se dice qué.
- **FALTA**: no está.
- **NO MEDIBLE**: no se puede ver desde una cámara de TV detrás del fondo, y se dice por qué.
- **NO APLICA**: sustituido o descartado por el usuario.

## Resumen

**382 elementos revisados:** 209 hechos · 112 a medias · 25 sin hacer · 31 no medibles desde la tele · 5 no aplican.

**Fuera del registro:** 31 peticiones del chat no tenían fila en `docs/peticiones_usuario.md`, y 13 de ellas no están terminadas. Se añaden al registro 87 filas nuevas (#131-#217).

| Fuente | Total | HECHO | PARCIAL | FALTA | NO MEDIBLE | NO APLICA |
|---|---|---|---|---|---|---|
| Chat | 125 | 74 | 41 | 5 | 1 | 4 |
| CLAUDE.md | 24 | 11 | 10 | 2 | 1 | 0 |
| Matriz pegada por el usuario | 59 | 25 | 20 | 0 | 14 | 0 |
| Matriz (literatura) | 108 | 68 | 25 | 1 | 14 | 0 |
| YouTube | 18 | 13 | 4 | 1 | 0 | 0 |
| Guía Ivanovic | 20 | 11 | 5 | 4 | 0 | 0 |
| Estado del arte | 9 | 3 | 0 | 6 | 0 | 0 |
| Comparativa apps | 5 | 1 | 2 | 1 | 0 | 1 |
| Revisión completa | 5 | 1 | 1 | 2 | 1 | 0 |
| Auditorías 17-10 | 9 | 2 | 4 | 3 | 0 | 0 |
| **Total** | **382** | **209** | **112** | **25** | **31** | **5** |

Notas a la tabla:
- Una misma petición puede aparecer en varias fuentes. Por ejemplo, «cuerdas» sale en el chat, en `CLAUDE.md` y en la matriz.
- «Matriz (literatura)» son las secciones 1-5b de `docs/matriz_cobertura.md`.
- «Matriz pegada por el usuario» es su sección 6.

## Lo más grave

1. **Se pierden más de la mitad de sus golpes** en los partidos completos: como mucho el 43 % de sus golpes y el 29 % de sus saques en la final del US Open. Los 4 partidos lanzados el 18-10 no valen. Ya se mide (`audit.recall_items`, `scripts/validate_recall.py`), pero no está arreglado. Hay fallos de identidad sin explicar.
2. **Golpe angulado: no existe**, aunque se pidió el 10-10 y se repitió. El bote de su bola ya se mide (`shot_bounce_m`), pero `court_metrics.shot_landing` solo da cruzada, paralela o al centro.
3. **Volea a media pista con golpe de fondo: no existe.** `technique.contact_type` solo llama «volea» a un impacto sin bote dentro de la línea de saque. Entre la línea de saque y el fondo, el golpe queda sin clase.
4. **Bola corta baja o alta cerca de la red: a medias.**
   - No hay nivel «cerca de la red»: «dentro de la pista» junta todo lo que está a más de 0,5 m de la línea de fondo.
   - En la videoteca, «corta», «baja», «alta» y «cerca de la red» están en el mismo grupo y no se pueden combinar.
5. **La auditoría no enseñaba lo que falta.**
   - Una petición «NO» o «PARCIAL» sin regla salía como «pocos datos».
   - Una «PARCIAL» cuyas comprobaciones pasaban salía como un aviso más, en la sección 11.
   - La revisión automática decía «OK» con peticiones sin hacer.
   - Cuatro filas «HECHO» (#102, #106, #110 y #112) no tenían ninguna prueba escrita. La tienen, pero nadie la había comprobado.
6. **Guía de Ivanovic (puntos que el usuario destacó):**
   - 3 a medias: falta «punta arriba / codo alto».
   - 6 a medias: faltan 3 alarmas, y la de pausa usa una medida declarada no medible.
   - 10 sin hacer: la mano libre en la aceleración y el impacto.
7. **Estado del arte:** de los cambios marcados «Cambiar», no se ha hecho ninguno de los que mejorarían la calidad: bote, pista, OCR 3.x, WASB, clasificador de golpes con F3Set. El último ayudaría directamente al punto 1.

## 1. Peticiones del chat que NO estaban en el registro (31)

| Fuente | Fecha | Palabras del usuario / de la fuente | Registro | Estado | Prueba (código o web) | Qué falta / por qué |
|---|---|---|---|---|---|---|
| Chat | 10-10 17:27 | «detectar impactos de bola por AUDIO» | **NUEVA #131** | **HECHO** | `impacts.py` (onsets), fusionado con la bola y la muñeca en `stages.py` | El audio llega 2-4 fotogramas tarde: es señal secundaria (validado). |
| Chat | 10-10 18:05 | «ángulos (golpe angulado) — repetido el 19-10 08:11: «golpe angulado ... te lo he dicho muchas veces»» | **NUEVA #132** | **FALTA** | Solo `court_metrics.shot_landing` (cruzada, paralela, al centro) y el bote `shot_bounce_m` | No existe la clase «angulado» (bola cruzada que bota corta cerca de la línea lateral) ni como dirección ni como condición de «Cópiala» ni como filtro. Es medible desde la tele: el bote ya se calcula. Nunca estuvo en el registro: se perdió al resumir el mensaje en la fila 5. |
| Chat | 11-10 08:10 | «(enlaces de Reddit sobre análisis de tenis y ML)» | **NUEVA #133** | **NO APLICA** | Consulta puntual sin requisito de producto | No hay constancia en el repositorio de qué se sacó de esos enlaces. |
| Chat | 11-10 18:06 | «prefiero una baseline completa a cerrar más golpes» | **NUEVA #134** | **HECHO** | Solo la derecha tiene informe; revés y saque solo se clasifican (CLAUDE.md requisito 10) |  |
| Chat | 11-10 19:23 | «distancia al fondo, red» | **NUEVA #135** | **PARCIAL** | `learn.CONDITIONS` «Dónde golpea» (dentro de la pista, sobre la línea, 1-2 m, 2-4 m, muy atrás) | Hay distancia al fondo, pero no a la red: «dentro de la pista» junta todo lo que está a más de 0,5 m dentro de la línea, de la zona de saque a la red. |
| Chat | 13-10 09:47 | «lo puedes añadir al contexto o fichero base?» | **NUEVA #136** | **HECHO** | `CLAUDE.md` «Vistas por golpe pedidas por el usuario» |  |
| Chat | 13-10 18:31 | «hay algo que se pueda paralelizar ... threading» | **NUEVA #137** | **HECHO** | `fine_ahead.py` (bola en la CPU en paralelo) |  |
| Chat | 13-10 18:34 | «se puede hacer modelos hibridos de alguna manera?» | **NUEVA #138** | **HECHO** | `config/default.yaml` (`pose_model: hybrid`), YOLO11 + RTMPose-x |  |
| Chat | 14-10 20:08 | «si se pierde calidad no tocamos nada» | **NUEVA #139** | **HECHO** | Velocidad cerrada (14-10) en `docs/estado_proyecto.md` |  |
| Chat | 14-10 20:08 | «de la jugadora de fondo se sacan imagenes para la captura de datos en vista frontal?» | **NUEVA #140** | **PARCIAL** | Lado lejano: posición, desplazamiento, altura del impacto y destino (`report.py`, `FAR_OK`) | No se usa como vista frontal para medidas del cuerpo: a 60-90 px los tobillos y la raqueta salen imprecisos. |
| Chat | 17-10 09:49 | «(punto 0) la imagen ... Estroboscópica ... no vale para nada; ... Sus pies en este golpe tampoco» | **NUEVA #141** | **HECHO** | «Sus pies en este golpe» con fotogramas reales y «El recorrido del brazo» plegado (`report_template.html`) |  |
| Chat | 17-10 09:49 | «(punto 2) como se puede hacer una aplicacion profesional ... mas jugadores, mas golpes ... como se lanza, almacenamiento, videos, progreso y monitorizacion» | **NUEVA #142** | **PARCIAL** | `docs/aplicacion_local.md`; `app/core.py`, `app/window.py`, `app/notify.py`, `app/storage.py` | Construida y probada, pero el análisis real de los 4 partidos (18-10) se lanzó con el ciclo, no desde la aplicación; nunca usada con datos correctos. |
| Chat | 17-10 09:49 | «(punto 3) esta es una guia para la derecha de otra jugadora ... revisar si aplica todo» | **NUEVA #143** | **PARCIAL** | `docs/comparacion_guia_ivanovic.md` | De sus 20 huecos, 7 siguen a medias o sin hacer (ver fuente «Guía Ivanovic»). |
| Chat | 17-10 09:49 | «(punto 4) hay tareas o schedulers ... salen terminales y se apagan solos» | **NUEVA #144** | **HECHO** | `oculto.vbs` (ciclo sin ventanas) |  |
| Chat | 17-10 10:09 | «no quiero nada en la nube ni pagar ni nada» | **NUEVA #145** | **HECHO** | `docs/arquitectura_producto.md` «Decisión del usuario» |  |
| Chat | 17-10 10:49 | «borra las carpetas de pruebas antiguas» | **NUEVA #146** | **HECHO** | Petición del ciclo para borrar `_poc*` (commit 17-10 10:49) |  |
| Chat | 17-10 10:52 | «la guia de ivanovic esta aplicada al 100 por 100? sobre todo los puntos 1 2 3 5 6 y 10» | **NUEVA #147** | **PARCIAL** | Huecos 1, 2 y 5 hechos | 3 a medias (falta «punta arriba / codo alto»), 6 a medias (faltan 3 alarmas), 10 sin hacer (mano libre en aceleración e impacto). |
| Chat | 17-10 13:05 | «empieza por la maqueta de una fase» | **NUEVA #148** | **HECHO** | `docs/maqueta_leccion_armado.html` |  |
| Chat | 17-10 13:11 | «no se como validar eso lo tienes que hacer tu» | **NUEVA #149** | **HECHO** | `learn_check.check_lesson`, `tests/test_learn_web.py` |  |
| Chat | 17-10 17:21 | «estos son mas videos de youtube para analizar (3 enlaces)» | **NUEVA #150** | **HECHO** | `docs/investigacion_youtube_usuario.md` (17-10) |  |
| Chat | 17-10 17:25 | «como se separan los golpes (derecha, reves, saque, voleas), los jugadores, los partidos» | **NUEVA #151** | **HECHO** | `docs/aplicacion_local.md` §2; `app/index.py` | Volea y media volea solo como clase de contacto dentro de derecha y revés. |
| Chat | 18-10 10:12 | «como queda la estructura de directorios ... carpeta normalizada de los jugadores» | **NUEVA #152** | **HECHO** | `docs/aplicacion_local.md` (vídeos por contenido, no por jugadora), `app/storage.py` |  |
| Chat | 18-10 11:19 | «y analizo estos videos (2 enlaces de Olivari)» | **NUEVA #153** | **HECHO** | `docs/investigacion_youtube_usuario.md` (18-10) | Su propuesta 4 sigue sin hacer (fuente YouTube). |
| Chat | 18-10 12:11 | «mi movil es android google pixel 8 ... que copie directo al pixel» | **NUEVA #154** | **PARCIAL** | `app/phone.py` | Sin probar con el teléfono conectado. |
| Chat | 19-10 06:15 | «es fisicamente imposible que en un partido solo de 86 o 77 golpes ... no quiero que se pierdan golpes» | **NUEVA #155** | **FALTA** | Medido: `scripts/validate_recall.py`, `validation/recall_eval.py`, `audit.recall_items` (19-10) | Detección sin arreglar: como mucho 43 % de sus golpes y 29 % de sus saques en la final del US Open. Falta correr el banco de 650 golpes anotados y corregir la etapa que los pierde. |
| Chat | 19-10 06:29 | «como sabes la identidad de la jugadora y porque hay fallos? porque no buscas en la web de la wta la imagen y altura» | **NUEVA #156** | **PARCIAL** | `identity.py` (ropa + icono de saque); altura en `config/players` | Fallos sin explicar ni corregir; una foto de la WTA sería una fuente externa (requisito 6) y no sirve desde detrás: la identidad debe validarse con `validation/recall_eval.py`. |
| Chat | 19-10 08:11 | «bola corta baja cerca de la red» | **NUEVA #157** | **PARCIAL** | Se pueden combinar «Dónde golpea: dentro de la pista» + «Altura: rodilla» en «Cópiala» (`learn.CONDITIONS`) | No hay nivel «cerca de la red» (`technique.situation`: «dentro de la pista» = más de 0,5 m dentro de la línea de fondo); en la videoteca «cerca de la red» y «baja» no se pueden combinar (mismo grupo). Sin consignas propias de esta bola. |
| Chat | 19-10 08:11 | «bola corta alta cerca de la red» | **NUEVA #158** | **PARCIAL** | Igual: «dentro de la pista» + «pecho-hombro» o «por encima del hombro» | Igual que la anterior: sin nivel cerca de la red ni combinación en la videoteca. |
| Chat | 19-10 08:11 | «volea a media pista con el golpe de fondo derecha o reves (sin ser empuñadura de volea)» | **NUEVA #159** | **FALTA** | `technique.contact_type`: «volea» solo si no bota y está dentro de la línea de saque | Un impacto sin bote entre la línea de saque y el fondo queda sin clase; no se distingue swing de fondo de volea; ni condición ni filtro. Medible: la bola dice si botó. |
| Chat | 19-10 08:11 | «la app que hiciste completa como se arranca, se puede usar ahora?» | **NUEVA #160** | **PARCIAL** | Acceso directo «Tennisbio» (`app/shortcut.py`), ventana (`app/window.py`) | Arranca, pero los análisis de los 4 partidos no son válidos (golpes perdidos). |
| Chat | 19-10 08:11 | «como se enlazan los partidos de una jugadora ... tienen que estar el analisis junto» | **NUEVA #161** | **HECHO** | `docs/aplicacion_local.md` §2: un análisis por jugadora y golpe junta todos sus partidos (`analisis\<jugadora>_<golpe>`) |  |

## 2. FALTA (sin hacer) (22)

| Fuente | Fecha | Palabras del usuario / de la fuente | Registro | Estado | Prueba (código o web) | Qué falta / por qué |
|---|---|---|---|---|---|---|
| Chat | 10-10 17:27 | «la derecha de Elena Rybakina en 4 partidos completos» | #1 | **FALTA** | `3_analisis_completo.bat`; lanzado el 18-10 (petición PC 32) | El análisis de los 4 partidos encuentra como mucho el 43 % de sus golpes y el 29 % de sus saques (`audit.recall_items`, `point_count.py`): los resultados no valen. Sin arreglo de la detección todavía. |
| Chat | 18-10 21:08 | «lanza los 4 partidos completos» | #1 | **FALTA** | Lanzado (petición PC 32) | Resultado no válido: faltan más de la mitad de sus golpes. |
| CLAUDE.md | req. 7 | «Partido completo solo cuando la aplicación tenga todas las funciones» | #1 | **FALTA** |  | Se lanzó el 18-10 y el resultado no vale. |
| CLAUDE.md | Plan vigente 7 | «Ejecución de los 4 partidos en el PC (una vez)» | #1 | **FALTA** |  | Resultado no válido. |
| Matriz (literatura) | §3 | «Nuevo split step antes del siguiente golpe de la rival» | **NUEVA #176** | **FALTA** | — | La ventana acaba 0,8 s tras el impacto: medible alargándola. |
| YouTube | 18-10 Olivari 4 | ««Cómo» de la fase 1: «mirando la raqueta de la rival»» | **NUEVA #189** | **FALTA** | — | No está en `learn.py`. |
| Guía Ivanovic | hueco 10 | «Mano libre en la aceleración y el impacto (pliegue, que no cruce)» | **NUEVA #193** | **FALTA** | — | No hay medida ni punto de control (`impact.wrist_non_lateral` no existe). |
| Guía Ivanovic | hueco 18 | «Medidas de lado: codo por delante de la cadera, inclinación del tronco en la espera» | **NUEVA #196** | **FALTA** | — | No están en `practice.SIDE_METRICS`. |
| Guía Ivanovic | hueco 19 | «Progresión por etapas sin calendario y paso a pista» | **NUEVA #197** | **FALTA** | — | Pendiente de confirmar con el usuario (descartó la hoja de sesión). |
| Guía Ivanovic | hueco 20 | «Tiempo entre puntos (rutina) bajo presión» | **NUEVA #198** | **FALTA** | — | Opcional, fuera del golpe. |
| Estado del arte | 13-10 | «Bote: GBDT/CatBoost sobre la trayectoria» | **NUEVA #199** | **FALTA** | — | Sigue la heurística. |
| Estado del arte | 13-10 | «Pista: TennisCourtDetector (14 puntos) + refinado» | **NUEVA #200** | **FALTA** | — | Sigue la detección por líneas propia. |
| Estado del arte | 13-10 | «Marcador: rapidocr 3.x con PP-OCRv5» | **NUEVA #201** | **FALTA** | `pyproject.toml` sigue en rapidocr-onnxruntime 1.x | Hecho solo «OCR cuando cambia». |
| Estado del arte | 13-10 | «Bola: probar WASB» | **NUEVA #202** | **FALTA** | — | No probado. |
| Estado del arte | 13-10 | «3D: prueba A/B con MotionAGFormer» | **NUEVA #203** | **FALTA** | — | No probado. |
| Estado del arte | 13-10 | «Golpe: clasificador aprendido con F3Set (E2E-Spot/F3ED)» | **NUEVA #204** | **FALTA** | — | No hecho; ayudaría a la pérdida de golpes del 19-10. |
| Comparativa apps | §4.3 | «Volumen: unos 400 golpes con 4 partidos» | **NUEVA #205** | **FALTA** | — | Los 4 partidos dieron menos de la mitad de sus golpes. |
| Revisión completa | §3 B | «Passing y globo» | **NUEVA #209** | **FALTA** | — | Medible en parte (rival en la red + trayectoria); sin hacer. |
| Revisión completa | §3 B | «Dejada (bote muy corto en campo rival)» | **NUEVA #210** | **FALTA** | — | Medible con el bote de su bola; sin hacer. |
| Auditorías 17-10 | técnica #5 | «CHECKS de la mano en el armado da por hecho que va por debajo del hombro» | **NUEVA #211** | **FALTA** | `learn.CHECKS` aún dice «la mano por debajo de la línea del hombro» | Decir «a la altura que marca su valor». |
| Auditorías 17-10 | técnica #25 | «Pendiente de la guía: punta arriba/codo alto, terminación hacia adelante, codo libre» | **NUEVA #216** | **FALTA** | — | Ver huecos 3 y 9 de Ivanovic. |
| Auditorías 17-10 | técnica #26 | «Documentos desactualizados (aprendido_entrenadores §2 y §4)» | **NUEVA #217** | **FALTA** | — | Sin prueba de que se actualizaran. |

## 3. PARCIAL (a medias) (102)

| Fuente | Fecha | Palabras del usuario / de la fuente | Registro | Estado | Prueba (código o web) | Qué falta / por qué |
|---|---|---|---|---|---|---|
| Chat | 10-10 17:27 | «detección ligera de jugadores ... saber el lado y quién golpea; se la sigue teniendo en cuenta los cambios de lado» | #23 | **PARCIAL** | `identity.py` (ropa + icono de saque del marcador) | 19-10: fallos de identidad en los partidos completos; sin validar con datos anotados hasta `validation/recall_eval.py` (19-10), que aún no se ha corrido. |
| Chat | 10-10 17:27 | «Tipo de apoyo, anchura de la base, flexión de rodillas, rotación de cadera y hombros y su separación (X-factor), ángulo del codo, punto de impacto, cadena cinética, posición en pista» | #25 | **PARCIAL** | `technique.py`, `court_metrics.py`, `reliability.py` | Giro de hombros y X-factor en 2D salen «sesgo» y no se dan como valor suyo; rodillas con escorzo; impacto delante/detrás no medible desde detrás. El resto, hecho. |
| Chat | 10-10 18:05 | «Necesitas cámaras frontales, traseras y laterales?» | #79 | **PARCIAL** | `practice.py` (vista lateral de entreno, aparte y marcada) | Pocas derechas de lado medidas; no hay vistas laterales del partido (solo la cámara de fondo). |
| Chat | 10-10 18:05 | «half volleys» | #16 | **PARCIAL** | `technique.contact_type` («media volea»), condición «Contacto» | La clase existe pero no tiene técnica propia ni casos en los datos; la detección no está validada con medias voleas. |
| Chat | 10-10 18:09 | «Tiene que ser usable y entendible. Cómo hacen otras apps?» | #9 | **PARCIAL** | «Cópiala» como lección (`learn.LESSON`) | Nunca se ha visto con los datos completos y correctos de un partido (19-10: faltan golpes). |
| Chat | 10-10 18:12 | «screenshots de los golpes con más score de cada tipo» | #33 | **PARCIAL** | Videoteca ordenada por representatividad, calidad, tiempo y atípicos (`report_template.html`, `lib-sort`) | No hay orden por resultado del punto (CLAUDE.md lo pide en las galerías); «mejor técnica» no existe por diseño. |
| Chat | 11-10 09:02 | «este video no tiene ni una volea. Son derechas cerca de la red» | #16 | **PARCIAL** | `technique.contact_type` usa la pista y la bola | Volea solo dentro de la línea de saque (ver «volea a media pista»). |
| Chat | 11-10 09:05 | «yo no puedo validar nada a mano... Todo tiene que ser automático» | #45 | **PARCIAL** | `audit.py`, ciclo automático | El 19-10 el usuario detectó a mano que faltaban golpes: la auditoría no lo comprobaba hasta `audit.recall_items` (19-10). |
| Chat | 11-10 09:05 | «Estás usando lo más moderno posible de inteligencia artificial?» | #58 | **PARCIAL** | YOLO11-pose + RTMPose-x híbrido, TrackNetV3, RTMPose de raqueta, RTMW3D | Quedan sin probar los cambios marcados «Cambiar» en `docs/estado_del_arte.md` (bote, pista, OCR, WASB, clasificador de golpes): ver fuente «Estado del arte». |
| Chat | 11-10 09:05 | «Qué te dije de comparar las salidas de apps reales, lo llegaste a hacer?» | #74 | **PARCIAL** | `docs/comparativa_apps.md` | Comparación documental, no pantalla a pantalla con las apps. |
| Chat | 11-10 09:12 | «empieza con la validación automática» | #12 | **PARCIAL** | `scripts/validate_f3set.py`, `scripts/validate_racket.py`, `scripts/validate_recall.py` | Ninguna medida del cuerpo (codo, rodillas, pasos, apoyo) validada contra una referencia anotada. |
| Chat | 11-10 09:56 | «el grado de cierre de la muñeca vs raqueta» | #36 | **PARCIAL** | `racket_forearm` (ángulo 2D), «Retraso de la raqueta» | Ángulo proyectado, no la extensión real de la muñeca; poco fiable cerca del impacto. |
| Chat | 11-10 18:21 | «El informe como lo veo en el móvil?» | #2 | **PARCIAL** | `app/mobile.py` (copia sin conexión), `app/phone.py` (al Pixel por cable) | La copia directa al Pixel 8 no se ha probado en el teléfono (el usuario lo aplazó el 18-10). |
| Chat | 11-10 19:23 | «todos los escenarios nominales, Edge, corner, error ... Gestión fuentes, Algoritmia, Modelos IA, Procesamiento, Performance, Velocidad, Salida informe» | #13 | **PARCIAL** | `tests/` (unos 50 ficheros) | El caso «se pierden la mitad de los golpes de un partido real» no lo cubría ninguna prueba hasta el 19-10. |
| Chat | 11-10 19:23 | «steps y footwork» | #64 | **PARCIAL** | `footwork.py` | Tipos de paso solo cuando los pies se ven quietos ≥ 40 %; paso cruzado casi nunca detectado. |
| Chat | 11-10 19:23 | «Qué es lo que tendría que hacer para dar un golpe de derecha como la jugadora X... Y ahí ver todas las posibilidades» | #4 | **PARCIAL** | «Cópiala» (`learn.py`) | Faltan variantes (angulado, corta cerca de la red, volea a media pista) y datos correctos de los 4 partidos. |
| Chat | 12-10 13:14 | «como se que lo que se genera esta bien y cumple todos los requisitos» | #11 | **PARCIAL** | `audit.py`, `learn_check.py` | La auditoría comprueba la forma más que el contenido, y daba «OK» con golpes perdidos y peticiones sin hacer. |
| Chat | 12-10 16:30 | «videos de analisis de golpes ... eso lo puedes analizar e interpretar y ver como asociarlo al codigo?» | #15 | **PARCIAL** | `scripts/youtube_research.py`, `docs/aprendido_entrenadores.md` | Quedan mejoras 2, 9, 11 y 15 a medias (fuente YouTube). |
| Chat | 12-10 17:40 | «necesito verlo con el test rapido no con 1 hora» | #10 | **PARCIAL** | `2c_solo_informe.bat`, ciclo automático | Una medida nueva exige rehacer la pasada fina. |
| Chat | 12-10 17:40 | «o una bola cercana a la red» | #55 | **PARCIAL** | filtro «cerca de la red» de la videoteca (`LIBF`) | En la videoteca «cerca de la red», «corta», «baja» y «alta» están en el mismo grupo y no se pueden combinar; en «Cópiala» no hay nivel «cerca de la red». |
| Chat | 12-10 18:06 | «todos los tipos de footwork y desplazamiento ... desde que hace el split step y finaliza y como recupera» | #64 | **PARCIAL** | `footwork.py`, «Sus pies en este golpe» | Paso cruzado casi nunca; primer paso y ajuste «no medible» con tobillos que tiemblan; la ventana acaba 0,8 s tras el impacto. |
| Chat | 12-10 21:31 | «te puedes bajar otros videos de la jugadora practicando con otro enfoque de camaras» | #79 | **PARCIAL** | `scripts/practice_videos.py`, `practice.py` | Pocas derechas de lado. |
| Chat | 12-10 22:25 | «la meta ... es que yo pueda mejorar y basar mi derecha en ... rybakina» | #68 | **PARCIAL** | «Cópiala» | Sin datos correctos de los 4 partidos; faltan variantes pedidas. |
| Chat | 13-10 05:48 | «(punto 2) contienen todo lo hablado en los chats ... la matriz completa ... las 2000 y pico combinaciones» | #70 | **PARCIAL** | `learn_check.combos` | Las combinaciones salen de las condiciones existentes: las variantes que faltan (angulado, corta cerca de la red, volea a media pista) no están en ninguna combinación. |
| Chat | 13-10 05:48 | «(punto 3) el informe web contiene el conocimiento de los videos del analisis de derecha de youtube» | #71 | **PARCIAL** | consignas, errores y ejercicios de `learn.py` | Ver fuente YouTube. |
| Chat | 13-10 05:48 | «(punto 6) revisa de arriba a abajo el informe ... hay que añadir utilidad» | #73 | **PARCIAL** | diseño de `docs/diseno_definitivo.md` | Nunca revisado con los datos completos y correctos. |
| Chat | 13-10 05:48 | «(punto 8) derecha paralela en posicion cerrada golpeando parada bola plana en el lado derecho de la pista» | #69 | **PARCIAL** | `learn_check.USER_EXAMPLE` | Depende de tener golpes así; con los datos actuales casi nunca hay golpes exactos. |
| Chat | 13-10 06:09 | «no puedes depender de que se me ocurran a mi funcionalidades» | #78 | **PARCIAL** | matriz con fuentes, entrenadores, guía de Ivanovic | Esta revisión demuestra lo contrario: variantes pedidas por el usuario (angulado, corta cerca de la red, volea a media pista) se perdieron. |
| Chat | 13-10 13:16 | «la web es completa en ... modelo tecnico ... ux ... pedagogia ... meta» | #123 | **PARCIAL** | lección, plan, foco, glosario | Ver variantes que faltan y datos de los 4 partidos. |
| Chat | 13-10 13:51 | «el resto de derecha para devolver el saque y todas sus variantes» | #130 | **PARCIAL** | `returns.py` | Primer/segundo saque probable; pocos restos medidos. |
| Chat | 13-10 19:17 | «todos los escenarios de los cambios asociados a los modelos nuevos ... nominales, edge, corner, error» | #13 | **PARCIAL** | `tests/test_hybrid_pose.py`, `tests/test_fine_speed.py` | Ver fila 13. |
| CLAUDE.md | req. 1 | «todas sus variantes (bola rápida/lenta, alta/baja, corta/profunda, en carrera/parada/salto, cada apoyo, dirección, ataque/defensa)» | #5 | **PARCIAL** | `learn.CONDITIONS` (16 condiciones) | Todas las variantes listadas existen; faltan las que el usuario añadió en el chat (angulado, corta cerca de la red, volea a media pista). |
| CLAUDE.md | req. 1 | «pasos y juego de pies» | #64 | **PARCIAL** | `footwork.py` | Ver fila 64. |
| CLAUDE.md | req. 5 | «100 % automático» | #45 | **PARCIAL** | ciclo automático, auditoría | La pérdida de golpes no la detectó nada automático hasta el 19-10. |
| CLAUDE.md | req. 8 | «Cobertura de casos: nominales, límite, esquina y error» | #13 | **PARCIAL** | `tests/` | Ver fila 13. |
| CLAUDE.md | req. 10 | «móvil/nube al final» | #2 | **PARCIAL** | `app/mobile.py` | Pixel sin probar; nube descartada. |
| CLAUDE.md | Plan vigente 5 | «Validación automática de cada medida con clips públicos anotados» | #12 | **PARCIAL** | `scripts/validate_*.py` | Solo detección, clases, raqueta y pausa; ninguna medida del cuerpo. |
| CLAUDE.md | Informe | «Galerías ordenadas por calidad de captura, representatividad y resultado del punto» | **NUEVA #162** | **PARCIAL** | `lib-sort` (representativos, calidad, cronológico, atípicos) | No hay orden por resultado del punto (solo filtro). |
| CLAUDE.md | Identidad | «Identidad automática ... así se siguen los cambios de lado» | #23 | **PARCIAL** | `identity.py` | Fallos el 19-10. |
| CLAUDE.md | Métricas ampliadas | «Raqueta: altura de la cabeza, cara, trayectoria bajo-alto, lag, altura de la terminación» | #86 | **PARCIAL** | `racket.py`, `racket_face.py` | Lag proyectado; cara en el impacto estimada. |
| CLAUDE.md | Métricas ampliadas | «Pies: split step, reacción, pasos de ajuste, recuperación» | #88 | **PARCIAL** | `footwork.py` | Ver fila 88. |
| Matriz (literatura) | §1 | «Final del armado (máximo giro, raqueta más atrás)» | **NUEVA #163** | **PARCIAL** | `loaded` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz (literatura) | §1 | «Final de la extensión» | **NUEVA #164** | **PARCIAL** | `extension` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz (literatura) | §2 | «Giro de cadera y de hombros al final del armado» | **NUEVA #165** | **PARCIAL** | `shoulder_turn`, `hip_turn` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz (literatura) | §2 | «Separación cadera–hombros (X-factor)» | **NUEVA #166** | **PARCIAL** | `x_factor` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz (literatura) | §2 | «Cabeza quieta tras el impacto» | **NUEVA #167** | **PARCIAL** | `head_still_after_cm` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz (literatura) | §2 | «Hombros más girados que la cadera en el impacto» | **NUEVA #168** | **PARCIAL** | `shoulder_turn`, `hip_turn` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz (literatura) | §2 | «Transferencia de peso del armado al impacto» | **NUEVA #169** | **PARCIAL** | `weight_shift`, `com_over_feet` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz (literatura) | §2 | «Empuje de piernas («bajar y subir»)» | **NUEVA #170** | **PARCIAL** | `hip_rise` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz (literatura) | §3 | «Primer paso: tipo (gravity, jab, pivot, counter, cruzado, lateral)» | **NUEVA #171** | **PARCIAL** | — | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz (literatura) | §3 | «Cada paso nombrado: lateral (sin cruzar), cruzado, de carrera, hacia delante, hacia atrás, de ajuste» | **NUEVA #172** | **PARCIAL** | `step_kinds`, `approach_steps`, `approach_pattern` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz (literatura) | §3 | «Frenado: último paso largo con caída de la velocidad» | **NUEVA #173** | **PARCIAL** | `braking_step` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz (literatura) | §3 | «Patada atrás (tijera) tras el impacto» | **NUEVA #174** | **PARCIAL** | `kick_back` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz (literatura) | §3 | «Recuperación: tipo de cada paso de vuelta, cuándo empieza» | **NUEVA #175** | **PARCIAL** | `recovery_steps`, `recovery_pattern`, `recovery_first_step` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz (literatura) | §3 | «Orientación del pie (talón → dedo gordo respecto a la línea de fondo) en el armado y el impacto» | **NUEVA #177** | **PARCIAL** | `front_foot_angle_deg`, `back_foot_angle_deg`, `PLAUSIBLE` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz (literatura) | §3 | «Pivote sobre la punta del pie de atrás (talón arriba, punta apoyada)» | **NUEVA #178** | **PARCIAL** | `back_heel_lift`, `back_heel_lift_s`, `PIVOT_REF_S` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz (literatura) | §4 | «Raqueta al lado del cuerpo o por detrás de la espalda en el armado (debate WTA/ATP)» | **NUEVA #179** | **PARCIAL** | `racket_head_lateral`, `racket_plane` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz (literatura) | §4 | «Retraso de la muñeca (lag)» | **NUEVA #180** | **PARCIAL** | `racket_forearm` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz (literatura) | §4 | «Cara en el impacto» | **NUEVA #181** | **PARCIAL** | — | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz (literatura) | §4 | «Velocidad de la raqueta relativa entre golpes» | **NUEVA #182** | **PARCIAL** | `racket_speed_rel` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz (literatura) | §4 | «Posición de la mano en el mango» | **NUEVA #183** | **PARCIAL** | `hand_on_handle` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz (literatura) | §5 | «Altura de la bola en su vuelo, bote, punto más alto; contacto subiendo / arriba / cayendo» | **NUEVA #184** | **PARCIAL** | `flights`, `ball_phase`, `contact_vs_top` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz (literatura) | §5 | «Longitud del peloteo» | **NUEVA #185** | **PARCIAL** | `shot_in_point`, `shots_in_point` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz (literatura) | §5 | «Resto, globo, dejada, volea, subida a la red» | **NUEVA #186** | **PARCIAL** | `approach`, `play` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz (literatura) | §5 | «Ganador / error (forzado o no)» | **NUEVA #187** | **PARCIAL** | — | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz (literatura) | §5b | «Resto de primer o de segundo saque» | **NUEVA #188** | **PARCIAL** | `serve_number` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz pegada por el usuario | §6 | «Empuje de piernas / extensión triple (tobillo, rodilla, cadera)» | #84-98 (por sección) | **PARCIAL** | `hip_rise`, `hip_height` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz pegada por el usuario | §6 | «Rotación pélvica» | #84-98 (por sección) | **PARCIAL** | `hip_turn`, `t_max_hip_turn` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz pegada por el usuario | §6 | «Separación cadera–hombro (torque)» | #84-98 (por sección) | **PARCIAL** | `x_factor` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz pegada por el usuario | §6 | «Retraso de la muñeca (lag) y su liberación» | #84-98 (por sección) | **PARCIAL** | `racket_forearm` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz pegada por el usuario | §6 | «Carga: flexión de rodillas» | #84-98 (por sección) | **PARCIAL** | `hip_height` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz pegada por el usuario | §6 | «Pie de arrastre (pie trasero que se arrastra)» | #84-98 (por sección) | **PARCIAL** | `drag_foot` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz pegada por el usuario | §6 | «Caída de la raqueta por debajo de la bola» | #84-98 (por sección) | **PARCIAL** | `side_metrics`, `racket_drop_below_contact_cm` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz pegada por el usuario | §6 | «Cara de la raqueta en la caída y en el impacto» | #84-98 (por sección) | **PARCIAL** | `face_tilt` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz pegada por el usuario | §6 | «Trayectoria vertical del swing (de abajo arriba)» | #84-98 (por sección) | **PARCIAL** | `swing_low_to_high`, `swing` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz pegada por el usuario | §6 | «Golpe plano, liftado o cortado» | #84-98 (por sección) | **PARCIAL** | `swing` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz pegada por el usuario | §6 | «Botepronto (media volea)» | #84-98 (por sección) | **PARCIAL** | `contact_type` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz pegada por el usuario | §6 | «Volea de derecha» | #84-98 (por sección) | **PARCIAL** | `contact_type` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz pegada por el usuario | §6 | «Zona de impacto: delante de la cadera» | #84-98 (por sección) | **PARCIAL** | `side_metrics`, `contact_in_front_pct`, `contact_in_front_3d_pct` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz pegada por el usuario | §6 | «Latencia de reacción al golpe de la rival» | #84-98 (por sección) | **PARCIAL** | `split_landing_vs_opp_s`, `first_step_s` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz pegada por el usuario | §6 | «Apertura prematura de hombros (fuga de energía)» | #84-98 (por sección) | **PARCIAL** | `shoulders_open_first` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz pegada por el usuario | §6 | «Liberación anticipada de la muñeca («casting»)» | #84-98 (por sección) | **PARCIAL** | `side_metrics`, `lag_accel_deg`, `lag_pre_impact_deg` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz pegada por el usuario | §6 | «Fuerza en dirección incorrecta (horizontal o descendente)» | #84-98 (por sección) | **PARCIAL** | `swing_low_to_high` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz pegada por el usuario | §6 | «Ángulo real del swing de abajo arriba (+10° a +45°)» | #84-98 (por sección) | **PARCIAL** | `side_metrics`, `swing_angle_deg` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz pegada por el usuario | §6 | «Rodilla de atrás en la carga (110–130°) y de delante en el impacto» | #84-98 (por sección) | **PARCIAL** | `side_metrics`, `back_knee_loaded_deg`, `front_knee_impact_deg` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| Matriz pegada por el usuario | §6 | «Inclinación del tronco hacia delante o atrás en el impacto» | #84-98 (por sección) | **PARCIAL** | `side_metrics`, `trunk_lean_impact_deg` | Parcial en `docs/matriz_cobertura.md`: aproximado, 2D o solo en la vista lateral. |
| YouTube | mejora 2 | «Raqueta al lado o detrás de la espalda y adónde apunta la punta» | #100 | **PARCIAL** | `racket_head_lateral`, clase `racket_plane` | No existe «adónde apunta la punta» (`tip_points_to`). |
| YouTube | mejora 9 | «Caída por debajo de la bola» | #107 | **PARCIAL** | `practice.SIDE_METRICS` (vista lateral) | Desde la tele no; solo de lado. |
| YouTube | mejora 11 | «Frases con datos existentes (mano libre, terminación, base al terminar, desplazarse bajo)» | #109 | **PARCIAL** | `extension.wrist_non_lateral`, `finish.base_court_m` | Faltan `finish.elbow_non` y la cadera durante el desplazamiento. |
| YouTube | mejora 15 | «Examen interno R1-R25» | #113 | **PARCIAL** | `audit.py` §3 | Nada confirmado ni refutado con datos suficientes. |
| Guía Ivanovic | hueco 3 | «Clase de forma del armado: bucle verdadero, loop falso, recto atrás; tendencia «punta arriba / codo alto»» | **NUEVA #190** | **PARCIAL** | clase `takeback_loop` (`technique.py`) | Falta la tendencia «punta arriba / codo alto». |
| Guía Ivanovic | hueco 6 | «Alarmas por golpe: cara al cielo, punta hacia la red tras el giro, pausa arriba, caída bajo la rodilla, cabeza que sube, retrocede en el impacto» | **NUEVA #191** | **PARCIAL** | `ALARMS` en `report_template.html` (9 alarmas) | Faltan «punta hacia la red tras el giro», «caída bajo la rodilla» y «se mueve hacia atrás en el impacto»; la alarma de pausa usa una medida declarada no medible el 18-10. |
| Guía Ivanovic | hueco 9 | «Terminación «hacia adelante», «la mano libre recoge la raqueta», codo al terminar» | **NUEVA #192** | **PARCIAL** | clase `catch_racket` | Faltan el nivel «hacia adelante» en `technique.finish_class` y el codo libre al terminar (`finish.elbow_non`). |
| Guía Ivanovic | hueco 13 | ««Sus principios» (5-6 frases) y «Lo que la distingue»» | **NUEVA #194** | **PARCIAL** | «Su firma» (`a-sig`) | No hay «Sus principios». |
| Guía Ivanovic | hueco 17 | «Fuentes en COACH: Iino y Kojima 2001, Bahamonde y Knudson 2003, Kawamoto 2019, LTA, Wulf, autoinstrucciones» | **NUEVA #195** | **PARCIAL** | Wulf en `learn.py` | Faltan Iino, Kojima, Bahamonde, Knudson 2003, Kawamoto, LTA y el metaanálisis. |
| Comparativa apps | §4.4 | «Validación de cuerdas y 3D con referencia real» | **NUEVA #206** | **PARCIAL** | `scripts/validate_racket.py` | Sin referencia 3D real. |
| Comparativa apps | §3 Peor | «Golpes: sin volea, remate ni cortado» | **NUEVA #207** | **PARCIAL** | volea y media volea como clase; cortado como trayectoria | Sin técnica propia de volea, remate ni cortado. |
| Revisión completa | §2 fallo 17 | «Lógica duplicada JS/Python: calcular una vez en Python» | **NUEVA #208** | **PARCIAL** | `model.py` | La plantilla aún calcula en JavaScript partes de Comparar, la videoteca y la lección. |
| Auditorías 17-10 | técnica #15 | «Grados de estimaciones poco fiables como objetivo (cara en el impacto)» | **NUEVA #212** | **PARCIAL** | `impact.face_tilt` con «(estimación)» | Sigue mostrando grados en el impacto. |
| Auditorías 17-10 | técnica #17 | «Textos COACH (el porqué con fuente) en todas las claves de la lección» | **NUEVA #213** | **PARCIAL** | `explain.COACH` | Sin COACH: `footwork.recovery_start_s`, `class.recovery_first_step`, `footwork.rear_leg_step_after`, `class.approach_main`. |
| Auditorías 17-10 | técnica #18 | «Fuentes de Ivanovic §3 #17» | **NUEVA #214** | **PARCIAL** | Wulf | Ver hueco 17 de Ivanovic. |
| Auditorías 17-10 | técnica #22 | «Armado «antes» o «al» bote según el sitio» | **NUEVA #215** | **PARCIAL** | `explain.COACH` (`stroke.t_takeback`: «antes del bote») | Unificar en «armado completo cuando bota». |

## 4. NO MEDIBLE desde la tele (honesto) (31)

| Fuente | Fecha | Palabras del usuario / de la fuente | Registro | Estado | Prueba (código o web) | Qué falta / por qué |
|---|---|---|---|---|---|---|
| Chat | 11-10 19:23 | «grip en espera» | #7 | **NO MEDIBLE** | `learn.NOT_FROM_TV` (empuñadura), `explain.grip_compatible` (estimación) | La mano ocupa 20-40 px: el bisel no se ve. |
| CLAUDE.md | req. 1 | «empuñadura (en espera y al golpear, si se puede ver)» | #7 | **NO MEDIBLE** | `learn.NOT_FROM_TV` | No se ve desde la tele; estimación de compatibilidad en `explain.grip_compatible`. |
| Matriz (literatura) | §2 | «Pausa entre armado y swing» | en su documento | **NO MEDIBLE** | `pause_at_loaded` | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz (literatura) | §2 | «Momento de los picos en ms» | en su documento | **NO MEDIBLE** | — | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz (literatura) | §2 | «Rotación interna del hombro, pronación, desviaciones de la muñeca» | en su documento | **NO MEDIBLE** | — | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz (literatura) | §2 | «Contacto delante/detrás del cuerpo» | en su documento | **NO MEDIBLE** | — | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz (literatura) | §2 | «Mirada» | en su documento | **NO MEDIBLE** | — | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz (literatura) | §2 | «Fuerzas, momentos articulares» | en su documento | **NO MEDIBLE** | — | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz (literatura) | §3 | «Altura del split step» | en su documento | **NO MEDIBLE** | — | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz (literatura) | §4 | «Ángulo exacto de la trayectoria en el impacto» | en su documento | **NO MEDIBLE** | — | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz (literatura) | §4 | «Velocidad de la raqueta absoluta» | en su documento | **NO MEDIBLE** | — | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz (literatura) | §4 | «Empuñadura (bisel)» | en su documento | **NO MEDIBLE** | — | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz (literatura) | §4 | «Empuñadura en la espera y cambio de empuñadura» | en su documento | **NO MEDIBLE** | — | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz (literatura) | §4 | «Pronación, contribución de cada segmento, punto en el cordaje, presión de agarre» | en su documento | **NO MEDIBLE** | — | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz (literatura) | §5 | «Efecto (rpm), velocidad de salida, altura sobre la red» | en su documento | **NO MEDIBLE** | — | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz (literatura) | §5b | «Velocidad y efecto del saque que resta (km/h, rpm)» | en su documento | **NO MEDIBLE** | — | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz pegada por el usuario | §6 | «Reacción al suelo (fuerza contra la pista)» | #84-98 (por sección) | **NO MEDIBLE** | — | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz pegada por el usuario | §6 | «Pronación del antebrazo, flexión palmar y desviación de la muñeca» | #84-98 (por sección) | **NO MEDIBLE** | — | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz pegada por el usuario | §6 | «Mirada fija en el punto de impacto («quiet eye»)» | #84-98 (por sección) | **NO MEDIBLE** | `front_metrics`, `head_to_contact_idx` | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz pegada por el usuario | §6 | «Estabilidad lumbopélvica, activación de oblicuos (fugas de energía musculares)» | #84-98 (por sección) | **NO MEDIBLE** | — | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz pegada por el usuario | §6 | «Trayectoria horizontal del swing (de dentro a fuera)» | #84-98 (por sección) | **NO MEDIBLE** | — | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz pegada por el usuario | §6 | «Relajación y tensión de la empuñadura» | #84-98 (por sección) | **NO MEDIBLE** | — | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz pegada por el usuario | §6 | «Propiedades de la raqueta: swingweight, rigidez, encordado, tensión» | #84-98 (por sección) | **NO MEDIBLE** | — | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz pegada por el usuario | §6 | «Velocidad de la cabeza de la raqueta en km/h» | #84-98 (por sección) | **NO MEDIBLE** | `racket_speed_rel` | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz pegada por el usuario | §6 | «Velocidad angular de cada segmento en grados por segundo» | #84-98 (por sección) | **NO MEDIBLE** | `chain` | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz pegada por el usuario | §6 | «Tasa de desarrollo de fuerza contra el suelo» | #84-98 (por sección) | **NO MEDIBLE** | — | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz pegada por el usuario | §6 | «Efecto, ángulo y velocidad de salida de la bola» | #84-98 (por sección) | **NO MEDIBLE** | `ball_speed_avg_kmh` | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz pegada por el usuario | §6 | «Activación muscular (electromiografía)» | #84-98 (por sección) | **NO MEDIBLE** | — | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz pegada por el usuario | §6 | «Rangos articulares de muñeca, codo y hombro; cargas del codo» | #84-98 (por sección) | **NO MEDIBLE** | — | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Matriz pegada por el usuario | §6 | «Aerodinámica, altitud, temperatura, humedad» | #84-98 (por sección) | **NO MEDIBLE** | — | No observable desde una cámara de TV detrás del fondo (`docs/matriz_cobertura.md`). |
| Revisión completa | §3 A | «Efecto recibido (liftado, plano, cortado)» | en su documento | **NO MEDIBLE** | — | Bola pequeña y borrosa a 25-50 fps. |

## 5. NO APLICA (sustituido o descartado) (4)

| Fuente | Fecha | Palabras del usuario / de la fuente | Registro | Estado | Prueba (código o web) | Qué falta / por qué |
|---|---|---|---|---|---|---|
| Chat | 11-10 07:34 | «Añade vídeos de YouTube tipo Rybakina forehand analysis» | #62 | **NO APLICA** | Sustituido por el requisito 6 |  |
| Chat | 11-10 18:29 | «usar One Drive ... Qué otras opciones hay?» | #3 | **NO APLICA** | El 17-10 el usuario descartó la nube y el pago |  |
| Chat | 13-10 13:30 | «menos la hoja de sesion puedes hacer los 3» | #129 | **NO APLICA** | Hoja de sesión descartada |  |
| Comparativa apps | §4.2 | «Referencias con otras jugadoras» | en su documento | **NO APLICA** | Excluido por el requisito 6 |  |

## 6. HECHO, en breve (192)

| Fuente | Fecha | Petición | Registro | Prueba |
|---|---|---|---|---|
| Chat | 10-10 17:27 | parametrizable para otros jugadores y golpes (revés, saque, volea) | #18 | `config/players`, `config/strokes` (forehand, backhand, overhead) |
| Chat | 10-10 17:27 | Nunca subir vídeos a git. Datos extraídos e informes en C:\tenis\output | #19 | `config.py`, rutas de `config/local.yaml` |
| Chat | 10-10 17:27 | Sin CUDA. Usar ONNX Runtime (CPU o DirectML) nativo en Windows, sin WSL | #20 | `pose/estimator.py` (DmlExecutionProvider) |
| Chat | 10-10 17:27 | Dos pasadas: pasada barata ... pasada fina ±1 s | #21 | `stages.py` |
| Chat | 10-10 17:27 | quedarse con la cámara principal, descartar repeticiones y primeros planos | #22 | `scenes.py`, `replays.py` |
| Chat | 10-10 17:27 | leer el marcador de la TV con OCR (set/juego/tanteo, situaciones de presión) | #24 | `scoreboard.py` |
| Chat | 10-10 17:27 | Fases: preparación, armado, aceleración, impacto, terminación | #26 | `technique.PHASES` (8 fases) |
| Chat | 10-10 17:27 | Agregados: por partido/set, inicio vs final (fatiga), ganadores vs errores, presión | #27 | `findings.py`, `model.py` |
| Chat | 10-10 17:27 | informe HTML con gráficos y fotogramas con el esqueleto dibujado encima | #28 | `report.py`, `report_template.html` |
| Chat | 10-10 17:27 | Preparar el entorno y medir la velocidad real (fps de inferencia) | #29 | `scripts/benchmark.py`, `scripts/check_env.py` |
| Chat | 10-10 17:40 | Cuál es el estado del arte ... en lo que seríamos igual, mejor y peor | #30 | `docs/comparativa_apps.md`, `docs/estado_del_arte.md` |
| Chat | 10-10 18:05 | Cómo haces para hacer incrementales si añado videos a posteriori? | #31 | `pipeline.py` (huellas por etapa) |
| Chat | 10-10 18:05 | Revisas todo tipo de stances | #87 | `learn.CONDITIONS` «Apoyo» (abierto, semiabierto, neutro, cerrado), clase `movement` «en el aire» |
| Chat | 10-10 18:05 | bolas fuertes | #5 | `learn.CONDITIONS` «Velocidad de la bola» (de `technique.situation`) |
| Chat | 10-10 18:05 | centradas, laterales | #5 | `learn.CONDITIONS` «Bola centrada o abierta» (centrada, abierta, muy abierta) |
| Chat | 10-10 18:05 | cortas | #5 | `learn.CONDITIONS` «Dónde golpea» («dentro de la pista»), filtro «corta» de la videoteca |
| Chat | 10-10 18:07 | Cómo se puede expandir a otros golpes o jugadores? | #32 | `config/strokes`, `docs/aplicacion_local.md` §2 |
| Chat | 10-10 18:12 | N imágenes de un golpe completo para tomar como ejemplo | #33 | 8 fotogramas clave por golpe y tira de fases de la lección |
| Chat | 10-10 18:13 | hazme la maqueta del informe con datos inventados | #34 | `docs/maqueta-informe.html` |
| Chat | 11-10 07:34 | Faltan todas las medidas de la raqueta altura ángulos cuerdas abiertas cerradas en toda la fase del golpe | #35 | `racket.py`, `racket_face.py`; «Raqueta por fase» en un golpe |
| Chat | 11-10 08:22 | Falta toda la cadena completa del golpe... Desde el salto inicial takeback de la raqueta | #26 | `technique.PHASES` (espera/split → recuperación) |
| Chat | 11-10 08:49 | añade YOLO al benchmark | #29 | `scripts/benchmark.py` |
| Chat | 11-10 09:02 | smoke test ... y no procesar 20 gigas | #37 | `2_prueba_rapida.bat` |
| Chat | 11-10 09:56 | si las cuerdas apuntan al suelo, valla lateral, trasera, ángulos ... Es obligatorio | #8 | `racket_face.py`, `racket3d.py`; «Cuerdas:» en cada fase de la lección (`a-l-strings`) y «Raqueta por fase» |
| Chat | 11-10 17:24 | sigue con la dirección y profundidad del golpe | #38 | `court_metrics.shot_landing` |
| Chat | 11-10 17:32 | El lado del fondo de la pista | #39 | seguimiento con recorte (`stages.py`), `report.py` (`FAR_OK`) |
| Chat | 11-10 18:06 | un script para instalar todos los pre requisitos ... uno de uso rápido y otro completo | #40 | `1_instalar.bat`, `2_prueba_rapida.bat`, `3_analisis_completo.bat` |
| Chat | 11-10 18:21 | un golpe no pueden ser 8 pantallazos solo | #42 | vídeo con capas, curvas, «La bola y ella», Comparar |
| Chat | 11-10 18:27 | Mi pc no puede ser servidor | #43 | HTML sin servidor |
| Chat | 11-10 19:01 | Haz el punto 4 [exportación] | #41 | `export.py` (PDF y un MP4 por golpe), enlazados en «Datos» |
| Chat | 11-10 19:37 | Olvídate de videos míos o de entrenadores... de otras jugadoras | #44 | Sin entradas externas; vista lateral de entreno aparte |
| Chat | 11-10 19:40 | No quiero un PDF enorme ... No puedes además inventar datos | #46 | `limits.py`, `reliability.py`, PDF de pocas páginas |
| Chat | 11-10 19:48 | posición cabeza, altura al inicio y al final del cuerpo | #48 | `technique.stroke_curves`, «Bajar y subir» |
| Chat | 12-10 06:32 | Que modelo técnico y taxonomía has implementado? Cómo saber si es completo? | #47 | `docs/matriz_cobertura.md` |
| Chat | 12-10 11:41 | no puedo perder la sesion y el conocimiento del chat | #49 | `docs/estado_proyecto.md`, registros en `pc-logs` |
| Chat | 12-10 13:09 | para 4 partidos de 3 sets cuanto tardara? | #14 | ≈ 6 h por partido medidas (prueba 7, 14-10); el usuario cerró la velocidad |
| Chat | 12-10 14:37 | añade progreso y monitorizacion | #50 | `progreso.json`, registros con hora |
| Chat | 12-10 16:48 | no instales edge, usa brave | #52 | `screens.py` |
| Chat | 12-10 17:21 | no puedes pasar de 100 a 0 | #53 | pantallas antiguas plegadas en «Más» |
| Chat | 12-10 17:40 | cuando la bola bota que esta haciendo el jugador, o cuando la bola sale de la raqueta del rival o pasa la red | #54 | `report.ball_moments`, «La bola y ella» |
| Chat | 12-10 17:40 | un stance close con un golpe paralelo | #55 | Condiciones combinables «Apoyo» + «Dirección» en «Cópiala»; grupos «Apoyo» y «Dirección» de la videoteca |
| Chat | 12-10 17:40 | una imagen con la diferencia de alturas de la cabeza con barras horizontales | #56 | `heightBars` en `report_template.html` |
| Chat | 12-10 18:14 | el play del video no funciona | #65 | `startPlay` |
| Chat | 12-10 18:25 | añade fechas y duracion en los logs | #66 | `comun.ps1` |
| Chat | 12-10 22:25 | que ficheros y rutas y arbol de ficheros se generan y se validan | #83 | `audit.file_tree_items` |
| Chat | 12-10 22:35 | puedes dejar vistas complejas pero siempre extras ... no borrar el trabajo hecho | #67 | «Más», partes plegadas |
| Chat | 12-10 22:43 | se puede automatizar esa cadena de comandos tambien? | #80 | `prueba_rapida.ps1` → auditoría → `pc-logs` |
| Chat | 13-10 05:48 | (punto 10) para 10 golpes tardes 5 horas | #75 | ≈ 6 h por partido; cerrado por el usuario el 14-10 |
| Chat | 13-10 05:48 | (punto 10) un cincuenta por ciento de golpes dudosos | #76 | banderas de `review` |
| Chat | 13-10 08:41 | automatiza todo el ciclo en local | #119 | `scripts/auto_cycle.py`, `ciclo_automatico.ps1` |
| Chat | 13-10 09:47 | tracking del cuerpo respecto a la bola en los momentos clave ... fotogramas y medidas reales | #114 | `report.ball_moments` |
| Chat | 13-10 09:47 | que distancia baja el cuerpo y que distancia sube con fotogramas y barras horizontales | #115 | `technique.body_moves` |
| Chat | 13-10 09:47 | medir la distancia entre la 2 piernas ... de amplia la base | #116 | `technique.body_moves` (`base_court_m`) |
| Chat | 13-10 09:47 | el tronco al finalizar hacia que lado mira | #117 | clase `finish_trunk` |
| Chat | 13-10 11:21 | pasar de 10 vistas a 2 y el resto agrupadas | #122 | «Cópiala», «Sus golpes», «Más» |
| Chat | 13-10 11:25 | los videos no se pueden poner en pantalla completa | #120 | `toggleFull` |
| Chat | 13-10 11:25 | visualizar de forma separada todos los grafos y segmentos | #121 | `LPRESET`, `setLayers` |
| CLAUDE.md | req. 1 | taxonomía: espera, split step, primer paso, preparación, armado, aceleración, impacto, terminación, recuperación, ritmo | #26 | `learn.PHASES` + `FEET`, «Su ritmo, distancia y peso» |
| CLAUDE.md | req. 2 | vídeo primero, pocos números bien elegidos | #9 | `learn.LESSON` (≤ 3 claves por fase, vídeo de la fase), `tests/test_learn_web.py` |
| CLAUDE.md | req. 3 | Nada inventado ... diferencias solo si superan el error | #59 | `reliability.py`, `model.py` |
| CLAUDE.md | req. 4 | Cuerdas / orientación de la cara: obligatorio | #8 | «Cuerdas:» por fase en la lección (`report_template.html`) |
| CLAUDE.md | req. 6 | Sin fuentes externas; vista lateral de entreno aparte y marcada | #44 | `practice.py` |
| CLAUDE.md | req. 9 | un partido en horas, no días | #14 | ≈ 6 h por partido |
| CLAUDE.md | Vistas por golpe | La bola y ella; Bajar y subir; Base; Tronco al terminar | #114 | `report.ball_moments`, `technique.body_moves` |
| CLAUDE.md | Métricas ampliadas | altura del impacto, inclinación del tronco, brazo no dominante, cabeza ±50 ms, terminación | #85 | `technique.py` |
| CLAUDE.md | Situación | rápida/lenta, centrada/abierta, corta/profunda, baja/media/alta, ataque/neutra/defensa, apoyo | #90 | `technique.situation`, `learn.CONDITIONS` |
| CLAUDE.md | Situación | Media volea: solo candidata | #16 | `technique.contact_type` |
| CLAUDE.md | Informe | Secuencia de 8 fotogramas clave, estroboscópica y tira de contactos | #33 | `report_template.html` (tira de fases, «El recorrido del brazo») |
| Matriz (literatura) | §1 | Golpe del rival → split step | en su documento | `ready` |
| Matriz (literatura) | §1 | Inicio del giro de bloque (preparación) | en su documento | `takeback` |
| Matriz (literatura) | §1 | Inicio del swing hacia delante | en su documento | `acceleration` |
| Matriz (literatura) | §1 | Impacto | en su documento | — |
| Matriz (literatura) | §1 | Final de la terminación | en su documento | `finish` |
| Matriz (literatura) | §1 | Primer paso de recuperación | en su documento | `recovery` |
| Matriz (literatura) | §2 | Postura de espera (rodillas, base, peso) | en su documento | `body_height`, `base_width`, `hip_height` |
| Matriz (literatura) | §2 | Mano libre en la garganta de la raqueta en la espera / giro de bloque | en su documento | `hands_apart`, `ready_hands` |
| Matriz (literatura) | §2 | Momento del armado respecto al bote ("armado completo al botar") | en su documento | `loaded_vs_bounce` |
| Matriz (literatura) | §2 | Brazo libre extendido y cruzado | en su documento | `elbow_non`, `shoulder_abd_non` |
| Matriz (literatura) | §2 | Carga de la pierna exterior / descenso de cadera | en su documento | `hip_height`, `weight_loaded_to_non` |
| Matriz (literatura) | §2 | Peso entre los pies / equilibrio | en su documento | `com_over_feet`, `head_over_base`, `trunk_tilt` |
| Matriz (literatura) | §2 | Cadena cinética (orden pelvis → tronco → brazo → antebrazo) | en su documento | — |
| Matriz (literatura) | §2 | Altura del contacto (respecto a rodilla, cadera, hombro) | en su documento | `wrist_dom_height`, `wrist_dom_vs_hip`, `wrist_dom_vs_shoulder` |
| Matriz (literatura) | §2 | Separación lateral del contacto | en su documento | `wrist_dom_lateral` |
| Matriz (literatura) | §2 | Ángulo del codo en el impacto (brazo recto / doble flexión) | en su documento | `elbow_dom`, `arm` |
| Matriz (literatura) | §2 | Cabeza estable en el impacto | en su documento | `head_motion_impact_cm` |
| Matriz (literatura) | §2 | Extensión tras el contacto | en su documento | `arm_extension`, `swing_rise_after` |
| Matriz (literatura) | §2 | Terminación sobre el hombro / limpiaparabrisas / alrededor / invertida | en su documento | `finish` |
| Matriz (literatura) | §2 | "3 × 90°" al final | en su documento | `finish_3x90` |
| Matriz (literatura) | §2 | Paso adelante de la pierna trasera tras el impacto | en su documento | `rear_leg_step_after` |
| Matriz (literatura) | §2 | Altura y separación del codo (armado e impacto) | en su documento | `elbow_dom_vs_shoulder`, `elbow_dom_lateral` |
| Matriz (literatura) | §3 | Split step: aterrizaje respecto al golpe del rival | en su documento | `ready`, `takeback_after_opp` |
| Matriz (literatura) | §3 | Split step: despegue y aterrizaje respecto al golpe del rival | en su documento | `split_takeoff_vs_opp_s`, `split_landing_vs_opp_s` |
| Matriz (literatura) | §3 | Presencia del split | en su documento | `ready` |
| Matriz (literatura) | §3 | Velocidad 0,2 s antes y después del split | en su documento | `speed_pre_split_mps`, `speed_post_split_mps` |
| Matriz (literatura) | §3 | Primer paso: momento (reacción) | en su documento | `first_step_s` |
| Matriz (literatura) | §3 | Primer paso: dirección correcta respecto a la bola | en su documento | `first_step_right_way` |
| Matriz (literatura) | §3 | Número de pasos hasta la bola | en su documento | `steps_to_impact` |
| Matriz (literatura) | §3 | Longitud de cada paso; anchura del primero | en su documento | `first_step_length_m`, `last_step_length_m` |
| Matriz (literatura) | §3 | Pasos de ajuste | en su documento | `adjustment_steps` |
| Matriz (literatura) | §3 | Distribución lateral / delante / atrás | en su documento | `move_direction` |
| Matriz (literatura) | §3 | Cambios de dirección | en su documento | `direction_changes` |
| Matriz (literatura) | §3 | Velocidad media y máxima de carrera | en su documento | `peak_speed_mps`, `speed_at_impact_mps` |
| Matriz (literatura) | §3 | Recorrido hasta la bola | en su documento | `path_m` |
| Matriz (literatura) | §3 | Tipo de apoyo (abierto, semiabierto, neutro, cerrado) | en su documento | `stance_loaded`, `stance_impact` |
| Matriz (literatura) | §3 | Subtipos: abierto de ataque, abierto defensivo, neutro de ataque | en su documento | `stance_role` |
| Matriz (literatura) | §3 | Pierna que carga | en su documento | `weight_loaded_to_non` |
| Matriz (literatura) | §3 | En carrera, en salto, a un pie, deslizando | en su documento | `movement` |
| Matriz (literatura) | §3 | Última zancada más larga en carrera | en su documento | `last_step_length_m` |
| Matriz (literatura) | §3 | Recuperación: distancia, dirección, tiempo | en su documento | `off_centre_at_opp_hit_m`, `moving_at_opp_hit_mps` |
| Matriz (literatura) | §3 | Rodear la bola para la derecha invertida | en su documento | `around_ball` |
| Matriz (literatura) | §3 | Base y anchura de la base sobre la pista | en su documento | `base_court_m`, `feet_move_m` |
| Matriz (literatura) | §4 | Forma del armado: bucle, recto, "pat the dog" | en su documento | `takeback`, `takeback_face` |
| Matriz (literatura) | §4 | Inicio de la aceleración respecto al bote; girar mientras se desplaza | en su documento | `acceleration_vs_bounce`, `takeback_vs_first_step` |
| Matriz (literatura) | §4 | Altura de la mano en el armado (no por encima de la cabeza) | en su documento | `wrist_dom_vs_shoulder` |
| Matriz (literatura) | §4 | Cara de la raqueta al final del armado | en su documento | `face_tilt`, `face_points_to` |
| Matriz (literatura) | §4 | Caída de la raqueta antes de acelerar | en su documento | `racket_head_vs_wrist`, `wrist_drop` |
| Matriz (literatura) | §4 | Trayectoria de abajo arriba (signo) / liftado-plano-cortado | en su documento | `swing_low_to_high`, `swing` |
| Matriz (literatura) | §4 | Empuñadura: "compatible con este / semioccidental-occidental" | en su documento | `grip_compatible` |
| Matriz (literatura) | §5 | Bote: profundidad, anchura, dentro/fuera | en su documento | `shot_bounce_m`, `shot_in`, `shot_depth_m` |
| Matriz (literatura) | §5 | Dirección cruzada, paralela, al centro, invertidas | en su documento | `shot_direction`, `shot_type` |
| Matriz (literatura) | §5 | Velocidad media de la bola en pista | en su documento | `ball_speed_avg_kmh` |
| Matriz (literatura) | §5 | Qué hace ella en cada momento de la bola (cruza la red, bota, punto más alto) | en su documento | `ball_net`, `ball_bounce`, `ball_top` |
| Matriz (literatura) | §5 | Curvas de altura (cabeza, cadera, mano, cabeza de la raqueta) a lo largo del golpe, con su curva típica y su franja | en su documento | `stroke_curves`, `_typical_curves` |
| Matriz (literatura) | §5 | Fase ataque / neutra / defensa | en su documento | `intent` |
| Matriz (literatura) | §5 | Calidad del golpe (sustituto: profundidad, anchura, velocidad media) | en su documento | `shot_quality_proxy` |
| Matriz (literatura) | §5 | Puntos ganados en ataque / en defensa | en su documento | `point_won` |
| Matriz (literatura) | §5 | Presión, set, fatiga | en su documento | — |
| Matriz (literatura) | §5b | Resto: reconocerlo (saca la rival y es su primer golpe del punto) | en su documento | `play`, `return_of_serve` |
| Matriz (literatura) | §5b | Dirección del saque recibido: abierto, al cuerpo, a la T | en su documento | `serve_dir` |
| Matriz (literatura) | §5b | Lado del resto: iguales / ventaja | en su documento | `return_side` |
| Matriz (literatura) | §5b | Resto: posición de espera | en su documento | `return_ready_depth_m` |
| Matriz (literatura) | §5b | Resto: entrar hacia la bola | en su documento | `return_step_in_m` |
| Matriz (literatura) | §5b | Resto: split step respecto al saque | en su documento | `split_landing_vs_opp_s` |
| Matriz (literatura) | §5b | Resto: armado corto (bloqueo) o swing completo; terminación | en su documento | `return_type`, `return_type`, `takeback` |
| Matriz (literatura) | §5b | Resto: dirección y profundidad de su resto | en su documento | `shot_type`, `shot_depth_m` |
| Matriz (literatura) | §5b | Resto: tiempo que tiene desde el saque | en su documento | `ball_speed`, `time_available_s` |
| Matriz pegada por el usuario | §6 | Giro de hombros (unit turn) | #84-98 (por sección) | `shoulder_turn`, `shoulder_turn`, `hands_apart` |
| Matriz pegada por el usuario | §6 | Extensión del codo | #84-98 (por sección) | `elbow_dom`, `arm_extension` |
| Matriz pegada por el usuario | §6 | Cabeza estable y eje vertical | #84-98 (por sección) | `head_motion_cm`, `head_still_after_cm`, `head_over_base` |
| Matriz pegada por el usuario | §6 | Brazo recto o doble flexión | #84-98 (por sección) | `arm`, `elbow_dom` |
| Matriz pegada por el usuario | §6 | Brazo libre paralelo a la línea de fondo en el giro; distancia a la bola | #84-98 (por sección) | `shoulder_abd_non`, `elbow_non`, `wrist_dom_lateral` |
| Matriz pegada por el usuario | §6 | Brazo libre recogido al pecho tras el contacto («catch») | #84-98 (por sección) | `wrist_non_lateral` |
| Matriz pegada por el usuario | §6 | Inclinación lateral del tronco | #84-98 (por sección) | `trunk_tilt` |
| Matriz pegada por el usuario | §6 | Bucle de la preparación (forma) | #84-98 (por sección) | `takeback`, `takeback_path`, `takeback_loop` |
| Matriz pegada por el usuario | §6 | Caída de la raqueta por debajo de la mano | #84-98 (por sección) | `racket_head_vs_wrist`, `wrist_drop` |
| Matriz pegada por el usuario | §6 | Apoyos abierto, semiabierto, neutro, cerrado | #84-98 (por sección) | `stance_impact`, `stance_loaded` |
| Matriz pegada por el usuario | §6 | Apoyo en suspensión (salto) | #84-98 (por sección) | `movement` |
| Matriz pegada por el usuario | §6 | Apoyo abierto extremo defensivo | #84-98 (por sección) | `stance_role` |
| Matriz pegada por el usuario | §6 | Split step | #84-98 (por sección) | `split_landing_vs_opp_s` |
| Matriz pegada por el usuario | §6 | Pasos de ajuste | #84-98 (por sección) | `adjustment_steps` |
| Matriz pegada por el usuario | §6 | Pasos cruzados | #84-98 (por sección) | `crossover_steps`, `step_kinds` |
| Matriz pegada por el usuario | §6 | Paso de ataque hacia dentro de la pista (step-in) | #84-98 (por sección) | `step_in` |
| Matriz pegada por el usuario | §6 | Pasos de recuperación (laterales o cruzados) | #84-98 (por sección) | `recovery_pattern`, `recovery_first_step` |
| Matriz pegada por el usuario | §6 | Terminación sobre el hombro contrario | #84-98 (por sección) | `finish` |
| Matriz pegada por el usuario | §6 | Terminación en látigo sobre el mismo hombro (buggy whip) | #84-98 (por sección) | `finish` |
| Matriz pegada por el usuario | §6 | Terminación baja, a la cintura contraria | #84-98 (por sección) | `finish` |
| Matriz pegada por el usuario | §6 | Adaptación a bola rápida, corta, alta, abierta | #84-98 (por sección) | `ball_speed`, `depth`, `ball_height` |
| Matriz pegada por el usuario | §6 | Dirección: cruzado, paralelo, dentro-fuera, dentro-dentro | #84-98 (por sección) | `shot_type` |
| Matriz pegada por el usuario | §6 | Zona de impacto: altura y separación lateral | #84-98 (por sección) | `wrist_dom_vs_hip`, `wrist_dom_lateral` |
| Matriz pegada por el usuario | §6 | Equilibrio al terminar | #84-98 (por sección) | `head_over_base`, `trunk_tilt` |
| Matriz pegada por el usuario | §6 | Superficie de la pista | #84-98 (por sección) | `surface`, `yaml` |
| YouTube | mejora 1 | Líneas dibujadas sobre el fotograma | #99 | `coachLines` en `report_template.html` |
| YouTube | mejora 3 | Altura y separación del codo | #101 | `elbow_dom_vs_shoulder`, `elbow_dom_lateral` |
| YouTube | mejora 4 | Punta de la raqueta respecto a la cabeza | #102 | `loaded.racket_tip_vs_head` en `learn.LESSON` |
| YouTube | mejora 5 | Transferencia de peso | #103 | `stroke.weight_shift` |
| YouTube | mejora 6 | Empuje de piernas | #104 | `stroke.hip_rise` |
| YouTube | mejora 7 | Ritmo con la bola | #105 | `acceleration_vs_bounce` |
| YouTube | mejora 8 | Frenado de los hombros | #106 | `stroke.shoulder_brake` en `learn.PHASES` |
| YouTube | mejora 10 | Gira mientras corre | #108 | `takeback_vs_first_step` |
| YouTube | mejora 12 | Lo que la distingue | #110 | «Su firma» (`a-sig`) |
| YouTube | mejora 13 | Consigna y error que evita, por fase | #111 | `learn.cp` (cue, mistake, drill) |
| YouTube | mejora 14 | Estilo en una frase | #112 | «Estilo de su derecha» (`learn_check.py`) |
| YouTube | 17-10 (3 vídeos) | Tira de fases con foto real y avance fotograma a fotograma | en su documento | lección (commit 17-10 19:33) |
| YouTube | 18-10 Olivari 1-3 | Síntomas tarde/larga/red con sus medidas; cabeza quieta tras el impacto | en su documento | `learn.LATE_SIGNS`, `stroke.head_still_after_cm` |
| Guía Ivanovic | hueco 1 | Corregir COACH de la pausa: sin pausa entre armado y swing | en su documento | `explain.COACH` («El bucle debe ser continuo…») |
| Guía Ivanovic | hueco 2 | Llevar a Cópiala takeback_vs_net, mano y codo en el armado, terminación alta, contact_vs_top, dur_preparation | en su documento | `learn.LESSON` y `learn.PHASES` |
| Guía Ivanovic | hueco 4 | «Su ritmo con la bola» y panel «Timing, distancia y peso» | en su documento | «Su ritmo, distancia y peso» (`a-rhythm`) |
| Guía Ivanovic | hueco 5 | Índice «Si te pasa…» | en su documento | `learn.LATE_SIGNS`, «Si te pasa…» |
| Guía Ivanovic | hueco 7 | «Cómo comprobarlo» en cada punto de control | en su documento | `learn.CHECKS` |
| Guía Ivanovic | hueco 8 | Glosario: los ~14 términos que faltan | en su documento | `learn.GLOSSARY` |
| Guía Ivanovic | hueco 11 | Pies según la distancia que corre | en su documento | «Cambia con lo que corre hasta la bola» (`L_BY` en la lección) |
| Guía Ivanovic | hueco 12 | Último apoyo y bucle respecto al bote y a los últimos pasos | en su documento | `stroke.last_plant_vs_bounce`, `stroke.loaded_vs_last_plant` en `learn.FEET` |
| Guía Ivanovic | hueco 14 | Táctica medida: cambios de dirección, secuencias, botes en los últimos 2 m, cómo usa su derecha | en su documento | «Cómo usa su derecha» (`a-tac`) |
| Guía Ivanovic | hueco 15 | Bajo presión: también dirección y profundidad | en su documento | «Cómo usa su derecha» (bajo presión) |
| Guía Ivanovic | hueco 16 | Resto: clase bloqueo | en su documento | `returns.return_type` |
| Estado del arte | 13-10 | Pose: RTMPose-x sobre el recorte, con pies | en su documento | híbrido YOLO11 + RTMPose-x (`config/default.yaml`) |
| Estado del arte | 13-10 | Cortes de plano: TransNetV2 | en su documento | `scripts/export_transnetv2.py` |
| Estado del arte | 13-10 | Ejecución: lotes, FP16, sesiones persistentes; una sola decodificación d3d11va | en su documento | `io/video.py`, `fine_ahead.py` |
| Comparativa apps | §4.1 | Interpretación: decir qué hacer, no solo qué cambia | en su documento | consignas, «Si te pasa…», «Tu plan» (`learn.py`) |
| Revisión completa | §2 fallos 1-16, 18-19 | Identidad por golpe, cara en el impacto, cadena suavizada, escala por fotograma, ventana, desentrelazado, errores por go | en su documento | `stages.py`, `body_scale.py`, `model.py`, `findings.py`, `io/video.py`, `pose/estimator.py` |
| Auditorías 17-10 | técnica #1-4, 6-14, 16, 19-21, 23-24 | Textos contradictorios, claves de la lección, intent y width, glosario | en su documento | `learn.py`, `explain.py` (commits 17-10 14:30-15:16) |
| Auditorías 17-10 | peticiones R1-R10, fallos de código | intent/width, vídeo primero, fiabilidad en todas las pantallas, cuerdas en la lección, informe vacío, exportación enlaza | en su documento | commits 17-10 14:30-15:26 (`tests/test_learn_web.py`) |

## 7. Correcciones al registro

No se ha borrado ninguna fila. Cambian estas:

| Fila | Antes | Ahora | Por qué |
|---|---|---|---|
| #1 | NO (pendiente por diseño) | FALTA | Lanzado el 18-10; el resultado no vale (golpes perdidos) |
| #2 | NO (aplazado) | PARCIAL | Copia al móvil hecha (`app/mobile.py`, `app/phone.py`); el Pixel, sin probar |
| #3 | NO (aplazado) | NO APLICA | El usuario descartó la nube y el pago (17-10) |
| #5 | PARCIAL | PARCIAL | Se añade lo que faltaba de su mensaje: angulado, corta cerca de la red, volea a media pista |
| #8 | PARCIAL | HECHO | Las cuerdas ya salen en cada fase de la lección (`a-l-strings`) |
| #14, #75, #125 | NO | HECHO | ≈ 6 h por partido; el usuario cerró la velocidad el 14-10 («si se pierde calidad no tocamos nada») |
| #16 | PARCIAL | PARCIAL | Se añade la volea a media pista |
| #23 | HECHO | PARCIAL | Fallos de identidad el 19-10, sin validar |
| #25 | HECHO | PARCIAL | Giro de hombros y X-factor en 2D no se dan (sesgo); rodillas con escorzo |
| #33 | HECHO | HECHO | Sin orden por resultado: se registra aparte (galerías) |
| #55 | PARCIAL | PARCIAL | Detalle: cerrado + paralela sí se combinan; «cerca de la red» no |
| #102, #106, #110, #112 | HECHO sin prueba | HECHO con prueba | Se rellena dónde está |

## 8. Cómo se evita que vuelva a pasar

- **`scripts/check_requests.py`** (`tennisbio.requests_check`). Comprueba que cada fila del registro:
  - tiene un estado válido;
  - si es HECHO, dice dónde está, y cada `fichero` y `módulo.nombre` que cita existe de verdad en el código;
  - si no es HECHO, dice qué falta.
  Si algo de eso no se cumple, falla. Después lista primero todo lo que no está HECHO. Las pruebas están en `tests/test_check_requests.py`.
- **Auditoría** (`audit.to_markdown`). Empieza con «Peticiones del usuario SIN TERMINAR: N de M», con cada una y lo que falta, antes de cualquier comprobación que pase.
  - Una petición sin terminar ya no puede salir como «pocos datos».
  - Las variantes que el usuario nombró y no existen (angulado, corta cerca de la red, volea a media pista) salen como ✘ en «Situaciones».
- **Revisión automática del PC** (`scripts/auto_cycle.py review`). Pone ese mismo bloque justo debajo del veredicto. «OK» ya no puede leerse como «todo hecho».
- **Regla de trabajo:**
  - Cada mensaje nuevo del usuario se apunta en el registro con sus propias palabras, una fila por variante, nunca resumido.
  - Una fila pasa a HECHO solo con su prueba en el código, comprobada por el script.
