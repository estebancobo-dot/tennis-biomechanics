"""From the model to plain language: what she does at each moment, how sure it is, and what
changes in each situation. Every sentence is a template filled with her measured values (median
and usual range); a sentence whose numbers are missing is simply not written.
"""
import math

from .model import FACTORS, MIN_N

PHASE_TITLES = {"ready": "Espera", "takeback": "Preparación", "loaded": "Armado", "acceleration": "Aceleración",
                "impact": "Impacto", "extension": "Extensión", "finish": "Terminación", "recovery": "Recuperación"}
PHASE_TITLES_OVERHEAD = {"takeback": "Lanzamiento", "loaded": "Trofeo", "acceleration": "Caída de la raqueta",
                         "recovery": "Aterrizaje"}


def fmt(v, d=0):
    if v is None or not math.isfinite(v):
        return "—"
    v = round(v, d) + 0.0                     # no "-0"
    return f"{v:,.{d}f}".replace(",", " ").replace(".", ",").replace(" ", ".")


def _rng(t, d=0, unit=""):
    return f"{fmt(t['p25'], d)} a {fmt(t['p75'], d)}{unit}"


def _t(model, key):
    return model["typical"].get(key)


# phase → list of (key, sentence builder(t) → text). Builders get the typical stats of the key.
def _lines():
    L = {}
    L["ready"] = [
        ("ready.body_height", lambda t: f"Espera agachada a un {fmt(t['median'])} % de su altura de pie (habitual {_rng(t)} %)."),
        ("ready.base_width", lambda t: f"Pies separados un {fmt(t['median'])} % de su altura ({_rng(t)} %)."),
        ("ready.hands_apart", lambda t: "Las dos manos en la raqueta." if t["median"] < 12 else
         f"La mano libre separada de la raqueta ({fmt(t['median'])} % de su altura)."),
        # knee angles seen from behind and above are foreshortened (legs look straight): not shown,
        # the leg load is told by the hip height instead
        ("ready.hip_height", lambda t: f"Cadera a un {fmt(t['median'])} % de su altura (rodillas flexionadas: {_rng(t)} %)."),
        ("ball_net.hip_height", lambda t: f"Cuando la bola cruza la red: cadera a un {fmt(t['median'])} % de su altura ({_rng(t)} %)."),
        ("ball_net.shoulder_turn", lambda t: f"Cuando la bola cruza la red: hombros ya girados {fmt(t['median'])}°."),
    ]
    L["takeback"] = [
        ("stroke.t_takeback", lambda t: f"Empieza a preparar {fmt(t['median'], 2)} s antes del impacto ({_rng(t, 2)} s)."),
        ("stroke.takeback_after_opp", lambda t: f"Arranca {fmt(t['median'], 2)} s después del golpe de la rival."),
        ("stroke.takeback_vs_bounce", lambda t: (f"Lo hace {fmt(abs(t['median']), 2)} s antes del bote." if t["median"] < 0 else
                                                 f"Lo hace {fmt(t['median'], 2)} s después del bote.")),
        ("stroke.loaded_vs_bounce", lambda t: (f"Termina de armar {fmt(-t['median'], 2)} s antes de que bote la bola." if t["median"] < 0 else
                                               f"Termina de armar {fmt(t['median'], 2)} s después del bote.")),
        ("stroke.takeback_vs_net", lambda t: (f"Empieza a preparar {fmt(abs(t['median']), 2)} s antes de que la bola cruce la red." if t["median"] < -0.03 else
                                              f"Empieza a preparar {fmt(t['median'], 2)} s después de que la bola cruce la red." if t["median"] > 0.03 else
                                              "Empieza a preparar justo cuando la bola cruza la red.")),
        ("ball_bounce.hip_height", lambda t: f"Cuando bota la bola: cadera a un {fmt(t['median'])} % de su altura."),
        ("takeback.hands_apart", lambda t: "Gira con la mano libre todavía en la raqueta (giro unitario)." if t["median"] < 15 else
         "La mano libre ya se ha separado de la raqueta."),
        ("takeback.shoulder_turn", lambda t: f"Hombros girados {fmt(t['median'])}° al empezar."),
    ]
    L["loaded"] = [
        ("loaded.shoulder_turn", lambda t: f"Hombros girados {fmt(t['median'])}° ({_rng(t)}°)."),
        ("loaded.hip_turn", lambda t: f"Cadera girada {fmt(t['median'])}°."),
        ("loaded.x_factor", lambda t: f"Separación hombros–cadera de {fmt(t['median'])}° ({_rng(t)}°)."),
        ("loaded.racket_head_vs_wrist", lambda t: (f"Raqueta por encima de la mano ({fmt(t['median'])} % de su altura)." if t["median"] > 2 else
                                                   f"Raqueta por debajo de la mano ({fmt(-t['median'])} %)." if t["median"] < -2 else
                                                   "Raqueta a la altura de la mano.")),
        ("loaded.wrist_dom_vs_shoulder", lambda t: (f"Mano a {fmt(abs(t['median']))} % de su altura {'por encima' if t['median'] > 0 else 'por debajo'} del hombro.")),
        ("loaded.shoulder_abd_non", lambda t: (f"Brazo libre levantado {fmt(t['median'])}° respecto al tronco, señalando la bola." if t["median"] > 60 else
                                               f"Brazo libre cerca del cuerpo ({fmt(t['median'])}°).")),
        ("loaded.elbow_non", lambda t: f"Brazo libre {'extendido' if t['median'] > 140 else 'flexionado'} ({fmt(t['median'])}°)."),
        ("loaded.hip_height", lambda t: f"Cadera a un {fmt(t['median'])} % de su altura (carga de piernas)."),
        ("loaded.com_over_feet", lambda t: ("Peso sobre el pie de atrás (el de su brazo)." if t["median"] < 0.4 else
                                            "Peso sobre el pie adelantado." if t["median"] > 0.6 else "Peso repartido entre los dos pies.")),
        ("loaded.face_tilt", lambda t: f"Cara de la raqueta {'cerrada' if t['median'] >= 0 else 'abierta'} {fmt(abs(t['median']))}°."),
        ("stroke.pause_at_loaded", lambda t: f"Pausa en el armado: {fmt(t['median'], 2)} s."),
        ("stroke.loaded_vs_top", lambda t: (f"Termina de armar {fmt(abs(t['median']), 2)} s antes de que la bola llegue a lo más alto del bote."
                                            if t["median"] < 0 else f"Termina de armar {fmt(t['median'], 2)} s después de lo más alto del bote.")),
    ]
    L["loaded"].append(("loaded.racket_forearm", lambda t: f"Al terminar de armar, ángulo antebrazo–raqueta de {fmt(t['median'])}° "
                                                       f"({_rng(t)}°): la muñeca ya va echada hacia atrás (retraso)."))
    L["loaded"] += [
        ("loaded.elbow_dom_vs_shoulder", lambda t: f"Codo {'por encima' if t['median'] > 2 else 'por debajo' if t['median'] < -2 else 'a la altura'} del hombro al armar "
                                                   f"({fmt(abs(t['median']))} % de su altura)."),
        ("loaded.elbow_dom_lateral", lambda t: f"Codo separado del cuerpo un {fmt(t['median'])} % de su altura al armar."
                                               if t["median"] > 6 else "Codo pegado al cuerpo al armar."),
        ("stroke.takeback_vs_first_step", lambda t: (f"Gira los hombros {fmt(abs(t['median']), 2)} s antes de dar el primer paso: gira mientras se mueve."
                                                     if t["median"] < -0.05 else f"Gira después de empezar a moverse ({fmt(t['median'], 2)} s).")),
    ]
    L["acceleration"] = [
        ("stroke.t_acceleration", lambda t: f"Empieza a acelerar {fmt(t['median'], 2)} s antes del impacto."),
        ("stroke.wrist_drop", lambda t: f"Antes deja caer la mano un {fmt(t['median'])} % de su altura ({_rng(t)} %)."),
        ("acceleration.racket_head_vs_wrist", lambda t: (f"La cabeza de la raqueta cae por debajo de la mano ({fmt(-t['median'])} %)." if t["median"] < -2 else
                                                         "La cabeza de la raqueta sigue a la altura de la mano o por encima.")),
        ("acceleration.racket_forearm", lambda t: f"Ángulo antebrazo–raqueta de {fmt(t['median'])}° (retraso de la muñeca)."),
        ("stroke.dur_forward", lambda t: f"Del armado al impacto tarda {fmt(t['median'], 2)} s ({_rng(t, 2)} s)."),
        ("stroke.shoulders_open_first", lambda t: ("La cadera abre antes que los hombros: mantiene la separación hasta el final." if t["median"] < -0.02 else
                                                   "Los hombros empiezan a abrirse antes que la cadera (apertura prematura): pierde parte de la separación."
                                                   if t["median"] > 0.04 else "Cadera y hombros abren casi a la vez.")),
        ("stroke.acceleration_vs_bounce", lambda t: (f"Empieza a acelerar {fmt(t['median'], 2)} s después del bote." if t["median"] > 0.02 else
                                                     f"Empieza a acelerar {fmt(-t['median'], 2)} s antes del bote." if t["median"] < -0.02 else
                                                     "Empieza a acelerar justo cuando bota la bola.")),
        ("stroke.hip_rise", lambda t: f"Empuja con las piernas: la cadera sube un {fmt(t['median'])} % de su altura hasta el impacto." if t["median"] > 1.5
                            else "Golpea sin subir la cadera (sin empuje vertical de piernas)."),
        ("stroke.racket_speed_rel", lambda t: f"Velocidad de la raqueta: {fmt(t['median'], 1)} alturas por segundo ({_rng(t, 1)}); "
                                              "no es su velocidad real (sale borrosa), solo sirve para comparar sus golpes entre sí."),
    ]
    L["impact"] = [
        ("impact.wrist_dom_height", lambda t: f"Golpea con la mano a un {fmt(t['median'])} % de su altura ({_rng(t)} %)."),
        ("impact.wrist_dom_vs_hip", lambda t: (f"Contacto {fmt(abs(t['median']))} % de su altura {'por encima' if t['median'] > 0 else 'por debajo'} de la cadera.")),
        ("impact.wrist_dom_lateral", lambda t: f"Separada del cuerpo: la mano a {fmt(t['median'])} % de su altura de la cadera."),
        ("impact.elbow_dom", lambda t: f"Codo a {fmt(t['median'])}° ({'brazo casi recto' if t['median'] >= 150 else 'brazo flexionado'})."),
        ("stroke.contact_vs_top", lambda t: (f"Toma la bola subiendo, {fmt(abs(t['median']), 2)} s antes de lo más alto del bote ({_rng(t, 2)} s)."
                                             if t["median"] < -0.05 else f"Toma la bola cayendo, {fmt(t['median'], 2)} s después de lo más alto del bote."
                                             if t["median"] > 0.05 else "Toma la bola en lo más alto del bote.")),
        ("stroke.contact_height_m", lambda t: f"La bola está a {fmt(t['median'], 2)} m del suelo en el contacto ({_rng(t, 2)} m)."),
        ("stroke.swing_low_to_high", lambda t: f"El swing sube hacia la bola: la mano va {fmt(t['median'])}° hacia arriba."),
        ("impact.trunk_tilt", lambda t: (f"Tronco inclinado {fmt(abs(t['median']))}° hacia su {'lado del brazo' if t['median'] > 0 else 'lado contrario'}."
                                         if abs(t["median"]) >= 4 else "Tronco vertical.")),
        ("impact.head_over_base", lambda t: ("Cabeza centrada sobre los pies." if abs(t["median"]) < 4 else
                                             f"Cabeza desplazada un {fmt(abs(t['median']))} % hacia su {'lado del brazo' if t['median'] > 0 else 'lado contrario'}.")),
        ("impact.body_height", lambda t: f"Cuerpo a un {fmt(t['median'])} % de su altura de pie."),
        ("impact.base_m", lambda t: f"Base de {fmt(t['median'], 2)} m ({_rng(t, 2)} m)."),
        ("stroke.weight_shift", lambda t: ("Pasa el peso hacia el pie de delante del armado al impacto." if t["median"] > 0.1 else
                                           "Se queda con el peso atrás en el impacto." if t["median"] < -0.1 else
                                           "Mantiene el peso repartido entre los pies del armado al impacto.")),
        ("impact.elbow_dom_vs_shoulder", lambda t: f"En el impacto el codo está {fmt(abs(t['median']))} % de su altura {'por encima' if t['median'] > 0 else 'por debajo'} del hombro."),
        ("stroke.hand_on_handle", lambda t: f"Agarra la raqueta con la mano a un {fmt(t['median'])} % de su longitud desde el final del mango "
                                            f"({_rng(t)} %; fiabilidad baja: la mano mide pocos píxeles)."),
    ]
    L["extension"] = [
        ("extension.wrist_non_lateral", lambda t: ("El brazo libre se recoge pegado al cuerpo tras el contacto («catch»)." if t["median"] > -12 else
                                                   f"El brazo libre queda separado del cuerpo tras el contacto ({fmt(-t['median'])} % de su altura).")),
        ("extension.arm_extension", lambda t: f"Brazo extendido al {fmt(t['median'])} % hacia delante tras el contacto."),
        ("stroke.swing_rise_after", lambda t: f"La mano sube un {fmt(t['median'])} % de su altura en los 150 ms siguientes."),
    ]
    L["finish"] = [
        ("stroke.t_finish", lambda t: f"Termina {fmt(t['median'], 2)} s después del impacto."),
        ("finish.wrist_dom_vs_shoulder", lambda t: f"Mano {'por encima' if t['median'] > 0 else 'por debajo'} del hombro ({fmt(abs(t['median']))} %)."),
        ("finish.wrist_dom_lateral", lambda t: f"Mano al {'lado contrario' if t['median'] < 0 else 'lado de su brazo'} del cuerpo."),
        ("finish.head_over_base", lambda t: ("Termina en equilibrio: la cabeza sobre los pies." if abs(t["median"]) < 6 else
                                             f"Termina con la cabeza desplazada {fmt(abs(t['median']))} % de su altura hacia su {'lado del brazo' if t['median'] > 0 else 'lado contrario'}.")),
        ("finish.trunk_tilt", lambda t: "Tronco vertical al terminar." if abs(t["median"]) < 8 else
                                        f"Tronco inclinado {fmt(abs(t['median']))}° al terminar."),
        ("finish.face_tilt", lambda t: f"Cara de la raqueta {'cerrada' if t['median'] >= 0 else 'abierta'} {fmt(abs(t['median']))}°."),
    ]
    L["recovery"] = [
        ("footwork.recovery_to_centre_m", lambda t: f"En el segundo siguiente vuelve {fmt(t['median'], 1)} m hacia el centro."),
    ]
    return L


