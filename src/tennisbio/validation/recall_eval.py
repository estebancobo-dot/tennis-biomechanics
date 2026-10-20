"""Stroke recall benchmark: every annotated stroke of the player (F3Set-Tennis), followed through the
match pipeline to the step where it is lost.

The match pipeline (stages: scenes → players → identity → candidates → fine) runs on a "compilation"
of the broadcast: the annotated points of each match (with a few seconds before and after), joined in
one video, so it is processed exactly as a full match is (main camera, identity by the scoreboard,
replays, candidates, gate, ball, confirmation). Every annotated stroke of hers is then placed in the
outputs of each stage, in this order (the first that fails is where it was lost):

1. fuera_de_camara      its instant is not in a main-camera shot (scenes.json)
2. sin_seguimiento      no tracked run of the near player covers it (players / identity runs): no
                        candidate of either end can come from there
3. repeticion           the run is taken as a replay (scoreboard missing, or a slower / silent repeat
                        of an earlier path: the same rule as st_candidates)
4. identidad_sin_decidir / identidad_equivocada
                        the run's near_is_target is None, or says the wrong player is near
5. no_candidato         no candidate of her end within CONFIRM_TOL_S
6. error / lejana_no_encontrada / sin_ventana
                        her window failed, the far player was not found in it, or no window record
7. criba_sin_golpe      the gate dropped the window (no ball hit of her end near the candidates)
8. bola_no_vista        the window was analysed but the stroke was not confirmed, with the ball seen in
                        fewer than SEEN_NEEDED of the frames around it
9. no_confirmado        analysed, ball seen, not confirmed (pose / fusion)
10. encontrado          a stroke of hers in strokes.json within `tol` of the annotated contact
    encontrado_dudoso    not in strokes.json but in strokes_doubtful.json (a run of undecided identity,
                         analysed in full and kept apart): not lost, not yet counted as hers

Nothing here changes what the pipeline detects: the replay rule is recomputed from the stage outputs with
the same helpers, and the windows are read from the fine stage's own log lines.
"""
from __future__ import annotations

import json
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .impact_eval import clip_bounds, parse_label

KINDS = {"serve": "saque", "forehand": "derecha", "backhand": "revés", "volley_other": "volea / remate / otro"}
SIDES = {"near": "cercana", "far": "lejana"}
STEPS = {
    "fuera_de_camara": "fuera de la cámara principal",
    "sin_seguimiento": "jugadora cercana no seguida (sin tramo)",
    "repeticion": "descartado como repetición",
    "identidad_sin_decidir": "identidad sin decidir",
    "identidad_equivocada": "identidad equivocada",
    "no_candidato": "no es candidato",
    "error": "error al procesar la ventana",
    "lejana_no_encontrada": "jugadora lejana no encontrada en la ventana",
    "sin_ventana": "sin ventana registrada",
    "criba_sin_golpe": "criba «sin golpe» (sin pose)",
    "bola_no_vista": "bola no vista y no confirmado",
    "no_confirmado": "no confirmado (bola vista)",
    "encontrado_dudoso": "encontrado, de identidad dudosa (apartado)",
    "encontrado": "encontrado",
}
FOUND = ("encontrado", "encontrado_dudoso")
LOST = [k for k in STEPS if k not in FOUND]


def stroke_kind(shot: str, hand: str, technique: str) -> str:
    """serve / forehand / backhand / volley_other of an F3Set stroke."""
    if shot == "serve":
        return "serve"
    if technique in ("volley", "smash") or hand not in ("fh", "bh"):
        return "volley_other"
    return "forehand" if hand == "fh" else "backhand"


