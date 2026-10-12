"""HTML report: all matches of one player and one stroke type, in one offline page.

Layout and interaction come from the approved mockup (docs/maqueta-informe.html), whose data
generator is replaced by the real strokes. Per-stroke frame series go to small .js files loaded
on demand (works from file://), and the stage shows the real window video with the skeleton.

    tennisbio report            → <output>/informe/index.html
"""
import json
import os
import shutil
import subprocess

import numpy as np
import time
from dataclasses import asdict
from pathlib import Path

from .catalog import Match


def opponent_profile(match):
    from .stages import opponent_profile as op
    return op(match)

TEMPLATE = Path(__file__).with_name("report_template.html")

# report key → (group, name, subtitle, unit, decimals, provisional noise, reliability 1-3, source)
METRICS = {
    "xf": ("body", "X-factor", "separación hombros–cadera, armado", "°", 1, 3.4, 2, "x_factor_deg"),
    "sh": ("body", "Rotación de hombros", "armado", "°", 0, 6, 2, "shoulder_turn_loaded_deg"),
    "xf3d": ("body", "X-factor 3D", "estimación monocular (RTMW3D), armado", "°", 0, 6, 2, "x_factor_3d_deg"),
    "sh3d": ("body", "Rotación de hombros 3D", "estimación monocular, armado · 0 = de cara a la red", "°", 0, 8, 2, "shoulder_turn_3d_deg"),
    "knee": ("body", "Descenso de cadera", "% de altura, espera → armado", "%", 1, 1.4, 2, "hip_drop_pct"),
    "elbow": ("body", "Codo en el impacto", "hombro–codo–muñeca", "°", 0, 7, 2, "elbow_impact_deg"),
    "offArm": ("body", "Brazo no dominante en el armado", "ángulo del codo (180 = extendido)", "°", 0, 10, 2, "non_arm_extension_loaded_deg"),
    "elbowNon": ("body", "Codo no dominante en el impacto", "revés a dos manos: segundo brazo", "°", 0, 8, 2, "non_elbow_impact_deg"),
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
    "trophyKnee": ("body", "Flexión en el trofeo", "saque: descenso de cadera, % de altura", "%", 1, 1.5, 2, "serve_knee_bend_hip_drop_pct"),
    "trophyTilt": ("body", "Inclinación de hombros en el trofeo", "saque: + hombro del brazo de lanzamiento más alto", "°", 0, 5, 3, "serve_shoulder_tilt_trophy_deg"),
    "toss": ("body", "Brazo de lanzamiento", "saque: altura de la mano en el trofeo, % de altura", "%", 0, 4, 3, "serve_toss_arm_height_pct"),
    "landing": ("feet", "Aterrizaje", "saque: m dentro de la pista tras el impacto", "m", 2, 0.15, 3, None),
    "shotDepth": ("feet", "Profundidad de su golpe", "m desde la línea de fondo rival al bote (− = larga)", "m", 1, 0.3, 3, None),
    "ballKmh": ("feet", "Velocidad media de su bola", "km/h en horizontal, del impacto al bote (no la de salida)", "km/h", 0, 5, 2, None),
    "shotQ": ("feet", "Calidad del golpe (indicador propio)", "0-100: profundidad, anchura y velocidad media", "", 0, 6, 2, None),
    "split": ("feet", "Split step", "aterrizaje, ms tras el golpe del rival", "ms", 0, 30, 2, None),
    "base": ("feet", "Base (% de altura)", "% de altura, armado", "%", 0, 4.5, 3, "base_width_loaded_pct"),
    "baseM": ("feet", "Anchura de la base", "metros en la pista, impacto", "m", 2, 0.08, 3, None),
    "disp": ("feet", "Desplazamiento", "m desde el golpe del rival", "m", 1, 0.3, 3, None),
    "recov": ("feet", "Recuperación", "s del impacto al primer paso", "s", 2, 0.15, 2, None),
}
NET_Y = 11.885
# metrics that stay reliable when she is at the far end (small, facing the camera)
FAR_OK = {"contactH", "disp", "shotDepth", "landing", "ballKmh", "shotQ"}
# estimates, not measurements (the racket is blurred at contact): shown, never used as findings
ESTIMATED = {"rFaceImp", "rYawImp"}


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


