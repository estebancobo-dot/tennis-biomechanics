"""Replays and the other cameras of the broadcast, used and linked to the live stroke they show
(#218, docs/plan_maestro.md block 2: «the source are the matches»).

Until now replays of the main camera were only found to be dropped (tennisbio.replays, the
candidates stage) and every other camera (side, front, close-ups) was thrown away by the scenes
stage. Here every stretch of the broadcast that is not live play becomes a *view*:

- ``repeticion_principal``: the main camera again (scoreboard gone, or her feet retracing a path of the
  last 90 s more slowly or without impact sounds: the same rules as the candidates stage, untouched);
- ``lateral``: the court seen from a side (long, near-horizontal lines; no converging sidelines);
- ``frontal``: the court seen from an end but from another camera (converging sidelines, lower camera
  than the main one, or not the main camera's look);
- ``primer_plano``: a person fills the frame;
- ``otra``: anything else (crowd, graphics, the bench): kept with its evidence, never linked.

Each view (but ``otra``) is linked to the live stroke(s) it shows:

- a main-camera replay whose feet path matches a live run: by that path. Slow-motion factor =
  replay duration / live duration of the same stretch of path (2 = twice slower), checked against
  the ratio of the feet speeds; the instant of each impact inside the replay follows from it;
- any other view: by time order (the block of replays after a point shows that point) and by the
  number of impacts heard in it (n impacts → the last n strokes of the point; none → its last stroke).

Nothing is invented: a view without a point before it in the last 90 s (or with live play of
another point in between) is kept unlinked. All the rules work on what the cheap pass already
produced (scenes.json, court.json, players.npz, score.json, the audio onsets); the stage only
samples 1-3 frames of the shots that need it (people size, lines, camera tilt).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .replays import Run, find_replays, matches, path_speed

KINDS = ("repeticion_principal", "lateral", "frontal", "primer_plano", "otra")
LABELS = {"repeticion_principal": "Repetición (cámara principal)", "lateral": "Cámara lateral",
          "frontal": "Cámara frontal", "primer_plano": "Primer plano", "otra": "Otra toma"}
OTHER_CAMERAS = ("lateral", "frontal", "primer_plano")

WINDOW_S = 90.0          # a replay follows its live point within this time (as tennisbio.replays)
POINT_GAP_S = 8.0        # live strokes closer than this belong to the same rally
LIVE_SHARE = 0.5         # a main-camera shot is live play when this share of its frames has the court
MIN_SHOT_S = 0.4         # shorter shots (flashes, wipes between shots) are not views
OTHER_PLAY_S = 12.0      # live play longer than this after a point's last stroke (+2 s) and before a view:
#                          another point (its strokes not found) came in between → the view stays unlinked
CLOSEUP_H = 0.45         # tallest person / frame height at or above this: a close-up
MIN_COURT = 0.25         # court colour share (scenes.court_fraction) of a frame that shows the court
LATERAL_HORIZ = 0.6      # share of the long lines' length that is near-horizontal (≤ 12°) in a side view
HORIZ_DEG = 12.0
MIN_LONG_LINES = 2       # long straight lines (≥ 20 % of the width) needed to judge their direction
PITCH_TOL = 8.0          # degrees: a fitted court this much below the main camera's tilt is another camera
NORMAL_SPEED = (0.8, 1.25)   # slow-motion factor in this range: a replay at normal speed
FACTOR_AGREE = 0.35      # duration ratio and speed ratio agree within this relative difference
STROKE_TOL_S = 0.5       # a link's live time and a stroke's match time: the same stroke


# --- evidence of a shot -----------------------------------------------------------------------------
def frame_evidence(frame: np.ndarray, people_h: float | None = None) -> dict:
    """What one sampled frame shows: court seen from an end (0-2, scenes.court_line_evidence), the long
    straight lines and the share of their length that is near-horizontal, and the tallest person's
    height / frame height when a detector gave it. The frame is shrunk to 160 px wide, as in scenes."""
    import cv2

    from .scenes import _line_segments, court_line_evidence

    h, w = frame.shape[:2]
    small = cv2.resize(frame, (160, max(1, round(160 * h / w))), interpolation=cv2.INTER_AREA) if w != 160 else frame
    segs, _ = _line_segments(small)
    sw = small.shape[1]
    ln = np.hypot(segs[:, 2] - segs[:, 0], segs[:, 3] - segs[:, 1]) if len(segs) else np.zeros(0)
    long_ = ln >= 0.2 * sw
    ang = np.degrees(np.arctan2(np.abs(segs[:, 3] - segs[:, 1]), np.abs(segs[:, 2] - segs[:, 0]))) if len(segs) else np.zeros(0)
    tot = float(ln[long_].sum())
    horiz = float(ln[long_ & (ang <= HORIZ_DEG)].sum() / tot) if tot > 0 else None
    return {"lines_behind": int(court_line_evidence(small)), "long_lines": int(long_.sum()),
            "horiz_share": None if horiz is None else round(horiz, 3),
            "people_h": None if people_h is None else round(float(people_h), 3)}


def merge_evidence(samples: list[dict]) -> dict:
    """One shot from its sampled frames: the most court seen from an end, the median line layout, the
    tallest person, the median camera tilt of the fitted courts."""
    if not samples:
        return {"sampled": 0}
    vals = lambda k: [s[k] for s in samples if s.get(k) is not None]
    out = {"sampled": len(samples), "lines_behind": max(vals("lines_behind"), default=0),
           "long_lines": int(np.median(vals("long_lines"))) if vals("long_lines") else 0}
    hz, ph, pt = vals("horiz_share"), vals("people_h"), vals("pitch_deg")
    out["horiz_share"] = round(float(np.median(hz)), 3) if hz else None
    out["people_h"] = round(float(max(ph)), 3) if ph else None
    out["pitch_deg"] = round(float(np.median(pt)), 1) if pt else None
    return out


def classify(ev: dict, main_pitch: float | None) -> tuple[str, float, str]:
    """(kind, confidence 0-1, rule) of a non-live stretch from its evidence:

    replay reasons (sin_marcador / recorrido) → repeticion_principal; tallest person ≥ CLOSEUP_H of the
    frame → primer_plano; court seen from an end (converging sidelines): a fitted court tilted ≥
    PITCH_TOL below the main camera → frontal, as tilted as the main camera → repeticion_principal (its
    court was not found by the court stage), no tilt → frontal (low confidence); court colour ≥ MIN_COURT
    with mostly horizontal long lines → lateral; court colour with people smaller than a close-up and no
    end view → lateral (low confidence); the rest → otra."""
    reasons = ev.get("replay") or []
    if reasons:
        return "repeticion_principal", (0.9 if "recorrido" in reasons else 0.7), "+".join(reasons)
    ph = ev.get("people_h")
    if ph is not None and ph >= CLOSEUP_H:
        return "primer_plano", 0.8, f"persona de {ph:.0%} de la altura de la imagen"
    court = float(ev.get("court_fraction") or 0.0)
    pitch = ev.get("pitch_deg")
    if (ev.get("lines_behind") or 0) >= 1:
        if pitch is not None and main_pitch is not None:
            if pitch < main_pitch - PITCH_TOL:
                return "frontal", 0.7, f"pista desde un fondo, cámara más baja ({pitch:.0f}° frente a {main_pitch:.0f}°)"
            if abs(pitch - main_pitch) <= PITCH_TOL:
                return "repeticion_principal", 0.5, f"vista de la cámara principal ({pitch:.0f}°) fuera del juego"
        return "frontal", 0.4, "pista desde un fondo, no es la vista principal"
    hz = ev.get("horiz_share")
    if court >= MIN_COURT and hz is not None and hz >= LATERAL_HORIZ and (ev.get("long_lines") or 0) >= MIN_LONG_LINES:
        return "lateral", 0.7, f"pista de lado ({hz:.0%} de las líneas largas horizontales)"
    if court >= MIN_COURT and ph is not None and ph < CLOSEUP_H:
        return "lateral", 0.4, "pista visible sin vista desde un fondo"
    return "otra", 0.3, "sin pista ni persona en primer plano"


# --- main-camera replays linked by her feet path ----------------------------------------------------
def _moving(p: np.ndarray, trim_m: float = 0.2) -> np.ndarray:
    """Indices of the points of a path (finite points only) between the first and the last trim_m metres
    of its length: standing still before and after the movement is left out (its nearest live point is
    ambiguous, and the replay often holds it longer)."""
    ok = np.flatnonzero(np.isfinite(p).all(1))
    if len(ok) < 2:
        return ok
    cum = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(p[ok], axis=0), axis=1))]
    keep = (cum >= min(trim_m, cum[-1] / 4)) & (cum <= cum[-1] - min(trim_m, cum[-1] / 4))
    return ok[keep] if keep.sum() >= 2 else ok


def slowmo_factor(replay: Run, live: Run) -> dict | None:
    """Slow-motion factor of a replay against the live run it retraces: replay duration / live duration
    of the same stretch of path (the replay's moving points → their nearest live points; the live
    stretch runs from the first to the last of those), checked against the ratio of the feet speeds
    (replays.path_speed). 2 = twice slower than live. {factor, by_duration, by_speed, agree, live_t0,
    live_t1, replay_t0} or None without enough points."""
    rp, lp = np.asarray(replay.path, float), np.asarray(live.path, float)
    ri = _moving(rp)
    li = np.flatnonzero(np.isfinite(lp).all(1))
    if len(ri) < 5 or len(li) < 10:
        return None
    near = li[np.argmin(np.linalg.norm(rp[ri][:, None, :] - lp[li][None, :, :], axis=2), axis=1)]
    j0, j1 = int(near.min()), int(near.max())
    dur_l = (j1 - j0 + 1) / live.fps
    dur_r = (ri[-1] - ri[0] + 1) / replay.fps
    by_dur = dur_r / dur_l if j1 > j0 else None
    v_r, v_l = path_speed(rp[ri[0]:ri[-1] + 1], replay.fps), path_speed(lp[j0:j1 + 1], live.fps)
    by_speed = v_l / v_r if v_r > 0 and v_l > 0 else None
    if by_dur is None and by_speed is None:
        return None
    agree = by_dur is not None and by_speed is not None and abs(by_dur - by_speed) <= FACTOR_AGREE * max(by_dur, by_speed)
    if by_dur is None:
        factor = by_speed
    elif by_speed is not None and not agree:
        factor = math.sqrt(by_dur * by_speed)
    else:
        factor = by_dur
    return {"factor": round(float(factor), 2), "by_duration": None if by_dur is None else round(float(by_dur), 2),
            "by_speed": None if by_speed is None else round(float(by_speed), 2), "agree": bool(agree),
            "live_t0": live.t0 + j0 / live.fps, "live_t1": live.t0 + j1 / live.fps,
            "replay_t0": replay.t0 + ri[0] / replay.fps}


def live_match(i: int, runs: list[Run], replays: set[int], window_s: float = WINDOW_S) -> int | None:
    """The live run (not a replay) of the last window_s seconds whose path run i retraces; the latest."""
    r = runs[i]
    for k in range(i - 1, -1, -1):
        e = runs[k]
        if k in replays or not (0 <= r.t0 - e.t1 <= window_s):
            continue
        if matches(r, e):
            return k
    return None


def speed_label(factor: float | None) -> str | None:
    if factor is None:
        return None
    return "normal" if NORMAL_SPEED[0] <= factor <= NORMAL_SPEED[1] else ("lenta" if factor > NORMAL_SPEED[1] else "rapida")


# --- stretches of the broadcast ---------------------------------------------------------------------
@dataclass
class View:
    t0: float
    t1: float
    source: str                      # "run" (a replay run of the players stage), "marcador", "plano"
    shot: int | None = None          # index in scenes.json shots
    evidence: dict = field(default_factory=dict)
    run: int | None = None
    kind: str = "otra"
    confidence: float = 0.0
    rule: str = ""
    links: list = field(default_factory=list)


def _spans(mask: np.ndarray, fps: float) -> list[tuple[float, float]]:
    e = np.flatnonzero(np.diff(np.r_[0, mask.astype(int), 0]))
    return [(a / fps, b / fps) for a, b in zip(e[::2], e[1::2])]


def court_play_mask(scenes: dict, court: dict | None) -> np.ndarray:
    """Frames (scenes fps) of main camera with the court found (as stages.play_mask; without court.json
    nothing is play: every shot is then a view to classify)."""
    n = max([s["end"] for s in scenes.get("shots", [])] + [0])
    m = np.zeros(n, bool)
    if not court:
        return m
    main = np.zeros(n, bool)
    for s in scenes["shots"]:
        main[s["start"]:s["end"]] = s.get("main_camera", False)
    for o in court.get("shots", []):
        if o.get("H") is not None:
            m[o["start"]:min(o["end"], n)] = True
    return m & main


def main_pitch_of(court: dict | None) -> float | None:
    """Tilt of the main camera: the median over the court segments, weighted by their length."""
    segs = [o for o in (court or {}).get("shots", []) if o.get("H") is not None and o.get("pitch_deg") is not None]
    if not segs:
        return None
    w = np.array([o["end"] - o["start"] for o in segs], float)
    p = np.array([o["pitch_deg"] for o in segs], float)
    order = np.argsort(p)
    c = np.cumsum(w[order])
    return float(p[order][np.searchsorted(c, c[-1] / 2)])


def views_to_sample(scenes: dict, court: dict | None, replay_spans: list[tuple[float, float]] = ()) -> list[int]:
    """Indices of the scenes shots that are not live play (nor a main-camera replay already found):
    the only ones whose frames are sampled."""
    fps = float(scenes.get("fps") or 1.0)
    play = court_play_mask(scenes, court)
    out = []
    for i, s in enumerate(scenes.get("shots", [])):
        if (s["end"] - s["start"]) / fps < MIN_SHOT_S:
            continue
        share = play[s["start"]:s["end"]].mean() if s["end"] > s["start"] else 0.0
        if s.get("main_camera") and share >= LIVE_SHARE:
            continue
        t0, t1 = s["start"] / fps, s["end"] / fps
        if any(a <= (t0 + t1) / 2 < b for a, b in replay_spans):
            continue
        out.append(i)
    return out


def sample_times(scenes: dict, i: int, n_max: int = 3, every_s: float = 2.0) -> list[float]:
    """1 to n_max times inside shot i (its middle; more for long shots), away from its edges."""
    fps = float(scenes.get("fps") or 1.0)
    s = scenes["shots"][i]
    t0, t1 = s["start"] / fps, s["end"] / fps
    n = int(np.clip((t1 - t0) // every_s, 1, n_max))
    return [float(t0 + (t1 - t0) * (k + 1) / (n + 1)) for k in range(n)]


# --- links to live strokes --------------------------------------------------------------------------
def _point_before(t: float, strokes: list[dict], window_s: float = WINDOW_S, gap_s: float = POINT_GAP_S) -> list[dict]:
    """The last rally before time t (within window_s): live strokes at most gap_s apart, in order."""
    before = sorted((s for s in strokes if s["t"] <= t and t - s["t"] <= window_s), key=lambda s: s["t"])
    if not before:
        return []
    pt = [before[-1]]
    for s in reversed(before[:-1]):
        if pt[0]["t"] - s["t"] > gap_s:
            break
        pt.insert(0, s)
    return pt


def _live_between(a: float, b: float, live: list[tuple[float, float]]) -> float:
    return sum(max(0.0, min(b, y) - max(a, x)) for x, y in live)


def link_by_order(v: View, strokes: list[dict], live: list[tuple[float, float]], hits: int) -> list[dict]:
    """Links of a view to the point just before it (the replay block after a point shows that point):
    with n impacts heard, its last n strokes; with none, its last stroke. No point in the last 90 s, or
    more than OTHER_PLAY_S of live play after it (another point whose strokes were not found): none."""
    pt = _point_before(v.t0, strokes)
    if not pt or _live_between(pt[-1]["t"] + 2.0, v.t0, live) > OTHER_PLAY_S:
        return []
    shown = pt[-max(1, min(hits, len(pt))):]
    if v.kind == "primer_plano":
        conf = 0.3
    elif hits == 0:
        conf = 0.4
    else:
        conf = 0.6 if hits <= len(pt) else 0.5
    return [{"live_t": round(s["t"], 3), "side": s.get("side"), "method": "orden", "hits_heard": hits,
             "point_strokes": len(pt), "confidence": conf} for s in shown]


def link_by_path(v: View, runs: list[Run], k_live: int, strokes: list[dict]) -> list[dict]:
    """Links of a main-camera replay run to the strokes of the live stretch whose path it retraces, with
    the slow-motion factor and the instant of each impact inside the replay."""
    r, e = runs[v.run], runs[k_live]
    f = slowmo_factor(r, e)
    if f is None:
        return []
    a, b = f["live_t0"], f["live_t1"]
    shown = [s for s in strokes if a - 0.3 <= s["t"] <= b + 0.3] or [s for s in strokes if e.t0 - 0.3 <= s["t"] <= e.t1 + 0.3]
    conf = 0.9 if f["agree"] else 0.7
    out = []
    for s in sorted(shown, key=lambda s: s["t"]):
        t_rep = f["replay_t0"] + (s["t"] - a) * f["factor"]
        out.append({"live_t": round(s["t"], 3), "side": s.get("side"), "method": "recorrido", "slowmo": f["factor"],
                    "speed": speed_label(f["factor"]), "slowmo_by_duration": f["by_duration"],
                    "slowmo_by_speed": f["by_speed"], "confidence": conf,
                    "impact_t_in_replay": round(t_rep, 3) if v.t0 - 0.5 <= t_rep <= v.t1 + 0.5 else None})
    if not out:      # her path matched but no stroke was found live: the link to the live stretch stays
        out.append({"live_t": None, "live_span": [round(e.t0, 3), round(e.t1, 3)], "side": "near", "method": "recorrido",
                    "slowmo": f["factor"], "speed": speed_label(f["factor"]), "slowmo_by_duration": f["by_duration"],
                    "slowmo_by_speed": f["by_speed"], "confidence": 0.5, "impact_t_in_replay": None})
    return out


def build_views(scenes: dict, court: dict | None, runs: list[Run], no_board: list[tuple[float, float]],
                onsets: np.ndarray, strokes: list[dict], evidence: dict[int, dict] | None = None) -> dict:
    """views.json: every non-live stretch with its kind and evidence, and its links to the live strokes.

    scenes, court: the stages' outputs (court None: no court found anywhere); runs: her runs on the
    main camera with her feet path (stages._near_paths, as in the candidates stage); no_board: the
    replay spans without scoreboard (stages.replay_spans_without_board); onsets: impact sounds (s);
    strokes: live strokes, each {"t", "side"} (candidates.json); evidence: sampled evidence per scenes
    shot index (merge_evidence), for the shots of views_to_sample."""
    evidence = evidence or {}
    fps = float(scenes.get("fps") or 1.0)
    shots = scenes.get("shots", [])
    onsets = np.asarray(onsets, float).ravel()
    main_pitch = main_pitch_of(court)
    # 1) main-camera replays, by the same rules as the candidates stage (whose output does not change)
    by_path = set(find_replays(runs)) if runs else set()
    views: list[View] = []
    for i, r in enumerate(runs):
        mid = (r.t0 + r.t1) / 2
        reasons = (["sin_marcador"] if any(a <= mid < b for a, b in no_board) else [])
        if i in by_path:
            reasons.append("recorrido")
        if not reasons:
            continue
        v = View(r.t0, r.t1, "run", run=i, evidence={"replay": reasons, "impacts_heard": r.impacts})
        views.append(v)
    covered = [(v.t0, v.t1) for v in views]
    for a, b in no_board:                     # replays without scoreboard where she was not tracked
        if (b - a) >= MIN_SHOT_S and not any(x < b and a < y for x, y in covered):
            views.append(View(a, b, "marcador", evidence={"replay": ["sin_marcador"]}))
    # 2) every other non-live shot, by its evidence
    for i in views_to_sample(scenes, court, list(no_board) + covered):
        s = shots[i]
        ev = {"main_camera": bool(s.get("main_camera")), "court_fraction": s.get("court_fraction"),
              "court_lines": s.get("court_lines"), "main_view": s.get("main_view"), **evidence.get(i, {"sampled": 0})}
        views.append(View(s["start"] / fps, s["end"] / fps, "plano", shot=i, evidence=ev))
    views.sort(key=lambda v: v.t0)
    for v in views:
        if v.shot is None:                    # the scenes shot that holds it, for the evidence
            mid = (v.t0 + v.t1) / 2 * fps
            v.shot = next((k for k, s in enumerate(shots) if s["start"] <= mid < s["end"]), None)
        v.kind, v.confidence, v.rule = classify(v.evidence, main_pitch)
    # 3) links
    play = court_play_mask(scenes, court)
    for v in views:                           # live play = play frames that are not a replay
        if v.kind == "repeticion_principal":
            play[max(0, int(v.t0 * fps)):int(math.ceil(v.t1 * fps))] = False
    live = _spans(play, fps)
    strokes = [s for s in strokes if s.get("t") is not None]
    replays_idx = {v.run for v in views if v.run is not None}
    for v in views:
        if v.kind == "otra":
            continue
        hits = int(np.sum((onsets >= v.t0) & (onsets <= v.t1))) if len(onsets) else 0
        v.evidence.setdefault("impacts_heard", hits)
        if v.run is not None:
            k = live_match(v.run, runs, replays_idx)
            if k is not None:
                v.links = link_by_path(v, runs, k, strokes)
                if v.links:
                    continue
        v.links = link_by_order(v, strokes, live, hits)
    out_views, links = [], []
    for v in views:
        d = {"t0": round(v.t0, 3), "t1": round(v.t1, 3), "kind": v.kind, "label": LABELS[v.kind],
             "confidence": v.confidence, "rule": v.rule, "source": v.source, "shot": v.shot,
             "evidence": v.evidence, "links": v.links}
        out_views.append(d)
        for ln in v.links:
            links.append({**ln, "shot_span": [d["t0"], d["t1"]], "kind": v.kind,
                          "confidence": round(min(ln["confidence"], max(v.confidence, 0.3)), 2)})
    by_kind = {k: sum(v.kind == k for v in views) for k in KINDS}
    return {"version": 1, "fps": fps, "main_pitch_deg": main_pitch, "views": out_views, "links": links,
            "summary": {"views": len(views), **by_kind, "links": len(links),
                        "linked_views": sum(bool(v.links) for v in views),
                        "slowmo_links": sum(1 for ln in links if (ln.get("slowmo") or 0) > NORMAL_SPEED[1])}}


# --- strokes.json -------------------------------------------------------------------------------------
def attach(strokes: list[dict], doc: dict | None, tol_s: float = STROKE_TOL_S) -> list[dict]:
    """The strokes with an optional `views` list (the replays and other cameras that show each one) and,
    when one of them is a main-camera slow-motion replay, `slowmo_view: true`. The other fields are not
    touched; a stroke without views gets neither key (a previous `views`/`slowmo_view` is replaced)."""
    out = []
    links = [ln for ln in (doc or {}).get("links", []) if ln.get("live_t") is not None]
    times = np.array([s.get("match_time_s", np.nan) for s in strokes], float)
    per: dict[int, list] = {}
    for ln in links:
        if not len(times):
            break
        side = ln.get("side")
        d = np.abs(times - ln["live_t"])
        if side is not None:
            d = np.where([s.get("side", "near") == side for s in strokes], d, np.inf)
        k = int(np.nanargmin(np.where(np.isfinite(d), d, np.inf))) if np.isfinite(d).any() else -1
        if k >= 0 and d[k] <= tol_s:
            per.setdefault(k, []).append({"kind": ln["kind"], "label": LABELS[ln["kind"]], "t0": ln["shot_span"][0],
                                          "t1": ln["shot_span"][1], "slowmo": ln.get("slowmo"), "speed": ln.get("speed"),
                                          "impact_t": ln.get("impact_t_in_replay"), "method": ln["method"],
                                          "confidence": ln["confidence"]})
    for k, s in enumerate(strokes):
        s = {kk: vv for kk, vv in s.items() if kk not in ("views", "slowmo_view")}
        if k in per:
            s["views"] = sorted(per[k], key=lambda x: x["t0"])
            if any(x["kind"] == "repeticion_principal" and (x["slowmo"] or 0) > NORMAL_SPEED[1] for x in per[k]):
                s["slowmo_view"] = True
        out.append(s)
    return out


def coverage(strokes: list[dict]) -> dict:
    """Strokes with a linked replay of the main camera and with another camera (counts and shares)."""
    n = len(strokes)
    rep = sum(any(v["kind"] == "repeticion_principal" for v in s.get("views") or []) for s in strokes)
    oth = sum(any(v["kind"] in OTHER_CAMERAS for v in s.get("views") or []) for s in strokes)
    slow = sum(bool(s.get("slowmo_view")) for s in strokes)
    return {"strokes": n, "with_replay": rep, "with_other_camera": oth, "with_slowmo": slow,
            "replay_share": round(rep / n, 3) if n else 0.0, "other_share": round(oth / n, 3) if n else 0.0}


# --- clips of the views, for the report (#218, 09-11) ------------------------------------------------------
CLIP_DIR = "view_clips"          # beside windows/ in the match folder (match_files.at)
CLIP_PRE_S = 1.0                 # live seconds before her impact kept in a clip whose impact instant is known
CLIP_POST_S = 0.8                # ... and after (× the slow-motion factor inside the replay)
CLIP_MAX_S = 10.0                # a view without a known instant: the shot from its start, at most this long
CLIP_WIDTH = 1280                # clips for watching (the report), not for measuring: lighter than the windows
CLIP_CRF = 23


def clip_settings(cfg: dict) -> dict:
    """`views.clips` of the configuration with its defaults (the view_clips stage's fingerprint)."""
    c = ((cfg or {}).get("views") or {}).get("clips") or {}
    return {"enabled": bool(c.get("enabled", True)), "pre_s": float(c.get("pre_s", CLIP_PRE_S)),
            "post_s": float(c.get("post_s", CLIP_POST_S)), "max_s": float(c.get("max_s", CLIP_MAX_S)),
            "width": int(c.get("width", CLIP_WIDTH)), "crf": int(c.get("crf", CLIP_CRF))}


def stroke_key(s: dict) -> str | None:
    """The key that joins a stroke of strokes.json with its clips and its slow-motion measures: side and match
    time (both stay the same when the fine pass runs again)."""
    t = s.get("match_time_s")
    if t is None:
        return None
    return f"{s.get('side') or 'near'}@{float(t):.3f}"


def clip_spec(view: dict, st: dict | None = None) -> dict | None:
    """Where the clip of one linked view of a stroke is cut (match seconds) and where her impact falls in it.

    With the impact instant inside the replay (a main-camera replay linked by her feet path): from pre_s live
    seconds before to post_s after it, times the slow-motion factor, inside the shot. Otherwise (linked by
    order: the instant is not known): the shot from its start, at most max_s; impact_in_clip None.
    {t0, dur, impact_in_clip, whole_shot, file} or None for a view too short to show."""
    st = st or clip_settings({})
    a, b = float(view["t0"]), float(view["t1"])
    it = view.get("impact_t")
    if it is not None and a - 0.5 <= it <= b + 0.5:
        f = float(view.get("slowmo") or 1.0)
        t0, t1 = max(a, it - st["pre_s"] * f), min(b, it + st["post_s"] * f)
        imp, whole = round(float(it) - t0, 3), False
    else:
        t0, t1, imp, whole = a, min(b, a + st["max_s"]), None, b - a <= st["max_s"]
    if t1 - t0 < MIN_SHOT_S:
        return None
    t0, dur = round(t0, 3), round(t1 - t0, 3)
    return {"t0": t0, "dur": dur, "impact_in_clip": imp if imp is None or 0 <= imp <= dur else None,
            "whole_shot": bool(whole), "file": f"v{int(round(t0 * 1000)):09d}_{int(round(dur * 1000)):05d}.mp4"}


def clip_plan(strokes: list[dict], st: dict | None = None) -> list[dict]:
    """One row per linked view of each stroke (strokes.json `views`), with the clip that shows it. Strokes shown
    by the same view at nearby instants share a clip file only when it is exactly the same cut."""
    out = []
    for s in strokes:
        key = stroke_key(s)
        if key is None:
            continue
        for v in s.get("views") or []:
            c = clip_spec(v, st)
            if c is None:
                continue
            out.append({"key": key, "stroke_id": s.get("stroke_id"), "stroke": s.get("stroke"), "side": s.get("side") or "near",
                        "view_t0": v["t0"], "view_t1": v["t1"], "kind": v["kind"], "label": v.get("label") or LABELS.get(v["kind"], ""),
                        "speed": v.get("speed"), "slowmo": v.get("slowmo"), "method": v.get("method"),
                        "confidence": v.get("confidence"), **{k: c[k] for k in ("file", "impact_in_clip", "whole_shot")},
                        "clip_t0": c["t0"], "clip_dur": c["dur"]})
    return out


def cut_view_clip(video, t0: float, dur: float, dest, interlaced: bool = False, audio_track: int = 0,
                  width: int = 0, max_width: int = CLIP_WIDTH, crf: int = CLIP_CRF, timeout: int = 300):
    """A short clip of the broadcast for the report: re-encoded (H.264, yuv420p: what every browser plays), at most
    max_width wide, deinterlaced one frame per frame (yadif) when the source is interlaced, the chosen audio track.
    Written through a temporary file and checked, so an interrupted cut is never reused. Returns dest."""
    import os
    import subprocess
    from pathlib import Path

    from .io.video import probe

    dest = Path(dest)

    def valid(p) -> bool:
        try:
            return probe(p).duration > 0.2
        except Exception:                        # noqa: BLE001 — unreadable: not valid
            return False

    if dest.exists() and valid(dest):
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.stem + ".part" + dest.suffix)
    filters = ["yadif=0"] if interlaced else []
    if width and width > max_width:
        filters.append(f"scale={max_width}:-2")
    vf = ["-vf", ",".join(filters)] if filters else []
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, t0):.3f}", "-i", str(video), "-t", f"{dur:.3f}",
                        "-map", "0:v:0", "-map", f"0:a:{audio_track}?", *vf, "-c:v", "libx264", "-crf", str(int(crf)),
                        "-preset", "veryfast", "-g", "12", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                        "-c:a", "aac", "-ac", "2", "-b:a", "96k", str(tmp)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    if r.returncode != 0 or not valid(tmp):
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"no se pudo recortar la toma de {dur:.1f} s en {t0:.1f} s ({(r.stderr or '').strip()[-200:]})")
    os.replace(tmp, dest)
    return dest