def player_points(clips: list[dict], player: str) -> list[dict]:
    """The annotated points of the player's matches: one dict per point with every stroke of both
    players (source frames), who hit it (target / opponent), her end and the stroke kind."""
    pl = player.lower()
    out = []
    for c in clips:
        if pl not in (c["near_name"] + c["far_name"]).lower():
            continue
        name, a, b = clip_bounds(c["video"])
        near_is_her = pl in c["near_name"].lower()
        evs = []
        for e in c["events"]:
            g = parse_label(e["frame"], e["label"])
            her = (g.side == "near") == near_is_her
            evs.append({"frame": a + g.frame, "side": g.side, "who": "target" if her else "opponent",
                        "kind": stroke_kind(g.shot, g.hand, g.technique), "shot": g.shot, "technique": g.technique,
                        "label": e["label"]})
        out.append({"id": c["video"], "video": name, "a": a, "b": b, "fps": float(c["fps"]),
                    "near_is_target": near_is_her, "opponent": c["far_name"] if near_is_her else c["near_name"],
                    "events": evs})
    return sorted(out, key=lambda p: (p["video"], p["a"]))


def all_points(clips: list[dict]) -> list[dict]:
    """Every annotated point of every match (training data of tennisbio.spotting): one dict per point with
    its strokes (source frames, end, kind) and the two players' names."""
    out = []
    for c in clips:
        name, a, b = clip_bounds(c["video"])
        evs = []
        for e in c["events"]:
            g = parse_label(e["frame"], e["label"])
            evs.append({"frame": a + g.frame, "side": g.side, "who": "opponent",
                        "kind": stroke_kind(g.shot, g.hand, g.technique), "shot": g.shot, "technique": g.technique,
                        "label": e["label"]})
        out.append({"id": c["video"], "video": name, "a": a, "b": b, "fps": float(c["fps"]), "near_is_target": False,
                    "near_name": c["near_name"], "far_name": c["far_name"], "events": evs})
    return sorted(out, key=lambda p: (p["video"], p["a"]))


def plan_segments(points: list[dict], pre_s: float = 6.0, post_s: float = 3.0, join_gap_s: float = 2.0) -> list[dict]:
    """Seconds of the source video to take for a set of points of ONE video: each point from pre_s
    before its first annotated frame (serve preparation: identity and the split step need it) to post_s
    after its last; overlapping or nearly touching pieces are joined. [{src_t0, src_t1, points: [ids]}]"""
    segs = []
    for p in sorted(points, key=lambda p: p["a"]):
        t0, t1 = max(0.0, p["a"] / p["fps"] - pre_s), p["b"] / p["fps"] + post_s
        if segs and t0 - segs[-1]["src_t1"] <= join_gap_s:
            segs[-1]["src_t1"] = max(segs[-1]["src_t1"], t1)
            segs[-1]["points"].append(p["id"])
        else:
            segs.append({"src_t0": round(t0, 3), "src_t1": round(t1, 3), "points": [p["id"]]})
    return segs


def simulated_pick(points: list[dict], segs: list[dict], min_s: float = 3.0) -> dict | None:
    """The user's identity click (19-10), simulated for the benchmark from the annotations: the middle of
    the first point of at least min_s seconds and who is near there. {"t", "near_is_her", "simulated"}."""
    by_id = {p["id"]: p for p in points}
    for s in segs:
        for pid in s["points"]:
            p = by_id.get(pid)
            if p and (p["b"] - p["a"]) / p["fps"] >= min_s:
                mid = (p["a"] + p["b"]) / 2 / p["fps"]
                return {"t": round(s["offset"] + mid - s["src_t0"], 3), "near_is_her": bool(p["near_is_target"]),
                        "simulated": True}
    return None


def place_events(points: list[dict], segs: list[dict]) -> tuple[list[dict], list[tuple[float, float]]]:
    """Annotated strokes in compilation time (segments with their `offset`: start in the compilation),
    and the annotated spans (first to last frame of each point) in compilation time."""
    by_id = {p["id"]: p for p in points}
    evs, spans = [], []
    for s in segs:
        for pid in s["points"]:
            p = by_id[pid]
            to_c = lambda f: s["offset"] + f / p["fps"] - s["src_t0"]
            spans.append((round(to_c(p["a"]), 3), round(to_c(p["b"]), 3)))
            for e in p["events"]:
                evs.append({**e, "t": round(to_c(e["frame"]), 3), "point": pid})
    return sorted(evs, key=lambda e: e["t"]), spans