def stroke_record(s: dict, match_idx: int, match: Match, duration_s: float, idx: int, hand: str | None = None) -> dict:
    """One stroke in the report's schema (see the mockup's STROKES). hand: of the analysed player
    (the opponent's when the rows are hers)."""
    hand = hand or match.player.hand
    m, ph, rk = s.get("metrics", {}), s.get("phases", {}), s.get("racket", {})
    t_av = _num(m.get("time_available_s"))
    pos = s.get("court_pos_m")
    # left-handers are mirrored so that "+x" is always the forehand side (comparable players)
    x = None if pos is None else (-pos[0] if hand == "left" else pos[0])
    y = None if pos is None else NET_Y - pos[1]                # distance from the net, as in the mockup
    ch = _num(m.get("contact_height_pct"))
    height = None if ch is None else "baja" if ch < 40 else "alta" if ch > 75 else "media"
    disp = _num(s.get("displacement_m"))
    bounce = s.get("bounce_court_m")
    bounce_depth = None if bounce is None else round(bounce[1], 2)      # m in front of her baseline
    # short ball: bounce more than 4.5 m inside the court when known (else: hit from inside the court)
    short_ball = (bounce_depth > 4.5) if bounce_depth is not None else (y is not None and y < 10.6)
    fast, wide, short = (t_av is not None and t_av < 1.15), (disp is not None and disp > 2.6), short_ball
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
    vals["landing"] = _num(s.get("landing_inside_m"))
    vals["shotDepth"] = _num(s.get("shot_depth_m"))
    vals["ballKmh"] = _num(s.get("ball_speed_avg_kmh"))
    vals["shotQ"] = _num(s.get("shot_quality_proxy"))
    vals["recov"] = _num((ph.get("recovery") or {}).get("t_rel")) if (ph.get("recovery") or {}).get("method") == "first_step" else None
    far = s.get("side") == "far"
    if far:
        vals = {k: (v if k in FAR_OK else None) for k, v in vals.items()}
    chain = s.get("chain") or {}
    confs = [p.get("confidence", 0) for p in ph.values()]
    quality = max(0.05, min(0.99, (sum(confs) / len(confs) if confs else 0.5) - 0.08 * len(s.get("review", []))))
    sit = {"neutra": not (fast or wide or short) and height == "media" and t_av is not None,
           "abierta": wide, "rapida": fast, "baja": height == "baja", "corta": short}
    t = float(s.get("match_time_s", 0))
    return {
        # stable id: the match and the instant of the impact (a re-run that adds a stroke elsewhere keeps it)
        "id": s.get("stroke_id") or f"{match.id}-{int(round(t * 100)):07d}", "idx": 0, "match": match_idx,
        "frac": t / duration_s if duration_s else None,
        **_score_fields(s.get("score")), "finishType": None,
        # out = error (from where it bounced); otherwise unknown until the point is followed further
        "outcome": {"out": "error", "net": "error", "winner": "ganador", "rally": "sigue"}.get(
            s.get("outcome") or ("out" if s.get("shot_in") is False else "")),
        "outcomeDetail": s.get("outcome") or ("out" if s.get("shot_in") is False else None),
        "shotInPoint": s.get("shot_in_point"), "shotsInPoint": s.get("shots_in_point"),
        "shotIn": s.get("shot_in"), "shotDir": s.get("shot_direction"), "shotSide": s.get("shot_side"),
        "shotX": None if not s.get("shot_bounce_m") else (-s["shot_bounce_m"][0] if hand == "left" else s["shot_bounce_m"][0]),
        "shotY": None if not s.get("shot_bounce_m") else s["shot_bounce_m"][1],
        "tAvail": t_av, "bounceDepth": bounce_depth,
        "bounceX": None if bounce is None else (-bounce[0] if hand == "left" else bounce[0]),
        "bounceToImpact": _num(m.get("bounce_to_impact_s")), "disp": disp, "height": height, "x": x, "y": y, "fast": fast, "wide": wide, "short": short,
        "stance": None if far else s.get("stance"), "stanceAngle": None if far else s.get("stance_angle_deg"),
        "chainOK": None if far else chain.get("proximal_to_distal"), "chainPeaks": None if far else chain.get("peaks_s"),
        "quality": round(quality * (0.6 if far else 1.0), 3), "side": "far" if far else "near", "review": s.get("review", []), "source": s.get("impact_source"),
        "m": vals, "vt": t, "sit": sit,
        "phases": {k: v.get("t_rel") for k, v in ph.items()},
        # heights through the stroke and the ball moments (s from contact): near side only
        "curves": None if far else (s.get("technique") or {}).get("curves"),
        "ballT": None if far else {k: -v["t_to_contact"] for k, v in ((s.get("technique") or {}).get("phases") or {}).items()
                                   if k.startswith("ball_") and isinstance(v, dict) and v.get("t_to_contact") is not None},
        "face": {k: (v or {}).get("points_to") for k, v in face.items()},
        "video": None, "vImpact": s.get("window_impact_s"), "series": None,
    }


