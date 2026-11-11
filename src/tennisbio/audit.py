"""Automatic audit of the real outputs against the user's requirements (CLAUDE.md) and the coverage
matrix of the stroke (docs/matriz_cobertura.md).

It reads what a run produced (each match's strokes.json and manifest, the report's embedded data,
its videos, and the screenshots taken by scripts/capturas_informe.py) and answers, requirement by
requirement, whether it is there: every element of the taxonomy measured and shown (or declared
"not measurable from TV"), every situation of the stroke, the 8 key moments, the racket face,
values within physical limits, a playable video for every stroke, every screen rendered without
errors, nothing asked of the user and the time per match.

Statuses: "ok"; "falta" (a requirement not met: to fix); "pocos datos" (in place but this run has
too few strokes to show it; a full match decides); "aviso" (works, with a caveat).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "docs" / "matriz_cobertura.md"

REQUIREMENTS = {
    1: "Toda la taxonomía del golpe y todas sus variantes (situaciones)",
    2: "Información, no tablas: vídeo real como prueba en cada pantalla",
    3: "Nada inventado: valores posibles, respaldados por sus golpes; lo no medible se dice",
    4: "Cuerdas / orientación de la cara de la raqueta",
    5: "100 % automático",
    6: "Sin fuentes externas (nada de vídeos de otros)",
    9: "Rendimiento: un partido en horas, no días",
    11: "Cada petición del usuario en el chat (docs/peticiones_usuario.md), una a una",
    12: "Mejores modelos: cada candidato medido frente al actual y los adoptados en uso (B3)",
}
# requirement 1, word by word: each variant the user named → factor of the model ("" = none)
VARIANTS_ASKED = {
    "Bola rápida / lenta": "ball_speed", "Bola alta / baja": "ball_height", "Bola corta / profunda": "depth",
    "En carrera / parada / en salto": "movement", "Cada apoyo": "stance_impact", "Dirección del golpe": "shot_type",
    "Ataque / defensa": "intent", "Bola subiendo / arriba / cayendo": "ball_phase", "Bola centrada / abierta": "width",
}
# variants the user named in the chat that have no class yet (docs/revision_peticiones_19-10.md): always
# «falta» until a class exists. The three of 19-10 (angled shot, short ball near the net, mid-court volley)
# are built since 20-10 (situations.py) and counted by situation_items.
VARIANTS_NOT_BUILT: dict[str, str] = {}
KEY_MOMENTS = {"ready": "espera / split step", "takeback": "inicio de preparación", "loaded": "armado",
               "acceleration": "inicio de aceleración", "impact": "impacto", "extension": "extensión",
               "finish": "terminación", "recovery": "recuperación"}
# physical limits of what is shown (a value outside them is a measurement error that got through)
from . import match_files as _mf
from .limits import BALL_INCOMING_KMH, METRIC_LIMITS
from .pipeline import total_seconds

LIMITS = {
    **{f"metrics.{k}": v for k, v in METRIC_LIMITS.items()},
    "ball_flight.incoming_speed_kmh": BALL_INCOMING_KMH, "ball_flight.apex_height_m": (0.2, 4.0),
    "ball_flight.contact_height_m": (0.05, 3.0), "footwork.peak_speed_mps": (0, 9.5), "footwork.path_m": (0, 20),
    "footwork.approach_speed_mps": (0, 9.5), "displacement_m": (0, 20), "stance_width_m": (0.1, 2.5),
}
CURVE_LIMITS = {"head": (60, 120), "hip": (30, 70), "hand": (15, 135), "racket": (15, 150)}
BROWSER_CODECS = {"h264", "vp8", "vp9", "av1"}


def _plain(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def parse_matrix(path: Path = MATRIX) -> list[dict]:
    """Rows of the coverage matrix: section, element, status (✔ ◐ ○ ✘), backticked identifiers."""
    rows, section = [], ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
        if not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        status = next((c for c in cells if c in ("✔", "◐", "○", "✘")), None)
        if status is None:
            continue
        impl = cells[-1]
        rows.append({"section": section, "element": cells[0], "status": status, "impl": impl,
                     "ids": re.findall(r"`([^`]+)`", impl)})
    return rows


def stroke_values(s: dict) -> dict:
    """Every measured value of one stroke under a dotted name (None when not measured)."""
    from .technique import flatten

    t = s.get("technique") or {}
    out = {k: v for k, v in flatten(t).items()}
    for k, v in (t.get("footwork") or {}).items():
        out.setdefault(f"footwork.{k}", v)
    for k, v in (t.get("classes") or {}).items():
        out[f"class.{k}"] = v
    for k, v in (t.get("phases") or {}).items():
        out[f"tphase.{k}"] = v or None
    for k, v in (s.get("phases") or {}).items():
        out[f"phase.{k}"] = (v or {}).get("frame") if isinstance(v, dict) else v
    for k, v in (s.get("metrics") or {}).items():
        out[f"metrics.{k}"] = v
    for k, v in (s.get("ball_flight") or {}).items():
        out[f"ball_flight.{k}"] = v
    for k, v in (t.get("curves") or {}).items():
        out[f"curves.{k}"] = v if any(x is not None for x in v) else None
    for k, v in (s.get("face") or {}).items():
        out[f"face.{k}"] = (v or {}).get("tilt_deg") if isinstance(v, dict) else v
    for k, v in s.items():
        if not isinstance(v, (dict,)) and k not in out:
            out[k] = v
    out["chain.proximal_to_distal"] = (s.get("chain") or {}).get("proximal_to_distal")
    return out


def _matches(ident: str, key: str) -> bool:
    ident = ident.strip()
    if ident.endswith("*"):
        stem = ident[:-1]
        return any(seg.startswith(stem) for seg in key.split(".")) or key.startswith(stem)
    return key == ident or key.endswith("." + ident)


def _code_ref(ident: str) -> bool | None:
    """'ball3d.flights' → True if that function exists; None when it is not a code reference."""
    m = re.fullmatch(r"([a-z_0-9]+)\.([A-Za-z_][A-Za-z_0-9]*)", ident)
    if not m or not (ROOT / "src" / "tennisbio" / f"{m.group(1)}.py").exists():
        return None
    import importlib
    try:
        return hasattr(importlib.import_module(f"tennisbio.{m.group(1)}"), m.group(2))
    except Exception:
        return False


def report_data(html: Path) -> dict | None:
    """The data the report page was built with (embedded as `const DATA = …;`)."""
    try:
        txt = html.read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r"const DATA = (\{.*?\});\n", txt, re.S)
    return json.loads(m.group(1)) if m else None


def shown_keys(data: dict) -> set[str]:
    """Keys whose values the report puts in front of the user, in the stroke's dotted names."""
    from .report import METRICS

    shown = set()
    # «Cópiala» shows every checkpoint that has a value in at least one stroke (with how many back it)
    for r in data.get("strokes") or []:
        shown |= {k for k, v in (r.get("lv") or {}).items() if v is not None}
    model = data.get("model") or {}
    cards = list(model.get("cards") or [])
    for v in (model.get("variants") or {}).values():
        cards += v.get("cards") or []
    for c in cards:
        for ln in c.get("lines") or []:
            shown.add(ln["key"])
    shown |= {f"footwork.{k}" for k, v in (model.get("footwork") or {}).items() if v and v.get("n", 1)}
    shown |= {f"class.{v['factor']}" for v in (model.get("variants") or {}).values()}
    if any("Puntos que gana" in t for t in model.get("summary") or []):
        shown.add("point_won")
    shown |= {f"curves.{k}" for k in (model.get("curves") or {}) if k not in ("t", "events")}
    for k, spec in METRICS.items():
        if any((s.get("m") or {}).get(k) is not None for s in data.get("strokes", [])):
            shown.add(f"metrics.{spec[-1]}")
    # the conditions of «Cópiala»: each stroke's class is counted in its chips and selects it
    for s in data.get("strokes", []):
        shown |= {f"class.{k}" for k, v in (s.get("cl") or {}).items() if v is not None}
    # the court of each stroke's match (stroke screen, «Pista»)
    if any(s.get("surface") for s in data.get("strokes", [])):
        shown.add("surface")
    # «Sus pies en este golpe» (stroke screen): every footwork value of each stroke
    for s in data.get("strokes", []):
        for k, v in (s.get("feet") or {}).items():
            if v not in (None, False, [], ""):
                shown.add(f"footwork.{k}")
                if k == "around_ball":
                    shown.add("class.around_ball")
    return shown


def planned_keys() -> set[str]:
    """Keys the report knows how to show (when there are enough strokes and they are reliable)."""
    from .explain import CLASS_PHASE, LINES
    from .model import FACTORS, FOOTWORK_KEYS
    from .report import METRICS

    keys = {k for lines in LINES.values() for k, _ in lines}
    keys |= {f"class.{k}" for k in CLASS_PHASE}
    keys |= {f"footwork.{k}" for k in FOOTWORK_KEYS}
    # counted in the feet panel of «Su derecha»; factors are the situations to choose
    keys |= {f"footwork.{k}" for k in ("first_step_type", "last_plant_foot", "move_direction", "rear_leg_step_after", "first_step_right_way")}
    keys |= {f"class.{k}" for k in FACTORS} | {"point_won", "class.around_ball", "class.approach_main", "class.recovery_first_step"}
    from .report import FEET_KEYS
    keys |= {f"footwork.{k}" for k in FEET_KEYS}
    keys |= {f"metrics.{spec[-1]}" for spec in METRICS.values()}
    keys |= {f"curves.{k}" for k in ("head", "hip", "hand", "racket")}
    # stroke fields the stroke screen and the explorer read directly
    src = (ROOT / "src" / "tennisbio" / "report.py").read_text(encoding="utf-8")
    keys |= set(re.findall(r'\bs\.get\("(\w+)"', src))
    keys |= {f"tphase.{p}" for p in ("ball_net", "ball_bounce", "ball_top")}
    keys |= {f"phase.{p}" for p in KEY_MOMENTS}
    keys |= {"chain.proximal_to_distal"} | {f"face.{p}" for p in KEY_MOMENTS}
    from .learn import CONDITIONS, learn_keys
    keys |= set(learn_keys())                      # every checkpoint of «Cópiala»
    keys |= {f"class.{k}" for k in CONDITIONS}     # and every condition the user chooses there
    return keys


def _share(vals: list) -> float:
    return sum(v is not None for v in vals) / len(vals) if vals else 0.0


def _item(req, area, name, status, detail, **kw) -> dict:
    return {"req": req, "area": area, "name": name, "status": status, "detail": detail, **kw}


def audit(match_dirs: list[Path], report_dir: Path | None, stroke: str = "forehand",
          shots_dir: Path | None = None, min_strokes: int = 20) -> dict:
    """The audit of one run: a list of items, each a requirement check with its status."""
    from .model import FACTORS, MIN_N

    strokes, manifests, errors = [], {}, 0
    for d in match_dirs:
        f = _mf.at(d, "strokes.json")
        if f.exists():
            strokes += [s for s in json.loads(f.read_text(encoding="utf-8")) if s.get("stroke") == stroke]
        if (_mf.at(d, "manifest.json")).exists():
            manifests[d.name] = json.loads((_mf.at(d, "manifest.json")).read_text(encoding="utf-8"))
        if (_mf.at(d, "strokes_errores.json")).exists():
            errors += len(json.loads((_mf.at(d, "strokes_errores.json")).read_text(encoding="utf-8")) or [])
    from .situations import apply as _situations
    for s in strokes:                 # outputs written before the situations existed: added, never overwritten
        _situations(s, overwrite=False)
    near = [s for s in strokes if s.get("side") != "far"]
    vals = [stroke_values(s) for s in near]
    all_keys = sorted({k for v in vals for k in v})
    few = len(near) < min_strokes
    data = report_data(report_dir / "index.html") if report_dir else None
    shown = shown_keys(data) if data else set()
    planned = planned_keys()
    nm_text = _plain(" ".join(((data or {}).get("model") or {}).get("not_measurable") or []))
    items = []
    items.append(_item(1, "Golpes", f"{stroke}: golpes analizados",
                       "ok" if not few else "pocos datos",
                       f"{len(near)} del lado cercano (con todo el detalle), {len(strokes) - len(near)} del lejano"
                       + (f"; con menos de {min_strokes} muchas situaciones no se pueden describir" if few else ""),
                       n=len(near), far=len(strokes) - len(near)))
    items += recall_items(match_dirs)
    items += b4_items(match_dirs, items, stroke, len(near), len(strokes) - len(near))   # #23, #205, #218/#219 (08-11)
    if report_dir:          # the serve report (informe_saque next to this one) says how much of her serves it covers
        serve_html = (report_dir if stroke == "overhead" else report_dir.parent / "informe_saque") / "index.html"
        items.append(serve_coverage_item(match_dirs, serve_html))
    items += views_items(match_dirs)
    items += view_clips_items(match_dirs, report_dir, stroke)    # #218 (09-11): the clips on the stroke's page
    items += slowmo_items(match_dirs, report_dir, stroke)        # #218 (09-11): measured on the slow-motion replay
    items += camera_items(match_dirs, stroke)

    # 1. taxonomy: each row of the coverage matrix
    for row in parse_matrix():
        name = f"{row['section'].split('(')[0].strip()} · {row['element']}"
        if row["status"] == "✘":
            words = [w for w in re.findall(r"\w+", _plain(row["element"])) if len(w) >= 6]
            told = any(w[:7] in nm_text for w in words)
            items.append(_item(3, "Taxonomía", name, "ok" if told else "aviso",
                               "no observable desde la tele; el informe lo dice" if told else
                               "no observable desde la tele, pero el informe no lo dice en «Lo que la tele no permite medir»"))
            continue
        if row["status"] == "○":
            items.append(_item(1, "Taxonomía", name, "falta", "hueco medible sin implementar"))
            continue
        from .practice import MIN_N as P_MIN, SIDE_METRICS
        pkeys = [i for i in row["ids"] if i in SIDE_METRICS]
        if pkeys:                    # measured on the side view of the practice videos (own screen)
            pr = (data or {}).get("practice") or {}
            summ = pr.get("summary") or {}
            ns = {k: (summ.get(k) or {}).get("n", 0) for k in pkeys}
            done = [k for k in pkeys if (summ.get(k) or {}).get("median") is not None]
            st = "ok" if len(done) == len(pkeys) else "pocos datos" if pr else "aviso"
            items.append(_item(1, "Taxonomía", name, st,
                               "vista lateral de entrenamiento: " + ", ".join(f"{k} en {n} derechas de lado" for k, n in ns.items())
                               + ("" if pr else " (todavía no hay vídeos de entrenamiento analizados)")
                               + ("" if st == "ok" else f"; se resume con {P_MIN} o más"), keys=pkeys))
            continue
        found, code_ok, best, is_shown, is_planned, plan_any = [], True, 0.0, False, False, False
        for ident in row["ids"]:
            c = _code_ref(ident)
            if c is not None:
                code_ok &= c
                continue
            plan_any |= any(_matches(ident, k) for k in planned)
            ks = [k for k in all_keys if _matches(ident, k)]
            found += ks
            for k in ks:
                best = max(best, _share([v.get(k) for v in vals]))
                is_shown |= k in shown
                is_planned |= k in planned
        if not row["ids"] or (not found and code_ok and any(_code_ref(i) for i in row["ids"])):
            # described in words or only by its code: the stroke screen / model carries it
            st, det = ("ok", "implementado (sin nombre de dato en la matriz)") if code_ok else ("falta", "el código citado no existe")
        elif not found:
            # with few strokes a value that is only written when measurable may simply not be there yet
            st = "pocos datos" if few else "falta" if row["status"] == "✔" else "aviso"
            det = f"no aparece en los datos de ningún golpe de esta ejecución ({', '.join(row['ids'])})"
        elif best == 0:
            st, det = ("pocos datos" if few else "falta"), "en los datos, pero sin valor en ningún golpe de esta ejecución"
        elif not is_planned and plan_any:
            # the report shows it at one moment (e.g. the end of the backswing) where this run could not see it
            st, det = ("pocos datos" if few else "aviso"), (f"se mide ({best:.0%} de los golpes) en otros momentos, pero no en el "
                                                            "que enseña el informe (no se vio en esta ejecución)")
        elif not is_planned:
            st, det = "falta", f"se mide ({best:.0%} de los golpes) pero el informe no lo enseña en ninguna pantalla"
        elif not is_shown:
            st, det = "pocos datos", f"se mide ({best:.0%} de los golpes); el informe lo enseñará con más golpes o más fiabilidad"
        else:
            st, det = "ok", f"medido en el {best:.0%} de los golpes y en el informe"
            from .explain import COACH
            if not any(k in COACH or k.split(".")[-1] in COACH or "class." + k.split(".")[-1] in COACH for k in found if k in planned):
                st, det = "aviso", det + ", pero sin explicación de qué significa (por qué importa)"
        if row["status"] == "◐" and st == "ok":
            det += " (parcial: ver la matriz)"
        items.append(_item(1, "Taxonomía", name, st, det, keys=sorted(set(found))[:8], measured=round(best, 2)))

    # 1. the user's matrix: every item has its place in «Aprende su derecha» (value, cue, drill or why not)
    from .learn import matrix_places
    places = matrix_places([r for r in parse_matrix() if r["section"].startswith("6.")])
    nowhere = [e for e, w in places.items() if w is None]
    items.append(_item(1, "Aprende su derecha", "Cada punto de la matriz del usuario tiene su sitio en la pantalla",
                       "falta" if nowhere else "ok", f"{len(places) - len(nowhere)} de {len(places)}"
                       + (f"; sin sitio: {', '.join(nowhere[:6])}" if nowhere else "")))

    # 1. variants: every situation the user asked for
    model = (data or {}).get("model") or {}
    variants = model.get("variants") or {}
    for label, why in VARIANTS_NOT_BUILT.items():
        items.append(_item(1, "Situaciones", label, "falta", why))
    items += situation_items(near, MIN_N)
    for label, fk in VARIANTS_ASKED.items():
        if not fk:
            items.append(_item(1, "Situaciones", label, "falta",
                               "se mide por golpe (dirección del golpe) pero no es una situación de «Su derecha»"))
            continue
        counts = {}
        for v in vals:
            c = v.get(f"class.{fk}")
            if c is not None:
                counts[c] = counts.get(c, 0) + 1
        shown_lv = sorted(v["level"] for v in variants.values() if v.get("factor") == fk)
        levels = FACTORS[fk][1]
        missing = [lv for lv in levels if counts.get(lv, 0) >= MIN_N and lv not in shown_lv]
        det = ", ".join(f"{lv} {counts.get(lv, 0)}" for lv in levels) + f" (se muestra con ≥ {MIN_N} golpes)"
        st = "falta" if missing else "ok" if shown_lv else "pocos datos"
        items.append(_item(1, "Situaciones", label, st,
                           det + (f"; con golpes suficientes y sin mostrar: {', '.join(missing)}" if missing else ""),
                           shown=shown_lv))

    # 1. every combination measurement × situation level: with enough strokes in that level its 8 phases
    # must be there, each with its lines, her mean skeleton and its videos; with fewer, it is counted
    items += _combination_items(model, vals, MIN_N, FACTORS)

    # 3. internal exam: what coaches say about her forehand, against her measured strokes (never in the report)
    from .exam import CONFIRMS, FEW, REFUTES, claims
    for rid, text, verdict, det in claims(vals, MIN_N):
        items.append(_item(3, "Examen de entrenadores", f"{rid} {text}",
                           {CONFIRMS: "ok", FEW: "pocos datos", REFUTES: "aviso"}.get(verdict, "ok"), f"{verdict}: {det}"))

    # 1. the 8 key moments of every stroke
    for p, name in KEY_MOMENTS.items():
        sh = _share([v.get(f"phase.{p}") for v in vals])
        items.append(_item(1, "Fases", f"Fotograma clave: {name}",
                           "ok" if sh >= 0.8 else "aviso" if sh >= 0.5 else ("pocos datos" if not near else "falta"),
                           f"encontrado en el {sh:.0%} de los golpes"))

    # 4. racket face
    for p in ("ready", "takeback", "loaded", "impact", "finish"):
        sh = _share([v.get(f"face.{p}") for v in vals])
        exp = p == "impact"
        st = "ok" if sh >= (0.3 if exp else 0.5) else "aviso" if sh > 0 or p == "ready" else "falta"
        items.append(_item(4, "Cuerdas", f"Cara de la raqueta: {KEY_MOMENTS[p]}", st,
                           f"en el {sh:.0%} de los golpes" + (" (estimación interpolada, se marca así)" if exp else "")
                           + (" (la espera suele caer antes del segundo que se analiza con la raqueta)" if p == "ready" and sh < 0.5 else "")))

    # 3. physical limits of what is shown
    bad = []
    for k, (lo, hi) in LIMITS.items():
        xs = [v.get(k) for v in vals if isinstance(v.get(k), (int, float)) and not isinstance(v.get(k), bool)]
        out = [x for x in xs if not lo <= x <= hi]
        if out:
            bad.append(f"{k}: {len(out)} de {len(xs)} fuera de {lo}–{hi}")
    for k, (lo, hi) in CURVE_LIMITS.items():
        xs = [x for v in vals for x in (v.get(f"curves.{k}") or []) if x is not None]
        out = [x for x in xs if not lo - 1e-6 <= x <= hi + 1e-6]
        if out:
            bad.append(f"curva {k}: {len(out)} de {len(xs)} puntos fuera de {lo}–{hi} %")
    items.append(_item(3, "Valores posibles", "Valores dentro de límites físicos", "falta" if bad else "ok",
                       "; ".join(bad) if bad else f"{len(LIMITS) + len(CURVE_LIMITS)} medidas comprobadas en {len(near)} golpes"))
    from .learn import content
    from .reliability import assess, summary
    units = {c["key"]: c.get("unit") for ph in content()["phases"] for c in ph["checkpoints"] if not c["key"].startswith("practice.")}
    rel = assess(near, units)
    if rel:
        sm = summary(rel)
        noisy = sorted((k for k, v in rel.items() if v["verdict"] == "ruido"), key=lambda k: -rel[k].get("noise", rel[k].get("flip", 0)))
        biased = [k for k, v in rel.items() if v["verdict"] == "sesgo" and "med2d" in v]
        impossible = [k for k, v in rel.items() if v["verdict"] == "sesgo" and "implausible" in v]
        judged = sum(v for k, v in sm.items() if k != "sin juzgar")
        noisy_txt = ", ".join(f"{k} ±{rel[k]['noise']}" if "noise" in rel[k] else f"{k} cambia {rel[k]['flip']:.0%}" for k in noisy[:12])
        items.append(_item(3, "Valores posibles", "Cada medida comprobada: técnica o ruido (fotogramas vecinos frente a diferencias entre golpes)",
                           "ok" if judged else "pocos datos",
                           f"{len(rel)} medidas: " + ", ".join(f"{v} {k}" for k, v in sorted(sm.items())) +
                           (f". No se dan como valor suyo (ruido): {noisy_txt}" if noisy else "")
                           + (". No coinciden con el segundo método (3D), no se dan: " + ", ".join(f"{k} 2D {rel[k]['med2d']}° / 3D {rel[k]['med3d']}°" for k in biased) if biased else "")
                           + (". Fuera de lo físicamente posible en demasiados golpes, no se dan: " + ", ".join(
                               f"{k} {rel[k]['implausible']} de {rel[k]['n_values']}" for k in impossible) if impossible else "")
                           + ". «no comprobable»: no depende del instante de las fases (esta prueba no la valida). Con menos de 5 golpes no se juzga"))
    vals_n = [stroke_values(s) for s in near]
    for k, name in (("loaded.racket_tip_vs_head", "Punta de la raqueta respecto a la cabeza en el armado"),
                    ("stroke.shoulder_brake", "Frenado de los hombros antes del contacto")):
        n = sum(isinstance(v.get(k), (int, float)) for v in vals_n)
        items.append(_item(3, "Valores posibles", name, "ok" if near and n >= 0.5 * len(near) else "pocos datos",
                           f"medido en {n} de {len(near)} golpes; en «Aprende»" + (f"; fiabilidad: {rel[k]['verdict']}" if rel.get(k) else "")))
    if data:
        lines = [ln for c in (model.get("cards") or []) for ln in c.get("lines") or []]
        weak = [ln["key"] for ln in lines if (ln.get("n") or 0) < MIN_N or ln.get("rel") is None]
        items.append(_item(3, "Valores posibles", "Cada frase lleva cuántos golpes la respaldan y su fiabilidad",
                           "falta" if weak else "ok" if lines else "pocos datos",
                           f"{len(lines)} frases" + (f"; sin respaldo suficiente: {', '.join(weak[:6])}" if weak else "")))
        items.append(_item(3, "Valores posibles", "Lo no medible se dice", "ok" if model.get("not_measurable") else "falta",
                           f"{len(model.get('not_measurable') or [])} elementos en «Lo que la tele no permite medir»"))

    # 6. side view from practice videos: a separate, marked source (never mixed with the matches)
    if data is not None:
        items += _practice_items(data.get("practice"), report_dir)

    # 2. video for every stroke of the report
    if data and report_dir:
        rs = [s for s in data.get("strokes", []) if s.get("side") != "far"]
        no_video = [s["id"] for s in rs if not s.get("video") or not (report_dir / s["video"]).exists()]
        no_series = [s["id"] for s in rs if not s.get("series") or not (report_dir / s["series"]).exists()]
        items.append(_item(2, "Vídeo", "Cada golpe tiene su vídeo", "falta" if no_video or not rs else "ok",
                           f"{len(rs) - len(no_video)} de {len(rs)} golpes con vídeo" + (f"; sin vídeo: {', '.join(no_video[:5])}" if no_video else "")))
        items.append(_item(2, "Vídeo", "Cada golpe tiene su esqueleto fotograma a fotograma", "falta" if no_series else "ok",
                           f"{len(rs) - len(no_series)} de {len(rs)}"))
        codecs = _codecs([report_dir / s["video"] for s in rs if s.get("video") and (report_dir / s["video"]).exists()][:20])
        bad_c = {f: c for f, c in codecs.items() if c not in BROWSER_CODECS}
        items.append(_item(2, "Vídeo", "El navegador puede reproducir los vídeos",
                           "falta" if bad_c else "ok" if codecs else "aviso",
                           f"formatos: {', '.join(sorted(set(codecs.values()))) or 'sin comprobar (falta ffprobe)'}"
                           + (f"; no reproducibles: {len(bad_c)}" if bad_c else "")))
    elif report_dir:
        items.append(_item(2, "Informe", "El informe existe y tiene sus datos", "falta", f"no se pudo leer {report_dir / 'index.html'}"))

    # 2. what the user sees: every screen rendered, without errors (scripts/capturas_informe.py)
    if shots_dir:
        items += _screens(shots_dir)

    # 5 and 9. automatic, errors, time
    failed = [f"{m}: {st}" for m, man in manifests.items() for st, e in man.items() if (e.get("summary") or {}).get("errors")]
    items.append(_item(5, "Automático", "Golpes que fallaron al procesarse", "aviso" if errors else "ok",
                       f"{errors} golpes con error (guardados en strokes_errores.json)" if errors else "ninguno"))
    from .report import doubts, measure_notes
    review = sum(bool(doubts(s.get("review"))) for s in strokes)
    nr = [s for s in strokes if s.get("side") != "far"]                # the detailed strokes, as on the screen
    notes = sum(bool(measure_notes(s.get("review"))) and not doubts(s.get("review")) for s in nr)
    if nr:
        share = sum(bool(doubts(s.get("review"))) for s in nr) / len(nr)
        kinds = {}
        for s in nr:
            for f in doubts(s.get("review")):
                kinds[f.split(":")[0]] = kinds.get(f.split(":")[0], 0) + 1
        items.append(_item(5, "Automático", "Golpes dudosos (duda sobre el golpe, no sobre una medida)",
                           "ok" if share <= 0.3 else "aviso",
                           f"{sum(bool(doubts(s.get('review'))) for s in nr)} de {len(nr)} del lado cercano ({share:.0%}); motivos: {', '.join(f'{k} {v}' for k, v in sorted(kinds.items(), key=lambda kv: -kv[1])) or 'ninguno'}. "
                           f"Otros {notes} golpes solo tienen una medida que falta (raqueta no vista, valor imposible descartado): "
                           "son válidos y no cuentan como dudosos"))
    # 11-11 (review of the Base, R1): this was «Nada pide revisión manual», always ok; that check now looks at what the
    # application waits for from the user (manual_review_item, in side_checks); this one only says what is marked
    items.append(_item(5, "Automático", "Golpes con dudas marcadas (se enseñan, no se piden)", "ok",
                       f"{review} golpes llevan dudas marcadas; el informe las enseña, no se piden al usuario"))
    for m, man in manifests.items():
        dur = ((man.get("probe") or {}).get("summary") or {}).get("duration_min")
        secs = total_seconds(man)          # stages run at the same time count once
        if dur:
            per_h = secs / 3600 / (dur / 60) if dur else None        # hours of processing per hour of video
            # B1 (10-11, with the user): a 3.5 h match from scratch in one night, ≤ 8 h (SPEED_TARGET). 11-11 (review of
            # the Base, R2): only a run whose heavy stages computed is a time; one that re-read its caches is not (it
            # said 1,2-2,1 h while a run from scratch took 7,6 h): that one is information, in another area
            from .stage_times import not_real
            reread = not_real(man)
            est = f"{secs / 60:.0f} min para {dur:.0f} min de vídeo ≈ {per_h * 3.5:.1f} h para un partido de 3,5 h"
            if reread:
                items.append(_item(9, "Rendimiento (información)", f"Tiempo: {m}", "pocos datos",
                                   f"{est}, pero no es desde cero: releyeron sus datos guardados {', '.join(reread)}. "
                                   "La cifra que cuenta es «Tiempo desde cero»"))
            else:
                st = "ok" if per_h is not None and per_h <= SPEED_TARGET else "aviso"
                items.append(_item(9, "Rendimiento", f"Tiempo: {m}", st,
                                   f"{est} (objetivo ≤ {SPEED_TARGET * 3.5:.1f} h; todas sus etapas pesadas calcularon)"))
        views = (man.get("views") or {}).get("seconds")
        if views is not None:                     # B-3: the camera-shots stage under 15 min a match
            items.append(_item(9, "Rendimiento", f"Tomas de cámara: {m}", "ok" if views <= 900 else "aviso",
                               f"{views / 60:.1f} min (objetivo ≤ 15 min)"))
    if failed:
        items.append(_item(5, "Automático", "Etapas con errores", "falta", "; ".join(failed)))

    summary = {st: sum(i["status"] == st for i in items) for st in ("ok", "falta", "pocos datos", "aviso")}
    return {"stroke": stroke, "strokes": len(strokes), "near": len(near), "summary": summary, "items": items}


