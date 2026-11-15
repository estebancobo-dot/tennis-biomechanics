"""P0.5a (15-11, #305): the new application's page (built from ui/ into app/p0/index.html, one self-contained file) with
its data put in, and a made-up example of those data for the tests and the repository's preview.

    python -m tennisbio.app.p0_app --ejemplo out.html
    python -m tennisbio.app.p0_app --beta <report index.html> <audit json> <queue estado.md> <matches json> out.html

The data contract is ui/src/contrato.ts. The beta's data still come through design/p0/build_app.py (the validated
mockup's builder, #305); P0.5b reads them straight from the analysis.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PAGE = Path(__file__).with_name("p0") / "index.html"
SLOT = "window.__TENNISBIO__ = /*DATOS*/null"
ROOT = Path(__file__).resolve().parents[3]


def pagina(datos: dict) -> str:
    """The application's page with `datos` in it. «</» is escaped so no text of the data can close the script."""
    html = PAGE.read_text(encoding="utf-8")
    if SLOT not in html:
        raise RuntimeError(f"{PAGE} no tiene el hueco de los datos: vuelve a construir ui/ (scripts/construir_ui.py)")
    js = json.dumps(datos, ensure_ascii=False).replace("</", "<\\/")
    return html.replace(SLOT, "window.__TENNISBIO__ = " + js, 1)


def ejemplo() -> dict:
    """Data that look like an analysis and are made up: no real player, match or measure (said on screen)."""
    jug, riv = "Jugadora de ejemplo", "Rival de ejemplo"
    partidos = [{"id": f"torneo-de-ejemplo-r{i}-{2026}", "rival": f"{riv} {i}", "personas": [jug, f"{riv} {i}"],
                 "analysed": i < 3, "surf": "dura", "torneo": "Torneo de ejemplo", "ronda": f"{i}.ª ronda",
                 "fecha": "2026", "near": 20 * i if i < 3 else 0, "far": 5 * i if i < 3 else 0} for i in (1, 2, 3)]
    fases = [{"id": pid, "title": t, "focus": f"Foco de ejemplo de la fase «{t}».", "when": "momento de ejemplo",
              "checks": [{"key": f"{pid}.medida_{k}", "label": f"Medida {k} de {t.lower()}", "unit": "°", "dec": 0,
                          "cue": "Una frase de ejemplo.", "mistake": "Un error típico de ejemplo.", "m": None}
                         for k in (1, 2, 3)]}
             for pid, t in (("ready", "Espera y split step"), ("takeback", "Inicio de la preparación"),
                            ("loaded", "Armado completo"), ("acceleration", "Caída e inicio de la aceleración"),
                            ("impact", "Impacto"), ("extension", "Extensión"), ("finish", "Terminación"),
                            ("recovery", "Recuperación"), ("feet", "Pies: del split step al golpe"))]
    golpes = [{"id": f"g{i}", "match": i % 2, "rival": partidos[i % 2]["rival"], "set": 1 + i % 3, "score": "30-15",
               "bits": ["rápida" if i % 2 else "lenta", "bola media"], "outcome": "en juego", "stance": "abierto",
               "movement": "en carrera" if i % 3 else "parada", "finish": "sobre el hombro", "quality": (i * 37) % 100,
               "repr": (i * 53) % 100, "fast": bool(i % 2), "m": {"sh": 60.0 + i, "xf": 15.0 + i % 5}} for i in range(12)]
    for g in golpes[:4]:
        g["trayectoria"] = _trayectoria_ejemplo()
    trabajos = [{"id": "prueba_ejemplo", "accion": "prueba", "partido": partidos[2]["id"], "estado": "en_marcha",
                 "donde": "kaggle", "nota": "fine: 40 % (ejemplo)"},
                {"id": "partido_ejemplo", "accion": "partido", "partido": partidos[2]["id"], "estado": "pendiente",
                 "donde": "", "nota": "falta la aprobación del usuario (#262)"},
                {"id": "hecho_ejemplo", "accion": "partido", "partido": partidos[0]["id"], "estado": "hecho",
                 "donde": "kaggle", "nota": ""}]
    return {
        "ejemplo": True, "generated": "ejemplo", "player": {"id": "ejemplo", "name": jug}, "stroke": "forehand",
        "known": ["Una diferencia conocida de ejemplo."], "conclusions": [], "findings": [],
        "metrics": {"sh": {"name": "Rotación de hombros", "unit": "°", "dec": 0, "rel": 2},
                    "xf": {"name": "X-factor", "unit": "°", "dec": 0, "rel": 2}},
        "situations": [{"id": "todas", "label": "Todas", "n": len(golpes), "m": {}}],
        "phases": fases, "plan": [], "symptoms": [], "not_tv": [["Fuerzas", "Solo cinemática desde la tele."]],
        "glossary": [], "strokes": golpes, "n_near": len(golpes), "n_far": 3,
        "players": [{"id": "ejemplo", "name": jug, "hand": "right", "backhand": "two_handed", "height_m": 1.8, "ficha": True}],
        "matches": partidos,
        "queue": {"head": "Última vuelta: ejemplo", "jobs": trabajos, "kaggle": {"used": 10.0, "total": 30.0},
                  "modal": {"left": 20.0, "total": 30.0}},
        "quality": {"total": {"score": 0.9, "ok": 90, "n": 100, "accepted": 20, "cells": 24, "unmeasured": 2},
                    "threshold": 0.8, "cells": [{"d": "Datos", "c": "Exactitud", "l": "nube", "score": None, "n": 0,
                                                 "ok": 0, "unmeasured": True, "accepted": False, "fail": [],
                                                 "how": "cómo se medirá (ejemplo)"}],
                    "counts": {"ok": 90, "falta": 10}, "fails": [{"name": "Comprobación de ejemplo", "detail": "—",
                                                                  "area": "Ejemplo"}],
                    "domains": {"Datos": {"score": 0.9}, "Pantallas": {"score": None}}},
        "run_info": {},
    }