# metric → (series group, series key, phase used by the metric)
SERIES_NOISE = {"elbow": ("ang", "Codo", "impact"), "xf": ("ang", "X-factor", "loaded"),
                "rFaceArm": ("face", "tilt", "loaded"), "rFaceImp": ("face", "tilt", "impact"),
                "rFaceFin": ("face", "tilt", "finish")}


def frame_noise(x, k: int, half=6) -> float | None:
    """Frame-to-frame jitter of a per-frame series around frame k from the second difference
    (x[t-1] - 2x[t] + x[t+1] has variance 6σ² for white noise): robust σ = 1.4826·median|Δ²| / √6.

    The keypoints are already smoothed (kinematics.clean), so this is a LOWER bound of the
    measurement noise; the stroke-to-stroke noise also includes phase timing. The report keeps
    the larger of this and the provisional value until it is measured on equivalent strokes."""
    vals = []
    for t in range(max(1, k - half), min(len(x) - 1, k + half + 1)):
        a, b, c = x[t - 1], x[t], x[t + 1]
        if None not in (a, b, c):
            vals.append(abs(a - 2 * b + c))
    return None if len(vals) < 3 else 1.4826 * float(np.median(vals)) / np.sqrt(6)


def noise_from_series(series_files: list[tuple[Path, dict]]) -> dict:
    """Median over strokes of the frame-to-frame noise of each metric that has a per-frame series."""
    per = {k: [] for k in SERIES_NOISE}
    for path, phases in series_files:
        ser = json.loads(path.read_text(encoding="utf-8"))
        for key, (grp, name, phase) in SERIES_NOISE.items():
            f = (phases.get(phase) or {}).get("frame")
            src = ser.get(grp) or {}
            x = src.get(name)
            if f is None or x is None:
                continue
            k = f - (src.get("first", ser["first"]) if grp == "face" else ser["first"])
            n = frame_noise(x, k)
            if n is not None:
                per[key].append(n)
    return {k: round(float(np.median(v)), 2) for k, v in per.items() if len(v) >= 3}


def noise_from_pairs(strokes: list[dict], min_strokes=20) -> dict:
    """Upper bound of the measurement noise: for neutral-ball strokes, pair each one with the most
    similar stroke (time available, contact height, court position, standardised) and take the
    robust spread of their differences / √2. It also contains real technique variation, so it
    over-estimates the noise — a conservative threshold for "real difference"."""
    pool = [s for s in strokes if s["sit"].get("neutra")]
    feats = []
    for s in pool:
        f = [s.get("tAvail"), s["m"].get("contactH"), s.get("x"), s.get("y")]
        feats.append([np.nan if v is None else float(v) for v in f])
    if len(pool) < min_strokes:
        return {}
    F = np.array(feats)
    F = (F - np.nanmean(F, 0)) / (np.nanstd(F, 0) + 1e-9)
    F = np.nan_to_num(F)
    from scipy.spatial import cKDTree      # nearest neighbour without an n×n matrix (thousands of strokes)

    _, idx = cKDTree(F).query(F, k=2)
    nn = np.where(idx[:, 0] == np.arange(len(F)), idx[:, 1], idx[:, 0])     # itself, unless duplicated
    out = {}
    for k in METRICS:
        diffs = [pool[i]["m"].get(k) - pool[j]["m"].get(k) for i, j in enumerate(nn)
                 if pool[i]["m"].get(k) is not None and pool[j]["m"].get(k) is not None]
        if len(diffs) >= min_strokes // 2:
            out[k] = round(1.4826 * float(np.median(np.abs(diffs))) / np.sqrt(2), 2)
    return out