# --- the fine pass on the slow-motion replay (#218, 09-11) ---------------------------------------------------
SLOWMO_HALF_S = 0.4      # live seconds either side of her impact cut from the slow-motion replay (× the factor)
SLOWMO_SEARCH_S = 0.12   # live seconds either side of the mapped instant where the wrist's speed peak is the impact
MIN_SLOWMO = NORMAL_SPEED[1]     # a replay slower than this is «a cámara lenta»
# what the slow-motion replay measures, beside the live value of the same name (strokes.json `metrics` / `racket`)
SLOWMO_MEASURES = {"elbow_impact_deg": ("Codo en el impacto", "°", ("metrics", "elbow_impact_deg")),
                   "contact_height_pct": ("Altura de la mano en el impacto", "% de su altura", ("metrics", "contact_height_pct")),
                   "contact_lateral_pct": ("Mano separada de la cadera", "% de su altura", ("metrics", "contact_lateral_pct")),
                   "racket_elevation_deg": ("Raqueta en el impacto (inclinación)", "°", ("racket", "impact", "elevation_deg")),
                   "racket_head_above_wrist_cm": ("Cabeza de la raqueta sobre la mano", "cm", ("racket", "impact", "head_above_wrist_cm"))}


def slowmo_settings(cfg: dict) -> dict:
    """`views.fine_on_slowmo` (on/off) and its parameters (the slowmo_fine stage's fingerprint). The models are those
    of the fine pass (fine_pass.pose_model, racket_face.pose_onnx)."""
    v = (cfg or {}).get("views") or {}
    on = v.get("fine_on_slowmo", True)
    on = bool(on.get("enabled", True)) if isinstance(on, dict) else bool(on)
    return {"enabled": on, "half_s": float(v.get("slowmo_half_s", SLOWMO_HALF_S)),
            "racket": bool(v.get("slowmo_racket", True)), "imgsz": int((cfg or {}).get("fine_imgsz", 960)),
            "pose_model": ((cfg or {}).get("fine_pass") or {}).get("pose_model", "yolo")}