LINES = _lines()
# feet and split step inside the phases where a coach looks at them
LINES["ready"].insert(0, ("footwork.split_landing_vs_opp_s", lambda t: (
    "Cae del split step justo cuando golpea la rival." if abs(t["median"]) <= 0.08 else
    f"Cae del split step {fmt(abs(t['median']), 2)} s {'después' if t['median'] > 0 else 'antes'} de que golpee la rival.")))
LINES["takeback"].append(("footwork.first_step_s", lambda t: f"Da el primer paso {fmt(t['median'], 2)} s después del split step ({_rng(t, 2)} s)."))
LINES["takeback"].append(("footwork.steps_to_impact", lambda t: f"Llega a la bola en {fmt(t['median'])} pasos."))
LINES["impact"].append(("stroke.head_motion_cm", lambda t: ("Su cabeza se queda quieta en el impacto" if t["median"] <= 3 else
                                                         "Su cabeza se mueve en el impacto") +
                        f" ({fmt(t['median'], 1)} cm en ±50 ms)."))
LINES["impact"].append(("stroke.head_still_after_cm", lambda t: ("Tras golpear, su cabeza sigue quieta sobre los hombros" if t["median"] <= 3 else
                                                               "Tras golpear, su cabeza se mueve sobre los hombros") +
                        f" ({fmt(t['median'], 1)} cm en 150 ms)."))


def _foot_dir(a: float) -> str:
    """How a coach says where the toes point (foot angle against the baseline, technique.DESCRIPTORS)."""
    return ("hacia atrás" if a < -10 else "paralelo a la línea de fondo, hacia el lado en que golpea" if a < 25 else
            "en diagonal hacia la red" if a < 65 else "hacia la red" if a < 115 else "cruzado hacia el otro lado")


LINES["loaded"].append(("loaded.back_foot_angle_deg", lambda t: f"Al armar, el pie de atrás apunta {_foot_dir(t['median'])} "
                                                                f"({fmt(t['median'])}° respecto a la línea de fondo; {_rng(t)}°)."))
