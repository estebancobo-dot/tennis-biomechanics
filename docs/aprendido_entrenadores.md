# Lo aprendido de los entrenadores (vídeos de YouTube sobre la derecha)

**Uso:** solo para aprender cómo analizan y explican los entrenadores. **Nada de esto es dato de la
jugadora ni puede aparecer en el informe** (requisito 6). Las afirmaciones sobre Rybakina sirven como
"examen" interno: cosas que nuestras medidas deberían poder confirmar o refutar con sus golpes.

**Material:** `indice.json` lista 24 vídeos; 16 tienen transcripción (`dicho.txt`). Sin subtítulos
(solo cámara lenta o vídeos sin voz): A89PHT3_yI0, XEshCsHrvcc, W0uSDf3AaY8, lOHM3WXWSgc, ujbqEz-JtZA
(Rybakina en cámara lenta), Ge9rRL6LMdM, ULIxMsGg-c4, wGqD-ui0skU. No se descargó ningún fotograma
(todos dan `Requested format is not available`), así que lo que los entrenadores *dibujan* en pantalla
solo se conoce por lo que dicen ("if I draw a line…").

**Ruido de las transcripciones:** subtítulos automáticos. Nombres destrozados ("Ryakina", "Bukov",
"Jovovich", "SA"/"Yanik" = Sinner, "Curios" = Kyrgios, "Arabic position" = *attacking position*,
"Palmas longus"); en los vídeos traducidos (عالم الرياضيون) hay frases sin sentido ("P I'll be tennis
mental"). **Dos vídeos de Rybakina parecen narraciones genéricas con voz sintética y música**
(NjhkWWT3nSM, g9T7zSq_iBE): las frases son plausibles pero no se apoyan en imágenes concretas; la cita de
Vukov ("brush up, not through") es una dramatización. Se marcan con credibilidad baja. JJG
(YQDx7xiZCSE) anuncia al principio "una diferencia clave… que se rompe en momentos importantes" y la
transcripción **nunca dice cuál es** (probablemente estaba en un rótulo o en un tramo sin subtítulos).

Claves = las de `technique.py`, `footwork.py`, `explain.py` (formato `fase.descriptor`, `stroke.*`,
`class.*`, `footwork.*`).

---

## 1. Lo que dicen de la derecha de Rybakina (el examen)

Credibilidad: **A** = análisis sobre imágenes de partido o entrenamiento (JJG, Meike Babel);
**C** = narración genérica (NjhkWWT3nSM, g9T7zSq_iBE). "Medible" se refiere a la cámara de TV
de detrás del fondo.

| # | Afirmación (vídeo · tiempo · cita breve) | Cred. | ¿Medible desde la tele? Clave existente | Cómo se decide |
|---|---|---|---|---|
| R1 | Derecha basada en "simplicity, timing, and clean ball striking. Not heavy spin" y "very linear swing path" (YQDx7xiZCSE · 0:27-0:38) | A | ◐ El efecto no (✘✘). La trayectoria sí: `stroke.swing_low_to_high`, `class.swing`, `stroke.takeback_path` | Confirma si `class.swing` sale "liftado" con ángulo moderado (no extremo) y la preparación es "compacta"; "lineal" no tiene medida (ver mejora 2) |
| R2 | En la espera y al caer del split step tiene "both hands on the grip" (YQDx7xiZCSE · 1:00-1:10; también en el revés js3SPxF5eV0 · 1:20) | A | ✔ `ready.hands_apart`, `class.ready_hands` | Confirma si "dos manos en la raqueta" ≥ 80 % |
| R3 | Empuñadura semioccidental, puede liftar y también pegar plano (YQDx7xiZCSE · 1:25-1:36) | A | ◐ Solo "compatible con": `explain.grip_compatible` (bisel ✘✘) | Confirma si sale "compatible con semioccidental u occidental"; la variedad plano/liftado: dispersión de `stroke.swing_low_to_high` por situación |
| R4 | Giro unitario temprano: "side on before the ball lands on her side" (YQDx7xiZCSE · 1:38-1:56; g9T7zSq_iBE · 2:48) | A | ✔ `stroke.takeback_vs_bounce`, `stroke.takeback_vs_net`, `takeback.hands_apart`, `ball_bounce.*` (giro de hombros cuando bota) | Confirma si la preparación empieza antes del bote (mediana < 0) y los hombros ya están girados al botar |
| R5 | Brazo "very relaxed" → potencia sin esfuerzo (YQDx7xiZCSE · 2:02-2:08) | A | ✘✘ (tensión muscular). Indirecto: `stroke.pause_at_loaded`, `acceleration.racket_forearm` | No decidible |
| R6 | En el armado, brazo izquierdo extendido "with a slight bend", hacia su derecha; sirve de "gauge" de la distancia a la bola (YQDx7xiZCSE · 2:11-3:18; g9T7zSq_iBE · 1:02, 2:10) | A | ✔ `loaded.elbow_non`, `loaded.shoulder_abd_non`, `loaded.wrist_non_lateral`; distancia: `impact.wrist_dom_lateral` | Confirma si `elbow_non` 130-170° y el brazo libre señala la bola; "gauge": correlación baja de `wrist_dom_lateral` entre situaciones (distancia constante) |
| R7 | La mano libre cruza la línea media en el giro ("offhand comes past your midline") (jTsLtU4vRSg · 2:38-2:45, como consejo general apoyado en ella) | A | ◐ Dato existe (`loaded.wrist_non_lateral`, `takeback.wrist_non_lateral`), sin frase | Confirma si la mano libre pasa al lado de su brazo (lateral > 0) al final del armado |
| R8 | Raqueta arriba en el armado: "the tip of the racket is above her head", codo de atrás alto, muñeca algo por encima del codo (YQDx7xiZCSE · 3:20-3:59; revés igual "slightly above head height" js3SPxF5eV0 · 1:56-2:07) | A | ◐ `loaded.racket_tip_height` y `loaded.body_height` existen (la resta no); `loaded.racket_head_vs_wrist`, `stroke.takeback_peak_vs_shoulder`; altura del codo ✘ medible (falta clave) | Confirma si punta > cabeza en el armado en la mayoría; codo: añadir `loaded.elbow_vs_shoulder` (mejora 3) |
| R9 | Cuando la bola ya ha botado y sube, empieza la caída de la raqueta y carga la pierna de atrás (YQDx7xiZCSE · 4:12-4:35) | A | ✔ `stroke.loaded_vs_bounce`, `stroke.loaded_vs_top`, `loaded.com_over_feet`, `footwork.weight_loaded_to_non` | Confirma si el armado termina entre el bote y lo más alto, con el peso en el pie de atrás |
| R10 | "Anytime her opponent's ball bounces, her racket is about in the highest and furthest part of her take back" (jTsLtU4vRSg · 0:32-0:47) | A | ✔ `stroke.loaded_vs_bounce` | **El mejor ítem del examen:** confirma si la mediana está a ±0,1 s del bote; refuta si arma claramente después |
| R11 | Con bolas más duras y profundas sigue llegando a tiempo gracias a la preparación temprana (jTsLtU4vRSg · 1:00-1:10) | A | ✔ variante "bola rápida" del modelo: `stroke.loaded_vs_bounce`, `stroke.takeback_after_opp` | Confirma si `loaded_vs_bounce` no se retrasa más que el ruido con bola rápida |
| R12 | En bolas altas y pesadas se va atrás, se coloca detrás de la bola y carga la pierna exterior (jTsLtU4vRSg · 1:43-1:55) | A | ✔ situación `depth` × `ball_height`, `class.move_direction` ("atrás"), `footwork.weight_loaded_to_non` | Confirma si con contacto alto aumenta la proporción de golpes desde 1-2 m detrás y movimiento hacia atrás |
| R13 | La raqueta cae por debajo de una línea (por debajo de la bola) para liftar (YQDx7xiZCSE · 4:36-4:55; revés: punta por debajo de la cadera js3SPxF5eV0 · 3:58-4:06) | A | ✔ `acceleration.racket_head_vs_wrist`, `stroke.wrist_drop` (fiab. baja en la cabeza de la raqueta); comparación con la bola ✘ (falta clave, mejora 9) | Confirma si la cabeza cae por debajo de la mano antes de acelerar en la mayoría |
| R14 | Cadera de perfil → mirando a la pista en el contacto (YQDx7xiZCSE · 4:56-5:18) | A | ◐ `loaded.hip_turn` vs `impact.hip_turn` (2D) | Confirma si la cadera gira claramente entre armado e impacto (diferencia > ruido) |
| R15 | Contacto con el codo flexionado, como Sinner/Djokovic, "still… out in front" (YQDx7xiZCSE · 5:30-5:50) | A | ✔ `impact.elbow_dom`, `class.arm`; "delante" ✘ (profundidad) | Confirma si `class.arm` = "doble flexión" mayoritaria (codo < 135°); lo de "delante" no se puede comprobar |
| R16 | En el contacto "the strings are almost facing down" (YQDx7xiZCSE · 6:13-6:27) | A | ◐ cara en el impacto solo interpolada (`strings`, fiab. 1) | **No decidible** y probablemente falso tal como se dice (la literatura da cara casi vertical, pocos grados cerrada); útil como prueba de honestidad: la app no debe "confirmarlo" |
| R17 | Terminación alrededor del hombro, sin frenar ("all the way through without slowing it down") (YQDx7xiZCSE · 6:37-7:01) | A | ✔ `class.finish`, `finish.wrist_dom_vs_shoulder`, `stroke.t_finish`, `extension.arm_extension` | Confirma si "sobre el hombro" es la terminación más frecuente |
| R18 | Compacta y eficiente, "really quick unit turn" (YQDx7xiZCSE · 7:05-7:16) | A | ✔ `class.takeback`, `stroke.takeback_path`, `stroke.dur_preparation` | Confirma si "compacta" domina o la duración de la preparación es corta frente a su ritmo |
| R19 | En la caída: tapón del mango apuntando a la bola, punta hacia el fondo, cuerdas algo hacia el suelo (YQDx7xiZCSE · 7:29-7:48) | A | ◐ `acceleration.racket_angle`, `face_points_to` en aceleración (fiab. 1, desenfoque); dirección en 3D: `racket3d` sin clave | Parcial; con `racket3d` se podría decir "raqueta apuntando hacia el fondo" (mejora 2) |
| R20 | "She likes to play a lot of closed stance forehands" para pegar delante, y la pierna de atrás pasa adelante tras el impacto (YQDx7xiZCSE · 8:03-8:38) | A | ✔ `class.stance_impact`, `class.stance_role`, `footwork.rear_leg_step_after`, `com_over_feet` (armado → impacto) | **Ítem fuerte:** el circuito usa apoyo abierto en ~84 % (IJSSC 2025). Confirma si su proporción de cerrado/neutro es claramente mayor, sobre todo en bola corta o de ataque; refuta si es abierto como el resto |
| R21 | Peso de la pierna de atrás a la de delante (YQDx7xiZCSE · 7:57-8:03; jTsLtU4vRSg · 2:00-2:09) | A | ◐ `loaded.com_over_feet` e `impact.com_over_feet` existen; la transferencia (diferencia) no tiene frase | Confirma si `com_over_feet` pasa de < 0,4 a > 0,6 |
| R22 | "Algo se rompe en momentos importantes" (YQDx7xiZCSE · 0:00-0:20, sin explicar) | A | ✔ variante de presión (OCR del marcador) en el modelo | Lo que cambie bajo presión por encima del ruido; si nada cambia, se dice así |
| R23 | Coordinación de la cadena: piernas → cadera → tronco → brazo; los hombros siguen a la cadera y la separación almacena energía (g9T7zSq_iBE · 5:57-6:07, 10:29-10:37, 11:43-11:50) | C | ✔ `chain` (solo el orden), `loaded.x_factor`, `stroke.t_max_hip_turn` vs `t_max_shoulder_turn` | Confirma si el orden correcto aparece en la mayoría; los ms no |
| R24 | Practica "brush up, not through" con Vukov (NjhkWWT3nSM · 0:06-0:10) | C | ◐ `stroke.swing_low_to_high`, `stroke.swing_rise_after` | Contradice R1 ("hit through"); dejar como ruido |
| R25 | Revés (solo contexto): manos juntas, preparación alta "very similar to her forehand", carga la pierna de atrás antes de la caída, cabeza quieta (js3SPxF5eV0 · 0:43, 1:13, 3:07, 5:19) | A | Para el revés (después). `stroke.head_motion_cm` ya existe | Cuando se analice el revés |

Resumen del examen: de 25 afirmaciones, **13 se pueden decidir ya** con claves existentes
(R2, R4, R6, R9, R10, R11, R12, R13, R15-codo, R17, R18, R20, R22), **8 se deciden parcialmente o
necesitan una clave nueva barata** (R1, R3, R7, R8, R14, R19, R21, R23) y **4 no son decidibles**
desde la tele (R5, R16, "contacto delante" de R15, R24). Los ítems más discriminantes son R10
(armado completo al botar), R20 (apoyo cerrado frente al 84 % de abierto del circuito), R8 (punta por
encima de la cabeza) y R15 (doble flexión).

---

## 2. Lista de comprobación del entrenador (por fase)

Estado: ✔ medido y explicado · ◐ parcial (dato sin frase, o aproximado) · ✘ falta pero es medible
desde la tele · ✘✘ no observable desde la tele.

### Espera y split step
| Punto que miran | Quién lo dice | Estado | Clave / qué añadir |
|---|---|---|---|
| Caer del split cuando golpea la rival | SZ1Y8z-c9Qk 2:31; YQDx7xiZCSE 1:00 | ✔ | `footwork.split_landing_vs_opp_s` |
| Dos manos en la raqueta en la espera | YQDx7xiZCSE 1:02; js3SPxF5eV0 1:20 | ✔ | `class.ready_hands` |
| Empuñadura de espera / cambio de empuñadura | YQDx7xiZCSE 1:12-1:22 | ✘✘ | mano de 20-40 px |
| Empezar a moverse cuando la bola sale de la raqueta rival, no al botar | SZ1Y8z-c9Qk 1:25-1:50 | ✔ | `stroke.takeback_after_opp`, `footwork.first_step_s` |
| Posición en pista para atacar (sobre la línea de fondo, no 2-3 m detrás) | SZ1Y8z-c9Qk 0:50-1:00; AWgTZBADqoo 4:24 | ✔ | situación `depth` |

### Desplazamiento y primer paso
| Punto | Quién | Estado | Clave / qué añadir |
|---|---|---|---|
| Girar mientras corre (no correr y girar al final) | SZ1Y8z-c9Qk 2:47-3:12; _m5Lmb84i6g 0:50 | ◐ | `stroke.takeback_after_opp` y `footwork.first_step_s` existen por separado; añadir `takeback_vs_first_step` (s) y frase "gira mientras corre" |
| Desplazarse bajo ("stay down when you move") | SZ1Y8z-c9Qk 1:19 | ◐ | curva `hip` en `technique.stroke_curves`; añadir `approach.hip_height` (media durante el desplazamiento) |
| Colocarse detrás de la bola; distancia correcta | jTsLtU4vRSg 1:43; g9T7zSq_iBE 1:09-1:25 | ✔ | `impact.wrist_dom_lateral`, `footwork.adjustment_steps` |

### Preparación (giro unitario)
| Punto | Quién | Estado | Clave / qué añadir |
|---|---|---|---|
| Giro de hombros primero, temprano, antes del bote | YQDx7xiZCSE 1:38; js3SPxF5eV0 1:29; _m5Lmb84i6g 0:50 | ✔ | `stroke.takeback_vs_bounce`, `takeback.shoulder_turn`, `takeback.hands_apart` |
| Mano libre en la garganta llevando la raqueta atrás | _m5Lmb84i6g 1:01 | ✔ | `takeback.hands_apart` |
| Mano libre más allá de la línea media | jTsLtU4vRSg 2:38 | ◐ | `wrist_non_lateral` existe sin frase ni COACH |
| Tamaño del armado: compacto vs amplio; altura máxima de la mano | Un4Bpskjimc 7:36-8:03; AWgTZBADqoo 2:43-3:30 | ✔ | `class.takeback`, `stroke.takeback_path`, `stroke.takeback_peak_vs_shoulder` |

### Armado ("set / power position")
| Punto | Quién | Estado | Clave / qué añadir |
|---|---|---|---|
| Armado completo cuando bota la bola | jTsLtU4vRSg 0:32; _m5Lmb84i6g 0:52 | ✔ | `stroke.loaded_vs_bounce` |
| Hombros perpendiculares a la línea de fondo; hombro izquierdo "mira" la bola; barbilla junto al hombro | _m5Lmb84i6g 1:09-1:20; jTsLtU4vRSg 2:54 | ◐ | `loaded.shoulder_turn` (2D) |
| Brazo libre extendido, paralelo a la línea de fondo | YQDx7xiZCSE 2:11; _m5Lmb84i6g 1:29 | ✔ | `loaded.elbow_non`, `loaded.shoulder_abd_non` |
| Punta de la raqueta por encima de la cabeza / a la altura del hombro (Sinner) / muy alta (Del Potro) | YQDx7xiZCSE 3:20; AWgTZBADqoo 2:43-3:12 | ◐ | `racket_tip_height` y `body_height` existen; añadir `loaded.tip_vs_head` (= diferencia) y frase |
| Raqueta vertical (Djokovic) u horizontal con la punta hacia la valla lateral (Sinner) | AWgTZBADqoo 0:55-1:30 | ◐ | `loaded.racket_angle` existe sin frase; dirección 3D en `racket3d` |
| Punta hacia la valla lateral, no hacia el fondo ("late hitting concept") | Un4Bpskjimc 3:08-3:52 | ✘ | añadir `loaded.tip_points_to` (lateral / fondo / cielo) desde `racket3d` o desde el escorzo de la raqueta (punta hacia la cámara = raqueta corta en imagen) |
| Codo de atrás alto (ATP, "throwing") vs bajo y pegado a la cadera (WTA) | YQDx7xiZCSE 3:39; WZ-AJ1QDP0U 2:02-3:15, 5:12 | ✘ | añadir `loaded.elbow_vs_shoulder` (vertical, % altura) y `loaded.elbow_lateral` (respecto a la cadera); medible bien desde detrás |
| Romper el plano: la raqueta pasa detrás de la espalda (WTA) o se queda a su lado (ATP) | WZ-AJ1QDP0U 0:17; xiglYZXz9L8 0:20-0:50; 1pRz1QqEKsM 0:23, 6:06 | ✘ | **la cámara de detrás es ideal**: punta de la raqueta respecto a la línea vertical del hombro dominante en el marco del cuerpo; añadir `loaded.tip_lateral` y clase `takeback_plane` ("al lado del cuerpo" / "detrás de la espalda") |
| Cara de la raqueta al final del armado (cerrada, "pat the dog"; ATP cierra por fuera) | 1pRz1QqEKsM 3:36; AWgTZBADqoo 1:30 | ✔ | `loaded.face_tilt`, `class.takeback_face`, `strings` |
| Carga en la pierna de atrás / exterior | YQDx7xiZCSE 4:21; _m5Lmb84i6g 1:46; js3SPxF5eV0 3:07 | ✔ | `loaded.com_over_feet`, `footwork.weight_loaded_to_non`, `loaded.hip_height` |
| Pausa / sincronía con la bola | Un4Bpskjimc 3:56 ("until a very last second") | ✔ | `stroke.pause_at_loaded`, `stroke.loaded_vs_top` |

### Caída y aceleración
| Punto | Quién | Estado | Clave / qué añadir |
|---|---|---|---|
| Caída de la raqueta por debajo de la bola / de la cadera | YQDx7xiZCSE 4:36; js3SPxF5eV0 3:58 | ◐ | `acceleration.racket_head_vs_wrist`, `stroke.wrist_drop`; falta comparar la punta más baja con la altura del contacto (`acceleration.tip_below_contact`) |
| Empezar la caída cuando la bola sube tras el bote | YQDx7xiZCSE 4:12 | ◐ | derivable de `t_acceleration` y el bote; añadir `stroke.acceleration_vs_bounce` |
| Retraso (lag), "whip", tapón del mango hacia la bola, punta hacia el fondo | _m5Lmb84i6g 2:03-2:31; Un4Bpskjimc 4:04-4:30; AWgTZBADqoo 1:30-1:52 | ◐ | `acceleration.racket_forearm` (proyectado, fiab. media-baja) |
| "Flip" de la raqueta (de punta lateral a detrás) al iniciar el swing | Un4Bpskjimc 4:04-4:25; AWgTZBADqoo 1:35 | ✘ | cambio de `racket_angle`/dirección 3D entre armado y aceleración (desenfoque parcial: fiab. baja) |
| Cadena cinética: piernas → cadera → tronco → brazo; "pull out of the slot", no empujar con el brazo | g9T7zSq_iBE 4:00, 5:57; WZ-AJ1QDP0U 3:20 | ✔ | `chain` (orden) |
| Separación cadera–hombros | g9T7zSq_iBE 10:29; jTsLtU4vRSg 2:26 | ◐ | `loaded.x_factor` (2D) |
| Impulso de piernas "sit down and up" | Un4Bpskjimc 12:15; AWgTZBADqoo 3:57; -VnCO7JgFHI 6:40 | ◐ | curvas de cadera; añadir `stroke.hip_rise` (subida de la cadera del punto más bajo al impacto, % altura) |
| Brazo relajado / mano blanda | YQDx7xiZCSE 2:02; Un4Bpskjimc 9:52 | ✘✘ | |
| Pronación tras el contacto, rotación interna, músculos | -VnCO7JgFHI 5:10; oLFfMNPy1tI | ✘✘ | |

### Impacto
| Punto | Quién | Estado | Clave / qué añadir |
|---|---|---|---|
| Altura: bola en lo más alto del bote, a la cintura | SZ1Y8z-c9Qk 4:16-4:41 | ✔ | `stroke.contact_vs_top`, `class.ball_phase`, `impact.wrist_dom_vs_hip` |
| Distancia lateral (≈1 m, "spacing") | SZ1Y8z-c9Qk 7:45; g9T7zSq_iBE 1:09 | ✔ | `impact.wrist_dom_lateral` |
| Contacto delante (30-40 cm; 45° hacia el poste) | _m5Lmb84i6g 2:52; SZ1Y8z-c9Qk 7:55 | ✘✘ | profundidad (posible estimación futura con `ball3d`/`racket3d`, no prioritaria) |
| Brazo recto vs doble flexión | YQDx7xiZCSE 5:30; -VnCO7JgFHI 3:20; 1pRz1QqEKsM 0:31 | ✔ | `impact.elbow_dom`, `class.arm` |
| Codo cerca del cuerpo (WTA) vs separado (ATP) | 1pRz1QqEKsM 6:23-6:43 | ✘ | añadir `impact.elbow_lateral` (codo respecto a la cadera/hombro, % altura) |
| Hombros de cara a la red en el contacto, y que dejen de girar justo antes ("no sobre-rotar") | _m5Lmb84i6g 2:33; Un4Bpskjimc 12:36-13:07 | ◐ | `impact.shoulder_turn`; añadir "frenado de hombros": velocidad de giro de hombros en el impacto / su pico (`stroke.shoulder_brake`) |
| Cabeza quieta | _m5Lmb84i6g 0:31, 3:16; js3SPxF5eV0 5:19 | ✔ | `stroke.head_motion_cm` |
| Trayectoria de abajo arriba **y hacia delante** | -VnCO7JgFHI 0:51-2:30; 5_lg1EVXKUg 1:52 | ✔ | `stroke.swing_low_to_high`, `class.swing` (el "hacia delante" es profundidad ✘✘) |
| Cara en el impacto (8°, 30°, "casi hacia abajo"…) | -VnCO7JgFHI 1:13; _m5Lmb84i6g 2:59; YQDx7xiZCSE 6:13 | ✘✘ | solo estimación interpolada; las cifras de los entrenadores ni siquiera coinciden entre sí |
| Equilibrio / pequeño salto | _m5Lmb84i6g 3:10 | ✔ | `impact.head_over_base`, `impact.trunk_tilt`, `class.movement` |
| Golpe tarde → bola junto al cuerpo, cara abierta | SZ1Y8z-c9Qk 2:02 | ◐ | `wrist_dom_lateral` bajo + `loaded_vs_bounce` tarde; falta la frase que lo relacione |

### Extensión, terminación y recuperación
| Punto | Quién | Estado | Clave / qué añadir |
|---|---|---|---|
| Atravesar la bola, extender, "keep the ball on the strings" | YQDx7xiZCSE 6:00; js3SPxF5eV0 5:01 | ✔ | `extension.arm_extension`, `stroke.swing_rise_after` |
| No frenar en la terminación | YQDx7xiZCSE 6:51 | ◐ | `stroke.t_finish`; sin medida de deceleración |
| Terminación sobre el hombro; hombro dominante bajo la barbilla | YQDx7xiZCSE 6:37; _m5Lmb84i6g 3:34 | ✔ | `class.finish`, `finish.wrist_dom_vs_shoulder` |
| Brazo libre doblado y siguiendo al hombro; codo libre alto ("show your bicep", revés) | _m5Lmb84i6g 2:37; js3SPxF5eV0 6:19 | ◐ | `finish.elbow_non` existe como descriptor, sin frase |
| Pierna de atrás pasa adelante; peso hacia delante | YQDx7xiZCSE 8:18-8:38; _m5Lmb84i6g 3:45 | ✔ | `footwork.rear_leg_step_after` |
| Base ancha al terminar (~0,5 m) para salir rápido | _m5Lmb84i6g 3:52 | ◐ | `impact.base_m`; falta en la terminación |
| Recuperación | (casi no la tratan) | ✔ | `footwork.recovery_*` |

### Ritmo, estilo y transversales
| Punto | Quién | Estado | Clave / qué añadir |
|---|---|---|---|
| Ritmo con la bola: armada al botar, caída al subir, contacto arriba | jTsLtU4vRSg 0:32; YQDx7xiZCSE 4:12; SZ1Y8z-c9Qk 4:16 | ✔ | `loaded_vs_bounce`, `loaded_vs_top`, `contact_vs_top`, `stroke.tempo_ratio` |
| Estilo ATP vs WTA (plano, codo, contacto, tamaño del armado) | WZ-AJ1QDP0U; xiglYZXz9L8; 1pRz1QqEKsM | ✘ | clase compuesta `fh_style` a partir de `tip_lateral`, `elbow_vs_shoulder`, `elbow_lateral`, `class.takeback`, `class.arm` (descriptiva, nunca "mejor/peor") |
| Armado ajustado a la velocidad de la bola (compacto con bolas rápidas) | Un4Bpskjimc 7:52-8:11; AWgTZBADqoo 4:41 | ✔ | variantes `ball_speed` × `class.takeback`/`takeback_path` |
| Golpe a golpe vs presión ("se rompe en momentos importantes") | YQDx7xiZCSE 0:15 | ✔ | variante de presión |
| Ganadores/errores por golpe | _m5Lmb84i6g 0:13 | ◐ | `point_won`, `shot_in` |
| Precisión → consistencia → potencia; riesgo de lesión | 5_lg1EVXKUg 6:03; AWgTZBADqoo 6:06 | ✘✘ | fuera de alcance |

---

## 3. Cómo lo explican y lo enseñan

### Estructura típica de un análisis
1. **Gancho** con lo que la distingue o un dato del partido: "one key difference in her technique"
   (YQDx7xiZCSE 0:00), "tres veces más ganadores de derecha que de revés" (_m5Lmb84i6g 0:13),
   "de 450 a 250 del mundo" (Un4Bpskjimc 0:00).
2. **Caracterización en una frase** antes del detalle: "built around simplicity, timing, and clean
   ball striking" (YQDx7xiZCSE 0:27); Mouratoglou enumera primero los 4 momentos a mirar (0:26).
3. **Recorrido por fases en orden**, cada una con la misma plantilla: *qué hace* → *por qué sirve*
   (mecanismo: "stores energy", "spacing", "gives time") → *qué copiar* ("this is the phase that you
   really want to try and get into", YQDx7xiZCSE 7:50).
4. **Contraste con el error típico de club**: "club players… decelerate through the follow-through"
   (YQDx7xiZCSE 6:51), "start moving when the ball bounces… too late" (SZ1Y8z-c9Qk 1:44).
5. **Advertencias**: lo que exige mucho timing (AWgTZBADqoo 5:58; js3SPxF5eV0 2:18), no forzar un
   estilo que no es natural (WZ-AJ1QDP0U 5:00; 1pRz1QqEKsM 7:04).
6. **Resumen de "3 cosas"** (jTsLtU4vRSg) o "si solo copias una cosa" (js3SPxF5eV0 6:36).

### Técnicas en pantalla que mencionan
| Técnica | Ejemplo | ¿La tiene la app? |
|---|---|---|
| Cámara lenta, avance fotograma a fotograma | todos | ✔ 0,25× / 0,5×, botones de fotograma |
| Congelar en una posición clave | "here we can see she's in her set position" | ✔ 8 fotogramas clave |
| **Dibujar líneas**: línea de hombros y altura de la punta, línea bajo la raqueta para ver la caída ("green line"), línea por la cadera | YQDx7xiZCSE 3:24, 4:38, 7:33; js3SPxF5eV0 1:56, 3:59 | ✘ (solo esqueleto, ángulos y trayectoria de la muñeca) |
| Plano vertical imaginario junto al cuerpo ("a wall here") | xiglYZXz9L8 0:30; Un4Bpskjimc 3:47 | ✘ |
| Comparación lado a lado (antes/después, jugadora A vs B) | Un4Bpskjimc 3:36, 8:17; AWgTZBADqoo 0:41 | ✔ lado a lado y superpuesto (solo sus propios golpes, como debe ser) |
| Demostración del entrenador imitando la posición | 1pRz1QqEKsM; -VnCO7JgFHI | ✘ (no aplica: sustituto = esqueleto medio) |
| Fotograma fijo en el contacto de muchas jugadoras ("take a still shot right at contact") | 1pRz1QqEKsM 2:07 | ◐ tira de contactos, galerías; falta "todos sus impactos superpuestos en uno" |
| Estadística del partido como contexto | _m5Lmb84i6g 0:13 | ✔ (resultado, presión) |

### Vocabulario (traducción propuesta para la app)
- *unit turn* → **giro unitario / giro de bloque**; *side on* → **de perfil**; *coil / uncoil* →
  **enroscar / desenroscar (cargar / soltar el tronco)**.
- *set position, power position* → **posición de armado / de potencia**; *take back* → **preparación**.
- *racket drop, into the slot* → **caída de la raqueta, entrar en el carril**; *pull out of the slot*
  → **tirar de la raqueta desde el cuerpo**.
- *lag, whip* → **retraso de la raqueta, efecto látigo**; *pre-stretch* → **preestiramiento**.
- *pat the dog* → **cara hacia el suelo ("acariciar al perro")**; *close the strings on the outside*
  → **cerrar la cara por fuera**.
- *breaking the plane* → **romper el plano (la raqueta pasa por detrás de la espalda)**.
- *spacing* → **distancia a la bola / espacio**; *gauge* → **referencia, regla de medir**.
- *load the back leg / outside leg* → **cargar la pierna de atrás / exterior**; *sit down and up* →
  **bajar y subir (impulso de piernas)**; *drive through the ball* → **atravesar la bola**.
- *brush up* → **cepillar la bola hacia arriba**; *low to high* → **de abajo arriba**.
- *windshield wiper* → **limpiaparabrisas**; *over the shoulder* → **sobre el hombro**.
- *late hitting concept* (OTI) → **"golpe tardío"**: la raqueta se queda apuntando al lateral hasta el
  último momento.

### Analogías que usan
- El brazo libre como **regla para medir la distancia** a la bola (YQDx7xiZCSE 3:09).
- **Goma elástica** que se estira y se suelta (Un4Bpskjimc 4:49); **látigo** (_m5Lmb84i6g 2:19).
- **Pared imaginaria** a la derecha o junto al cuerpo (Un4Bpskjimc 3:47; xiglYZXz9L8 0:33).
- **Lanzar una piedra rasante** = derecha ATP de codo alto (WZ-AJ1QDP0U 3:05).
- **Conducir un Ferrari** = mucha velocidad de raqueta difícil de controlar (Un4Bpskjimc 9:12).
- "La bola **no pesa** en lo más alto del bote" (SZ1Y8z-c9Qk 5:13): física falsa; no reproducir.
- "Enseña el bíceps" en la terminación (js3SPxF5eV0 6:21); "barbilla en el hombro" (jTsLtU4vRSg 2:54).

### Lo que le falta a la app en la forma de explicar
1. **Líneas dibujadas** sobre el fotograma clave (las usan para casi cada afirmación).
2. **Gancho "lo que la distingue"**: hoy el resumen recorre fases; no destaca los 2-3 rasgos en los
   que se separa de la referencia de los manuales (p. ej. "arma completo justo al botar",
   "usa más apoyo cerrado que el circuito").
3. Plantilla **qué hace → por qué → qué copiar**: hay *qué hace* (LINES) y *por qué* (COACH), falta
   la frase de **cómo imitarlo** (la consigna) y el **error típico que evita**.
4. **Dónde se rompe**: un apartado propio "con bola rápida / bajo presión cambia esto" con vídeo.
5. Vocabulario del entrenador: "giro unitario", "posición de potencia", "romper el plano", "efecto
   látigo" aparecen poco o nada; el glosario debería incluirlos.

---

## 4. Huecos y mejoras priorizados (solo lo viable con la cámara de TV)

| # | Mejora | Tipo | Esfuerzo | Por qué importa |
|---|---|---|---|---|
| 1 | **Líneas del entrenador sobre el fotograma clave**: línea de hombros y de cadera; horizontal a la altura de la cabeza para ver la punta en el armado; horizontal en la mano del armado para ver la caída; vertical por el hombro dominante ("el plano") | Presentación (`render.py` / plantilla) | bajo-medio | Es la herramienta que usan para casi todo; convierte números en algo que se ve |
| 2 | **Dónde está la raqueta en el armado: al lado del cuerpo o detrás de la espalda** (`loaded.tip_lateral` respecto al hombro dominante, marco del cuerpo) + dirección de la punta (`loaded.tip_points_to`: lateral / fondo / cielo, desde `racket3d` o el escorzo) + clase `takeback_plane` | Medida nueva + frase + COACH | medio | Es *el* debate ATP/WTA y el "late hitting concept"; desde detrás se ve muy bien; resuelve R19 |
| 3 | **Altura y separación del codo** en el armado y el impacto (`elbow_vs_shoulder`, `elbow_lateral`) | Medida nueva + frase | bajo | Codo alto (ATP) vs bajo y pegado (WTA); "codo de atrás alto" (R8); contacto con el codo cerca del cuerpo |
| 4 | **Punta respecto a la cabeza en el armado** (`loaded.tip_vs_head` = `racket_tip_height` − `body_height`) y frase con `racket_angle` ("raqueta vertical / tumbada") | Clave derivada + frase | bajo | Ítem R8 del examen; distingue armados tipo Del Potro / Djokovic / Sinner sin nombrarlos |
| 5 | **Transferencia de peso** en una frase: `com_over_feet` del armado al impacto + `rear_leg_step_after` | Frase (datos existentes) | bajo | Lo repiten todos (R21); hoy está repartido en dos sitios sin conectar |
| 6 | **Impulso de piernas "bajar y subir"**: `stroke.hip_rise` (de la cadera más baja al impacto) | Medida nueva (de curvas existentes) | bajo | Lo citan 3 vídeos; el informe dice cuánto baja, no cuánto sube |
| 7 | **Ritmo con la bola en lenguaje de entrenador**: "cuando bota, la raqueta está arriba y atrás", "deja caer la raqueta cuando la bola sube" (`stroke.acceleration_vs_bounce`) como frase principal del resumen | Clave derivada + resumen | bajo | Es el ítem más claro del examen (R10, R9) y el consejo nº 1 de Meike Babel |
| 8 | **Frenado de los hombros antes del contacto** (velocidad de giro de hombros en el impacto / su pico; `stroke.shoulder_brake`) | Medida nueva | medio | "No sobre-rotar" (OTI); el orden de la cadena ya se mide, falta este remate. Fiabilidad media: frase solo si supera el ruido |
| 9 | **Caída por debajo de la bola**: punta más baja en la aceleración frente a la altura del contacto (`acceleration.tip_below_contact`) | Medida nueva | medio | R13; base del liftado; fiabilidad baja por desenfoque → presentar como estimación |
| 10 | **"Gira mientras corre"**: `takeback_vs_first_step` y frase | Clave derivada + frase | bajo | Consejo de posicionamiento repetido; une pies y preparación |
| 11 | **Frases que faltan con datos existentes**: mano libre cruzando la línea media (`wrist_non_lateral`), brazo libre en la terminación (`finish.elbow_non`), base al terminar, desplazamiento bajo (cadera media en el desplazamiento) | Frases + COACH | bajo | Puntos de la lista que ya se miden pero no se dicen |
| 12 | **Pantalla/sección "Lo que la distingue"**: los 2-3 rasgos con mayor distancia a la referencia de la literatura (p. ej. % de apoyo cerrado frente al 84 % abierto; armado respecto al bote) con su vídeo | Presentación + lógica | medio | Es como empiezan todos los análisis; da el "gancho" sin inventar nada |
| 13 | **Consigna "para imitarla" y error que evita** por fase (tercera columna junto a `PHASE_FOCUS` y `COACH`), redactada desde las fuentes ya citadas | Texto | bajo-medio | Requisito 1 ("qué hay que hacer para pegar como X"); estructura qué→por qué→cómo |
| 14 | **Clase descriptiva de estilo** (`fh_style`: "al lado del cuerpo, codo alto" / "alrededor de la espalda, codo bajo" / mixto) combinando 2-3, nunca como juicio de calidad | Clase compuesta | bajo (tras 2-3) | Vocabulario que el usuario va a oír en todos los análisis; los entrenadores insisten en que ninguno es "mejor" |
| 15 | **Examen interno de las afirmaciones de entrenadores** (este documento, sección 1) como test/validación en `docs/validacion.md`: para cada ítem, regla de confirmación y resultado tras los 4 partidos. **Nunca en el informe** | Validación | medio | Comprueba que las medidas "ven" lo que ve un experto; detecta medidas que no discriminan |

Fuera de la lista a propósito (✘✘ o de valor dudoso): empuñadura exacta, brazo relajado, pronación,
cara exacta en el impacto (las cifras de los entrenadores — 8°, 30°, "casi hacia abajo" — se
contradicen entre sí), contacto delante (profundidad; como mucho una estimación 3D futura con
`ball3d`/`racket3d`), velocidad y efecto absolutos, ejercicios de entrenamiento (vibración, coger la
bola con la mano), que no son medidas de partido.
