# Matriz de cobertura de la derecha

Referencia: lo que la literatura técnica y biomecánica describe de una derecha y lo que miden los
sistemas profesionales (fuentes al final). Cada elemento con su estado en TennisBio:

- ✔ **medido** (descriptor implementado, con su fiabilidad)
- ◐ **parcial** (implementado de forma incompleta o aproximada)
- ○ **hueco medible** (la tele lo permite y falta implementarlo)
- ✘ **no observable desde la tele** (se dice así en la app, nunca se inventa)

Cámara: detrás del fondo y elevada; jugadora cercana de 300-400 px, 25-60 fps; pose COCO-17,
5 puntos de raqueta, bola, homografía de la pista, marcador.

## 1. Fases (modelo ITF: Elliott, Reid y Crespo; Landlinger 2010; Tennis Australia; Knudson)

| Evento / fase | Estado | Implementación |
|---|---|---|
| Golpe del rival → split step | ✔ | `ready` (aterrizaje del split) |
| Inicio del giro de bloque (preparación) | ✔ | `takeback` |
| Final del armado (máximo giro, raqueta más atrás) | ◐ | `loaded` = pausa de la muñeca; falta contrastar con el máximo giro de hombros |
| Inicio del swing hacia delante | ✔ | `acceleration` |
| Impacto | ✔ | bola + pose (validado: ±1 fotograma) |
| Final de la extensión | ◐ | `extension` = impacto + 50 ms fijo |
| Final de la terminación | ✔ | `finish` |
| Primer paso de recuperación | ✔ | `recovery` |

## 2. Cuerpo

| Elemento | Fuente | Estado | Implementación / acción |
|---|---|---|---|
| Postura de espera (rodillas, base, peso) | TA 2013; Elliott 2006 | ✔ | `ready.body_height`, `base_width`, `hip_height` |
| Mano libre en la garganta de la raqueta en la espera / giro de bloque | TA 2013; ITF | ✔ | `hands_apart`, clase `ready_hands` |
| Momento del armado respecto al bote ("armado completo al botar") | TA 2013 | ✔ | `stroke.loaded_vs_bounce` |
| Giro de cadera y de hombros al final del armado | Takahashi; Landlinger | ◐ | `loaded.shoulder_turn`, `hip_turn` (2D, magnitud; 3D experimental) |
| Separación cadera–hombros (X-factor) | Takahashi; Landlinger; TA | ◐ | `loaded.x_factor` (2D, media) |
| Pausa entre armado y swing | Elliott 2006 | ✔ | `stroke.pause_at_loaded` |
| Brazo libre extendido y cruzado | Elliott; TA | ✔ | `loaded.elbow_non`, `shoulder_abd_non`, `wrist_non_*` |
| Carga de la pierna exterior / descenso de cadera | TA; Nesbit 2008 | ✔ | `hip_height`, `knee_*` (2D, baja), `weight_loaded_to_non` |
| Peso entre los pies / equilibrio | iTPA; TA | ✔ | `com_over_feet`, `head_over_base`, `trunk_tilt` |
| Cadena cinética (orden pelvis → tronco → brazo → antebrazo) | Landlinger; Elliott | ✔ | orden de picos suavizados; **solo el orden** (los 18 ms que separan a la élite no se resuelven) |
| Momento de los picos en ms | Landlinger | ✘ | por debajo de 1 fotograma |
| Rotación interna del hombro, pronación, desviaciones de la muñeca | Elliott 1997; Pedro 2022 | ✘ | rotaciones sobre el eje del segmento: invisibles en 2D |
| Altura del contacto (respecto a rodilla, cadera, hombro) | Elliott 1989; Reid 2013 | ✔ | `impact.wrist_dom_height`, `wrist_dom_vs_hip`, `wrist_dom_vs_shoulder` |
| Separación lateral del contacto | Knudson 2006 (se observa desde detrás) | ✔ | `impact.wrist_dom_lateral` |
| Contacto delante/detrás del cuerpo | TA; ITF | ✘ | eje de profundidad (solo 3D estimado) |
| Ángulo del codo en el impacto (brazo recto / doble flexión) | Elliott 1989/1997; Gordon | ✔ | `impact.elbow_dom` (2D, media) + clase `arm` |
| Cabeza estable en el impacto | Lafont 2008; TA | ✔ | `head_motion` (relativa a la cadera, ±50 ms) |
| Mirada | Lafont 2008 | ✘ | se ve de espaldas |
| Hombros más girados que la cadera en el impacto | Reid; Landlinger | ◐ | `impact.shoulder_turn`, `hip_turn` (2D) |
| Extensión tras el contacto | ITF | ✔ | `extension.arm_extension`, `swing_rise_after` |
| Terminación sobre el hombro / limpiaparabrisas / alrededor / invertida | TA; Counts | ✔ | clase `finish` (heurística) |
| "3 × 90°" al final | Reid 2013 | ✔ | clase `finish_3x90` (hombro y codo; la muñeca no se ve) |
| Paso adelante de la pierna trasera tras el impacto | Landlinger 2010 | ✔ | `footwork.rear_leg_step_after` |
| Fuerzas, momentos articulares | — | ✘ | cinemática solamente |

