# Comparación de la guía «Derecha estilo Ivanovic · v13» con TennisBio

He leído entera la guía: las 12 pestañas, de arriba abajo, sin modificarla. En el repositorio he leído `CLAUDE.md`, `docs/estado_proyecto.md`, `docs/matriz_cobertura.md`, `docs/peticiones_usuario.md`, el principio de `docs/aprendido_entrenadores.md`, `learn.py` completo, `explain.py` (COACH, PHASE_FOCUS, PRIMARY, NOT_MEASURABLE, grip_compatible) y la estructura de pantallas de `report_template.html`. Además he buscado con grep en `technique.py`, `footwork.py`, `audit.py`, `learn_check.py` y `export.py`. No he modificado ningún fichero.

**Lo más importante:**
- **Una contradicción en nuestros textos.** `explain.py`, `COACH["stroke.pause_at_loaded"]`, dice: «Una pausa breve al final del armado sincroniza el swing con la bola» (Elliott 2006). La guía cita la misma fuente para lo contrario: con una pausa se pierde la energía del ciclo de estiramiento-acortamiento. Nuestra propia consigna de `learn.py` (`class.takeback`: «sin pararte») también va en contra. Hay que revisar la fuente y corregir el texto.
- **Medidas que ya calculamos y «Cópiala» no enseña.** Son las claves de la guía: giro antes de que la bola cruce la red, pausa arriba (loop falso), mano y codo en el armado, terminación alta, contacto en el pico.
- **Lo que no es de su derecha.** El plan semanal, la mente y el material son conocimiento genérico. Solo cabe como texto con fuente, y el usuario ya descartó la «hoja de sesión» (petición 129).

## 1. Cómo es la guía

**Pestañas.** Inicio, 1 Técnica, 2 Plan, 3 Diagnóstico, 4 Chuletas, 5 Lectura y footwork, 6 Táctica y resto, 7 Mente, 8 Equipamiento, 9 Referencia visual, 10 Timing, distancia y peso, 11 Glosario.

**Cómo enseña:**
- **Un perfil concreto de alumno.** Hombre de 45 años, 1,80 m, empuñadura eastern o semiwestern, revés a una mano, entrena en casa en 3-4 pasos.
- **Una cadena de causas.** Sus 5 problemas (de frente, peso atrás, tarde, bajo, girarse de más) salen de una sola cadena: leer tarde → split tarde → giro tarde → contacto tarde → el cuerpo compensa. De ahí salen dos palancas: «preparar antes» y «proyectar hacia adelante». Las resumen 6 principios.
- **Una sola fuente de cifras (pestaña 1).** Las 7 fases llevan rangos (ángulos, cm, grip /10, reparto del peso), tablas de alturas, punta y cuerdas por momento, y codo, muñeca y grip fase a fase. También explica la biomecánica con 6 artículos citados y separa siempre «dato medido» de «explicación de entrenador».
- **Práctica por drills.** Cada drill tiene código (A1-A9, B1-B8, T1-T5, P1-P9, F1-F6, D1-D4, R1-R4), duración, series × repeticiones y un «Comprueba:» con el criterio. Encajan en sesiones A, B y C, en una semana según los días de pista y en una progresión de 12 semanas con 4 etapas de paso a pista.
- **Autodiagnóstico.** Tres entradas: síntoma, resultado de la bola y lo que se ve en tu vídeo. Cada una lleva a una causa y a unos drills. Hay tests de progreso con metas por semana y protocolos de molestias.
- **Uso diario.** Chuletas (las 7 fases en una línea, el ritmo «gira, atrás, golpe», checklists antes de jugar y táctico), ayudas vocales con fuente (metaanálisis) y diario.

**Cómo se usa.** La tabla de Inicio dice para qué sirve cada pestaña y cuándo abrirla (antes de la sesión, tras grabarte, en el banquillo, en el próximo encordado). Hay un «orden recomendado», los límites de la guía y una lista de cambios respecto a la v12.

**Recursos de diseño.** Tablas de consulta, listas numeradas, «Comprueba:» en cada drill, palabras en voz alta, referencias cruzadas entre pestañas, fuentes enlazadas, glosario alfabético de 26 términos y avisos de honestidad («esto es estimación»).

