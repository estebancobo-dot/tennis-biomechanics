"""«Aprende su derecha»: the forehand of the player as a template the user can copy.

The structure is the one of professional coaching apps (Sportsbox P-positions, ITF coaching
manuals): the stroke split into positions, each with 3-5 checkpoints; for each checkpoint her
measured value (from her strokes of the chosen situation), what to do, the typical mistake and a
drill. The coaching text (cue, mistake, drill, what changes in each situation) is coaching knowledge
(ITF / Crespo-Reid, Elliott, Tennis Australia, coaches' analyses of her forehand), never her data:
the report marks it as such. Her values always come from her strokes, with how many back them.

Every item of the user's master matrix (docs/matriz_cobertura.md, section 6) is attached to a
checkpoint, to a situation or to the list of what TV cannot measure, so nothing of it is left out.
"""
from __future__ import annotations

SOURCE = "Conocimiento de entrenadores (ITF, Tennis Australia, análisis de entrenadores de su derecha)"

# checkpoint: key (flattened stroke value), label, unit, decimals, how her value reads, cue (what to do),
# mistake, drill, matrix items it covers
def cp(key, label, unit, dec, read, cue, mistake, drill, covers=()):
    return {"key": key, "label": label, "unit": unit, "dec": dec, "read": read, "cue": cue, "mistake": mistake,
            "drill": drill, "covers": list(covers)}