## 3. Pies y desplazamiento

| Elemento | Fuente | Estado | Implementación / acción |
|---|---|---|---|
| Split step: aterrizaje respecto al golpe del rival | Uzu 2009; Filipcic 2017 | ✔ | `ready` + `takeback_after_opp` |
| Split step: despegue y aterrizaje respecto al golpe del rival | Avilés; Mecheri; Filipcic | ✔ | `split_takeoff_vs_opp_s`, `split_landing_vs_opp_s` |
| Presencia del split | Cardiff Met | ✔ | método de `ready` |
| Velocidad 0,2 s antes y después del split | Filipcic 2017 | ✔ | `speed_pre_split_mps`, `speed_post_split_mps` |
| Primer paso: momento (reacción) | Uzu; Mecheri | ✔ | `first_step_s` |
| Primer paso: tipo (gravity, jab, pivot, counter, cruzado, lateral) | Bragg 2001; Vuong 2022 | ◐ | cruzado, gravity, jab, pivote, lateral, delante, atrás (counter step no se distingue del gravity sin los pies) |
| Primer paso: dirección correcta respecto a la bola | Mecheri | ✔ | `first_step_right_way` (respecto a dónde golpea) |
| Número de pasos hasta la bola | Tanabe (≈2 H, ≈3 M) | ✔ | `steps_to_impact` |
| Longitud de cada paso; anchura del primero | Tanabe | ✔ | lista de pasos, `first_step_length_m`, `last_step_length_m` |
| Pasos de ajuste | Cardiff Met; Giles | ✔ | `adjustment_steps` |
| Distribución lateral / delante / atrás | Weber; Kovacs | ✔ | clase `move_direction` |
| Cambios de dirección | Giles 2023 | ✔ | `direction_changes` |
| Velocidad media y máxima de carrera | Martínez-Gallego; TA | ✔ | `peak_speed_mps` (p90, suavizado), `speed_at_impact_mps` |
| Recorrido hasta la bola | Reid 2013 (70 % tras 3-4 m) | ✔ | `path_m` |
| Tipo de apoyo (abierto, semiabierto, neutro, cerrado) | IJSSC 2025 (abierto 83,6 %) | ✔ | `stance_loaded`, `stance_impact` |
| Subtipos: abierto de ataque, abierto defensivo, neutro de ataque | Martin 2021 | ✔ | clase `stance_role` |
| Pierna que carga | Sandamas 2013 | ✔ | `weight_loaded_to_non` (proxy) |
| En carrera, en salto, a un pie, deslizando | Giles & Reid 2021; Starbuck | ✔ | clase `movement`; deslizar solo en tierra/hierba |
| Última zancada más larga en carrera | Giles & Reid 2021 | ✔ | `last_step_length_m` (por situación en el modelo) |
| Recuperación: distancia, dirección, tiempo | Armstrong 2024; Yandell | ✔ | `recovery_*` a 1 s, `off_centre_at_opp_hit_m`, `moving_at_opp_hit_mps` |
| Orientación del pie, apoyo de talón/punta | — | ✘ | COCO-17 sin puntas ni talones |
| Altura del split step | — | ✘ | eje vertical confundido con la profundidad |