## 2. Cada elemento de la guía frente a la app

Abreviaturas:
- **Cópiala** = `tab-aprende` (`learn.py`).
- **Patrón típico** = «Su patrón típico» (`sec-modelo`, `explain.py`).
- **Golpe** = «Sus golpes → un golpe» (`tab-golpe`).
- **Conclusiones** = `tab-conclusiones`.
- **Vista lateral** = `tab-lateral` (`practice.py`).

En «¿Aplica?»:
- **Sí** = medible desde la tele.
- **Texto** = solo como texto de entrenador con fuente.
- **No-otra** = es de otra jugadora o del alumno.
- **No-TV** = no medible desde la tele.
- **No-dec** = decisión del usuario.

### Inicio (estructura y método)

| Elemento | ¿Lo tiene la app? | ¿Aplica? | Qué añadir |
|---|---|---|---|
| Tabla de pestañas: para qué y cuándo abrir cada una | Parcial: «Empieza aquí» y menú «Más» | Texto | Una línea «cuándo usar» en cada pantalla de «Más» |
| Perfil del alumno | Parcial: solo su altura, guardada en el navegador (`a-uh`) | Sí (dato del navegador) | Mano dominante del usuario para reflejar las consignas; nivel opcional |
| «Cómo leer las cifras» (orientativas, tendencia) | Sí: etiquetas N golpes, provisional, ruidosa; pantalla Fiabilidad | — | — |
| Cambios respecto a la versión anterior | Sí: «Novedades» | — | — |
| Cadena causal de 5 problemas → 2 palancas | No | Texto, con sus medidas | Un «encadenado de errores» que lleve a los puntos de control (tiempo → contacto → compensaciones) |
| 6 principios | Parcial: «Su firma» y el estilo en una frase | Sí | «Sus principios»: 5-6 rasgos fiables en frases, del modelo |
| Orden recomendado | Sí: «Tu plan» (tiempo → contacto → piernas → trayectoria → terminación) | — | — |
| Límites de la guía (no sustituye al entrenador, fisio) | Parcial: «Lo que la tele no permite medir» | Texto | Una frase de límites de uso |

### 1 · Técnica

