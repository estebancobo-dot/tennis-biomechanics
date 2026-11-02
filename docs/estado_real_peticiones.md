# Estado real de las peticiones (generado por `scripts/real_status.py`; no editar a mano)

226 peticiones (sin las que no aplican). «HECHO» en el registro es la etiqueta de Claude; aquí cuenta solo lo que se comprueba.

| Nivel | Peticiones |
|---|---|
| 0 sin construir | 23 |
| 1 construido, sin comprobar | 104 |
| 2 comprobación que falla | 57 |
| 3 comprobado en salidas | 42 |
| 4 validado con verdad | 0 |
| 5 aceptado por el usuario | 0 |

| # | Petición | Registro | Nivel | Lo que comprueba la auditoría |
|---|---|---|---|---|
| 4 | Responder de forma profesional a «¿qué hay que hacer para pegar como X?», con todas las po | PARCIAL | 2 comprobación que falla | 201 comprobaciones: 1 falta, 23 pocos datos, 177 ok; la peor: «La lección: como mucho 3 claves por fase, cada una con su valor, ejercicio y  |
| 5 | Taxonomía completa con todas las variantes (bola rápida/lenta, alta/baja, corta/profunda,  | PARCIAL | 2 comprobación que falla | 32 comprobaciones: 1 falta, 7 pocos datos, 24 ok; la peor: «La lección: como mucho 3 claves por fase, cada una con su valor, ejercicio y cóm |
| 6 | Juego de pies: split step, primer paso, ajuste, reacción, recuperación (11-10 08:22, 19:23 | PARCIAL | 2 comprobación que falla | 35 comprobaciones: 1 pocos datos, 34 ok; la peor: «3. Pies y desplazamiento · Presencia del split» (se mide (100% de los golpes); el informe |
| 7 | Empuñadura en la espera y al golpear (11-10 19:23) | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 5 comprobaciones: 5 ok |
| 9 | Información, no tablas; profesional, «con sentido humano», nivel de las apps punteras (10- | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 10 comprobaciones: 1 aviso, 9 ok; la peor: «Tablas a la |
| 10 | Ver los cambios en la prueba rápida, sin 1 h (12-10 17:32, 17:40) | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 11 comprobaciones: 11 ok |
| 11 | Validar solo que las salidas reales tienen todo lo pedido y todos los casos del modelo y l | PARCIAL | 2 comprobación que falla | 191 comprobaciones: 16 pocos datos, 175 ok; la peor: «1. Fases · Golpe del rival → split step» (se mide (100% de los golpes); el informe lo  |
| 12 | Validar cada medida con clips públicos anotados; el usuario no valida a mano (11-10 09:05, | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 1 comprobaciones: 1 ok |
| 13 | Casos nominales, límite, esquina y error en fuentes, algoritmos, IA, procesado, rendimient | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#13); no se comprueba en las salidas: en los tests del código (uv run pytest, pc-logs:pruebas.log), no en las sa |
| 15 | Bajar y analizar vídeos de entrenadores de YouTube para aprender y encontrar huecos (12-10 | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 1 comprobaciones: 1 ok |
| 16 | Distinguir por contexto (derecha junto a la red o volea) y cubrir las medias voleas (10-10 | PARCIAL | 2 comprobación que falla | 5 comprobaciones: 3 pocos datos, 2 ok; la peor: «Volea a media pista con golpe de fondo (#159)» (0 golpes de 193 (la clase «Contacto» se pud |
| 17 | Una entrada que se entienda sola: «no entiendo nada ni cómo usarla» (12-10 16:22) | PARCIAL | 2 comprobación que falla | 10 comprobaciones: 1 falta, 1 pocos datos, 8 ok; la peor: «La lección: como mucho 3 claves por fase, cada una con su valor, ejercicio y cómo |
| 18 | Herramienta Python cinemática 2D, 1 jugador y 1 golpe, parametrizable (10-10 17:27) | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 19 | Vídeos y salidas fuera del repo, rutas por configuración (10-10 17:27) | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 20 | Windows nativo sin NVIDIA ni WSL, ONNX en CPU o DirectML (10-10 17:27) | HECHO | 3 comprobado en salidas | 4 comprobaciones: 4 ok |
| 21 | Dos pasadas, barata y fina de ±1 s (10-10 17:27) | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 22 | Solo la cámara principal, sin repeticiones ni primeros planos (10-10 17:27) | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 24 | OCR del marcador y presión (10-10 17:27) | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 26 | Fases y cadena completa, del salto inicial a la terminación (10-10 17:27; 11-10 08:22) | HECHO | 3 comprobado en salidas | 8 comprobaciones: 8 ok |
| 27 | Agregados por partido y set, fatiga, ganadores y errores, presión (10-10 17:27) | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 28 | Informe HTML con gráficos y esqueleto (10-10 17:27) | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 29 | Fase 0: entorno y fps reales, con YOLO (10-10 17:27; 11-10 08:49) | HECHO | 3 comprobado en salidas | 4 comprobaciones: 4 ok |
| 30 | Estado del arte: igual, mejor o peor que otras apps (10-10 17:40; 11-10 09:05, 18:06) | HECHO | 1 construido, sin comprobar | no se comprueba en las salidas: documento de estado del arte (docs), no una salida |
| 31 | Procesado incremental al añadir vídeos (10-10 18:05) | HECHO | 1 construido, sin comprobar | no se comprueba en las salidas: proceso (caché por etapas), no una salida |
| 32 | Ampliable a otros golpes y jugadores (10-10 18:07) | HECHO | 1 construido, sin comprobar | no se comprueba en las salidas: configuración (config/players, config/strokes), no una salida |
| 33 | Capturas de los mejores golpes de cada tipo y N imágenes de un golpe (10-10 18:12) | HECHO | 3 comprobado en salidas | 8 comprobaciones: 8 ok |
| 34 | Maqueta con datos inventados, con apoyos (10-10 18:13; 12-10 17:21) | HECHO | 1 construido, sin comprobar | no se comprueba en las salidas: maqueta (docs/maqueta-informe.html), no una salida |
| 35 | Medidas de la raqueta (altura, ángulos) en todo el golpe; qué miden los profesionales (11- | HECHO | 2 comprobación que falla | 11 comprobaciones: 2 pocos datos, 9 ok; la peor: «6. Matriz del usuario · Caída de la raqueta por debajo de la bola» (vista lateral de entre |
| 36 | Mano y antebrazo, cierre de la muñeca (11-10 09:56, 10:19) | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 3 comprobaciones: 3 ok |
| 37 | Prueba en local sin procesar 20 GB (11-10 09:02) | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 38 | Dirección y profundidad del golpe (11-10 17:24) | HECHO | 2 comprobación que falla | 6 comprobaciones: 1 pocos datos, 5 ok; la peor: «5. Bola, resultado y contexto · Bote: profundidad, anchura, dentro/fuera» (se mide (50% de  |
| 39 | Lado del fondo de la pista (11-10 17:32-17:33) | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 40 | Scripts de instalación, uso rápido y completo, sin leer nada (11-10 18:06, 18:21) | HECHO | 1 construido, sin comprobar | no se comprueba en las salidas: scripts de doble clic (instalar, prueba, análisis) |
| 41 | Exportación: cómo se ven y se graban (11-10 18:06; 19:01 «haz el punto 4») | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 42 | Un golpe no son 8 pantallazos: vídeo y más (11-10 18:21) | HECHO | 3 comprobado en salidas | 11 comprobaciones: 11 ok |
| 43 | El PC no es servidor (11-10 18:27) | HECHO | 1 construido, sin comprobar | no se comprueba en las salidas: decisión de arquitectura (sin servidor) |
| 44 | Sin vídeos del usuario, de entrenadores ni de otras jugadoras (11-10 19:37), salvo su entr | HECHO | 2 comprobación que falla | 11 comprobaciones: 1 aviso, 10 ok; la peor: «Tablas a la vista en «Conclusiones (Panel y Comparativas)»» (1 tablas (el usuario pidió informa |
| 45 | Todo automático y completo: el usuario no revisa nada (11-10 09:05, 19:38; 12-10 11:41) | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 2 comprobaciones: 2 ok |
| 46 | Sin PDF enorme y sin inventar datos (11-10 19:40) | HECHO | 2 comprobación que falla | 2 comprobaciones: 1 falta, 1 ok; la peor: «Valores dentro de límites físicos» (ball_flight.apex_height_m: 3 de 91 fuera de 0.2–4.0) |
| 47 | Modelo técnico con fuentes; cómo saber si está completo (12-10 06:32) | HECHO | 2 comprobación que falla | 169 comprobaciones: 16 pocos datos, 153 ok; la peor: «1. Fases · Golpe del rival → split step» (se mide (100% de los golpes); el informe lo  |
| 48 | Posición de la cabeza y altura del cuerpo al inicio y al final (11-10 19:48) | HECHO | 3 comprobado en salidas | 3 comprobaciones: 3 ok |
| 49 | No perder contexto ni sesión; registros automáticos (12-10 11:39-11:45) | HECHO | 1 construido, sin comprobar | no se comprueba en las salidas: registros subidos solos a pc-logs |
| 50 | Progreso y monitorización visibles (12-10 14:37, 14:43) | HECHO | 1 construido, sin comprobar | no se comprueba en las salidas: registros con fecha y duración en la terminal |
| 51 | El código de la prueba es el de los casos reales (12-10 14:37) | HECHO | 1 construido, sin comprobar | no se comprueba en las salidas: el mismo código (clip_pipeline, stages) en la prueba y en los partidos |
| 52 | Brave, no instalar Edge (12-10 16:48) | HECHO | 3 comprobado en salidas | 9 comprobaciones: 9 ok |
| 53 | No pasar de 100 a 0: conservar lo anterior (12-10 17:21) | HECHO | 2 comprobación que falla | 10 comprobaciones: 1 aviso, 9 ok; la peor: «Tablas a la vista en «Conclusiones (Panel y Comparativas)»» (1 tablas (el usuario pidió informac |
| 54 | Qué hace ella cuando la rival golpea, la bola cruza la red, bota y llega arriba (12-10 17: | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 55 | Ver una bola cerca de la red y un apoyo cerrado con golpe paralelo (12-10 17:40) | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 1 comprobaciones: 1 ok |
| 56 | Barras horizontales con la diferencia de altura de la cabeza (12-10 17:40) | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 57 | Nada de gráficas de muchas líneas ni tablas sin frases (12-10 17:10) | HECHO | 2 comprobación que falla | 10 comprobaciones: 1 aviso, 9 ok; la peor: «Tablas a la vista en «Conclusiones (Panel y Comparativas)»» (1 tablas (el usuario pidió informac |
| 58 | La IA más moderna posible (11-10 09:05) | HECHO | 1 construido, sin comprobar | no se comprueba en las salidas: elección de modelos (RTMPose, YOLO11, TrackNetV3, RTMW3D) |
| 59 | Diferencias solo por encima del error y en situaciones equivalentes (10-10 18:05) | HECHO | 2 comprobación que falla | 6 comprobaciones: 1 falta, 5 ok; la peor: «Valores dentro de límites físicos» (ball_flight.apex_height_m: 3 de 91 fuera de 0.2–4.0) |
| 64 | Todos los tipos de desplazamiento, del split step a la recuperación, con cada tipo de paso | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 10 comprobaciones: 10 ok |
| 65 | El play del vídeo funciona (no solo un fotograma) (12-10 18:14, 21:03, 21:14) | HECHO | 3 comprobado en salidas | 11 comprobaciones: 11 ok |
| 66 | Fechas y duración en los registros (12-10 18:25) | HECHO | 1 construido, sin comprobar | no se comprueba en las salidas: registros con fecha y duración (comun.ps1), no una salida |
| 67 | No borrar el trabajo hecho: lo complejo como extra (12-10 22:35; 13-10 05:48 p6) | HECHO | 2 comprobación que falla | 14 comprobaciones: 1 aviso, 13 ok; la peor: «Tablas a la vista en «Conclusiones (Panel y Comparativas)»» (1 tablas (el usuario pidió informa |
| 68 | La meta: mejorar mi derecha tomando la de X como base (12-10 22:25; 13-10 05:48 p5) | PARCIAL | 2 comprobación que falla | 8 comprobaciones: 1 falta, 1 pocos datos, 6 ok; la peor: «La lección: como mucho 3 claves por fase, cada una con su valor, ejercicio y cómo  |
| 69 | Ejemplo: «derecha paralela, apoyo cerrado, parada, bola plana, lado derecho» (cómo lo hace | PARCIAL | 2 comprobación que falla | 1 comprobaciones: 1 pocos datos; la peor: «Tu ejemplo: derecha paralela, apoyo cerrado, parada, plana, lado de su derecha» (0 golpes exactos |
| 70 | Las 2000 y pico combinaciones, usables y validadas (13-10 05:48 p2; 06:00) | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 10 comprobaciones: 10 ok |
| 71 | El conocimiento de los vídeos de entrenadores en la web (12-10 21:31; 13-10 05:48 p3) | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 21 comprobaciones: 4 aviso, 17 ok; la peor: «R17 La ter |
| 72 | El conocimiento del chat (modelo técnico, taxonomía, matriz) implementado en la web, no so | PARCIAL | 2 comprobación que falla | 170 comprobaciones: 16 pocos datos, 154 ok; la peor: «1. Fases · Golpe del rival → split step» (se mide (100% de los golpes); el informe lo  |
| 73 | Revisar la web de arriba abajo para que aporte valor (13-10 05:48 p6) | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 23 comprobaciones: 1 aviso, 22 ok; la peor: «Tablas a l |
| 74 | ¿El análisis de las apps de pago y libres fue profundo o superficial? (13-10 05:48 p7) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#74); no se comprueba en las salidas: análisis documental (docs/comparativa_apps.md), no una salida |
| 76 | «Un 50 % de golpes dudosos» (13-10 05:48 p10) | HECHO | 2 comprobación que falla | 1 comprobaciones: 1 aviso; la peor: «Golpes dudosos (duda sobre el golpe, no sobre una medida)» (100 de 193 del lado cercano (52%); motivos: |
| 77 | No lanzar pruebas de 6 h para validar (13-10 06:01) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#77); no se comprueba en las salidas: lanzadores cortos (2c, 2d) sin repetir el análisis de vídeo |
| 78 | No depender de que al usuario se le ocurran funciones (13-10 06:09) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#78); no se comprueba en las salidas: proceso: Claude propone las funciones desde la matriz y los entrenadores |
| 79 | Vídeos de entrenamiento con otras cámaras, en un apartado aparte y marcado (12-10 21:31, 2 | PARCIAL | 2 comprobación que falla | 20 comprobaciones: 11 pocos datos, 9 ok; la peor: «Derechas filmadas de lado» (6 (se resume cada medida con 12 o más)) |
| 80 | Encadenar solo la prueba y las comprobaciones; que Claude lo monitorice (12-10 22:43) | HECHO | 1 construido, sin comprobar | no se comprueba en las salidas: cadena de prueba, auditoría y subida a pc-logs |
| 81 | Tamaño de la salida; comprobación sin gastar tokens (12-10 22:40) | HECHO | 1 construido, sin comprobar | no se comprueba en las salidas: tamanos.txt y auditoría en Python sin Claude |
| 82 | Dónde se graban las salidas, qué va a git, qué se reutiliza (12-10 22:47) | HECHO | 1 construido, sin comprobar | no se comprueba en las salidas: salidas en C:\tenis\output, registros en pc-logs, caché por etapas |
| 83 | Árbol de ficheros generados y validados (12-10 22:25) | HECHO | 2 comprobación que falla | 7 comprobaciones: 4 falta, 3 ok; la peor: «Partido sin-fecha_f43dd2_rybakina: salida de cada etapa, ventanas y series» (15 ficheros de etapa |
| 84 | Matriz §1 Cadena cinética (suelo → pelvis → separación → tronco → codo → muñeca) (12-10 21 | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 10 comprobaciones: 10 ok |
| 85 | Matriz §2 Cuerpo (cabeza, brazos, tronco, piernas, pie de arrastre) | PARCIAL | 2 comprobación que falla | 14 comprobaciones: 3 pocos datos, 11 ok; la peor: «6. Matriz del usuario · Rodilla de atrás en la carga (110–130°) y de delante en el impact |
| 86 | Matriz §3 Raqueta (bucle, caída, cara, trayectoria) | PARCIAL | 2 comprobación que falla | 13 comprobaciones: 2 pocos datos, 11 ok; la peor: «6. Matriz del usuario · Caída de la raqueta por debajo de la bola» (vista lateral de entr |
| 87 | Matriz §4 Apoyos (abierto, semiabierto, neutro o cerrado, salto, abierto extremo) | HECHO | 3 comprobado en salidas | 4 comprobaciones: 4 ok |
| 88 | Matriz §5 Pies (split, ajuste, cruzado, paso de ataque, recuperación) | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 8 comprobaciones: 8 ok |
| 89 | Matriz §6 Modalidades (plano, liftado, cortado, botepronto, volea, 3 terminaciones) | PARCIAL | 2 comprobación que falla | 8 comprobaciones: 1 pocos datos, 7 ok; la peor: «Botepronto / media volea: casos (#16)» (5 golpes de 193 (la clase «Contacto» se pudo decidi |
| 90 | Matriz §7 Adaptación a la bola (rápida, corta, alta, lateral) | PARCIAL | 2 comprobación que falla | 16 comprobaciones: 6 pocos datos, 10 ok; la peor: «Golpe angulado (#132)» (0 golpes de 193 (la clase «Golpe angulado» se pudo decidir en 85; |
| 91 | Matriz §8 Dirección (cruzado, paralelo, dentro-fuera, dentro-dentro) | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 3 comprobaciones: 3 ok |
| 92 | Matriz §9 Control (zona de impacto, relajación, equilibrio) | PARCIAL | 2 comprobación que falla | 4 comprobaciones: 1 pocos datos, 3 ok; la peor: «6. Matriz del usuario · Zona de impacto: delante de la cadera» (vista lateral de entrenamie |
| 95 | Matriz §12 Neuro y visión (latencia, mirada, EMG) | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 3 comprobaciones: 3 ok |
| 97 | Matriz §14 Fugas de energía (apertura prematura, casting, vector) | PARCIAL | 2 comprobación que falla | 4 comprobaciones: 1 pocos datos, 3 ok; la peor: «6. Matriz del usuario · Liberación anticipada de la muñeca («casting»)» (vista lateral de e |
| 98 | Matriz §15 Contexto y ambiente (superficie, aerodinámica) | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 99 | Mejora 1 (entrenadores): líneas dibujadas sobre el fotograma | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 100 | Mejora 2: raqueta al lado del cuerpo o detrás de la espalda, y adónde apunta la punta | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 1 comprobaciones: 1 ok |
| 101 | Mejora 3: altura y separación del codo | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 102 | Mejora 4: punta de la raqueta respecto a la cabeza en el armado | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 103 | Mejora 5: transferencia de peso en una frase | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 104 | Mejora 6: empuje de piernas («bajar y subir») | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 105 | Mejora 7: ritmo con la bola (caída al subir la bola) | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 106 | Mejora 8: frenado de los hombros antes del contacto | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 107 | Mejora 9: caída por debajo de la bola | PARCIAL | 2 comprobación que falla | 2 comprobaciones: 2 pocos datos; la peor: «6. Matriz del usuario · Caída de la raqueta por debajo de la bola» (vista lateral de entrenamient |
| 108 | Mejora 10: «gira mientras corre» | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 109 | Mejora 11: frases con datos existentes (mano libre, terminación, base al terminar, desplaz | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 4 comprobaciones: 4 ok |
| 110 | Mejora 12: «Lo que la distingue» (2-3 rasgos frente a la literatura, con vídeo) | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 111 | Mejora 13: consigna «para imitarla» y error que evita, por fase | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 112 | Mejora 14: clase descriptiva de estilo (`fh_style`) | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 113 | Mejora 15: examen interno con las afirmaciones de entrenadores (R1-R25) | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 19 comprobaciones: 4 aviso, 15 ok; la peor: «R17 La ter |
| 114 | Cuerpo respecto a la bola en cada momento (golpe rival, cruza la red, cae, bota, sube, gol | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 115 | Cuánto baja y sube el cuerpo, con fotogramas y barras horizontales: de la espera al punto  | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 116 | Distancia entre las piernas en los golpes: base y estabilidad (13-10 11:50) | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 117 | Hacia dónde mira el tronco al terminar (valla lateral, de frente, girado) según el golpe ( | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 118 | Validar cada medida de forma automática, no a mano: ¿técnica o ruido? (13-10 08:40-10:30) | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 119 | Automatizar todo el ciclo en el PC: el usuario no lanza pruebas ni avisa (13-10 10:40, 11: | HECHO | 1 construido, sin comprobar | no se comprueba en las salidas: ciclo automático del PC: revision_automatica.md en pc-logs |
| 120 | Vídeo a pantalla completa (13-10 12:00) | HECHO | 2 comprobación que falla | 10 comprobaciones: 1 aviso, 9 ok; la peor: «Tablas a la vista en «Conclusiones (Panel y Comparativas)»» (1 tablas (el usuario pidió informac |
| 121 | Ver lo que se pinta por separado, por grupos o una a una (13-10 12:00) | HECHO | 2 comprobación que falla | 10 comprobaciones: 1 aviso, 9 ok; la peor: «Tablas a la vista en «Conclusiones (Panel y Comparativas)»» (1 tablas (el usuario pidió informac |
| 122 | Web en 2 vistas principales y el resto en «Más», en dos grupos (funcional y técnico), sin  | HECHO | 2 comprobación que falla | 10 comprobaciones: 1 aviso, 9 ok; la peor: «Tablas a la vista en «Conclusiones (Panel y Comparativas)»» (1 tablas (el usuario pidió informac |
| 123 | Lo que se aprende en una sesión: plan de 3 prioridades en orden, foco externo por fase, de | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 124 | Hacia dónde mira el tronco y las manos en la espera, medidas fiables (13-10 13:00) | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 1 comprobaciones: 1 ok |
| 126 | Consignas con su número en «Cómo hacerlo tú» («baja unos 14 cm desde la espera, como ella» | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 127 | Guía de primer uso, «empieza aquí» (13-10 14:00) | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 128 | Glosario de términos (13-10 14:00) | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 130 | Resto de derecha (devolver el saque) con todas sus variantes, en la matriz y en la aplicac | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 12 comprobaciones: 12 ok |
| 131 | detectar impactos de bola por AUDIO (Chat, 10-10 17:27) | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 132 | ángulos (golpe angulado) — repetido el 19-10 08:11: «golpe angulado ... te lo he dicho muc | HECHO | 2 comprobación que falla | 2 comprobaciones: 1 pocos datos, 1 ok; la peor: «Golpe angulado (#132)» (0 golpes de 193 (la clase «Golpe angulado» se pudo decidir en 85; s |
| 134 | prefiero una baseline completa a cerrar más golpes (Chat, 11-10 18:06) | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 135 | distancia al fondo, red (Chat, 11-10 19:23) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#135); sin comprobación automática asignada |
| 136 | lo puedes añadir al contexto o fichero base? (Chat, 13-10 09:47) | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 137 | hay algo que se pueda paralelizar ... threading (Chat, 13-10 18:31) | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 138 | se puede hacer modelos hibridos de alguna manera? (Chat, 13-10 18:34) | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 139 | si se pierde calidad no tocamos nada (Chat, 14-10 20:08) | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 140 | de la jugadora de fondo se sacan imagenes para la captura de datos en vista frontal? (Chat | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#140); sin comprobación automática asignada |
| 141 | (punto 0) la imagen ... Estroboscópica ... no vale para nada; ... Sus pies en este golpe t | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 142 | (punto 2) como se puede hacer una aplicacion profesional ... mas jugadores, mas golpes ... | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#142); sin comprobación automática asignada |
| 143 | (punto 3) esta es una guia para la derecha de otra jugadora ... revisar si aplica todo (Ch | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#143); sin comprobación automática asignada |
| 144 | (punto 4) hay tareas o schedulers ... salen terminales y se apagan solos (Chat, 17-10 09:4 | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 145 | no quiero nada en la nube ni pagar ni nada (Chat, 17-10 10:09) | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 146 | borra las carpetas de pruebas antiguas (Chat, 17-10 10:49) | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 147 | la guia de ivanovic esta aplicada al 100 por 100? sobre todo los puntos 1 2 3 5 6 y 10 (Ch | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#147); sin comprobación automática asignada |
| 148 | empieza por la maqueta de una fase (Chat, 17-10 13:05) | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 149 | no se como validar eso lo tienes que hacer tu (Chat, 17-10 13:11) | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 150 | estos son mas videos de youtube para analizar (3 enlaces) (Chat, 17-10 17:21) | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 151 | como se separan los golpes (derecha, reves, saque, voleas), los jugadores, los partidos (C | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 152 | como queda la estructura de directorios ... carpeta normalizada de los jugadores (Chat, 18 | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 153 | y analizo estos videos (2 enlaces de Olivari) (Chat, 18-10 11:19) | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 154 | mi movil es android google pixel 8 ... que copie directo al pixel (Chat, 18-10 12:11) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#154); sin comprobación automática asignada |
| 155 | es fisicamente imposible que en un partido solo de 86 o 77 golpes ... no quiero que se pie | FALTA | 0 sin construir | SIN HACER según el registro (#155, docs/peticiones_usuario.md) |
| 156 | como sabes la identidad de la jugadora y porque hay fallos? porque no buscas en la web de  | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#156); sin comprobación automática asignada |
| 157 | bola corta baja cerca de la red (Chat, 19-10 08:11) | HECHO | 2 comprobación que falla | 1 comprobaciones: 1 pocos datos; la peor: «Bola corta baja cerca de la red (#157)» (0 golpes de 193 (la clase «Bola corta cerca de la red» s |
| 158 | bola corta alta cerca de la red (Chat, 19-10 08:11) | HECHO | 2 comprobación que falla | 1 comprobaciones: 1 pocos datos; la peor: «Bola corta alta cerca de la red (#158)» (0 golpes de 193 (la clase «Bola corta cerca de la red» s |
| 159 | volea a media pista con el golpe de fondo derecha o reves (sin ser empuñadura de volea) (C | PARCIAL | 2 comprobación que falla | 2 comprobaciones: 2 pocos datos; la peor: «Volea a media pista con golpe de fondo (#159)» (0 golpes de 193 (la clase «Contacto» se pudo deci |
| 160 | la app que hiciste completa como se arranca, se puede usar ahora? (Chat, 19-10 08:11) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#160); sin comprobación automática asignada |
| 161 | como se enlazan los partidos de una jugadora ... tienen que estar el analisis junto (Chat, | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 162 | Galerías ordenadas por calidad de captura, representatividad y resultado del punto (CLAUDE | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#162); sin comprobación automática asignada |
| 163 | Final del armado (máximo giro, raqueta más atrás) (Matriz (literatura), §1) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#163); sin comprobación automática asignada |
| 164 | Final de la extensión (Matriz (literatura), §1) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#164); sin comprobación automática asignada |
| 165 | Giro de cadera y de hombros al final del armado (Matriz (literatura), §2) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#165); sin comprobación automática asignada |
| 166 | Separación cadera–hombros (X-factor) (Matriz (literatura), §2) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#166); sin comprobación automática asignada |
| 167 | Cabeza quieta tras el impacto (Matriz (literatura), §2) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#167); sin comprobación automática asignada |
| 168 | Hombros más girados que la cadera en el impacto (Matriz (literatura), §2) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#168); sin comprobación automática asignada |
| 169 | Transferencia de peso del armado al impacto (Matriz (literatura), §2) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#169); sin comprobación automática asignada |
| 170 | Empuje de piernas («bajar y subir») (Matriz (literatura), §2) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#170); sin comprobación automática asignada |
| 171 | Primer paso: tipo (gravity, jab, pivot, counter, cruzado, lateral) (Matriz (literatura), § | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#171); sin comprobación automática asignada |
| 172 | Cada paso nombrado: lateral (sin cruzar), cruzado, de carrera, hacia delante, hacia atrás, | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#172); sin comprobación automática asignada |
| 173 | Frenado: último paso largo con caída de la velocidad (Matriz (literatura), §3) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#173); sin comprobación automática asignada |
| 174 | Patada atrás (tijera) tras el impacto (Matriz (literatura), §3) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#174); sin comprobación automática asignada |
| 175 | Recuperación: tipo de cada paso de vuelta, cuándo empieza (Matriz (literatura), §3) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#175); sin comprobación automática asignada |
| 176 | Nuevo split step antes del siguiente golpe de la rival (Matriz (literatura), §3) | FALTA | 0 sin construir | SIN HACER según el registro (#176, docs/peticiones_usuario.md) |
| 177 | Orientación del pie (talón → dedo gordo respecto a la línea de fondo) en el armado y el im | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#177); sin comprobación automática asignada |
| 178 | Pivote sobre la punta del pie de atrás (talón arriba, punta apoyada) (Matriz (literatura), | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#178); sin comprobación automática asignada |
| 179 | Raqueta al lado del cuerpo o por detrás de la espalda en el armado (debate WTA/ATP) (Matri | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#179); sin comprobación automática asignada |
| 180 | Retraso de la muñeca (lag) (Matriz (literatura), §4) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#180); sin comprobación automática asignada |
| 181 | Cara en el impacto (Matriz (literatura), §4) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#181); sin comprobación automática asignada |
| 182 | Velocidad de la raqueta relativa entre golpes (Matriz (literatura), §4) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#182); sin comprobación automática asignada |
| 183 | Posición de la mano en el mango (Matriz (literatura), §4) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#183); sin comprobación automática asignada |
| 184 | Altura de la bola en su vuelo, bote, punto más alto; contacto subiendo / arriba / cayendo  | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#184); sin comprobación automática asignada |
| 185 | Longitud del peloteo (Matriz (literatura), §5) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#185); sin comprobación automática asignada |
| 186 | Resto, globo, dejada, volea, subida a la red (Matriz (literatura), §5) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#186); sin comprobación automática asignada |
| 187 | Ganador / error (forzado o no) (Matriz (literatura), §5) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#187); sin comprobación automática asignada |
| 188 | Resto de primer o de segundo saque (Matriz (literatura), §5b) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#188); sin comprobación automática asignada |
| 189 | «Cómo» de la fase 1: «mirando la raqueta de la rival» (YouTube, 18-10 Olivari 4) | FALTA | 0 sin construir | SIN HACER según el registro (#189, docs/peticiones_usuario.md) |
| 190 | Clase de forma del armado: bucle verdadero, loop falso, recto atrás; tendencia «punta arri | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#190); sin comprobación automática asignada |
| 191 | Alarmas por golpe: cara al cielo, punta hacia la red tras el giro, pausa arriba, caída baj | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#191); sin comprobación automática asignada |
| 192 | Terminación «hacia adelante», «la mano libre recoge la raqueta», codo al terminar (Guía Iv | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#192); sin comprobación automática asignada |
| 193 | Mano libre en la aceleración y el impacto (pliegue, que no cruce) (Guía Ivanovic, hueco 10 | FALTA | 0 sin construir | SIN HACER según el registro (#193, docs/peticiones_usuario.md) |
| 194 | «Sus principios» (5-6 frases) y «Lo que la distingue» (Guía Ivanovic, hueco 13) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#194); sin comprobación automática asignada |
| 195 | Fuentes en COACH: Iino y Kojima 2001, Bahamonde y Knudson 2003, Kawamoto 2019, LTA, Wulf,  | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#195); sin comprobación automática asignada |
| 196 | Medidas de lado: codo por delante de la cadera, inclinación del tronco en la espera (Guía  | FALTA | 0 sin construir | SIN HACER según el registro (#196, docs/peticiones_usuario.md) |
| 197 | Progresión por etapas sin calendario y paso a pista (Guía Ivanovic, hueco 19) | FALTA | 0 sin construir | SIN HACER según el registro (#197, docs/peticiones_usuario.md) |
| 198 | Tiempo entre puntos (rutina) bajo presión (Guía Ivanovic, hueco 20) | FALTA | 0 sin construir | SIN HACER según el registro (#198, docs/peticiones_usuario.md) |
| 199 | Bote: GBDT/CatBoost sobre la trayectoria (Estado del arte, 13-10) | FALTA | 0 sin construir | SIN HACER según el registro (#199, docs/peticiones_usuario.md) |
| 200 | Pista: TennisCourtDetector (14 puntos) + refinado (Estado del arte, 13-10) | FALTA | 0 sin construir | SIN HACER según el registro (#200, docs/peticiones_usuario.md) |
| 201 | Marcador: rapidocr 3.x con PP-OCRv5 (Estado del arte, 13-10) | FALTA | 0 sin construir | SIN HACER según el registro (#201, docs/peticiones_usuario.md) |
| 202 | Bola: probar WASB (Estado del arte, 13-10) | FALTA | 0 sin construir | SIN HACER según el registro (#202, docs/peticiones_usuario.md) |
| 203 | 3D: prueba A/B con MotionAGFormer (Estado del arte, 13-10) | FALTA | 0 sin construir | SIN HACER según el registro (#203, docs/peticiones_usuario.md) |
| 204 | Golpe: clasificador aprendido con F3Set (E2E-Spot/F3ED) (Estado del arte, 13-10) | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 205 | Volumen: unos 400 golpes con 4 partidos (Comparativa apps, §4.3) | FALTA | 0 sin construir | SIN HACER según el registro (#205, docs/peticiones_usuario.md) |
| 206 | Validación de cuerdas y 3D con referencia real (Comparativa apps, §4.4) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#206); sin comprobación automática asignada |
| 207 | Golpes: sin volea, remate ni cortado (Comparativa apps, §3 Peor) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#207); sin comprobación automática asignada |
| 208 | Lógica duplicada JS/Python: calcular una vez en Python (Revisión completa, §2 fallo 17) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#208); sin comprobación automática asignada |
| 209 | Passing y globo (Revisión completa, §3 B) | FALTA | 0 sin construir | SIN HACER según el registro (#209, docs/peticiones_usuario.md) |
| 210 | Dejada (bote muy corto en campo rival) (Revisión completa, §3 B) | FALTA | 0 sin construir | SIN HACER según el registro (#210, docs/peticiones_usuario.md) |
| 211 | CHECKS de la mano en el armado da por hecho que va por debajo del hombro (Auditorías 17-10 | FALTA | 0 sin construir | SIN HACER según el registro (#211, docs/peticiones_usuario.md) |
| 212 | Grados de estimaciones poco fiables como objetivo (cara en el impacto) (Auditorías 17-10,  | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#212); sin comprobación automática asignada |
| 213 | Textos COACH (el porqué con fuente) en todas las claves de la lección (Auditorías 17-10, t | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#213); sin comprobación automática asignada |
| 214 | Fuentes de Ivanovic §3 #17 (Auditorías 17-10, técnica #18) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#214); sin comprobación automática asignada |
| 215 | Armado «antes» o «al» bote según el sitio (Auditorías 17-10, técnica #22) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#215); sin comprobación automática asignada |
| 216 | Pendiente de la guía: punta arriba/codo alto, terminación hacia adelante, codo libre (Audi | FALTA | 0 sin construir | SIN HACER según el registro (#216, docs/peticiones_usuario.md) |
| 217 | Documentos desactualizados (aprendido_entrenadores §2 y §4) (Auditorías 17-10, técnica #26 | FALTA | 0 sin construir | SIN HACER según el registro (#217, docs/peticiones_usuario.md) |
| 218 | La fuente son los partidos: que funcione la vista de fondo en los dos lados, que funcionen | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 4 comprobaciones: 4 ok |
| 219 | Las tomas de la cámara de fondo cuentan para los dos lados: golpes del fondo contados y co | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#219); sin comprobación automática asignada |
| 220 | Almacenamiento definitivo: árbol por jugador, partido y golpe; nombres, colisiones y todos | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 221 | Detectar golpes con modelos entrenados, como las apps profesionales, no con reglas a mano  | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#221); sin comprobación automática asignada |
| 222 | Un clic por partido para decir quién es ella (19-10 19:57) | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 223 | Revés y derecha cortados (20-10 06:33) | FALTA | 0 sin construir | SIN HACER según el registro (#223, docs/peticiones_usuario.md) |
| 224 | Saques: plano, cortado o kick; primero o segundo (20-10 07:30) | FALTA | 0 sin construir | SIN HACER según el registro (#224, docs/peticiones_usuario.md) |
| 225 | La aplicación no se cuelga ni ralentiza el PC (24-10 10:22-10:47) | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 226 | Lista de partidos profesional: nombres normalizados, torneo, ronda, fecha, fotos; sin prue | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 227 | Pantalla completa en la aplicación (24-10 10:36) | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 229 | Renombrar el vídeo no rompe nada; el partido se identifica por su contenido (25-10 13:21-1 | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 230 | Uso de CPU, RAM, iGPU y disco por etapa (mín, media, máx) y aprovechar el equipo (26-10 12 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#230); sin comprobación automática asignada |
| 231 | Un partido no puede tardar el doble sin saber la causa; la etapa de tomas lenta (26-10 11: | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#231); sin comprobación automática asignada |
| 232 | Ningún proceso que se pueda colgar sin probar; la exportación del revés se colgó (27-10 09 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#232); sin comprobación automática asignada |
| 233 | Una referencia completa y medida antes de validar nada (26-10 11:09) | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 234 | Prueba de valor de la aplicación con los datos reales (27-10 07:21) | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 235 | Cadena cinética, footwork y timing: lo que define el golpe (27-10 09:33) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#235); sin comprobación automática asignada |
| 236 | Huellas numeradas sobre los pies y patrones de pasos (27-10 09:38) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#236); sin comprobación automática asignada |
| 237 | El PC empieza cada trabajo al momento (GitHub Actions), sin esperas de 10-40 min (27-10 10 | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 238 | La validación es siempre automática; el usuario no valida la aplicación (27-10 11:42) | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#238); sin comprobación automática asignada |
| 239 | No se descarta ninguna petición (27-10 11:42) | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 240 | Comparar la aplicación con las profesionales una vez estén los golpes (27-10 11:42) | FALTA | 0 sin construir | SIN HACER según el registro (#240, docs/peticiones_usuario.md) |
| 241 | Aplicación genérica: jugadores, golpes y partidos por configuración, nada fijo en el códig | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 242 | Flujo de la aplicación: añadir N partidos, elegir la persona, jugadores masculinos y femen | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#242); sin comprobación automática asignada |
| 243 | Todos los escenarios del producto los contempla Claude sin esperar a que se pidan (27-10 1 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#243); sin comprobación automática asignada |
| 244 | Resultado del punto creíble (hoy 2 golpes ganadores en 191 derechas) (prueba de valor 27-1 | FALTA | 0 sin construir | SIN HACER según el registro (#244, docs/peticiones_usuario.md) |
| 245 | Rivales, fechas y rondas bien escritos en el informe (prueba de valor 27-10) | FALTA | 0 sin construir | SIN HACER según el registro (#245, docs/peticiones_usuario.md) |
