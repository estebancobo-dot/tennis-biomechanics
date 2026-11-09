# Estado real de las peticiones (generado por `scripts/real_status.py`; no editar a mano)

237 peticiones (sin las que no aplican). «HECHO» en el registro es la etiqueta de Claude; aquí cuenta solo lo que se comprueba. «Comprobado en salidas» = existe y es coherente con los datos reales, no que sea correcto; eso es «validado con verdad».

| Nivel | Peticiones |
|---|---|
| 0 sin construir | 16 |
| 1 construido, sin comprobar | 63 |
| 2 comprobación que falla | 73 |
| 3 comprobado en salidas | 85 |
| 4 validado con verdad | 0 |

## Por paquete del plan (en el orden de ejecución)

«¿Cerrado?» lo calcula este programa: sí solo si la prueba principal pasa (todas sus comprobaciones de la auditoría en «ok») y todas las peticiones del paquete están comprobadas en salidas (nivel 3 o 4).

| Paquete | Peticiones | sin construir | construido, sin comprobar | comprobación que falla | comprobado en salidas | validado con verdad | Se cierra con | Prueba principal | ¿Cerrado? |
|---|---|---|---|---|---|---|---|---|---|
| B1 Base · velocidad y uso del PC | 10 | 0 | 0 | 7 | 3 | 0 | Prueba desde cero de 35 min en ≤ 45 min; CPU/iGPU por etapa medidas en cada ejecución | falla | no |
| B2 Base · robustez (nada se cuelga, todo se recupera) | 3 | 0 | 0 | 0 | 3 | 0 | Prueba por cada caso de error y cuelgue; 0 etapas con error en la referencia | ok | **sí** |
| B3 Base · mejores modelos (estado del arte medido) | 10 | 0 | 0 | 0 | 10 | 0 | Cada candidato medido frente al actual (precisión con datos anotados y fotogramas/s en el PC) | ok | **sí** |
| B4 Base · no perder golpes | 6 | 0 | 0 | 4 | 2 | 0 | Recall F3Set y RacketVision por lado y tipo, sin bajar la precisión | falla | no |
| B5 Base · exportación | 1 | 0 | 0 | 0 | 1 | 0 | Vídeos por golpe en ≤ 20 min sin cuelgues | ok | **sí** |
| B6 Base · referencia definitiva de los 4 partidos | 4 | 0 | 0 | 3 | 1 | 0 | 4 partidos sin errores de etapa; auditoría generada | ok | no |
| B7 Base · aplicación autónoma e infraestructura | 36 | 0 | 0 | 7 | 29 | 0 | Un partido nuevo de principio a fin sin el ciclo ni el chat; capturas de cada pantalla sin fallos | ok | no |
| M1 Medidas · fases, cadena cinética y ritmo | 12 | 0 | 7 | 4 | 1 | 0 | Cada medida: fiable en la auditoría (ruido < variación) y sin depender de la cámara | — | — |
| M2 Medidas · pies y apoyos | 20 | 2 | 10 | 4 | 4 | 0 | Pasos y apoyos medidos en la mayoría de golpes; fiables en la auditoría | — | — |
| M3 Medidas · cuerpo | 14 | 1 | 2 | 4 | 7 | 0 | Fiables en la auditoría y sin depender de la cámara | — | — |
| M4 Medidas · raqueta, mano y empuñadura | 18 | 2 | 8 | 7 | 1 | 0 | Fiables o «no medible desde la tele» dicho; cara del impacto marcada como estimación | — | — |
| M5 Medidas · bola y situación del golpe | 18 | 0 | 4 | 12 | 2 | 0 | Cada situación con golpes suficientes o «pocos datos» dicho; diferencias solo por encima del ruido | — | — |
| M6 Medidas · tipos de golpe | 11 | 4 | 3 | 4 | 0 | 0 | Recall por tipo con datos anotados | — | — |
| M7 Medidas · contexto del punto | 7 | 3 | 2 | 0 | 2 | 0 | Resultado del punto coherente con el marcador; nombres y fechas correctos | — | — |
| P1 Producto · contenido para copiar su golpe (Cópiala / Aprende) | 32 | 2 | 11 | 10 | 9 | 0 | Cada consigna con su medida, su fuente y su vídeo; examen interno R1-R25 pasado | — | — |
| P2 Producto · pantallas e informe | 18 | 0 | 5 | 3 | 10 | 0 | Capturas automáticas de todas las pantallas sin fallos; nada borrado de lo anterior | — | — |
| P3 Producto · validación automática | 6 | 0 | 2 | 4 | 0 | 0 | Cada medida y cada petición con una prueba automática y su umbral | — | — |
| P4 Producto · comparación con las apps profesionales | 3 | 1 | 2 | 0 | 0 | 0 | Cada diferencia con su decisión y su prueba | — | — |
| P5 Producto · escenarios y genericidad | 4 | 0 | 4 | 0 | 0 | 0 | Cada escenario de docs/escenarios_producto.md con su prueba | — | — |
| P6 Producto · móvil (al final) | 2 | 0 | 2 | 0 | 0 | 0 | Copia al móvil comprobada | — | — |
| D Documentación y reglas de trabajo | 2 | 1 | 1 | 0 | 0 | 0 | Documentos al día con el código (prueba de enlaces y fechas) | — | — |

Lo que le falta a cada paquete de la Base para cerrarse:

- **B1**: prueba principal: Tiempo: smoke_tennis-yusipopen-final-sobolenko-rybakin: aviso; peticiones sin comprobar o que fallan: #14, #29, #75, #125, #137, #230, #231
- **B4**: prueba principal: Saques por punto de su saque: smoke_tennis-yusipopen-final-sobolenko-rybakin: aviso, Cobertura del saque dicha en el informe: aviso; peticiones sin comprobar o que fallan: #23, #151, #155, #205
- **B6**: peticiones sin comprobar o que fallan: #1, #134, #233
- **B7**: peticiones sin comprobar o que fallan: #18, #20, #21, #22, #37, #66, #242

## Cada petición

