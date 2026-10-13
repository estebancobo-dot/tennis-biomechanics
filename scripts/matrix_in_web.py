"""Where each item of the user's master matrix (docs/matriz_cobertura.md, section 6) is in the web
report, and whether a given run actually shows it. Read from the code (what each screen can show)
and from a run's strokes.json (how many strokes carry the value), not from memory.

    python scripts/matrix_in_web.py [strokes.json] > docs/matriz_en_la_web.md
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio import practice  # noqa: E402
from tennisbio.audit import _code_ref, _matches, _plain, parse_matrix, stroke_values  # noqa: E402
from tennisbio.explain import CLASS_PHASE, COACH, LINES, NOT_MEASURABLE, PRIMARY  # noqa: E402
from tennisbio.model import MIN_N  # noqa: E402
from tennisbio.report import FEET_KEYS, METRICS  # noqa: E402

PER_STROKE_CLASS = {"finish": "Terminación", "movement": "Cómo llega", "ball_phase": "Bola en el contacto",
                    "contact_type": "Bola en el contacto", "stance_impact": "Apoyo", "shot_type": "Su golpe (dirección)"}
METRIC_SRC = {spec[-1]: spec[1] for spec in METRICS.values() if spec[-1]}
LINE_KEYS = {k: p for p, lines in LINES.items() for k, _ in lines}
NM = _plain(" ".join(NOT_MEASURABLE))
PRACTICE = {**practice.SIDE_METRICS, **practice.FRONT_METRICS, **practice.D3_METRICS}


def where(ident: str) -> list[str]:
    """Places of the report that can show this matrix identifier (short or dotted name)."""
    k = ident.split(".")[-1].rstrip("*")
    out = []
    src = [name for m, name in METRIC_SRC.items() if _matches(ident, m) or m.startswith(k + "_")]
    if src:
        out.append(f"Análisis de golpe › métricas ({', '.join(sorted(set(src)))}), Explorador, Comparativas")
    if any(_matches(ident, f) or _matches(ident, "footwork." + f) for f in FEET_KEYS):
        out.append("Análisis de golpe › «Sus pies en este golpe»")
    cls = [c for c in PER_STROKE_CLASS if _matches(ident, "class." + c)]
    if cls:
        out.append(f"Análisis de golpe › ficha ({', '.join(PER_STROKE_CLASS[c] for c in cls)}), filtros de la Videoteca")
    for lk, p in LINE_KEYS.items():
        if _matches(ident, lk):
            vis = "a la vista" if lk in PRIMARY.get(p, []) else "plegada en «Más medidas»"
            out.append(f"Su derecha › {p} ({vis}, con ≥ {MIN_N} golpes)")
    cp = [c for c in CLASS_PHASE if _matches(ident, "class." + c)]
    for c in cp:
        out.append(f"Su derecha › {CLASS_PHASE[c]} (porcentajes, con ≥ {MIN_N} golpes)")
    if k in PRACTICE:
        out.append("Vista lateral (entreno)")
    return out


def count(ident: str, vals: list[dict]) -> int:
    return sum(1 for v in vals if any(x is not None and not (isinstance(x, list) and not x) for kk, x in v.items()
                                      if _matches(ident, kk)))


def main():
    strokes = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")) if len(sys.argv) > 1 else []
    near = [s for s in strokes if s.get("stroke") == "forehand" and s.get("side") != "far"]
    vals = [stroke_values(s) for s in near]
    rows = [r for r in parse_matrix() if r["section"].startswith("6.")]
    out = ["# La matriz del usuario en la web", "",
           f"Generado por `scripts/matrix_in_web.py` a partir del código del informe y de {len(near)} derechas del lado cercano.",
           "", "| Elemento | Estado | Dónde está en la web | Golpes con el dato | ¿Se ve hoy? | Explicación / cómo hacerlo |",
           "|---|---|---|---|---|---|"]
    tally = {}
    for r in rows:
        keys = [i for i in r["ids"] if _code_ref(i) is None]
        places = sorted({p for k in keys for p in where(k)})
        n = max((count(k, vals) for k in keys), default=0)
        told = r["status"] == "✘" and any(w[:7] in NM for w in re.findall(r"\w+", _plain(r["element"])) if len(w) >= 6)
        if r["status"] == "✘":
            seen = "se dice «no medible»" if told else "NO (ni se dice)"
        elif not places:
            seen = "NO: no hay sitio en la web"
        elif any(p.startswith("Análisis de golpe") for p in places) and n:
            seen = f"sí, golpe a golpe ({n})"
        elif any(p.startswith("Vista lateral") for p in places):
            seen = "solo vista lateral"
        elif n >= MIN_N:
            seen = "sí, en Su derecha"
        else:
            seen = f"NO: hacen falta {MIN_N} golpes, hay {n}"
        coach = "sí" if any(_matches(k, c) or _matches(k, "class." + c) for k in keys for c in COACH) else "no"
        tally[seen.split(":")[0].split(",")[0]] = tally.get(seen.split(":")[0].split(",")[0], 0) + 1
        out.append(f"| {r['element']} | {r['status']} | {'; '.join(places) or '—'} | {n if keys else '—'} | {seen} | por qué: {coach}; cómo hacerlo: no |")
    out += ["", "## Recuento", ""] + [f"- {k}: {v}" for k, v in sorted(tally.items(), key=lambda kv: -kv[1])]
    print("\n".join(out))


if __name__ == "__main__":
    main()
