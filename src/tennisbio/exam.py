"""Internal exam: what coaches say about her forehand (docs/aprendido_entrenadores.md, R1-R25),
checked against her measured strokes. Never shown in her report (requirement 6): it only tells
whether our measurements agree with expert eyes. A claim confirmed is evidence the measurement
works; one refuted is a lead (the measurement or the coach may be wrong); some are not decidable
from TV and the app must not pretend otherwise."""
from __future__ import annotations

import numpy as np

CONFIRMS, REFUTES, UNDECIDABLE, FEW = "confirma", "refuta", "no decidible", "pocos datos"


def _num(vals, k):
    return np.array([v[k] for v in vals if isinstance(v.get(k), (int, float)) and not isinstance(v.get(k), bool)], float)


def _cls(vals, k):
    return [v[k] for v in vals if v.get(k) is not None]


def _share(xs, pred):
    return sum(1 for x in xs if pred(x)) / len(xs) if xs else float("nan")


def _verdict(n, min_n, ok, txt):
    if n < min_n:
        return FEW, f"{n} golpes con el dato (hacen falta {min_n})"
    return (CONFIRMS if ok else REFUTES), txt


def claims(vals: list[dict], min_n: int) -> list[tuple[str, str, str, str]]:
    """(id, claim, verdict, detail) for each decidable claim."""
    out = []

    def add(rid, text, res):
        out.append((rid, text, *res))

    sw = _cls(vals, "class.swing")
    add("R1", "Golpe liftado de trayectoria moderada, no extrema",
        _verdict(len(sw), min_n, _share(sw, lambda c: c.startswith("liftado")) > 0.6 and np.median(_num(vals, "stroke.swing_low_to_high") if len(_num(vals, "stroke.swing_low_to_high")) else [0]) < 60,
                 f"liftado {_share(sw, lambda c: c.startswith('liftado')):.0%}, inclinación mediana "
                 f"{np.median(_num(vals, 'stroke.swing_low_to_high')) if len(_num(vals, 'stroke.swing_low_to_high')) else float('nan'):.0f}°"))
    rh = _cls(vals, "class.ready_hands")
    add("R2", "Dos manos en la raqueta en la espera (≥ 80 %)",
        _verdict(len(rh), min_n, _share(rh, lambda c: "dos manos" in c) >= 0.8, f"dos manos {_share(rh, lambda c: 'dos manos' in c):.0%}"))
    tb = _num(vals, "stroke.takeback_vs_bounce")
    add("R4", "Empieza a preparar antes del bote", _verdict(len(tb), min_n, len(tb) and np.median(tb) < 0,
                                                             f"mediana {np.median(tb) if len(tb) else float('nan'):+.2f} s respecto al bote"))
    en = _num(vals, "loaded.elbow_non")
    add("R6", "Brazo libre casi extendido en el armado (codo 130-170°)",
        _verdict(len(en), min_n, len(en) and 130 <= np.median(en) <= 170, f"codo libre mediano {np.median(en) if len(en) else float('nan'):.0f}°"))
    wl = _num(vals, "loaded.wrist_non_lateral")
    add("R7", "La mano libre pasa al lado del brazo en el armado", _verdict(len(wl), min_n, len(wl) and np.median(wl) > 0,
                                                                         f"posición lateral mediana {np.median(wl) if len(wl) else float('nan'):+.0f}"))
    lb = _num(vals, "stroke.loaded_vs_bounce")
    add("R10", "Armado completo cuando bota la bola (±0,1 s)", _verdict(len(lb), min_n, len(lb) and abs(np.median(lb)) <= 0.1,
                                                                      f"mediana {np.median(lb) if len(lb) else float('nan'):+.2f} s respecto al bote"))
    fast = [v.get("stroke.loaded_vs_bounce") for v in vals if v.get("class.ball_speed") in ("rápida", "muy rápida")]
    slow = [v.get("stroke.loaded_vs_bounce") for v in vals if v.get("class.ball_speed") in ("lenta", "media")]
    fast, slow = [x for x in fast if x is not None], [x for x in slow if x is not None]
    add("R11", "Con bola rápida sigue armando a tiempo (no más de 0,1 s más tarde)",
        _verdict(min(len(fast), len(slow)), min_n, len(fast) and len(slow) and np.median(fast) - np.median(slow) <= 0.1,
                 f"rápida {np.median(fast) if fast else float('nan'):+.2f} s, lenta {np.median(slow) if slow else float('nan'):+.2f} s"))
    hi = [v.get("class.move_direction") for v in vals if v.get("class.ball_height") in ("pecho-hombro", "por encima del hombro")]
    lo = [v.get("class.move_direction") for v in vals if v.get("class.ball_height") in ("rodilla", "cadera", "cintura-pecho")]
    hi, lo = [x for x in hi if x], [x for x in lo if x]
    add("R12", "Con bola alta se va más hacia atrás", _verdict(min(len(hi), len(lo)), min_n,
                                                             _share(hi, lambda c: "atrás" in c) > _share(lo, lambda c: "atrás" in c),
                                                             f"hacia atrás: alta {_share(hi, lambda c: 'atrás' in c):.0%}, resto {_share(lo, lambda c: 'atrás' in c):.0%}"))
    wd = _num(vals, "stroke.wrist_drop")
    add("R13", "La mano cae antes de acelerar en la mayoría", _verdict(len(wd), min_n, _share(list(wd), lambda x: x > 0) > 0.5,
                                                                     f"cae en el {_share(list(wd), lambda x: x > 0):.0%}"))
    d = [v["loaded.hip_turn"] - v["impact.hip_turn"] for v in vals
         if isinstance(v.get("loaded.hip_turn"), (int, float)) and isinstance(v.get("impact.hip_turn"), (int, float))]
    add("R14", "La cadera gira hacia la pista entre armado e impacto (> 10°)", _verdict(len(d), min_n, len(d) and np.median(d) > 10,
                                                                                      f"giro mediano {np.median(d) if d else float('nan'):.0f}°"))
    arm = _cls(vals, "class.arm")
    add("R15", "Contacto con el codo flexionado (doble flexión mayoritaria)",
        _verdict(len(arm), min_n, _share(arm, lambda c: "doble" in c) > 0.5, f"doble flexión {_share(arm, lambda c: 'doble' in c):.0%}"))
    fin = _cls(vals, "class.finish")
    top = max(set(fin), key=fin.count) if fin else None
    add("R17", "La terminación más frecuente es sobre el hombro", _verdict(len(fin), min_n, top == "sobre el hombro", f"la más frecuente: {top}"))
    tk = _cls(vals, "class.takeback")
    add("R18", "Preparación compacta", _verdict(len(tk), min_n, _share(tk, lambda c: c == "compacta") > 0.5,
                                                 f"compacta {_share(tk, lambda c: c == 'compacta'):.0%}"))
    stc = _cls(vals, "class.stance_impact")
    add("R20", "Más apoyos cerrados o neutros que el circuito (~16 %)",
        _verdict(len(stc), min_n, _share(stc, lambda c: c in ("cerrado", "neutro")) > 0.25,
                 f"cerrado o neutro {_share(stc, lambda c: c in ('cerrado', 'neutro')):.0%}"))
    w = [(v["loaded.com_over_feet"], v["impact.com_over_feet"]) for v in vals
         if isinstance(v.get("loaded.com_over_feet"), (int, float)) and isinstance(v.get("impact.com_over_feet"), (int, float))]
    add("R21", "El peso pasa del pie de atrás al de delante", _verdict(len(w), min_n, w and np.median([b - a for a, b in w]) > 0.2,
                                                                     f"cambio mediano {np.median([b - a for a, b in w]) if w else float('nan'):+.2f}"))
    ch = [v["chain.proximal_to_distal"] for v in vals if v.get("chain.proximal_to_distal") is not None]
    add("R23", "La cadera llega a su máximo giro antes que los hombros", _verdict(len(_num(vals, "stroke.shoulders_open_first")), min_n,
        len(_num(vals, "stroke.shoulders_open_first")) and np.median(_num(vals, "stroke.shoulders_open_first")) > 0,
        f"hombros {np.median(_num(vals, 'stroke.shoulders_open_first')) if len(_num(vals, 'stroke.shoulders_open_first')) else float('nan'):+.2f} s "
        f"después de la cadera; orden completo de la cadena en el {_share(ch, bool):.0%}"))
    for rid, text in (("R5", "Brazo relajado (tensión muscular)"), ("R16", "Cuerdas casi hacia el suelo en el contacto"),
                      ("R3", "Empuñadura semioccidental exacta")):
        out.append((rid, text, UNDECIDABLE, "no se ve desde la tele: la app no lo afirma"))
    return out