| Elemento | ¿Lo tiene la app? | ¿Aplica? | Qué añadir |
|---|---|---|---|
| Grip continental en la espera; cambio con la mano libre durante el giro | No (se dice «no medible», `NOT_MEASURABLE`) | No-TV | — |
| Mano libre en la garganta en la espera y en el giro | Sí: `class.ready_hands`, `takeback.hands_apart` (Cópiala, fase 1) | Sí (dudosa: petición 7, R2) | — |
| Presión del grip /10 por fase | Texto en `NOT_FROM_TV` («3 de 10») | No-TV / Texto | — |
| Espera: base 50-60 cm entre tobillos | Sí: `ready.base_width` (%) | Sí | Darla también en m (`base_court_m` en la espera) |
| Espera: rodillas 140-150° | Parcial: `ready.hip_height` (la rodilla tiene escorzo) | Sí, relativa | — |
| Espera: tronco inclinado 10-15° hacia delante | No | No-TV de frente; Vista lateral posible | Medida de inclinación en la espera desde la vista lateral |
| Espera: manos entre cintura y pecho, cabeza de la raqueta por encima | Medido por fase (`wrist_dom_height`, `racket_head_vs_wrist`), no en Cópiala | Sí | Punto de control «Altura de manos y raqueta en la espera» |
| Mirada al rival y luego a la bola | No (dicho) | No-TV | — |
| Giro de bloque: hombros 80-90°, cadera 45° | Parcial: `takeback/loaded.shoulder_turn`, `hip_turn`, `x_factor` (2D marcado «sesgo») | Sí, con su fiabilidad | — |
| Momento del giro: «antes de que cruce la red» | Medido (`stroke.takeback_vs_net`, en Patrón típico), pero Cópiala solo usa `takeback_vs_bounce` | Sí | Añadir `takeback_vs_net` como punto de control y como objetivo |
| Peso 60/40 en el giro, 70 % en el loop | Parcial: `com_over_feet`, `weight_loaded_to_non` | Sí | Frase de su reparto del peso al armar |
| Raqueta al pecho apuntando a la valla lateral (triángulo intacto) | Parcial: `hands_apart`, `racket_angle` | Sí | Punto de control «punta hacia la valla lateral al girar» |
| Duración del giro 0,3-0,5 s | Medido (`dur_preparation`, solo en el resumen) | Sí | Mostrarla en la fase 2 |
| Loop: la cabeza de la raqueta sobre su cabeza | Sí: `loaded.racket_tip_vs_head` | — | — |
| Loop: punta arriba (12 h-1 h) frente a codo alto y raqueta colgada | Parcial: `racket_tip_vs_head` + `elbow_dom_vs_shoulder` + `takeback_face` (pat the dog); `tip_points_to` no existe (petición 100) | Sí | Clase «tendencia del armado: punta arriba / codo alto» con `racket_angle` |
| Loop: mano a la altura del hombro | Medido (`loaded.wrist_dom_vs_shoulder`, en COACH), no en Cópiala | Sí | Punto de control y objetivo |
| Loop: codo 110-120° y separado | Parcial: `elbow_dom_lateral` sí; el ángulo `loaded.elbow_dom` no está en Cópiala | Sí | Punto de control «codo en el armado» |
| Brazo libre estirado delante, paralelo a la línea de fondo | Sí: `loaded.elbow_non`, `shoulder_abd_non` | — | — |
| Cabeza quieta en el loop | Parcial: curva de la cabeza (Golpe); `head_motion_cm` solo ±50 ms del impacto | Sí | Movimiento de la cabeza del armado al impacto |
| Sin pausa arriba | Medido (`stroke.pause_at_loaded`), no en Cópiala; el COACH dice lo contrario | Sí | Punto de control «sin pausa arriba» y corregir el COACH |
| Tres formas de llevar la raqueta atrás: loop verdadero, loop falso, straight-back | Parcial: `class.takeback` = compacta / amplia / en bucle alto | Sí | Etiquetar «loop falso» (bucle + pausa) y «recto atrás» (mano sin subir) |
| Drop: el brazo entero baja, sin romper la muñeca | Parcial: `wrist_drop`, `racket_lag_deg`, `racket_forearm` | Sí | — |
| Drop: 15-25 cm por debajo de la bola | Solo Vista lateral (`racket_drop_below_contact_cm`) | No-TV | — |
| Drop: cara abierta o de lado que se cierra tarde | Parcial: `acceleration.face_tilt` (fiabilidad baja) | Sí, con aviso | — |
| La cadera arranca durante el drop | Parcial: `shoulders_open_first`, `t_max_hip_turn`, cadena | Sí | — |
| Swing: piernas → cadera → tronco → brazo | Sí: cadena (orden), `hip_rise` | — | — |
| El codo avanza primero, por delante de la cadera | No | No-TV (profundidad); Vista lateral posible | Medida de lado o 3D, marcada como estimación |
| El brazo libre se pliega en el swing | Parcial: `extension.wrist_non_lateral` (catch) | Sí | Mano libre en la aceleración y el impacto |
| La cara se cierra hasta vertical en el impacto | Parcial: `impact.face_tilt` estimado | Sí, como estimación | — |
| Contacto 50-70 cm delante de la cadera | Solo Vista lateral (`contact_in_front_pct`) | No-TV | — |
| Contacto a 75-90 cm lateral, brazo casi estirado | Sí: `impact.wrist_dom_lateral` (% y cm del usuario) | — | — |
| Altura del contacto entre cintura y pecho | Sí: `wrist_dom_vs_hip` y condición «Altura de la bola» | — | — |
| Codo 120-150° (doble flexión) | Sí: `impact.elbow_dom`, `class.arm` | — | — |
| Muñeca algo extendida en el impacto | Parcial: `racket_forearm` borroso | Sí, con aviso | — |
| Caderas de frente, hombros paralelos sin pasarse | Parcial: `impact.hip_turn` y `shoulder_turn` (2D, sesgo) | Sí, con su fiabilidad | — |
| Peso 70-80 % delante; pie delantero firme | Sí: `weight_shift`, `feet_move_m`; `front_foot_angle` marcado «sesgo» | — | — |
| Terminación hacia el objetivo y luego al hombro | Sí: `class.finish`, `extension.arm_extension` | — | — |
| Terminación alta: mano a la altura del hombro o más | Medido (`finish.wrist_dom_vs_shoulder`, en PRIMARY), no en Cópiala | Sí | Punto de control y regla «por debajo del pecho = swing plano» |
| Codo hacia la red y a la altura de la barbilla al terminar | No en Cópiala (descriptores de codo por fase) | Sí | Codo al terminar (petición 109: `finish.elbow_non`) |
| La mano libre recoge la raqueta al terminar | No | Sí (`hands_apart` al terminar) | Clase «recoge con la mano libre» |
| De frente a la red al terminar; el pie de atrás despega o pivota | Sí: `class.finish_trunk`, `back_heel_lift`, `rear_leg_step_after`, `kick_back` | — | — |
| Tabla de alturas de mano y cabeza de la raqueta por momento | Parcial: curvas de altura (Golpe, Patrón típico) | Sí | Tabla «sus alturas por fase» con medianas |
| Dónde se estira el brazo (codo por fase) | Parcial: gráfica de ángulos plegada (Golpe) | Sí | Línea del codo fase a fase en Cópiala |
| Punta hacia el lateral en el impacto; la cara se cierra justo después | Parcial: `racket_angle` y `face_tilt` en extensión y terminación | Sí, con aviso | — |
| Transición desde el straight-back | No | Texto | Progresión en texto si su «forma» difiere |
| Biomecánica: cadena cinética, separación, piernas y cadera (con fuentes) | Sí: COACH (Landlinger, Elliott, Nesbit, Iino ausente) | — | Añadir Iino y Kojima 2001 |
| Ciclo estiramiento-acortamiento (no pararse; split) | No; el COACH de pausa lo contradice | Texto | Corregir el COACH y añadir este principio |
| Carga del hombro (prevención) | No | Texto | Fuera de alcance salvo una línea |
| Apoyo neutro frente a abierto (Bahamonde y Knudson, Kawamoto) | Parcial: COACH «abierto 84 %» | Texto | Citar que la velocidad es parecida en los dos apoyos |
| Efecto: cara casi vertical y swing más inclinado | Sí: `swing_low_to_high`, `class.swing` | — | — |
| Tabla de punta y cuerdas por momento; dos alarmas | Parcial: «Raqueta por fase» (Golpe), clase `takeback_face` | Sí | Alarmas automáticas: cara al cielo en el armado; punta hacia la red tras el giro |
| Codo, muñeca y grip fase a fase | Parcial | Sí (codo) / No-TV (grip, muñeca) | — |
| Tipos de terminación (clásica, limpiaparabrisas, hacia adelante) | Sí: `class.finish` (falta «hacia adelante») | Sí | Nivel «hacia adelante» (extensión larga + terminación alta) |
| Apoyos con cm entre tobillos (80-90 / 70-85) | Sí: `base_court_m` en m y `class.stance_*` | — | — |
| Cargar, empujar, recibir, recuperar | Sí: `hip_drop_cm`, `hip_rise`, `weight_shift`, recuperación | — | — |
| Brazo libre: tabla por fase y errores | Parcial | Sí | Error «mano libre cruza al otro lado en el impacto» (`impact.wrist_non_lateral`) |
| Cabeza y mirada: tabla por momento | Parcial: `head_motion_cm`; mirada no medible | Sí / No-TV | «Levanta la cabeza tras el impacto»: curva de la cabeza +0-0,2 s |
| Proyección: tres bolas en línea, raqueta al objetivo 2-3 fotogramas después | Parcial: `arm_extension` | Sí, como estimación (`racket3d`) | — |
| Variaciones según la pelota (alta, baja, fuerte, abierta, corta, dejada) | Sí: condiciones y «Qué cambia» medido | — | Nivel «dejada o bola muy corta» si hay datos |