def recall_items(match_dirs: list[Path]) -> list[dict]:
    """No stroke lost: per match, her strokes found (all kinds, both ends) against what its scoreboard says
    was played (tennisbio.point_count): points and her service points read from score.json, serves
    expected in [service points, 2 × service points], all her strokes in a typical range per point (a
    range, never an exact count). Red ("falta") when clearly too few: under half of the lower end."""
    from .point_count import count_points, recall_verdict

    out = []
    for d in match_dirs:
        sc, st = _mf.at(d, "score.json"), _mf.at(d, "strokes.json")
        if not sc.exists():
            continue
        try:
            readings = json.loads(sc.read_text(encoding="utf-8")).get("readings") or []
            strokes = json.loads(st.read_text(encoding="utf-8")) if st.exists() else []
        except (OSError, ValueError):
            continue
        counts = count_points(readings)
        serves = sum(s.get("stroke") == "overhead" for s in strokes)
        # points the TV did not show (nobody plays on the main camera) are not expected to hold her strokes (08-11)
        unseen_txt = ""
        try:
            from .point_count import seen_counts, unseen_points
            cj_f, sp_f0 = _mf.at(d, "candidates.json"), _mf.at(d, "spotting.json")
            if cj_f.exists():
                cj0 = json.loads(cj_f.read_text(encoding="utf-8"))
                cd0 = cj0.get("candidates", cj0) if isinstance(cj0, dict) else cj0
                sp0 = json.loads(sp_f0.read_text(encoding="utf-8")) if sp_f0.exists() else []
                un = unseen_points(readings, cd0, sp0)
                if un["all"]:
                    counts = seen_counts(counts, un)
                    unseen_txt = (f" (sin {un['all']} puntos en los que nadie juega en la cámara principal: la tele no "
                                  f"los enseñó, {un['hers']} de su saque)")
        except (OSError, ValueError, KeyError, TypeError):
            pass
        status, detail = recall_verdict(len(strokes), serves, counts)
        detail += unseen_txt
        sides = f" ({sum(s.get('side') != 'far' for s in strokes)} cerca, {sum(s.get('side') == 'far' for s in strokes)} lejos)"
        try:                                      # strokes of undecided identity: analysed, kept apart, not hers yet
            doubt = json.loads((_mf.at(d, "strokes_doubtful.json")).read_text(encoding="utf-8")) if (_mf.at(d, "strokes_doubtful.json")).exists() else []
        except (OSError, ValueError):
            doubt = []
        if doubt:
            sides += f"; además {len(doubt)} de identidad dudosa, apartados (no cuentan como suyos)"
        out.append(_item(1, "Golpes", f"Golpes encontrados frente al marcador: {d.name}", status, detail + sides,
                         found=len(strokes), serves=serves, counts=counts, doubtful=len(doubt),
                         near=sum(s.get("side") != "far" for s in strokes), far=sum(s.get("side") == "far" for s in strokes)))
        # B4 (04-11): each point on her serve with no serve found, and why (camera, detection or stroke type)
        try:
            from .point_count import GAP_CAUSES, serve_gaps
            sc_f = _mf.at(d, "scenes.json")
            shots = []
            if sc_f.exists():
                scn = json.loads(sc_f.read_text(encoding="utf-8"))
                fps = float(scn.get("fps") or 1.0)
                shots = [(sh["start"] / fps, sh["end"] / fps) for sh in scn.get("shots", []) if sh.get("main_camera")]
            sp_f = _mf.at(d, "spotting.json")
            spotted = json.loads(sp_f.read_text(encoding="utf-8")) if sp_f.exists() else None
            cd_f = _mf.at(d, "candidates.json")
            cands = None
            if cd_f.exists():
                cj = json.loads(cd_f.read_text(encoding="utf-8"))
                cands = cj.get("candidates", cj) if isinstance(cj, dict) else cj
            dr_f = _mf.at(d, "strokes_descartados.json")
            dropped = json.loads(dr_f.read_text(encoding="utf-8")) if dr_f.exists() else None
            g = serve_gaps(readings, strokes, shots, spotted=spotted, candidates=cands, doubtful=doubt, dropped=dropped)
            if g["points"]:
                why = ", ".join(f"{GAP_CAUSES[k]} {v}" for k, v in g["by_cause"].items() if v)
                # points nobody plays in on the main camera (no candidate, nothing spotted) were not shown by the
                # broadcast: not measurable from TV, left out of the count and said (07-11, requests 127-130)
                seen_pts = g["points"] - g.get("unseen", 0)
                miss = seen_pts - g["found"]
                st_ = ("ok" if g["found"] >= SERVE_POINTS_MIN * seen_pts - 1e-9 else
                       ("aviso" if miss <= 0.3 * seen_pts else "falta"))
                # the serves lost must not all be of one kind (08-11, agreed with the user): her end in the lost points
                # (first stroke found) against her end in the serves found
                bias = serve_loss_bias(strokes, g)
                far_gap = bool(bias) and SERVE_FAR_GAP_ACCEPTED and "lado lejano" in bias
                if bias and st_ == "ok" and not far_gap:
                    st_ = "aviso"
                out.append(_item(1, "Golpes", f"Saques por punto de su saque: {d.name}", st_,
                                 f"{g['found']} de {seen_pts} puntos de su saque vistos con su saque encontrado "
                                 f"({g['found'] / max(seen_pts, 1):.0%}; objetivo ≥ {SERVE_POINTS_MIN:.0%})"
                                 + (f"; SESGO: {bias}" + ("; aceptado como limitación conocida del lado lejano "
                                                         "(08-11), dicho en el informe" if far_gap else "")
                                    if bias else "")
                                 + (f" ({g['unseen']} puntos más sin nadie jugando en la cámara principal: la tele "
                                    "no los enseñó, no cuentan)" if g.get("unseen") else "")
                                 + (f"; sin saque: {why}" if why else "")
                                 + (f"; sus saques encontrados caen en puntos de su saque {g['serves_at']['her_points']}, "
                                    f"de la rival {g['serves_at']['opponent_points']}, fuera de los puntos leídos "
                                    f"{g['serves_at']['elsewhere']}")
                                 + (f"; en los puntos sin saque, su primer golpe encontrado llega {fs['median']} s "
                                    f"(mediana de {fs['n']}) después de que vuelva la cámara principal"
                                    if (fs := g.get("first_stroke_after_shot_start_s")) else "")
                                 + (f"; ese primer golpe (puntos con golpes y sin saque, {fw['n']}): tipo {fw['type']}, "
                                    f"lado {fw['side']}, {fw['behind_baseline']} detrás de la línea de fondo"
                                    if (fw := g.get("first_strokes_without_serve")) and fw["n"] else "")
                                 + (f"; lo que vio el detector antes de su primer golpe: {sb}"
                                    if (sb := g.get("spotter_before_first")) else "")
                                 + (f"; en los puntos sin ningún golpe suyo: con golpes de alguien (detector) "
                                    f"{nb['golpes_de_alguien']}, sin golpes de nadie {nb['nadie_golpea']}, cámara "
                                    f"principal {nb['camara_principal_s_mediana']} s (mediana)"
                                    + (f", candidatos {nb['candidatos']}" if nb.get("candidatos") else "")
                                    + (f", golpes suyos perdidos {nb['suyos_perdidos']}" if nb.get("suyos_perdidos") else "")
                                    + (f", motivos del descarte {nb['motivos_descarte']}" if nb.get("motivos_descarte") else "")
                                    if (nb := g.get("no_strokes_points")) and g["by_cause"].get("sin_golpes") else "")
                                 + (f"; saques del marcador descartados en la pasada fina: {mb}"
                                    if (mb := _board_drops(dropped)) else "")
                                 + ("; primeros: " + ", ".join(f"{x['t0'] / 60:.1f}-{x['t1'] / 60:.1f} min ({x['cause']})"
                                                               for x in g["gaps"][:8]) if g["gaps"] else ""),
                                 serve_gaps=g))
        except Exception as e:  # noqa: BLE001 — the audit must still be written
            out.append(_item(1, "Golpes", f"Saques por punto de su saque: {d.name}", "aviso", f"no se pudo calcular ({e})"))
    return out


# her serves found per point of her serve the TV showed (B4's main test). 0.90 set by Claude without an external
# reference; agreed with the user on 08-11: 0.85 from the morning of 09-11 if a match is still below 0.90, together with
# F3Set precision ≥ F3SET_PRECISION_MIN, no bias in the serves lost (serve_loss_bias) and the coverage said in the report
# 08-11 (the user: «cierra el saque con el 85% con el gap del lado lejano»): 0.85, the 90 % stays as the target of the
# measures phase; the far end is the known gap (a far serve the spotter never sees: no rule recovers it), accepted and
# said in the report (SERVE_FAR_GAP); a bias toward the near end still fails
SERVE_POINTS_MIN = 0.85
SERVE_FAR_GAP_ACCEPTED = True
SERVE_FAR_GAP = ("el saque del lado lejano está menos cubierto: el detector no ve algunos de sus saques de ese lado "
                 "(limitación conocida)")
F3SET_PRECISION_MIN = 0.94
BIAS_MIN_LOST = 5               # lost points with a known end needed to call a bias
BIAS_MAX_DIFF = 0.35            # far-end share among the lost against among the found


def serve_loss_bias(strokes: list[dict], g: dict) -> str:
    """'' or why the serves lost are of one kind: her end (near/far) in the points without a serve (first stroke found)
    against the end of her serves found."""
    lost = [x["first_stroke"]["side"] for x in g.get("gaps", []) if (x.get("first_stroke") or {}).get("side")]
    found = [s.get("side") for s in strokes if s.get("stroke") == "overhead" and s.get("side")]
    if len(lost) < BIAS_MIN_LOST or not found:
        return ""
    fl, ff = sum(x == "far" for x in lost) / len(lost), sum(x == "far" for x in found) / len(found)
    if abs(fl - ff) <= BIAS_MAX_DIFF:
        return ""
    return (f"los puntos sin saque son del lado lejano en un {fl:.0%} frente al {ff:.0%} de sus saques encontrados "
            f"({len(lost)} con lado conocido)")


def f3set_precision_item(out_root: Path) -> dict:
    """B4 (08-11): no stroke invented — the precision of her strokes on F3Set (annotated by people) holds."""
    name = f"Golpes inventados: precisión en F3Set ≥ {F3SET_PRECISION_MIN:.2f}"
    r = _latest_recall(out_root)
    if r is None:
        return _item(1, "Golpes", name, "aviso", "sin recuento de F3Set (recall_validation_detector.json)")
    f, p, rec, found, gt = r
    return _item(1, "Golpes", name, "ok" if p >= F3SET_PRECISION_MIN - 1e-9 else "falta",
                 f"precisión {p:.3f}, encontrados {found} de {gt} ({rec:.0%}) en {f}")


F3SET_RECALL_MIN = 0.85         # 11-11 (R4): her annotated strokes found by the analysis's detector (0.90 on 08-11)
F3SET_KIND_MIN = 0.95           # 11-11 (R4): found strokes given their annotated kind (derecha/revés; saque)
F3SET_RECALL_ITEM = "Golpes encontrados frente a F3Set (detector del análisis)"
F3SET_KIND_ITEM = "Tipo de golpe frente a F3Set (anotado)"


def _latest_recall_summary(out_root: Path) -> tuple[str, dict] | None:
    for name in ("recall_validation_detector.json", "recall_validation.json"):
        f = _find(out_root, name, f"datasets/reports/{name}")
        if f is None:
            continue
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        s = r.get("summary_valid") or r.get("summary") or {}
        if s:
            return name, s
    return None


def f3set_detector_items(out_root: Path) -> list[dict]:
    """B4's main test (11-11, R4 of the review of the Base): the analysis's own detector against the strokes people
    annotated in F3Set (scripts/validate_recall.py), not the old clip path that «Validación con clips anotados» measures
    (51 strokes, recall 0.65, passed with F1 ≥ 0.6). #151: the kind of each found stroke against its annotated kind
    (the confusion was measured but no check read it)."""
    r = _latest_recall_summary(out_root)
    if r is None:
        return [_item(1, "Golpes", n, "aviso", "sin recuento de F3Set (recall_validation_detector.json)")
                for n in (F3SET_RECALL_ITEM, F3SET_KIND_ITEM)]
    f, s = r
    tot = s.get("total") or {}
    rec = tot.get("recall")
    out = [_item(1, "Golpes", F3SET_RECALL_ITEM, "aviso" if rec is None else "ok" if rec >= F3SET_RECALL_MIN else "falta",
                 f"{tot.get('found')} de {tot.get('gt')} golpes suyos anotados encontrados"
                 + (f" ({rec:.0%}; objetivo ≥ {F3SET_RECALL_MIN:.0%})" if rec is not None else "") + f" en {f}")]
    conf = s.get("kind_confusion") or {}
    pairs = [(k.split("->")[0], k.split("->")[1], int(v)) for k, v in conf.items() if "->" in k]
    grd = [x for x in pairs if x[0] in ("forehand", "backhand")]
    srv = [x for x in pairs if x[0] == "serve"]
    if not grd or not srv:
        out.append(_item(1, "Golpes", F3SET_KIND_ITEM, "aviso", f"sin la confusión de tipos en {f} (kind_confusion)"))
        return out
    g_ok, g_n = sum(n for a, b, n in grd if a == b), sum(n for _, _, n in grd)
    s_ok, s_n = sum(n for _, b, n in srv if b == "overhead"), sum(n for _, _, n in srv)
    ga, sa = g_ok / g_n, s_ok / s_n
    worst = sorted(((n, f"{a}→{b}") for a, b, n in grd + srv if not (a == b or (a == "serve" and b == "overhead"))), reverse=True)
    out.append(_item(1, "Golpes", F3SET_KIND_ITEM, "ok" if min(ga, sa) >= F3SET_KIND_MIN else "falta",
                     f"derecha/revés con su tipo {g_ok} de {g_n} ({ga:.1%}), saques {s_ok} de {s_n} ({sa:.1%}); objetivo ≥ "
                     f"{F3SET_KIND_MIN:.0%}" + (f"; confusiones: {', '.join(f'{k} {n}' for n, k in worst[:4])}" if worst else "")
                     + f" ({f})"))
    return out


# --- package B4 (08-11): the requests that had no check of their own on the outputs --------------------------------
# #23 (follow her across the changes of ends) was checked only by «golpes analizados» (any stroke analysed), #205
# (about 400 strokes with the 4 matches) and #155 were FALTA with no rule, #219 (far end counted and measured) borrowed
# the replays' check. Thresholds set by Claude (08-11), written here and in each item's detail.
IDENTITY_DECIDED_MIN = 0.95     # runs of the main camera whose near player is decided (hers or the opponent)
IDENTITY_AGREE_MIN = 0.90       # runs where the end-change chain (scoreboard) and her clothes say the same, of those
#                                 where both speak: two independent cues
IDENTITY_SAME_GAME_MIN = 0.95   # pairs of runs inside one game (no change of ends) with the same clothes group
ENDS_SHARE_MIN = 0.25           # share of her strokes at each end (she plays about half of each match at each one)
FAR_CONFIRMED_MIN = 0.90        # her candidate strokes confirmed by the fine pass (not discarded)
FAR_POSITION_MIN = 0.80         # her far strokes with what is measurable there: her position on court
VOLUME_MIN = 400                # «unos 400 golpes con 4 partidos» (docs/comparativa_apps.md §4.3), of the analysed stroke


def _sides_of(item: dict | None) -> tuple[int, int] | None:
    """(near, far) of her strokes from the item «Golpes encontrados frente al marcador» (its fields, or its text)."""
    if not item:
        return None
    if item.get("near") is not None and item.get("far") is not None:
        return int(item["near"]), int(item["far"])
    m = re.search(r"\((\d+) cerca, (\d+) lejos\)", item.get("detail", ""))
    return (int(m.group(1)), int(m.group(2))) if m else None