LINES["impact"].append(("impact.front_foot_angle_deg", lambda t: f"En el impacto, el pie de delante apunta {_foot_dir(t['median'])} "
                                                                 f"({fmt(t['median'])}°; {_rng(t)}°)."))
LINES["impact"].append(("impact.back_foot_angle_deg", lambda t: f"En el impacto, el pie de atrás apunta {_foot_dir(t['median'])} "
                                                                f"({fmt(t['median'])}°; {_rng(t)}°)."))
LINES["impact"].append(("footwork.back_heel_lift_s", lambda t: (
    f"Levanta el talón de atrás y pivota sobre la punta {fmt(abs(t['median']), 2)} s "
    f"{'después' if t['median'] >= 0 else 'antes'} del impacto ({_rng(t, 2)} s).")))
LINES["recovery"].append(("footwork.off_centre_at_opp_hit_m", lambda t: f"Cuando la rival vuelve a golpear está a {fmt(t['median'], 1)} m del centro."))

# What each measurement means for the stroke, as a coach would say it, with where it comes from
# (the sources of docs/matriz_cobertura.md). Shown under every sentence of «Su derecha».
COACH = {
    "ready.body_height": ("Esperar con las rodillas flexionadas permite salir antes hacia la bola.", "Tennis Australia"),
    "ready.hip_height": ("Esperar con las rodillas flexionadas permite salir antes hacia la bola.", "Tennis Australia"),
    "ready.base_width": ("Los pies algo más separados que los hombros dan una base estable para el primer paso.", "Tennis Australia"),
    "ready.hands_apart": ("La mano libre en la raqueta ayuda a girar hombros y raqueta a la vez.", "Tennis Australia; ITF"),
    "class.ready_hands": ("La mano libre en la raqueta ayuda a girar hombros y raqueta a la vez.", "Tennis Australia; ITF"),
    "footwork.split_landing_vs_opp_s": ("Caer del split step cuando golpea la rival permite reaccionar antes a la dirección de la bola.", "Uzu 2009; Filipcic 2017"),
    "ball_net.hip_height": ("Dónde está su cuerpo cuando la bola cruza la red dice si va por delante o por detrás de la bola.", "Tennis Australia"),
    "ball_net.shoulder_turn": ("Haber girado ya los hombros cuando la bola cruza la red indica una preparación temprana.", "ITF (Crespo, Reid)"),
    "stroke.t_takeback": ("Preparar pronto da tiempo a armar del todo antes del bote.", "ITF (Crespo, Reid); Tennis Australia"),
    "stroke.takeback_after_opp": ("Cuanto antes arranca tras el golpe de la rival, más tiempo tiene para colocarse.", "ITF (Crespo, Reid)"),
    "stroke.takeback_vs_bounce": ("Empezar a preparar antes del bote es lo que piden los manuales de técnica.", "Tennis Australia"),
    "stroke.takeback_vs_net": ("Empezar a preparar con la bola en el aire, antes de que cruce la red, es preparación temprana.", "ITF (Crespo, Reid)"),
    "stroke.loaded_vs_bounce": ("Tennis Australia pide el armado completo cuando bota la bola.", "Tennis Australia 2013"),
    "stroke.loaded_vs_top": ("Armar antes de que la bola llegue a lo más alto deja el swing listo para tomarla subiendo.", "Reid, Elliott y Crespo 2013"),
    "ball_bounce.hip_height": ("Bajar la cadera cuando bota la bola carga las piernas para el swing.", "Tennis Australia; Nesbit 2008"),
    "takeback.hands_apart": ("Girar con la mano libre en la raqueta es el «giro unitario»: hombros y raqueta van juntos.", "Tennis Australia; ITF"),
    "takeback.shoulder_turn": ("La preparación empieza por el giro del tronco, no por el brazo.", "ITF (Crespo, Reid)"),
    "class.takeback": ("Una preparación compacta ahorra tiempo contra bolas rápidas; una amplia da más recorrido al swing.", "Yandell; Tennis Australia"),
    "footwork.first_step_s": ("Un primer paso rápido tras el split step es la base de llegar bien a la bola.", "Uzu 2009; Mecheri"),
    "footwork.steps_to_impact": ("Las profesionales suelen llegar con 2-3 pasos y ajustar con pasos cortos al final.", "Tanabe; Cardiff Met"),
    "loaded.shoulder_turn": ("Girar los hombros carga el tronco para el swing.", "Landlinger 2010; Elliott 2006"),
    "loaded.hip_turn": ("La cadera gira menos que los hombros: esa diferencia estira el tronco.", "Landlinger 2010"),
    "loaded.x_factor": ("Girar los hombros más que la cadera estira el tronco y almacena energía para el swing.", "Landlinger 2010; Tennis Australia"),
    "loaded.racket_head_vs_wrist": ("La raqueta por encima de la mano al armar prepara el bucle y la caída posterior.", "Yandell; Tennis Australia"),
    "loaded.wrist_dom_vs_shoulder": ("La mano no debe subir por encima de la cabeza al armar.", "Tennis Australia"),
    "loaded.shoulder_abd_non": ("El brazo libre señalando la bola ayuda a girar el tronco y a medir la distancia.", "Elliott 2006; Tennis Australia"),
    "loaded.elbow_non": ("El brazo libre extendido equilibra el giro y luego tira del tronco hacia delante.", "Elliott 2006; Tennis Australia"),
    "loaded.hip_height": ("Bajar la cadera al armar carga las piernas: es la fuente del empuje y de la rotación.", "Tennis Australia; Nesbit 2008"),
    "loaded.com_over_feet": ("Dónde está el peso entre los pies al armar dice qué pierna empuja la rotación.", "Tennis Australia"),
    "loaded.face_tilt": ("La cara de la raqueta al final del armado define el bucle: cerrada (hacia el suelo) o abierta.", "Elliott y Marsh 1989"),
    "class.takeback_face": ("La cara de la raqueta al final del armado define el bucle: cerrada (hacia el suelo) o abierta.", "Elliott y Marsh 1989"),
    "class.stance_loaded": ("El apoyo con el que arma decide cuánto puede girar la cadera.", "Martin 2021; Tennis Australia"),
    "stroke.pause_at_loaded": ("El bucle debe ser continuo: una pausa larga arriba reduce lo que aporta el estiramiento de los músculos; "
                                "si hay que esperar a la bola, se espera en el giro, no en lo alto del armado.", "Elliott 2006; Wilson, Elliott y Wood 1991"),
    "loaded.racket_forearm": ("La muñeca echada hacia atrás al armar se suelta al final del swing y aporta velocidad.", "Landlinger 2010; Pedro 2022"),
    "acceleration.racket_forearm": ("La muñeca echada hacia atrás se suelta al final del swing y aporta velocidad.", "Landlinger 2010; Pedro 2022"),
    "stroke.t_acceleration": ("En las profesionales el swing hacia delante es corto y muy rápido.", "Landlinger 2010"),
    "stroke.dur_forward": ("En las profesionales el swing hacia delante es corto y muy rápido.", "Landlinger 2010"),
    "stroke.wrist_drop": ("Dejar caer la mano y la raqueta por debajo de la bola permite golpear de abajo arriba (liftado).", "Reid, Elliott y Crespo 2013"),
    "acceleration.racket_head_vs_wrist": ("La cabeza de la raqueta cae por debajo de la mano antes de subir hacia la bola: es la base del liftado.", "Reid, Elliott y Crespo 2013; Yandell"),
    "class.swing": ("La dirección del swing (de abajo arriba o plano) decide el efecto de la bola.", "Takahashi; Elliott y Marsh 1989"),
    "chain": ("Picos de velocidad en orden cadera → tronco → brazo → antebrazo: el cuerpo pasa la energía al brazo.", "Landlinger 2010; Elliott 2006"),
    "stroke.racket_speed_rel": ("La velocidad real no se ve en la tele; esta solo compara sus golpes entre sí.", "—"),
    "impact.wrist_dom_height": ("La altura del contacto marca qué bolas le resultan cómodas.", "Reid, Elliott y Crespo 2013"),
    "impact.wrist_dom_vs_hip": ("Golpear entre la cintura y el pecho es la zona de contacto más habitual del circuito.", "Elliott 1989; Reid 2013"),
    "impact.wrist_dom_lateral": ("Golpear separada del cuerpo deja espacio para extender el brazo.", "Knudson 2006"),
    "impact.elbow_dom": ("Brazo recto o doble flexión son dos modelos válidos: lo importante es repetir el mismo en todos los golpes.", "Elliott 1989, 1997"),
    "class.arm": ("Brazo recto o doble flexión son dos modelos válidos: lo importante es repetir el mismo en todos los golpes.", "Elliott 1989, 1997"),
    "class.ball_phase": ("Tomar la bola subiendo quita tiempo a la rival; tomarla cayendo da más tiempo propio.", "ITF (Crespo, Reid)"),
    "class.racket_plane": ("Con la raqueta al lado del cuerpo el armado es más corto y estable; por detrás de la espalda "
                           "el recorrido es más largo (más aceleración, más difícil de sincronizar). Es un debate abierto "
                           "entre entrenadores del circuito.", "Entrenadores WTA/ATP"),
    "loaded.racket_head_lateral": ("Dónde queda la cabeza de la raqueta respecto al hombro al final del armado: al lado del "
                                   "cuerpo o hacia la espalda.", "Entrenadores WTA/ATP"),
    "class.contact_type": ("La media volea (justo tras el bote, muy baja) y la volea (sin bote, junto a la red) piden un swing "
                           "más corto y la cara más estable que la derecha normal: se separan para no mezclarlas.", "ITF (Crespo, Reid)"),
    "stroke.contact_vs_top": ("Tomar la bola subiendo quita tiempo a la rival; tomarla cayendo da más tiempo propio.", "ITF (Crespo, Reid)"),
    "stroke.contact_height_m": ("La altura de la bola en el contacto dice qué bolas le llegan y cuáles elige.", "Reid, Elliott y Crespo 2013"),
    "stroke.swing_low_to_high": ("La mano sube hacia la bola en el contacto: golpe con efecto liftado.", "Takahashi; Elliott y Marsh 1989"),
    "impact.trunk_tilt": ("Un tronco estable en el impacto da precisión.", "Tennis Australia"),
    "impact.head_over_base": ("La cabeza centrada sobre los pies indica equilibrio en el impacto.", "Tennis Australia"),
    "stroke.head_motion_cm": ("Las mejores jugadoras mantienen la cabeza quieta en el impacto.", "Lafont 2008"),
    "stroke.head_still_after_cm": ("Las expertas mantienen la cabeza orientada al punto de contacto también después de golpear; "
                                   "levantarla pronto para ver la bola arrastra los hombros.", "Lafont 2008"),
    "impact.body_height": ("Lo que baja el cuerpo en el impacto dice cuánto usa las piernas.", "Tennis Australia"),
    "impact.base_m": ("Una base ancha da estabilidad en el impacto.", "Tennis Australia"),
    "loaded.base_court_m": ("La distancia real entre los pies al armar decide cuánto puede cargar la pierna exterior y "
                            "girar la cadera sin perder el equilibrio.", "Tennis Australia"),
    "impact.base_court_m": ("Una base algo más ancha que los hombros en el impacto da estabilidad para soltar el swing; "
                            "demasiado estrecha o demasiado ancha frena la rotación.", "Tennis Australia"),
    "finish.base_court_m": ("Mantener la base al terminar indica que golpeó en equilibrio y puede recuperar enseguida.",
                            "Tennis Australia"),
    "stroke.feet_move_m": ("Los pies plantados del armado al impacto dan una base fija para girar; si se mueven, "
                           "está ajustando o golpeando en carrera.", "Tennis Australia; Giles y Reid 2021"),
    "surface": ("La superficie cambia el bote y el apoyo: en tierra se desliza al golpear y la bola sube más; "
                "en hierba bota bajo y rápido. Solo se comparan golpes de la misma superficie.", "ITF (Crespo, Reid); Tennis Australia"),
    "footwork.crossover_steps": ("El paso cruzado cubre más distancia que el lateral: aparece al ir a bolas lejanas y "
                                 "al recuperar hacia el centro.", "Kovacs 2009; Tennis Australia"),
    "class.stance_impact": ("El apoyo abierto es el más usado en el circuito (84 % de las derechas en un estudio de 2025); el cerrado aparece más al atacar bolas cortas.", "IJSSC 2025; Martin 2021"),
    "class.stance_role": ("El mismo apoyo puede ser de ataque o de defensa según cómo llega a la bola.", "Martin 2021"),
    "class.movement": ("Cómo llega a la bola (parada o en carrera) cambia el apoyo y la terminación.", "Giles y Reid 2021"),
    "stroke.hand_on_handle": ("Dónde agarra el mango cambia el brazo de palanca; desde la tele es una medida poco fiable.", "Yandell"),
    "extension.arm_extension": ("Seguir hacia la bola tras el contacto indica que el swing no se frena.", "ITF (Crespo, Reid)"),
    "stroke.swing_rise_after": ("La mano sigue subiendo tras el contacto: el swing termina el efecto liftado.", "Takahashi"),
    "stroke.t_finish": ("Una terminación completa indica que no frenó el brazo.", "Tennis Australia"),
    "finish.wrist_dom_vs_shoulder": ("Terminar con la mano por encima del hombro es la terminación clásica de una derecha con efecto.", "Tennis Australia"),
    "finish.wrist_dom_lateral": ("Cruzar el brazo al otro lado del cuerpo indica que el tronco ha girado del todo.", "Tennis Australia"),
    "finish.face_tilt": ("La cara de la raqueta al terminar refleja cómo ha girado el antebrazo.", "Elliott 1997"),
    "class.finish": ("Sobre el hombro en golpes largos; limpiaparabrisas en bolas con más efecto o abiertas.", "Tennis Australia"),
    "class.finish_3x90": ("La terminación «3 × 90°» (hombro, codo y muñeca a unos 90°) es la referencia de los manuales.", "Reid 2013"),
    "footwork.recovery_to_centre_m": ("Volver hacia el centro tras golpear prepara la siguiente bola.", "Armstrong 2024"),
    "footwork.off_centre_at_opp_hit_m": ("Estar cerca del centro cuando golpea la rival reduce lo que tiene que correr.", "Armstrong 2024; Yandell"),
    "strings": ("Hacia dónde miran las cuerdas en cada momento describe el bucle de la raqueta.", "Elliott y Marsh 1989"),
    "first_step_right_way": ("Que el primer paso vaya hacia la bola indica una lectura temprana.", "Mecheri"),
    "rear_leg_step_after": ("Pasar la pierna de atrás adelante tras golpear indica una rotación completa del tronco.", "Landlinger 2010"),
    "footwork.speed_pre_split_mps": ("Frenar antes del split step y acelerar después indica un split bien hecho.", "Filipcic 2017"),
    "footwork.speed_post_split_mps": ("Frenar antes del split step y acelerar después indica un split bien hecho.", "Filipcic 2017"),
    "footwork.split_takeoff_vs_opp_s": ("Despegar justo antes de que golpee la rival permite caer cuando ya se ve la dirección.", "Uzu 2009; Avilés"),
    "footwork.first_step_length_m": ("Un primer paso largo y rápido es el que más distancia gana.", "Tanabe"),
    "footwork.last_step_length_m": ("En carrera, la última zancada más larga sirve para frenar y golpear.", "Giles y Reid 2021"),
    "footwork.adjustment_steps": ("Los pasos cortos de ajuste al final colocan el cuerpo a la distancia justa de la bola.", "Cardiff Met; Giles"),
    "footwork.direction_changes": ("Muchos cambios de dirección pueden indicar que leyó tarde la bola (también pueden ser pasos de ajuste).", "Giles 2023"),
    "footwork.peak_speed_mps": ("La velocidad máxima dice cuánto tuvo que correr para llegar.", "Martínez-Gallego 2013"),
    "footwork.approach_speed_mps": ("Llegar frenada a la bola permite golpear en equilibrio.", "Giles y Reid 2021"),
    "footwork.path_m": ("La mayoría de golpes del circuito llegan tras correr 3-4 m o menos.", "Reid 2013"),
    "footwork.weight_loaded_to_non": ("Qué pierna carga el peso al armar decide de dónde sale la rotación.", "Sandamas 2013"),
    "footwork.move_direction": ("Hacia dónde se mueve (lateral, delante, atrás) cambia el apoyo que puede usar.", "Weber; Kovacs"),
    "class.move_direction": ("Hacia dónde se mueve (lateral, delante, atrás) cambia el apoyo que puede usar.", "Weber; Kovacs"),
    "footwork.first_step_type": ("El tipo de primer paso (cruzado, lateral, pivote) depende de hacia dónde y cuánto tiene que ir.", "Bragg 2001; Vuong 2022"),
    "metrics.head_motion_impact_cm": ("Las mejores jugadoras mantienen la cabeza quieta en el impacto.", "Lafont 2008"),
    "class.shot_type": ("La dirección de su golpe (cruzada, paralela, invertida) cambia la preparación y el apoyo.", "F3Set; TennisViz"),
    "shot_direction": ("La dirección de su golpe (cruzada, paralela, invertida) cambia la preparación y el apoyo.", "F3Set; TennisViz"),
    "class.intent": ("Atacar, mantener o defender cambia la técnica: compararla en cada caso evita confundir técnica con situación.", "TennisViz"),
    "point_won": ("Cuántos puntos gana atacando o defendiendo con su derecha.", "TennisViz (Conversion / Steal)"),
    "class.play": ("Resto, inicio del punto o peloteo: cada momento del punto pide una derecha distinta.", "F3Set"),
    "class.ball_speed": ("Con menos tiempo (bola rápida) se prepara antes y se acorta el armado; con bola lenta hay que generar la potencia.", "Tennis Australia; ITF"),
    "class.ball_height": ("La altura del contacto cambia la carga de piernas, la trayectoria y la terminación.", "ITF; Elliott-Reid-Crespo"),
    "class.depth": ("Dentro de la pista se ataca; muy atrás se defiende con más altura: la técnica cambia con el sitio.", "TennisViz; ITF"),
    "class.court_side": ("Desde el lado del revés la derecha se rodea (invertida): otro apoyo y otra dirección.", "ITF; F3Set"),
    "class.serve_number": ("El resto de primer saque es casi un bloqueo; el de segundo saque, la ocasión de atacar.", "Tennis Australia; ITF"),
    "class.serve_dir": ("Abierto, al cuerpo o a la T: cada saque pide un primer paso distinto (diagonal, de apertura o hacia el centro).", "ITF; Kovacs 2009"),
    "class.return_side": ("En iguales y en ventaja la derecha recibe saques distintos: abiertos en iguales, a la T o al cuerpo en ventaja.", "Tennis Australia"),
    "return_ready_depth_m": ("Dónde espera el saque: más atrás gana tiempo, más adentro quita tiempo a la rival.", "ITF; Tennis Australia"),
    "return_step_in_m": ("Entrar hacia la bola en el resto adelanta el contacto y quita tiempo a la rival.", "ITF"),
    "approach": ("Las subidas a la red empiezan con una derecha de ataque desde dentro de la pista.", "SwingVision; F3Set"),
    "approach_main": ("Pasos laterales para distancias cortas, cruzados y de carrera para las largas: así se cubre la pista con eficiencia.", "Kovacs 2009; Tennis Australia"),
    "recovery_first_step": ("La recuperación suele empezar con un paso cruzado o con pasos laterales según lo lejos que quedó del centro.", "Kovacs 2009; Armstrong 2024"),
    "braking_step": ("En carrera, frenar con un último paso largo permite golpear en equilibrio.", "Giles y Reid 2021"),
    "kick_back": ("La patada atrás (tijera) compensa el giro del tronco cuando golpea en el aire o en carrera.", "Tennis Australia"),
    "around_ball": ("Rodear la bola para pegar de derecha desde el lado del revés (derecha invertida) es una decisión táctica de ataque.", "TennisViz; Tennis Australia"),
    "loaded.elbow_dom_vs_shoulder": ("Codo alto y separado del cuerpo: armado al lado del cuerpo; codo bajo y pegado: armado más por detrás de la espalda.", "Análisis de entrenadores WTA/ATP; Tennis Australia"),
    "loaded.elbow_dom_lateral": ("Codo alto y separado del cuerpo: armado al lado del cuerpo; codo bajo y pegado: armado más por detrás de la espalda.", "Análisis de entrenadores WTA/ATP; Tennis Australia"),
    "impact.elbow_dom_vs_shoulder": ("La altura del codo en el impacto dice cuánto «tira» el brazo hacia arriba en el contacto.", "Elliott 1997"),
    "stroke.takeback_vs_first_step": ("Girar mientras se desplaza ahorra tiempo: llega a la bola ya preparada.", "Tennis Australia; ITF"),
    "stroke.acceleration_vs_bounce": ("Esperar al bote para empezar a acelerar sincroniza el swing con la bola.", "ITF (Crespo, Reid)"),
    "stroke.hip_rise": ("Subir con las piernas al golpear inicia la cadena cinética desde el suelo y ayuda al efecto liftado.", "Elliott 2006; Reid 2013"),
    "stroke.weight_shift": ("Pasar el peso hacia delante (o de la pierna exterior a la otra en apoyo abierto) lleva la energía del suelo a la bola.", "Tennis Australia"),
    "extension.wrist_non_lateral": ("Recoger el brazo libre contra el pecho («catch») frena el lado del brazo libre y acelera el giro del tronco.", "Tennis Australia; ITF"),
    "loaded.racket_tip_vs_head": ("La punta de la raqueta arriba al final del armado es el principio del bucle: luego cae por debajo de la bola.", "ITF (Crespo, Reid); análisis de entrenadores de su derecha (R8)"),
    "loaded.elbow_dom": ("El codo doblado y separado del cuerpo al armar deja espacio al brazo para acelerar; la altura varía entre estilos.", "ITF (Crespo, Reid); Tennis Australia"),
    "class.takeback_loop": ("Bucle continuo, loop falso o recto atrás son las tres formas de armar que distinguen los entrenadores; el bucle continuo aprovecha el estiramiento de los músculos.", "Elliott 2006; ITF"),
    "stroke.shoulder_brake": ("El tronco gira fuerte y se frena justo antes del contacto: esa energía pasa al brazo y a la raqueta (secuencia de la cadena cinética).", "Landlinger 2010; Elliott 2006"),
    "stroke.hip_drop_cm": ("Bajar la cadera antes de golpear carga las piernas; el empuje posterior inicia la cadena cinética.", "Elliott 2006; Reid, Elliott y Crespo 2013"),
    "stroke.racket_lag_deg": ("Con la muñeca relajada, la raqueta se retrasa respecto al antebrazo al empezar el swing y sale después como un látigo.", "Landlinger 2010; Elliott 2006"),
    "stroke.last_plant_vs_bounce": ("Llegar pronto y tener el último apoyo firme cerca del bote da tiempo a golpear equilibrado.", "ITF (Crespo, Reid); Tennis Australia"),
    "stroke.loaded_vs_last_plant": ("Correr ya girado y terminar de armar en los últimos pasos evita llegar a la bola y tener que armar todavía.", "Tennis Australia; ITF"),
    "class.back_at_impact": ("Golpear mientras se retrocede lleva el peso hacia atrás: la bola sale con menos peso y más corta.", "ITF (Crespo, Reid)"),
    "class.catch_racket": ("Recoger la raqueta con la mano libre al terminar cierra el giro del tronco y deja lista para recuperar.", "Tennis Australia"),
    "class.finish_trunk": ("Hacia dónde mira el tronco al terminar dice cuánto ha girado: más en los cruzados y con más efecto.", "ITF (Crespo, Reid)"),
    "stroke.dur_preparation": ("La preparación tiene su ritmo: ni a trompicones ni tan lenta que no esté armada al botar la bola.", "Tennis Australia"),
    "chain.proximal_to_distal": ("La cadena cinética va de abajo arriba: cadera, tronco, brazo y raqueta; desde la tele se mide el orden de los picos, no los milisegundos.", "Landlinger 2010; Elliott 2006"),
    "finish.head_over_base": ("Terminar con la cabeza sobre los pies indica que no perdió el equilibrio al frenar el giro.", "Tennis Australia"),
    "finish.trunk_tilt": ("Un tronco estable al terminar indica que no hubo «desplome» tras el golpe.", "Tennis Australia"),
    "stroke.shoulders_open_first": ("Si los hombros abren antes que la cadera se pierde la separación (fuga de energía, «apertura prematura»).", "Landlinger 2010; Elliott 2006"),
    "footwork.step_in": ("El paso de ataque (step-in) lleva el peso hacia delante, dentro de la pista.", "Tennis Australia; Kovacs 2009"),
    "footwork.drag_foot": ("Arrastrar el pie de atrás tras golpear mantiene el equilibrio en carrera.", "Tennis Australia"),
    "step_in": ("El paso de ataque (step-in) lleva el peso hacia delante, dentro de la pista.", "Tennis Australia; Kovacs 2009"),
    "drag_foot": ("Arrastrar el pie de atrás tras golpear mantiene el equilibrio en carrera.", "Tennis Australia"),
    "loaded.back_foot_angle_deg": ("El pie de atrás colocado de lado (paralelo a la línea de fondo o algo hacia la red) es el apoyo "
                                   "sobre el que carga y gira la cadera.", "Tennis Australia"),
    "loaded.front_foot_angle_deg": ("Hacia dónde apunta el pie de delante al armar decide cuánto podrá girar la cadera.", "Tennis Australia"),
    "impact.front_foot_angle_deg": ("El pie de delante abierto hacia la red deja girar la cadera; muy cerrado la bloquea.",
                                    "Tennis Australia; Elliott 2006"),
    "impact.back_foot_angle_deg": ("El pie de atrás gira hacia la red con la cadera: si se queda clavado de lado, la rotación se frena.",
                                   "Tennis Australia; Landlinger 2010"),
    "footwork.back_heel_lift": ("Pivotar sobre la punta del pie de atrás (el talón se levanta) deja que la cadera gire del todo "
                                "hacia la bola: es una comprobación clásica de los entrenadores.", "Tennis Australia; ITF (Crespo, Reid)"),
    "back_heel_lift": ("Pivotar sobre la punta del pie de atrás (el talón se levanta) deja que la cadera gire del todo "
                       "hacia la bola: es una comprobación clásica de los entrenadores.", "Tennis Australia; ITF (Crespo, Reid)"),
    "footwork.back_heel_lift_s": ("El talón de atrás se levanta cuando la cadera empieza a girar hacia la bola, alrededor del impacto.",
                                  "Tennis Australia; Elliott 2006"),
}
# What a coach checks at each moment (critical features: Knudson 2006; Tennis Australia)
PHASE_FOCUS = {
    "ready": "que caiga del split step justo cuando golpea la rival, con una base estable.",
    "takeback": "que empiece girando los hombros, no solo el brazo, en cuanto sabe a qué lado va la bola.",
    "loaded": "armado completo cuando bota la bola: hombros girados, raqueta arriba y brazo libre señalando la bola.",
    "acceleration": "que la raqueta caiga por debajo de la mano y que la cadera arranque antes que el brazo.",
    "impact": "contacto delante y al lado del cuerpo, con la cabeza quieta.",
    "extension": "que el brazo siga hacia la bola antes de cruzar el cuerpo.",
    "finish": "terminación completa y en equilibrio.",
    "recovery": "el primer paso de vuelta antes de que golpee la rival.",
}
# The keys a coach says first at each moment (the rest is folded under «Más medidas»)
PRIMARY = {
    "ready": ["footwork.split_landing_vs_opp_s", "ready.hip_height", "class.ready_hands"],
    "takeback": ["stroke.takeback_vs_net", "stroke.takeback_vs_bounce", "takeback.shoulder_turn", "class.takeback", "first_step_right_way"],
    "loaded": ["stroke.loaded_vs_bounce", "loaded.x_factor", "class.stance_loaded", "class.takeback_face", "strings",
               "loaded.elbow_dom_vs_shoulder", "loaded.shoulder_abd_non"],
    "acceleration": ["acceleration.racket_head_vs_wrist", "chain", "stroke.hip_rise", "class.swing"],
    "impact": ["class.ball_phase", "impact.wrist_dom_vs_hip", "class.arm", "class.stance_impact", "stroke.weight_shift",
               "stroke.head_motion_cm", "strings"],
    "extension": ["extension.arm_extension", "stroke.swing_rise_after", "extension.wrist_non_lateral"],
    "finish": ["class.finish", "finish.wrist_dom_vs_shoulder", "finish.head_over_base", "strings"],
    "recovery": ["footwork.recovery_to_centre_m", "footwork.off_centre_at_opp_hit_m", "rear_leg_step_after"],
}
STRINGS_REL = {"ready": 3, "takeback": 3, "loaded": 3, "acceleration": 1, "impact": 1, "extension": 1, "finish": 3, "recovery": 2}
CLASS_TEXT = {
    "stance_loaded": "Apoyo al armar", "stance_impact": "Apoyo en el impacto", "stance_role": "Función del apoyo",
    "takeback_face": "Cara al final del armado", "finish": "Terminación", "arm": "Brazo",
    "takeback": "Preparación", "ready_hands": "Manos en la espera", "movement": "Cómo llega a la bola", "feet_at_impact": "Pies en el impacto",
    "swing": "Trayectoria", "ball_phase": "Bola en el contacto", "finish_3x90": "Termina con hombro y codo a unos 90° («3 × 90°»)",
    "contact_type": "Contacto (tras el bote, media volea o volea)",
    "racket_plane": "Raqueta al final del armado",
    "takeback_loop": "Forma del armado (bucle, loop falso o recto atrás)",
    "back_at_impact": "Golpea retrocediendo (moviéndose hacia su línea de fondo)",
    "catch_racket": "La mano libre recoge la raqueta al terminar",
}
CLASS_PHASE = {"ready_hands": "ready", "takeback": "takeback", "stance_loaded": "loaded", "takeback_face": "loaded",
               "ball_phase": "impact",
               "stance_impact": "impact", "stance_role": "impact",
               "arm": "impact", "finish": "finish", "finish_3x90": "finish", "movement": "impact", "feet_at_impact": "impact", "swing": "acceleration",
               "contact_type": "impact", "racket_plane": "loaded", "takeback_loop": "loaded",
               "back_at_impact": "impact", "catch_racket": "finish"}