### 2 · Plan

| Elemento | ¿Lo tiene la app? | ¿Aplica? | Qué añadir |
|---|---|---|---|
| Sesiones A, B y C con duración | No | Texto / No-dec (hoja de sesión descartada) | Nada, salvo que el usuario lo pida |
| Semana según los días de pista; reglas de carga | No | Texto / No-dec | — |
| Material, raqueta lastrada | No | Texto | — |
| Calentamiento, complementario, vuelta a la calma, movilidad (sesión C) | No | Texto (fuera del golpe) | Baja prioridad |
| Drills con series × repeticiones | Sí: un ejercicio por punto de control (`cp.drill`) | — | — |
| «Comprueba:» de cada drill | No (hay «error típico» y «Tu objetivo») | Texto + su número | Línea «Cómo comprobarlo» por punto de control |
| Qué drills tocan cada semana | No | Texto | — |
| Progresión en 12 semanas, plazos realistas | Parcial: «Tu plan», 3 prioridades «cuando salga sola, la siguiente» | Texto | Etapas con criterio de paso, sin calendario |
| Paso a pista en 4 etapas | No | Texto | Una línea en «Tu plan» |
| Efecto en el resto del juego | No | No-otra | — |

### 3 · Diagnóstico

| Elemento | ¿Lo tiene la app? | ¿Aplica? | Qué añadir |
|---|---|---|---|
| Síntoma → qué revisar → drills | Parcial: `mistake` por punto de control | Texto | Índice «Si te pasa…» que lleve a los puntos de control y a sus vídeos |
| Por el resultado de la bola (corta, larga, red, sin control) | Parcial: Conclusiones «errores frente al resto» | Sí (en ella) | «Qué cambia en sus errores a la red o fuera» con las causas de la guía como hipótesis |
| Por lo que ves en el vídeo (loop falso, drop excesivo, contacto tarde, cabeza…) | Parcial: medidas sueltas | Sí | Alarmas por golpe en Golpe (`pause_at_loaded`, caída bajo la rodilla, cabeza) |
| Tests de progreso con vídeo propio | No | No-dec (sin clips del usuario) / Texto | Solo como texto de autocomprobación |
| Molestias y protocolos (codo, hombro, rodilla, sobreentrenamiento) | Mínimo: una línea en `NOT_FROM_TV` | Texto | Nota breve con fuente |

