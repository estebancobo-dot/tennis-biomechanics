"""Findings and conclusions in Python, for the exported videos and the PDF summary.

Mirrors the logic of the HTML report (report_template.html: DIST, repr, PAIRS, discover, verdict,
conclusions), which runs in the browser. Input: the output of report.prepare().
"""
import math
from dataclasses import dataclass, field

import numpy as np

MEANING = {
    "xf": ("más separación tronco–cadera en el armado: más energía elástica acumulada", "menos separación tronco–cadera: cadera y tronco giran juntos, menos «muelle»"),
    "sh": ("más giro de hombros en el armado: preparación más completa", "menos giro de hombros: preparación más corta"),
    "xf3d": ("más separación tronco–cadera (3D, experimental)", "menos separación tronco–cadera (3D, experimental)"),
    "sh3d": ("más giro de hombros (3D, experimental)", "menos giro de hombros (3D, experimental)"),
    "knee": ("baja más la cadera: más carga de piernas", "golpea más erguida: menos uso de piernas"),
    "elbow": ("brazo más extendido en el impacto", "codo más flexionado: impacto más pegado al cuerpo"),
    "elbowNon": ("segundo brazo más extendido en el impacto", "segundo brazo más flexionado en el impacto"),
    "offArm": ("brazo libre más extendido en el armado", "brazo libre más recogido en el armado"),
    "lat": ("impacta más separada del cuerpo", "impacta más cerca del cuerpo (más «atascada»)"),
    "contactH": ("impacta más alto respecto a su cuerpo", "impacta más bajo respecto a su cuerpo"),
    "head": ("la cabeza se mueve más en el impacto: menos estabilidad", "cabeza más estable en el impacto"),
    "finishH": ("terminación más alta", "terminación más baja o más corta"),
    "rHead": ("cabeza de la raqueta más alta en el armado", "raqueta más baja en el armado"),
    "rDrop": ("deja caer más la raqueta antes de acelerar: más recorrido de abajo arriba", "menos caída de la raqueta: swing más plano"),
    "rElevImp": ("raqueta más levantada en el impacto", "raqueta más horizontal en el impacto"),
    "rFaceArm": ("cara más cerrada en el armado", "cara más abierta en el armado"),
    "rFaceImp": ("cara más cerrada en el impacto: la bola tiende a salir más baja y con más efecto", "cara más abierta en el impacto: la bola tiende a salir más alta y larga"),
    "rFaceFin": ("cara más cerrada en la terminación: más giro de muñeca", "menos giro de muñeca en la terminación"),
    "rYawImp": ("cara orientada más hacia el lado de su brazo dominante", "cara orientada más hacia el lado contrario"),
    "split": ("aterriza el split step más tarde respecto al golpe rival", "aterriza el split step antes"),
    "base": ("base más ancha en el armado", "base más estrecha en el armado"),
    "baseM": ("base más ancha en el impacto", "base más estrecha en el impacto"),
    "disp": ("llega con más desplazamiento", "se desplaza menos para llegar"),
    "recov": ("tarda más en iniciar la recuperación", "recupera antes"),
    "shotDepth": ("su bola bota más lejos del fondo rival: golpes más cortos", "su bola bota más cerca del fondo rival: golpes más profundos"),
    "trophyKnee": ("más flexión de piernas en el trofeo", "menos flexión de piernas en el trofeo"),
    "trophyTilt": ("más inclinación de hombros en el trofeo", "hombros más horizontales en el trofeo"),
    "toss": ("brazo de lanzamiento más alto", "brazo de lanzamiento más bajo"),
    "landing": ("aterriza más dentro de la pista", "aterriza más atrás"),
}

PHASES = [("ready", "Espera", "Espera / split step"), ("takeback", "Preparación", "Inicio del takeback"),
          ("loaded", "Armado", "Armado completo"), ("acceleration", "Aceleración", "Inicio de aceleración"),
          ("impact", "Impacto", "Impacto"), ("extension", "Extensión", "Extensión"),
          ("finish", "Terminación", "Terminación"), ("recovery", "Recuperación", "Recuperación")]
PHASES_OVERHEAD = {"takeback": ("Lanzamiento", "Inicio del lanzamiento"), "loaded": ("Trofeo", "Posición de trofeo"),
                   "acceleration": ("Caída", "Caída de la raqueta"), "recovery": ("Aterrizaje", "Aterrizaje / recuperación")}