def _class_line(c: dict) -> str | None:
    if not c or (c.get("n") or 0) < MIN_N:        # a percentage of a handful of strokes says nothing
        return None
    tot = c["n"]
    if set(c["counts"]) <= {True, False, "True", "False", "true", "false"}:       # yes/no classes
        yes = sum(v for k, v in c["counts"].items() if str(k).lower() == "true")
        return f"en el {round(100 * yes / tot)} % de sus golpes"
    parts = [f"{k} {round(100 * v / tot)} %" for k, v in list(c["counts"].items())[:3]]
    return ", ".join(parts)


def phase_cards(model: dict, stroke: str, factor: str | None = None, level: str | None = None) -> list[dict]:
    """8 cards: title, lines (text + key + reliability + change in this situation), skeleton, strokes."""
    titles = dict(PHASE_TITLES, **(PHASE_TITLES_OVERHEAD if stroke == "overhead" else {}))
    var = (model["variants"].get(factor) or {}).get(level) if factor else None
    eff = {e["key"]: e for e in (var or {}).get("effects", [])}
    classes = var["classes"] if var else model["classes"]
    cards = []
    for p, title in titles.items():
        lines = []
        for key, build in LINES.get(p, []):
            t = _t(model, key)
            if not t:
                continue
            try:
                text = build(t)
            except (TypeError, ValueError, KeyError):
                continue
            e = eff.get(key)
            if e:                         # the value in this situation, not only the difference
                d = 2 if t["unit"] in ("s", "m", "m/s", "") else 0
                text = f"{text} En esta situación: {fmt(t['median'] + e['diff'], d)}{_u(t['unit'])}."
            lines.append({"key": key, "text": text, "rel": t["rel"], "n": t["n"],
                          "change": None if not e else {"diff": round(e["diff"], 3), "unit": t["unit"], "ref": e["ref"]}})
        for ck, cp in CLASS_PHASE.items():
            if cp == p and classes.get(ck):
                txt = _class_line(classes[ck])
                if txt:
                    lines.append({"key": "class." + ck, "text": f"{CLASS_TEXT[ck]}: {txt}.", "rel": 3, "n": classes[ck]["n"], "change": None})
        lines += _extra_lines(p, var or model)
        for ln in lines:
            ln["why"], ln["src"] = COACH.get(ln["key"], (None, None))
            ln["main"] = ln["key"] in PRIMARY.get(p, []) or bool(ln["change"])
        order = PRIMARY.get(p, [])
        lines.sort(key=lambda ln: (not ln["main"], order.index(ln["key"]) if ln["key"] in order else 99))
        # the effects of this situation on this phase that no template covers
        for key, e in eff.items():
            if key.split(".")[0] == p and not any(l["key"] == key for l in lines):
                t = _t(model, key)
                lines.append({"key": key, "text": f"{t['name']}: {fmt(t['median'] + e['diff'], 1)}{_u(t['unit'])} "
                              f"(habitual {fmt(t['median'], 1)}{_u(t['unit'])}).", "rel": t["rel"], "n": e["n"],
                              "change": {"diff": round(e["diff"], 3), "unit": t["unit"], "ref": e["ref"]}})
        skel = ((var or {}).get("skeleton") or {}).get(p) or model["skeleton"].get(p)
        cards.append({"phase": p, "title": title, "lines": lines, "skeleton": skel, "focus": PHASE_FOCUS.get(p),
                      "copy": copy_cue(p, model, classes),
                      "changes": sum(1 for l in lines if l["change"])})
    return cards


