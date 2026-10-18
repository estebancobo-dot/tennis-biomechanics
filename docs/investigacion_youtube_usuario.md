# Vídeos de análisis elegidos por el usuario (17-10)

Tres vídeos de entrenadores sobre la derecha de otros jugadores, analizados en el PC (petición 17: texto y unos 90 fotogramas de cada uno; `pc-logs:investigacion_17/`). Solo sirven para aprender cómo analizan y explican; nada de ellos entra en el informe (requisito 6).

| Vídeo | Entrenador | Vista |
|---|---|---|
| Ash Barty Tennis Forehand | Meike Babel (ex top 30 WTA) | De frente (entreno) y lado a lado de dos golpes suyos |
| Arthur Fils Heavy Topspin Forehand | Intuitive Tennis | El entrenador repite el gesto junto a un recuadro con el jugador |
| Sinner's Forehand: Complete Analysis | Jason Frausto (TennisUnleashed) | Lateral y desde detrás (como la tele), lado a lado con Jack Sock |

## Qué miran y en qué orden

1. **Contexto:** dónde juega (Barty: el 51 % de sus derechas desde la línea de fondo o dentro).
2. **Empuñadura:** la estiman con un plano cercano a cámara lenta.
3. **Preparación:** el giro con la mano libre; las manos se separan a la altura de la cabeza.
4. **Armado:** su altura, que cambia según la bola recibida. También la raqueta de lado con las cuerdas hacia la valla del fondo, y el codo separado «1-2 pelotas».
5. **Carga:** bajar y cargar la pierna de fuera.
6. **Aceleración:** la cadera antes que la raqueta; el extremo del mango apunta a la bola (lag); la cara mira al suelo.
7. **Impacto:** delante del cuerpo; la cara, neutra o algo cerrada.
8. **Terminación y salto:** despega como consecuencia, no a propósito.
9. **Variantes:** el apoyo según la bola; dos golpes suyos lado a lado (más tiempo: armado más alto).
10. **Resumen:** «lo que puedes copiar», en 4 puntos.

## Cómo lo enseñan (gráficos)

- **Secuencias de 3-4 fotos reales** del jugador, una al lado de otra (Fils, Barty).
- **Lado a lado sincronizado:** dos golpes o dos jugadores.
- **Avance fotograma a fotograma**, parando en cada posición.
- **Un círculo** sobre la parte que importa (punta de la raqueta, muñeca, bola) y **una frase corta** sobre el vídeo.
- **Mapa de pista** con el % de golpes desde dentro (Barty).
- **Sin esqueletos, ángulos ni gráficas.** Primero el golpe a velocidad real, después lento.

## Frente a la aplicación

**Medidas.** Todo lo que se puede ver desde la tele ya está en `learn.py` o en la matriz:

| Punto de los entrenadores | Dónde está |
|---|---|
| Golpea desde dentro de la pista | clase `depth` |
| Altura del armado | `loaded.wrist_dom_vs_shoulder` y «Cambia con la bola» |
| Giro con la mano libre | `takeback.hands_apart` |
| Bajar y cargar la pierna de fuera | «Bajar y subir», `loaded.com_over_feet` |
| Cadera antes que la raqueta | `chain.proximal_to_distal` |
| Despega del suelo | `movement` «en el aire» |
| Apoyo según la bola | apoyo por situación |
| Lag | `racket_lag_deg` |
| Cuerdas | línea de cuerdas por fase |
| Codo separado | `loaded.elbow_dom_lateral` |
| Split step | fase 1 |

Fuera de alcance:
- **Empuñadura:** «lo que la tele no mide».
- **Punta por delante de la mano y su recorrido («tip flip»):** es profundidad desde detrás; no medible desde la tele.
- **Comparar con otro jugador:** excluido por el requisito 6.

**Presentación.** Ya estaban:
- el lado a lado (Comparar y «Cambia con la bola»);
- la marca dibujada sobre el vídeo de cada fase, que equivale a su círculo;
- el mapa de pista;
- el botón de velocidad real.

Añadido el 17-10 en la lección:
- **Tira de fases con una foto real de su golpe más representativo en cada fase:** la secuencia de los entrenadores, con sus propios golpes. En el móvil siguen los botones de texto, para no bajar el vídeo de la primera pantalla.
- **‹ ›: avance fotograma a fotograma** dentro de la fase.
- La auditoría comprueba la tira: «La tira de fases enseña su golpe en fotos reales».

No se cambia:
- **La frase sobre el vídeo:** el foco ya está al lado, y repetirlo encima tapa la imagen.
- **El orden «real y luego lento»:** se queda el lento con el botón de velocidad real. La lección es para mirar una fase, no el golpe entero.

# Julien Olivari: «3 fundamentos» y «Dame 10 minutos» (18-10)