def slowmo_view(stroke: dict) -> dict | None:
    """The slowest main-camera replay of a stroke with her impact instant inside it, or None."""
    vs = [v for v in stroke.get("views") or [] if v.get("kind") == "repeticion_principal"
          and (v.get("slowmo") or 0) > MIN_SLOWMO and v.get("impact_t") is not None]
    return max(vs, key=lambda v: v["slowmo"]) if vs else None


def _live_value(stroke: dict, path: tuple):
    v = stroke
    for k in path:
        v = v.get(k) if isinstance(v, dict) else None
    return None if v is None else float(v)


def _racket_at(video, frames: list[int], wrist: np.ndarray, height_px: float, height_m: float, racket) -> dict:
    """Racket of the 5-point model (RacketVision: 0 tip, 1 throat, 2 handle, 3-4 sides) on a few frames of the
    replay, in a box around her dominant wrist: elevation of handle → head centre (as racket.RacketObs, + head
    above the handle) and the head's height above the wrist in cm. Medians over the frames read; {} without any."""
    import cv2

    from .io.video import open_capture

    cap = open_capture(video)
    els, abv = [], []
    try:
        for f in frames:
            if not np.isfinite(wrist[f]).all():
                continue
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(f))
            ok, fr = cap.read()
            if not ok:
                continue
            half = 0.45 * height_px
            box = np.array([wrist[f][0] - half, wrist[f][1] - half, wrist[f][0] + half, wrist[f][1] + half], float)
            kp, sc = racket(fr, box[None])
            if not len(kp) or np.mean(sc[0]) < 0.3:
                continue
            head = kp[0][[0, 1, 3, 4]].mean(0)
            d = head - kp[0][2]
            els.append(float(np.degrees(np.arctan2(-d[1], abs(d[0])))))
            abv.append(float((wrist[f][1] - head[1]) / height_px * height_m * 100))
    finally:
        cap.release()
    if not els:
        return {}
    return {"racket_elevation_deg": round(float(np.median(els)), 1), "racket_head_above_wrist_cm": round(float(np.median(abv)), 1),
            "racket_frames": len(els)}