def copy_cue(p: str, model: dict, classes: dict) -> str | None:
    """«Para copiarla»: what to do at this moment, as a coach would say it, built only from her
    measured values (median of her strokes; the main class when it has enough strokes)."""
    t = lambda k: _t(model, k)
    def top(ck):
        c = classes.get(ck)
        return next(iter(c["counts"])) if c and c.get("n", 0) >= MIN_N and c.get("counts") else None
    def height_word(v):       # contact height against the hips (% of her height)
        return "las rodillas" if v < -15 else "la cadera" if v < 3 else "la cintura" if v < 12 else "el pecho" if v < 22 else "los hombros"
    parts = []
    if p == "ready":
        if top("ready_hands") == "dos manos en la raqueta":
            parts.append("espera con las dos manos en la raqueta")
        h = t("ready.hip_height")
        if h:
            parts.append(f"con las rodillas flexionadas (cadera a un {fmt(h['median'])} % de tu altura)")
        sp = t("footwork.split_landing_vs_opp_s")
        if sp:
            parts.append("y cae del split step justo cuando golpea la rival" if abs(sp["median"]) <= 0.1 else
                         f"y cae del split step {fmt(abs(sp['median']), 2)} s {'después' if sp['median'] > 0 else 'antes'} del golpe de la rival")
    elif p == "takeback":
        n = t("stroke.takeback_vs_net")
        if n:
            parts.append("empieza a girar los hombros antes de que la bola cruce la red" if n["median"] < -0.03 else
                         "empieza a girar los hombros cuando la bola cruza la red" if n["median"] <= 0.05 else
                         f"empieza a girar los hombros {fmt(n['median'], 2)} s después de que la bola cruce la red")
        ha = t("takeback.hands_apart")
        if ha and ha["median"] < 15:
            parts.append("con la mano libre todavía en la raqueta")
        if top("takeback"):
            parts.append(f"con una preparación {top('takeback')}")
        tf = t("stroke.takeback_vs_first_step")
        if tf and tf["median"] < -0.05:
            parts.append("girando mientras te mueves")
    elif p == "loaded":
        lb = t("stroke.loaded_vs_bounce")
        if lb:
            parts.append("termina de armar antes de que bote la bola" if lb["median"] < 0 else "termina de armar justo después del bote")
        sh = t("loaded.shoulder_turn")
        if sh:
            parts.append(f"con los hombros girados unos {fmt(round(sh['median'] / 5) * 5)}°")
        if top("stance_loaded"):
            parts.append(f"apoyo {top('stance_loaded')}")
        ab = t("loaded.shoulder_abd_non")
        if ab and ab["median"] > 60:
            parts.append("y el brazo libre señalando la bola")
    elif p == "acceleration":
        r = t("acceleration.racket_head_vs_wrist")
        if r and r["median"] < -2:
            parts.append("deja caer la raqueta por debajo de la mano")
        hr = t("stroke.hip_rise")
        if hr and hr["median"] > 1.5:
            parts.append("empuja hacia arriba con las piernas")
        ch = model.get("chain")
        if ch and ch.get("n", 0) >= MIN_N:
            parts.append("y deja que la cadera y el tronco arrastren al brazo")
    elif p == "impact":
        if top("ball_phase"):
            parts.append(f"toma la bola {top('ball_phase').replace('bola ', '')}")
        h = t("impact.wrist_dom_vs_hip")
        if h:
            parts.append(f"a la altura de {height_word(h['median'])}")
        if top("arm"):
            parts.append(f"con el brazo en {top('arm')}" if top("arm") == "doble flexión" else f"con el brazo {top('arm')}")
        if top("stance_impact"):
            parts.append(f"apoyo {top('stance_impact')}")
        hm = t("stroke.head_motion_cm")
        if hm and hm["median"] <= 3:
            parts.append("y la cabeza quieta")
    elif p == "extension":
        e = t("extension.arm_extension")
        if e:
            parts.append("sigue empujando hacia la bola con el brazo después del contacto")
    elif p == "finish":
        if top("finish"):
            fin = top("finish")
            parts.append("termina en látigo, sobre el mismo hombro" if fin.startswith("látigo") else
                         f"termina {fin}" if fin.startswith(("sobre", "alrededor")) else f"termina con un final {fin}")
    elif p == "recovery":
        if top("recovery_first_step"):
            parts.append(f"vuelve hacia el centro empezando con un paso {top('recovery_first_step')}")
        elif t("footwork.recovery_to_centre_m"):
            parts.append("vuelve hacia el centro en cuanto terminas el golpe")
    if not parts:
        return None
    s = ", ".join(parts).replace(", y ", " y ")
    return s[0].upper() + s[1:] + "."


