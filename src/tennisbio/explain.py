"""From the model to plain language: what she does at each moment, how sure it is, and what
changes in each situation. Every sentence is a template filled with her measured values (median
and usual range); a sentence whose numbers are missing is simply not written.
"""
import math

from .model import FACTORS

PHASE_TITLES = {"ready": "Espera", "takeback": "Preparación", "loaded": "Armado", "acceleration": "Aceleración",
                "impact": "Impacto", "extension": "Extensión", "finish": "Terminación", "recovery": "Recuperación"}
PHASE_TITLES_OVERHEAD = {"takeback": "Lanzamiento", "loaded": "Trofeo", "acceleration": "Caída de la raqueta",
                         "recovery": "Aterrizaje"}


def fmt(v, d=0):
    if v is None or not math.isfinite(v):
        return "—"
    return f"{v:,.{d}f}".replace(",", " ").replace(".", ",").replace(" ", ".")


def _rng(t, d=0, unit=""):
    return f"{fmt(t['p25'], d)}–{fmt(t['p75'], d)}{unit}"


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
        ("ready.knee_dom", lambda t: f"Rodillas a unos {fmt(t['median'])}° (estimación 2D)."),
    ]
    L["takeback"] = [
        ("stroke.t_takeback", lambda t: f"Empieza a preparar {fmt(t['median'], 2)} s antes del impacto ({_rng(t, 2)} s)."),
        ("stroke.takeback_after_opp", lambda t: f"Arranca {fmt(t['median'], 2)} s después del golpe de la rival."),
        ("stroke.takeback_vs_bounce", lambda t: (f"Lo hace {fmt(abs(t['median']), 2)} s antes del bote." if t["median"] < 0 else
                                                 f"Lo hace {fmt(t['median'], 2)} s después del bote.")),
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
    ]
    L["acceleration"] = [
        ("stroke.t_acceleration", lambda t: f"Empieza a acelerar {fmt(t['median'], 2)} s antes del impacto."),
        ("stroke.wrist_drop", lambda t: f"Antes deja caer la mano un {fmt(t['median'])} % de su altura ({_rng(t)} %)."),
        ("acceleration.racket_head_vs_wrist", lambda t: (f"La cabeza de la raqueta cae por debajo de la mano ({fmt(-t['median'])} %)." if t["median"] < -2 else
                                                         "La cabeza de la raqueta sigue a la altura de la mano o por encima.")),
        ("acceleration.racket_forearm", lambda t: f"Ángulo antebrazo–raqueta de {fmt(t['median'])}° (retraso de la muñeca)."),
        ("stroke.dur_forward", lambda t: f"Del armado al impacto tarda {fmt(t['median'], 2)} s ({_rng(t, 2)} s)."),
    ]
    L["impact"] = [
        ("impact.wrist_dom_height", lambda t: f"Golpea con la mano a un {fmt(t['median'])} % de su altura ({_rng(t)} %)."),
        ("impact.wrist_dom_lateral", lambda t: f"Separada del cuerpo: la mano a {fmt(t['median'])} % de su altura de la cadera."),
        ("impact.elbow_dom", lambda t: f"Codo a {fmt(t['median'])}° ({'brazo casi recto' if t['median'] >= 150 else 'brazo flexionado'})."),
        ("stroke.swing_low_to_high", lambda t: f"Llega a la bola subiendo: trayectoria de la mano de {fmt(t['median'])}° hacia arriba."),
        ("impact.trunk_tilt", lambda t: (f"Tronco inclinado {fmt(abs(t['median']))}° hacia su {'lado del brazo' if t['median'] > 0 else 'lado contrario'}."
                                         if abs(t["median"]) >= 4 else "Tronco vertical.")),
        ("impact.head_over_base", lambda t: ("Cabeza centrada sobre los pies." if abs(t["median"]) < 4 else
                                             f"Cabeza desplazada un {fmt(abs(t['median']))} % hacia su {'lado del brazo' if t['median'] > 0 else 'lado contrario'}.")),
        ("impact.body_height", lambda t: f"Cuerpo a un {fmt(t['median'])} % de su altura de pie."),
        ("impact.base_m", lambda t: f"Base de {fmt(t['median'], 2)} m ({_rng(t, 2)} m)."),
    ]
    L["extension"] = [
        ("extension.arm_extension", lambda t: f"Brazo extendido al {fmt(t['median'])} % hacia delante tras el contacto."),
        ("stroke.swing_rise_after", lambda t: f"La mano sube un {fmt(t['median'])} % de su altura en los 150 ms siguientes."),
    ]
    L["finish"] = [
        ("stroke.t_finish", lambda t: f"Termina {fmt(t['median'], 2)} s después del impacto."),
        ("finish.wrist_dom_vs_shoulder", lambda t: f"Mano {'por encima' if t['median'] > 0 else 'por debajo'} del hombro ({fmt(abs(t['median']))} %)."),
        ("finish.wrist_dom_lateral", lambda t: f"Mano al {'lado contrario' if t['median'] < 0 else 'lado de su brazo'} del cuerpo."),
        ("finish.face_tilt", lambda t: f"Cara de la raqueta {'cerrada' if t['median'] >= 0 else 'abierta'} {fmt(abs(t['median']))}°."),
    ]
    L["recovery"] = [
        ("footwork.recovery_to_centre_m", lambda t: f"En el segundo siguiente vuelve {fmt(t['median'], 1)} m hacia el centro."),
    ]
    return L