PHASES = [
    {"id": "ready", "title": "1 · Espera y split step", "when": "Cuando la rival golpea: pequeño salto y aterrizaje con los dos pies.",
     "checkpoints": [
         cp("footwork.split_landing_vs_opp_s", "Aterrizaje del split step", "s", 2,
            "segundos después del golpe de la rival (≈ 0 = aterriza justo cuando la rival golpea)",
            "Salta un poco antes de que la rival golpee y aterriza justo cuando golpea: así sales hacia la bola en cuanto sabes dónde va.",
            "Saltar tarde (aterrizar cuando la bola ya viene) o no saltar: el primer paso sale tarde.",
            "Con un compañero: di «ya» en voz alta cuando golpee y aterriza en ese instante; 10 bolas, luego sin hablar.",
            ["Split step", "Latencia de reacción al golpe de la rival"]),
         cp("ready.hip_height", "Altura de la cadera en la espera", "%", 0, "% de su altura (más bajo = rodillas más flexionadas)",
            "Rodillas flexionadas y peso en la parte delantera de los pies, listo para salir.",
            "Esperar de pie con las piernas rectas.", "Sombras: posición de espera 5 s, split step y salida lateral; 3 series de 8.",
            ["Carga: flexión de rodillas"]),
         cp("ready.base_width", "Anchura de los pies en la espera", "%", 0, "% de su altura entre tobillos",
            "Pies algo más separados que los hombros.", "Pies juntos: no puedes empujar hacia ningún lado.",
            "Marca en el suelo la anchura de tus hombros y espera con los pies un poco por fuera.", []),
         cp("class.ready_hands", "Manos en la espera", "", 0, "cómo sujeta la raqueta",
            "Coloca las manos como ella (arriba): si sujeta la garganta con la mano libre, gira hombros y raqueta juntos; si la separa, la mano libre ya apunta hacia la bola.",
            "Soltar o mover la mano libre sin intención: el giro se hace solo con el brazo.", "Espera con las manos como ella y gira hombros y raqueta juntos en el split step.",
            ["Giro de hombros (unit turn)"]),
     ]},
    {"id": "takeback", "title": "2 · Inicio de la preparación (giro de hombros)", "when": "En cuanto sabe que es derecha: gira hombros y raqueta a la vez.",
     "checkpoints": [
         cp("stroke.takeback_vs_bounce", "Cuándo empieza a girar", "s", 2, "s respecto al bote de la bola (− = antes de que bote)",
            "Empieza a girar los hombros antes de que la bola bote en tu campo.",
            "Esperar al bote para preparar: llegas tarde y acortas el golpe.",
            "Peloteo suave: di «giro» cuando la bola cruce la red; tienes que estar de lado antes del bote.",
            ["Giro de hombros (unit turn)", "Adaptación a bola rápida, corta, alta, abierta"]),
         cp("takeback.shoulder_turn", "Giro de hombros al empezar", "°", 0, "° de giro (2D, desde detrás)",
            "Gira hombros y tronco como un bloque, con la raqueta delante del cuerpo.",
            "Llevar la raqueta atrás solo con el brazo.", "Sombras con la raqueta sujeta con las dos manos hasta que los hombros estén de lado.",
            ["Giro de hombros (unit turn)", "Rotación torácica"]),
         cp("stroke.takeback_vs_first_step", "Gira mientras se mueve", "s", 2, "s respecto a su primer paso (− = gira antes de dar el primer paso)",
            "Gira mientras corres hacia la bola, no al llegar.", "Correr de frente y girar al final.",
            "Bolas abiertas alternas: gira en el primer paso y corre ya de lado.", ["Pasos cruzados"]),
         cp("class.takeback", "Forma de la preparación", "", 0, "compacta / amplia / en bucle alto",
            "Prepara con la forma que usa ella (arriba: compacta, amplia o en bucle alto) y sin pararte: la raqueta no debe quedarse quieta atrás.",
            "Parar la raqueta atrás (punto muerto): pierdes la aceleración.",
            "Sombras dibujando una «gota» con la cabeza de la raqueta, sin pausas, a cámara lenta.", ["Bucle de la preparación (forma)"]),
     ]},
    {"id": "loaded", "title": "3 · Armado completo", "when": "Hombros girados al máximo, raqueta arriba y atrás, peso en la pierna de atrás.",
     "checkpoints": [
         cp("loaded.shoulder_turn", "Giro de hombros", "°", 0, "° (más = más de espaldas a la red)",
            "Hombros de lado, la espalda casi mirando a la red rival.", "Girar poco: el golpe sale solo de brazo.",
            "Con una pica a la espalda: gira hasta que señale el poste de la red.", ["Giro de hombros (unit turn)"]),
         cp("loaded.x_factor", "Separación hombros–cadera", "°", 0, "° que los hombros giran más que la cadera",
            "Los hombros giran más que la cadera: el tronco queda «enrollado» como un muelle.",
            "Girar cadera y hombros a la vez: no hay torsión que soltar.", "Sombras: gira hombros con la cadera quieta mirando al lateral.",
            ["Separación cadera–hombro (torque)", "Rotación pélvica"]),
         cp("loaded.elbow_non", "Brazo libre", "°", 0, "ángulo del codo libre (180 = estirado)",
            "El brazo libre casi estirado, paralelo a la línea de fondo y señalando la bola: mide la distancia.",
            "Brazo libre pegado al cuerpo: el giro se queda corto y pierdes la referencia de la bola.",
            "Lanza la bola con la mano libre y señálala con ese brazo hasta el bote; luego golpea.",
            ["Brazo libre paralelo a la línea de fondo en el giro; distancia a la bola"]),
         cp("loaded.racket_head_vs_wrist", "Cabeza de la raqueta respecto a la mano", "%", 0, "% de altura (+ por encima de la mano)",
            "La cabeza de la raqueta arriba, por encima de la mano, con la cara mirando al suelo.",
            "Raqueta baja desde el principio: el swing sale plano y sin aceleración.", "Sombras parando en el armado: comprueba en un espejo que la cabeza esté por encima de la mano.",
            ["Bucle de la preparación (forma)", "Cara de la raqueta en la caída y en el impacto"]),
         cp("loaded.elbow_dom_vs_shoulder", "Altura del codo en el armado", "%", 0, "% de altura respecto al hombro (+ por encima del hombro)",
            "Lleva el codo a la altura a la que lo lleva ella al armar.", "Codo muy alto (por encima del hombro): el armado se alarga y tensa el hombro.",
            "Sombras parando en el armado frente a un espejo: el codo a su altura respecto al hombro.", []),
         cp("loaded.elbow_dom_lateral", "Separación del codo en el armado", "%", 0, "% de altura hacia fuera del hombro",
            "Separa el codo del cuerpo como ella al armar.", "Codo pegado al costado: el brazo no tiene espacio para acelerar.",
            "Sombras con una pelota entre el codo y el costado sin apretarla.", []),
         cp("loaded.racket_tip_vs_head", "Punta de la raqueta respecto a su cabeza", "%", 0, "% de altura (+ la punta por encima de su cabeza)",
            "Copia la altura de la punta en el armado: si ella la tiene a la altura de la cabeza o por encima, la tuya igual.",
            "Punta muy por encima y mano alta: armado largo que llega tarde; punta caída desde el principio: no hay bucle.",
            "Sombras parando en el armado frente a un espejo lateral: la punta a la altura que marca su valor.",
            ["Bucle de la preparación (forma)"]),
         cp("loaded.racket_head_lateral", "Raqueta al lado del cuerpo o hacia la espalda", "%", 0, "% de altura respecto al hombro (+ al lado, − hacia la espalda)",
            "Mira si ella deja la raqueta al lado del cuerpo o la lleva hacia la espalda y copia su plano.",
            "Llevar la raqueta muy detrás de la espalda sin control: llegas tarde.",
            "Sombras frente a una pared lateral: la cabeza de la raqueta no debe tocarla.", []),
         cp("loaded.face_tilt", "Cuerdas al final del armado", "°", 0, "° de cierre de la cara (+ cuerdas hacia el suelo, − hacia el cielo)",
            "Lleva la cara de la raqueta como ella al final del armado (cerrada = mirando al suelo).",
            "Cara abierta hacia el cielo en el armado: tienes que corregirla en el swing y llegas tarde.",
            "Sombras parando en el armado: comprueba en un espejo hacia dónde miran las cuerdas.",
            ["Cara de la raqueta en la caída y en el impacto"]),
         cp("stroke.loaded_vs_bounce", "Armado completo respecto al bote", "s", 2, "s (≈ 0 = armada justo cuando bota la bola)",
            "Ten el armado completo cuando la bola bota.", "Seguir armando después del bote: prisa al final.",
            "Peloteo: di «bote» y comprueba que la raqueta ya está arriba y atrás.", ["Adaptación a bola rápida, corta, alta, abierta"]),
         cp("class.stance_loaded", "Apoyo al armar", "", 0, "abierto / semiabierto / neutro / cerrado",
            "Coloca el pie de atrás y carga el peso en él al armar.", "Armar con el peso en los talones.",
            "Sombras: armar, notar el peso en la pierna de atrás 1 s, golpear.", ["Apoyos abierto, semiabierto, neutro, cerrado"]),
         cp("practice.back_knee_loaded_deg", "Rodilla de atrás en la carga (vista lateral, entreno)", "°", 0, "° de la rodilla (180 = recta; 110-130 = carga profunda)",
            "Flexiona la rodilla de atrás como ella al armar.", "Armar con la pierna de atrás recta.",
            "Sombras con una silla detrás: rozarla con los glúteos al armar.",
            ["Rodilla de atrás en la carga (110–130°) y de delante en el impacto"]),
         cp("loaded.base_court_m", "Base al armar", "m", 2, "m entre los pies sobre la pista",
            "Abre la base como ella al armar: los pies a esa distancia te dan apoyo para girar y empujar.",
            "Pies juntos al armar: no hay base para empujar ni para girar.",
            "Marca su distancia con dos conos y arma con un pie en cada uno; 3×8 sombras.", ["Carga: flexión de rodillas"]),
         cp("loaded.hip_height", "Carga de piernas", "%", 0, "altura de la cadera, % de su altura (más bajo = más carga)",
            "Baja la cadera al armar: flexiona las rodillas para empujar después.", "Golpear con las piernas rectas.",
            "Sentadilla de un cuarto en el armado y empuje hacia arriba al golpear; 3×10.",
            ["Carga: flexión de rodillas", "Empuje de piernas / extensión triple (tobillo, rodilla, cadera)"]),
     ]},
    {"id": "acceleration", "title": "4 · Caída de la raqueta e inicio de la aceleración", "when": "La raqueta cae detrás y por debajo antes de ir hacia delante; empieza a girar la cadera.",
     "checkpoints": [
         cp("stroke.wrist_drop", "Caída de la mano", "%", 0, "% de altura que baja la mano antes de acelerar",
            "Deja caer la raqueta por debajo de la altura a la que vas a golpear.", "Ir directo desde arriba: golpe plano hacia abajo.",
            "Golpea desde una caja: empieza con la raqueta por debajo de la bola y sube.",
            ["Caída de la raqueta por debajo de la mano", "Caída de la raqueta por debajo de la bola", "Fuerza en dirección incorrecta (horizontal o descendente)"]),
         cp("stroke.shoulders_open_first", "Abre primero la cadera", "s", 2, "s (+ = los hombros se abren antes que la cadera: apertura prematura)",
            "Empieza a girar la cadera y deja que los hombros la sigan.", "Abrir los hombros primero: pierdes la torsión (fuga de energía).",
            "Sombras: gira solo la cadera hacia la red manteniendo los hombros de lado 0,5 s; luego suelta.",
            ["Apertura prematura de hombros (fuga de energía)", "Separación cadera–hombro (torque)", "Rotación pélvica"]),
         cp("stroke.weight_shift", "Transferencia de peso", "", 2, "cambio del peso entre los pies del armado al impacto (+ hacia el pie no dominante, el de delante en la derecha)",
            "Pasa el peso del pie de atrás al de delante mientras golpeas, como ella.",
            "Golpear con el peso atrás (cayendo hacia atrás): la bola sale sin peso.",
            "Sombras: armar con el peso atrás 1 s y golpear terminando apoyado en el pie de delante; 3×8.",
            ["Equilibrio al terminar"]),
         cp("stroke.acceleration_vs_bounce", "Empieza a acelerar respecto al bote", "s", 2, "s después del bote (ritmo con la bola: cae la raqueta mientras sube la bola)",
            "Deja caer la raqueta y empieza a acelerar cuando la bola sube tras botar, como ella.",
            "Acelerar antes del bote (llegas pronto y frenas) o muy tarde (golpe apurado).",
            "Peloteo diciendo «bote» y «ya»: «ya» es cuando empiezas a acelerar; ajusta el intervalo al suyo.",
            ["Adaptación a bola rápida, corta, alta, abierta"]),
         cp("stroke.hip_drop_cm", "Cuánto baja (espera → punto más bajo)", "cm", 0, "cm que baja la cadera desde la espera hasta su punto más bajo antes de golpear",
            "Baja la cadera tanto como ella antes de golpear: flexiona rodillas y cadera, no te agaches con la espalda.",
            "No bajar (piernas rectas) o bajar doblando la espalda.",
            "Frente a un espejo con una marca a la altura de tu cadera en la espera: baja hasta su medida y sube al golpear.",
            ["Carga: flexión de rodillas", "Empuje de piernas / extensión triple (tobillo, rodilla, cadera)"]),
         cp("stroke.hip_rise", "Empuje de piernas", "%", 1, "% de altura que sube la cadera hasta el impacto",
            "Empuja contra el suelo y sube la cadera mientras golpeas.", "Quedarse abajo: el golpe sale solo de brazo.",
            "Golpe desde rodillas flexionadas terminando de puntillas; 3×10.",
            ["Empuje de piernas / extensión triple (tobillo, rodilla, cadera)", "Reacción al suelo (fuerza contra la pista)"]),
         cp("acceleration.face_tilt", "Cuerdas en la caída", "°", 0, "° de cierre al empezar a acelerar (+ hacia el suelo)",
            "En la caída, cuerdas algo cerradas hacia el suelo, como ella.", "Abrir la cara al bajar la raqueta: la bola sale alta y sin efecto.",
            "Sombras lentas: para en la caída y mira las cuerdas.", ["Cara de la raqueta en la caída y en el impacto"]),
         cp("stroke.swing_low_to_high", "Trayectoria de abajo arriba", "°", 0, "° de subida de la mano en los 100 ms previos al impacto (2D desde detrás)",
            "Sube la raqueta de abajo arriba a través de la bola (de +10° a +45° según el efecto).",
            "Swing horizontal o descendente: la bola se va a la red o sin efecto.",
            "Golpes por encima de una cuerda colocada 1 m sobre la red.",
            ["Trayectoria vertical del swing (de abajo arriba)", "Golpe plano, liftado o cortado", "Fuerza en dirección incorrecta (horizontal o descendente)"]),
         cp("practice.swing_angle_deg", "Ángulo real del swing (vista lateral, entreno)", "°", 0, "° medidos de lado en sus entrenamientos",
            "Busca ese mismo ángulo de subida en tus golpes.", "Swing plano por miedo a mandar la bola larga.",
            "Grábate de lado y compara el ángulo de subida de la mano en los últimos 0,1 s.",
            ["Ángulo real del swing de abajo arriba (+10° a +45°)"]),
         cp("stroke.racket_lag_deg", "Máximo retraso de la raqueta (lag)", "°", 0, "° más pequeño entre antebrazo y raqueta del armado al impacto (menos = más retraso)",
            "Deja que la raqueta se quede atrás mientras el brazo empieza a ir hacia delante, como ella: la muñeca relajada la retrasa sola.",
            "Muñeca rígida: la raqueta va a la vez que el brazo y no hay latigazo («casting» cuando se suelta pronto).",
            "Sombras lentas con la muñeca suelta: nota cómo la cabeza de la raqueta se queda atrás al empezar el swing.",
            ["Retraso de la muñeca (lag) y su liberación", "Liberación anticipada de la muñeca («casting»)"]),
         cp("acceleration.racket_forearm", "Retraso de la raqueta (lag)", "°", 0, "° entre antebrazo y raqueta (menos = más retraso)",
            "Deja que la raqueta se quede atrás de la mano al acelerar, con la muñeca relajada.",
            "Lanzar la raqueta con la muñeca desde atrás (casting).", "Golpes a media pista con la muñeca relajada, sintiendo que la mano tira de la raqueta.",
            ["Retraso de la muñeca (lag) y su liberación", "Liberación anticipada de la muñeca («casting»)"]),
     ]},
    {"id": "impact", "title": "5 · Impacto", "when": "El contacto (sonido y bola).",
     "checkpoints": [
         cp("stroke.shoulder_brake", "Frenado de los hombros antes del contacto", "%", 0, "% que ha bajado la velocidad de giro de los hombros en el contacto (100 = parados)",
            "Gira el tronco fuerte y deja que se frene justo antes del contacto: esa energía pasa al brazo y a la raqueta.",
            "Seguir girando el tronco a tope en el contacto (todo es giro, el brazo va detrás) o frenar demasiado pronto.",
            "Sombras con la raqueta: gira y detén el pecho mirando a la red mientras el brazo sigue hacia delante; 3×8.", []),
         cp("impact.wrist_dom_vs_hip", "Altura del impacto", "%", 0, "% de altura respecto a la cadera (+ por encima)",
            "Golpea entre la cintura y el pecho; muévete para que la bola llegue ahí.", "Dejar que la bola te coma (demasiado alta) o golpear agachado sin flexionar.",
            "Peloteo marcando con conos dónde tienes que estar para que la bola llegue a la cintura.",
            ["Zona de impacto: altura y separación lateral"]),
         cp("impact.wrist_dom_lateral", "Separación lateral del cuerpo", "%", 0, "% de altura de la mano a la cadera",
            "Deja un brazo y medio de distancia entre el cuerpo y la bola.", "Golpear pegado al cuerpo: el brazo se encoge.",
            "Pon una raqueta en el suelo marcando la distancia y golpea sin pisarla.", ["Zona de impacto: altura y separación lateral"]),
         cp("impact.base_court_m", "Base en el impacto", "m", 2, "m entre los pies sobre la pista al golpear",
            "Golpea con los pies a la distancia a la que los tiene ella: base estable, ni junta ni exagerada.",
            "Golpear con los pies juntos o con un pie en el aire sin necesidad: pierdes equilibrio y precisión.",
            "Peloteo con dos marcas en el suelo a su distancia; golpea con un pie en cada una.", ["Equilibrio al terminar"]),
         cp("stroke.feet_move_m", "Pies quietos al golpear", "m", 2, "m que más se mueve un pie del armado al impacto (0 = plantados)",
            "Fija los pies como ella del armado al impacto (si ella da un paso hacia la bola, dalo tú también).",
            "Seguir moviendo los pies mientras golpeas: el golpe sale sin base.",
            "Sombras: arma, quédate plantado y golpea; luego con un paso hacia la bola.", ["Equilibrio al terminar"]),
         cp("impact.elbow_dom", "Codo en el impacto", "°", 0, "° (180 = brazo recto; < 135 = doble flexión)",
            "Copia su brazo: mira si golpea con el brazo casi recto o con el codo flexionado y mantenlo igual en todos los golpes.",
            "Cambiar el brazo de un golpe a otro.", "Sombras parando en el impacto: comprueba el ángulo del codo en un espejo.",
            ["Extensión del codo", "Brazo recto o doble flexión"]),
         cp("stroke.head_motion_cm", "Cabeza quieta en el impacto", "cm", 1, "cm que se mueve la cabeza ±50 ms del contacto",
            "Mantén la cabeza quieta y mira el punto de impacto un instante después de golpear.",
            "Levantar la cabeza para ver adónde va la bola.", "Golpea y sigue mirando el punto de contacto hasta oír el bote en el otro campo.",
            ["Cabeza estable y eje vertical", "Mirada fija en el punto de impacto («quiet eye»)"]),
         cp("practice.contact_in_front_pct", "Impacto delante de la cadera (vista lateral, entreno)", "%", 0, "% de su altura por delante del centro de la cadera",
            "Golpea delante de la cadera de delante, nunca a la altura del cuerpo.", "Golpear tarde, con la bola a tu lado.",
            "Pon un cono delante del pie de delante y golpea la bola cuando pase a su altura.",
            ["Zona de impacto: delante de la cadera"]),
         cp("practice.trunk_lean_impact_deg", "Tronco hacia delante o atrás (vista lateral, entreno)", "°", 0, "° (+ hacia delante)",
            "Tronco erguido o algo hacia delante en el impacto.", "Echarse hacia atrás al golpear.",
            "Golpea terminando con el peso en el pie de delante.", ["Inclinación del tronco hacia delante o atrás en el impacto"]),
         cp("impact.trunk_tilt", "Inclinación del tronco", "°", 0, "° respecto a la vertical",
            "Tronco estable; inclínalo solo lo justo para subir la raqueta de abajo arriba.", "Doblarse hacia atrás o caerse hacia un lado.",
            "Sombras con una pica en la espalda: que no se separe de la columna.", ["Inclinación lateral del tronco"]),
         cp("impact.face_tilt", "Cara de la raqueta en el impacto", "°", 0, "° de cierre (estimación: la raqueta sale borrosa)",
            "Cara casi vertical, ligeramente cerrada.", "Cara abierta: la bola se va larga.",
            "Golpes lentos a media pista sintiendo la cara vertical en el contacto.", ["Cara de la raqueta en la caída y en el impacto"]),
         cp("class.ball_phase", "Bola subiendo, arriba o cayendo", "", 0, "en qué momento del bote golpea",
            "Si ella la toma subiendo, adelántate: no esperes a que la bola caiga.", "Retroceder siempre para esperar la bola.",
            "Golpes desde la línea de fondo sin retroceder, tomando la bola tras el bote.",
            ["Adaptación a bola rápida, corta, alta, abierta"]),
     ]},
    {"id": "extension", "title": "6 · Extensión tras el impacto", "when": "≈ 50 ms después del contacto: el brazo sigue hacia el objetivo.",
     "checkpoints": [
         cp("extension.arm_extension", "Extensión del brazo", "%", 0, "% del brazo extendido hacia delante",
            "Sigue empujando la raqueta hacia el objetivo después del contacto.", "Cortar el golpe en el impacto.",
            "Golpea y deja la raqueta apuntando al objetivo un segundo antes de terminar.", ["Extensión del codo"]),
         cp("extension.wrist_non_lateral", "Brazo libre recogido (catch)", "%", 0, "% de altura de la mano libre respecto a la cadera",
            "Recoge el brazo libre hacia el pecho mientras giras: frena el lado izquierdo y acelera la raqueta.",
            "Dejar el brazo libre suelto atrás o abajo.", "Sombras: al golpear, la mano libre «atrapa» la raqueta a la altura del pecho al terminar.",
            ["Brazo libre recogido al pecho tras el contacto («catch»)"]),
     ]},
    {"id": "finish", "title": "7 · Terminación", "when": "La mano en su punto más alto.",
     "checkpoints": [
         cp("class.finish", "Tipo de terminación", "", 0, "sobre el hombro / limpiaparabrisas / látigo / alrededor del cuerpo",
            "Termina como ella en esa situación (en paralelos y bolas rápidas suele ser más corta).",
            "Terminar siempre igual sea cual sea la bola.", "Sombras de las tres terminaciones; luego peloteo cambiándolas a la voz del compañero.",
            ["Terminación sobre el hombro contrario", "Terminación en látigo sobre el mismo hombro (buggy whip)", "Terminación baja, a la cintura contraria"]),
         cp("finish.face_tilt", "Cuerdas al terminar", "°", 0, "° de cierre al final (+ hacia el suelo)",
            "Termina con la cara de la raqueta como ella (la cara gira y se cierra tras el contacto).",
            "Bloquear la muñeca y terminar con la cara abierta.", "Sombras: al terminar, mira dónde quedan las cuerdas.", []),
         cp("class.finish_trunk", "Hacia dónde mira el tronco al terminar", "", 0, "de frente a la red / girado hacia el lado del revés / mirando a la valla",
            "Termina con el tronco girado como ella en ese tipo de golpe (los cruzados y los golpes con más efecto suelen girar más).",
            "Dejar el tronco de lado al terminar (el brazo golpea solo) o pasarse del giro y perder el equilibrio.",
            "Sombras: termina y mira hacia dónde apunta tu pecho; compara con el suyo en el vídeo.",
            ["Terminación sobre el hombro contrario"]),
         cp("stroke.hip_rise_after_cm", "Cuánto sube tras golpear (punto más bajo → más alto)", "cm", 0, "cm que sube la cadera desde su punto más bajo hasta el más alto tras el impacto",
            "Empuja contra el suelo y sube como ella al golpear y terminar.",
            "Quedarse abajo al terminar: el golpe sale solo de brazo.",
            "Golpe desde la carga terminando de puntillas; mide con la marca del espejo cuánto subes.",
            ["Empuje de piernas / extensión triple (tobillo, rodilla, cadera)"]),
         cp("finish.base_court_m", "Base al terminar (en la pista)", "m", 2, "m entre los pies al terminar",
            "Termina con la base que tiene ella: estable para recuperar enseguida.", "Terminar con los pies juntos o desequilibrado.",
            "Golpea y quédate 2 s en la terminación con los pies marcados.", ["Equilibrio al terminar"]),
         cp("finish.head_over_base", "Equilibrio al terminar", "%", 0, "cabeza respecto al centro de los pies, % de altura",
            "Termina con la cabeza encima de los pies, sin caerte.", "Caerte hacia atrás o hacia un lado al terminar.",
            "Golpea y quédate quieto en la terminación 2 s; si te mueves, repite.", ["Equilibrio al terminar"]),
         cp("finish.base_width", "Base al terminar", "%", 0, "% de su altura entre tobillos al final",
            "Termina con los pies tan separados como ella: la base ancha sostiene el giro.",
            "Juntar los pies al terminar: pierdes el equilibrio y llegas tarde a la siguiente bola.",
            "Golpea y quédate en la terminación con los pies marcados en el suelo; compara con su anchura.", ["Equilibrio al terminar"]),
     ]},
    {"id": "recovery", "title": "8 · Recuperación", "when": "Primer paso de vuelta tras el golpe.",
     "checkpoints": [
         cp("footwork.recovery_start_s", "Cuándo empieza a recuperar", "s", 2, "s desde el impacto hasta el primer paso de vuelta",
            "Empieza a volver en cuanto terminas el golpe.", "Quedarte mirando la bola.",
            "Golpe + recuperación al centro con pasos laterales antes de que el compañero golpee.", ["Pasos de recuperación (laterales o cruzados)"]),
         cp("class.recovery_first_step", "Primer paso de vuelta", "", 0, "lateral / cruzado / hacia delante…",
            "Si estás lejos del centro, primer paso cruzado; si estás cerca, pasos laterales.", "Volver de espaldas o andando.",
            "Desde una esquina: un cruce y dos laterales hasta el centro; 10 repeticiones.", ["Pasos de recuperación (laterales o cruzados)"]),
         cp("footwork.rear_leg_step_after", "La pierna de atrás pasa adelante", "", 0, "en qué % de golpes",
            "Deja que la pierna de atrás pase adelante tras el impacto: es el giro completo del cuerpo.", "Clavar los pies y frenar el giro.",
            "Sombras dejando que la pierna de atrás termine delante.", []),
     ]},
]