def phases_for(stroke: str) -> list[tuple[str, str, str]]:
    if stroke != "overhead":
        return PHASES
    return [(k, *PHASES_OVERHEAD.get(k, (n, lg))) for k, n, lg in PHASES]


def meaning(k: str, d: float) -> str:
    m = MEANING.get(k)
    return "" if not m else m[0] if d > 0 else m[1]


def fmt(v, d=0) -> str:
    """Spanish number format (decimal comma)."""
    if v is None or not math.isfinite(v):
        return "—"
    s = f"{v:,.{d}f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    return s


def sign(v: float) -> str:
    return "+" if v > 0 else "−" if v < 0 else "±"


def unit_str(m: dict) -> str:
    return "°" if m["unit"] == "°" else " " + m["unit"]


def fmt_metric(m: dict, v) -> str:
    return "—" if v is None or not math.isfinite(v) else f"{fmt(v, m['dec'])}{unit_str(m)}"


def _vals(strokes, k):
    return np.array([s["m"][k] for s in strokes if s["m"].get(k) is not None and math.isfinite(s["m"][k])], float)


def distributions(data: dict) -> dict:
    """Per metric: p10, p50, p90, sd, n over all strokes (as DIST in the report)."""
    out = {}
    for m in data["metrics"]:
        v = _vals(data["strokes"], m["k"])
        out[m["k"]] = None if not len(v) else {
            "p10": float(np.quantile(v, .1)), "p50": float(np.quantile(v, .5)), "p90": float(np.quantile(v, .9)),
            "sd": float(v.std()) if len(v) > 1 and v.std() > 0 else m["noise"], "n": int(len(v))}
    return out


def representativeness(data: dict, dist: dict) -> None:
    """s['repr'] in 0..1: closeness of every metric to her median (1 = the typical stroke)."""
    for s in data["strokes"]:
        z = [((s["m"][m["k"]] - dist[m["k"]]["p50"]) / dist[m["k"]]["sd"]) ** 2 for m in data["metrics"]
             if dist.get(m["k"]) and s["m"].get(m["k"]) is not None and math.isfinite(s["m"][m["k"]])]
        # a stroke with few measured metrics (far side, racket unseen) cannot be "the typical one"
        avail = [m for m in data["metrics"] if dist.get(m["k"])]
        cover = len(z) / len(avail) if avail else 0.0
        s["repr"] = (1 / (1 + math.sqrt(sum(z) / len(z)))) * min(1.0, cover / 0.7) if z else 0.0
        if s.get("side") == "far":
            s["repr"] *= 0.3


def show_score(s: dict) -> float:
    """Order for galleries and reels: typical and well captured first."""
    return s.get("repr", 0) * .6 + s.get("quality", 0) * .4


@dataclass
class Effect:
    d: float
    lo: float
    hi: float
    na: int
    nb: int
    ma: float
    mb: float


def effect(k: str, A: list, B: list) -> Effect:
    a, b = _vals(A, k), _vals(B, k)
    ma = float(a.mean()) if len(a) else math.nan
    mb = float(b.mean()) if len(b) else math.nan
    if len(a) < 5 or len(b) < 5:
        return Effect(math.nan, math.nan, math.nan, len(a), len(b), ma, mb)
    d = mb - ma
    se = math.sqrt(a.var() / len(a) + b.var() / len(b))
    return Effect(d, d - 1.96 * se, d + 1.96 * se, len(a), len(b), ma, mb)


def verdict(e: Effect, noise: float) -> tuple[str, str]:
    """(class, text): good = real difference, warn = probable, crit = within the noise / few strokes."""
    if not math.isfinite(e.d):
        return "crit", "Pocos golpes"
    z, sure = abs(e.d) / noise, math.copysign(1, e.lo) == math.copysign(1, e.hi)
    if z > 1 and sure:
        return "good", "Diferencia real"
    if z > 1 or (sure and z > .6):
        return "warn", "Probable"
    return "crit", "Dentro del ruido"