### 4 · Chuletas

| Elemento | ¿Lo tiene la app? | ¿Aplica? | Qué añadir |
|---|---|---|---|
| Las 7 fases en una línea | Parcial: `focus` y `when` de cada fase, resumen | Sí | Chuleta de una pantalla con sus 8 fases y un número cada una (también en el PDF) |
| Ritmo «gira, atrás, golpe» | Parcial: medidas sueltas (`takeback_vs_net`, `loaded_vs_bounce`, `contact_vs_top`) y «La bola y ella» por golpe | Sí | «Su ritmo con la bola» en una línea con sus medianas |
| Hoja de sesión | No | No-dec (petición 129) | — |
| Checklist antes de jugar (un solo foco) | Parcial: «Tu plan» de una en una y `focus` | Texto | — |
| Checklist táctico | No | Texto | — |
| «En el cambio de lado: gira antes» | No | Texto | — |

### 5 · Lectura y footwork

| Elemento | ¿Lo tiene la app? | ¿Aplica? | Qué añadir |
|---|---|---|---|
| Por qué anticipar | Parcial: COACH del split y de la reacción | Texto | — |
| Qué mirar del rival (posición, preparación, swing, cara) | No | No-TV (su mirada) | Su resultado: `takeback_after_opp` y `first_step_right_way` ya existen |
| Patrones y saque del rival, zurdos, en la red, estado del rival | No | No-otra (análisis del rival) | — |
| Drills de lectura (vídeo con predicción, palabra en el impacto…) | No | Texto | — |
| Split: cuándo (aterriza en el golpe del rival) | Sí: `split_landing_vs_opp_s`, `takeoff` | — | — |
| Split: 5-15 cm, sobre la parte delantera del pie | No (altura no medible, dicho) | No-TV | — |
| Split: variantes (cae abierto hacia el lado, avanzando) | Parcial: velocidad antes y después del split, dirección del primer paso | Sí | Dirección del aterrizaje y primer paso según el lado de la bola |
| Tipos de paso | Sí: `step_kinds`, `approach_pattern`, `crossover_steps` | — | — |
| Combinación base (cruzado largo + 1-2 cortos) | Sí: `approach_main`, `adjustment_steps` | — | — |
| Según la bola: primer paso y apoyo | Parcial: condiciones × apoyo | Sí | Tabla con sus datos: «según cuánto corre, su primer paso y su apoyo» |
| Recuperación al centro de los ángulos, desplazado hacia su golpe | Parcial: `off_centre_at_opp_hit_m`, `recovery_*` | Sí | Destino de la recuperación según la dirección de su golpe |
| Superficie (posición de espera, deslizar) | Sí: `surface`, «deslizando» | — | Profundidad de su espera en el peloteo por superficie |
| Drills F1-F6 y cuándo meterlos | Parcial: ejercicios de la tarjeta «Pies» | — | — |