def slowmo_measures(run, guess: int, factor: float, search_s: float = SLOWMO_SEARCH_S) -> dict | None:
    """Her arm at the impact in the slow-motion replay, from the pose of the replay clip (clip_pipeline.ClipRun):
    the impact is the dominant wrist's speed peak (relative to her body) within ±search_s live seconds of the instant
    mapped from the live impact (`guess`, a frame of the clip), else that instant; each value is the median of the
    impact frame and its two neighbours (in slow motion they are 1/factor as far apart in real time). The same
    definitions as the live stroke (stroke_analysis): elbow angle, hand height above the lower foot and hand to
    the side of the hips, in % of her height. None when she is not seen at the impact."""
    from .kinematics import joint_angle, speed, to_body_frame

    sk, img = run.sk, np.asarray(run.img, float)
    T = len(img)
    if T == 0 or not (0 <= guess < T):
        return None
    h = run.height_t if run.height_t is not None and np.isfinite(run.height_t).any() else run.height_px
    if not np.isfinite(np.nanmean(np.asarray(h, float))):
        return None
    with np.errstate(invalid="ignore", divide="ignore"):
        body = to_body_frame(img, sk, h)
        dw = sk["dom_wrist"]
        v = np.asarray(speed(body[:, dw], run.fps), float)
        r = max(1, int(round(search_s * factor * run.fps)))
        lo, hi = max(0, guess - r), min(T, guess + r + 1)
        seg = v[lo:hi]
        if np.isfinite(seg).any():
            k, by = lo + int(np.nanargmax(seg)), "muñeca"
        else:
            k, by = guess, "tiempo"
        nb = list(range(max(0, k - 1), min(T, k + 2)))
        elbow = joint_angle(body[:, sk["dom_shoulder"]], body[:, sk["dom_elbow"]], body[:, dw])
        feet_y = np.fmin(body[:, sk["left_ankle"], 1], body[:, sk["right_ankle"], 1])
        med = lambda a: None if not np.isfinite(a[nb]).any() else round(float(np.nanmedian(a[nb])), 1)
        m = {"elbow_impact_deg": med(elbow), "contact_height_pct": med((body[:, dw, 1] - feet_y) * 100),
             "contact_lateral_pct": med(np.abs(body[:, dw, 0]) * 100)}
    if all(x is None for x in m.values()):
        return None
    return {"impact_frame": int(k), "impact_by": by, "frames": nb, "measures": m}