## 4. Raqueta, swing y empuñadura

| Elemento | Fuente | Estado | Implementación / acción |
|---|---|---|---|
| Forma del armado: bucle, recto, "pat the dog" | Yandell; TA | ✔ | clases `takeback` y `takeback_face` (cara al suelo = pat the dog) |
| Altura de la mano en el armado (no por encima de la cabeza) | TA | ✔ | `loaded.wrist_dom_vs_shoulder` |
| Cara de la raqueta al final del armado | Elliott & Marsh 1989 | ✔ | `loaded.face_tilt`, `face_points_to` (fiabilidad buena) |
| Caída de la raqueta antes de acelerar | Yandell; Reid 2013 | ✔ | `acceleration.racket_head_vs_wrist`, `wrist_drop` |
| Retraso de la muñeca (lag) | Landlinger; Pedro 2022 | ◐ | `racket_forearm` (ángulo proyectado; no es la extensión anatómica) |
| Trayectoria de abajo arriba (signo) / liftado-plano-cortado | Takahashi; Elliott & Marsh | ✔ | `swing_low_to_high` + clase `swing` |
| Ángulo exacto de la trayectoria en el impacto | Kwon 2017 | ✘ | las diferencias reales (3°) están por debajo del error |
| Cara en el impacto | Kwon 2017; Choppin 2011 | ◐ | solo estimación interpolada; las conclusiones no dan grados |
| Velocidad de la raqueta absoluta | Landlinger (33 m/s) | ✘ | desenfoque |
| Velocidad de la raqueta relativa entre golpes | sensores | ◐ | `racket_speed_rel` (baja fiabilidad, solo para comparar) |
| Posición de la mano en el mango | Yandell | ◐ | `hand_on_handle` (baja fiabilidad) |
| Empuñadura (bisel) | Yandell; Elliott 1997 | ✘ | mano de 20-40 px |
| Empuñadura: "compatible con este / semioccidental-occidental" | Elliott 1989/1997 | ✔ | `explain.grip_compatible` (tres indicios; nunca el bisel) |
| Empuñadura en la espera y cambio de empuñadura | — | ✘ | no hay estudio ni imagen suficiente |
| Pronación, contribución de cada segmento, punto en el cordaje, presión de agarre | Pedro 2022; Choppin | ✘ | |

## 5. Bola, resultado y contexto (sistemas profesionales)

| Elemento | Quién lo da | Estado | Implementación / acción |
|---|---|---|---|
| Bote: profundidad, anchura, dentro/fuera | Hawk-Eye, SwingVision | ✔ | `shot_landing` |
| Dirección cruzada, paralela, al centro, invertidas | F3Set, TennisViz | ✔ | `shot_direction`, `shot_type` |
| Velocidad media de la bola en pista | Hawk-Eye, sensores | ✔ | `ball_speed_avg_kmh` (horizontal, media; no la de salida) |
| Efecto (rpm), velocidad de salida, altura sobre la red | Hawk-Eye | ✘ | bola pequeña y borrosa; sin 3D |
| Fase ataque / neutra / defensa | TennisViz | ✔ | clase `intent` |
| Calidad del golpe (sustituto: profundidad, anchura, velocidad media) | TennisViz (Shot Quality) | ✔ | `shot_quality_proxy` (indicador propio, no el de TennisViz) |
| Puntos ganados en ataque / en defensa | TennisViz (Conversion / Steal) | ✔ | `point_won` (cambio del marcador) × intención del último golpe del punto |
| Longitud del peloteo | todos | ◐ | sus golpes del punto contados con los impactos de la pasada barata (`shot_in_point`, `shots_in_point`); clase "resto / inicio del punto / peloteo". Solo si el plano empieza antes del punto |
| Resto, globo, dejada, volea, subida a la red | F3Set, SwingVision | ◐ | subida ✔ (`approach`), resto ✔ (`play`); globo, dejada y volea: otros golpes, después |
| Ganador / error (forzado o no) | F3Set, SwingVision | ◐ | fuera ✔, red y ganador probables; forzado/no forzado ✘ (subjetivo) |
| Presión, set, fatiga | ATP/WTA | ✔ | marcador (OCR) |