### 6 · Táctica y resto

| Elemento | ¿Lo tiene la app? | ¿Aplica? | Qué añadir |
|---|---|---|---|
| Las 4 direcciones, su riesgo y cuándo empezar | Sí: `shot_type` (condición «Dirección») y mapa «Destino» | — | — |
| Proporción de 3-4 cruzados por cada cambio | No | Sí (sus golpes seguidos en el punto) | Secuencias de dirección dentro del punto |
| Cuándo cambiar de dirección (bola cómoda, rival fuera de sitio) | No | Parcial (`intent`, `ball_speed` × `shot_type`) | «Cambia de dirección sobre todo con…» |
| Profundidad (últimos 1-2 m) | Sí: `shot_depth_m`, botes | — | % de botes en los últimos 2 m como frase |
| Altura sobre la red | No | No-TV (dicho) | — |
| Patrones de puntos (cruzado-cruzado-paralelo, saque + 1, aproximación…) | Parcial: `around_ball`, `approach`, `play` | Sí, en parte | Patrones de 2-3 golpes si hay golpes seguidos |
| «Cómo jugaba Ivanovic» | No | No-otra; su equivalente sí | «Cómo usa su derecha» (invertidas, subidas, desde dónde ataca) |
| Condiciones: superficie / viento y sol | Superficie sí / viento no | Sí / No-TV | — |
| Errores de decisión | No | Juicio, no se mide | — |
| Drills de dirección D1-D4 | Parcial: ejercicios de condición | Texto | — |
| Resto: preparación corta, apoyo, contacto, split | Sí: `returns.py`, condiciones, `return_ready_depth_m`, `return_step_in_m` | — | — |
| Tres restos (bloqueo, agresivo, cortado) | Sí (18-10): `class.return_type` (bloqueo, armado corto, swing completo, cortado), condición «Tipo de resto» | Sí | — |
| Dónde colocarse; 1.er y 2.º saque; según tipo y dirección del saque | Sí: `serve_number`, `serve_dir`, `return_side` | — | — |
| Drills y errores del resto | Parcial | Texto | — |

### 7 · Mente

| Elemento | ¿Lo tiene la app? | ¿Aplica? | Qué añadir |
|---|---|---|---|
| Respiración (soltar el aire en el impacto) | No | No-TV (posible indicio de audio, sin validar) | — |
| Rutina entre puntos (25 s ITF) | No | Medible en parte (marcador + audio) | Tiempo entre puntos y bajo presión (fuera de la derecha, baja prioridad) |
| Foco externo | Sí: `focus` por fase (Wulf, `learn.py`) | — | Citar a Wulf en la web |
| Lenguaje interno, visualización, confianza (Bandura), flow, diario | No | Texto | Fuera de alcance o una nota |
| Puntos importantes con más margen (altura y centro) | Parcial: Conclusiones compara técnica bajo presión, no táctica | Sí | Dirección y profundidad bajo presión |
| Cuando te atenazas | Parcial: comparación bajo presión | Sí (resultado) | — |
| Rachas buenas y malas | No | Sí (marcador: tras error o tras punto ganado) | Comparación posible |
| Partidos largos y cansancio | Sí: «Primer tercio / último tercio» | — | — |
| Rival y entorno | No | No-TV | — |

### 8 · Equipamiento

| Elemento | ¿Lo tiene la app? | ¿Aplica? | Qué añadir |
|---|---|---|---|
| Raquetas del alumno (Gravity, Speed) | No | No-otra | — |
| Cordaje, tensión, cuándo encordar, plomo | Dicho «no medible» (`NOT_MEASURABLE`, `NOT_FROM_TV`) | No-TV / Texto | — |