def with_click(d: Path, summ: dict | None) -> dict | None:
    """The identity summary once the user's click is applied (09-11): the click (identidad_clic.json) is applied by the
    candidates stage, never written back to identity.json, so the stage's own summary still said «0 decididos» for a
    match decided by the click (Osaka: 0 of 148 in the audit, 148 of 148 in the analysis). With a click, the runs decided
    are those of identity.json after apply_pick, and the two cues compared are the clothes groups and the end changes
    (the identity stage's own check, parity_agree): the click names her group, the groups are checked by the ends."""
    from .identity import PICK_FILE, apply_pick
    if not summ:
        return summ
    pf, idf = _mf.at(d, PICK_FILE), _mf.at(d, "identity.json")
    if not pf.exists() or not idf.exists():
        return summ
    try:
        ident = json.loads(idf.read_text(encoding="utf-8"))
        pick = json.loads(pf.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return summ
    new, why = apply_pick(ident, pick)
    if why.get("pick") != "aplicado":
        return summ
    runs = new.get("runs", [])
    out = {**summ, "runs": len(runs), "decided": sum(r.get("near_is_target") is not None for r in runs),
           "none": sum(r.get("near_is_target") is None for r in runs), "click": int(why.get("by_click") or 0)}
    ck = ((summ.get("clothes") or {}).get("check") or {})
    if ck.get("parity_agree") is not None and ck.get("parity_runs") and ck.get("distinguishable") is not False:
        n = int(ck["parity_runs"])
        out.update(agree=int(round(float(ck["parity_agree"]) * n)), ends_won=n - int(round(float(ck["parity_agree"]) * n)),
                   clothes_won=0, doubtful=0)
    return out


def identity_item(match: str, summ: dict | None, sides: tuple[int, int] | None) -> dict:
    """#23: she is followed across the changes of ends in one match, from the identity stage's summary (manifest):
    the runs decided, the two independent cues agreeing (end changes read on the scoreboard and her clothes), the
    clothes stable inside a game, and her strokes found at both ends."""
    name = f"Identidad en los cambios de lado: {match}"
    if not summ or not summ.get("runs"):
        return _item(1, "Golpes", name, "aviso", "sin el resumen de la etapa identity (manifest.json)")
    runs = int(summ["runs"])
    decided = int(summ.get("decided") or 0) / runs
    both = sum(int(summ.get(k) or 0) for k in ("agree", "ends_won", "clothes_won", "doubtful"))
    agree = int(summ.get("agree") or 0) / both if both else None
    same = (summ.get("clothes") or {}).get("same_game_same")
    bad = []
    if decided < IDENTITY_DECIDED_MIN - 1e-9:
        bad.append(f"planos decididos {decided:.0%} < {IDENTITY_DECIDED_MIN:.0%}")
    # 11-11: when the clothes do not tell the two players apart (both in white) their agreement with the end changes
    # says nothing; the end changes and the user's click decide, and only the runs decided count
    alike = ((summ.get("clothes") or {}).get("check") or {}).get("distinguishable") is False
    if not alike and (agree is None or agree < IDENTITY_AGREE_MIN - 1e-9):
        bad.append("cambios de lado y ropa sin comparar" if agree is None else
                   f"cambios de lado y ropa de acuerdo {agree:.0%} < {IDENTITY_AGREE_MIN:.0%}")
    if same is not None and same < IDENTITY_SAME_GAME_MIN - 1e-9 and not alike:
        # (11-11) players dressed alike: their clothes groups are not two people, so their stability says nothing
        bad.append(f"ropa igual dentro de un juego {same:.0%} < {IDENTITY_SAME_GAME_MIN:.0%}")
    ends = ""
    if sides is None:
        bad.append("sin el lado de sus golpes")
    else:
        n = sum(sides)
        low = min(sides) / n if n else 0.0
        ends = f"; sus golpes: {sides[0]} cerca y {sides[1]} lejos ({low:.0%} en el lado con menos)"
        if low < ENDS_SHARE_MIN - 1e-9:
            bad.append(f"golpes en un lado {low:.0%} < {ENDS_SHARE_MIN:.0%}")
    return _item(1, "Golpes", name, "aviso" if bad else "ok",
                 f"{summ.get('decided', 0)} de {runs} planos decididos ({decided:.0%}; objetivo ≥ {IDENTITY_DECIDED_MIN:.0%})"
                 + ("" if agree is None else f"; cambios de lado del marcador y ropa de acuerdo en {summ.get('agree')} de "
                    f"{both} planos con las dos señales ({agree:.0%}; objetivo ≥ {IDENTITY_AGREE_MIN:.0%})")
                 + ("" if same is None else f"; misma ropa dentro de un juego {same:.0%} (objetivo ≥ "
                    f"{IDENTITY_SAME_GAME_MIN:.0%})") + ends
                 + (f"; dudosos {summ.get('doubtful', 0)}, sin decidir {summ.get('none', 0)}")
                 + (f"; con su clic {summ['click']}" if summ.get("click") else "")
                 + (f" · falla: {', '.join(bad)}" if bad else "") + ". Sin verdad anotada: coherencia, no validación")


# what a far stroke has measured at that distance (CLAUDE.md, far end), as stroke fields of the fine pass
FAR_MEASURES = {
    "desplazamiento": lambda s: s.get("displacement_m") is not None,
    "altura del impacto": lambda s: (s.get("metrics") or {}).get("contact_height_pct") is not None,
    "destino": lambda s: bool(s.get("shot_bounce_m")),
}


def far_end_item(match: str, sides: tuple[int, int] | None, fine: dict | None, far_strokes: list[dict] | None,
                 far_candidates: int | None = None) -> dict:
    """#218/#219: the strokes of the main camera's far end count for her too: found (a fair share of hers at that
    end), confirmed by the fine pass (not discarded) and measured with what is measurable at that distance (position)."""
    name = f"Golpes del fondo: {match}"
    bad, txt = [], []
    if sides is None:
        bad.append("sin el lado de sus golpes")
    else:
        n = sum(sides)
        share = sides[1] / n if n else 0.0
        txt.append(f"{sides[1]} de sus {n} golpes en el lado lejano ({share:.0%}; objetivo ≥ {ENDS_SHARE_MIN:.0%})")
        if share < ENDS_SHARE_MIN - 1e-9:
            bad.append(f"lado lejano {share:.0%}")
    if far_candidates and sides is not None:          # per end, when the candidates are at hand
        conf = min(1.0, sides[1] / far_candidates)
        txt.append(f"confirmados {sides[1]} de {far_candidates} candidatos suyos del fondo ({conf:.0%})")
    elif fine and fine.get("candidates"):
        conf = int(fine.get("confirmed") or 0) / int(fine["candidates"])
        txt.append(f"confirmados {fine.get('confirmed')} de {fine['candidates']} candidatos suyos de los dos lados ({conf:.0%})")
    else:
        conf = None
        bad.append("sin el resumen de la pasada fina")
    if conf is not None and conf < FAR_CONFIRMED_MIN - 1e-9:
        bad.append(f"confirmados {conf:.0%} < {FAR_CONFIRMED_MIN:.0%}")
    if far_strokes is None:
        bad.append("sin strokes.json: lo medido en el fondo sin comprobar")
    elif far_strokes:
        n_f = len(far_strokes)
        pos = sum(bool(s.get("court_pos_m")) for s in far_strokes) / n_f
        txt.append(f"con su posición en la pista {pos:.0%} (objetivo ≥ {FAR_POSITION_MIN:.0%}; en el fondo solo lo fiable "
                   "a esa distancia: posición, desplazamiento, altura del impacto, destino)")
        # #219 (08-11): the rest of what is measurable at that distance, so the PC audit shows all of it
        shares = {k: sum(bool(f(s)) for s in far_strokes) / n_f for k, f in FAR_MEASURES.items()}
        near_pos = sum(s.get("court_pos_offset_s") not in (None, 0, 0.0) for s in far_strokes)
        # no phase of her body found (impact and extension come from the candidate, ready from the sound): no pose
        no_pose = sum(not any(((s.get("phases") or {}).get(k) or {}).get("frame") is not None
                              for k in ("takeback", "loaded", "acceleration", "finish", "recovery")) for s in far_strokes)
        txt.append(f"de sus {n_f} golpes del fondo: " + ", ".join(f"{k} {v:.0%}" for k, v in shares.items())
                   + (f"; posición de un fotograma a ≤ 0,2 s del impacto en {near_pos}" if near_pos else "")
                   + (f"; {no_pose} sin pose en la ventana (confirmados por la bola o el detector)" if no_pose else ""))
        if pos < FAR_POSITION_MIN - 1e-9:
            bad.append(f"posición medida {pos:.0%}")
    return _item(1, "Golpes", name, "aviso" if bad else "ok",
                 "; ".join(txt) + (f" · falla: {', '.join(bad)}" if bad else ""))


def volume_item(stroke: str, near: int, far: int, matches: int) -> dict:
    """#205: the volume the comparisons and the measurement noise need, about 400 strokes with the 4 matches."""
    n = near + far
    return _item(1, "Golpes", f"Volumen: {stroke} analizados en los partidos", "ok" if n >= VOLUME_MIN else "aviso",
                 f"{n} golpes ({near} cerca con todo el detalle, {far} lejos) en {matches} partidos; objetivo ≥ {VOLUME_MIN} "
                 "(docs/comparativa_apps.md §4.3)", n=n)


IDENTITY_TRUTH_MIN = 0.95       # her annotated strokes in runs whose identity was decided right, of the decided ones
FAR_RECALL_GAP_MAX = 0.10       # far-end recall on F3Set at most this below the near-end one (counted as the near ones)


def f3set_sides_items(out_root: Path) -> list[dict]:
    """#23, #218/#219 against annotated truth (F3Set, scripts/validate_recall.py, without the misaligned matches): the
    identity of the runs that hold her annotated strokes, and her far-end strokes found as often as the near-end ones."""
    names = ("Identidad frente a F3Set (anotado)", "Golpes del fondo frente a F3Set (anotado)")
    r, fname = None, None
    for name in ("recall_validation_detector.json", "recall_validation.json"):
        f = _find(out_root, name, f"datasets/reports/{name}")
        if f is not None:
            try:
                r, fname = json.loads(f.read_text(encoding="utf-8")), name
                break
            except (OSError, ValueError):
                continue
    if r is None:
        return [_item(1, "Golpes", n, "aviso", "sin recuento de F3Set (recall_validation_detector.json)") for n in names]
    s = r.get("summary_valid") or r.get("summary") or {}
    out = []
    ids = (s.get("identity") or {}).get("strokes") or {}
    right, wrong = int(ids.get("right") or 0), int(ids.get("wrong") or 0)
    if right + wrong:
        share = right / (right + wrong)
        out.append(_item(1, "Golpes", names[0], "ok" if share >= IDENTITY_TRUTH_MIN - 1e-9 else "aviso",
                         f"{right} de {right + wrong} golpes suyos anotados en planos con la identidad decidida la tienen bien "
                         f"({share:.0%}; objetivo ≥ {IDENTITY_TRUTH_MIN:.0%}); sin decidir {ids.get('undecided', 0)}, sin "
                         f"plano {ids.get('no_run', 0)}; perdidos por identidad {ids.get('lost_by_identity', 0)} ({fname})"))
    else:
        out.append(_item(1, "Golpes", names[0], "aviso", f"el recuento no tiene la identidad por golpe ({fname})"))
    bs = s.get("by_side") or {}
    nr, fr = (bs.get("near") or {}).get("recall"), (bs.get("far") or {}).get("recall")
    if nr is not None and fr is not None:
        gap = float(nr) - float(fr)
        out.append(_item(1, "Golpes", names[1], "ok" if gap <= FAR_RECALL_GAP_MAX + 1e-9 else "aviso",
                         f"lado lejano {bs['far'].get('found')} de {bs['far'].get('gt')} ({float(fr):.0%}) frente al cercano "
                         f"{bs['near'].get('found')} de {bs['near'].get('gt')} ({float(nr):.0%}); diferencia {gap * 100:.0f} "
                         f"puntos (objetivo ≤ {FAR_RECALL_GAP_MAX * 100:.0f}) ({fname})"))
    else:
        out.append(_item(1, "Golpes", names[1], "aviso", f"el recuento no tiene el recall por lado ({fname})"))
    return out


def b4_items(match_dirs: list[Path], items: list[dict], stroke: str, near: int, far: int) -> list[dict]:
    """The B4 checks of one run (audit): identity across ends and far-end strokes per match, and the volume."""
    out = [volume_item(stroke, near, far, len(match_dirs))]
    found = {i["name"].split(": ", 1)[1]: i for i in items if i["name"].startswith("Golpes encontrados frente al marcador: ")}
    for d in match_dirs:
        if d.name not in found:                      # no scoreboard read: not a complete match
            continue
        try:
            mf = _mf.at(d, "manifest.json")
            man = json.loads(mf.read_text(encoding="utf-8")) if mf.exists() else {}
            sides = _sides_of(found[d.name])
            out.append(identity_item(d.name, with_click(d, (man.get("identity") or {}).get("summary")), sides))
            st = _mf.at(d, "strokes.json")
            far_s = [s for s in json.loads(st.read_text(encoding="utf-8")) if s.get("side") == "far"] if st.exists() else None
            cf, n_far = _mf.at(d, "candidates.json"), None
            if cf.exists():
                cj = json.loads(cf.read_text(encoding="utf-8"))
                cands = cj.get("candidates", cj) if isinstance(cj, dict) else cj
                n_far = sum(c.get("side") == "far" and c.get("target", c.get("identity")) is True for c in cands) or None
            out.append(far_end_item(d.name, sides, (man.get("fine") or {}).get("summary"), far_s, n_far))
        except Exception as e:  # noqa: BLE001 — the audit must still be written
            out.append(_item(1, "Golpes", f"Identidad en los cambios de lado: {d.name}", "aviso", f"no se pudo calcular ({e})"))
    return out


def serve_coverage(d: Path) -> dict | None:
    """B4 (08-11): her serves found and the points of her serve the TV showed in one match folder, with the same
    inputs and the same numbers as the item «Saques por punto de su saque» (recall_items): serve_gaps over score.json,
    strokes.json, the main-camera shots, spotting, candidates, doubtful and dropped strokes. None without score.json."""
    from .point_count import serve_gaps

    sc = _mf.at(d, "score.json")
    if not sc.exists():
        return None
    load = lambda name, default=None: (json.loads(_mf.at(d, name).read_text(encoding="utf-8"))
                                       if _mf.at(d, name).exists() else default)
    readings = (load("score.json") or {}).get("readings") or []
    strokes = load("strokes.json", [])
    try:
        doubt = load("strokes_doubtful.json", [])
    except (OSError, ValueError):
        doubt = []
    shots = []
    scn = load("scenes.json")
    if scn:
        fps = float(scn.get("fps") or 1.0)
        shots = [(sh["start"] / fps, sh["end"] / fps) for sh in scn.get("shots", []) if sh.get("main_camera")]
    cj = load("candidates.json")
    cands = (cj.get("candidates", cj) if isinstance(cj, dict) else cj) if cj is not None else None
    g = serve_gaps(readings, strokes, shots, spotted=load("spotting.json"), candidates=cands, doubtful=doubt,
                   dropped=load("strokes_descartados.json"))
    unseen = g.get("unseen", 0)
    return {"found": g["found"], "points": g["points"], "unseen": unseen, "shown": g["points"] - unseen}


def serve_coverage_text(match_dirs: list[tuple[str, Path]]) -> dict:
    """The sentences of the serve report (screen «Datos del análisis»): one per match ({"match", "text"}) and the
    total over the matches with a scoreboard; «sin marcador…» where score.json is missing."""
    from .point_count import NO_SCOREBOARD, serve_coverage_sentence

    rows, found, shown, missing = [], 0, 0, 0
    for label, d in match_dirs:
        try:
            c = serve_coverage(d)
        except (OSError, ValueError, KeyError, TypeError) as e:
            rows.append({"match": label, "text": f"no se pudo calcular ({e})"})
            continue
        if c is None:
            missing += 1
            rows.append({"match": label, "text": NO_SCOREBOARD})
            continue
        found, shown = found + c["found"], shown + c["shown"]
        rows.append({"match": label, "text": serve_coverage_sentence(c["found"], c["shown"])})
    if missing == len(match_dirs):
        total = NO_SCOREBOARD
    else:
        total = serve_coverage_sentence(found, shown) + (" (solo los partidos con marcador)" if missing else "")
    return {"matches": rows, "total": total, "limitation": SERVE_FAR_GAP}


def serve_coverage_item(match_dirs: list[Path], report_html: Path | None) -> dict:
    """«Cobertura del saque dicha en el informe» (B4, 08-11): the serve report says how much of her serves it covers,
    with the numbers of serve_gaps (tolerance 0) for each match and in total."""
    from html import unescape

    from .point_count import NO_SCOREBOARD

    name = "Cobertura del saque dicha en el informe"
    if report_html is None or not report_html.exists():
        return _item(1, "Golpes", name, "aviso", f"no se encontró el informe del saque ({report_html})")
    try:
        txt = unescape(report_html.read_text(encoding="utf-8"))
    except OSError as e:
        return _item(1, "Golpes", name, "aviso", f"no se pudo leer el informe del saque ({e})")
    exp = serve_coverage_text([(d.name, d) for d in match_dirs])
    want = ([(r["match"], r["text"]) for r in exp["matches"]] + [("total", exp["total"].split(" (solo")[0])]
            + [("limitación", exp["limitation"])])
    bad = [f"{m}: falta «{t}»" for m, t in want if t not in txt]
    shown = [t for m, t in want if t != NO_SCOREBOARD]
    if bad:
        return _item(1, "Golpes", name, "aviso", "el informe del saque no dice su cobertura con los números del "
                     "marcador: " + "; ".join(bad[:6]), expected=want)
    return _item(1, "Golpes", name, "ok", "el informe del saque lo dice: " + "; ".join(f"{m}: {t}" for m, t in want)
                 + ("" if shown else " (sin marcador en ningún partido)"), expected=want)


def _board_drops(dropped: list[dict] | None) -> dict:
    """The scoreboard's serve candidates (source «marcador») the fine pass dropped, by reason (08-11)."""
    out: dict = {}
    for x in dropped or []:
        if x.get("source") == "marcador":
            out[str(x.get("why"))] = out.get(str(x.get("why")), 0) + 1
    return out


def camera_items(match_dirs: list[Path], stroke: str = "forehand", weak_below: int = 6) -> list[dict]:
    """B-15a (docs/analisis_referencias.md §2): how much of each measure the camera explains, from her near strokes
    and the homography of their series; a measure at 10 % or more and above chance is the picture, not her."""
    from .camera_share import LIMIT, camera_of, shares

    rows = []
    for d in match_dirs:
        f = _mf.at(d, "strokes.json")
        if not f.exists():
            continue
        try:
            strokes = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for s in strokes:
            if s.get("stroke") != stroke or s.get("side") == "far" or not s.get("series"):
                continue
            try:
                ser = json.loads((f.parent / s["series"]).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            cam = camera_of(ser.get("H"), (s.get("height_scale") or {}).get("px"), s.get("camera_pitch_deg"))
            if cam:
                rows.append((d.name, cam, stroke_values(s)))
    res = shares(rows)
    name = f"{stroke}: medidas que dependen de la cámara (la cámara explica ≥ {LIMIT:.0%} de su variación)"
    if not res:
        return [_item(3, "Fiabilidad", name, "pocos datos",
                      f"{len(rows)} golpes con la homografía de su ventana: hacen falta al menos 40")]
    bad = [e for e in res if e["camera_dependent"]]
    nm = len({r[0] for r in rows})
    weak = (f"; prueba débil con {nm} partidos (cámaras parecidas): «dentro del azar» no demuestra que no dependan"
            if nm < weak_below else "")
    det = (f"{len(res)} medidas en {len(rows)} golpes de {nm} partidos; dependen de la cámara: "
           + (", ".join(f"{e['measure']} {e['share']:.0%} (azar {e['chance']:.0%})" for e in bad[:12]) or "ninguna")
           + weak)
    return [_item(3, "Fiabilidad", name, "aviso" if bad else ("pocos datos" if weak else "ok"), det,
                  measures=res)]


def views_items(match_dirs: list[Path], min_strokes: int = 20) -> list[dict]:
    """#218: per match, the share of her strokes with a linked replay of the main camera and with another
    camera of the broadcast (side, front, close-up), from strokes.json (`views`, tennisbio.views)."""
    from .views import coverage

    out = []
    for d in match_dirs:
        st = _mf.at(d, "strokes.json")
        if not st.exists():
            continue
        name = f"Repeticiones y otras cámaras enlazadas: {d.name}"
        if not (_mf.at(d, "views.json")).exists():
            out.append(_item(1, "Repeticiones y otras cámaras", name, "aviso",
                             "la etapa «views» no se ha ejecutado en este partido (sin views.json)"))
            continue
        try:
            strokes = json.loads(st.read_text(encoding="utf-8"))
            vs = json.loads((_mf.at(d, "views.json")).read_text(encoding="utf-8")).get("summary") or {}
        except (OSError, ValueError):
            continue
        c = coverage(strokes)
        det = (f"{c['replay_share']:.0%} de sus golpes con repetición enlazada ({c['with_replay']} de {c['strokes']}, "
               f"{c['with_slowmo']} a cámara lenta) · {c['other_share']:.0%} con otra cámara ({c['with_other_camera']}) · "
               f"tomas: {vs.get('repeticion_principal', 0)} repeticiones, {vs.get('lateral', 0)} laterales, "
               f"{vs.get('frontal', 0)} frontales, {vs.get('primer_plano', 0)} primeros planos, {vs.get('otra', 0)} otras")
        status = "pocos datos" if c["strokes"] < min_strokes else ("ok" if c["with_replay"] or c["with_other_camera"] else "aviso")
        out.append(_item(1, "Repeticiones y otras cámaras", name, status, det, **{k: v for k, v in c.items()}))
    return out


VIEW_CLIPS_OK = 0.9        # share of her linked strokes whose clips exist and are in the report
SLOWMO_OK = 0.5            # share of her slow-motion replays measured (she can be out of the replay's frame)


def _json_doc(f: Path) -> dict:
    try:
        doc = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def view_clips_items(match_dirs: list[Path], report_dir: Path | None, stroke: str = "forehand") -> list[dict]:
    """#218 (09-11): per match, «Repeticiones en el informe: <partido>»: of her strokes of this type with a linked
    replay or other camera (strokes.json `views`), the share whose every clip exists (view_clips stage) and is
    referenced in the report's page (the stroke's «Análisis de golpe»). Its detail says what is missing."""
    from .view_stages import CLIPS_FILE
    from .views import stroke_key

    html = ""
    if report_dir is not None and (report_dir / "index.html").exists():
        try:
            html = (report_dir / "index.html").read_text(encoding="utf-8")
        except OSError:
            html = ""
    out = []
    for d in match_dirs:
        st = _mf.at(d, "strokes.json")
        if not st.exists():
            continue
        name = f"Repeticiones en el informe: {d.name}"
        try:
            strokes = [s for s in json.loads(st.read_text(encoding="utf-8")) if s.get("stroke") == stroke]
        except (OSError, ValueError):
            continue
        linked = [s for s in strokes if s.get("views")]
        if not linked:
            out.append(_item(2, "Repeticiones y otras cámaras", name, "pocos datos",
                             f"ninguno de sus {len(strokes)} golpes ({stroke}) tiene repeticiones u otras cámaras enlazadas"))
            continue
        doc = _json_doc(_mf.at(d, CLIPS_FILE))
        if not doc.get("clips") and not doc.get("summary"):
            out.append(_item(2, "Repeticiones y otras cámaras", name, "aviso",
                             f"{len(linked)} golpes con tomas enlazadas, pero la etapa «view_clips» no se ha ejecutado (sin {CLIPS_FILE})"))
            continue
        folder = _mf.at(d, doc.get("dir") or "view_clips")
        by_key: dict = {}
        for c in doc.get("clips") or []:
            by_key.setdefault(c.get("key"), []).append(c)
        ok = no_clip = not_shown = 0
        for s in linked:
            cs = by_key.get(stroke_key(s), [])
            exists = bool(cs) and all(c.get("ok", True) and (folder / c["file"]).exists() and (folder / c["file"]).stat().st_size > 0
                                      for c in cs)
            shown = bool(cs) and bool(html) and all(f"{folder.name}/{c['file']}" in html for c in cs)
            ok += exists and shown
            no_clip += not exists
            not_shown += exists and not shown
        share = ok / len(linked)
        det = (f"{share:.0%} de sus golpes con tomas enlazadas tienen sus recortes y están en el informe ({ok} de {len(linked)})"
               + (f" · {no_clip} sin recorte" if no_clip else "") + (f" · {not_shown} con recorte pero no en el informe" if not_shown else "")
               + ("" if html else " · sin informe (index.html) que comprobar")
               + f" · {(doc.get('summary') or {}).get('clips', 0)} recortes en el partido")
        out.append(_item(2, "Repeticiones y otras cámaras", name, "ok" if share >= VIEW_CLIPS_OK else "aviso", det,
                         linked=len(linked), shown=ok, no_clip=no_clip, not_shown=not_shown))
    return out


def slowmo_items(match_dirs: list[Path], report_dir: Path | None, stroke: str = "forehand") -> list[dict]:
    """#218 (09-11), with `views.fine_on_slowmo` on: per match, «Medidas en la cámara lenta: <partido>»: of her
    near strokes of this type with a slow-motion replay whose impact instant is known, the share measured on it
    (slowmo_fine stage) and shown in the report; every measured value kept beside, never in place of, the live one
    (the live values of strokes.json are not touched). Not written when the switch is off."""
    from .view_stages import SLOWMO_FILE
    from .views import slowmo_view, stroke_key

    html = None
    if report_dir is not None and (report_dir / "index.html").exists():
        try:
            html = (report_dir / "index.html").read_text(encoding="utf-8")
        except OSError:
            html = None
    out = []
    for d in match_dirs:
        st = _mf.at(d, "strokes.json")
        f = _mf.at(d, SLOWMO_FILE)
        doc = _json_doc(f)
        if not st.exists() or (f.exists() and doc.get("enabled") is False):
            continue
        name = f"Medidas en la cámara lenta: {d.name}"
        try:
            strokes = [s for s in json.loads(st.read_text(encoding="utf-8")) if s.get("stroke") == stroke and s.get("side") != "far"]
        except (OSError, ValueError):
            continue
        want = [s for s in strokes if slowmo_view(s) is not None]
        if not want:
            # nothing to measure is not a failure (09-11): the check is that every stroke with such a replay is measured
            # and shown; with none, it holds and says so (the other matches show it working on real replays)
            out.append(_item(2, "Repeticiones y otras cámaras", name, "ok" if strokes else "pocos datos",
                             f"ninguno de sus {len(strokes)} golpes cercanos ({stroke}) tiene repetición a cámara lenta con su "
                             "instante: nada que medir en este partido"))
            continue
        if not f.exists():
            out.append(_item(2, "Repeticiones y otras cámaras", name, "aviso",
                             f"{len(want)} golpes con cámara lenta, pero la etapa «slowmo_fine» no se ha ejecutado (sin {SLOWMO_FILE})"))
            continue
        got = {m.get("key"): m for m in doc.get("strokes") or [] if m.get("measures")}
        measured = [s for s in want if stroke_key(s) in got]
        share = len(measured) / len(want)
        vals = sum(len(got[stroke_key(s)]["measures"]) for s in measured)
        # in the report: the stroke's slow-motion clip is referenced in its page (with its measures beside it)
        n_shown = sum(f"slowmo/{got[stroke_key(s)].get('clip')}" in html for s in measured) if html is not None else 0
        det = (f"{share:.0%} de sus golpes con repetición a cámara lenta medidos en ella ({len(measured)} de {len(want)}, "
               f"{vals} valores junto a los del directo) · {(doc.get('summary') or {}).get('frames', 0)} fotogramas en "
               f"{(doc.get('summary') or {}).get('seconds', 0):.0f} s"
               + (f" · {n_shown} de {len(measured)} con «en la repetición a cámara lenta» en el informe" if html is not None
                  else " · sin informe que comprobar"))
        bad = share < SLOWMO_OK or (html is not None and n_shown < len(measured))
        out.append(_item(2, "Repeticiones y otras cámaras", name, "aviso" if bad else "ok", det,
                         slowmo=len(want), measured=len(measured), shown=n_shown))
    return out


def situation_items(strokes: list[dict], min_n: int) -> list[dict]:
    """Each situation the user named (plan block 3, situations.ASKED): her strokes in it, the strokes where
    its signals were measured, and whether «Aprende» offers it as a condition. «pocos datos» = «sin golpes
    suficientes» (fewer than min_n: the lesson cannot be shown with her strokes of that kind)."""
    from .learn import CONDITIONS
    from .situations import ASKED, apply

    out = []
    for s in strokes:                          # outputs written before the situations existed
        apply(s, overwrite=False)
    cls = [((s.get("technique") or {}).get("classes") or {}) for s in strokes]
    for label, (key, levels) in ASKED.items():
        offered = key in CONDITIONS and all(lv in CONDITIONS[key][1] for lv in levels)
        n = sum(c.get(key) in levels for c in cls)
        measured = sum(c.get(key) is not None for c in cls)
        det = (f"{n} golpes de {len(strokes)} (la clase «{CONDITIONS.get(key, (key,))[0]}» se pudo decidir en {measured}; "
               f"sin señal, ninguna clase: nunca se inventa)")
        if key == "contact_type" and "media volea" in levels:
            cand = sum("half_volley_candidate" in (s.get("review") or []) for s in strokes)
            no_b = sum(1 for s in strokes if (s.get("metrics") or {}).get("bounce_to_impact_s") is None)
            det += (f"; candidatos marcados por la misma regla: {cand}; golpes sin bote visto: {no_b} (la bola no deja ver un "
                    "bote a menos de 0,06 s del impacto a 50 fps, 0,08 s a 25: ball.min_bounce_to_impact_s)")
        if not offered:
            st, det = "falta", det + "; no es una condición de «Aprende» (learn.CONDITIONS)"
        elif n >= min_n:
            st = "ok"
        else:
            st, det = "pocos datos", det + f"; sin golpes suficientes (se enseña con ≥ {min_n})"
        out.append(_item(1, "Situaciones", label, st, det, n=n, measured=measured))
    return out


def _combination_items(model: dict, vals: list[dict], min_n: int, factors: dict) -> list[dict]:
    from .explain import LINES

    keys = [k for p in LINES for k, _ in LINES[p]]
    view = model.get("variants") or {}
    out = []
    for label, fk in VARIANTS_ASKED.items():
        if not fk:
            continue
        levels = factors[fk][1] if fk in factors else []
        ok_lv, few_lv, bad = [], [], []
        combos = combos_ok = 0
        for lv in levels:
            own = [v for v in vals if v.get(f"class.{fk}") == lv]
            n_k = {k: sum(1 for v in own if v.get(k) is not None) for k in keys}
            v = view.get(f"{fk}|{lv}")
            enough = [k for k, n in n_k.items() if n >= min_n]
            combos += len(keys)
            if len(own) < min_n or v is None:
                if len(own) >= min_n:
                    bad.append(f"{lv}: {len(own)} golpes y no está en «Su derecha»")
                few_lv.append(f"{lv} {len(own)}")
                continue
            cards = v.get("cards") or []
            shown = {ln["key"] for c in cards for ln in c.get("lines", [])}
            miss = [k for k in enough if k not in shown]
            empty = [c["phase"] for c in cards if not c.get("lines")]
            if len(cards) < 8 or empty:
                bad.append(f"{lv}: fases sin contenido {empty or len(cards)}")
            if not v.get("strokes"):
                bad.append(f"{lv}: sin vídeos")
            if miss:
                bad.append(f"{lv}: {len(miss)} medidas con golpes suficientes sin mostrar ({', '.join(miss[:4])})")
            combos_ok += len(enough) - len(miss)
            ok_lv.append(lv)
        st = "falta" if bad else "ok" if ok_lv else "pocos datos"
        out.append(_item(1, "Combinaciones", f"{label}: cada medida en cada nivel",
                         st, f"{len(keys)} medidas × {len(levels)} niveles = {combos} combinaciones; "
                         f"{combos_ok} mostradas con ≥ {min_n} golpes" + (f"; niveles con pocos golpes: {', '.join(few_lv)}" if few_lv else "")
                         + (f"; PROBLEMAS: {'; '.join(bad[:4])}" if bad else ""), combos=combos, shown=combos_ok))
    return out


def _practice_items(pr: dict | None, report_dir: Path | None) -> list[dict]:
    from .practice import D3_METRICS, D3_VIEWS, FRONT_METRICS, MIN_N, SIDE_METRICS

    area = "Vista lateral (entrenamiento)"
    if not pr or not pr.get("videos"):
        return [_item(6, area, "Vídeos de entrenamiento analizados", "aviso",
                      "todavía no hay vídeos de entrenamiento (se bajan en el PC con la prueba rápida; ver el registro)")]
    st = pr.get("strokes") or []
    side = [s for s in st if s.get("view") == "lateral" and s.get("stroke") == "forehand" and not s.get("discarded") and not s.get("unconfirmed")]
    disc = [s for s in st if s.get("discarded")]
    items = [_item(6, area, "Vídeos de entrenamiento analizados", "ok",
                   f"{len(pr['videos'])} vídeos, {len(st)} golpes; cámara: {pr.get('views')}; "
                   f"{len(disc)} descartados por valores imposibles"),
             _item(6, area, "Derechas filmadas de lado", "ok" if len(side) >= MIN_N else "pocos datos",
                   f"{len(side)} (se resume cada medida con {MIN_N} o más)")]
    front = [s for s in st if s.get("view") == "frontal" and s.get("stroke") == "forehand" and not s.get("discarded") and not s.get("unconfirmed")]
    in3d = [s for s in st if s.get("view") in D3_VIEWS and s.get("stroke") == "forehand" and not s.get("discarded") and not s.get("unconfirmed")]
    for k, (lab, _, _) in {**SIDE_METRICS, **FRONT_METRICS, **D3_METRICS}.items():
        e = (pr.get("summary") or {}).get(k) or {}
        n = e.get("n", 0)
        own = front if k in FRONT_METRICS else in3d if k in D3_METRICS else side
        status = "ok" if e.get("median") is not None else "pocos datos" if n or len(own) < MIN_N else "falta"
        where = "de frente" if k in FRONT_METRICS else "con estimación 3D" if k in D3_METRICS else "de lado"
        items.append(_item(1, area, lab, status, f"{n} derechas {where} con esta medida"
                           + (f"; mediana {e['median']}" if e.get("median") is not None else "")))
    if report_dir and pr.get("base"):
        miss = [s["id"] for s in st if not s.get("clip") or not (report_dir / pr["base"] / s["clip"]).exists()]
        items.append(_item(2, area, "Cada golpe de entrenamiento tiene su vídeo con el esqueleto", "falta" if miss else "ok",
                           f"{len(st) - len(miss)} de {len(st)}" + (f"; sin vídeo: {', '.join(miss[:5])}" if miss else "")))
    return items


def _codecs(files: list[Path]) -> dict:
    if not shutil.which("ffprobe"):
        return {}
    out = {}
    for f in files:
        try:
            r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name",
                                "-of", "csv=p=0", str(f)], capture_output=True, text=True, timeout=20)
            out[f.name] = r.stdout.strip() or "?"
        except (OSError, subprocess.SubprocessError):
            out[f.name] = "?"
    return out


