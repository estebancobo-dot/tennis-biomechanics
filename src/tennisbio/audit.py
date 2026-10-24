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
                       n=len(near)))
    items += recall_items(match_dirs)
    items += views_items(match_dirs)

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
    items.append(_item(5, "Automático", "Nada pide revisión manual", "ok",
                       f"{review} golpes llevan dudas marcadas; el informe las enseña, no se piden al usuario"))
    for m, man in manifests.items():
        dur = ((man.get("probe") or {}).get("summary") or {}).get("duration_min")
        secs = total_seconds(man)          # stages run at the same time count once
        if dur:
            per_h = secs / 3600 / (dur / 60) if dur else None        # hours of processing per hour of video
            st = "ok" if per_h is not None and per_h * 3.5 <= 12 else "aviso"
            items.append(_item(9, "Rendimiento", f"Tiempo: {m}", st,
                               f"{secs / 60:.0f} min para {dur:.0f} min de vídeo ≈ {per_h * 3.5:.1f} h para un partido de 3,5 h "
                               "(con las etapas medidas en su última ejecución)"))
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
        status, detail = recall_verdict(len(strokes), serves, counts)
        sides = f" ({sum(s.get('side') != 'far' for s in strokes)} cerca, {sum(s.get('side') == 'far' for s in strokes)} lejos)"
        try:                                      # strokes of undecided identity: analysed, kept apart, not hers yet
            doubt = json.loads((_mf.at(d, "strokes_doubtful.json")).read_text(encoding="utf-8")) if (_mf.at(d, "strokes_doubtful.json")).exists() else []
        except (OSError, ValueError):
            doubt = []
        if doubt:
            sides += f"; además {len(doubt)} de identidad dudosa, apartados (no cuentan como suyos)"
        out.append(_item(1, "Golpes", f"Golpes encontrados frente al marcador: {d.name}", status, detail + sides,
                         found=len(strokes), serves=serves, counts=counts, doubtful=len(doubt)))
    return out


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
    12: r"Validación con clips anotados", 13: Note("en los tests del código (uv run pytest, pc-logs:pruebas.log), no en las salidas"),
    14: r"^Rendimiento$", 15: r"Vídeos de análisis de entrenadores", 16: r"Botepronto|Volea",
    17: r"Pantalla «Cópiala|Novedades|^Aprende su derecha$", 18: r"golpes analizados", 19: r"Cada golpe tiene su vídeo",
    20: r"^Rendimiento$", 21: r"golpes analizados", 22: r"golpes analizados", 23: r"golpes analizados",
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
    51: Note("el mismo código (clip_pipeline, stages) en la prueba y en los partidos"), 52: r"Navegador de las capturas|Pantalla «",
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
    132: r"Golpe angulado", 157: r"Bola corta baja cerca de la red", 158: r"Bola corta alta cerca de la red",
    159: r"Volea a media pista con golpe de fondo|Volea fuera de la línea de saque",
}
ORDER = {"falta": 0, "aviso": 1, "pocos datos": 2, "ok": 3}


def parse_petitions(path: Path = PETITIONS_DOC) -> list[tuple[int, str, str]]:
    """(number, request, state in the document) of each row of the table of user requests."""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines() if path.exists() else []:
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) >= 3 and c[0].isdigit():
            out.append((int(c[0]), c[1], c[2]))
    return out


def side_checks(out_root: Path) -> list[dict]:
    """Outputs that live next to the match folders: the validation with annotated public clips and the
    coach videos Claude learned from."""
    base = [out_root, out_root.parent, out_root.parent.parent]
    items = []
    f3 = next((b / "datasets" / "reports" / "f3set_validation.json" for b in base
               if (b / "datasets" / "reports" / "f3set_validation.json").exists()), None)
    if f3 is None:
        items.append(_item(3, "Validación", "Validación con clips anotados (F3Set)", "aviso", "no se encontró f3set_validation.json"))
    else:
        sm = json.loads(f3.read_text(encoding="utf-8")).get("summary", {})
        items.append(_item(3, "Validación", "Validación con clips anotados (F3Set)", "ok" if sm.get("f1", 0) >= 0.6 else "falta",
                           f"golpes: precisión {sm.get('precision')}, recall {sm.get('recall')}; derecha/revés {sm.get('fh_bh_accuracy')}; "
                           f"dirección {sm.get('direction_accuracy')}. Solo detección y clases: el valor de cada medida (codo, rodillas, "
                           "pasos…) aún no tiene clips anotados con los que compararse"))
    inv = next((b / "investigacion" / "indice.json" for b in base if (b / "investigacion" / "indice.json").exists()), None)
    if inv is None:
        items.append(_item(6, "Aprendizaje", "Vídeos de análisis de entrenadores (solo para aprender)", "aviso", "no se han bajado"))
    else:
        v = json.loads(inv.read_text(encoding="utf-8"))
        n = sum(1 for x in v if x.get("subtitles"))
        items.append(_item(6, "Aprendizaje", "Vídeos de análisis de entrenadores (solo para aprender)", "ok" if n else "aviso",
                           f"{len(v)} vídeos, {n} con texto (docs/aprendido_entrenadores.md); nunca en el informe"))
    return items


def file_tree_items(match_dirs: list[Path], report_dir: Path | None, out_root: Path) -> list[dict]:
    """Every file a run must leave, checked to exist and not be empty: each stage's outputs per match,
    a video window and a frame-by-frame series per stroke, the report with its series and thumbnails,
    the export (PDF and clips) and the practice section (one clip per stroke)."""
    from . import stages  # noqa: F401  (registers the stages)
    from .pipeline import STAGES

    items = []
    ok = lambda f: f.exists() and f.stat().st_size > 0
    for d in match_dirs:
        miss = [f"{n}/{o}" for n, st in STAGES.items() for o in st.outputs if not ok(d / o)]
        st_file = _mf.at(d, "strokes.json")
        strokes = json.loads(st_file.read_text(encoding="utf-8")) if ok(st_file) else []
        win = [x for x in strokes if x.get("window") and not ok(_mf.at(d, "windows") / x["window"])]
        ser = [x for x in strokes if x.get("series") and not ok(d / x["series"])]
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
    pr = next((b / "entrenamiento" for b in (out_root, out_root.parent) if (b / "entrenamiento" / "entrenamiento.json").exists()), None)
    if pr is not None:
        st = json.loads((pr / "entrenamiento.json").read_text(encoding="utf-8")).get("strokes", [])
        miss = [x["id"] for x in st if not x.get("clip") or not ok(pr / "clips" / x["clip"])]
        items.append(_item(5, "Ficheros", "Vista lateral: entrenamiento.json y un vídeo con esqueleto por golpe",
                           "falta" if miss else "ok", f"{len(st) - len(miss)} de {len(st)} vídeos"
                           + (f"; faltan: {', '.join(miss[:4])}" if miss else "")))
    return items


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
                         ("sus comprobaciones se cumplen, pero sigue a medias (ver docs/peticiones_usuario.md); " if st == "aviso" and partial else "") +
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