FEET = {"id": "feet", "title": "Pies: del split step al golpe", "when": "Todo el desplazamiento hacia la bola.",
        "checkpoints": [
         cp("footwork.crossover_steps", "Pasos cruzados", "", 0, "pasos cruzados en el golpe (hacia la bola y de vuelta)",
            "Cuando la bola te saca de sitio, cruza como ella: el pie de fuera pasa por delante y cubres más pista en menos pasos.",
            "Ir siempre con pasos laterales cortos a una bola lejana: llegas tarde.",
            "Desplazamientos de banda a banda: 2 pasos cruzados, apoyo y golpe en sombra; 3×6.",
            ["Pasos cruzados", "Pasos de recuperación (laterales o cruzados)"]),
            cp("footwork.first_step_s", "Primer paso tras el split step", "s", 2, "s desde el aterrizaje", "Primer paso explosivo hacia la bola nada más aterrizar.",
               "Dar un paso atrás antes de salir.", "Split step y primer paso a la orden de un compañero que señala un lado; 10 por lado.", ["Split step"]),
            cp("class.approach_main", "Tipo de pasos hacia la bola", "", 0, "cruzados / laterales / de carrera",
               "Lejos de la bola: pasos cruzados o de carrera; cerca: pasos laterales.", "Correr de frente y girar al final.",
               "Bolas alternas abiertas y cerradas; elige el paso según la distancia.", ["Pasos cruzados"]),
            cp("footwork.adjustment_steps", "Pasos de ajuste", "", 0, "pasos cortos en los últimos 0,8 s",
               "Pequeños pasos al final para colocarte a la distancia justa.", "Llegar con un paso largo y golpear desequilibrado.",
               "Escalera de agilidad y después golpe; o pasos cortos alrededor de un cono antes de cada derecha.", ["Pasos de ajuste"]),
            cp("footwork.step_in", "Paso hacia dentro de la pista", "", 0, "en qué % de golpes da el paso de ataque",
               "En bolas cortas o lentas, entra en la pista con el pie de delante al golpear.", "Golpear las bolas cortas desde atrás.",
               "Bola corta: paso adelante con el pie no dominante y golpe; 3×8.", ["Paso de ataque hacia dentro de la pista (step-in)"]),
            cp("footwork.braking_step", "Paso de frenado", "", 0, "en qué % de golpes frena con un último paso largo",
               "En carrera, un último paso largo frena el cuerpo antes de golpear.", "Golpear corriendo sin frenar.",
               "Carrera lateral y frenado en un cono antes de golpear.", ["Apoyo abierto extremo defensivo"]),
            cp("footwork.drag_foot", "Pie de atrás que se arrastra", "", 0, "en qué % de golpes",
               "En bolas abiertas, deja que el pie de atrás se arrastre para mantener el equilibrio.", "Levantar el pie de atrás y perder el equilibrio.",
               "Bolas abiertas en carrera dejando que la puntera del pie de atrás roce el suelo.", ["Pie de arrastre (pie trasero que se arrastra)"]),
            cp("class.stance_impact", "Apoyo en el impacto", "", 0, "abierto / semiabierto / neutro / cerrado",
               "Usa el apoyo que ella usa en esa situación (ver condición elegida).", "Usar siempre el mismo apoyo.",
               "Peloteo cambiando de apoyo a la voz del compañero.", ["Apoyos abierto, semiabierto, neutro, cerrado", "Apoyo en suspensión (salto)"]),
            cp("footwork.path_m", "Recorrido hasta la bola", "m", 1, "metros desde el golpe de la rival", "Muévete pronto: cuanto antes salgas, menos corres al final.",
               "Salir tarde y llegar corriendo.", "Bolas a 3-4 m del centro: llega parado antes del bote.", []),
        ]}