## Huecos medibles pendientes
- Final del armado: la pausa de la muñeca se guarda junto al momento del máximo giro de hombros y
  de cadera (`t_max_shoulder_turn`, `t_max_hip_turn`); falta validarlos con golpes anotados.
- Final de la extensión: el avance horizontal de la muñeca va hacia la red (profundidad, invisible
  desde detrás); se mantiene +50 ms, como en la literatura (40-60 ms).

## Fuentes principales
- Reid M, Elliott B, Crespo M (2013). Mechanics and learning practices associated with the tennis forehand: a review. *J Sports Sci Med* 12:225-231.
- Landlinger J et al. (2010). Key factors and timing patterns in the tennis forehand of different skill levels. *J Sports Sci Med* 9:643-651.
- Elliott B (2006). Biomechanics and tennis. *Br J Sports Med* 40:392-396.
- Elliott B, Takahashi K, Noffal G (1997). The influence of grip position on upper limb contributions to racket head velocity. *J Appl Biomech* 13:182-196.
- Knudson D (2006). Applying biomechanics to the qualitative analysis of the forehand. ISBS.
- Tennis Australia (2013). Coach Development – Technical Fundamentals.
- Nesbit SM et al. (2008). The role of knee positioning and range-of-motion on the closed-stance forehand. *J Sports Sci Med* 7:114-124.
- Kwon S et al. (2017). Influence of tennis racquet kinematics on ball topspin. *J Sports Sci Med* 16:505-513.
- Pedro B et al. (2022). Upper limb joint contribution to racket head speed in elite players (IMU). *Sensors* 22:1283.
- Elliott B, Marsh T (1989). Topspin and backspin forehand approach shots. *J Sports Sci*.
- Choppin S et al. (2011). Impact characteristics at the Wimbledon qualifying tournament. *Sports Eng*.
- Uzu R et al. (2009). A split-step shortens the time to perform a choice reaction step-and-reach movement. *J Sports Sci* 27(12).
- Filipcic A et al. (2017). Split-step timing / movement speed of professional and junior players. *J Hum Kinet*.
- Bragg & Andriacchi (2001). The lateral reaction step in tennis footwork. ISBS.
- Vuong et al. (2022). Initial step patterns for multidirectional acceleration. *J Hum Kinet* 85.
- Tanabe et al. Steps of professionals at the AIG Japan Open 2006.
- Giles B, Reid M (2021). Applying the brakes in tennis. *J Sports Sci* 39(3).
- Giles B et al. (2023). Movement styles, Australian Open. *Eur J Sport Sci*.
- Martin C et al. (2021). Influence of the forehand stance on knee biomechanics. *J Sports Sci*.
- Contextual cues and stance decision-making in tennis forehand (2025). *Int J Sports Sci Coach*.
- Armstrong C et al. (2024). Distance demands in Grand Slam tennis. *JSSM* 23:1-7.
- Martínez-Gallego R et al. (2013). Movement characteristics of elite players on hard courts. *JSSM* 12:275-281.
- Lafont D (2008). Gaze control during the hitting phase in tennis. *Int J Perf Anal Sport* 8:85-100.
- Hawk-Eye SkeleTRACK; ATP/TennisViz Insights (Shot Quality, In Attack, Conversion & Steal); SwingVision (ITF PAT 25-037); F3Set (ICLR 2025); THETIS; Match Charting Project.