| # | Petición | Paquete | Registro | Nivel | Lo que comprueba la auditoría |
|---|---|---|---|---|---|
| 1 | Derecha de Rybakina en sus 4 partidos completos, una vez y al final (10-10 17:27; 11-10 19 | B6 | HECHO | 2 comprobación que falla | 5 comprobaciones: 1 aviso, 1 pocos datos, 3 ok; la peor: «Saques por punto de su saque: smoke_tennis-yusipopen-final-sobolenko-rybakin» (10  |
| 2 | Ver informe y salidas en el móvil (11-10 18:21, 18:29, 18:33) | P6 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#2); no se comprueba en las salidas: aplazado por el usuario (móvil al final) |
| 4 | Responder de forma profesional a «¿qué hay que hacer para pegar como X?», con todas las po | P1 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 201 comprobaciones: 50 pocos datos, 151 ok; la peor: «1. Fases · Golpe del riva |
| 5 | Taxonomía completa con todas las variantes (bola rápida/lenta, alta/baja, corta/profunda,  | M5 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 32 comprobaciones: 25 pocos datos, 7 ok; la peor: «Golpe angulado (#132)» (0 go |
| 6 | Juego de pies: split step, primer paso, ajuste, reacción, recuperación (11-10 08:22, 19:23 | M2 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 35 comprobaciones: 4 pocos datos, 31 ok; la peor: «3. Pies y desplazamiento · S |
| 7 | Empuñadura en la espera y al golpear (11-10 19:23) | M4 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 5 comprobaciones: 1 pocos datos, 4 ok; la peor: «4. Raqueta, swing y empuñadura |
| 8 | Cuerdas y cara (suelo, valla lateral o trasera, ángulos, cierre muñeca–raqueta) en todas l | M4 | HECHO | 3 comprobado en salidas | 7 comprobaciones: 7 ok |
| 9 | Información, no tablas; profesional, «con sentido humano», nivel de las apps punteras (10- | P1 | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 9 comprobaciones: 9 ok |
| 10 | Ver los cambios en la prueba rápida, sin 1 h (12-10 17:32, 17:40) | B1 | HECHO | 3 comprobado en salidas | 12 comprobaciones: 12 ok |
| 11 | Validar solo que las salidas reales tienen todo lo pedido y todos los casos del modelo y l | P3 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 191 comprobaciones: 34 pocos datos, 157 ok; la peor: «1. Fases · Golpe del riva |
| 12 | Validar cada medida con clips públicos anotados; el usuario no valida a mano (11-10 09:05, | P3 | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 1 comprobaciones: 1 ok |
| 13 | Casos nominales, límite, esquina y error en fuentes, algoritmos, IA, procesado, rendimient | B2 | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 14 | Rendimiento: un partido en horas, no días (12-10 13:09) | B1 | HECHO | 2 comprobación que falla | 2 comprobaciones: 1 aviso, 1 ok; la peor: «Tiempo: smoke_tennis-yusipopen-final-sobolenko-rybakin» (94 min para 35 min de vídeo ≈ 9.4 h para |
| 15 | Bajar y analizar vídeos de entrenadores de YouTube para aprender y encontrar huecos (12-10 | P1 | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 1 comprobaciones: 1 ok |
| 16 | Distinguir por contexto (derecha junto a la red o volea) y cubrir las medias voleas (10-10 | M6 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 5 comprobaciones: 3 pocos datos, 2 ok; la peor: «Volea a media pista con golpe  |
| 17 | Una entrada que se entienda sola: «no entiendo nada ni cómo usarla» (12-10 16:22) | P2 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 10 comprobaciones: 1 pocos datos, 9 ok; la peor: «Tu ejemplo: derecha paralela, |
| 18 | Herramienta Python cinemática 2D, 1 jugador y 1 golpe, parametrizable (10-10 17:27) | B7 | HECHO | 2 comprobación que falla | 1 comprobaciones: 1 pocos datos; la peor: «forehand: golpes analizados» (13 del lado cercano (con todo el detalle), 12 del lejano; con menos |
| 19 | Vídeos y salidas fuera del repo, rutas por configuración (10-10 17:27) | B7 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 20 | Windows nativo sin NVIDIA ni WSL, ONNX en CPU o DirectML (10-10 17:27) | B7 | HECHO | 2 comprobación que falla | 3 comprobaciones: 1 aviso, 2 ok; la peor: «Tiempo: smoke_tennis-yusipopen-final-sobolenko-rybakin» (94 min para 35 min de vídeo ≈ 9.4 h para |
| 21 | Dos pasadas, barata y fina de ±1 s (10-10 17:27) | B7 | HECHO | 2 comprobación que falla | 1 comprobaciones: 1 pocos datos; la peor: «forehand: golpes analizados» (13 del lado cercano (con todo el detalle), 12 del lejano; con menos |
| 22 | Solo la cámara principal, sin repeticiones ni primeros planos (10-10 17:27) | B7 | HECHO | 2 comprobación que falla | 1 comprobaciones: 1 pocos datos; la peor: «forehand: golpes analizados» (13 del lado cercano (con todo el detalle), 12 del lejano; con menos |
| 23 | Seguir a la jugadora en los cambios de lado (10-10 17:27) | B4 | HECHO | 2 comprobación que falla | 2 comprobaciones: 1 aviso, 1 ok; la peor: «Identidad en los cambios de lado: smoke_tennis-yusipopen-final-sobolenko-rybakin» (65 de 67 plano |
| 24 | OCR del marcador y presión (10-10 17:27) | M7 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 25 | Métricas por derecha: apoyo, base, rodillas, cadera, hombros, X-factor, codo, impacto, cad | M1 | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 5 comprobaciones: 5 ok |
| 26 | Fases y cadena completa, del salto inicial a la terminación (10-10 17:27; 11-10 08:22) | M1 | HECHO | 2 comprobación que falla | 8 comprobaciones: 5 aviso, 3 ok; la peor: «Fotograma clave: inicio de preparación» (encontrado en el 69% de los golpes) |
| 27 | Agregados por partido y set, fatiga, ganadores y errores, presión (10-10 17:27) | M5 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 28 | Informe HTML con gráficos y esqueleto (10-10 17:27) | P2 | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 29 | Fase 0: entorno y fps reales, con YOLO (10-10 17:27; 11-10 08:49) | B1 | HECHO | 2 comprobación que falla | 2 comprobaciones: 1 aviso, 1 ok; la peor: «Tiempo: smoke_tennis-yusipopen-final-sobolenko-rybakin» (94 min para 35 min de vídeo ≈ 9.4 h para |
| 30 | Estado del arte: igual, mejor o peor que otras apps (10-10 17:40; 11-10 09:05, 18:06) | B3 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 31 | Procesado incremental al añadir vídeos (10-10 18:05) | B7 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 32 | Ampliable a otros golpes y jugadores (10-10 18:07) | B7 | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 33 | Capturas de los mejores golpes de cada tipo y N imágenes de un golpe (10-10 18:12) | P2 | HECHO | 2 comprobación que falla | 8 comprobaciones: 5 aviso, 3 ok; la peor: «Fotograma clave: inicio de preparación» (encontrado en el 69% de los golpes) |
| 34 | Maqueta con datos inventados, con apoyos (10-10 18:13; 12-10 17:21) | P2 | HECHO | 1 construido, sin comprobar | no se comprueba en las salidas: maqueta (docs/maqueta-informe.html), no una salida |
| 35 | Medidas de la raqueta (altura, ángulos) en todo el golpe; qué miden los profesionales (11- | M4 | HECHO | 2 comprobación que falla | 11 comprobaciones: 2 pocos datos, 9 ok; la peor: «6. Matriz del usuario · Caída de la raqueta por debajo de la bola» (vista lateral de entre |
| 36 | Mano y antebrazo, cierre de la muñeca (11-10 09:56, 10:19) | M4 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 3 comprobaciones: 1 pocos datos, 2 ok; la peor: «4. Raqueta, swing y empuñadura |
| 37 | Prueba en local sin procesar 20 GB (11-10 09:02) | B7 | HECHO | 2 comprobación que falla | 1 comprobaciones: 1 pocos datos; la peor: «forehand: golpes analizados» (13 del lado cercano (con todo el detalle), 12 del lejano; con menos |
| 38 | Dirección y profundidad del golpe (11-10 17:24) | M5 | HECHO | 2 comprobación que falla | 6 comprobaciones: 3 pocos datos, 3 ok; la peor: «5. Bola, resultado y contexto · Bote: profundidad, anchura, dentro/fuera» (se mide (69% de  |
| 39 | Lado del fondo de la pista (11-10 17:32-17:33) | M5 | HECHO | 2 comprobación que falla | 1 comprobaciones: 1 pocos datos; la peor: «forehand: golpes analizados» (13 del lado cercano (con todo el detalle), 12 del lejano; con menos |
| 40 | Scripts de instalación, uso rápido y completo, sin leer nada (11-10 18:06, 18:21) | B7 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 41 | Exportación: cómo se ven y se graban (11-10 18:06; 19:01 «haz el punto 4») | B5 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 42 | Un golpe no son 8 pantallazos: vídeo y más (11-10 18:21) | P2 | HECHO | 3 comprobado en salidas | 11 comprobaciones: 11 ok |
| 43 | El PC no es servidor (11-10 18:27) | B7 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 44 | Sin vídeos del usuario, de entrenadores ni de otras jugadoras (11-10 19:37), salvo su entr | P1 | HECHO | 3 comprobado en salidas | 10 comprobaciones: 10 ok |
| 45 | Todo automático y completo: el usuario no revisa nada (11-10 09:05, 19:38; 12-10 11:41) | B7 | HECHO | 3 comprobado en salidas | 3 comprobaciones: 3 ok |
| 46 | Sin PDF enorme y sin inventar datos (11-10 19:40) | P1 | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 47 | Modelo técnico con fuentes; cómo saber si está completo (12-10 06:32) | P1 | HECHO | 2 comprobación que falla | 169 comprobaciones: 25 pocos datos, 144 ok; la peor: «1. Fases · Golpe del rival → split step» (se mide (100% de los golpes); el informe lo  |
| 48 | Posición de la cabeza y altura del cuerpo al inicio y al final (11-10 19:48) | M3 | HECHO | 3 comprobado en salidas | 3 comprobaciones: 3 ok |
| 49 | No perder contexto ni sesión; registros automáticos (12-10 11:39-11:45) | B7 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 50 | Progreso y monitorización visibles (12-10 14:37, 14:43) | B7 | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 51 | El código de la prueba es el de los casos reales (12-10 14:37) | B7 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 52 | Brave, no instalar Edge (12-10 16:48) | B7 | HECHO | 3 comprobado en salidas | 9 comprobaciones: 9 ok |
| 53 | No pasar de 100 a 0: conservar lo anterior (12-10 17:21) | P2 | HECHO | 3 comprobado en salidas | 9 comprobaciones: 9 ok |
| 54 | Qué hace ella cuando la rival golpea, la bola cruza la red, bota y llega arriba (12-10 17: | M3 | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 55 | Ver una bola cerca de la red y un apoyo cerrado con golpe paralelo (12-10 17:40) | M5 | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 1 comprobaciones: 1 ok |
| 56 | Barras horizontales con la diferencia de altura de la cabeza (12-10 17:40) | M3 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 57 | Nada de gráficas de muchas líneas ni tablas sin frases (12-10 17:10) | P1 | HECHO | 3 comprobado en salidas | 9 comprobaciones: 9 ok |
| 58 | La IA más moderna posible (11-10 09:05) | B3 | HECHO | 3 comprobado en salidas | 15 comprobaciones: 15 ok |
| 59 | Diferencias solo por encima del error y en situaciones equivalentes (10-10 18:05) | M5 | HECHO | 2 comprobación que falla | 6 comprobaciones: 2 pocos datos, 4 ok; la peor: «Punta de la raqueta respecto a la cabeza en el armado» (medido en 6 de 13 golpes; en «Apren |
| 64 | Todos los tipos de desplazamiento, del split step a la recuperación, con cada tipo de paso | M2 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 10 comprobaciones: 2 pocos datos, 8 ok; la peor: «3. Pies y desplazamiento · Sp |
| 65 | El play del vídeo funciona (no solo un fotograma) (12-10 18:14, 21:03, 21:14) | P2 | HECHO | 3 comprobado en salidas | 11 comprobaciones: 11 ok |
| 66 | Fechas y duración en los registros (12-10 18:25) | B7 | HECHO | 2 comprobación que falla | 2 comprobaciones: 1 falta, 1 ok; la peor: «Registros con fecha y duración» (59 de 60 registros con fecha de inicio y de fin o duración; sin  |
| 67 | No borrar el trabajo hecho: lo complejo como extra (12-10 22:35; 13-10 05:48 p6) | P2 | HECHO | 3 comprobado en salidas | 13 comprobaciones: 13 ok |
| 68 | La meta: mejorar mi derecha tomando la de X como base (12-10 22:25; 13-10 05:48 p5) | P1 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 8 comprobaciones: 1 pocos datos, 7 ok; la peor: «Tu ejemplo: derecha paralela,  |
| 69 | Ejemplo: «derecha paralela, apoyo cerrado, parada, bola plana, lado derecho» (cómo lo hace | M5 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 1 comprobaciones: 1 pocos datos; la peor: «Tu ejemplo: derecha paralela, apoyo  |
| 70 | Las 2000 y pico combinaciones, usables y validadas (13-10 05:48 p2; 06:00) | M5 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 10 comprobaciones: 9 pocos datos, 1 ok; la peor: «Bola rápida / lenta: cada med |
| 71 | El conocimiento de los vídeos de entrenadores en la web (12-10 21:31; 13-10 05:48 p3) | P1 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 21 comprobaciones: 16 pocos datos, 5 ok; la peor: «R1 Golpe liftado de trayecto |
| 72 | El conocimiento del chat (modelo técnico, taxonomía, matriz) implementado en la web, no so | P1 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 170 comprobaciones: 25 pocos datos, 145 ok; la peor: «1. Fases · Golpe del riva |
| 73 | Revisar la web de arriba abajo para que aporte valor (13-10 05:48 p6) | P2 | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 22 comprobaciones: 22 ok |
| 74 | ¿El análisis de las apps de pago y libres fue profundo o superficial? (13-10 05:48 p7) | P4 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#74); no se comprueba en las salidas: análisis documental (docs/comparativa_apps.md), no una salida |
| 75 | Velocidad: «10 golpes en 5 horas es absurdo» (13-10 05:48 p10) | B1 | HECHO | 2 comprobación que falla | 2 comprobaciones: 1 aviso, 1 ok; la peor: «Tiempo: smoke_tennis-yusipopen-final-sobolenko-rybakin» (94 min para 35 min de vídeo ≈ 9.4 h para |
| 76 | «Un 50 % de golpes dudosos» (13-10 05:48 p10) | P3 | HECHO | 2 comprobación que falla | 1 comprobaciones: 1 aviso; la peor: «Golpes dudosos (duda sobre el golpe, no sobre una medida)» (8 de 13 del lado cercano (62%); motivos: ph |
| 77 | No lanzar pruebas de 6 h para validar (13-10 06:01) | B1 | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 78 | No depender de que al usuario se le ocurran funciones (13-10 06:09) | P5 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#78); no se comprueba en las salidas: proceso: Claude propone las funciones desde la matriz y los entrenadores |
| 79 | Vídeos de entrenamiento con otras cámaras, en un apartado aparte y marcado (12-10 21:31, 2 | P1 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 20 comprobaciones: 11 pocos datos, 9 ok; la peor: «Derechas filmadas de lado» ( |
| 80 | Encadenar solo la prueba y las comprobaciones; que Claude lo monitorice (12-10 22:43) | B7 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 81 | Tamaño de la salida; comprobación sin gastar tokens (12-10 22:40) | B7 | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 82 | Dónde se graban las salidas, qué va a git, qué se reutiliza (12-10 22:47) | B7 | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 83 | Árbol de ficheros generados y validados (12-10 22:25) | B7 | HECHO | 3 comprobado en salidas | 5 comprobaciones: 5 ok |
| 84 | Matriz §1 Cadena cinética (suelo → pelvis → separación → tronco → codo → muñeca) (12-10 21 | M1 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 10 comprobaciones: 1 pocos datos, 9 ok; la peor: «6. Matriz del usuario · Rotac |
| 85 | Matriz §2 Cuerpo (cabeza, brazos, tronco, piernas, pie de arrastre) | M3 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 14 comprobaciones: 4 pocos datos, 10 ok; la peor: «6. Matriz del usuario · Rodi |
| 86 | Matriz §3 Raqueta (bucle, caída, cara, trayectoria) | M4 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 13 comprobaciones: 2 pocos datos, 11 ok; la peor: «6. Matriz del usuario · Caíd |
| 87 | Matriz §4 Apoyos (abierto, semiabierto, neutro o cerrado, salto, abierto extremo) | M2 | HECHO | 2 comprobación que falla | 4 comprobaciones: 1 pocos datos, 3 ok; la peor: «6. Matriz del usuario · Apoyo abierto extremo defensivo» (se mide (77% de los golpes); el i |
| 88 | Matriz §5 Pies (split, ajuste, cruzado, paso de ataque, recuperación) | M2 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 8 comprobaciones: 1 pocos datos, 7 ok; la peor: «3. Pies y desplazamiento · Spl |
| 89 | Matriz §6 Modalidades (plano, liftado, cortado, botepronto, volea, 3 terminaciones) | M6 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 8 comprobaciones: 1 pocos datos, 7 ok; la peor: «Botepronto / media volea: caso |
| 90 | Matriz §7 Adaptación a la bola (rápida, corta, alta, lateral) | M5 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 16 comprobaciones: 15 pocos datos, 1 ok; la peor: «Golpe angulado (#132)» (0 go |
| 91 | Matriz §8 Dirección (cruzado, paralelo, dentro-fuera, dentro-dentro) | M5 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 3 comprobaciones: 2 pocos datos, 1 ok; la peor: «Dirección del golpe» (cruzada  |
| 92 | Matriz §9 Control (zona de impacto, relajación, equilibrio) | M3 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 4 comprobaciones: 1 pocos datos, 3 ok; la peor: «6. Matriz del usuario · Zona d |
| 93 | Matriz §10 Propiedades de la raqueta | P1 | HECHO | 1 construido, sin comprobar | — |
| 94 | Matriz §11 Cinemática cuantitativa (velocidad de raqueta, °/s, fuerza, rpm) | P1 | HECHO | 1 construido, sin comprobar | — |
| 95 | Matriz §12 Neuro y visión (latencia, mirada, EMG) | M3 | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 3 comprobaciones: 3 ok |
| 96 | Matriz §13 Microbiomecánica (muñeca, codo, hombro) | P1 | HECHO | 1 construido, sin comprobar | — |
| 97 | Matriz §14 Fugas de energía (apertura prematura, casting, vector) | M1 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 4 comprobaciones: 1 pocos datos, 3 ok; la peor: «6. Matriz del usuario · Libera |
| 98 | Matriz §15 Contexto y ambiente (superficie, aerodinámica) | M7 | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 99 | Mejora 1 (entrenadores): líneas dibujadas sobre el fotograma | P1 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 100 | Mejora 2: raqueta al lado del cuerpo o detrás de la espalda, y adónde apunta la punta | M4 | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 1 comprobaciones: 1 ok |
| 101 | Mejora 3: altura y separación del codo | M3 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 102 | Mejora 4: punta de la raqueta respecto a la cabeza en el armado | M4 | HECHO | 2 comprobación que falla | 1 comprobaciones: 1 pocos datos; la peor: «Punta de la raqueta respecto a la cabeza en el armado» (medido en 6 de 13 golpes; en «Aprende»; f |
| 103 | Mejora 5: transferencia de peso en una frase | M2 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 104 | Mejora 6: empuje de piernas («bajar y subir») | M2 | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 105 | Mejora 7: ritmo con la bola (caída al subir la bola) | M5 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 106 | Mejora 8: frenado de los hombros antes del contacto | M1 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 107 | Mejora 9: caída por debajo de la bola | M4 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 2 comprobaciones: 2 pocos datos; la peor: «6. Matriz del usuario · Caída de la  |
| 108 | Mejora 10: «gira mientras corre» | M2 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 109 | Mejora 11: frases con datos existentes (mano libre, terminación, base al terminar, desplaz | P1 | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 4 comprobaciones: 4 ok |
| 110 | Mejora 12: «Lo que la distingue» (2-3 rasgos frente a la literatura, con vídeo) | P1 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 111 | Mejora 13: consigna «para imitarla» y error que evita, por fase | P1 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 112 | Mejora 14: clase descriptiva de estilo (`fh_style`) | P1 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 113 | Mejora 15: examen interno con las afirmaciones de entrenadores (R1-R25) | P1 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 19 comprobaciones: 16 pocos datos, 3 ok; la peor: «R1 Golpe liftado de trayecto |
| 114 | Cuerpo respecto a la bola en cada momento (golpe rival, cruza la red, cae, bota, sube, gol | M3 | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 115 | Cuánto baja y sube el cuerpo, con fotogramas y barras horizontales: de la espera al punto  | M3 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 116 | Distancia entre las piernas en los golpes: base y estabilidad (13-10 11:50) | M2 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 117 | Hacia dónde mira el tronco al terminar (valla lateral, de frente, girado) según el golpe ( | M3 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 118 | Validar cada medida de forma automática, no a mano: ¿técnica o ruido? (13-10 08:40-10:30) | P3 | HECHO | 2 comprobación que falla | 2 comprobaciones: 1 pocos datos, 1 ok; la peor: «forehand: medidas que dependen de la cámara (la cámara explica ≥ 10% de su variación)» (13  |
| 119 | Automatizar todo el ciclo en el PC: el usuario no lanza pruebas ni avisa (13-10 10:40, 11: | B7 | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 120 | Vídeo a pantalla completa (13-10 12:00) | P2 | HECHO | 3 comprobado en salidas | 9 comprobaciones: 9 ok |
| 121 | Ver lo que se pinta por separado, por grupos o una a una (13-10 12:00) | P2 | HECHO | 3 comprobado en salidas | 9 comprobaciones: 9 ok |
| 122 | Web en 2 vistas principales y el resto en «Más», en dos grupos (funcional y técnico), sin  | P2 | HECHO | 3 comprobado en salidas | 9 comprobaciones: 9 ok |
| 123 | Lo que se aprende en una sesión: plan de 3 prioridades en orden, foco externo por fase, de | P1 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 124 | Hacia dónde mira el tronco y las manos en la espera, medidas fiables (13-10 13:00) | M3 | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 1 comprobaciones: 1 ok |
| 125 | Velocidad, rendimiento y algoritmia antes del tramo largo nocturno (13-10 13:05) | B1 | HECHO | 2 comprobación que falla | 2 comprobaciones: 1 aviso, 1 ok; la peor: «Tiempo: smoke_tennis-yusipopen-final-sobolenko-rybakin» (94 min para 35 min de vídeo ≈ 9.4 h para |
| 126 | Consignas con su número en «Cómo hacerlo tú» («baja unos 14 cm desde la espera, como ella» | P1 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 127 | Guía de primer uso, «empieza aquí» (13-10 14:00) | P2 | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 128 | Glosario de términos (13-10 14:00) | P2 | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 130 | Resto de derecha (devolver el saque) con todas sus variantes, en la matriz y en la aplicac | M6 | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 12 comprobaciones: 12 ok |
| 131 | detectar impactos de bola por AUDIO (Chat, 10-10 17:27) | M5 | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 132 | ángulos (golpe angulado) — repetido el 19-10 08:11: «golpe angulado ... te lo he dicho muc | M5 | HECHO | 2 comprobación que falla | 2 comprobaciones: 1 pocos datos, 1 ok; la peor: «Golpe angulado (#132)» (0 golpes de 13 (la clase «Golpe angulado» se pudo decidir en 5; sin |
| 134 | prefiero una baseline completa a cerrar más golpes (Chat, 11-10 18:06) | B6 | HECHO | 2 comprobación que falla | 2 comprobaciones: 1 pocos datos, 1 ok; la peor: «forehand: golpes analizados» (13 del lado cercano (con todo el detalle), 12 del lejano; con |
| 135 | distancia al fondo, red (Chat, 11-10 19:23) | M5 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#135); sin comprobación automática asignada |
| 136 | lo puedes añadir al contexto o fichero base? (Chat, 13-10 09:47) | B7 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 137 | hay algo que se pueda paralelizar ... threading (Chat, 13-10 18:31) | B1 | HECHO | 2 comprobación que falla | 6 comprobaciones: 2 aviso, 4 ok; la peor: «Tiempo: smoke_tennis-yusipopen-final-sobolenko-rybakin» (94 min para 35 min de vídeo ≈ 9.4 h para |
| 138 | se puede hacer modelos hibridos de alguna manera? (Chat, 13-10 18:34) | B3 | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 139 | si se pierde calidad no tocamos nada (Chat, 14-10 20:08) | B7 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 140 | de la jugadora de fondo se sacan imagenes para la captura de datos en vista frontal? (Chat | P5 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#140); sin comprobación automática asignada |
| 141 | (punto 0) la imagen ... Estroboscópica ... no vale para nada; ... Sus pies en este golpe t | P2 | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 142 | (punto 2) como se puede hacer una aplicacion profesional ... mas jugadores, mas golpes ... | P4 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#142); sin comprobación automática asignada |
| 143 | (punto 3) esta es una guia para la derecha de otra jugadora ... revisar si aplica todo (Ch | P1 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#143); sin comprobación automática asignada |
| 144 | (punto 4) hay tareas o schedulers ... salen terminales y se apagan solos (Chat, 17-10 09:4 | B7 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 145 | no quiero nada en la nube ni pagar ni nada (Chat, 17-10 10:09) | B7 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 146 | borra las carpetas de pruebas antiguas (Chat, 17-10 10:49) | B7 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 147 | la guia de ivanovic esta aplicada al 100 por 100? sobre todo los puntos 1 2 3 5 6 y 10 (Ch | P1 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#147); sin comprobación automática asignada |
| 148 | empieza por la maqueta de una fase (Chat, 17-10 13:05) | P2 | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 149 | no se como validar eso lo tienes que hacer tu (Chat, 17-10 13:11) | P3 | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 150 | estos son mas videos de youtube para analizar (3 enlaces) (Chat, 17-10 17:21) | P1 | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 151 | como se separan los golpes (derecha, reves, saque, voleas), los jugadores, los partidos (C | B4 | HECHO | 2 comprobación que falla | 2 comprobaciones: 1 pocos datos, 1 ok; la peor: «forehand: golpes analizados» (13 del lado cercano (con todo el detalle), 12 del lejano; con |
| 152 | como queda la estructura de directorios ... carpeta normalizada de los jugadores (Chat, 18 | B7 | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 153 | y analizo estos videos (2 enlaces de Olivari) (Chat, 18-10 11:19) | P1 | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 154 | mi movil es android google pixel 8 ... que copie directo al pixel (Chat, 18-10 12:11) | P6 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#154); sin comprobación automática asignada |
| 155 | es fisicamente imposible que en un partido solo de 86 o 77 golpes ... no quiero que se pie | B4 | HECHO | 2 comprobación que falla | 3 comprobaciones: 1 aviso, 2 ok; la peor: «Saques por punto de su saque: smoke_tennis-yusipopen-final-sobolenko-rybakin» (10 de 13 puntos de |
| 156 | como sabes la identidad de la jugadora y porque hay fallos? porque no buscas en la web de  | P5 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#156); sin comprobación automática asignada |
| 157 | bola corta baja cerca de la red (Chat, 19-10 08:11) | M5 | HECHO | 2 comprobación que falla | 1 comprobaciones: 1 pocos datos; la peor: «Bola corta baja cerca de la red (#157)» (0 golpes de 13 (la clase «Bola corta cerca de la red» se |
| 158 | bola corta alta cerca de la red (Chat, 19-10 08:11) | M5 | HECHO | 2 comprobación que falla | 1 comprobaciones: 1 pocos datos; la peor: «Bola corta alta cerca de la red (#158)» (0 golpes de 13 (la clase «Bola corta cerca de la red» se |
| 159 | volea a media pista con el golpe de fondo derecha o reves (sin ser empuñadura de volea) (C | M6 | PARCIAL | 2 comprobación que falla | a medias según el registro (ver docs/peticiones_usuario.md); 2 comprobaciones: 2 pocos datos; la peor: «Volea a media pista con golpe de fon |
| 160 | la app que hiciste completa como se arranca, se puede usar ahora? (Chat, 19-10 08:11) | B7 | HECHO | 3 comprobado en salidas | 5 comprobaciones: 5 ok |
| 161 | como se enlazan los partidos de una jugadora ... tienen que estar el analisis junto (Chat, | B7 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 162 | Galerías ordenadas por calidad de captura, representatividad y resultado del punto (CLAUDE | P2 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#162); sin comprobación automática asignada |
| 163 | Final del armado (máximo giro, raqueta más atrás) (Matriz (literatura), §1) | M1 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#163); sin comprobación automática asignada |
| 164 | Final de la extensión (Matriz (literatura), §1) | M1 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#164); sin comprobación automática asignada |
| 165 | Giro de cadera y de hombros al final del armado (Matriz (literatura), §2) | M1 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#165); sin comprobación automática asignada |
| 166 | Separación cadera–hombros (X-factor) (Matriz (literatura), §2) | M1 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#166); sin comprobación automática asignada |
| 167 | Cabeza quieta tras el impacto (Matriz (literatura), §2) | M3 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#167); sin comprobación automática asignada |
| 168 | Hombros más girados que la cadera en el impacto (Matriz (literatura), §2) | M1 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#168); sin comprobación automática asignada |
| 169 | Transferencia de peso del armado al impacto (Matriz (literatura), §2) | M2 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#169); sin comprobación automática asignada |
| 170 | Empuje de piernas («bajar y subir») (Matriz (literatura), §2) | M2 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#170); sin comprobación automática asignada |
| 171 | Primer paso: tipo (gravity, jab, pivot, counter, cruzado, lateral) (Matriz (literatura), § | M2 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#171); sin comprobación automática asignada |
| 172 | Cada paso nombrado: lateral (sin cruzar), cruzado, de carrera, hacia delante, hacia atrás, | M2 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#172); sin comprobación automática asignada |
| 173 | Frenado: último paso largo con caída de la velocidad (Matriz (literatura), §3) | M2 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#173); sin comprobación automática asignada |
| 174 | Patada atrás (tijera) tras el impacto (Matriz (literatura), §3) | M2 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#174); sin comprobación automática asignada |
| 175 | Recuperación: tipo de cada paso de vuelta, cuándo empieza (Matriz (literatura), §3) | M2 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#175); sin comprobación automática asignada |
| 176 | Nuevo split step antes del siguiente golpe de la rival (Matriz (literatura), §3) | M2 | FALTA | 0 sin construir | SIN HACER según el registro (#176, docs/peticiones_usuario.md) |
| 177 | Orientación del pie (talón → dedo gordo respecto a la línea de fondo) en el armado y el im | M2 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#177); sin comprobación automática asignada |
| 178 | Pivote sobre la punta del pie de atrás (talón arriba, punta apoyada) (Matriz (literatura), | M2 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#178); sin comprobación automática asignada |
| 179 | Raqueta al lado del cuerpo o por detrás de la espalda en el armado (debate WTA/ATP) (Matri | M4 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#179); sin comprobación automática asignada |
| 180 | Retraso de la muñeca (lag) (Matriz (literatura), §4) | M1 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#180); sin comprobación automática asignada |
| 181 | Cara en el impacto (Matriz (literatura), §4) | M4 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#181); sin comprobación automática asignada |
| 182 | Velocidad de la raqueta relativa entre golpes (Matriz (literatura), §4) | M4 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#182); sin comprobación automática asignada |
| 183 | Posición de la mano en el mango (Matriz (literatura), §4) | M4 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#183); sin comprobación automática asignada |
| 184 | Altura de la bola en su vuelo, bote, punto más alto; contacto subiendo / arriba / cayendo  | M5 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#184); sin comprobación automática asignada |
| 185 | Longitud del peloteo (Matriz (literatura), §5) | M7 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#185); sin comprobación automática asignada |
| 186 | Resto, globo, dejada, volea, subida a la red (Matriz (literatura), §5) | M6 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#186); sin comprobación automática asignada |
| 187 | Ganador / error (forzado o no) (Matriz (literatura), §5) | M7 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#187); sin comprobación automática asignada |
| 188 | Resto de primer o de segundo saque (Matriz (literatura), §5b) | M6 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#188); sin comprobación automática asignada |
| 189 | «Cómo» de la fase 1: «mirando la raqueta de la rival» (YouTube, 18-10 Olivari 4) | P1 | FALTA | 0 sin construir | SIN HACER según el registro (#189, docs/peticiones_usuario.md) |
| 190 | Clase de forma del armado: bucle verdadero, loop falso, recto atrás; tendencia «punta arri | M4 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#190); sin comprobación automática asignada |
| 191 | Alarmas por golpe: cara al cielo, punta hacia la red tras el giro, pausa arriba, caída baj | M4 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#191); sin comprobación automática asignada |
| 192 | Terminación «hacia adelante», «la mano libre recoge la raqueta», codo al terminar (Guía Iv | M3 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#192); sin comprobación automática asignada |
| 193 | Mano libre en la aceleración y el impacto (pliegue, que no cruce) (Guía Ivanovic, hueco 10 | M3 | FALTA | 0 sin construir | SIN HACER según el registro (#193, docs/peticiones_usuario.md) |
| 194 | «Sus principios» (5-6 frases) y «Lo que la distingue» (Guía Ivanovic, hueco 13) | P1 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#194); sin comprobación automática asignada |
| 195 | Fuentes en COACH: Iino y Kojima 2001, Bahamonde y Knudson 2003, Kawamoto 2019, LTA, Wulf,  | P1 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#195); sin comprobación automática asignada |
| 196 | Medidas de lado: codo por delante de la cadera, inclinación del tronco en la espera (Guía  | M2 | FALTA | 0 sin construir | SIN HACER según el registro (#196, docs/peticiones_usuario.md) |
| 197 | Progresión por etapas sin calendario y paso a pista (Guía Ivanovic, hueco 19) | P1 | FALTA | 0 sin construir | SIN HACER según el registro (#197, docs/peticiones_usuario.md) |
| 198 | Tiempo entre puntos (rutina) bajo presión (Guía Ivanovic, hueco 20) | M7 | FALTA | 0 sin construir | SIN HACER según el registro (#198, docs/peticiones_usuario.md) |
| 199 | Bote: GBDT/CatBoost sobre la trayectoria (Estado del arte, 13-10) | B3 | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 200 | Pista: TennisCourtDetector (14 puntos) + refinado (Estado del arte, 13-10) | B3 | HECHO | 3 comprobado en salidas | 4 comprobaciones: 4 ok |
| 201 | Marcador: rapidocr 3.x con PP-OCRv5 (Estado del arte, 13-10) | B3 | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 202 | Bola: probar WASB (Estado del arte, 13-10) | B3 | HECHO | 3 comprobado en salidas | 3 comprobaciones: 3 ok |
| 203 | 3D: prueba A/B con MotionAGFormer (Estado del arte, 13-10) | B3 | HECHO | 3 comprobado en salidas | 3 comprobaciones: 3 ok |
| 204 | Golpe: clasificador aprendido con F3Set (E2E-Spot/F3ED) (Estado del arte, 13-10) | B3 | HECHO | 3 comprobado en salidas | 5 comprobaciones: 5 ok |
| 205 | Volumen: unos 400 golpes con 4 partidos (Comparativa apps, §4.3) | B4 | HECHO | 2 comprobación que falla | 1 comprobaciones: 1 aviso; la peor: «Volumen: forehand analizados en los partidos» (25 golpes (13 cerca con todo el detalle, 12 lejos) en 1  |
| 206 | Validación de cuerdas y 3D con referencia real (Comparativa apps, §4.4) | M4 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#206); sin comprobación automática asignada |
| 207 | Golpes: sin volea, remate ni cortado (Comparativa apps, §3 Peor) | M6 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#207); sin comprobación automática asignada |
| 208 | Lógica duplicada JS/Python: calcular una vez en Python (Revisión completa, §2 fallo 17) | P2 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#208); sin comprobación automática asignada |
| 209 | Passing y globo (Revisión completa, §3 B) | M6 | FALTA | 0 sin construir | SIN HACER según el registro (#209, docs/peticiones_usuario.md) |
| 210 | Dejada (bote muy corto en campo rival) (Revisión completa, §3 B) | M6 | FALTA | 0 sin construir | SIN HACER según el registro (#210, docs/peticiones_usuario.md) |
| 211 | CHECKS de la mano en el armado da por hecho que va por debajo del hombro (Auditorías 17-10 | M4 | FALTA | 0 sin construir | SIN HACER según el registro (#211, docs/peticiones_usuario.md) |
| 212 | Grados de estimaciones poco fiables como objetivo (cara en el impacto) (Auditorías 17-10,  | M4 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#212); sin comprobación automática asignada |
| 213 | Textos COACH (el porqué con fuente) en todas las claves de la lección (Auditorías 17-10, t | P1 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#213); sin comprobación automática asignada |
| 214 | Fuentes de Ivanovic §3 #17 (Auditorías 17-10, técnica #18) | P1 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#214); sin comprobación automática asignada |
| 215 | Armado «antes» o «al» bote según el sitio (Auditorías 17-10, técnica #22) | M5 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#215); sin comprobación automática asignada |
| 216 | Pendiente de la guía: punta arriba/codo alto, terminación hacia adelante, codo libre (Audi | M4 | FALTA | 0 sin construir | SIN HACER según el registro (#216, docs/peticiones_usuario.md) |
| 217 | Documentos desactualizados (aprendido_entrenadores §2 y §4) (Auditorías 17-10, técnica #26 | D | FALTA | 0 sin construir | SIN HACER según el registro (#217, docs/peticiones_usuario.md) |
| 218 | La fuente son los partidos: que funcione la vista de fondo en los dos lados, que funcionen | B4 | HECHO | 3 comprobado en salidas | 5 comprobaciones: 5 ok |
| 219 | Las tomas de la cámara de fondo cuentan para los dos lados: golpes del fondo contados y co | B4 | HECHO | 3 comprobado en salidas | 3 comprobaciones: 3 ok |
| 220 | Almacenamiento definitivo: árbol por jugador, partido y golpe; nombres, colisiones y todos | B7 | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 221 | Detectar golpes con modelos entrenados, como las apps profesionales, no con reglas a mano  | B3 | HECHO | 3 comprobado en salidas | 5 comprobaciones: 5 ok |
| 222 | Un clic por partido para decir quién es ella (19-10 19:57) | B7 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 223 | Revés y derecha cortados (20-10 06:33) | M6 | FALTA | 0 sin construir | SIN HACER según el registro (#223, docs/peticiones_usuario.md) |
| 224 | Saques: plano, cortado o kick; primero o segundo (20-10 07:30) | M6 | FALTA | 0 sin construir | SIN HACER según el registro (#224, docs/peticiones_usuario.md) |
| 225 | La aplicación no se cuelga ni ralentiza el PC (24-10 10:22-10:47) | B2 | HECHO | 3 comprobado en salidas | 3 comprobaciones: 3 ok |
| 226 | Lista de partidos profesional: nombres normalizados, torneo, ronda, fecha, fotos; sin prue | B7 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 227 | Pantalla completa en la aplicación (24-10 10:36) | B7 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 229 | Renombrar el vídeo no rompe nada; el partido se identifica por su contenido (25-10 13:21-1 | B7 | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 230 | Uso de CPU, RAM, iGPU y disco por etapa (mín, media, máx) y aprovechar el equipo (26-10 12 | B1 | HECHO | 2 comprobación que falla | 4 comprobaciones: 1 aviso, 3 ok; la peor: «Tiempo: smoke_tennis-yusipopen-final-sobolenko-rybakin» (94 min para 35 min de vídeo ≈ 9.4 h para |
| 231 | Un partido no puede tardar el doble sin saber la causa; la etapa de tomas lenta (26-10 11: | B1 | HECHO | 2 comprobación que falla | 4 comprobaciones: 1 aviso, 3 ok; la peor: «Tiempo: smoke_tennis-yusipopen-final-sobolenko-rybakin» (94 min para 35 min de vídeo ≈ 9.4 h para |
| 232 | Ningún proceso que se pueda colgar sin probar; la exportación del revés se colgó (27-10 09 | B2 | HECHO | 3 comprobado en salidas | 5 comprobaciones: 5 ok |
| 233 | Una referencia completa y medida antes de validar nada (26-10 11:09) | B6 | HECHO | 2 comprobación que falla | 2 comprobaciones: 1 pocos datos, 1 ok; la peor: «forehand: golpes analizados» (13 del lado cercano (con todo el detalle), 12 del lejano; con |
| 234 | Prueba de valor de la aplicación con los datos reales (27-10 07:21) | B6 | HECHO | 3 comprobado en salidas | 3 comprobaciones: 3 ok |
| 235 | Cadena cinética, footwork y timing: lo que define el golpe (27-10 09:33) | M1 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#235); sin comprobación automática asignada |
| 236 | Huellas numeradas sobre los pies y patrones de pasos (27-10 09:38) | M2 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#236); sin comprobación automática asignada |
| 237 | El PC empieza cada trabajo al momento (GitHub Actions), sin esperas de 10-40 min (27-10 10 | B1 | HECHO | 3 comprobado en salidas | 1 comprobaciones: 1 ok |
| 238 | La validación es siempre automática; el usuario no valida la aplicación (27-10 11:42) | P3 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#238); sin comprobación automática asignada |
| 239 | No se descarta ninguna petición (27-10 11:42) | D | HECHO | 1 construido, sin comprobar | sin comprobación automática asignada |
| 240 | Comparar la aplicación con las profesionales una vez estén los golpes (27-10 11:42) | P4 | FALTA | 0 sin construir | SIN HACER según el registro (#240, docs/peticiones_usuario.md) |
| 241 | Aplicación genérica: jugadores, golpes y partidos por configuración, nada fijo en el códig | B7 | HECHO | 3 comprobado en salidas | 2 comprobaciones: 2 ok |
| 242 | Flujo de la aplicación: añadir N partidos, elegir la persona, jugadores masculinos y femen | B7 | PARCIAL | 2 comprobación que falla | sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); 5 comprobaciones: 5 ok |
| 243 | Todos los escenarios del producto los contempla Claude sin esperar a que se pidan (27-10 1 | P5 | PARCIAL | 1 construido, sin comprobar | A MEDIAS según el registro (#243); sin comprobación automática asignada |
| 244 | Resultado del punto creíble (hoy 2 golpes ganadores en 191 derechas) (prueba de valor 27-1 | M7 | FALTA | 0 sin construir | SIN HACER según el registro (#244, docs/peticiones_usuario.md) |
| 245 | Rivales, fechas y rondas bien escritos en el informe (prueba de valor 27-10) | M7 | FALTA | 0 sin construir | SIN HACER según el registro (#245, docs/peticiones_usuario.md) |