@dataclass
class Outputs:
    """What the stages left for one compilation (times in seconds of the compilation)."""
    main_shots: list = field(default_factory=list)        # [(t0, t1)] main camera
    runs: list = field(default_factory=list)              # [{t0, t1, near_is_target, method, replay, ...}]
    cands: list = field(default_factory=list)             # [{t, side, target}]
    windows: list = field(default_factory=list)           # [{t0, dur, side, passed, reason}]
    errors: list = field(default_factory=list)            # [t] candidates whose window failed
    strokes: list = field(default_factory=list)           # [{t, side, stroke}] her confirmed strokes
    doubtful: list = field(default_factory=list)          # [{t, side, stroke}] strokes of undecided identity
    ball_seen: object = None                              # f(window, t) → fraction of frames with the ball, or None
    notes: list = field(default_factory=list)


def _inside(t: float, spans) -> bool:
    return any(a <= t < b for a, b in spans)


def _run_at(runs, t):
    return next((r for r in runs if r["t0"] <= t < r["t1"]), None)


def match_strokes(strokes: list[dict], events: list[dict], tol: float) -> dict:
    """Greedy one-to-one matching of predicted strokes to annotated ones (closest first, ±tol s, same
    end). Returns {event index: stroke index}."""
    pairs = sorted((abs(s["t"] - e["t"]), i, j) for j, s in enumerate(strokes) for i, e in enumerate(events)
                   if abs(s["t"] - e["t"]) <= tol and s.get("side", "near") == e["side"])
    used_e, used_s, out = set(), set(), {}
    for _, i, j in pairs:
        if i not in used_e and j not in used_s:
            used_e.add(i)
            used_s.add(j)
            out[i] = j
    return out


def attribute(events: list[dict], out: Outputs, tol: float = 0.2, cand_tol: float = 0.4) -> list[dict]:
    """The step where each annotated stroke of hers is lost ("encontrado" when found). events: all
    annotated strokes (both players) in compilation time; returns her strokes with "step", the run's
    identity and the matched stroke."""
    from ..impacts import SEEN_NEEDED

    hers = [e for e in events if e["who"] == "target"]
    matched = match_strokes(out.strokes, hers, tol)
    rest = [i for i in range(len(hers)) if i not in matched]
    doubt = {rest[i]: j for i, j in match_strokes(out.doubtful, [hers[k] for k in rest], tol).items()}
    res = []
    for i, e in enumerate(hers):
        t, side = e["t"], e["side"]
        r = _run_at(out.runs, t)
        info = {**e, "run_method": None if r is None else r.get("method"),
                "run_identity": None if r is None else r.get("near_is_target")}
        if r is not None:
            truth = side == "near"
            info["identity_ok"] = None if r.get("near_is_target") is None else r["near_is_target"] == truth
        if i in matched:
            s = out.strokes[matched[i]]
            res.append({**info, "step": "encontrado", "pred_stroke": s.get("stroke"), "dt": round(s["t"] - t, 3)})
            continue
        if i in doubt:
            s = out.doubtful[doubt[i]]
            res.append({**info, "step": "encontrado_dudoso", "pred_stroke": s.get("stroke"), "dt": round(s["t"] - t, 3)})
            continue
        if out.main_shots and not _inside(t, out.main_shots):
            step = "fuera_de_camara"
        elif r is None:
            step = "sin_seguimiento"
        elif r.get("replay"):
            step = "repeticion"
        elif r.get("near_is_target") is None:
            step = "identidad_sin_decidir"
        elif not info["identity_ok"]:
            step = "identidad_equivocada"
        else:
            cs = [c for c in out.cands if c.get("side", "near") == side and abs(c["t"] - t) <= cand_tol and c.get("target")]
            if not cs:
                step = "no_candidato"
            else:
                c = min(cs, key=lambda c: abs(c["t"] - t))
                w = next((w for w in out.windows if w["side"] == side and w["t0"] - 1e-3 <= c["t"] <= w["t0"] + w["dur"] + 1e-3), None)
                if any(abs(x - c["t"]) < 1e-3 for x in out.errors):
                    step = "error"
                elif w is None:
                    step = "lejana_no_encontrada" if side == "far" else "sin_ventana"
                elif not w["passed"]:
                    step = "criba_sin_golpe"
                elif w.get("far_not_found"):
                    step = "lejana_no_encontrada"
                else:
                    f = out.ball_seen(w, t) if out.ball_seen else None
                    step = "bola_no_vista" if f is not None and f < SEEN_NEEDED else "no_confirmado"
                    info["ball_seen"] = None if f is None else round(f, 2)
        res.append({**info, "step": step})
    return res