# conditions the user combines (a stroke class each) with what changes and how to train it
CONDITIONS = {
    "shot_type": ("Dirección", {
        "cruzada": ("Cruzada: la más segura (más pista y la red más baja en el centro).", "Golpea la bola un poco antes del lado de tu cuerpo y termina hacia la esquina cruzada.", "Peloteo cruzado a una zona marcada; 20 seguidas."),
        "paralela": ("Paralela: menos pista y la red más alta; exige adelantar el punto de impacto y cerrar antes la cara.", "Golpea un poco más tarde que en la cruzada respecto a tu cuerpo, con la cara hacia la línea y el apoyo más cerrado.", "Desde la esquina, 10 paralelas a un cono en la línea; luego alternando cruzada y paralela."),
        "al centro": ("Al centro: margen y profundidad para neutralizar.", "Golpe largo con margen sobre la red.", "Peloteo apuntando a la zona entre las líneas de servicio y fondo."),
        "invertida cruzada": ("Dentro-fuera: rodea la bola desde el lado del revés hacia la esquina cruzada de la rival.", "Rodea la bola con pasos laterales y abre la cadera hacia la esquina.", "Bolas al revés: rodea y golpea dentro-fuera; 3×8."),
        "invertida paralela": ("Dentro-dentro: desde el lado del revés hacia la línea paralela.", "Rodea la bola y golpea más tarde, con la cara hacia la línea.", "Bolas al revés alternando dentro-fuera y dentro-dentro."),
        "invertida al centro": ("Invertida al centro.", "Rodea la bola y busca profundidad.", "Bolas al revés al centro de la pista."),
    }),
    "stance_impact": ("Apoyo", {
        "abierto": ("Abierto: pies paralelos a la red; reacción rápida y mucho giro de cadera.", "Carga en la pierna de fuera y gira la cadera; útil en bolas rápidas y abiertas.", "Bolas abiertas golpeando con apoyo abierto y recuperación inmediata."),
        "semiabierto": ("Semiabierto: el equilibrio entre estabilidad y giro.", "Pie de fuera algo retrasado (45°), peso al de fuera y giro.", "Peloteo en semiabierto 20 bolas."),
        "neutro": ("Neutro: pie de delante hacia la red; transfiere el peso hacia delante.", "Da un paso con el pie no dominante hacia la bola.", "Bolas medias golpeando con paso adelante."),
        "cerrado": ("Cerrado: pie de delante cruzado; avanza el peso y da estabilidad a golpes planos y paralelos.", "Paso con el pie no dominante cruzando hacia la línea, peso hacia delante, tronco de lado más tiempo.", "Bolas paradas con apoyo cerrado a la línea paralela; 3×8."),
    }),
    "movement": ("Cómo llega", {
        "parada": ("Parada: tiempo para colocarse; el golpe más clásico.", "Llega antes y ajusta con pasos cortos; golpe completo.", "Bolas a la mano con colocación previa."),
        "en movimiento": ("En movimiento: ajusta mientras llega.", "Gira mientras te mueves; último paso de apoyo firme.", "Bolas a 2 m golpeando en movimiento."),
        "en carrera": ("En carrera: prioridad a llegar y frenar.", "Frena con el último paso y termina en látigo si vas justa.", "Bolas abiertas en carrera y recuperación."),
        "deslizando": ("Deslizando (tierra/hierba).", "Desliza sobre el pie de fuera mientras golpeas.", "Deslizamientos controlados en tierra."),
        "en el aire": ("En el aire: ataque a bolas altas o cortas.", "Salta desde el pie de atrás y golpea en el aire.", "Bolas altas golpeando con salto."),
    }),
    "swing": ("Efecto", {
        "plano": ("Plano: trayectoria recta, poco efecto; potencia.", "Swing más horizontal, contacto más adelantado.", "Golpes planos a una diana baja junto a la red."),
        "liftado (de abajo arriba)": ("Liftado: de abajo arriba; margen sobre la red y bote alto.", "Raqueta por debajo de la bola y subida marcada (+20° a +45°).", "Golpes por encima de una cuerda a 1 m sobre la red."),
        "cortado (de arriba abajo)": ("Cortado / defensivo: ganar tiempo o neutralizar.", "Cara algo abierta, swing de arriba abajo, corto.", "Bolas abiertas en carrera respondiendo con cortado profundo."),
    }),
    "court_side": ("Lado de la pista", {
        "lado de su derecha": ("Desde su lado derecho de la pista.", "Lo natural: derecha con el cuerpo de lado al lateral.", "Bolas a la zona derecha."),
        "centro": ("Desde el centro.", "Elige dirección con la cadera.", "Bolas al centro."),
        "lado de su revés": ("Desde el lado del revés (rodeando la bola).", "Rodea la bola con pasos laterales; derecha invertida.", "Bolas al revés para rodear."),
    }),
    "ball_height": ("Altura de la bola", {
        "rodilla": ("Bola baja (rodilla).", "Flexiona mucho las piernas, no te agaches con la espalda.", "Bolas bajas cortas golpeando con las rodillas flexionadas."),
        "cadera": ("A la cadera.", "Algo de flexión; swing de abajo arriba.", "Bolas a media altura."),
        "cintura-pecho": ("Cintura–pecho: la zona ideal.", "Colócate para que la bola llegue aquí.", "Peloteo buscando esta altura."),
        "pecho-hombro": ("Alta (pecho-hombro).", "Adelántate y tómala subiendo o retrocede para que baje.", "Bolas con mucho efecto alto."),
        "por encima del hombro": ("Muy alta.", "Tómala subiendo o salta; terminación alta.", "Bolas altas con salto."),
    }),
    "ball_speed": ("Velocidad de la bola", {
        "lenta": ("Bola lenta: tienes que generar tú la potencia.", "Preparación completa, paso adelante y empuje de piernas.", "Bolas lentas atacando hacia dentro."),
        "media": ("Bola media.", "Golpe completo.", "Peloteo a ritmo medio."),
        "rápida": ("Bola rápida: prepara antes y acorta el armado.", "Giro temprano, armado compacto, usa la velocidad de la rival.", "Bolas rápidas desde cerca de la red del compañero."),
        "muy rápida": ("Bola muy rápida: casi un bloqueo.", "Giro de hombros mínimo y cara firme.", "Bolas muy rápidas bloqueando al centro."),
    }),
    "depth": ("Dónde golpea", {
        "dentro de la pista": ("Dentro de la pista: ataque.", "Paso hacia delante y golpe al subir.", "Bolas cortas atacando."),
        "sobre la línea": ("Sobre la línea de fondo.", "Posición estándar; tómala tras el bote sin retroceder.", "Peloteo sobre la línea."),
        "1-2 m detrás": ("1-2 m detrás de la línea.", "Más tiempo; golpe con más efecto para dar profundidad.", "Peloteo desde detrás."),
        "2-4 m detrás": ("Muy atrás: defensa.", "Más altura sobre la red para devolver profundo.", "Bolas profundas devolviendo alto."),
        "muy atrás": ("Muy lejos: defensa extrema.", "Bola alta y profunda para recuperar.", "Defensa desde el fondo."),
    }),
    "contact_type": ("Contacto", {
        "tras el bote": ("Tras el bote: la derecha normal.", "", ""),
        "media volea": ("Media volea (botepronto): justo al bote, muy baja.", "Flexiona mucho, armado muy corto y cara estable.", "Bolas a los pies golpeando al bote."),
        "volea": ("Volea de derecha: sin bote, junto a la red.", "Armado mínimo, muñeca firme y paso adelante.", "Voleas de derecha con paso adelante."),
    }),
}
RELAX_ORDER = ["depth", "ball_speed", "ball_height", "court_side", "contact_type", "swing", "movement", "stance_impact", "shot_type"]