def _screens(shots_dir: Path) -> list[dict]:
    """Screens of the report as the user sees them (capturas.json + one image per screen)."""
    import cv2

    meta_f = shots_dir / "capturas.json"
    if not meta_f.exists():
        return [_item(2, "Pantallas", "Capturas del informe", "aviso", "no se pudieron hacer las capturas (ver el registro)")]
    meta = json.loads(meta_f.read_text(encoding="utf-8"))
    items = []
    if not meta.get("h264", True):
        items.append(_item(2, "Pantallas", "Navegador de las capturas", "aviso",
                           f"{meta.get('browser', '')} no reproduce H.264: las capturas salen sin vídeo (Brave en Windows sí lo reproduce)"))
    for sc in meta.get("screens", []):
        img = cv2.imread(str(shots_dir / sc["file"])) if sc.get("file") else None
        blank = img is None or float(np.std(img)) < 6
        empty = sc.get("text_chars", 0) < 80
        no_video = sc.get("tab") == "golpe" and meta.get("h264", True) and not sc.get("videos")
        black = sc.get("black_canvases", 0)
        st = "falta" if blank or empty or sc.get("errors") or no_video or black else "ok"
        if "intro" in sc and not sc["intro"]:
            st, det_intro = "falta", "; no dice para qué sirve (sin frase de entrada)"
        else:
            det_intro = ""
        if sc.get("tables"):
            items.append(_item(2, "Pantallas", f"Tablas a la vista en «{sc.get('title', sc.get('tab'))}»", "aviso",
                               f"{sc['tables']} tablas (el usuario pidió información en frases, no tablas)"))
        if sc.get("many_lines"):
            st = "falta"
            det_intro += f"; {sc['many_lines']} gráficas con más de 4 líneas a la vista (difíciles de leer)"
        if sc.get("external_links"):
            items.append(_item(6, "Pantallas", f"Enlaces externos en «{sc.get('title', sc.get('tab'))}»", "falta",
                               f"{sc['external_links']} enlaces a otras webs"))
        det = f"{sc.get('text_chars', 0)} caracteres de texto, {sc.get('videos', 0)} vídeos, {sc.get('charts', 0)} gráficos"
        if sc.get("empty_msgs"):
            det += f"; mensajes de vacío: {sc['empty_msgs']}"
        if sc.get("errors"):
            det += f"; errores: {'; '.join(sc['errors'][:3])}"
        if blank:
            det += "; la imagen sale vacía"
        if no_video:
            det += "; el vídeo del golpe no se carga"
        if black:
            det += f"; {black} imágenes salen en negro"
        det += det_intro
        items.append(_item(2, "Pantallas", f"Pantalla «{sc.get('title', sc.get('tab'))}»", st, det, file=sc.get("file")))
    if meta.get("errors"):
        items.append(_item(2, "Pantallas", "Errores de la página", "falta", "; ".join(meta["errors"][:5])))
    by = {sc.get("tab"): sc for sc in meta.get("screens", [])}
    for pb in (meta.get("plays") or []) + [{**x, "name": x["name"] + " (con las animaciones de Windows desactivadas)"}
                                           for x in meta.get("plays_reduced_motion") or []]:
        if not pb.get("present"):
            continue
        ok = pb.get("plays") or not meta.get("h264", True)
        items.append(_item(2, "Vídeo", f"Reproducir: {pb['name']}", "ok" if pb.get("plays") else "aviso" if ok else "falta",
                           "el vídeo arranca y avanza" if pb.get("plays") else
                           ("sin H.264 en este navegador: no se puede comprobar" if ok else "al pulsarlo el vídeo no arranca")
                           + (f" ({pb['error']})" if pb.get("error") else "")))
    if "plays" in (by.get("golpe") or {}) and meta.get("h264", True):
        items.append(_item(2, "Vídeo", "El vídeo del golpe se reproduce al pulsar ▶", "ok" if by["golpe"]["plays"] else "falta",
                           "avanza y sigue reproduciéndose" if by["golpe"]["plays"] else "al pulsar ▶ no avanza o se para"))
    lr = meta.get("learn")
    if lr is not None:
        if lr.get("error"):
            items.append(_item(1, "Aprende su derecha", "La pantalla responde a cada combinación", "falta", f"no se pudo comprobar: {lr['error']}"))
        else:
            f = lr.get("failures") or []
            items.append(_item(1, "Aprende su derecha", "La pantalla responde a cada combinación", "falta" if f else "ok",
                               f"{lr['combinations']} combinaciones (cada condición, cada pareja y el ejemplo del usuario), "
                               f"{lr['checkpoints_checked']} puntos de control comprobados; {lr['with_exact_strokes']} con golpes exactos"
                               + (f"; FALLOS en {len(f)}: " + "; ".join(f"{x['sel']}: {', '.join(x['bad'][:2])}" for x in f[:4]) if f else "")))
        ex = lr.get("example")
        if ex:
            items.append(_item(1, "Aprende su derecha", "Tu ejemplo: derecha paralela, apoyo cerrado, parada, plana, lado de su derecha",
                               "falta" if ex.get("bad") else "ok" if ex.get("exact") else "pocos datos",
                               f"{ex.get('exact', 0)} golpes exactos, {ex.get('near', 0)} parecidos; "
                               f"{ex.get('valued', 0)} de {ex.get('rows', 0)} puntos con su valor medido"
                               + (f"; FALLOS: {', '.join(ex['bad'][:3])}" if ex.get("bad") else "")))
        if "signature" in lr:
            items.append(_item(1, "Aprende su derecha", "Lo que la distingue: su firma (rasgos que repite) con vídeo",
                               "ok" if lr["signature"] else "pocos datos",
                               f"{lr['signature']} rasgos que repite en ≥ 75 % de sus golpes, solo de medidas fiables"))
            items.append(_item(1, "Aprende su derecha", "Estilo de su derecha en una frase",
                               "ok" if "faltan" not in (lr.get("style") or "faltan") else "pocos datos", lr.get("style") or "—"))
        if lr.get("rows_all"):
            items.append(_item(1, "Aprende su derecha", "Puntos de «Aprende» con su valor medido (todas sus derechas)",
                               "ok" if lr["valued_all"] >= 0.8 * lr["rows_all"] else "pocos datos",
                               f"{lr['valued_all']} de {lr['rows_all']}; el resto dice por qué falta"))
        if "targeted_all" in lr:
            items.append(_item(1, "Aprende su derecha", "«Tu objetivo»: la consigna con su número en cada medida suya fiable",
                               "ok" if lr["targeted_all"] else "pocos datos",
                               f"{lr['targeted_all']} medidas con su número para copiar (las ruidosas o sesgadas no lo llevan); "
                               f"{lr.get('glossed_all', 0)} palabras con su explicación al tocarlas; guía de primer uso y glosario comprobados"))
    en = meta.get("entry")
    if en is not None:
        if en.get("error"):
            items.append(_item(2, "Diseño", "Primera pantalla, anchura y nombres (diseño definitivo)", "falta", f"no se pudo comprobar: {en['error']}"))
        else:
            e = en.get("entry") or {}
            items.append(_item(2, "Diseño", "Primera pantalla, anchura y nombres (diseño definitivo)", "falta" if en.get("failures") else "ok",
                               f"vídeo de la lección en y={e.get('vid_top')}–{e.get('vid_bottom')} de {e.get('height')}; al abrir {e.get('h2')} títulos, "
                               f"{e.get('words')} palabras, {e.get('buttons')} botones" + (f"; FALLOS: {'; '.join(en['failures'])}" if en.get("failures") else "")))
    ls = meta.get("lesson")
    if ls is not None:
        if ls.get("error"):
            items.append(_item(1, "Aprende su derecha", "La lección: vídeo primero y como mucho 3 claves por fase", "falta", f"no se pudo comprobar: {ls['error']}"))
        else:
            n, f = len(ls.get("phases") or []), ls.get("failures") or []
            items.append(_item(1, "Aprende su derecha", "La lección: como mucho 3 claves por fase, cada una con su valor, ejercicio y cómo comprobarlo",
                               "falta" if f or not n else "ok" if ls.get("with_keys") == n else "pocos datos",
                               f"{ls.get('with_keys', 0)} de {n} fases con claves suyas fiables"
                               + (f"; FALLOS: " + "; ".join(f"{x['phase']}: {', '.join(x['why'])}" for x in f[:4]) if f else "")))
            items.append(_item(2, "Vídeo", "La lección enseña su vídeo de cada fase, en bucle",
                               "ok" if n and ls.get("with_video") == n else "aviso" if ls.get("with_video") else "falta",
                               f"{ls.get('with_video', 0)} de {n} fases con su vídeo cargado"))
            th = ls.get("thumbs", 0)
            items.append(_item(2, "Vídeo", "La tira de fases enseña su golpe en fotos reales, como las secuencias de los entrenadores",
                               "pocos datos" if not ls.get("with_video") else "ok" if n and th >= n - 1 else "aviso" if th else "falta",
                               f"{th} de {n} fases con su foto en la tira" if ls.get("with_video") else "sin vídeo en esta ejecución"))
    checks = [("golpe", "ball_moments", "«La bola y ella»: qué hace cuando golpea la rival, cruza la red, bota y golpea ella", 2),
              ("golpe", "feet_cycle", "«Sus pies en este golpe»: el ciclo de pies del split step a la recuperación (8 pasos)", 8),
              ("golpe", "ball_measures", "«La bola y ella»: medidas reales en cada fotograma (cadera en cm, pies en m, recorrido)", 3),
              ("golpe", "body_hip", "«Bajar y subir»: 3 fotogramas (espera, punto más bajo, más alto tras golpear) con barras y cm", 4),
              ("golpe", "body_base", "«Base»: fotogramas con la barra entre los pies y su distancia en la pista", 3),
              ("golpe", "body_trunk", "«Tronco al terminar»: fotograma con la línea de hombros y hacia dónde mira", 2),
              ("golpe", "heights_layer", "Barras de altura de la cabeza y la cadera sobre el vídeo", 1),
              ("videoteca", "lib_filters", "Filtros combinables de la videoteca (apoyo, dirección, bola, contacto…)", 10),
              ("datos", "news", "Novedades de la versión (en «Datos del análisis»)", 1),
              ("golpe", "sentences", "«Análisis de golpe»: la raqueta por fase dicha en frases (la tabla sigue debajo)", 1),
              ("explorador", "sentences", "«Explorador»: resumen en frases de los golpes filtrados (la tabla sigue debajo)", 1),
              ("conclusiones", "sentences", "«Conclusiones»: qué cambia, en frases (la tabla sigue debajo)", 1),
              ("comparar", "sentences", "«Comparar golpes»: diferencias en frases (la tabla sigue debajo)", 1)]
    for tab, key, name, need in checks:
        v = (by.get(tab) or {}).get(key)
        if v is None:
            continue
        items.append(_item(2, "Vistas pedidas", name, "ok" if int(v) >= need else "falta", f"{int(v)} en la pantalla"))
    return items


PETITIONS_DOC = ROOT / "docs" / "peticiones_usuario.md"
# petition number → the audit items (name or area, regular expression) that check it on the real outputs;
# a string instead is why it cannot be checked on the outputs of a run
class Note(str):
    """Why a request is not checked on the outputs of a run (process, decision, document)."""