LINES = _lines()
CLASS_TEXT = {
    "stance_loaded": "Apoyo al armar", "stance_impact": "Apoyo en el impacto", "finish": "Terminación", "arm": "Brazo",
    "takeback": "Preparación", "ready_hands": "Manos en la espera", "movement": "Cómo llega a la bola",
    "swing": "Trayectoria",
}
CLASS_PHASE = {"ready_hands": "ready", "takeback": "takeback", "stance_loaded": "loaded", "stance_impact": "impact",
               "arm": "impact", "finish": "finish", "movement": "impact", "swing": "acceleration"}


def _class_line(c: dict) -> str | None:
    if not c or not c.get("n"):
        return None
    tot = c["n"]
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
        # the effects of this situation on this phase that no template covers
        for key, e in eff.items():
            if key.split(".")[0] == p and not any(l["key"] == key for l in lines):
                t = _t(model, key)
                lines.append({"key": key, "text": f"{t['name']}: {fmt(t['median'] + e['diff'], 1)}{_u(t['unit'])} "
                              f"(habitual {fmt(t['median'], 1)}{_u(t['unit'])}).", "rel": t["rel"], "n": e["n"],
                              "change": {"diff": round(e["diff"], 3), "unit": t["unit"], "ref": e["ref"]}})
        skel = ((var or {}).get("skeleton") or {}).get(p) or model["skeleton"].get(p)
        cards.append({"phase": p, "title": title, "lines": lines, "skeleton": skel,
                      "changes": sum(1 for l in lines if l["change"])})
    return cards


def _u(unit: str) -> str:
    return "" if not unit else unit if unit in ("°", "%") else " " + unit


def change_text(model: dict, e: dict) -> str:
    """'Giro de hombros en el armado: −8° respecto a bola media'."""
    t = model["typical"][e["key"]]
    ph = PHASE_TITLES.get(e["key"].split(".")[0], "")
    d = 2 if t["unit"] in ("s", "m", "m/s", "") else 0
    sign = "+" if e["diff"] > 0 else "−"
    return f"{t['name']}{(' · ' + ph.lower()) if ph else ''}: {sign}{fmt(abs(e['diff']), d)}{_u(t['unit'])} respecto a «{e['ref']}»"


def summary(model: dict, stroke: str) -> list[str]:
    """Her stroke in a few sentences: the classes that define it and her constants."""
    out = []
    c = model["classes"]
    def top(ck):
        x = c.get(ck)
        if not x or not x["counts"]:
            return None
        k, v = next(iter(x["counts"].items()))
        return k, round(100 * v / x["n"]), x["n"]
    for ck, txt in (("stance_impact", "Apoyo en el impacto"), ("finish", "Terminación"), ("takeback", "Preparación"),
                    ("arm", "Brazo en el impacto"), ("movement", "Llega a la bola")):
        t = top(ck)
        if t:
            out.append(f"{txt}: {t[0]} ({t[1]} % de {t[2]} golpes).")
    tf = _t(model, "stroke.dur_forward")
    tp = _t(model, "stroke.dur_preparation")
    if tf and tp:
        out.append(f"Ritmo: prepara en {fmt(tp['median'], 2)} s y acelera en {fmt(tf['median'], 2)} s.")
    n_const = len([k for k in model["constants"] if model["typical"][k]["rel"] >= 2])
    n_eff = len({e["key"] for e in model["effects"]})
    out.append(f"{n_const} rasgos se mantienen en todas las situaciones (su técnica de base) y {n_eff} cambian según la bola.")
    return out


NOT_MEASURABLE = [
    "Empuñadura exacta (en espera y al golpear): la mano mide pocos píxeles en la retransmisión.",
    "Impacto delante o detrás del cuerpo: es la dirección hacia la cámara; solo se estima en 3D.",
    "Velocidad de la raqueta y de la bola, y efecto (liftado/cortado): sale borroso a 25-60 fotogramas por segundo.",
    "Cara de la raqueta justo en el impacto: es una estimación interpolada (desenfoque).",
    "Flexión de rodillas exacta: escorzo desde detrás; se usa la altura de la cadera.",
]


def model_view(model: dict, stroke: str) -> dict:
    """Everything the 'Su golpe' screen needs, computed once in Python."""
    variants = {}
    for fk, lvls in model["variants"].items():
        for lv, v in lvls.items():
            variants[f"{fk}|{lv}"] = {
                "factor": fk, "factor_name": FACTORS[fk][0], "level": lv, "n": v["n"], "share": v["share"], "usual": v["usual"],
                "cards": phase_cards(model, stroke, fk, lv), "strokes": v["strokes"],
                "changes": [change_text(model, e) for e in v["effects"]],
            }
    return {"summary": summary(model, stroke), "cards": phase_cards(model, stroke), "variants": variants,
            "typical_strokes": model.get("typical_strokes", []), "n": model["n_strokes"], "n_near": model["n_near"],
            "footwork": model["footwork"], "not_measurable": NOT_MEASURABLE,
            "factors": {fk: FACTORS[fk][0] for fk in model["variants"]}}