def _rate(a: int, b: int):
    return None if not b else round(a / b, 3)


def summarize(attr: list[dict], events: list[dict], out_strokes: list[dict], spans: list, tol: float = 0.2,
              runs: list | None = None, point_spans: list | None = None) -> dict:
    """Recall by end, kind and end × kind; the losing step by end and by kind; precision of her strokes
    inside the annotated points; identity of the strokes and of the runs."""
    def rec(rows):
        f = sum(r["step"] == "encontrado" for r in rows)
        d = sum(r["step"] == "encontrado_dudoso" for r in rows)
        return {"gt": len(rows), "found": f, "recall": _rate(f, len(rows)), "found_doubtful": d,
                "recall_any": _rate(f + d, len(rows))}
    s = {"total": rec(attr)}
    s["by_side"] = {k: rec([r for r in attr if r["side"] == k]) for k in SIDES}
    s["by_kind"] = {k: rec([r for r in attr if r["kind"] == k]) for k in KINDS}
    s["by_side_kind"] = {f"{a}/{k}": rec([r for r in attr if r["side"] == a and r["kind"] == k]) for a in SIDES for k in KINDS}
    s["steps"] = {k: sum(r["step"] == k for r in attr) for k in STEPS}
    s["steps_by_side"] = {a: {k: sum(r["step"] == k and r["side"] == a for r in attr) for k in STEPS} for a in SIDES}
    s["steps_by_kind"] = {b: {k: sum(r["step"] == k and r["kind"] == b for r in attr) for k in STEPS} for b in KINDS}
    # precision: her predicted strokes inside the annotated points
    inside = [x for x in out_strokes if any(a - tol <= x["t"] <= b + tol for a, b in spans)]
    hers = [e for e in events if e["who"] == "target"]
    opp = [e for e in events if e["who"] == "opponent"]
    m_her = match_strokes(inside, hers, tol)
    taken = set(m_her.values())
    rest = [x for j, x in enumerate(inside) if j not in taken]
    opp_any = [x for x in rest if any(abs(x["t"] - e["t"]) <= tol for e in opp)]
    s["precision"] = {"predicted_in_points": len(inside), "true": len(taken), "opponent_strokes": len(opp_any),
                      "other": len(rest) - len(opp_any), "precision": _rate(len(taken), len(inside))}
    # stroke kind of the found ones (overhead = serve or smash)
    conf = {}
    for r in attr:
        if r["step"] == "encontrado":
            key = f"{r['kind']}->{r.get('pred_stroke')}"
            conf[key] = conf.get(key, 0) + 1
    s["kind_confusion"] = dict(sorted(conf.items()))
    s["identity"] = identity_summary(attr, runs or [], point_spans or [])
    return s