def _share_true(c: dict | None) -> tuple[int, int] | None:
    if not c or (c.get("n") or 0) < MIN_N:
        return None
    yes = sum(v for k, v in c["counts"].items() if str(k).lower() == "true")
    return round(100 * yes / c["n"]), c["n"]


def _extra_lines(p: str, src: dict) -> list[dict]:
    """Sentences that come from counts rather than medians: where the strings point, the kinetic
    chain, the first step and the back leg. src: the model or one of its variants."""
    out = []
    st = (src.get("strings") or {}).get(p)
    if st and st.get("n", 0) >= MIN_N:
        (to, k), = list(st["counts"].items())[:1]
        tilt = st.get("tilt")
        face = "" if tilt is None else (f", cara cerrada {fmt(tilt)}° (hacia el suelo)" if tilt > 5 else
                                        f", cara abierta {fmt(-tilt)}° (hacia el cielo)" if tilt < -5 else ", cara vertical")
        est = " Es una estimación: en este momento la raqueta sale borrosa." if STRINGS_REL[p] == 1 else ""
        out.append({"key": "strings", "text": f"Cuerdas mirando hacia {to} en el {round(100 * k / st['n'])} % de los golpes{face}.{est}",
                    "rel": STRINGS_REL[p], "n": st["n"], "change": None})
    if p == "acceleration":
        ch = _share_true(src.get("chain"))
        if ch:
            out.append({"key": "chain", "text": f"El cuerpo arrastra al brazo en orden (cadera → tronco → brazo → antebrazo) en el {ch[0]} % "
                        "de los golpes; se mide el orden, no los milisegundos.", "rel": 2, "n": ch[1], "change": None})
    fw = src.get("footwork") or {}
    if p == "takeback":
        r = _share_true(fw.get("first_step_right_way"))
        if r:
            out.append({"key": "first_step_right_way", "text": f"Su primer paso va hacia la bola en el {r[0]} % de los golpes.",
                        "rel": 2, "n": r[1], "change": None})
    if p == "finish":
        r = _share_true(fw.get("rear_leg_step_after"))
        if r:
            out.append({"key": "rear_leg_step_after", "text": f"La pierna de atrás pasa adelante tras golpear en el {r[0]} % de los golpes.",
                        "rel": 2, "n": r[1], "change": None})
    return out