PETITIONS = {
    1: Note("pendiente por diseño: los 4 partidos se analizan una vez, al final"), 2: Note("aplazado por el usuario (móvil al final)"),
    3: Note("aplazado por el usuario (nube al final)"),
    4: r"^Taxonomía$|^Situaciones$|^Combinaciones$|^Aprende su derecha$", 5: r"^Situaciones$|^Combinaciones$|^Aprende su derecha$",
    6: r"Pies y desplazamiento|Sus pies en este golpe|Split step|Pasos", 7: r"· Empuñadura|Posición de la mano en el mango|Mano libre en la garganta", 8: r"^Cuerdas$|Cara de la raqueta",
    9: r"^Pantallas$|Tablas a la vista", 10: r"Novedades|Reproducir", 11: r"^Taxonomía$|^Combinaciones$|^Vistas pedidas$",
    12: r"Validación con clips anotados",
    14: r"^Rendimiento$", 15: r"Vídeos de análisis de entrenadores", 16: r"Botepronto|Volea",
    17: r"Pantalla «Cópiala|Novedades|^Aprende su derecha$", 18: r"golpes analizados", 19: r"Cada golpe tiene su vídeo",
    21: r"golpes analizados", 22: r"golpes analizados", 23: r"golpes analizados",
    24: r"Presión, set, fatiga", 25: r"Separación cadera|Ángulo del codo|Tipo de apoyo|Cadena cinética",
    26: r"Fotograma clave", 27: r"Presión, set, fatiga", 28: r"Cada golpe tiene su esqueleto|Cada golpe tiene su vídeo",
    29: r"^Rendimiento$", 30: Note("documento de estado del arte (docs), no una salida"), 31: Note("proceso (caché por etapas), no una salida"),
    32: Note("configuración (config/players, config/strokes), no una salida"), 33: r"Fotograma clave",
    34: Note("maqueta (docs/maqueta-informe.html), no una salida"), 35: r"Cara de la raqueta|Caída de la raqueta",
    36: r"Retraso de la muñeca|Posición de la mano en el mango", 37: r"golpes analizados",
    38: r"Dirección|Bote: profundidad", 39: r"golpes analizados", 40: Note("scripts de doble clic (instalar, prueba, análisis)"),
    41: r"Resumen PDF", 42: r"Cada golpe tiene su vídeo|Reproducir", 43: Note("decisión de arquitectura (sin servidor)"),
    44: r"Enlaces externos|Vídeos de entrenamiento analizados|^Pantallas$", 45: r"Nada pide revisión manual|Golpes que fallaron",
    46: r"Resumen PDF|Valores dentro de límites", 47: r"^Taxonomía$", 48: r"Curvas de altura|Cabeza estable",
    49: Note("registros subidos solos a pc-logs"), 50: Note("registros con fecha y duración en la terminal"),
    52: r"Navegador de las capturas|Pantalla «",
    53: r"^Pantallas$", 54: r"La bola y ella", 55: r"Filtros combinables", 56: r"Barras de altura", 57: r"más de 4 líneas|Tablas a la vista|^Pantallas$",
    58: Note("elección de modelos (RTMPose, YOLO11, TrackNetV3, RTMW3D)"), 59: r"^Valores posibles$|Cada frase lleva",
    64: r"Split step|Pasos de ajuste|Pasos cruzados|Pasos de recuperación|Paso de ataque|Número de pasos|Sus pies en este golpe",
    65: r"^Reproducir|se reproduce al pulsar", 66: Note("registros con fecha y duración (comun.ps1), no una salida"),
    67: r"^Pantallas$|la tabla sigue debajo", 68: r"^Aprende su derecha$|Puntos de «Aprende» con su valor",
    69: r"Tu ejemplo", 70: r"responde a cada combinación|^Combinaciones$",
    71: r"responde a cada combinación|Vídeos de análisis de entrenadores|^Examen de entrenadores$",
    72: r"tiene su sitio en la pantalla|^Taxonomía$", 73: r"^Pantallas$|^Vistas pedidas$",
    74: Note("análisis documental (docs/comparativa_apps.md), no una salida"), 75: r"^Rendimiento$",
    76: r"Golpes dudosos", 77: Note("lanzadores cortos (2c, 2d) sin repetir el análisis de vídeo"),
    78: Note("proceso: Claude propone las funciones desde la matriz y los entrenadores"), 79: r"Vista lateral",
    80: Note("cadena de prueba, auditoría y subida a pc-logs"), 81: Note("tamanos.txt y auditoría en Python sin Claude"),
    82: Note("salidas en C:\\tenis\\output, registros en pc-logs, caché por etapas"), 83: r"^Ficheros$",
    84: r"Empuje de piernas|Rotación pélvica|Separación cadera|Giro de hombros|Extensión del codo|Retraso de la muñeca|Cadena cinética",
    85: r"Cabeza estable|Brazo recto|Brazo libre|Inclinación (lateral|del tronco)|flexión de rodillas|Rodilla de atrás|Pie de arrastre",
    86: r"Bucle de la preparación|Caída de la raqueta|Cara de la raqueta|Trayectoria vertical",
    87: r"Apoyos abierto|Apoyo abierto extremo|Apoyo en suspensión|Tipo de apoyo",
    88: r"Split step|Pasos de ajuste|Pasos cruzados|Paso de ataque|Pasos de recuperación",
    89: r"Golpe plano, liftado|Botepronto|Volea de derecha|Terminación (baja|en látigo|sobre el hombro)",
    90: r"Adaptación a bola|^Situaciones$", 91: r"Dirección: cruzado|Dirección del golpe",
    92: r"Zona de impacto|Equilibrio al terminar|Relajación",
    93: r"Propiedades de la raqueta", 94: r"Velocidad de la cabeza de la raqueta|Velocidad angular|Tasa de desarrollo|Efecto, ángulo",
    95: r"Latencia de reacción|Mirada fija|Activación muscular", 96: r"Pronación del antebrazo|Rangos articulares",
    97: r"Apertura prematura|casting|Fuerza en dirección incorrecta|Estabilidad lumbopélvica",
    98: r"Superficie de la pista|Aerodinámica", 99: r"Pantalla «Análisis de golpe»",
    100: r"Raqueta al lado del cuerpo", 101: r"Altura y separación del codo", 102: r"Punta de la raqueta respecto a la cabeza",
    103: r"Transferencia de peso", 104: r"Empuje de piernas", 105: r"Inicio de la aceleración respecto al bote",
    106: r"Frenado de los hombros", 107: r"Caída de la raqueta (bajo el impacto|por debajo de la bola)",
    108: r"girar mientras se desplaza", 109: r"Brazo libre recogido|Equilibrio al terminar|Terminación sobre",
    110: r"Lo que la distingue", 111: r"responde a cada combinación", 112: r"Estilo de su derecha",
    113: r"^Examen de entrenadores$",
    114: r"La bola y ella", 115: r"Bajar y subir|Cuánto baja|Cuánto sube", 116: r"«Base»|Base al armar|Base en el impacto|Pies quietos",
    117: r"Tronco al terminar|Hacia dónde mira el tronco",
    118: r"técnica o ruido|^Fiabilidad", 119: Note("ciclo automático del PC: revision_automatica.md en pc-logs"),
    120: r"^Pantallas$", 121: r"^Pantallas$", 122: r"^Pantallas$|Pantalla «",
    123: r"responde a cada combinación", 124: r"Hacia dónde mira el tronco|Manos en la espera|técnica o ruido",
    125: r"^Rendimiento$",
    126: r"Tu objetivo", 127: r"Tu objetivo|responde a cada combinación", 128: r"Tu objetivo|responde a cada combinación",
    129: Note("descartado por el usuario (13-10): sin hoja de sesión"),
    130: r"Resto de derecha|Resto:|Lado del resto|Dirección del saque|responde a cada combinación",
    218: r"^Repeticiones y otras cámaras$",
    # the code's tests on this PC (Windows native, generic code, robustness tests), 03-11
    13: r"Pruebas del código en este PC|Golpes que fallaron|Etapas con errores", 20: r"^Rendimiento$|Pruebas del código en este PC",
    241: r"Pruebas del código en este PC", 51: r"Pruebas del código en este PC",
    # Base packages (config/plan_peticiones.yaml), 02-11
    137: r"^Rendimiento$", 231: r"^Rendimiento$", 230: r"^Rendimiento$",
    237: Note("GitHub Actions: cada petición con su registro en la pestaña Actions del repositorio"),
    225: r"Golpes que fallaron|Etapas con errores", 232: r"Golpes que fallaron|Etapas con errores|Exportación",
    233: r"golpes analizados|Etapas con errores|Golpes encontrados frente al marcador",
    134: r"golpes analizados|Golpes encontrados frente al marcador",
    234: Note("prueba de valor del 27-10 (docs/plan_maestro.md, R2)"),
    151: r"golpes analizados|Golpes encontrados frente al marcador|^Tipo de golpe frente a F3Set", 219: r"^Repeticiones y otras cámaras$|Golpes encontrados frente al marcador",
    132: r"Golpe angulado", 157: r"Bola corta baja cerca de la red", 158: r"Bola corta alta cerca de la red",
    159: r"Volea a media pista con golpe de fondo|Volea fuera de la línea de saque",
}
# requests checked by their own tests run on the PC (module_tests_items), 03-11: they replace the notes above
_T = "Pruebas en este PC: "
PETITIONS.update({
    31: _T + "test_pipeline$", 32: _T + "(test_app_core|test_no_hardcoded_player)$", 49: _T + "test_auto_cycle$",
    80: _T + "test_auto_cycle$", 119: _T + "(test_auto_cycle|test_pc_requests)$", 144: _T + "test_auto_cycle$",
    152: _T + "(test_library|test_layout)$", 160: _T + "(test_app_window|test_app_core)$", 161: _T + "test_library$",
    220: _T + "(test_library|test_layout)$", 222: _T + "test_identity_click$", 226: _T + "test_app_window$",
    227: _T + "test_app_window$", 229: _T + "(test_auto_catalog_rename|test_library)$",
    242: _T + "(test_app_core|test_app_window)$", 225: r"Golpes que fallaron|Etapas con errores|" + _T + "(test_no_unbounded_calls|test_app_window)$",
    232: r"Golpes que fallaron|Etapas con errores|Exportación|" + _T + "(test_no_unbounded_calls|test_export_end)$",
    241: r"Pruebas del código en este PC|" + _T + "test_no_hardcoded_player$",
})
# Base packages B1 and B3, 04-11 (base_items, cli.run_audit): each request with a check on the outputs, the PC's
# configuration or its own tests on the PC; added on top of the rules above, never instead of a stricter one.
# Until 07-11 without an automatic check, on purpose: #30 (a document: docs/comparativa_apps.md); since 07-11 the
# document is checked against the measured models, the latest F3Set recall and its date (comparison_doc_item).
PETITIONS.update({
    # B1 · speed and use of the PC
    10: r"Novedades|Reproducir|" + _T + "test_auto_cycle$",
    77: _T + "(test_auto_cycle|test_pc_requests)$",
    137: r"^Rendimiento$|^Trabajo en paralelo$|" + _T + "(test_fine_ahead|test_parallel|test_fine_parallel)$",
    230: r"^Rendimiento$|^Uso del PC$|" + _T + "test_resources_summary$",
    231: r"^Rendimiento$|^Tiempo por etapa$|" + _T + "test_budget$",
    237: r"^Peticiones por GitHub Actions",
    # B3 · best models (each candidate measured against the current one; the adopted ones in use)
    58: r"^Modelo candidato medido|^Modelo en uso",
    138: r"^Modelo en uso: esqueleto híbrido|" + _T + "test_hybrid_pose$",
    199: r"^Modelo candidato medido: bounce|" + _T + "test_candidates$",
    200: r"^Modelo candidato medido: court14|^Modelo en uso: pista de 14 puntos|" + _T + "(test_court|test_candidates)$",
    201: r"^Modelo candidato medido: ocr5|" + _T + "test_candidates$",
    202: r"^Modelo candidato medido: wasb|^Modelo en uso: bola|" + _T + "test_candidates$",
    203: r"^Modelo candidato medido: mag3d|^Modelo en uso: giro 3D|" + _T + "test_trunk3d$",
    204: r"^Modelo candidato medido: f3ed|^Modelo en uso: detector de golpes|^Golpes del detector aprendido|"
         + _T + "(test_spotting|test_spotting_stage)$",
    221: r"^Modelo en uso: detector de golpes|^Golpes del detector aprendido|"
         + _T + "(test_spotting|test_spotting_stage|test_stroke_from_spotter)$",
})
# 04-11 to 06-11 #30 was a Note («documento de estado del arte (docs/comparativa_apps.md): sin comprobación automática
# posible; los modelos que compara se miden en #58 y #199-#204»). 07-11: the document is checked against the measured
# state (comparison_doc_item: its models, its detection figures, its date).
PETITIONS[30] = r"^Comparativa con otras apps al día"

# package B7 (04-11): the notes and unchecked requests of the base, now with their own tests run on the PC and the
# checks read from the PC's own files (infrastructure_items); they replace the notes above
PETITIONS.update({
    40: _T + "test_windows_scripts$", 43: _T + "test_local_only$", 145: _T + "test_local_only$",
    50: r"^Progreso visible|" + _T + "test_logs_progress$", 66: r"^Registros con fecha y duración$|" + _T + "test_logs_progress$",
    81: r"^Tamaño de la salida|" + _T + "test_output_places$", 82: _T + "(test_output_places|test_pipeline)$",
    136: _T + "test_project_context$", 139: _T + "test_speed_keeps_quality$", 146: r"^Carpetas de pruebas antiguas$",
    # «completo»: also the strokes found against the scoreboard (none lost), not only nothing asked to the user
    45: r"Nada pide revisión manual|Golpes que fallaron|Golpes encontrados frente al marcador",
    160: r"^Aplicación: |" + _T + "(test_app_window|test_app_core)$",
    242: r"^Aplicación: |" + _T + "(test_app_core|test_app_window)$",
})
# package B6 (08-11): the two requests of the 4 matches' reference that were only notes, now checked on the outputs.
# Until 08-11 #1 was Note («pendiente por diseño: los 4 partidos se analizan una vez, al final») and #234 Note
# («prueba de valor del 27-10 (docs/plan_maestro.md, R2)»).
# #1: the 4 complete matches analysed with every stage, no stroke failed, and none of hers lost against the scoreboard
#     (all of them and her serves per point); the final run, once, at the end, is still the plan's.
# #234: the value test with the real data, repeatable: the application holds the analysis of the real matches and the
#     screens the 27-10 test judged (Cópiala, Conclusiones) are painted with their content; what it found wrong has its
#     own request (#244 point result, #245 names; the kinetic chain in #84/#235).
PETITIONS.update({
    1: r"golpes analizados|^Partido .*: salida de cada etapa|Etapas con errores|^Golpes que fallaron al procesarse|"
       r"^Golpes encontrados frente al marcador|^Saques por punto de su saque",
    234: r"^Aplicación: análisis en su índice$|^Pantalla «(Cópiala|Conclusiones)",
})
# package B4 (08-11): each request with its own check on the outputs (b4_items). Until 08-11: #23 r"golpes analizados"
# (any stroke analysed, nothing about the ends), #155 and #205 no rule (FALTA), #218 r"^Repeticiones y otras cámaras$",
# #219 r"^Repeticiones y otras cámaras$|Golpes encontrados frente al marcador" (the replays are #218's, not the far end).
PETITIONS.update({
    23: r"^Identidad en los cambios de lado: |^Identidad frente a F3Set",
    155: r"^Golpes encontrados frente al marcador|^Saques por punto de su saque|^Golpes inventados: precisión en F3Set",
    205: r"^Volumen: ",
    218: r"^Repeticiones y otras cámaras$|^Golpes del fondo: |^Golpes del fondo frente a F3Set",
    219: r"^Golpes encontrados frente al marcador|^Golpes del fondo: |^Golpes del fondo frente a F3Set",
})
# #218 (09-11): the replays and other cameras shown on the stroke's page and measured on the slow-motion replay; until
# 09-11 r"^Repeticiones y otras cámaras$|^Golpes del fondo: |^Golpes del fondo frente a F3Set" (the area of the linking
# check and the far end's checks). The new checks are in the same area: the rule names them as well.
PETITIONS[218] = (r"^Repeticiones y otras cámaras$|^Golpes del fondo: |^Golpes del fondo frente a F3Set"
                  r"|^Repeticiones en el informe: |^Medidas en la cámara lenta: ")
# 11-11 (R7 of the review of the Base): B8 had no check of its own («sin medir»); the queue's checks name its requests,
# and #237 (start each job at once) also the queue's own wait, not only the GitHub Actions job's
PETITIONS.update({
    246: r"^Orquestador: ", 249: r"^Orquestador: prueba de extremo a extremo",
    226: r"^Lista de partidos: rival, torneo, ronda y fecha",
    41: r"Resumen PDF|^Vídeos exportados: |^Exportación terminada: ",
    225: r"^Aplicación: lo que consume abierta|Golpes que fallaron|Etapas con errores|Pruebas en este PC: (test_no_unbounded_calls|test_app_window)$",
    237: r"^Peticiones por GitHub Actions|^Orquestador: espera hasta empezar|^Orquestador: ejecutor vivo",
    119: r"^Orquestador: ejecutor vivo|^Orquestador: espera hasta empezar",
})
ORDER = {"falta": 0, "aviso": 1, "pocos datos": 2, "ok": 3}
# hours of processing per hour of video. The user's requirement 9 is «un partido en horas, no días»; the former
# 45/35 (35 min in ≤ 45 min) was Claude's own target. 10-11, with the user: a 3.5 h match in one night, ≤ 8 h
# from scratch, without losing quality (halving the frames was measured and refused: bench_fine_fps)
SPEED_TARGET = 8 / 3.5


def parse_petitions(path: Path = PETITIONS_DOC) -> list[tuple[int, str, str]]:
    """(number, request, state in the document) of each row of the table of user requests."""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines() if path.exists() else []:
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) >= 3 and c[0].isdigit():
            out.append((int(c[0]), c[1], c[2]))
    return out


def code_tests_item(log: Path | None) -> dict:
    """The code's automatic tests run on this PC after each new code (scripts/windows/pruebas_fondo.ps1): Windows,
    its iGPU and its paths, not only the cloud. Red when a test fails or the run was cut."""
    name = "Pruebas del código en este PC"
    if log is None:
        return _item(5, "Automático", name, "aviso", "todavía no se han ejecutado aquí (pruebas.log)")
    txt = log.read_text(encoding="utf-8-sig", errors="replace")       # Out-File utf8 writes a BOM (Windows PowerShell)
    head = dict(ln.split(": ", 1) for ln in txt.splitlines()[:4] if ": " in ln)
    m = re.search(r"(\d+) passed", txt)
    f = re.search(r"(\d+) failed", txt)
    e = re.search(r"(\d+) errors?\b", txt)
    passed, failed, errors = (int(x.group(1)) if x else 0 for x in (m, f, e))
    cut = "cortado" in head.get("codigo", "")
    st = "falta" if failed or errors or cut or not passed else "ok"
    names = re.findall(r"^FAILED (\S+)", txt, re.M)[:5]
    det = (f"código {head.get('commit', '?')} ({head.get('fin', '?')}): {passed} bien, {failed} fallan, {errors} errores"
           + ("; cortado a los 40 min" if cut else "") + (f"; fallan: {', '.join(names)}" if names else ""))
    return _item(5, "Automático", name, st, det, passed=passed, failed=failed)


# test modules that check user requests on the PC itself (pruebas.xml of scripts/windows/pruebas_fondo.ps1), 03-11
MODULE_TESTS = ("test_pipeline", "test_auto_cycle", "test_pc_requests", "test_library", "test_layout",
                "test_identity_click", "test_app_core", "test_app_window", "test_auto_catalog_rename",
                "test_no_hardcoded_player", "test_no_unbounded_calls",
                # Base packages B1 and B3, 04-11
                "test_budget", "test_resources_summary", "test_fine_ahead", "test_parallel", "test_fine_parallel",
                "test_hybrid_pose", "test_candidates", "test_court", "test_trunk3d", "test_spotting",
                "test_spotting_stage", "test_stroke_from_spotter",
                # package B7 (04-11)
                "test_windows_scripts", "test_local_only", "test_logs_progress", "test_output_places",
                "test_project_context", "test_speed_keeps_quality",
                # package B2 (04-11): an export cut or hung is reported, every export folder (#232)
                "test_export_end")


def module_tests_items(xml: Path | None) -> list[dict]:
    """One item per test module of MODULE_TESTS, from the PC's own run of the tests (JUnit XML): «ok» when all its
    tests passed there, «falta» when one failed, «aviso» when it did not run. Requests point at them (PETITIONS)."""
    if xml is None:
        return [_item(5, "Pruebas en este PC", f"Pruebas en este PC: {m}", "aviso", "todavía sin pruebas.xml")
                for m in MODULE_TESTS]
    import xml.etree.ElementTree as ET
    try:
        root = ET.parse(xml).getroot()
    except (ET.ParseError, OSError) as e:
        return [_item(5, "Pruebas en este PC", f"Pruebas en este PC: {m}", "aviso", f"pruebas.xml ilegible ({e})")
                for m in MODULE_TESTS]
    per: dict[str, dict] = {m: {"ok": 0, "fail": [], "skip": 0} for m in MODULE_TESTS}
    for tc in root.iter("testcase"):
        mod = (tc.get("classname") or "").split(".")[-1]
        if mod not in per:
            continue
        if tc.find("failure") is not None or tc.find("error") is not None:
            per[mod]["fail"].append(tc.get("name"))
        elif tc.find("skipped") is not None:
            per[mod]["skip"] += 1
        else:
            per[mod]["ok"] += 1
    out = []
    for m, r in per.items():
        st = "falta" if r["fail"] else ("ok" if r["ok"] else "aviso")
        det = (f"{r['ok']} bien, {len(r['fail'])} fallan, {r['skip']} omitidas"
               + (f"; fallan: {', '.join(r['fail'][:4])}" if r["fail"] else "") + (" (no se ejecutó)" if not any(r.values()) else ""))
        out.append(_item(5, "Pruebas en este PC", f"Pruebas en este PC: {m}", st, det))
    return out


# Base packages B1 and B3 (config/plan_peticiones.yaml), 04-11: checks computed from what the PC leaves next to the
# match folders (bench_candidates.json, ritmos.json, recursos/*.csv, ciclo_actions.log), from the manifests and from
# the PC's own configuration (the models the next analysis will use)

# candidates of scripts/bench_candidates.py → (what it is, the model it would replace)
CANDIDATE_MODELS = {
    "wasb": ("bola WASB", "TrackNetV3"), "rtmw": ("esqueleto RTMW-x", "RTMPose-x"),
    "court14": ("pista de 14 puntos (TennisCourtDetector)", "búsqueda de líneas"),
    "rfdetr": ("jugadora lejana RF-DETR", "YOLO11 en la mitad lejana"),
    "f3ed": ("detector de golpes F3ED", "detector propio entrenado con F3Set"),
    "ocr5": ("marcador PP-OCRv5", "PP-OCRv4 (rapidocr 1.4)"), "mag3d": ("giro 3D MotionAGFormer", "RTMW3D"),
    "bounce": ("bote CatBoost", "regla del giro de la bola"),
}
STAGE_SLOW_FACTOR = 2.0       # a stage is «slow» at this many times its usual rate on this PC (budgets.factor)
STAGE_MIN_REFS = 3            # runs of a stage on this PC needed to say what is usual
ACTIONS_WAIT_MIN = 10.0       # #237: a request must start within this (the waits were 10-40 min)


def _find(out_root: Path, *rels: str) -> Path | None:
    """The first of out_root/rel, its parent/rel or its grandparent/rel that exists."""
    for b in (out_root, out_root.parent, out_root.parent.parent):
        for r in rels:
            if (b / r).exists():
                return b / r
    return None


def candidate_items(out_root: Path) -> list[dict]:
    """B3: one item per state-of-the-art candidate, from the PC's measure (scripts/bench_candidates.py →
    bench_candidates.json): «ok» when it was measured against the current model (accuracy on annotated data and
    speed on this PC) and decided; «falta» when its measure failed; «aviso» when not measured or too little data."""
    f = _find(out_root, "bench_candidates.json", "datasets/reports/bench_candidates.json")
    rep = None
    if f is not None:
        try:
            rep = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            rep = None
    out = []
    for name, (what, ours) in CANDIDATE_MODELS.items():
        iname = f"Modelo candidato medido: {name} ({what})"
        if rep is None:
            out.append(_item(12, "Modelos", iname, "aviso",
                             "sin bench_candidates.json (se mide en el PC con scripts/bench_candidates.py)"))
            continue
        r = (rep.get("results") or {}).get(name)
        v = (r or {}).get("verdict") or {}
        if not r:
            st, det = "aviso", "todavía sin medir"
        elif r.get("error"):
            st, det = "falta", f"la medida falló: {str(r['error'])[:160]}"
        elif not v or v.get("insufficient"):
            st, det = "aviso", f"medida incompleta: {v.get('reason', 'sin decisión')}"
        else:
            st = "ok"
            det = (f"frente a {r.get('baseline') or ours}: precisión {r.get('accuracy', '?')}; velocidad {r.get('speed', '?')}; "
                   f"{'se adopta' if v.get('adopt') else 'no se adopta'} ({v.get('reason', '')[:160]})")
        out.append(_item(12, "Modelos", iname, st, det + f" [{rep.get('generated', '?')}, {rep.get('device', '?')}]"))
    return out