def _trayectoria_ejemplo() -> dict:
    """A made-up swing path (1280x720 px) with the shape of a looped forehand seen from behind, coloured as the user
    explained the short (#306): back to its highest point, before the bounce, after the bounce, contact and finish; the
    blurred stretch (acceleration and impact) marked."""
    import math

    def oval(deg: float) -> list[float]:                # the loop around her, seen from behind (1280x720 px)
        r = math.radians(deg)
        return [round(640 + 290 * math.cos(r), 1), round(360 - 170 * math.sin(r), 1)]

    puntos = []
    tramos = (("atras", 20, 105, 9), ("antes_bote", 105, 190, 8), ("tras_bote", 190, 335, 12))
    for tramo, d0, d1, n in tramos:                    # back and up, over the loop, down and forward to the ball
        for k in range(n):
            puntos.append({"tramo": tramo, "xy": oval(d0 + (d1 - d0) * k / n)})
    c0, top, end = oval(335), [560.0, 150.0], [330.0, 280.0]
    for k in range(13):                                # from the contact up over the shoulder to the finish
        u = k / 12
        puntos.append({"tramo": "contacto", "xy": [round((1 - u) ** 2 * c0[0] + 2 * (1 - u) * u * top[0] + u * u * end[0], 1),
                                                     round((1 - u) ** 2 * c0[1] + 2 * (1 - u) * u * top[1] + u * u * end[1], 1)]})
    for i, q in enumerate(puntos):
        q["t"] = round(-1.0 + 1.6 * i / (len(puntos) - 1), 3)
        q["borroso"] = -0.15 < q["t"] < 0.05           # acceleration and impact: blurred on TV
    cx, cy = c0
    return {"ancho": 1280, "alto": 720, "puntos": puntos, "contacto": [cx - 35, cy - 30, 70, 60]}


def datos_beta(report: Path, audit: Path, estado: Path, matches: Path) -> dict:
    """The beta's data, as the validated mockup read them (design/p0/build_app.py), with each match's two players."""
    sys.path.insert(0, str(ROOT / "design" / "p0"))
    from build_app import build
    from build_maqueta import report_data

    d = build(report_data(report), json.loads(audit.read_text(encoding="utf-8")), estado.read_text(encoding="utf-8"),
              json.loads(matches.read_text(encoding="utf-8")))
    for m in d["matches"]:
        m.setdefault("personas", [p for p in (d["player"]["name"], m.get("rival")) if p])
    d["grip"] = _first_text(report_data(report), "Empuñadura:")         # explain.grip_compatible, as the report says it
    return d


def _first_text(o, prefix: str) -> str | None:
    if isinstance(o, str):
        return o if o.startswith(prefix) else None
    for v in (o.values() if isinstance(o, dict) else o if isinstance(o, list) else ()):
        t = _first_text(v, prefix)
        if t:
            return t
    return None


def main(argv: list[str] | None = None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if a[:1] == ["--ejemplo"] and len(a) == 2:
        datos, out = ejemplo(), Path(a[1])
    elif a[:1] == ["--beta"] and len(a) == 6:
        datos, out = datos_beta(*map(Path, a[1:5])), Path(a[5])
    else:
        print(__doc__)
        return 2
    out.write_text(pagina(datos), encoding="utf-8")
    print(f"{out}: {out.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