# items of the user's matrix that TV cannot measure, with what to do about them anyway
NOT_FROM_TV = [
    ("Reacción al suelo, tasa de desarrollo de fuerza", "Se nota en el empuje de piernas (fase 4, medido)."),
    ("Pronación del antebrazo, flexión palmar, desviación de la muñeca", "Deja la muñeca relajada; la pronación sale sola tras el contacto si el brazo está suelto."),
    ("Mirada fija en el impacto (quiet eye)", "Ver «Cabeza quieta en el impacto» (fase 5)."),
    ("Estabilidad lumbopélvica, activación de oblicuos, electromiografía", "Trabajo de core fuera de pista; en el golpe, «abre primero la cadera» (fase 4)."),
    ("Trayectoria de dentro a fuera (horizontal)", "Ver la dirección «invertida cruzada» (dentro-fuera)."),
    ("Relajación y tensión de la empuñadura", "Agarre suave (3 de 10) en la preparación y firme solo en el contacto."),
    ("Propiedades de la raqueta (swingweight, rigidez, encordado, tensión)", "Fuera del vídeo; elige una raqueta que puedas acelerar sin forzar el brazo."),
    ("Velocidad de la cabeza en km/h, velocidad angular en °/s, efecto en rpm, velocidad de salida", "Solo comparaciones entre sus golpes (velocidad relativa de la raqueta)."),
    ("Rangos articulares y cargas del codo", "Si te duele el codo, revisa el agarre y no golpees tarde."),
    ("Aerodinámica, altitud, temperatura, humedad", "En altitud o con calor la bola vuela más: más efecto."),
]