def models_in_use_items(cfg: dict | None = None) -> list[dict]:
    """B3: the models the next analysis uses, from this PC's configuration and its model files: an adopted model
    configured without its file falls back to the former one (the pipeline never stops), and that is said here."""
    from .config import resolve_path

    if cfg is None:
        try:
            from .config import load_config
            cfg = load_config()
        except Exception as e:  # noqa: BLE001 — the audit must still be written
            return [_item(12, "Modelos", "Modelo en uso: configuración", "aviso", f"no se pudo leer la configuración ({e})")]
    from . import court, trunk3d

    def has(p) -> bool:
        q = resolve_path(p)
        return q is not None and Path(q).exists()

    fp = cfg.get("fine_pass") or {}
    sp = cfg.get("spotter") or {}
    rows = [
        ("detector de golpes aprendido (F3Set)", bool(sp.get("enabled")), has(sp.get("onnx")),
         f"spotter.enabled: {sp.get('enabled')}, {sp.get('onnx')}"),
        ("esqueleto híbrido (YOLO11 + RTMPose)", fp.get("pose_model") == "hybrid", True,
         f"fine_pass.pose_model: {fp.get('pose_model')}, refine: {fp.get('refine')}"),
        ("pista de 14 puntos (TennisCourtDetector)", str((cfg.get("court") or {}).get("detector", "tcd14")).lower() == "tcd14",
         Path(court.TCD_ONNX).exists(), f"court.detector: {(cfg.get('court') or {}).get('detector', 'tcd14')}"),
        ("giro 3D del tronco (MotionAGFormer)", ((cfg.get("trunk3d") or {}).get("model") or "motionagformer") == "motionagformer",
         trunk3d.model_path(cfg) is not None, f"trunk3d.model: {(cfg.get('trunk3d') or {}).get('model', 'motionagformer')}"),
        ("bola (TrackNetV3 de RacketVision)", bool((cfg.get("ball") or {}).get("onnx")), has((cfg.get("ball") or {}).get("onnx")),
         f"ball.onnx: {(cfg.get('ball') or {}).get('onnx')}"),
        ("raqueta (RTMPose de RacketVision)", bool((cfg.get("racket_face") or {}).get("pose_onnx")),
         has((cfg.get("racket_face") or {}).get("pose_onnx")), f"racket_face.pose_onnx: {(cfg.get('racket_face') or {}).get('pose_onnx')}"),
        ("cortes de plano (TransNetV2)", bool((cfg.get("scenes") or {}).get("onnx")), has((cfg.get("scenes") or {}).get("onnx")),
         f"scenes.onnx: {(cfg.get('scenes') or {}).get('onnx')}"),
    ]
    out = []
    for label, chosen, present, det in rows:
        st = "ok" if chosen and present else "aviso"
        why = ("elegido y con su modelo en este PC" if st == "ok" else
               "no elegido en la configuración" if not chosen else "elegido pero sin su fichero: se usa lo anterior")
        out.append(_item(12, "Modelos", f"Modelo en uso: {label}", st, f"{why} ({det})"))
    return out


def spotter_items(match_dirs: list[Path]) -> list[dict]:
    """#204/#221: per match, whether its candidate strokes came from the learned detector (manifest of the run)."""
    out = []
    for d in match_dirs:
        f = _mf.at(d, "manifest.json")
        try:
            man = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        except (OSError, ValueError):
            continue
        cand = (man.get("candidates") or {}).get("summary") or {}
        if not cand:
            continue
        sp = (man.get("spotting") or {}).get("summary") or {}
        ok = cand.get("source") == "spotter" and sp.get("enabled")
        out.append(_item(12, "Modelos", f"Golpes del detector aprendido: {d.name}", "ok" if ok else "aviso",
                         (f"{cand.get('candidates', '?')} candidatos del detector entrenado con F3Set "
                          f"({sp.get('near', '?')} cerca, {sp.get('far', '?')} lejos, umbral {sp.get('threshold', '?')})")
                         if ok else f"candidatos de las reglas, no del detector aprendido (origen: {cand.get('source') or 'reglas'})"))
    return out


def stage_time_items(match_dirs: list[Path], out_root: Path) -> list[dict]:
    """#231 (a match cannot take twice as long without knowing why): per match, each stage that really computed
    (≥ budget.REAL_RUN_S) in seconds per minute of video, against the slowest of its rates on this PC
    (ritmos.json); a stage above STAGE_SLOW_FACTOR × that rate is named, with the alarm raised live if any."""
    from .budget import ALARMS, RATES, REAL_RUN_S

    rf = _find(out_root, RATES)
    try:
        rates = json.loads(rf.read_text(encoding="utf-8")) if rf else {}
        alarms = (json.loads(af.read_text(encoding="utf-8")) if (af := _find(out_root, ALARMS)) else {}).get("alarmas") or []
    except (OSError, ValueError):
        rates, alarms = {}, []
    out = []
    for d in match_dirs:
        f = _mf.at(d, "manifest.json")
        try:
            man = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        except (OSError, ValueError):
            continue
        dur = ((man.get("probe") or {}).get("summary") or {}).get("duration_min")
        if not dur:
            continue
        name = f"Tiempo de cada etapa frente a su ritmo en este PC: {d.name}"
        slow, judged, rows = [], 0, []
        for st, e in man.items():
            if not isinstance(e, dict) or (e.get("seconds") or 0) < REAL_RUN_S:
                continue
            rate = e["seconds"] / dur
            ref = [x["s"] for x in rates.get(f"{st}:minuto", []) if isinstance(x.get("s"), (int, float))]
            rows.append((e["seconds"], st))
            if len(ref) < STAGE_MIN_REFS:
                continue
            judged += 1
            # against the slowest past run here, not the median (08-11, as budget.budget_per_unit since 04-11): the
            # median came from runs that only re-read their caches, and a stage that really computed (584c5b's fine
            # after a code change, 7.5 min) was named slow
            med = float(np.max(ref))
            if med > 0 and rate > STAGE_SLOW_FACTOR * med:
                al = [a for a in alarms if a.get("etapa") == st]
                slow.append(f"{st} {rate:.1f} s por min de vídeo, {rate / med:.1f} veces la más lenta aquí ({med:.1f})"
                            + (f"; alarma en vivo: {al[-1].get('texto', '')[:100]}" if al else "; sin alarma en vivo"))
        if not rows:
            continue
        top = ", ".join(f"{st} {s / 60:.1f} min" for s, st in sorted(rows, reverse=True)[:5])
        if not judged:
            out.append(_item(9, "Tiempo por etapa", name, "pocos datos",
                             f"{top}; sin ritmos suficientes de esas etapas en este PC (ritmos.json, hacen falta {STAGE_MIN_REFS})"))
            continue
        out.append(_item(9, "Tiempo por etapa", name, "aviso" if slow else "ok",
                         f"{judged} etapas comparadas con su mediana aquí; las que más tardan: {top}"
                         + (f"; MÁS LENTAS de {STAGE_SLOW_FACTOR:.0f} veces: " + " · ".join(slow) if slow else
                            f"; ninguna pasa de {STAGE_SLOW_FACTOR:.0f} veces su ritmo habitual")))
    return out


def parallel_items(match_dirs: list[Path]) -> list[dict]:
    """#137: per match, the minutes of stages that ran at the same time as another (manifest `overlap_s`)."""
    out = []
    for d in match_dirs:
        f = _mf.at(d, "manifest.json")
        try:
            man = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        except (OSError, ValueError):
            continue
        ov = {st: e.get("overlap_s", 0) for st, e in man.items() if isinstance(e, dict) and e.get("overlap_s")}
        if not any(isinstance(e, dict) and e.get("seconds") for e in man.values()):
            continue
        out.append(_item(9, "Trabajo en paralelo", f"Etapas a la vez: {d.name}", "ok" if ov else "aviso",
                         (f"{sum(ov.values()) / 60:.1f} min ganados con etapas a la vez ("
                          + ", ".join(f"{k} {v / 60:.1f} min" for k, v in ov.items()) + ")") if ov else
                         "todas las etapas de su última ejecución corrieron en serie"))
    return out


def resources_items(out_root: Path) -> list[dict]:
    """#230: CPU, RAM, iGPU and disk per stage (min / mean / max) of the latest run, from the samples of
    scripts/windows/medir_recursos.ps1 (<output>/recursos/*.csv) summarized by scripts/resources_summary.py."""
    name = "Uso del PC por etapa (CPU, RAM, iGPU y disco)"
    d = _find(out_root, "recursos")
    files = sorted(d.glob("recursos_*.csv")) if d else []
    if not files:
        return [_item(9, "Uso del PC", name, "aviso", "sin mediciones (recursos/*.csv de medir_recursos.ps1)")]
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("resources_summary", ROOT / "scripts" / "resources_summary.py")
        rs = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rs)
    except Exception as e:  # noqa: BLE001 — the audit must still be written
        return [_item(9, "Uso del PC", name, "aviso", f"no se pudo cargar resources_summary ({e})")]
    # the latest run with samples of a stage running (08-11: a run from the caches can end before any sample falls
    # inside a stage, and its file alone said nothing about the PC); the newer empty ones are named
    groups, after_min, used, skipped = [], 0.0, None, []
    for f in reversed(files[-10:]):
        try:
            allg = [g for g in rs.summarize(rs.read([f])) if g.get("etapa")]
        except Exception:  # noqa: BLE001 — a damaged file is skipped, and said
            skipped.append(f.name)
            continue
        # samples once the stage named had ended are not that stage's (07-11, #230): apart, at the end
        groups = [g for g in allg if not g.get("after")]
        if groups:
            after_min, used = round(sum(g["minutos"] for g in allg if g.get("after")), 1), f
            break
        skipped.append(f.name)
    if not groups:
        return [_item(9, "Uso del PC", name, "aviso", f"{files[-1].name} sin muestras con su etapa (ni las 9 anteriores)")]
    fmt = lambda t: "/".join("—" if x != x else f"{x:.0f}" for x in t)          # NaN → —
    det = "; ".join(f"{g['partido'][:30]} {g['etapa']} ({g['minutos']} min): CPU {fmt(g['stats']['cpu_total'])} %, "
                    f"iGPU {fmt(g['stats']['gpu_3d'])} %, RAM máx {g['stats']['ram_usada_gb'][2]:.1f} GB → {g['limite']}"
                    for g in groups[:6])
    if after_min:
        det += f"; {after_min} min de muestras con la etapa ya terminada (no cuentan para ninguna etapa)"
    if skipped:
        det += f"; más recientes sin muestras de una etapa en marcha (ejecuciones desde las cachés): {', '.join(skipped[:3])}"
    return [_item(9, "Uso del PC", name, "ok", f"{used.name} (mín/media/máx): {det}")]


def _request_time(repo: Path = ROOT):
    """Local time of the last commit that starts a job of the PC's runner (config/peticion_pc.txt or the workflow)."""
    from datetime import datetime
    try:
        r = subprocess.run(["git", "log", "-1", "--format=%ct", "--", "config/peticion_pc.txt", ".github/workflows/pc.yml"],
                           cwd=repo, capture_output=True, text=True, timeout=20)
        return datetime.fromtimestamp(int(r.stdout.strip())) if r.stdout.strip() else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _previous_job_end(folder: Path, before, skip: str = "ciclo_actions.log"):
    """The latest end of another PC job (its log in `folder`: transcript «End time:», «terminado fecha» of
    comun.ps1 or «termina fecha» of a request) up to `before` (+1 min); None when there is none. The Actions job
    waits while the PC is busy, so that time is not a wait of the runner (#237)."""
    from datetime import datetime, timedelta
    pats = ((r"End time: (\d{14})", "%Y%m%d%H%M%S"),
            (r"terminado (\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})", None),
            (r"termina (\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?)", None))
    best = None
    for f in folder.glob("*.log"):
        if f.name == skip:
            continue
        try:
            with f.open("rb") as h:
                h.seek(max(f.stat().st_size - 8192, 0))
                tail = h.read().decode("utf-8", errors="replace")
        except OSError:
            continue
        for pat, fmt in pats:
            for s in re.findall(pat, tail):
                try:
                    t = datetime.strptime(s, fmt) if fmt else datetime.fromisoformat(s.replace(" ", "T"))
                except ValueError:
                    continue
                if t <= before + timedelta(minutes=1) and (best is None or t > best):
                    best = t
    return best


def actions_item(out_root: Path, request_time=None) -> dict:
    """#237: the PC starts each request at once (GitHub Actions runner). From the transcript of the last job
    (<output>/ciclo_actions.log, «Start time») against the time of the last request commit."""
    from datetime import datetime, timedelta
    name = "Peticiones por GitHub Actions: espera hasta empezar"
    f = _find(out_root, "ciclo_actions.log")
    if f is None:
        return _item(5, "Peticiones del PC", name, "aviso", "el PC todavía no ha hecho ningún trabajo por GitHub Actions (sin ciclo_actions.log)")
    m = re.search(r"Start time: (\d{14})", f.read_text(encoding="utf-8-sig", errors="replace"))
    if not m:
        return _item(5, "Peticiones del PC", name, "aviso", "ciclo_actions.log sin hora de inicio")
    start = datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
    req = request_time if request_time is not None else _request_time()
    if req is None:
        return _item(5, "Peticiones del PC", name, "aviso", f"último trabajo {start:%d-%m %H:%M}; no se pudo leer la hora de la petición (git)")
    wait = (start - req).total_seconds() / 60
    if wait < -1:
        # 08-11: the scheduled cycle may take it first when the PC frees up (the Actions job waits on the same busy PC):
        # what counts is that it started at once once the PC was free, whoever started it
        cyc = _find(out_root, "ciclo_automatico.log")
        starts = []
        if cyc is not None:
            for ts in re.findall(r"==> \[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] Peticion",
                                 cyc.read_text(encoding="utf-8-sig", errors="replace")):
                t = datetime.fromisoformat(ts.replace(" ", "T"))
                if t >= req - timedelta(minutes=1):
                    starts.append(t)
        if starts:
            first = min(starts)
            prev = _previous_job_end(cyc.parent, first)
            busy = (prev - req).total_seconds() / 60 if prev is not None and prev > req else 0.0
            idle = (first - req).total_seconds() / 60 - busy
            return _item(5, "Peticiones del PC", name, "ok" if idle <= ACTIONS_WAIT_MIN else "aviso",
                         f"petición del {req:%d-%m %H:%M}, la empezó el ciclo programado a las {first:%H:%M}"
                         + (f"; el PC estaba con otro trabajo hasta las {prev:%H:%M} ({busy:.1f} min, no cuentan)"
                            if busy > 0 else "; el PC estaba libre")
                         + f", {max(idle, 0):.1f} min después de quedar libre (objetivo ≤ {ACTIONS_WAIT_MIN:.0f} min)")
        return _item(5, "Peticiones del PC", name, "aviso",
                     f"la última petición ({req:%d-%m %H:%M}) no empezó por GitHub Actions; el último trabajo por Actions fue el {start:%d-%m %H:%M}")
    # the time the PC was busy with another job after the request does not count (the job waits for it to end)
    prev = _previous_job_end(f.parent, start)
    busy = (prev - req).total_seconds() / 60 if prev is not None and prev > req else 0.0
    idle_wait = wait - busy
    busy_txt = (f"; el PC estaba con otro trabajo hasta las {prev:%H:%M} ({busy:.1f} min, no cuentan), "
                f"empezó {max(idle_wait, 0):.1f} min después de quedar libre" if busy > 0 else "; el PC estaba libre")
    return _item(5, "Peticiones del PC", name, "ok" if idle_wait <= ACTIONS_WAIT_MIN else "aviso",
                 f"petición del {req:%d-%m %H:%M}, empezó a los {max(wait, 0):.1f} min{busy_txt} (objetivo ≤ {ACTIONS_WAIT_MIN:.0f} min "
                 "desde la petición o desde que acaba el trabajo anterior)")