def identity_summary(attr: list[dict], runs: list[dict], point_spans: list) -> dict:
    """Identity seen from her annotated strokes (run right / wrong / undecided / no run) and from the
    runs that overlap annotated points (each with the truth: is she the near player there?), per cue
    that decided the run (cambios de lado / ropa / conflicto / none)."""
    strokes = {"right": sum(r.get("identity_ok") is True for r in attr),
               "wrong": sum(r.get("identity_ok") is False for r in attr),
               "undecided": sum("identity_ok" in r and r["identity_ok"] is None for r in attr),
               "no_run": sum("identity_ok" not in r for r in attr)}
    strokes["lost_by_identity"] = sum(r["step"] in ("identidad_sin_decidir", "identidad_equivocada") for r in attr)
    by_method = {}
    checked = 0
    for r in runs:
        truth = next((p["near_is_target"] for p in point_spans if p["t0"] < r["t1"] and r["t0"] < p["t1"]), None)
        if truth is None:
            continue
        checked += 1
        m = r.get("method") or "sin decidir"
        d = by_method.setdefault(m, {"runs": 0, "right": 0, "wrong": 0, "undecided": 0, "serve_vote": 0, "return_vote": 0})
        d["runs"] += 1
        d["serve_vote"] += r.get("serve_vote") is not None
        d["return_vote"] += r.get("return_vote") is not None
        if r.get("near_is_target") is None:
            d["undecided"] += 1
        elif r["near_is_target"] == truth:
            d["right"] += 1
        else:
            d["wrong"] += 1
    return {"strokes": strokes, "runs_checked": checked, "runs_by_cue": by_method}


# ---------------------------------------------------------------------------------------------- outputs

WINDOW_RX = re.compile(r"ventana w(\d{9})_(\d+) \((near|far), (\d+) candidatos\): (pasa|descartada sin pose) · (.*)$")
POSE_RX = re.compile(r"ventana w(\d{9})_(\d+): pose ")


def parse_window_log(lines) -> list[dict]:
    """Windows of the fine pass from its log lines (stages._gate_passes): start, duration, end,
    passed or gated and why. A window that passed with no "pose" line after it (far end: the far
    player not found at its start) is marked far_not_found."""
    wins, posed = [], set()
    for ln in lines:
        m = WINDOW_RX.search(ln)
        if m:
            what = m.group(6)
            reason = ("golpe_de_bola" if what.startswith("golpe de bola") else "bola_no_vista" if what.startswith("bola no vista")
                      else "sin_datos_de_bola" if what.startswith("sin datos") else "sin_golpe")
            wins.append({"id": f"w{m.group(1)}_{m.group(2)}", "t0": int(m.group(1)) / 1000, "dur": int(m.group(2)) / 1000,
                         "side": m.group(3), "n": int(m.group(4)), "passed": m.group(5) == "pasa", "reason": reason})
            continue
        m = POSE_RX.search(ln)
        if m:
            posed.add(f"w{m.group(1)}_{m.group(2)}")
    for w in wins:
        if w["passed"] and w["side"] == "far" and w["id"] not in posed:
            w["far_not_found"] = True
    return wins