def collect(matches: list[Match], out_root: Path, stroke="forehand", player_id: str | None = None) -> dict:
    """player_id: the match's player (strokes.json) or its opponent (strokes_opponent.json, when
    matches.yaml gives opponent_id); default: each match's player."""
    ms, strokes, review, raw = [], [], 0, []
    for mi, match in enumerate(matches):
        d = out_root / match.id
        is_opp = player_id is not None and player_id != match.player.id
        f = d / ("strokes_opponent.json" if is_opp else "strokes.json")
        if not f.exists():
            continue
        dur = json.loads((d / "probe.json").read_text(encoding="utf-8")).get("duration", 0) if (d / "probe.json").exists() else 0
        rows = [s for s in json.loads(f.read_text(encoding="utf-8")) if s.get("stroke") == stroke]
        for k, s in enumerate(rows):
            r = stroke_record(s, len(ms), match, dur, k, opponent_profile(match).hand if is_opp else match.player.hand)
            r["idx"] = len(strokes)
            r["_dir"], r["_window"], r["_series"] = str(d), s.get("window"), s.get("series")
            r["_phases"] = s.get("phases", {})
            strokes.append(r)
            review += bool(r["review"])
            raw.append({**s, "match_id": match.id, "stroke_id": r["id"]})
        found = json.loads((d / "score.json").read_text(encoding="utf-8")).get("opponent") if (d / "score.json").exists() else None
        rival = match.player.name if is_opp else (match.opponent or found or "—")
        ms.append({"id": match.id, "rival": rival, "surf": match.surface or "—",
                   "round": match.round or "—", "date": match.date or "—", "sets": None, "n": len(rows), "res": "—"})
    keep = stroke_metrics(stroke)
    return {"matches": ms, "strokes": strokes, "review": review, "_raw": raw,
            "metrics": [{"k": k, "g": g, "name": n, "sub": sub, "unit": u, "dec": dec, "noise": noise, "rel": rel,
                         "est": k in ESTIMATED}
                        for k, (g, n, sub, u, dec, noise, rel, _) in METRICS.items() if k in keep]}


def stroke_metrics(stroke: str) -> list[str]:
    """Report metrics of a stroke type (config/strokes/<stroke>.yaml), all when not configured."""
    import yaml
    from .config import CONFIG_DIR

    f = CONFIG_DIR / "strokes" / f"{stroke}.yaml"
    keys = yaml.safe_load(f.read_text(encoding="utf-8")).get("report_metrics") if f.exists() else None
    return [k for k in (keys or METRICS) if k in METRICS]


def thumbnail(video: Path, t: float, box: list | None, out: Path, width=360) -> bool:
    """Poster of a stroke for the video library: the frame of the impact, cropped around the player
    (16:10) when her box is known. Skipped when it already exists and is newer than the video."""
    if out.exists() and out.stat().st_mtime >= video.stat().st_mtime:
        return True
    if not shutil.which("ffmpeg"):
        return False
    vf = f"scale={width}:-2"
    if box:
        x0, y0, x1, y1 = box
        h = max(40.0, (y1 - y0) * 2.1)
        w = h * 1.6
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        vf = (f"crop='min({w:.0f},iw)':'min({h:.0f},ih)':"
              f"'max(0,min(iw-min({w:.0f},iw),{cx - w / 2:.0f}))':'max(0,min(ih-min({h:.0f},ih),{cy - h / 2:.0f}))',"
              f"scale={width}:-2")
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, t):.3f}", "-i", str(video), "-frames:v", "1",
                        "-vf", vf, "-q:v", "4", str(out)], capture_output=True)
    return r.returncode == 0 and out.exists()


def prepare(matches: list[Match], out_root: Path, stroke="forehand", player_id: str | None = None) -> dict:
    """Strokes and metrics with the measurement noise settled (shared by the report and the export).
    Each stroke keeps _dir, _window, _series and _phases (paths into the match folders)."""
    data = collect(matches, out_root, stroke, player_id)
    series_files = [(Path(r["_dir"]) / r["_series"], r["_phases"]) for r in data["strokes"]
                    if r["_series"] and (Path(r["_dir"]) / r["_series"]).exists()]
    auto = noise_from_series(series_files)
    for m in data["metrics"]:
        if m["k"] in auto:              # lower bound: never claim more precision than the provisional value
            m["noise"] = max(m["noise"], auto[m["k"]])
            m["noise_auto"] = auto[m["k"]]
    data["noise_auto"] = auto
    pairs = noise_from_pairs(data["strokes"])
    for m in data["metrics"]:
        if m["k"] in pairs:             # measured on her own equivalent strokes: replaces the provisional value
            # never below a third of the provisional value: a metric that barely varies would
            # otherwise make any tiny difference look real
            m["noise"] = max(pairs[m["k"]], auto.get(m["k"], 0.0), m["noise"] / 3)
            m["noise_pairs"] = pairs[m["k"]]
    data["noise_pairs"] = pairs
    data["noise_validated"] = bool(pairs)
    return data