def _pairs(strokes: list) -> list[dict]:
    max_set = max([1] + [s.get("set") or 0 for s in strokes])
    has_t = lambda s: s.get("tAvail") is not None
    return [
        dict(key="fatiga", t="al final del partido", c="último tercio frente al primero", neutral=True,
             A=lambda s: s["frac"] is not None and s["frac"] < 1 / 3, B=lambda s: s["frac"] is not None and s["frac"] >= 2 / 3),
        dict(key="sets", t="en el último set", c="último set frente al primero", neutral=True,
             A=lambda s: s.get("set") == 1, B=lambda s: max_set > 1 and s.get("set") == max_set),
        dict(key="presion", t="bajo presión", c="puntos de presión frente al resto", neutral=True,
             A=lambda s: s.get("pressure") is False, B=lambda s: s.get("pressure") is True),
        # split step is timed from the opponent's hit: with a faster ball it changes by definition
        dict(key="rapida", t="con bola rápida", c="bola rápida frente a lenta", neutral=False, skip=["split"],
             A=lambda s: has_t(s) and not s.get("fast"), B=lambda s: bool(s.get("fast"))),
        dict(key="resultado", t="en los errores", c="errores frente a golpes que siguen el punto o ganan", neutral=False,
             A=lambda s: s.get("outcome") in ("sigue", "ganador"), B=lambda s: s.get("outcome") == "error"),
    ]


@dataclass
class Finding:
    k: str
    title: str          # "X-factor al final del partido"
    context: str        # "último tercio frente al primero · bolas neutras"
    A: list = field(repr=False)
    B: list = field(repr=False)
    effect: Effect = None
    verdict: tuple = ("crit", "")
    score: float = 0.0

    def sentence(self, metric: dict) -> str:
        e = self.effect
        return (f"{self.title}: {sign(e.d)}{fmt(abs(e.d), metric['dec'])}{unit_str(metric)} — {meaning(self.k, e.d)} "
                f"({fmt(e.ma, metric['dec'])} → {fmt(e.mb, metric['dec'])}; {self.context}, n={e.na}/{e.nb})")


def discover(data: dict, top=10) -> list[Finding]:
    """The largest differences between situations, ranked by size in noise units × reliability."""
    strokes, out = data["strokes"], []
    for p in _pairs(strokes):
        for m in data["metrics"]:
            if m["k"] in p.get("skip", []) or m.get("est"):     # estimates are never findings
                continue
            neu = p["neutral"]
            A = [s for s in strokes if p["A"](s) and (not neu or s["sit"].get("neutra"))]
            B = [s for s in strokes if p["B"](s) and (not neu or s["sit"].get("neutra"))]
            e = effect(m["k"], A, B)
            if neu and not math.isfinite(e.d):
                neu = False
                A, B = [s for s in strokes if p["A"](s)], [s for s in strokes if p["B"](s)]
                e = effect(m["k"], A, B)
            if not math.isfinite(e.d):
                continue
            z = abs(e.d) / m["noise"]
            sure = math.copysign(1, e.lo) == math.copysign(1, e.hi)
            out.append(Finding(m["k"], f"{m['name']} {p['t']}", f"{p['c']} · {'bolas neutras' if neu else 'todas las bolas'}",
                               A, B, e, verdict(e, m["noise"]), z * (1 if sure else .5) * m["rel"] / 3))
    out.sort(key=lambda f: -f.score)
    return out[:top]


@dataclass
class Conclusion:
    text: str
    confidence: str     # text of the confidence chip
    level: str          # good / warn / crit
    strokes: list = field(default_factory=list, repr=False)    # video evidence (best first)
    finding: Finding | None = None