def replay_runs(d: dict, sk, court: dict, onsets: np.ndarray, score: dict) -> list[bool]:
    """For each run of stages.near_runs, whether st_candidates skips it as a replay (the same rule,
    recomputed from the stage outputs)."""
    from ..court_metrics import to_court
    from ..replays import Run, find_replays
    from ..stages import court_at, near_runs, replay_spans_without_board

    fps, frames = float(d["fps"]), d["frames"]
    no_board = replay_spans_without_board(score)
    runs_all, paths = list(near_runs(d, sk, court)), []
    for run, img, cf, h, _ in runs_all:
        t0, t1 = frames[run[0]] / fps, frames[run[-1]] / fps
        H = court_at(court, t0)[0]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            feet = np.nanmean(img[:, [sk["left_ankle"], sk["right_ankle"]]], axis=1) if H is not None else None
        path = to_court(H, np.nan_to_num(feet, nan=-1e6)) if feet is not None else np.full((len(run), 2), np.nan)
        if feet is not None:
            path[~np.isfinite(feet).all(1)] = np.nan
        paths.append(Run(t0, t1, path, fps, int(np.sum((onsets >= t0) & (onsets <= t1))) if len(onsets) else 0))
    slow = set(find_replays(paths))
    out = []
    for k, (run, *_r) in enumerate(runs_all):
        t_mid = frames[run[len(run) // 2]] / fps
        out.append(bool(no_board and any(a <= t_mid < b for a, b in no_board)) or k in slow)
    return out


def load_outputs(mdir: Path, hand: str = "right", window_log: Path | None = None) -> Outputs:
    """The Outputs of one match folder of the pipeline."""
    from ..skeleton import Skeleton

    rd = lambda n: json.loads((mdir / n).read_text(encoding="utf-8")) if (mdir / n).exists() else None
    o = Outputs()
    sc = rd("scenes.json") or {}
    sf = sc.get("fps") or 1
    o.main_shots = [(s["start"] / sf, s["end"] / sf) for s in sc.get("shots", []) if s.get("main_camera")]
    ident = rd("identity.json") or {}
    from ..identity import PICK_FILE, apply_pick
    if ident and (mdir / PICK_FILE).exists():     # the same runs the candidates stage used
        ident, _ = apply_pick(ident, rd(PICK_FILE))
    ifps = ident.get("fps") or 1
    runs = [{**r, "t0": r["start"] / ifps, "t1": r["end"] / ifps} for r in ident.get("runs", [])]
    if (mdir / "players.npz").exists() and runs:
        with np.load(mdir / "players.npz", allow_pickle=True) as z:
            d = {k: z[k] for k in z.files}
        audio = rd("audio_onsets.json") or {}
        tracks = audio.get("tracks") or [audio]
        tr = (rd("audio_track.json") or {}).get("track", 0)
        onsets = np.array(tracks[tr].get("t", [])) if tracks and tr < len(tracks) else np.zeros(0)
        rep = replay_runs(d, Skeleton("coco17", hand), rd("court.json") or {}, onsets, rd("score.json") or {})
        if len(rep) == len(runs):
            for r, x in zip(runs, rep):
                r["replay"] = x
        else:
            o.notes.append(f"repeticiones: {len(rep)} tramos recalculados frente a {len(runs)} en identity.json")
    o.runs = runs
    o.cands = rd("candidates.json") or []
    o.strokes = [{"t": s["match_time_s"], "side": s.get("side", "near"), "stroke": s.get("stroke")}
                 for s in rd("strokes.json") or []]
    o.doubtful = [{"t": s["match_time_s"], "side": s.get("side", "near"), "stroke": s.get("stroke")}
                  for s in rd("strokes_doubtful.json") or []]
    o.errors = [e["t"] for e in rd("strokes_errores.json") or []]
    log = window_log or mdir / "ventanas_fine.log"
    if log.exists():
        o.windows = parse_window_log(log.read_text(encoding="utf-8").splitlines())
    elif o.cands:
        o.notes.append("sin registro de ventanas de la pasada fina (se vuelve a ejecutar fine para tenerlo)")

    def seen(w, t):
        from ..ball import clean_track
        from ..fine_gate import seen_fraction
        f = next(iter(sorted((mdir / "windows").glob(f"{w['id']}_*_ball.npy"))), None) if (mdir / "windows").exists() else None
        if f is None:
            return None
        tr = np.load(f)
        if not len(tr):
            return None
        fps = len(tr) / w["dur"]
        width = 1280
        clip = mdir / "windows" / f"{w['id']}.mp4"
        if clip.exists():
            from ..io.video import probe
            width = probe(clip).width
        cl = clean_track(np.asarray(tr, float), width=width)
        return seen_fraction(~np.isnan(cl[:, 0]), int(round((t - w["t0"]) * fps)), fps)
    o.ball_seen = seen
    return o


# --------------------------------------------------------------------------------------------- report

def _pct(x):
    return "—" if x is None else f"{x * 100:.0f} %"


def to_markdown(res: dict) -> str:
    """The benchmark for a person (Spanish), short: recall by end and kind, where the strokes are lost."""
    s = res["summary"]
    L = ["# Golpes perdidos: recall frente a F3Set", "",
         f"{s['total']['gt']} golpes anotados de {res['player']} en {res['points']} puntos de {len(res['matches'])} partidos "
         f"(tolerancia ±{res['tol_s']} s). **Encontrados {s['total']['found']} ({_pct(s['total']['recall'])})**"
         + (f" y {s['total']['found_doubtful']} más apartados como de identidad dudosa (con ellos "
            f"{_pct(s['total']['recall_any'])})" if s['total'].get('found_doubtful') else "") + "; "
         f"precisión {_pct(s['precision']['precision'])} ({s['precision']['true']} de {s['precision']['predicted_in_points']} "
         f"golpes suyos dentro de los puntos; {s['precision']['opponent_strokes']} eran golpes de la rival).", "",
         "## Recall por lado y tipo", "", "| | " + " | ".join(KINDS.values()) + " | total |", "|---|" + "---|" * (len(KINDS) + 1)]
    for a, an in SIDES.items():
        cells = [f"{x['found']}/{x['gt']}" for x in (s["by_side_kind"][f"{a}/{k}"] for k in KINDS)]
        L.append(f"| {an} | " + " | ".join(cells) + f" | **{s['by_side'][a]['found']}/{s['by_side'][a]['gt']}** "
                 f"({_pct(s['by_side'][a]['recall'])}) |")
    L += ["", "## Dónde se pierden (primera etapa que falla)", "", "| Etapa | cercana | lejana | total |", "|---|---|---|---|"]
    for k in LOST:
        if s["steps"][k]:
            L.append(f"| {STEPS[k]} | {s['steps_by_side']['near'][k]} | {s['steps_by_side']['far'][k]} | **{s['steps'][k]}** |")
    worst = sorted(((v, k) for k, v in s["steps"].items() if k in LOST and v), reverse=True)
    if worst:
        L += ["", f"Lo que más importa arreglar: **{STEPS[worst[0][1]]}** ({worst[0][0]} golpes perdidos de "
                  f"{s['total']['gt'] - s['total']['found']})."]
    L += ["", "## Por tipo de golpe", "", "| Tipo | recall | etapa principal de pérdida |", "|---|---|---|"]
    for k, kn in KINDS.items():
        st = s["steps_by_kind"][k]
        top = max(LOST, key=lambda x: st[x])
        L.append(f"| {kn} | {s['by_kind'][k]['found']}/{s['by_kind'][k]['gt']} ({_pct(s['by_kind'][k]['recall'])}) | "
                 + (f"{STEPS[top]} ({st[top]})" if st[top] else "—") + " |")
    idn = s["identity"]
    L += ["", "## Identidad", "",
          f"Golpes suyos en un tramo con la identidad bien puesta: {idn['strokes']['right']}; mal puesta: {idn['strokes']['wrong']}; "
          f"sin decidir: {idn['strokes']['undecided']}; sin tramo: {idn['strokes']['no_run']}. "
          f"Perdidos por identidad: {idn['strokes']['lost_by_identity']}.", "",
          f"Tramos de la jugadora cercana dentro de puntos anotados: {idn['runs_checked']}.", "",
          "| Señal que decidió el tramo | tramos | bien | mal | sin decidir | con voto de saque | con voto de resto |",
          "|---|---|---|---|---|---|---|"]
    for m, d in sorted(idn["runs_by_cue"].items()):
        L.append(f"| {m} | {d['runs']} | {d['right']} | {d['wrong']} | {d['undecided']} | {d['serve_vote']} | {d['return_vote']} |")
    for n in res.get("notes", []):
        L.append(f"\n> Nota: {n}")
    L += ["", "Cómo repetirlo: `uv run python scripts/validate_recall.py --root <datasets>` (en el PC: YouTube no deja "
              "descargar desde servidores). Cada arreglo de detección debe subir el recall sin bajar la precisión."]
    return "\n".join(L) + "\n"