# request #30 (07-11): the state-of-the-art document (docs/comparativa_apps.md) checked against the measured state:
# the models it names, its stroke-detection figures and its date
COMPARISON_DOC = ROOT / "docs" / "comparativa_apps.md"
COMPARISON_ITEM = "Comparativa con otras apps al día (docs/comparativa_apps.md)"
COMPARISON_TOL = 0.03          # its precision / recall may differ this much from the latest F3Set recall
COMPARISON_MAX_DAYS = 14       # its date may be this many days older than the latest model measure
# model named in the document (regular expression) → (audit item that backs it, bench_candidates.json result that
# backs it); one «ok» item or one measured result (verdict, no error) is enough
COMPARISON_MODELS = {
    r"\bTrackNetV3\b": (r"^Modelo en uso: bola", "wasb"),
    r"\bRTMPose\b": (r"^Modelo en uso: (esqueleto híbrido|raqueta)", "rtmw"),
    r"\bYOLO11\b": (r"^Modelo en uso: esqueleto híbrido", "rfdetr"),
    r"\bTennisCourtDetector\b": (r"^Modelo en uso: pista de 14 puntos", "court14"),
    r"\bMotionAGFormer\b": (r"^Modelo en uso: giro 3D", "mag3d"),
    r"\bRTMW3D\b": (None, "mag3d"),
    r"\bTransNetV2\b": (r"^Modelo en uso: cortes de plano", None),
    r"\bF3ED\b": (r"^Modelo candidato medido: f3ed", "f3ed"),
    r"detector de golpes (aprendido|entrenado)": (r"^Modelo en uso: detector de golpes", "f3ed"),
    r"\bWASB\b": (r"^Modelo candidato medido: wasb", "wasb"),
    r"\bRTMW-x\b": (r"^Modelo candidato medido: rtmw", "rtmw"),
    r"\bRF-DETR\b": (r"^Modelo candidato medido: rfdetr", "rfdetr"),
    r"\bPP-OCRv5\b": (r"^Modelo candidato medido: ocr5", "ocr5"),
    r"\bCatBoost\b": (r"^Modelo candidato medido: bounce", "bounce"),
    r"modelo propio de bote": (None, "bounce_own"),
}
_MONTHS = {m: i + 1 for i, m in enumerate(("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                                           "septiembre", "octubre", "noviembre", "diciembre"))}


def _doc_date(text: str):
    """The date of the line «Estado: …» (07-11-2026, 2026-11-07, 7 de noviembre de 2026 or «octubre 2026», read as
    the first day of that month), or None."""
    from datetime import date
    m = re.search(r"^Estado:\s*([^.\n]+)", text, re.M)
    if not m:
        return None
    s = m.group(1).strip().lower()
    try:
        if d := re.match(r"(\d{1,2})-(\d{1,2})-(\d{4})", s):
            return date(int(d.group(3)), int(d.group(2)), int(d.group(1)))
        if d := re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", s):
            return date(int(d.group(1)), int(d.group(2)), int(d.group(3)))
        if d := re.match(r"(?:(\d{1,2}) de )?([a-záéíóú]+)(?: de)? (\d{4})", s):
            return date(int(d.group(3)), _MONTHS[d.group(2)], int(d.group(1) or 1))
    except (KeyError, ValueError):
        return None
    return None


def _latest_recall(out_root: Path):
    """(file name, precision, recall, found, annotated) of the latest F3Set recall (scripts/validate_recall.py, the
    learned detector's first), without the matches it excluded as misaligned; None when there is none."""
    for name in ("recall_validation_detector.json", "recall_validation.json"):
        f = _find(out_root, name, f"datasets/reports/{name}")
        if f is None:
            continue
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        s = r.get("summary_valid") or r.get("summary") or {}
        tot = s.get("total") or {}
        p = (s.get("precision") or {}).get("precision")
        if tot.get("recall") is not None and p is not None:
            return name, float(p), float(tot["recall"]), tot.get("found"), tot.get("gt")
    return None


def comparison_doc_item(items: list[dict], out_root: Path, doc: Path | None = None) -> dict:
    """#30: docs/comparativa_apps.md agrees with the measured state. «ok» only when (a) every model it names is in
    use or was measured on the PC (audit items «Modelo en uso» / «Modelo candidato medido», bench_candidates.json),
    (b) its stroke-detection figures (the first «P x / R y» of its row «Detección automática de golpes») are within
    COMPARISON_TOL of the latest F3Set recall, and (c) its date («Estado: …») is at most COMPARISON_MAX_DAYS older
    than the latest model measure (bench_candidates.json «generated»). Otherwise «aviso» with what is stale."""
    from datetime import datetime
    doc = COMPARISON_DOC if doc is None else Path(doc)
    if not doc.exists():
        return _item(12, "Modelos", COMPARISON_ITEM, "aviso", f"no se encontró {doc.name}")
    text = doc.read_text(encoding="utf-8")
    bf = _find(out_root, "bench_candidates.json", "datasets/reports/bench_candidates.json")
    try:
        bench = json.loads(bf.read_text(encoding="utf-8")) if bf else {}
    except (OSError, ValueError):
        bench = {}
    res = bench.get("results") or {}
    stale, good = [], []
    # (a) the models it names
    named, unbacked = [], []
    for pat, (item_rx, key) in COMPARISON_MODELS.items():
        if not re.search(pat, text):
            continue
        label = re.sub(r"\((\w+)\|\w+\)", r"\1", pat.replace(r"\b", ""))     # «detector de golpes aprendido»
        named.append(label)
        by_item = item_rx is not None and any(re.search(item_rx, i.get("name", "")) and i.get("status") == "ok" for i in items)
        r = res.get(key) if key else None
        by_bench = bool(r) and not r.get("error") and bool(r.get("verdict")) and not (r.get("verdict") or {}).get("insufficient")
        if not (by_item or by_bench):
            unbacked.append(label)
    if unbacked:
        stale.append(f"modelos que nombra sin estar en uso ni medidos en el PC: {', '.join(unbacked)}")
    elif named:
        good.append(f"{len(named)} modelos que nombra, todos en uso o medidos en el PC")
    # (b) its detection figures against the latest F3Set recall
    rec = _latest_recall(out_root)
    row = next((ln for ln in text.splitlines() if "Detección automática de golpes" in ln), "")
    m = re.search(r"P\s*(\d+[,.]\d+)\s*/\s*R\s*(\d+[,.]\d+)", row)
    if rec is None:
        stale.append("sin recuento de F3Set con el que comparar sus cifras (recall_validation_detector.json)")
    elif not m:
        stale.append("su fila «Detección automática de golpes» no da precisión y recall («P x / R y»)")
    else:
        dp, dr = (float(x.replace(",", ".")) for x in m.groups())
        fname, p, r_, found, gt = rec
        cmp = f"P {dp:.2f} / R {dr:.2f} en el documento frente a P {p:.2f} / R {r_:.2f} de {fname} ({found} de {gt})"
        (stale if abs(dp - p) > COMPARISON_TOL or abs(dr - r_) > COMPARISON_TOL else good).append(
            ("cifras de detección desfasadas: " if abs(dp - p) > COMPARISON_TOL or abs(dr - r_) > COMPARISON_TOL
             else "cifras de detección al día: ") + cmp)
    # (c) its date against the latest model measure
    dd = _doc_date(text)
    gen = str(bench.get("generated") or "")
    try:
        last = datetime.fromisoformat(gen.replace(" ", "T")).date() if gen else None
    except ValueError:
        last = None
    if dd is None:
        stale.append("sin fecha legible en su línea «Estado:»")
    elif last is None:
        stale.append(f"fecha {dd:%d-%m-%Y}; sin fecha de la última medida de modelos (bench_candidates.json)")
    elif (last - dd).days > COMPARISON_MAX_DAYS:
        stale.append(f"fecha {dd:%d-%m-%Y}, {(last - dd).days} días anterior a la última medida de modelos "
                     f"({last:%d-%m-%Y}; máximo {COMPARISON_MAX_DAYS})")
    else:
        good.append(f"fecha {dd:%d-%m-%Y} frente a la última medida de modelos {last:%d-%m-%Y}")
    return _item(12, "Modelos", COMPARISON_ITEM, "aviso" if stale else "ok",
                 ("DESFASADO: " + "; ".join(stale) + ("; bien: " + "; ".join(good) if good else "")) if stale
                 else "; ".join(good))


SCRATCH_TIME_ITEM = "Tiempo desde cero"
SCRATCH_MAX_DAYS = 14          # a run from scratch older than this was made with other code


def scratch_time_item(tables: list[dict], today: str | None = None) -> dict:
    """B1's main test (11-11, R2 of the review of the Base): the slowest run from scratch of the last SCRATCH_MAX_DAYS
    (all its heavy stages computed, stage_times.not_real; at least 20 min of video), as hours for a 3.5 h match;
    ≤ 8 h (SPEED_TARGET)."""
    import datetime as _dt
    from .stage_times import latest_from_scratch
    day0 = (today or _dt.date.today().isoformat())[:10]
    since = (_dt.date.fromisoformat(day0) - _dt.timedelta(days=SCRATCH_MAX_DAYS)).isoformat()
    t = latest_from_scratch(tables, since=since)       # the slowest of the last 14 days: it must hold for every video
    if t is None:
        return _item(9, "Rendimiento", SCRATCH_TIME_ITEM, "pocos datos",
                     "ninguna ejecución desde cero de 20 min de vídeo o más (prueba app_nuevo o poc del PC)")
    per = t["total_min"] / t["minutos_video"]
    top = ", ".join(f"{r['etapa']} {r['s'] / 60:.0f} min" for r in t["etapas"][:4])
    day = (today or _dt.date.today().isoformat())[:10]
    age = (_dt.date.fromisoformat(day) - _dt.date.fromisoformat(t["fecha"][:10])).days
    st = "ok" if per <= SPEED_TARGET and age <= SCRATCH_MAX_DAYS else "aviso"
    return _item(9, "Rendimiento", SCRATCH_TIME_ITEM, st,
                 f"{t['total_min']:.0f} min para {t['minutos_video']:.0f} min de vídeo ({per:.2f} veces) ≈ {per * 3.5:.1f} h "
                 f"para un partido de 3,5 h (objetivo ≤ {SPEED_TARGET * 3.5:.1f} h); {Path(t['carpeta']).name}, {t['fecha']}"
                 + (f" (hace {age} días: más de {SCRATCH_MAX_DAYS}, repetirla)" if age > SCRATCH_MAX_DAYS else "")
                 + f"; las que más tardan: {top}")


def base_items(match_dirs: list[Path], out_root: Path, cfg: dict | None = None) -> list[dict]:
    """Every check of the Base packages B1 and B3 that is not in audit() itself (cli.run_audit)."""
    items = []
    for fn in (lambda: candidate_items(out_root), lambda: models_in_use_items(cfg), lambda: spotter_items(match_dirs),
               lambda: stage_time_items(match_dirs, out_root), lambda: parallel_items(match_dirs),
               lambda: [_scratch_time(out_root, cfg)],
               lambda: resources_items(out_root), lambda: [actions_item(out_root)],
               lambda: [f3set_precision_item(out_root)], lambda: f3set_detector_items(out_root),
               lambda: f3set_sides_items(out_root),          # B4 (08-11): identity and far end against F3Set
               # #30: after the model items, which it reads
               lambda: [comparison_doc_item(items, out_root)]):
        try:
            items += fn()
        except Exception as e:  # noqa: BLE001 — one check that breaks never stops the audit
            items.append(_item(9, "Auditoría", "Comprobaciones de la base (B1, B3)", "aviso", f"no se pudo calcular ({e})"))
    return items

def _scratch_time(out_root: Path, cfg: dict | None) -> dict:
    from .config import load_config
    from .stage_times import all_tables, roots_of
    c = dict(cfg or load_config())
    c["paths"] = {**(c.get("paths") or {}), "output": str(out_root)}
    return scratch_time_item(all_tables(roots_of(c)))


# --- the PC's infrastructure, read from the files it leaves (package B7, 04-11) ----------------------------------------
_DATE = r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?"
LOG_RUNNING_S = 3 * 3600          # a request log without its end, written less than this ago: still running
OLD_TEST_DAYS = 14                # a test folder (_poc*) untouched for longer is an old one (request #146)


def progress_item(bases: list[Path]) -> dict:
    """#50: the progress of the running stage is visible: <output>/progreso.json with match, stage, % and time
    (pipeline.Context.progress writes it; the PC uploads it and the application shows it)."""
    name = "Progreso visible (progreso.json)"
    f = next((b / "progreso.json" for b in bases if (b / "progreso.json").exists()), None)
    if f is None:
        return _item(5, "Infraestructura", name, "aviso", "no se encontró progreso.json (ninguna etapa ha dicho su avance aquí)")
    try:
        p = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return _item(5, "Infraestructura", name, "falta", f"progreso.json ilegible ({e})")
    need = ("partido", "etapa", "hecho", "total", "porcentaje", "hora")
    miss = [k for k in need if p.get(k) is None]
    if miss or not re.match(_DATE, str(p.get("hora", ""))):
        return _item(5, "Infraestructura", name, "falta", f"progreso.json sin {', '.join(miss) or 'hora válida'}")
    return _item(5, "Infraestructura", name, "ok",
                 f"último: {p['etapa']} de {p['partido']} al {p['porcentaje']} % ({p['hecho']}/{p['total']}), "
                 f"{p.get('segundos', '?')} s, quedan ≈ {p.get('quedan_s', '?')} s, a las {p['hora']}")


def log_dates(text: str, age_s: float) -> str:
    """'' when a log of the PC says when it started and when it ended (or how long it took); else what is missing.
    Formats: the double-click scripts' transcripts (steps «==> [fecha]» and «Empezado … duracion total», comun.ps1),
    a request's log («Peticion N: … (fecha)» … «termina fecha»), the tests' log (inicio/fin) and event logs
    (each line with its date). A request log written less than LOG_RUNNING_S ago may still be running."""
    lines = [ln.strip().lstrip("﻿") for ln in text.splitlines() if ln.strip().lstrip("﻿")]
    if not lines:
        return "vacío"
    if "Windows PowerShell transcript start" in text[:400]:
        if "End time:" not in text[-400:] and age_s < LOG_RUNNING_S:
            return ""          # 11-11 (R6): a transcript still being written (PowerShell writes its steps late)
        if not re.search(r"==> \[" + _DATE + r"\]|Empezado " + _DATE, text):
            return "sin la fecha de sus pasos"
        if "End time:" in text[-400:] and "duracion total" not in text:
            return "terminó sin «Empezado … duracion total»"
        return ""
    if lines[0].startswith("Peticion "):
        if not re.search(r"\(" + _DATE, lines[0]):
            return "sin la fecha de inicio"
        if re.search(r"termina " + _DATE + r"|duracion total", "\n".join(lines[-5:])):
            return ""
        return "" if age_s < LOG_RUNNING_S else "sin «termina fecha» al final"
    if lines[0].startswith("commit:"):
        head = "\n".join(lines[:5])
        return "" if re.search(r"inicio: " + _DATE, head) and re.search(r"fin: " + _DATE, head) else "sin inicio y fin"
    heads = [ln for ln in lines if re.match(r"== " + _DATE, ln)]
    if heads:          # the app's queue (app_cola.log): «== fecha cola» … the work's output … «== fecha fin (código N)»
        return "" if heads[-1].split(" ", 3)[-1].startswith("fin") or age_s < LOG_RUNNING_S else "sin «== fecha fin» al final"
    dated = sum(bool(re.match(_DATE, ln)) for ln in lines)
    if dated and dated >= 0.8 * len(lines):          # an event log: each line with its date (tracebacks in between)
        return ""
    return "sin fechas"


def logs_item(bases: list[Path], now: float | None = None) -> dict:
    """#66: every log the PC writes in <output> (double-click scripts, Claude's requests, tests, events) says when it
    started and when it ended or how long it took (scripts/windows/comun.ps1 and ciclo_automatico.ps1)."""
    import time
    name = "Registros con fecha y duración"
    now = time.time() if now is None else now
    folder = next((b for b in bases if b.exists() and any(b.glob("*.log"))), None)
    if folder is None:
        return _item(5, "Infraestructura", name, "aviso", "no se encontró ningún registro (.log) del PC")
    logs = sorted(folder.glob("*.log"))
    # 10-11: the audit of a full analysis runs inside it, while its request log (prueba_completo.log) is still open and
    # silent for hours: a request log counts as running while the work's progress (progreso.json) is fresh
    pj = folder / "progreso.json"
    live = pj.exists() and now - pj.stat().st_mtime < 600
    bad = []
    for f in logs:
        try:
            age = now - f.stat().st_mtime
            why = log_dates(f.read_text(encoding="utf-8-sig", errors="replace"), 0.0 if live else age)
        except OSError as e:
            why = f"ilegible ({e})"
        if why:
            bad.append(f"{f.name}: {why}")
    return _item(5, "Infraestructura", name, "falta" if bad else "ok",
                 f"{len(logs) - len(bad)} de {len(logs)} registros con fecha de inicio y de fin o duración"
                 + (f"; sin ellas: {'; '.join(bad[:6])}" if bad else ""))


def _sizes(f: Path) -> tuple[str, dict[str, float]]:
    """tamanos.txt (comun.ps1, Subir-Registros): its date and MB of each output folder by its path."""
    date, mb = "", {}
    for ln in f.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if ln.startswith("fecha:"):
            date = ln.split(":", 1)[1].strip()
        m = re.match(r"\s*([\d.,]+)\s*MB\s+(\S.*)$", ln)
        if m:
            mb[m.group(2).strip()] = float(m.group(1).replace(",", "."))
    return date, mb


def sizes_item(bases: list[Path]) -> dict:
    """#81: the size of each output folder, written by the PC itself every cycle (registros/tamanos.txt, uploaded with
    the logs): the disk is watched without spending anyone's time or tokens."""
    name = "Tamaño de la salida (tamanos.txt)"
    f = next((b / "registros" / "tamanos.txt" for b in bases if (b / "registros" / "tamanos.txt").exists()), None)
    if f is None:
        return _item(5, "Infraestructura", name, "aviso", "no se encontró registros/tamanos.txt")
    date, mb = _sizes(f)
    if not date or not mb:
        return _item(5, "Infraestructura", name, "falta", "tamanos.txt sin fecha o sin carpetas")
    top = sorted(((v, k) for k, v in mb.items() if k.count("\\") <= 2), reverse=True)[:3]
    tot = sum(v for k, v in mb.items() if k.count("\\") <= 2)
    return _item(5, "Infraestructura", name, "ok", f"{len(mb)} carpetas, {tot / 1024:.1f} GB en total ({date}); las mayores: "
                 + ", ".join(f"{k.rsplit(chr(92), 1)[-1]} {v / 1024:.1f} GB" for v, k in top))


def old_test_folders_item(bases: list[Path], now: float | None = None, days: float = OLD_TEST_DAYS) -> dict:
    """#146 «borra las carpetas de pruebas antiguas»: test folders of the cycle (<output>/_poc*) untouched for more than
    `days` days, with their size (tamanos.txt) — they only fill the disk. Nothing is deleted here (only the user's
    request to the PC deletes them, ciclo_automatico.ps1 «borrar»)."""
    import time
    name = "Carpetas de pruebas antiguas"
    now = time.time() if now is None else now
    out = next((b for b in bases if b.exists() and any(b.glob("_poc*"))), None)
    if out is None:
        return _item(5, "Infraestructura", name, "ok", "ninguna carpeta de pruebas (_poc*) en la salida")
    sizes = {}
    tf = next((b / "registros" / "tamanos.txt" for b in bases if (b / "registros" / "tamanos.txt").exists()), None)
    if tf is not None:
        sizes = {k.rsplit("\\", 1)[-1]: v for k, v in _sizes(tf)[1].items()}
    old = []
    for d in sorted(p for p in out.glob("_poc*") if p.is_dir()):
        try:
            last = max([d.stat().st_mtime] + [c.stat().st_mtime for c in d.iterdir()])
        except OSError:
            continue
        if now - last > days * 86400:
            old.append((d.name, sizes.get(d.name)))
    if not old:
        return _item(5, "Infraestructura", name, "ok", f"ninguna carpeta de pruebas con más de {days:.0f} días sin usar")
    gb = sum(v for _, v in old if v) / 1024
    return _item(5, "Infraestructura", name, "aviso",
                 f"{len(old)} carpeta(s) de pruebas sin usar en más de {days:.0f} días"
                 + (f" ({gb:.1f} GB)" if gb else "") + ": " + ", ".join(n for n, _ in old[:8])
                 + ". Se borran con la petición «borrar» del PC")


def app_items(bases: list[Path]) -> list[dict]:
    """#160, #242: the application on the PC, from its own check (tennisbio app comprobar → capturas_app/ventana.json):
    the real window loads and every screen is painted without problems; its index holds the analyses."""
    f = next((b / "capturas_app" / "ventana.json" for b in bases if (b / "capturas_app" / "ventana.json").exists()), None)
    names = ("Aplicación: ventana real y pantallas", "Aplicación: análisis en su índice")
    if f is None:
        out = [_item(5, "Aplicación", n, "aviso", "todavía sin la comprobación de la aplicación (capturas_app/ventana.json)")
               for n in names]
        live_idx = app_index_counts(bases)
        if live_idx is not None:
            out[1] = _item(5, "Aplicación", names[1], "ok" if live_idx[0] else "aviso",
                           f"{live_idx[0]} análisis y {live_idx[1]} partidos en el índice de la aplicación "
                           "(leído del índice, datos/tennisbio.db)"
                           + ("" if live_idx[0] else ": los análisis de los partidos hechos por el ciclo automático "
                              "aún no están en ella"))
        return out
    try:
        v = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [_item(5, "Aplicación", n, "falta", f"ventana.json ilegible ({e})") for n in names]
    live, idx, probs = v.get("live") or {}, v.get("index") or {}, v.get("problems") or []
    ok_win = not probs and (v.get("screens") or 0) > 0 and live.get("ready") is True
    out = [_item(5, "Aplicación", names[0], "ok" if ok_win else "falta",
                 f"{v.get('screens', 0)} pantallas pintadas, {len(probs)} problemas; ventana real: "
                 + ("carga" if live.get("ready") else f"no carga ({live.get('error') or live.get('step') or 'sin dato'})")
                 + (f"; {'; '.join(str(p) for p in probs[:3])}" if probs else ""))]
    n_an, n_m = idx.get("analyses") or 0, idx.get("matches") or 0
    live_idx = app_index_counts(bases)
    if live_idx is not None:            # the index itself (07-11: ventana.json was from 04-11, before request 114)
        n_an, n_m = live_idx
    out.append(_item(5, "Aplicación", names[1], "ok" if n_an else "aviso",
                     f"{n_an} análisis y {n_m} partidos en el índice de la aplicación"
                     + (" (leído del índice, datos/tennisbio.db)" if live_idx is not None else "")
                     + ("" if n_an else ": los análisis de los partidos hechos por el ciclo automático aún no están en ella")))
    return out


def app_index_counts(bases: list[Path]) -> tuple[int, int] | None:
    """(analyses, matches) in the application's index as it is now (<base>/datos/tennisbio.db, read only), or None
    without it. The window's check (ventana.json) is a snapshot of the day it ran: the index changes after it
    (request 114 filled it on 07-11; the audit kept reading the 0 of 04-11)."""
    import sqlite3
    for b in bases:
        f = b / "datos" / "tennisbio.db"
        if not f.is_file():
            continue
        try:
            con = sqlite3.connect(f"{f.resolve().as_uri()}?mode=ro", uri=True, timeout=10)
            try:
                return (con.execute("SELECT count(*) FROM analyses").fetchone()[0],
                        con.execute("SELECT count(*) FROM matches").fetchone()[0])
            finally:
                con.close()
        except sqlite3.Error:
            continue
    return None


APP_COST_ITEM = "Aplicación: lo que consume abierta"
APP_CPU_MAX = 5.0             # % of the whole PC, mean over a minute with the window open (and nothing to do)
APP_RAM_MAX = 800             # MB, the process and its WebView2 children together
APP_COST_DAYS = 14


def app_cost_item(bases: list[Path], today: str | None = None) -> dict:
    """#225 (11-11, R8 of the review of the Base: «no se cuelga ni ralentiza el PC», never measured): what the open window
    costs, from scripts/app_recursos.py (capturas_diag/app_recursos.json, a PC request «medir»)."""
    import datetime as _dt
    f = next((b / "capturas_diag" / "app_recursos.json" for b in bases if (b / "capturas_diag" / "app_recursos.json").exists()), None)
    if f is None:
        return _item(5, "Aplicación", APP_COST_ITEM, "aviso", "sin medir (petición «medir app_recursos» del PC)")
    try:
        r = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return _item(5, "Aplicación", APP_COST_ITEM, "aviso", f"app_recursos.json ilegible ({e})")
    if r.get("error") or r.get("cpu_media_pct") is None:
        return _item(5, "Aplicación", APP_COST_ITEM, "falta", f"no se pudo medir: {r.get('error') or 'sin muestras'}")
    day = (today or _dt.date.today().isoformat())[:10]
    age = (_dt.date.fromisoformat(day) - _dt.date.fromisoformat(str(r.get("fecha", day))[:10])).days
    ok = r["cpu_media_pct"] <= APP_CPU_MAX and (r.get("ram_max_mb") or 0) <= APP_RAM_MAX
    st = "falta" if not ok else "aviso" if age > APP_COST_DAYS else "ok"
    return _item(5, "Aplicación", APP_COST_ITEM, st,
                 f"CPU media {r['cpu_media_pct']} % (máx {r.get('cpu_max_pct')} %; objetivo ≤ {APP_CPU_MAX:g} %), memoria hasta "
                 f"{r.get('ram_max_mb')} MB (objetivo ≤ {APP_RAM_MAX}) en {r.get('procesos')} procesos; {r.get('fecha')}"
                 + (f" (hace {age} días: repetirla)" if age > APP_COST_DAYS else ""))


MATCH_LIST_ITEM = "Lista de partidos: rival, torneo, ronda y fecha"
MATCH_LIST_FIELDS = (("opponent", "rival"), ("tournament", "torneo"), ("round", "ronda"), ("date", "fecha"))


def match_list_item(bases: list[Path]) -> dict:
    """#226 (11-11, R6 of the review of the Base: its test passed with invented rows): every match of the real registry
    (<base>/datos/tennisbio.db, read only; not the test runs nor the archived ones) has its rival, tournament, round and
    date. On 11-11 the 6 had no rival and their library folders were all «sin-fecha»."""
    import sqlite3
    f = next((b / "datos" / "tennisbio.db" for b in bases if (b / "datos" / "tennisbio.db").is_file()), None)
    if f is None:
        return _item(5, "Aplicación", MATCH_LIST_ITEM, "aviso", "sin el registro de partidos (datos/tennisbio.db)")
    try:
        con = sqlite3.connect(f"{f.resolve().as_uri()}?mode=ro", uri=True, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            rows = [dict(r) for r in con.execute("SELECT * FROM matches")]
        finally:
            con.close()
    except sqlite3.Error as e:
        return _item(5, "Aplicación", MATCH_LIST_ITEM, "aviso", f"no se pudo leer el registro ({e})")
    rows = [r for r in rows if ":" not in str(r.get("id")) and r.get("state") != "archivado"]
    if not rows:
        return _item(5, "Aplicación", MATCH_LIST_ITEM, "aviso", "ningún partido en el registro")
    gaps = {es: [r["id"] for r in rows if not str(r.get(k) or "").strip()] for k, es in MATCH_LIST_FIELDS}
    bad = {es: ids for es, ids in gaps.items() if ids}
    return _item(5, "Aplicación", MATCH_LIST_ITEM, "falta" if bad else "ok",
                 f"{len(rows)} partidos; " + ("; ".join(f"sin {es}: {len(ids)} ({', '.join(ids[:2])}{'…' if len(ids) > 2 else ''})"
                                                       for es, ids in bad.items()) if bad else "todos con sus cuatro datos"))


NEW_MATCH_ITEM = "Aplicación: un partido nuevo de principio a fin"
# a run before this day was made with older code (candidates v14, app index step: 07-11) and does not count
NEW_MATCH_SINCE = "2026-11-11"     # 11-11: through the single worker (tennisbio worker), not the app's own runner


NEW_MATCH_OWN_AREAS = ("Ficheros", "Automático")       # files of every stage, failed strokes, errors of a stage


def new_match_own_failures(base: Path) -> list[str] | None:
    """The checks of the new match itself that fail in the application's own audit of its analysis (the test's folder:
    <output>/_app_nuevo/output/analisis/<id>/actual|pendiente/auditoria/auditoria.json): its files and errors, and the
    checks that name the match (identity, strokes found). None without that audit."""
    folder = Path(base) / "_app_nuevo" / "output" / "analisis"
    auds = sorted(folder.glob("*/*/auditoria/auditoria.json")) if folder.is_dir() else []
    if not auds:
        return None
    out = []
    for a in auds:
        try:
            items = json.loads(a.read_text(encoding="utf-8")).get("items", [])
        except (OSError, ValueError):
            out.append(f"{a.parents[1].name}: auditoría ilegible")
            continue
        out += [f"{i.get('name')}: {(i.get('detail') or '')[:120]}" for i in items if i.get("status") == "falta"
                and (i.get("area") in NEW_MATCH_OWN_AREAS or (i.get("area") == "Golpes" and "prueba-app" in str(i.get("name"))))]
    return out


def new_match_item(bases: list[Path]) -> dict:
    """B7's main test (07-11): a match the application has never seen, analysed from start to end by the application
    alone (PC request `app_nuevo` → prueba_app_nuevo.log): it ends, with its analysis updated and no error."""
    f = next((b / "prueba_app_nuevo.log" for b in bases if (b / "prueba_app_nuevo.log").exists()), None)
    if f is None:
        return _item(5, "Aplicación", NEW_MATCH_ITEM, "aviso", "sin ejecutar todavía (petición «app_nuevo» del PC)")
    txt = f.read_text(encoding="utf-8", errors="replace")
    end = re.search(r"termina (\d{4}-\d{2}-\d{2}T[\d:]+)", txt)
    # 11-11: a doubtful identity also fails (a run on another player's match passed before). The analysis is judged by
    # the checks of the match itself (R6): its «FALLOS» also counted requests outside the Base and the audit of the
    # whole PC (32 checks on request 207, only 4 of them about the match)
    bad = [l.strip() for l in txt.splitlines() if re.search(r"Traceback|ERROR|\[error\]|\[fallo\]|identidad dudosa", l)]
    own = new_match_own_failures(f.parent)
    if own is None:
        bad += [l.strip() for l in txt.splitlines() if "analizado FALLOS" in l]       # without its audit: the summary
    else:
        bad += own
    # the app's former runner printed «[ok]»; the single worker's queue says the match job «hecho» (jobs status)
    done = "[ok]" in txt or re.search(r"^\s*hecho\s+#\d+ partido", txt, re.M) is not None
    ok = end is not None and not bad and done
    if ok and end.group(1)[:10] < NEW_MATCH_SINCE:
        return _item(5, "Aplicación", NEW_MATCH_ITEM, "aviso",
                     f"la última ejecución (termina {end.group(1)}) es anterior al código actual ({NEW_MATCH_SINCE}): "
                     "hay que repetirla (petición «app_nuevo» del PC)")
    dur = re.search(r"duracion total: ([\d.]+) min", txt)
    return _item(5, "Aplicación", NEW_MATCH_ITEM, "ok" if ok else "falta",
                 (f"terminó {end.group(1)}" if end else "sin terminar")
                 + (f" en {dur.group(1)} min" if dur else "")
                 + ("; análisis actualizado" if done else "; sin análisis actualizado")
                 + (f"; errores: {'; '.join(bad[:3])}" if bad else ""))


ORCH_E2E_ITEM = "Orquestador: prueba de extremo a extremo"
ORCH_ALIVE_ITEM = "Orquestador: ejecutor vivo cuando hay trabajo"
ORCH_WAIT_ITEM = "Orquestador: espera hasta empezar cada trabajo"
ORCH_WAIT_MAX_S = 5 * 60       # a job starts within 5 min of being queued, or of the end of the job before it
ORCH_HEARTBEAT_S = 3 * 60      # the worker says it lives every HEARTBEAT_S (30 s): 3 min without it, it is not running
ORCH_DAYS = 7                  # the waits of the last week's jobs


def orchestrator_items(bases: list[Path], now_s: float | None = None) -> list[dict]:
    """B8's main test (11-11, R7 of the review of the Base; «Orquestador: …» had no check, so it was «sin medir»):
    - the end-to-end test on the PC (request e2e → prueba_e2e.log): sent as the chat, paused as the application,
      resumed as the chat, all its checks true;
    - the worker is alive whenever jobs are waiting (datos/tennisbio.db: its heartbeat);
    - every job of the last week started at most ORCH_WAIT_MAX_S after it was queued or after the job before it ended
      (on 11-11 two waited 5-11 min: the worker had ended for new code and nobody started the next one)."""
    import sqlite3
    import time as _time
    now_s = _time.time() if now_s is None else now_s
    out = []
    f = next((b / "prueba_e2e.log" for b in bases if (b / "prueba_e2e.log").exists()), None)
    if f is None:
        out.append(_item(5, "Orquestador", ORCH_E2E_ITEM, "aviso", "sin ejecutar (petición «e2e» del PC)"))
    else:
        txt = f.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"\{.*\}", txt, re.S)
        try:
            res = json.loads(m.group(0)) if m else {}
        except ValueError:
            res = {}
        checks = res.get("checks") or {}
        bad = [k for k, v in checks.items() if v is not True]
        end = re.search(r"termina (\S+)", txt)
        ok = res.get("ok") is True and checks and not bad
        out.append(_item(5, "Orquestador", ORCH_E2E_ITEM, "ok" if ok else "falta",
                         f"{len(checks) - len(bad)} de {len(checks)} comprobaciones bien"
                         + (f"; fallan: {', '.join(bad)}" if bad else "") + (f"; termina {end.group(1)}" if end else "")))
    db = next((b / "datos" / "tennisbio.db" for b in bases if (b / "datos" / "tennisbio.db").is_file()), None)
    if db is None:
        return out + [_item(5, "Orquestador", n, "aviso", "sin la base de la cola (datos/tennisbio.db)")
                      for n in (ORCH_ALIVE_ITEM, ORCH_WAIT_ITEM)]
    try:
        con = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            beat = con.execute("SELECT value FROM settings WHERE key='ejecutor'").fetchone()
            waiting = con.execute("SELECT count(*) FROM jobs WHERE state='pendiente'").fetchone()[0]
            paused = con.execute("SELECT value FROM settings WHERE key='pausa'").fetchone()
            rows = [dict(r) for r in con.execute(
                "SELECT id, created, started, finished FROM jobs WHERE started IS NOT NULL AND created IS NOT NULL "
                "ORDER BY started")]
        finally:
            con.close()
    except sqlite3.Error as e:
        return out + [_item(5, "Orquestador", n, "aviso", f"no se pudo leer la cola ({e})") for n in (ORCH_ALIVE_ITEM, ORCH_WAIT_ITEM)]
    try:
        hb = json.loads(beat[0]) if beat else {}
    except (TypeError, ValueError):
        hb = {}
    alive = bool(hb.get("pid")) and now_s - float(hb.get("at") or 0) <= ORCH_HEARTBEAT_S
    is_paused = bool(paused) and str(paused[0]).lower() in ("true", "1")
    st = "ok" if alive or not waiting or is_paused else "falta"
    out.append(_item(5, "Orquestador", ORCH_ALIVE_ITEM, st,
                     f"ejecutor {'vivo' if alive else 'parado'}; {waiting} trabajos esperando"
                     + ("; cola en pausa" if is_paused else "")))
    from datetime import datetime as _d

    def ts(x):
        try:
            return _d.strptime(str(x)[:19], "%Y-%m-%d %H:%M:%S").timestamp()
        except ValueError:
            return None
    # a job's wait: from its queuing to its start, minus the time another job was running (it waited its turn)
    spans = [(ts(r["started"]), ts(r["finished"]) or now_s) for r in rows if ts(r["started"]) is not None]
    waits = []
    for r in rows:
        c, s0 = ts(r["created"]), ts(r["started"])
        if c is None or s0 is None or now_s - s0 > ORCH_DAYS * 86400 or s0 <= c:
            continue
        busy = sum(max(0.0, min(b, s0) - max(a, c)) for a, b in spans if (a, b) != (s0, ts(r["finished"]) or now_s))
        waits.append((max(0.0, s0 - c - busy), r["id"]))
    if not waits:
        out.append(_item(5, "Orquestador", ORCH_WAIT_ITEM, "pocos datos", f"ningún trabajo en los últimos {ORCH_DAYS} días"))
    else:
        worst = max(waits)
        late = [w for w in waits if w[0] > ORCH_WAIT_MAX_S]
        out.append(_item(5, "Orquestador", ORCH_WAIT_ITEM, "ok" if not late else "aviso",
                         f"{len(waits)} trabajos en {ORCH_DAYS} días; la mayor espera {worst[0] / 60:.1f} min (trabajo {worst[1]}); "
                         f"{len(late)} esperaron más de {ORCH_WAIT_MAX_S // 60} min"))
    return out


def infrastructure_items(out_root: Path) -> list[dict]:
    """The B7 checks read from the PC's own files (progress, logs, sizes, old test folders, the application) and B8's
    (the single worker's queue)."""
    bases = [out_root, out_root.parent, out_root.parent.parent]
    return ([progress_item(bases), logs_item(bases), sizes_item(bases), old_test_folders_item(bases)] + app_items(bases)
            + [new_match_item(bases), match_list_item(bases), app_cost_item(bases)] + orchestrator_items(bases))


MANUAL_REVIEW_ITEM = "Nada pide revisión manual"


def manual_review_item(bases: list[Path]) -> dict:
    """#45 and B7's main test (11-11, R1 of the review of the Base; before, an item that was always ok): nothing waits
    for the user in the application's index (<base>/datos/tennisbio.db, read only): no job «por confirmar» (a long
    recomputation waiting for a click). The one click allowed (who she is in a match, 19-10) is not a job and does not
    count."""
    import sqlite3
    for b in bases:
        f = b / "datos" / "tennisbio.db"
        if not f.is_file():
            continue
        try:
            con = sqlite3.connect(f"{f.resolve().as_uri()}?mode=ro", uri=True, timeout=10)
            try:
                rows = con.execute("SELECT id, kind, match, reason FROM jobs WHERE state='por confirmar' ORDER BY id").fetchall()
            finally:
                con.close()
        except sqlite3.Error as e:
            return _item(5, "Automático", MANUAL_REVIEW_ITEM, "aviso", f"no se pudo leer el índice de la aplicación ({e})")
        if rows:
            ex = "; ".join(f"#{r[0]} {r[1]} {r[2] or ''} ({(r[3] or '')[:60]})" for r in rows[:3])
            return _item(5, "Automático", MANUAL_REVIEW_ITEM, "aviso",
                         f"{len(rows)} trabajos esperan a que el usuario los confirme: {ex}")
        return _item(5, "Automático", MANUAL_REVIEW_ITEM, "ok",
                     "ningún trabajo espera al usuario en la aplicación (el clic de quién es ella no cuenta)")
    return _item(5, "Automático", MANUAL_REVIEW_ITEM, "aviso", "sin el índice de la aplicación (datos/tennisbio.db)")


def side_checks(out_root: Path) -> list[dict]:
    """Outputs that live next to the match folders: the validation with annotated public clips and the
    coach videos Claude learned from; what the application waits for from the user."""
    base = [out_root, out_root.parent, out_root.parent.parent]
    items = [manual_review_item(base)]
    f3 = next((b / "datasets" / "reports" / "f3set_validation.json" for b in base
               if (b / "datasets" / "reports" / "f3set_validation.json").exists()), None)
    if f3 is None:
        items.append(_item(3, "Validación", "Validación con clips anotados (F3Set)", "aviso", "no se encontró f3set_validation.json"))
    else:
        f3d = json.loads(f3.read_text(encoding="utf-8"))
        sm = f3d.get("summary", {})
        # 08-11: validate_f3set measures the old clip path (run_clip), not the analysis's detector (validate_recall)
        old = ("camino antiguo (run_clip, no el detector del análisis; el del análisis: recall_validation) — "
               if f3d.get("path", "legacy") == "legacy" else "")
        items.append(_item(3, "Validación", "Validación con clips anotados (F3Set)", "ok" if sm.get("f1", 0) >= 0.6 else "falta",
                           f"{old}golpes: precisión {sm.get('precision')}, recall {sm.get('recall')}; derecha/revés {sm.get('fh_bh_accuracy')}; "
                           f"dirección {sm.get('direction_accuracy')}. Solo detección y clases: el valor de cada medida (codo, rodillas, "
                           "pasos…) aún no tiene clips anotados con los que compararse"))
    items.append(code_tests_item(next((b / "pruebas.log" for b in base if (b / "pruebas.log").exists()), None)))
    items += module_tests_items(next((b / "pruebas.xml" for b in base if (b / "pruebas.xml").exists()), None))
    inv = next((b / "investigacion" / "indice.json" for b in base if (b / "investigacion" / "indice.json").exists()), None)
    if inv is None:
        items.append(_item(6, "Aprendizaje", "Vídeos de análisis de entrenadores (solo para aprender)", "aviso", "no se han bajado"))
    else:
        v = json.loads(inv.read_text(encoding="utf-8"))
        n = sum(1 for x in v if x.get("subtitles"))
        items.append(_item(6, "Aprendizaje", "Vídeos de análisis de entrenadores (solo para aprender)", "ok" if n else "aviso",
                           f"{len(v)} vídeos, {n} con texto (docs/aprendido_entrenadores.md); nunca en el informe"))
    try:
        items += infrastructure_items(out_root)
    except Exception as e:  # noqa: BLE001 — the audit must still be written
        items.append(_item(5, "Infraestructura", "Comprobaciones de la infraestructura del PC", "aviso", f"no se pudieron hacer ({e})"))
    return items


OPTIONAL_STAGES = {"fine_opponent"}     # its own job in the application: required only once it ran


def file_tree_items(match_dirs: list[Path], report_dir: Path | None, out_root: Path) -> list[dict]:
    """Every file a run must leave, checked to exist and not be empty: each stage's outputs per match,
    a video window and a frame-by-frame series per stroke, the report with its series and thumbnails,
    the export (PDF and clips) and the practice section (one clip per stroke)."""
    from . import stages  # noqa: F401  (registers the stages)
    from .pipeline import STAGES

    items = []
    ok = lambda f: f.exists() and f.stat().st_size > 0
    for d in match_dirs:
        # each file where the stages write it (match_files.at): in a library folder the cheap pass is in etapas/
        # and the rest in golpes/<jugadora>/ (04-11: read beside the folder, every library match lacked them all)
        # 11-11 (R6): the opponent's strokes are a job of their own in the application (app/engine.MAIN_STAGES); a match
        # the application analysed has not run that stage, and that is not a missing file (the app's new match failed so)
        try:
            ran = set(json.loads(_mf.at(d, "manifest.json").read_text(encoding="utf-8")))
        except (OSError, ValueError):
            ran = set()
        miss = [f"{n}/{o}" for n, st in STAGES.items() for o in st.outputs
                if not ok(_mf.at(d, o)) and not (n in OPTIONAL_STAGES and n not in ran)]
        st_file = _mf.at(d, "strokes.json")
        strokes = json.loads(st_file.read_text(encoding="utf-8")) if ok(st_file) else []
        win = [x for x in strokes if x.get("window") and not ok(_mf.at(d, "windows") / x["window"])]
        ser = [x for x in strokes if x.get("series") and not ok(_mf.at(d, x["series"]))]
        bad = miss + [f"ventana de {x.get('stroke_id', '?')}" for x in win[:3]] + [f"serie de {x.get('stroke_id', '?')}" for x in ser[:3]]
        items.append(_item(5, "Ficheros", f"Partido {d.name}: salida de cada etapa, ventanas y series",
                           "falta" if bad else "ok",
                           f"{sum(len(st.outputs) for st in STAGES.values())} ficheros de etapa, {len(strokes)} golpes con ventana y serie"
                           + (f"; faltan o están vacíos: {', '.join(bad[:8])}" if bad else "")))
    if report_dir is not None:
        data = report_data(report_dir / "index.html") or {}
        rs = data.get("strokes", [])
        js = [r for r in rs if r.get("series") and not ok(report_dir / r["series"])]
        th = [r for r in rs if r.get("thumb") and not ok(report_dir / r["thumb"])]
        items.append(_item(5, "Ficheros", "Informe: index.html, series y miniaturas", "falta" if not rs or js or th else "ok",
                           f"{len(rs)} golpes; series que faltan {len(js)}, miniaturas que faltan {len(th)}"))
        exp = next((p for p in (report_dir.parent / "exportar", report_dir.parent / "exportar_derecha") if p.exists()), None)
        if exp is not None:
            clips = list((exp / "golpes").glob("*.mp4")) if (exp / "golpes").exists() else []
            empty = [c.name for c in clips if not ok(c)]
            items.append(_item(5, "Ficheros", "Exportación: resumen PDF y un vídeo por golpe",
                               "falta" if empty or not ok(exp / "resumen.pdf") else "ok",
                               f"{len(clips)} vídeos" + (f"; vacíos: {', '.join(empty[:4])}" if empty else "")
                               + ("" if ok(exp / "resumen.pdf") else "; falta resumen.pdf")))
        items += export_end_items(report_dir.parent)
        items += [it for d in export_dirs(report_dir.parent) if (it := export_videos_item(d)) is not None]   # R5
    pr = next((b / "entrenamiento" for b in (out_root, out_root.parent) if (b / "entrenamiento" / "entrenamiento.json").exists()), None)
    if pr is not None:
        st = json.loads((pr / "entrenamiento.json").read_text(encoding="utf-8")).get("strokes", [])
        miss = [x["id"] for x in st if not x.get("clip") or not ok(pr / "clips" / x["clip"])]
        items.append(_item(5, "Ficheros", "Vista lateral: entrenamiento.json y un vídeo con esqueleto por golpe",
                           "falta" if miss else "ok", f"{len(st) - len(miss)} de {len(st)} vídeos"
                           + (f"; faltan: {', '.join(miss[:4])}" if miss else "")))
    return items


EXPORT_SAMPLE = 8               # 11-11 (R5): videos looked at per export folder, spread over the list
EXPORT_DUR_S = (2.0, 60.0)      # real speed → slow motion → freeze: seconds of a stroke video
EXPORT_SKEL_PX = 40             # pixels of each side's skeleton colour in a frame of the real-speed part
EXPORT_SKEL_SHARE = 0.75        # the share of the sampled videos that must show it


def _skeleton_pixels(video: Path, t: float = 0.5) -> tuple[int, int] | None:
    """Pixels of the export's left and right skeleton colours (export.SKC, BGR) in the frame at t, or None."""
    import cv2

    from .export import SKC
    try:
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-f", "image2pipe",
                            "-vcodec", "png", "-"], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    img = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR) if r.stdout else None
    if img is None:
        return None
    near = lambda c: int((np.abs(img.astype(np.int16) - np.array(c, np.int16)).max(axis=2) <= 30).sum())
    return near(SKC["l"]), near(SKC["r"])


def export_videos_item(d: Path) -> dict | None:
    """#41 (11-11, R5 of the review of the Base: its test was «the PDF exists»): in each export folder, a sample of the
    stroke videos (golpes/*.mp4) plays in a browser (codec), lasts what a stroke video lasts (real speed, slow motion,
    freeze) and carries the skeleton (its colours in a frame of the real-speed part)."""
    vids = sorted((Path(d) / "golpes").glob("*.mp4"))
    if not vids:
        return None
    name = f"Vídeos exportados: {Path(d).name}"
    if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
        return _item(2, "Ficheros", name, "aviso", "sin ffprobe/ffmpeg para mirarlos")
    k = min(EXPORT_SAMPLE, len(vids))
    sample = [vids[round(i * (len(vids) - 1) / max(1, k - 1))] for i in range(k)]
    bad, skel = [], 0
    for v in sample:
        try:
            r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                "stream=codec_name:format=duration", "-of", "default=nw=1", str(v)],
                               capture_output=True, text=True, timeout=20)
            info = dict(ln.split("=", 1) for ln in r.stdout.splitlines() if "=" in ln)
        except (OSError, subprocess.SubprocessError):
            info = {}
        codec, dur = info.get("codec_name", "?"), float(info.get("duration") or 0)
        if codec not in BROWSER_CODECS:
            bad.append(f"{v.name}: formato {codec}")
        elif not EXPORT_DUR_S[0] <= dur <= EXPORT_DUR_S[1]:
            bad.append(f"{v.name}: dura {dur:.1f} s")
        px = _skeleton_pixels(v)
        if px is not None and min(px) >= EXPORT_SKEL_PX:
            skel += 1
    st = "falta" if bad or skel < EXPORT_SKEL_SHARE * k else "ok"
    return _item(2, "Ficheros", name, st,
                 f"{k} de {len(vids)} vídeos mirados: {k - len(bad)} se reproducen con su duración, {skel} con el esqueleto"
                 + (f"; mal: {'; '.join(bad[:3])}" if bad else ""))