def _u(unit: str) -> str:
    return "" if not unit else unit if unit in ("°", "%") else " " + unit


def change_text(model: dict, e: dict) -> str:
    """'Giro de hombros en el armado: −8° respecto a bola media'."""
    t = model["typical"][e["key"]]
    ph = PHASE_TITLES.get(e["key"].split(".")[0], "")
    d = 2 if t["unit"] in ("s", "m", "m/s", "") else 0
    sign = "+" if e["diff"] > 0 else "−"
    return f"{t['name']}{(' · ' + ph.lower()) if ph else ''}: {sign}{fmt(abs(e['diff']), d)}{_u(t['unit'])} respecto a «{e['ref']}»"


# «En pocas palabras»: the first sentence available of each group, taken from the phase cards so the
# summary and the phases always say the same thing
SUMMARY_KEYS = [["stroke.takeback_vs_net", "stroke.takeback_vs_bounce", "stroke.t_takeback"],
                ["stroke.loaded_vs_bounce", "loaded.x_factor", "loaded.shoulder_turn"],
                ["class.ball_phase", "stroke.contact_vs_top"], ["impact.wrist_dom_vs_hip", "class.arm"],
                ["class.stance_impact"], ["stroke.head_motion_cm"], ["class.finish"], ["footwork.split_landing_vs_opp_s"]]