Dos vídeos del mismo entrenador, elegidos por el usuario y analizados en el PC (petición 25: texto con tiempos y unos 90 fotogramas de cada uno; `pc-logs:investigacion_25/`). Como los anteriores, solo sirven para aprender cómo enseña; nada entra en el informe (requisito 6).

| Vídeo | Duración | Vista |
|---|---|---|
| 3 Universal Tennis Fundamentals Every Pro Uses (`jeHMwLeUdgY`) | 12 min | Habla a cámara y lo demuestra de frente en pista; dos fotos de profesionales en el contacto (4:51, 10:23) |
| Give me 10 Minutes. I'll Make You a Pro Tennis Player (`svfPm693UP0`) | 22 min | Golpea él: de frente, de lado y **desde detrás, como la tele** (2:40-4:20); derecha, revés, saque, volea y smash |

## Qué enseña

**Vídeo 1: tres fundamentos para cualquier golpe**
1. **Ojos en la bola (0:31-5:05).** Mirar el contacto de la raqueta rival «a cámara lenta». Así el split step sale como reacción, sin pensarlo (1:19-2:00). Tras golpear, seguir mirando el punto de impacto («uno») y solo después levantar la cabeza (2:09-4:50). Lo ilustra con una foto de Federer en el contacto.
2. **Nunca a la red (5:06-8:08).** Fijarse en la parte de abajo de la bola y golpearla ahí: sale algo de liftado y más margen. Pensar en «ir por debajo de la bola» no le gusta, porque desconecta de la bola (7:54).
3. **Contacto delante (8:09-11:10).** Delante del hombro no dominante («no dejes que la bola pase tu zona»). Si golpeas tarde, la bola sube y sale larga, y el golpe te empuja hacia atrás. Su ejercicio (10:56): avanzar, frenar las piernas y dejar que el brazo siga hacia delante.
4. **Bajo presión (11:25):** usar esos tres pensamientos sobre la bola y no pensar en la técnica.

**Vídeo 2: subir de nivel**
- **Derecha (0:45-9:30).** Dejar la bola «pegada a las cuerdas» el mayor tiempo posible: acompañarla en vez de dar un golpe seco. Marcar su propio ritmo y no bloquear la potencia de la rival (2:40-6:30). Acelera solo cuando nota ese control, con el brazo suelto (8:50). En bolas cortas, primero controlar; para atacar bolas altas usa su «arm wrestling forehand», sin explicar la mecánica (5:01-6:00).
- **Revés (9:30-11:40):** la misma idea.
- **Saque (11:40-17:00):** el saque es un lanzamiento con el codo por delante; critica enseñar «hombro sobre hombro». **Volea (17:00-19:30):** la fuerza sale de las piernas y no hay armado. **Smash (19:30-21:45):** el brazo libre arriba hasta el contacto y la muñeca suelta.

## Cómo lo enseña
- **Pocas claves repetidas como un mantra**, contadas en voz alta («uno» y después levantar la cabeza) y en pista a velocidad real, con muchas repeticiones.
- **Habla consigo mismo** en cada golpe («este no se pegó»).
- **Una sola foto de un profesional** en el contacto para cada clave.
- **Sin esqueletos, números ni cámara lenta.** Tampoco aquí hay nada que la aplicación no tenga ya; «Cómo comprobarlo» ya usa palabras dichas en voz alta («giro», «bote», «ya», «arriba»).

## Frente a la aplicación

**Ya lo medimos y lo enseñamos**
- **Split step al golpe de la rival:** fase 1, `split_landing_vs_opp_s` y `first_step_s`.
- **Cabeza quieta en el impacto:** `stroke.head_motion_cm` (±50 ms). Su «Cómo comprobarlo» («hasta oír el bote») pide incluso más tiempo que el «uno» del entrenador.
- **Bola a la red:** `swing_low_to_high`, `wrist_drop` y el síntoma «La bola se va a la red». Su «parte de abajo de la bola» equivale al foco de la fase 4.
- **«Pegada a las cuerdas»:** es literalmente el foco de la fase 6 («como si la bola siguiera pegada a ellas»), medido con `arm_extension` y `swing_rise_after`.
- **Frenar las piernas para que pase el brazo:** `shoulder_brake`, `braking_step`, `weight_shift`.
- **Golpe tarde que te empuja hacia atrás:** `class.back_at_impact`, `finish.head_over_base`.
- **Bajo presión:** el resumen ya compara los puntos de presión con el resto (`findings`, «bajo presión»), con todas las medidas del informe (cabeza incluida).

**Lo medimos, pero la lección no lo dice así**
- **«Tarde → larga y hacia atrás»:** los síntomas «Llegas tarde» y «La bola se va larga» no enlazan `class.back_at_impact` ni `stroke.contact_vs_top`, que son justo las medidas de golpear tarde.
- **«Nunca a la red»:** sus errores a la red y fuera ya se cuentan en las conclusiones (`outcomeDetail`), pero el síntoma «La bola se va a la red» no los muestra.

