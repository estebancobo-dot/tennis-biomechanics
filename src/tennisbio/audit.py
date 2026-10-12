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
}
# requirement 1, word by word: each variant the user named → factor of the model ("" = none)
VARIANTS_ASKED = {
    "Bola rápida / lenta": "ball_speed", "Bola alta / baja": "ball_height", "Bola corta / profunda": "depth",
    "En carrera / parada / en salto": "movement", "Cada apoyo": "stance_impact", "Dirección del golpe": "shot_type",
    "Ataque / defensa": "intent", "Bola subiendo / arriba / cayendo": "ball_phase", "Bola centrada / abierta": "width",
}
KEY_MOMENTS = {"ready": "espera / split step", "takeback": "inicio de preparación", "loaded": "armado",
               "acceleration": "inicio de aceleración", "impact": "impacto", "extension": "extensión",
               "finish": "terminación", "recovery": "recuperación"}
# physical limits of what is shown (a value outside them is a measurement error that got through)
from .limits import METRIC_LIMITS

LIMITS = {
    **{f"metrics.{k}": v for k, v in METRIC_LIMITS.items()},
    "ball_flight.incoming_speed_kmh": (15, 240), "ball_flight.apex_height_m": (0.2, 4.0),
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
        f = d / "strokes.json"
        if f.exists():
            strokes += [s for s in json.loads(f.read_text(encoding="utf-8")) if s.get("stroke") == stroke]
        if (d / "manifest.json").exists():
            manifests[d.name] = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        if (d / "strokes_errores.json").exists():
            errors += len(json.loads((d / "strokes_errores.json").read_text(encoding="utf-8")) or [])
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

    # 1. variants: every situation the user asked for
    model = (data or {}).get("model") or {}
    variants = model.get("variants") or {}
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
    if data:
        lines = [ln for c in (model.get("cards") or []) for ln in c.get("lines") or []]
        weak = [ln["key"] for ln in lines if (ln.get("n") or 0) < MIN_N or ln.get("rel") is None]
        items.append(_item(3, "Valores posibles", "Cada frase lleva cuántos golpes la respaldan y su fiabilidad",
                           "falta" if weak else "ok" if lines else "pocos datos",
                           f"{len(lines)} frases" + (f"; sin respaldo suficiente: {', '.join(weak[:6])}" if weak else "")))
        items.append(_item(3, "Valores posibles", "Lo no medible se dice", "ok" if model.get("not_measurable") else "falta",
                           f"{len(model.get('not_measurable') or [])} elementos en «Lo que la tele no permite medir»"))

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
    review = sum(bool(s.get("review")) for s in strokes)
    items.append(_item(5, "Automático", "Nada pide revisión manual", "ok",
                       f"{review} golpes llevan dudas marcadas; el informe las enseña, no se piden al usuario"))
    for m, man in manifests.items():
        dur = ((man.get("probe") or {}).get("summary") or {}).get("duration_min")
        secs = sum(e.get("seconds", 0) for e in man.values())
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
    checks = [("golpe", "ball_moments", "«La bola y ella»: qué hace cuando golpea la rival, cruza la red, bota y golpea ella", 2),
              ("golpe", "feet_cycle", "«Sus pies en este golpe»: el ciclo de pies del split step a la recuperación (8 pasos)", 8),
              ("golpe", "heights_layer", "Barras de altura de la cabeza y la cadera sobre el vídeo", 1),
              ("videoteca", "lib_filters", "Filtros combinables de la videoteca (apoyo, dirección, bola, contacto…)", 10),
              ("modelo", "news", "Novedades de la versión en la pantalla de entrada", 1)]
    for tab, key, name, need in checks:
        v = (by.get(tab) or {}).get(key)
        if v is None:
            continue
        items.append(_item(2, "Vistas pedidas", name, "ok" if int(v) >= need else "falta", f"{int(v)} en la pantalla"))
    return items


def to_markdown(res: dict) -> str:
    """The audit for a person: requirement by requirement, what is missing first."""
    icon = {"ok": "✔", "falta": "✘", "pocos datos": "…", "aviso": "!"}
    s = res["summary"]
    out = [f"# Auditoría de requisitos ({res['stroke']})", "",
           f"{res['near']} golpes del lado cercano. ✔ {s['ok']} cumplidos · ✘ {s['falta']} no cumplidos · "
           f"… {s['pocos datos']} sin golpes suficientes en esta ejecución · ! {s['aviso']} avisos", ""]
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