def summary(model: dict, stroke: str) -> list[str]:
    """Her stroke in a few sentences: what she does at the key moments, then rhythm and grip."""
    out = []
    lines = {ln["key"]: ln for c in phase_cards(model, stroke) for ln in c["lines"]}
    for group in SUMMARY_KEYS:
        ln = next((lines[k] for k in group if k in lines), None)
        if ln:
            out.append(ln["text"])
    tf = _t(model, "stroke.dur_forward")
    tp = _t(model, "stroke.dur_preparation")
    if tf and tp:
        out.append(f"Ritmo: prepara en {fmt(tp['median'], 2)} s y acelera en {fmt(tf['median'], 2)} s.")
    pts = model.get("points_by_intent") or {}
    parts = [f"{k} {round(100 * v['won'] / v['n'])} % de {v['n']}" for k, v in sorted(pts.items()) if v["n"] >= 10]
    if parts:
        out.append("Puntos que gana según cómo acaba el punto con su golpe: " + ", ".join(parts) + ".")
    g = grip_compatible(model)
    if g:
        out.append(g)
    n_const = len([k for k in model["constants"] if model["typical"][k]["rel"] >= 2])
    n_eff = len({e["key"] for e in model["effects"]})
    if model.get("n_near", 0) < MIN_N:
        out.append(f"Con {model.get('n_near', 0)} golpes analizados todavía no se puede describir su técnica: hacen falta al menos "
                   f"{MIN_N} para dar cualquier dato (los vídeos de cada golpe sí se pueden ver).")
    elif n_const or n_eff:
        out.append(f"{n_const} rasgos se mantienen en todas las situaciones (su técnica de base) y {n_eff} cambian según la bola.")
    return out


def grip_compatible(model: dict) -> str | None:
    """The grip cannot be seen (a 20-40 px hand); it can only be called *compatible* with a family,
    from three signs reported in the literature (Elliott et al. 1989, 1997): contact above the hip,
    and a closed face at the end of the backswing go with semi-western / western grips; contact below
    the hip and a vertical face with eastern. (The elbow is left out: the sources do not agree on its
    direction.)"""
    h, f = (_t(model, k) for k in ("impact.wrist_dom_vs_hip", "loaded.face_tilt"))
    votes = []
    if h:
        votes.append(1 if h["median"] > 3 else -1 if h["median"] < -2 else 0)
    if f:
        votes.append(1 if f["median"] > 10 else -1 if f["median"] < 0 else 0)
    if len(votes) < 2:
        return None
    sc = sum(votes)
    fam = ("semioccidental u occidental" if sc >= 2 else "este" if sc <= -2 else None)
    if fam is None:
        return "Empuñadura: no concluyente desde la tele (los indicios no coinciden)."
    return (f"Empuñadura: compatible con {fam} (altura del contacto y cara en el armado). "
            "El tipo exacto no se ve en la retransmisión.")


FEET_NOT_MEASURABLE = ("Orientación del pie y apoyo de talón o de punta (pivote del pie de atrás): el esqueleto de estos golpes "
                       "no tiene puntos en los pies (talones y puntas); se miden cuando la pose los da.")
NOT_MEASURABLE = [
    "Empuñadura exacta (el bisel), en la espera y al golpear, y el cambio de empuñadura: la mano mide pocos píxeles "
    "en la retransmisión. Solo se dice si sus golpes son compatibles con una empuñadura semioccidental u occidental.",
    "Impacto delante o detrás del cuerpo: es la dirección hacia la cámara; solo se estima en 3D.",
    "Velocidad de la raqueta y de la bola en km/h, y el efecto (vueltas por minuto): salen borrosas a 25-60 fotogramas "
    "por segundo. La velocidad de la raqueta solo se compara entre sus golpes.",
    "Altura de la bola sobre la red y velocidad de salida de su golpe: la bola es pequeña y no hay una segunda cámara.",
    "Cara de la raqueta justo en el impacto: es una estimación interpolada (desenfoque).",
    "Ángulo exacto de la trayectoria de la raqueta en el impacto: las diferencias reales (unos 3°) son menores que el error.",
    "Flexión de rodillas exacta: escorzo desde detrás; se usa la altura de la cadera.",
    "Rotación interna del hombro, pronación del antebrazo y movimientos de la muñeca: son giros sobre el propio eje del "
    "brazo, invisibles en la imagen.",
    "Momento exacto (en milisegundos) de cada pico de la cadena cinética: está por debajo de un fotograma; se da el orden.",
    "Mirada: se la ve de espaldas.",
    "Fuerzas y cargas en las articulaciones: solo se mide el movimiento.",
    FEET_NOT_MEASURABLE,
    "Altura del salto del split step: desde detrás, subir se confunde con alejarse.",
    "Nuevo split step antes del siguiente golpe de la rival: el vídeo de cada golpe acaba 0,8 s después del impacto.",
    "Punto del cordaje donde golpea, presión de agarre y contribución de cada segmento a la velocidad: necesitan "
    "sensores o cámaras de laboratorio.",
    "Reacción y fuerzas contra el suelo, tasa de desarrollo de fuerza, activación muscular (electromiografía), "
    "estabilidad lumbopélvica, rangos articulares y cargas del codo: necesitan plataformas de fuerza, sensores o laboratorio.",
    "Propiedades de la raqueta (swingweight, rigidez, encordado, tensión), relajación o tensión de la empuñadura, "
    "trayectoria horizontal del swing (de dentro a fuera), velocidad angular en grados por segundo, aerodinámica, "
    "altitud, temperatura y humedad: no se ven en la retransmisión.",
]


def model_view(model: dict, stroke: str) -> dict:
    """Everything the 'Su golpe' screen needs, computed once in Python."""
    variants = {}
    for fk, lvls in model["variants"].items():
        for lv, v in lvls.items():
            variants[f"{fk}|{lv}"] = {
                "factor": fk, "factor_name": FACTORS[fk][0], "level": lv, "n": v["n"], "share": v["share"], "usual": v["usual"],
                "compared": v.get("compared", True),
                "cards": phase_cards(model, stroke, fk, lv), "strokes": v["strokes"],
                "changes": [change_text(model, e) for e in v["effects"]],
                "curves": v.get("curves"),
            }
    nm = list(NOT_MEASURABLE)
    # with heels and toes in her strokes the foot direction and the pivot are measured: not «no medible»
    feet_seen = ((model.get("footwork") or {}).get("back_heel_lift") or {}).get("n") or any(
        k.endswith("_foot_angle_deg") for k in model.get("typical", {}))
    if feet_seen:
        nm.remove(FEET_NOT_MEASURABLE)
    if model.get("steps_reliable_share") is not None and model["steps_reliable_share"] < 0.5:
        nm.append("Pasos uno a uno, primer paso y split step: en estas imágenes sus tobillos tiemblan demasiado "
                  f"(medibles solo en el {round(100 * model['steps_reliable_share'])} % de los golpes); sí se miden "
                  "su desplazamiento, la velocidad con la que llega y su recuperación.")
    return {"summary": summary(model, stroke), "cards": phase_cards(model, stroke), "variants": variants,
            "typical_strokes": model.get("typical_strokes", []), "n": model["n_strokes"], "n_near": model["n_near"],
            "footwork": model["footwork"], "not_measurable": nm, "min_n": MIN_N,
            "coach": {k: v[0] for k, v in COACH.items() if k.startswith("footwork.") or k in (
                "first_step_right_way", "rear_leg_step_after", "approach_main", "recovery_first_step", "braking_step", "kick_back", "around_ball",
                "step_in", "drag_foot", "back_heel_lift")}, "curves": model.get("curves"),
            "factors": {fk: FACTORS[fk][0] for fk in model["variants"]}}