def player_dict(matches: list[Match], player_id: str | None = None) -> dict:
    if not matches:
        return {}
    if player_id and player_id != matches[0].player.id:
        from .stages import opponent_profile
        return asdict(opponent_profile(matches[0]))
    return asdict(matches[0].player)


def build(matches: list[Match], out_root: Path, dest: Path | None = None, stroke="forehand",
          player: dict | None = None, player_id: str | None = None) -> Path:
    """Write the report (index.html + series/*.js) and return the path of index.html.

    matches: those of one player (the report is per player and stroke)."""
    if player is None:
        player = player_dict(matches, player_id)
    dest = Path(dest or out_root / "informe")
    (dest / "series").mkdir(parents=True, exist_ok=True)
    data = prepare(matches, out_root, stroke, player_id)
    for r in data["strokes"]:
        r.pop("_phases", None)
        d = Path(r.pop("_dir"))
        win, ser = r.pop("_window"), r.pop("_series")
        box = None
        if ser and (d / ser).exists():
            txt = (d / ser).read_text(encoding="utf-8")
            js = dest / "series" / f"{r['id']}.js"
            js.write_text(f"window.SERIES[{json.dumps(r['id'])}]={txt};", encoding="utf-8")
            r["series"] = f"series/{r['id']}.js"
            sj = json.loads(txt)
            k = sj["impact"] - sj["first"]
            box = next((sj["box"][j] for j in (k, k - 1, k + 1, k - 2, k + 2) if 0 <= j < len(sj["box"]) and sj["box"][j]), None)
        if win and (d / "windows" / win).exists():
            r["video"] = Path(os.path.relpath(d / "windows" / win, dest)).as_posix()
            th = dest / "thumbs" / f"{r['id']}.jpg"
            th.parent.mkdir(exist_ok=True)
            if r.get("vImpact") is not None and thumbnail(d / "windows" / win, r["vImpact"], box, th):
                r["thumb"] = f"thumbs/{r['id']}.jpg"
        elif win:
            r["video"] = Path(os.path.relpath(d / "windows" / win, dest)).as_posix()
    from . import findings as F
    from .explain import model_view
    from .model import build_model
    dist = F.distributions(data)
    F.representativeness(data, dist)
    finds = F.discover(data)
    concl = F.conclusions(data, dist, finds)
    pair_of = {p["t"]: p["key"] for p in F._pairs(data["strokes"])}
    data["findings"] = [{"k": f.k, "t": f.title, "c": f.context, "A": [s["id"] for s in f.A], "B": [s["id"] for s in f.B],
                         "e": vars(f.effect), "v": list(f.verdict), "q": getattr(f, "q", None),
                         "pair": next((v for t, v in pair_of.items() if f.title.endswith(t)), "")} for f in finds]
    data["conclusions"] = [{"text": c.text, "conf": c.confidence, "level": c.level, "ids": [s["id"] for s in c.strokes[:40]],
                            "find": finds.index(c.finding) if c.finding in finds else None} for c in concl]
    data["model"] = model_view(build_model(data.pop("_raw", [])), stroke)
    data["player"] = player or {}
    data["stroke"] = stroke
    data["generated"] = time.strftime("%Y-%m-%d %H:%M")
    ids = {r["id"] for r in data["strokes"]}
    for sub, ext in (("series", ".js"), ("thumbs", ".jpg")):          # strokes that no longer exist
        for f in (dest / sub).glob(f"*{ext}") if (dest / sub).exists() else []:
            if f.stem not in ids:
                f.unlink(missing_ok=True)
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False))
    out = dest / "index.html"
    out.write_text(html, encoding="utf-8")
    return out