def export_end_items(out_dir: Path) -> list[dict]:
    """Request 232 (27-10: the backhand export hung twice): one item per export folder beside the reports
    (exportar_derecha, exportar_reves, exportar_saque, another player's…) saying whether its last export ended;
    the «Exportación: resumen PDF…» item above only looks at the forehand one."""
    from .export import END_RECORD

    return [export_end_item(d) for d in export_dirs(out_dir)]


def export_dirs(out_dir: Path) -> list[Path]:
    from .export import END_RECORD
    return [d for d in sorted(p for p in Path(out_dir).glob("exportar*") if p.is_dir())
            if any((d / n).exists() for n in (END_RECORD, "pila.txt", "resumen.pdf", "golpes"))]


def export_end_item(d: Path) -> dict:
    """Whether the last export into folder d ended. An export removes export.END_RECORD when it starts and writes it
    last, so it is there only when the last export ended. Before that record existed (exports up to 04-11) the dates
    say it: the summary PDF is written last, after the last stack dump of pila.txt (opened at the start and written
    every 5 min while the export runs). A stroke in en_curso.txt short of the total is an export cut or hung there."""
    from .export import END_RECORD

    d = Path(d)
    name = f"Exportación terminada: {d.name}"
    cur = (d / "en_curso.txt").read_text(encoding="utf-8", errors="replace").strip() if (d / "en_curso.txt").exists() else ""
    m = re.search(r"(\d+)/(\d+)$", cur)
    cut = bool(m) and int(m.group(1)) < int(m.group(2))

    def mt(n):
        return (d / n).stat().st_mtime if (d / n).exists() else None
    if mt(END_RECORD) is not None:            # removed when an export starts: there only if the last one ended
        try:
            rec = json.loads((d / END_RECORD).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            return _item(5, "Ficheros", name, "falta", f"{END_RECORD} ilegible ({e})")
        bad = rec.get("failed") or []
        return _item(5, "Ficheros", name, "falta" if bad else "ok",
                     f"terminó el {rec.get('ended', '?')} en {(rec.get('seconds') or 0) / 60:.0f} min: "
                     f"{rec.get('videos', '?')} vídeos de {rec.get('strokes', '?')} golpes"
                     + (f"; {len(bad)} no se pudieron exportar: " + ", ".join(str(b.get("id")) for b in bad[:4]) if bad else ""))
    if cut:
        return _item(5, "Ficheros", name, "falta",
                     f"cortada o colgada en el golpe {cur} (en_curso.txt; dónde estaba cada hilo en pila.txt)")
    if mt("pila.txt") is None:
        return _item(5, "Ficheros", name, "aviso", "sin pila.txt ni registro de fin: no se sabe si terminó")
    if mt("resumen.pdf") is not None and mt("resumen.pdf") >= mt("pila.txt"):
        return _item(5, "Ficheros", name, "ok", f"terminó: su resumen PDF es posterior a su inicio (sin {END_RECORD}: "
                     "exportación anterior a ese registro)" + (f"; último golpe {cur}" if cur else ""))
    return _item(5, "Ficheros", name, "falta", "no terminó: no dejó el resumen PDF de esta exportación"
                 + (f" (último golpe {cur})" if cur else ""))


def petition_items(items: list[dict]) -> list[dict]:
    """One item per user request: the worst status of the audit items that check it on the outputs,
    never better than what the register says (a FALTA request is «falta», a PARCIAL one at best «aviso")."""
    from .requests_check import canonical
    out = []
    for n, text, state in parse_petitions():
        name = f"#{n} {re.sub(r' [(][0-9]{2}-10 .*$', '', text)[:110]}"
        rule = PETITIONS.get(n)
        st_reg = canonical(state)
        if st_reg in ("NO APLICA", "NO MEDIBLE"):
            continue
        # a request the register says is not done is never «ok» nor «pocos datos», whatever its checks say
        if st_reg == "FALTA":
            out.append(_item(11, "Peticiones", name, "falta", f"SIN HACER según el registro (#{n}, docs/peticiones_usuario.md)"))
            continue
        if st_reg is None:
            out.append(_item(11, "Peticiones", name, "falta", f"sin estado válido en el registro («{state}»)"))
            continue
        if rule is None or isinstance(rule, Note):
            done = st_reg == "HECHO"
            why = "sin comprobación automática asignada" if rule is None else f"no se comprueba en las salidas: {rule}"
            out.append(_item(11, "Peticiones", name, "ok" if done and rule is not None else "aviso",
                             ("" if done else f"A MEDIAS según el registro (#{n}); ") + why))
            continue
        rx = re.compile(rule)
        hit = [i for i in items if i.get("req") != 11 and (rx.search(i["name"]) or rx.search(i.get("area", "")))]
        if not hit:
            out.append(_item(11, "Peticiones", name, "aviso", f"ninguna comprobación de esta ejecución la cubre ({rule})"))
            continue
        worst = min(hit, key=lambda i: ORDER[i["status"]])
        cnt = {st: sum(i["status"] == st for i in hit) for st in ORDER}
        st = worst["status"]
        partial = state.startswith(("PARCIAL", "NO"))
        if st == "ok" and partial:                 # its checks pass, but part of it is not built yet
            st = "aviso"
        out.append(_item(11, "Peticiones", name, st,
                         # 08-11: «se cumplen» only when they do (it was said too when one of them warned)
                         ("sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); "
                          if st == "aviso" and partial and worst["status"] == "ok" else
                          "a medias según el registro (ver docs/peticiones_usuario.md); " if partial else "") +
                         f"{len(hit)} comprobaciones: " + ", ".join(f"{v} {k}" for k, v in cnt.items() if v)
                         + ("" if worst["status"] == "ok" else f"; la peor: «{worst['name']}» ({worst['detail'][:120]})")))
    return out


def to_markdown(res: dict) -> str:
    """The audit for a person: requirement by requirement, what is missing first."""
    icon = {"ok": "✔", "falta": "✘", "pocos datos": "…", "aviso": "!"}
    s = res["summary"]
    out = [f"# Auditoría de requisitos ({res['stroke']})", "",
           f"{res['near']} golpes del lado cercano. ✔ {s['ok']} cumplidos · ✘ {s['falta']} no cumplidos · "
           f"… {s['pocos datos']} sin golpes suficientes en esta ejecución · ! {s['aviso']} avisos", ""]
    # first, and never folded: what the user asked for and is not done (docs/peticiones_usuario.md)
    try:
        from .requests_check import pending_markdown
        out += [pending_markdown(), ""]
    except Exception as e:                       # the audit must still be written
        out += [f"## Peticiones del usuario SIN TERMINAR: no se pudo leer el registro ({e})", ""]
    for req, title in REQUIREMENTS.items():
        its = [i for i in res["items"] if i["req"] == req]
        if not its:
            continue
        out += [f"## {req}. {title}", ""]
        for st in ("falta", "aviso", "pocos datos", "ok"):
            for i in its:
                if i["status"] == st:
                    out.append(f"- {icon[st]} **{i['name']}**: {i['detail']}")
        out.append("")
    return "\n".join(out)


def write(res: dict, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "auditoria.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    md = dest / "auditoria.md"
    md.write_text(to_markdown(res), encoding="utf-8")
    return md