**Medible desde la tele, pero falta**
- **Cabeza quieta *después* del impacto:** cuánto tiempo sigue quieta tras golpear, no solo ±50 ms. La fuente es Lafont 2008: las expertas mantienen la cabeza orientada al contacto tras golpear. Fiabilidad media-baja, porque la cabeza gira con el tronco en la terminación.
- **Nota:** `head_motion_impact_cm` usa la nariz (`stroke_analysis.py`). Desde detrás la nariz no se ve y el modelo la adivina; el centro de las orejas sería más estable. Habría que comprobarlo antes de crear la medida nueva.

**No medible desde la tele**
- **Mirada y «parte de abajo de la bola»:** se la ve de espaldas (✘ en la matriz). Lo más cercano es la vista frontal de entreno, `head_to_contact_idx`.
- **Tiempo de la bola en las cuerdas:** dura unos milisegundos, menos de un fotograma (20-40 ms). Además lo fija la física del impacto, no la jugadora.
- **Contacto delante del hombro:** es el eje de profundidad. Solo se ve en la vista lateral de entreno (`contact_in_front_pct`) o en la estimación 3D.
- **Brazo suelto, tensión del agarre:** ya está en «lo que la tele no mide».

## Contradicciones y quién tiene razón
- **«La bola pegada a las cuerdas el mayor tiempo posible».** Tomada al pie de la letra es falsa: el contacto dura unos milisegundos sea cual sea la técnica. Como sensación sirve, y lo que se ve es el recorrido de la raqueta tras el contacto. La lección ya lo dice bien («como si…») y lo mide (`swing_rise_after`, `arm_extension`). No se cambia.
- **«Golpea la parte de abajo de la bola», frente a nuestro foco de la fase 4 («deja caer la cabeza de la raqueta por debajo de la bola»).** La mecánica es la misma: caída por debajo de la bola y subida de abajo arriba (Reid, Elliott y Crespo 2013; Elliott y Marsh 1989). Lo que cambia es el foco: el suyo está en la bola. Los dos son focos externos (Wulf, ya usado en la lección). Se mantiene el nuestro, porque describe lo que se mide en ella.
- **Split step «por instinto, mirando la raqueta rival», frente a nuestro «aterriza cuando oigas el golpe».** No chocan. El momento lo respaldan Uzu 2009 y Filipcic 2017; él da la señal visual y nosotros la sonora.
- **Saque: «hombro sobre hombro es un error».** Contradice la literatura: en el saque de élite la inclinación de hombros forma parte de la cadena cinética (Elliott 2006). No afecta a la derecha. Cuando se haga el saque, se medirá su inclinación sin juzgarla con esta opinión.

## Propuestas (por orden)
1. **Síntomas «Llegas tarde» y «La bola se va larga»:** añadir `class.back_at_impact` y `stroke.contact_vs_top`. Ya están medidas: solo hay que enlazarlas.
2. **Síntoma «La bola se va a la red»:** enseñar cuántos de sus errores van a la red y cuántos fuera (`outcomeDetail`), con la etiqueta «probable» que ya llevan y solo si hay suficientes golpes con resultado conocido.
3. **Medida nueva «Cabeza quieta tras el impacto»** (○ en la matriz): ms tras el impacto en que la cabeza sigue dentro de pocos cm respecto a los hombros, medida con el centro de las orejas. Se validaría con los clips públicos y con `head_to_contact_idx` del entreno, y solo se enseña si supera el ruido de medida. Antes, revisar si `head_motion_cm` debe dejar la nariz.
4. **«Cómo» de la fase 1:** añadir «mirando la raqueta de la rival» como consejo de entrenador (no es un dato suyo).

**Hecho (18-10), propuestas 1-3:**
1. «Llegas tarde» y «La bola se va larga» enlazan `class.back_at_impact`, `class.ball_phase` y `stroke.contact_vs_top`, y dicen en qué % de sus golpes (de la situación elegida) golpea retrocediendo y toma la bola cayendo, con un golpe así para verlo (`learn.LATE_SIGNS`). Si la medida es ruido, no se da.
2. «La bola se va a la red» dice cuántos de sus errores van a la red, largos o anchos (largo/ancho sale del bote de su bola en la pista), marcado «probable», con un golpe de cada; con menos de 5 errores de resultado conocido dice «pocos datos».
3. `stroke.head_still_after_cm`: lo que más se mueve el centro de las orejas respecto al de los hombros en los 150 ms tras el impacto (solo lado cercano), con su ruido medido moviendo el contacto ±1-2 fotogramas. `head_motion_cm` no se toca (sigue con la nariz). Queda pendiente validarla con clips anotados y con `head_to_contact_idx` del entreno.

No se cambia: el foco de la fase 4 ni la frase de la fase 6. La volea, el smash y el saque quedan para cuando se analicen esos golpes (requisito 10).