### 9 · Referencia visual

| Elemento | ¿Lo tiene la app? | ¿Aplica? | Qué añadir |
|---|---|---|---|
| Cómo mirar vídeos (una cosa cada vez, cámara lenta) | Sí: capas, 0,25×, fases, `PHASE_FOCUS` «Qué mirar» | — | — |
| Compararte desde el mismo ángulo | Sí entre sus golpes (Comparar); con el usuario no | No-dec | — |
| Qué observar y pregunta para tu vídeo | Parcial: «Qué mirar» | Texto | «Pregunta para tu vídeo» por fase |
| Análisis publicados con fuentes | No (`aprendido_entrenadores.md` es examen interno) | No-dec (requisito 6) | — |
| Vídeos de entrenamiento a cámara lenta | Sí: Vista lateral (entreno), su excepción | — | — |
| Tres cosas que más rinden | Parcial: «Su firma» | Sí | «Lo que la distingue» (mejora 12, pendiente) |
| Copia a un solo modelo | Implícito | — | — |

### 10 · Timing, distancia y peso

| Elemento | ¿Lo tiene la app? | ¿Aplica? | Qué añadir |
|---|---|---|---|
| 4 objetivos (pico, distancia, peso, de lado) | Parcial: medidas sueltas | Sí | Panel «Timing, distancia y peso» con sus cuatro números |
| Coger la bola en el pico | Sí: `class.ball_phase`; `contact_vs_top` (s) no está en Cópiala | Sí | Punto de control en segundos respecto al pico |
| Referencias LTA y Mouratoglou | No | Texto | Fuentes en COACH |
| Llegar pronto y ajustar al final | Sí: `adjustment_steps` | — | — |
| Retroceder antes del golpe; no golpear retrocediendo | Parcial: `move_direction`, `speed_at_impact_mps` | Sí | Punto de control «se mueve hacia atrás en el impacto» |
| «De frente» depende de los hombros | Parcial: `shoulders_open_first` | Sí | — |
| Apoyo cerrado con cuidado | Sí: condición «Apoyo» | — | — |
| Ritmo: tabla momento de la bola → qué haces | Sí por golpe («La bola y ella») | — | Versión «típica» en Cópiala |
| Dónde se puede esperar (giro sí, arriba no) | No | Sí | Situar la pausa: en el giro o en el punto alto |
| Loop lento-rápido; la subida regula | Parcial: `tempo_ratio`, `dur_*` | Sí | Frase de ritmo de subida frente a velocidad de la bola |
| Colocarse mientras prepara; correr girado y loop en los 2-3 últimos pasos | Parcial: `takeback_vs_first_step` | Sí | Inicio del loop respecto a los últimos pasos |
| Último apoyo firme cerca del bote | No | Sí | Último apoyo respecto al bote |
| Por qué te caes hacia atrás (5 causas) | Parcial: `finish.head_over_base`, `weight_shift` | Sí | Diagnóstico con sus medidas |
| Drills T1-T5 y P1-P9 | Parcial: ejercicios «di bote» | Texto | — |
| Ayudas vocales (metaanálisis) | Parcial: ejercicios con palabras | Texto | Cita y las tres reglas de uso |

### 11 · Glosario

| Elemento | ¿Lo tiene la app? | ¿Aplica? | Qué añadir |
|---|---|---|---|
| 26 términos | Sí: `learn.GLOSSARY` (42 términos) | — | Faltan: bucle (loop), loop falso, recto atrás (straight-back), giro de bloque (unit turn), doble flexión, pico del bote, paso cruzado, ciclo estiramiento-acortamiento, pat the dog, gira-atrás-golpe, sombras (shadow swing), dentro-fuera y dentro-dentro, bisel y tipos de empuñadura (con «no medible») |

## 3. Huecos que sí aplican, por prioridad

