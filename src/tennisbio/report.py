"""HTML report: all matches of one player and one stroke type, in one offline page.

Layout and interaction come from the approved mockup (docs/maqueta-informe.html), whose data
generator is replaced by the real strokes. Per-stroke frame series go to small .js files loaded
on demand (works from file://), and the stage shows the real window video with the skeleton.

    tennisbio report            → <output>/informe/index.html
"""
import json
import os
import time
from dataclasses import asdict
from pathlib import Path

from .catalog import Match

TEMPLATE = Path(__file__).with_name("report_template.html")

# report key → (group, name, subtitle, unit, decimals, provisional noise, reliability 1-3, source)
METRICS = {
    "xf": ("body", "X-factor", "separación hombros–cadera, armado", "°", 1, 3.4, 2, "x_factor_deg"),
    "sh": ("body", "Rotación de hombros", "armado", "°", 0, 6, 2, "shoulder_turn_loaded_deg"),
    "knee": ("body", "Descenso de cadera", "% de altura, espera → armado", "%", 1, 1.4, 2, "hip_drop_pct"),
    "elbow": ("body", "Codo en el impacto", "hombro–codo–muñeca", "°", 0, 7, 2, "elbow_impact_deg"),
    "lat": ("body", "Impacto lateral", "% de altura desde la cadera", "%", 1, 3.5, 3, "contact_lateral_pct"),
    "contactH": ("body", "Altura del impacto", "% de su altura sobre el suelo", "%", 0, 4, 3, "contact_height_pct"),
    "head": ("body", "Estabilidad de la cabeza", "desplazamiento ±50 ms del impacto", "cm", 1, 1, 2, "head_motion_impact_cm"),
    "finishH": ("body", "Altura de la terminación", "muñeca, % de altura sobre la cadera", "%", 0, 5, 3, "finish_wrist_height_pct"),
    "rHead": ("racket", "Altura de la cabeza en el armado", "cm por encima de la muñeca", "cm", 0, 6, 3, None),
    "rDrop": ("racket", "Caída de la raqueta", "cm por debajo de la muñeca al iniciar la aceleración", "cm", 0, 6, 2, None),
    "rElevImp": ("racket", "Inclinación en el impacto", "° de la raqueta sobre la horizontal", "°", 0, 8, 1, None),
    "rFaceArm": ("racket", "Cara en el armado", "° de cierre (+ cuerdas al suelo, − al cielo)", "°", 0, 10, 2, None),
    "rFaceImp": ("racket", "Cara en el impacto", "° de cierre · estimada (desenfoque)", "°", 0, 12, 1, None),
    "rFaceFin": ("racket", "Cara en la terminación", "° de cierre", "°", 0, 10, 2, None),
    "rYawImp": ("racket", "Dirección de la cara en el impacto", "° (0 = a la red, + hacia su lado dominante)", "°", 0, 12, 1, None),
    "split": ("feet", "Split step", "aterrizaje, ms tras el golpe del rival", "ms", 0, 30, 2, None),
    "base": ("feet", "Anchura de la base", "% de altura, armado", "%", 0, 4.5, 3, "base_width_loaded_pct"),
    "baseM": ("feet", "Anchura de la base", "metros en la pista, impacto", "m", 2, 0.08, 3, None),
    "disp": ("feet", "Desplazamiento", "m desde el golpe del rival", "m", 1, 0.3, 3, None),
    "recov": ("feet", "Recuperación", "s del impacto al primer paso", "s", 2, 0.15, 2, None),
}
NET_Y = 11.885


def _num(v):
    return None if v is None else float(v)


def _score_fields(sc: dict | None) -> dict:
    """set / game / score text / pressure from the scoreboard reading at the stroke (or None)."""
    if not sc:
        return {"set": None, "game": None, "score": None, "pressure": None}
    g = sc.get("games") or [[0, 0]]
    pts = sc.get("points") or [None, None]
    games = f"{g[-1][0]}-{g[-1][1]}"
    points = "-".join(p or "0" for p in pts) if any(pts) else ""
    return {"set": sc.get("set"), "game": sum(g[-1]) + 1, "score": f"{games} {points}".strip() + (f" · {sc['banner'].lower()}" if sc.get("banner") else ""),
            "pressure": bool(sc.get("pressure"))}