def fine_on_slowmo(video, stroke: dict, view: dict, cfg: dict, dest_dir=None, interlaced: bool = False,
                   cut_args: dict | None = None, hand: str = "right", height_m: float = 1.84, racket=None,
                   runner=None, log=print) -> dict | None:
    """Fine pass on the impact frames of a main-camera slow-motion replay of `stroke` (less motion blur per real
    instant: `view["slowmo"]` frames of the broadcast per live frame), never instead of the live values.

    The replay is cut around `view["impact_t"]` (± slowmo_half_s live seconds × the factor, inside the shot, with
    the fine pass's cut: full quality, one frame per field) into dest_dir, her pose is run on it (the fine pass's
    model, pose only: clip_pipeline.run_clip(pose_only=True), cached beside the clip) and, with `racket` (the
    5-point racket model), the racket at the impact. Her impact in the replay comes from the live one through
    the factor (live t = live impact + (t - impact_t) / factor) and is refined by the wrist's speed peak
    (slowmo_measures). Returns {clip, clip_t0, slowmo, impact_in_clip, impact_by, fps, frames, tracked, measures,
    live} or None (no slow-motion view with its instant, or she is not seen at the impact)."""
    from pathlib import Path

    if not view or view.get("impact_t") is None or (view.get("slowmo") or 0) <= MIN_SLOWMO:
        return None
    st = slowmo_settings(cfg)
    f = float(view["slowmo"])
    it = float(view["impact_t"])
    t0, t1 = max(float(view["t0"]), it - st["half_s"] * f), min(float(view["t1"]), it + st["half_s"] * f)
    if t1 - t0 < 0.2:
        return None
    dest_dir = Path(dest_dir or ".")
    name = f"s{int(round(t0 * 1000)):09d}_{int(round((t1 - t0) * 1000)):05d}.mp4"
    if runner is None:
        from .clip_pipeline import run_clip as runner
    from .stages import cut_window
    clip = cut_window(Path(video), t0, t1 - t0, dest_dir / name, interlaced, **(cut_args or {}))
    run = runner(clip, clip.with_name(f"{clip.stem}_pose.npz"), hand, height_m, rackets=False, init_mode="largest",
                 imgsz=st["imgsz"], log=log, pose_model=st["pose_model"], pose_only=True)
    if not len(run.img):
        return None
    guess = int(round((it - t0) * run.fps))
    got = slowmo_measures(run, min(max(guess, 0), len(run.img) - 1), f)
    if got is None:
        return None
    m = dict(got["measures"])
    if racket is not None and st["racket"]:
        k = got["impact_frame"]
        h = run.height_t[k] if run.height_t is not None and np.isfinite(run.height_t[k]) else run.height_px
        if np.isfinite(h) and h > 0:
            m.update(_racket_at(clip, got["frames"], run.img[:, run.sk["dom_wrist"]], float(h), height_m, racket))
    live = {k: _live_value(stroke, path) for k, (_, _, path) in SLOWMO_MEASURES.items()}
    return {"clip": name, "clip_t0": round(t0, 3), "slowmo": f, "impact_in_clip": round(got["impact_frame"] / run.fps, 3),
            "impact_by": got["impact_by"], "fps": float(run.fps), "frames": len(run.img),
            "tracked": round(float(run.tracked_frac), 3), "measures": m,
            "live": {k: (None if v is None else round(v, 1)) for k, v in live.items()}}