| # | Hueco | Esfuerzo | Dónde iría |
|---|---|---|---|
| 1 | Corregir `COACH["stroke.pause_at_loaded"]`: sin pausa entre armado y swing (estiramiento-acortamiento, Elliott 2006) | S | `explain.py` |
| 2 | Llevar a Cópiala las medidas que ya existen y son clave en la guía: `takeback_vs_net`, `pause_at_loaded` («sin pausa arriba»), `loaded.wrist_dom_vs_shoulder`, `loaded.elbow_dom`, `finish.wrist_dom_vs_shoulder` (terminación alta), `contact_vs_top`, `dur_preparation`. Cada una con objetivo (`TARGETS`) y consigna | S | `learn.PHASES`, fases 2, 3, 5 y 7 |
| 3 | Clase de forma del armado como la de la guía: bucle verdadero, loop falso, recto atrás, y la tendencia «punta arriba / codo alto» | S-M | `technique.py` (clases), Cópiala fase 2-3, Golpe |
| 4 | «Su ritmo con la bola» y panel «Timing, distancia y peso»: giro al cruzar la red → armado en el bote → contacto en el pico, más distancia, peso y hombros, con sus medianas | S | Cópiala (tras «Su firma») y PDF |
| 5 | Índice «Si te pasa…» (síntoma → causa → punto de control → su vídeo), texto con fuente | M | Cópiala, sección nueva junto a «Tu plan» |
| 6 | Alarmas automáticas por golpe: cara al cielo en el armado, punta hacia la red tras el giro, pausa arriba, caída bajo la rodilla, cabeza que sube, se mueve hacia atrás en el impacto | M | Golpe («Medidas que faltan» y «Dudas») |
| 7 | «Cómo comprobarlo» en cada punto de control (el «Comprueba:» de la guía, con su número) | S-M | `learn.cp` + plantilla |
| 8 | Glosario: añadir los ~14 términos que faltan | S | `learn.GLOSSARY` |
| 9 | Terminación: nivel «hacia adelante», «la mano libre recoge la raqueta» y codo al terminar | S | `technique.py` clases, Cópiala fase 7 |
| 10 | Mano libre en la aceleración y el impacto (pliegue, que no cruce) | S | Cópiala fases 4-5 |
| 11 | Pies según la distancia que corre, con sus datos: primer paso, pasos y apoyo por situación | M | Cópiala «Pies» |
| 12 | Último apoyo y comienzo del bucle respecto al bote y a los últimos pasos (corre girada y hace el loop al final) | M | `technique` / `footwork`, Cópiala fase 3 |
| 13 | «Sus principios» (5-6 frases desde su firma) y «Lo que la distingue» (mejora 12) | M | Cópiala, arriba |
| 14 | Táctica medida: proporción de cambios de dirección, secuencias de 2-3 golpes, % de botes en los últimos 2 m, «Cómo usa su derecha» | M-L | Sus golpes → En la pista; Conclusiones |
| 15 | Bajo presión y en rachas: también dirección y profundidad, no solo técnica | M | Conclusiones (`c-group` «Táctica») |
| 16 | Resto: clase «bloqueo» — **hecho (18-10)**: `returns.return_type`, condición «Tipo de resto» | S | `returns.py` / clases, condición «Saque que resta» |
| 17 | Fuentes que faltan en COACH: Iino y Kojima 2001, Bahamonde y Knudson 2003, Kawamoto 2019, LTA, Wulf, metaanálisis de autoinstrucciones | S | `explain.COACH`, `learn.py` |
| 18 | Medidas de lado (Vista lateral): codo por delante de la cadera, inclinación del tronco en la espera | M | `practice.side_metrics`, Vista lateral y Cópiala |
| 19 | Progresión por etapas sin calendario (criterio de paso) y paso a pista. Antes, confirmar con el usuario: descartó la hoja de sesión | S | «Tu plan» |
| 20 | Tiempo entre puntos (rutina) bajo presión: fuera del golpe | M | Conclusiones (opcional) |

**Lo que no aplica.** Material del alumno, análisis del rival (patrones, saque, zurdos), mirada, grip y su presión, altura del split y sobre la red, viento y sol, enlaces a vídeos y análisis externos (requisito 6), tests con el vídeo del usuario (sin clips propios) y hoja de sesión (descartada). Plan semanal, preparación física, mente y molestias: como mucho, notas breves con fuente.

Ficheros que habría que tocar:
- `src/tennisbio/learn.py`
- `src/tennisbio/explain.py`
- `src/tennisbio/technique.py`
- `src/tennisbio/report_template.html`
- `docs/matriz_cobertura.md`