def learn_keys() -> list[str]:
    return [c["key"] for ph in PHASES + [FEET] for c in ph["checkpoints"]]


def content() -> dict:
    """Everything static the «Aprende su derecha» screen needs."""
    return {"phases": PHASES + [FEET], "conditions": {k: {"name": n, "levels": lv} for k, (n, lv) in CONDITIONS.items()},
            "relax": RELAX_ORDER, "not_tv": NOT_FROM_TV, "source": SOURCE}


def covered_matrix_items() -> set[str]:
    return {it for ph in PHASES + [FEET] for c in ph["checkpoints"] for it in c["covers"]}


# items of the user's matrix answered by a situation the user chooses (section 1 of the screen) or by
# the match itself, and those answered in «lo que la tele no permite medir»
BY_CONDITION = {"Adaptación a bola rápida, corta, alta, abierta": "ball_speed", "Dirección: cruzado, paralelo, dentro-fuera, dentro-dentro": "shot_type",
                "Golpe plano, liftado o cortado": "swing", "Botepronto (media volea)": "contact_type", "Volea de derecha": "contact_type",
                "Apoyo en suspensión (salto)": "movement", "Superficie de la pista": "surface"}


def matrix_places(rows: list[dict]) -> dict:
    """element of the user's matrix → where «Aprende su derecha» answers it (None = nowhere)."""
    cov = {}
    for ph in PHASES + [FEET]:
        for c in ph["checkpoints"]:
            for it in c["covers"]:
                cov.setdefault(it, []).append(f"{ph['title']} › {c['label']}")
    cov = {k: "; ".join(v) for k, v in cov.items()}
    nm = " ".join(w for w, _ in NOT_FROM_TV).lower()
    out = {}
    for r in rows:
        e = r["element"]
        if e in cov:
            out[e] = cov[e]
        elif e in BY_CONDITION:
            out[e] = f"Condición «{CONDITIONS[BY_CONDITION[e]][0]}»" if BY_CONDITION[e] in CONDITIONS else "Superficie de sus partidos (sección 1)"
        elif r["status"] == "✘" and any(w in nm for w in e.lower().replace(",", " ").split() if len(w) > 6):
            out[e] = "Lo que la tele no permite medir"
        else:
            out[e] = None
    return out
