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


def fine_on_slowmo(video, stroke: dict, view: dict, cfg: dict) -> dict | None:
    """Fine pass on the impact frames of a main-camera slow-motion replay of `stroke` (less motion blur
    per frame: `view["slowmo"]` frames of the broadcast per real frame).

    TODO(#218, plan_maestro block 2.1): cut the replay around `view["impact_t"]` (± 0.2 s × factor),
    run the same pose / racket models as the fine pass on it, map its frames back to live time
    (live t = impact live t + (t - impact_t) / factor) and return the racket face and the arm at the
    impact measured there, beside (never instead of) the live values. Until then the stroke only says
    it has such a view (`slowmo_view`)."""
    raise NotImplementedError("pasada fina sobre la repetición a cámara lenta: pendiente (#218)")