def stroke_record(s: dict, match_idx: int, match: Match, duration_s: float, idx: int) -> dict:
    """One stroke in the report's schema (see the mockup's STROKES)."""
    m, ph, rk = s.get("metrics", {}), s.get("phases", {}), s.get("racket", {})
    t_av = _num(m.get("time_available_s"))
    pos = s.get("court_pos_m")
    x = None if pos is None else pos[0]
    y = None if pos is None else NET_Y - pos[1]                # distance from the net, as in the mockup
    ch = _num(m.get("contact_height_pct"))
    height = None if ch is None else "baja" if ch < 40 else "alta" if ch > 75 else "media"
    disp = _num(s.get("displacement_m"))
    fast, wide, short = (t_av is not None and t_av < 1.15), (disp is not None and disp > 2.6), (y is not None and y < 10.6)
    vals = {k: (_num(m.get(src)) if src else None) for k, (*_, src) in METRICS.items()}
    vals["rHead"] = _num((rk.get("loaded") or {}).get("head_above_wrist_cm"))
    acc = _num((rk.get("acceleration") or {}).get("head_above_wrist_cm"))
    vals["rDrop"] = None if acc is None else -acc
    vals["rElevImp"] = _num((rk.get("impact") or {}).get("elevation_deg"))
    face = s.get("face") or {}
    for key, ph_name, field in (("rFaceArm", "loaded", "tilt_deg"), ("rFaceImp", "impact", "tilt_deg"),
                                ("rFaceFin", "finish", "tilt_deg"), ("rYawImp", "impact", "yaw_deg")):
        vals[key] = _num((face.get(ph_name) or {}).get(field))
    ready = ph.get("ready") or {}
    if ready.get("method") == "split_step_landing" and t_av is not None and ready.get("t_rel") is not None:
        vals["split"] = round((ready["t_rel"] + t_av) * 1000)
    vals["baseM"] = _num(s.get("stance_width_m"))
    vals["disp"] = disp
    vals["recov"] = _num((ph.get("recovery") or {}).get("t_rel")) if (ph.get("recovery") or {}).get("method") == "first_step" else None
    confs = [p.get("confidence", 0) for p in ph.values()]
    quality = max(0.05, min(0.99, (sum(confs) / len(confs) if confs else 0.5) - 0.08 * len(s.get("review", []))))
    sit = {"neutra": not (fast or wide or short) and height == "media" and t_av is not None,
           "abierta": wide, "rapida": fast, "baja": height == "baja", "corta": short}
    t = float(s.get("match_time_s", 0))
    return {
        "id": f"{match.id}-{idx + 1:03d}", "idx": 0, "match": match_idx, "frac": t / duration_s if duration_s else 0,
        **_score_fields(s.get("score")), "outcome": None, "finishType": None,
        "tAvail": t_av, "disp": disp, "height": height, "x": x, "y": y, "fast": fast, "wide": wide, "short": short,
        "stance": s.get("stance"), "stanceAngle": s.get("stance_angle_deg"),
        "chainOK": (s.get("chain") or {}).get("proximal_to_distal"), "chainPeaks": (s.get("chain") or {}).get("peaks_s"),
        "quality": round(quality, 3), "review": s.get("review", []), "source": s.get("impact_source"),
        "m": vals, "vt": t, "sit": sit,
        "phases": {k: v.get("t_rel") for k, v in ph.items()},
        "face": {k: (v or {}).get("points_to") for k, v in face.items()},
        "video": None, "vImpact": s.get("window_impact_s"), "series": None,
    }


def collect(matches: list[Match], out_root: Path, stroke="forehand") -> dict:
    ms, strokes, review = [], [], 0
    for mi, match in enumerate(matches):
        d = out_root / match.id
        f = d / "strokes.json"
        if not f.exists():
            continue
        dur = json.loads((d / "probe.json").read_text(encoding="utf-8")).get("duration", 0) if (d / "probe.json").exists() else 0
        rows = [s for s in json.loads(f.read_text(encoding="utf-8")) if s.get("stroke") == stroke]
        for k, s in enumerate(rows):
            r = stroke_record(s, len(ms), match, dur, k)
            r["idx"] = len(strokes)
            r["_dir"], r["_window"], r["_series"] = str(d), s.get("window"), s.get("series")
            strokes.append(r)
            review += bool(r["review"])
        ms.append({"id": match.id, "rival": match.opponent or "—", "surf": match.surface or "—",
                   "round": match.round or "—", "date": match.date or "—", "sets": None, "n": len(rows), "res": "—"})
    return {"matches": ms, "strokes": strokes, "review": review,
            "metrics": [{"k": k, "g": g, "name": n, "sub": sub, "unit": u, "dec": dec, "noise": noise, "rel": rel}
                        for k, (g, n, sub, u, dec, noise, rel, _) in METRICS.items()]}


def build(matches: list[Match], out_root: Path, dest: Path | None = None, stroke="forehand",
          player: dict | None = None) -> Path:
    """Write the report (index.html + series/*.js) and return the path of index.html.

    matches: those of one player (the report is per player and stroke)."""
    if player is None and matches:
        player = asdict(matches[0].player)
    dest = Path(dest or out_root / "informe")
    (dest / "series").mkdir(parents=True, exist_ok=True)
    data = collect(matches, out_root, stroke)
    for r in data["strokes"]:
        d = Path(r.pop("_dir"))
        win, ser = r.pop("_window"), r.pop("_series")
        if win:
            r["video"] = Path(os.path.relpath(d / "windows" / win, dest)).as_posix()
        if ser and (d / ser).exists():
            js = dest / "series" / f"{r['id']}.js"
            js.write_text(f"window.SERIES[{json.dumps(r['id'])}]={(d / ser).read_text(encoding='utf-8')};", encoding="utf-8")
            r["series"] = f"series/{r['id']}.js"
    data["player"] = player or {}
    data["stroke"] = stroke
    data["generated"] = time.strftime("%Y-%m-%d %H:%M")
    data["noise_validated"] = False
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False))
    out = dest / "index.html"
    out.write_text(html, encoding="utf-8")
    return out