def conclusions(data: dict, dist: dict, finds: list[Finding]) -> list[Conclusion]:
    st, n = data["strokes"], len(data["strokes"])
    MK = {m["k"]: m for m in data["metrics"]}
    best = lambda a: sorted(a, key=lambda s: -show_score(s))
    pct = lambda a, f: 100 * sum(1 for s in a if f(s)) / len(a) if a else math.nan
    out = []
    if n < 10:
        out.append(Conclusion(f"Con {n} golpe{'' if n == 1 else 's'} solo se describe lo observado; las comparaciones necesitan "
                              "al menos 5 golpes por grupo y el ruido de medida, 20 con bola neutra.", "pocos datos", "crit"))
    counts = sorted(((k, sum(1 for s in st if s.get("stance") == k)) for k in ("abierto", "semiabierto", "cerrado")), key=lambda x: -x[1])
    nst = sum(c for _, c in counts)
    if nst:
        extra = f"; {counts[1][0]} {fmt(100 * counts[1][1] / nst)} %" if counts[1][1] else ""
        out.append(Conclusion(f"Apoyo más frecuente: {counts[0][0]} ({fmt(100 * counts[0][1] / nst)} % de {nst} golpes{extra}).",
                              "fiable" if nst >= 20 else "orientativo", "good" if nst >= 20 else "warn",
                              best([s for s in st if s.get("stance") == counts[0][0]])))
    for ph, txt, k in (("loaded", "en el armado", "rFaceArm"), ("impact", "en el impacto", "rFaceImp"), ("finish", "en la terminación", "rFaceFin")):
        labs = [s["face"].get(ph) for s in st if (s.get("face") or {}).get(ph)]
        if not labs:
            continue
        lab = max(set(labs), key=labs.count)
        md = (dist.get(k) or {}).get("p50") if k in MK else None
        face = f", cara {'cerrada' if md >= 0 else 'abierta'} {fmt(abs(md))}° (mediana)" if md is not None else ""
        out.append(Conclusion(f"Las cuerdas apuntan {txt} hacia {lab} en {fmt(100 * labs.count(lab) / len(labs))} % de los golpes{face}.",
                              "estimada (desenfoque)" if ph == "impact" else "media" if len(labs) >= 20 else "orientativo",
                              "crit" if ph == "impact" else "warn", best([s for s in st if (s.get("face") or {}).get(ph) == lab])))
    dr = [s for s in st if s.get("shotDir")]
    if dr:
        c = lambda k: fmt(pct(dr, lambda s: s["shotDir"] == k))
        known_in = [s for s in st if s.get("shotIn") is not None]
        depth = f"; bota a {fmt(dist['shotDepth']['p50'], 1)} m del fondo rival (mediana)" if dist.get("shotDepth") and "shotDepth" in MK else ""
        out.append(Conclusion(f"Dirección de su golpe: {c('cruzada')} % cruzada, {c('paralela')} % paralela, {c('al centro')} % al centro; "
                              f"{fmt(pct(known_in, lambda s: s['shotIn'] is False))} % fuera{depth}.",
                              "fiable" if len(dr) >= 20 else "orientativo", "good" if len(dr) >= 20 else "warn", best(dr)))
    known = [s for s in st if s.get("outcome")]
    if known:
        w = [s for s in known if s["outcome"] == "ganador"]
        out.append(Conclusion(f"Resultado conocido en {len(known)} de {n} golpes: {len(w)} ganadores probables, "
                              f"{sum(1 for s in known if s.get('outcomeDetail') == 'out')} errores fuera, "
                              f"{sum(1 for s in known if s.get('outcomeDetail') == 'net')} a la red; el resto sigue el punto.",
                              "media" if len(known) >= 20 else "orientativo", "warn", best(w)))
    ch = [s for s in st if s.get("chainOK") is not None]
    if ch:
        out.append(Conclusion(f"Cadena cinética en orden (pelvis → tronco → brazo → antebrazo) en {fmt(pct(ch, lambda s: s['chainOK']))} % de {len(ch)} golpes.",
                              "media", "warn", best([s for s in ch if s["chainOK"]])))
    ta = [s["tAvail"] for s in st if s.get("tAvail") is not None]
    if ta:
        out.append(Conclusion(f"Tiempo disponible entre el golpe del rival y el suyo: mediana {fmt(float(np.median(ta)), 2)} s "
                              f"({fmt(pct([s for s in st if s.get('tAvail') is not None], lambda s: s.get('fast')))} % de bolas rápidas, < 1,15 s).",
                              "fiable" if len(ta) >= 20 else "orientativo", "good" if len(ta) >= 20 else "warn"))
    if "baseM" in MK and dist.get("baseM"):
        b = dist["baseM"]
        out.append(Conclusion(f"Base en el impacto: mediana {fmt_metric(MK['baseM'], b['p50'])} (p10–p90 {fmt(b['p10'], 2)}–{fmt(b['p90'], 2)} m, {b['n']} golpes).",
                              "fiable" if b["n"] >= 20 else "orientativo", "good" if b["n"] >= 20 else "warn"))
    for f in finds:
        if f.verdict[0] in ("good", "warn"):
            out.append(Conclusion(f.sentence(MK[f.k]) + ".", "diferencia real" if f.verdict[0] == "good" else "probable",
                                  f.verdict[0], best(f.B), f))
    if n >= 10 and not any(f.verdict[0] != "crit" for f in finds):
        out.append(Conclusion("Ninguna diferencia entre situaciones (fatiga, presión, bola rápida) supera el ruido de medida.",
                              "según los datos actuales", "warn"))
    return out


def typical(strokes: list, k: str, noise: float):
    """The stroke that best represents a group for one metric: near its median, well captured."""
    v = [s for s in strokes if s["m"].get(k) is not None and math.isfinite(s["m"][k])]
    if not v:
        return None
    md = float(np.median([s["m"][k] for s in v]))
    return min(v, key=lambda s: abs(s["m"][k] - md) / (noise or 1) - s.get("quality", 0))
