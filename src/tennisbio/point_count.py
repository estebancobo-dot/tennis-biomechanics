"""Points played and her service points, counted from the scoreboard readings (score.json).

Used by the audit to say how many strokes of hers a full match must contain, without any
"points × shots per point" guess presented as exact: the points and the service points come from the
scoreboard itself; only the shots per rally are a typical range, and it is shown as a range.

The OCR readings are noisy (other matches' scoreboards, replays of an older score, a misread digit):
- readings flagged by the reader (columns_mismatch) or with impossible games are dropped;
- the total of games played (all sets) can only grow along the match: the longest non-decreasing
  sequence of it in time is kept, and for each total the most read set of games;
- inside a game the points can only grow (outside deuce): a reading going back is dropped.

Each change between consecutive kept states adds the points it implies: inside a game the difference
(15→30 = 1, 40-40→AD = 1, AD-x→x-AD = 2); across a game change the points still needed by the
winner of the previous game from its last reading (minimum), plus 4 to 10 points per game never read,
plus the points of the new game. The result is a lower value (`points`) and an upper one
(`points_high`: a game that ended from deuce may have had hidden deuce cycles; unread games).
"""
from __future__ import annotations

import bisect
from collections import Counter

RANK = {"0": 0, "00": 0, "15": 1, "30": 2, "40": 3, "AD": 4, "A": 4, "AV": 4}
GAME_MIN, GAME_TYPICAL_HIGH = 4, 10          # points of a game never read: at least 4, rarely above 10
# her shots per point in WTA rallies (serve included): a typical range, never an exact value. Mean rally
# length on the WTA tour is about 3.5-5 shots per point (both players, serve included), plus second serves.
HER_SHOTS_PER_POINT = (1.6, 2.6)


def _pts(p, tiebreak: bool):
    """Point ranks of one reading: (a, b) ints, or None when unreadable. None/"" before the first
    point of a game is 0 (the scoreboard shows nothing)."""
    if p is None or len(p) != 2:
        return None
    out = []
    for x in p:
        if x is None or str(x).strip() == "":
            out.append(0)
            continue
        s = str(x).strip().upper()
        if tiebreak:
            if not s.isdigit():
                return None
            out.append(int(s))
        elif s in RANK:
            out.append(RANK[s])
        else:
            return None
    if not tiebreak and (out[0] == 4 and out[1] != 3 or out[1] == 4 and out[0] != 3):
        return None                             # advantage only from deuce
    return tuple(out)


def _state(r: dict):
    games = r.get("games")
    if not games or r.get("flags") or any(len(g) != 2 for g in games):
        return None
    try:
        games = tuple((int(a), int(b)) for a, b in games)
    except (TypeError, ValueError):
        return None
    if any(a < 0 or b < 0 or a > 7 or b > 7 for a, b in games[:-1]) or any(x > 13 for x in games[-1]):
        return None
    cur = games[-1]
    tb = bool(r.get("tiebreak")) or cur == (6, 6)
    pts = _pts(r.get("points"), tb)
    if pts is None:
        return None
    return {"t": float(r["t"]), "games": games, "g": sum(a + b for a, b in games), "pts": pts, "tb": tb,
            "server": r.get("server")}


def _lnds(vals: list[int]) -> list[int]:
    """Indices of a longest non-decreasing subsequence."""
    tails, tail_i, prev = [], [], [-1] * len(vals)
    for i, v in enumerate(vals):
        k = bisect.bisect_right(tails, v)
        if k == len(tails):
            tails.append(v)
            tail_i.append(i)
        else:
            tails[k], tail_i[k] = v, i
        prev[i] = tail_i[k - 1] if k else -1
    out, i = [], tail_i[-1] if tail_i else -1
    while i >= 0:
        out.append(i)
        i = prev[i]
    return out[::-1]


def clean_states(readings: list[dict]) -> list[dict]:
    """The kept scoreboard states in time order (see the module docstring), consecutive repeats merged."""
    st = sorted((s for s in (_state(r) for r in readings or []) if s is not None), key=lambda s: s["t"])
    if not st:
        return []
    st = [st[i] for i in _lnds([s["g"] for s in st])]
    modal = {g: Counter(s["games"] for s in st if s["g"] == g).most_common(1)[0][0] for g in {s["g"] for s in st}}
    st = [s for s in st if s["games"] == modal[s["g"]]]
    # the server of each game: the most read marker in it
    srv = {}
    for s in st:
        if s["server"] in (0, 1):
            srv.setdefault(s["g"], Counter())[s["server"]] += 1
    out = []
    for s in st:
        s = {**s, "server": srv[s["g"]].most_common(1)[0][0] if s["g"] in srv else None}
        if out and out[-1]["g"] == s["g"] and out[-1]["pts"] == s["pts"]:
            continue
        if out and out[-1]["g"] == s["g"] and _in_game(out[-1], s) is None:
            continue                            # points going back inside a game: a misread
        out.append(s)
    return out


def _deuce(p) -> bool:
    return p[0] >= 3 and p[1] >= 3


def _in_game(a: dict, b: dict):
    """Points played from state a to state b of the same game, or None when b cannot follow a."""
    pa, pb = a["pts"], b["pts"]
    if a["tb"] or b["tb"]:
        d = sum(pb) - sum(pa)
        return d if d >= 0 and pb[0] >= pa[0] and pb[1] >= pa[1] else None
    if _deuce(pa) and _deuce(pb):
        if pa == pb:
            return 0
        return 2 if pa[0] == 4 and pb[1] == 4 or pa[1] == 4 and pb[0] == 4 else 1
    if _deuce(pb):                               # into deuce: to 40-40 (6 points) and maybe one more
        if pa[0] > 3 or pa[1] > 3:
            return None
        return 6 - sum(pa) + (0 if pb == (3, 3) else 1)
    if _deuce(pa):
        return None
    d = sum(pb) - sum(pa)
    return d if d >= 0 and pb[0] >= pa[0] and pb[1] >= pa[1] else None


def remaining_min(pts, winner: int | None, tiebreak: bool = False) -> int:
    """Fewest points that end a game from `pts` with `winner` (0 / 1) winning it (None: either)."""
    if winner is None:
        return min(remaining_min(pts, 0, tiebreak), remaining_min(pts, 1, tiebreak))
    w, lo = pts[winner], pts[1 - winner]
    if tiebreak:
        return max(7, lo + 2) - w if max(7, lo + 2) > w else 1
    if w == 4:
        return 1
    if lo == 4:
        return 3
    if lo <= 2:
        return 4 - w
    return (3 - w) + 2


def _winner(a: dict, b: dict):
    """Who won the game that ended between states a and b (0 / 1), from the games of a's set in b."""
    i = len(a["games"]) - 1
    if i >= len(b["games"]):
        return None
    (x0, y0), (x1, y1) = a["games"][i], b["games"][i]
    if x1 > x0 and y1 == y0:
        return 0
    if y1 > y0 and x1 == x0:
        return 1
    return None


def count_points(readings: list[dict]) -> dict:
    """Points played and her service points (row 0 of the scoreboard is her) in the stretch read.

    Returns {"points", "points_high", "her_service_points", "her_service_points_high", "unknown_server",
    "games_seen", "games_unread", "states", "span_s"}."""
    st = clean_states(readings)
    out = {"points": 0, "points_high": 0, "her_service_points": 0.0, "her_service_points_high": 0.0,
           "unknown_server": 0, "games_seen": len({s["g"] for s in st}), "games_unread": 0, "states": len(st),
           "span_s": None if not st else [st[0]["t"], st[-1]["t"]]}

    def add(n_lo, n_hi, server, tb=False):
        out["points"] += n_lo
        out["points_high"] += n_hi
        if tb or server is None:              # tie-break: the serve alternates; unknown: half and half
            out["her_service_points"] += n_lo / 2
            out["her_service_points_high"] += n_hi / 2
            out["unknown_server"] += 0 if tb else n_lo
        elif server == 0:
            out["her_service_points"] += n_lo
            out["her_service_points_high"] += n_hi
    for a, b in zip(st, st[1:]):
        if b["g"] == a["g"]:
            d = _in_game(a, b)
            add(d, d, a["server"], a["tb"])
            continue
        k = b["g"] - a["g"]
        rem = remaining_min(a["pts"], _winner(a, b), a["tb"])
        add(rem, rem + (2 if _deuce(a["pts"]) and not a["tb"] else 0), a["server"], a["tb"])
        if k > 1:
            out["games_unread"] += k - 1
            add(GAME_MIN * (k - 1), GAME_TYPICAL_HIGH * (k - 1), None, True)
        first = sum(b["pts"])
        if not b["tb"] and _deuce(b["pts"]):
            first = 6 + (0 if b["pts"] == (3, 3) else 1)
        add(first, first, b["server"], b["tb"])
    out["her_service_points"] = round(out["her_service_points"], 1)
    out["her_service_points_high"] = round(out["her_service_points_high"], 1)
    return out


def expected_strokes(counts: dict) -> dict:
    """Her strokes a stretch with these points must contain: serves [service points, 2 × service points]
    (a fault is a serve too) and all her strokes in a typical range (HER_SHOTS_PER_POINT per point)."""
    s_lo, s_hi = counts["her_service_points"], counts["her_service_points_high"]
    p_lo, p_hi = counts["points"], counts["points_high"]
    return {"serves": [round(s_lo), round(2 * s_hi)],
            "all_typical": [round(HER_SHOTS_PER_POINT[0] * p_lo), round(HER_SHOTS_PER_POINT[1] * p_hi)],
            # a hard floor: at least one serve per point she serves
            "all_min": round(s_lo)}


def recall_verdict(found_all: int, found_serves: int, counts: dict, min_points: int = 15) -> tuple[str, str]:
    """(status, Spanish detail) of the audit item: "pocos datos" with fewer than min_points points read;
    "falta" when the strokes found are clearly too few (under half the lower end of the typical range,
    or serves under half her service points: both are upper bounds of the recall); "aviso" under the
    lower end; "ok" otherwise."""
    if counts["points"] < min_points:
        return "pocos datos", (f"el marcador solo deja contar {counts['points']} puntos: no se puede comprobar "
                               "si faltan golpes")
    ex = expected_strokes(counts)
    lo, hi = ex["all_typical"]
    s_lo, s_hi = ex["serves"]
    r_all = found_all / lo if lo else 1.0
    r_srv = found_serves / s_lo if s_lo else 1.0
    det = (f"marcador: {counts['points']}-{counts['points_high']} puntos jugados ({counts['games_seen']} juegos leídos, "
           f"{counts['games_unread']} sin leer), {counts['her_service_points']:.0f} con su saque. "
           f"Esperados: {s_lo}-{s_hi} saques (1 o 2 por punto de saque) y {lo}-{hi} golpes en total "
           f"(rango típico de {HER_SHOTS_PER_POINT[0]}-{HER_SHOTS_PER_POINT[1]} golpes suyos por punto, no exacto). "
           f"Encontrados: {found_all} golpes, {found_serves} saques/remates → como mucho "
           f"{min(1, r_all):.0%} de sus golpes y {min(1, r_srv):.0%} de sus saques")
    if r_all < 0.5 or (s_lo >= 10 and r_srv < 0.5):
        return "falta", det + ". Faltan muchos golpes (ver scripts/validate_recall.py para saber en qué etapa se pierden)"
    if r_all < 1.0 or (s_lo >= 10 and r_srv < 1.0):
        return "aviso", det
    return "ok", det


GAP_CAUSES = {"sin_camara": "sin plano de la cámara principal", "sin_golpes": "sin ningún golpe suyo",
              "sin_saque": "golpes suyos, pero ningún saque"}


def serve_gaps(readings: list[dict], strokes: list[dict], main_shots: list[tuple[float, float]],
               lead_s: float = 25.0, spotted: list[dict] | None = None) -> dict:
    """B4 (04-11): the points played on HER serve (scoreboard row 0 serving, a point counted between two readings of
    the same game) with no serve of hers found, and why: no main-camera shot in that stretch (the broadcast did not
    show it), none of her strokes at all (detection), or strokes but no serve (stroke type). The stretch of a point is
    from the first reading that shows its score (5 s earlier at most) to the reading that shows the next one. Returns {"points": n, "found": n, "gaps": [{"t0", "t1", "cause"}], "by_cause": {cause: n}}."""
    st = clean_states(readings)
    serve_t = sorted(float(s["match_time_s"]) for s in strokes
                     if s.get("stroke") == "overhead" and s.get("match_time_s") is not None)
    any_t = sorted(float(s["match_time_s"]) for s in strokes if s.get("match_time_s") is not None)
    by_t = {float(s["match_time_s"]): s for s in strokes if s.get("match_time_s") is not None}
    import bisect

    def inside(ts, a, b):
        i = bisect.bisect_left(ts, a)
        return i < len(ts) and ts[i] <= b

    out = {"points": 0, "found": 0, "gaps": [], "by_cause": {k: 0 for k in GAP_CAUSES}}
    her_w, opp_w = [], []                       # point stretches on her serve and on the opponent's
    since = st[0]["t"] if st else 0.0           # when the score of the current reading was first shown
    for a, b in zip(st, st[1:]):
        same_score = b["g"] == a["g"] and b["pts"] == a["pts"]
        if not same_score:
            start, since = since, b["t"]
        if b["g"] != a["g"] or a["tb"] or same_score or not _in_game(a, b):
            continue
        # the point starts once its score is on the board (a few seconds of slack for the reading rate)
        t0, t1 = start - min(lead_s, 5.0), b["t"]
        if a["server"] != 0:
            if a["server"] == 1:
                opp_w.append((t0, t1))
            continue
        her_w.append((t0, t1))
        out["points"] += 1
        if inside(serve_t, t0, t1):
            out["found"] += 1
            continue
        if not any(s < t1 and e > t0 for s, e in main_shots):
            cause = "sin_camara"
        elif not inside(any_t, t0, t1):
            cause = "sin_golpes"
        else:
            cause = "sin_saque"
        out["by_cause"][cause] += 1
        gap = {"t0": round(t0, 1), "t1": round(t1, 1), "cause": cause}
        # when the main camera comes back in this point and her first stroke found after it: a serve lost at the very
        # start of the shot (after a replay or a close-up) shows as a first stroke many seconds after the shot starts
        st_main = [s0 for s0, e0 in main_shots if e0 > t0 and s0 < t1]
        if st_main:
            s0 = max(t0, min(st_main))
            gap["shot_start"] = round(s0, 1)
            first = next((t for t in any_t if s0 <= t <= t1), None)
            if first is not None:
                gap["first_stroke_after_s"] = round(first - s0, 1)
                fs = by_t.get(first) or {}
                cp = fs.get("court_pos_m") or [None, None]
                gap["first_stroke"] = {"stroke": fs.get("stroke"), "source": fs.get("stroke_source"),
                                       "pose": fs.get("stroke_pose"), "side": fs.get("side"),
                                       "court_y_m": None if cp[1] is None else round(float(cp[1]), 2)}
        out["gaps"].append(gap)
    delays = sorted(g["first_stroke_after_s"] for g in out["gaps"] if "first_stroke_after_s" in g)
    # what the learned spotter saw (spotting.json, both players) in each point without a serve before her first stroke
    # found (07-11): a serve on her side lost later, the opponent's stroke (her serve never spotted), or nothing
    if spotted is not None:
        sp = sorted((float(e["t"]), e) for e in spotted if e.get("t") is not None)
        seen = {"saque_suyo_visto_y_perdido": 0, "golpe_suyo_visto_y_perdido": 0, "golpe_de_la_rival_antes": 0,
                "nada_antes": 0, "sin_primer_golpe": 0}
        for g in out["gaps"]:
            fs = g.get("first_stroke") or {}
            side = fs.get("side")
            end = g["t0"] + g.get("first_stroke_after_s", 0) + (g.get("shot_start", g["t0"]) - g["t0"]) if fs else g["t1"]
            before = [e for t, e in sp if g["t0"] <= t < end - 0.3]
            if not fs:
                seen["sin_primer_golpe"] += 1
            if side and any(e.get("side") == side and e.get("kind") == "serve" for e in before):
                seen["saque_suyo_visto_y_perdido"] += 1
            elif side and any(e.get("side") == side for e in before):
                seen["golpe_suyo_visto_y_perdido"] += 1
            elif side and any(e.get("side") not in (None, side) for e in before):
                seen["golpe_de_la_rival_antes"] += 1
            elif fs:
                seen["nada_antes"] += 1
        out["spotter_before_first"] = seen
    firsts = [g["first_stroke"] for g in out["gaps"] if g.get("cause") == "sin_saque" and g.get("first_stroke")]
    from collections import Counter
    out["first_strokes_without_serve"] = {
        "n": len(firsts),
        "type": dict(Counter(f"{f['stroke']}/{f['source']}" for f in firsts)),
        "side": dict(Counter(str(f["side"]) for f in firsts)),
        "behind_baseline": sum(1 for f in firsts if f["court_y_m"] is not None and f["court_y_m"] <= 0.5)}
    out["first_stroke_after_shot_start_s"] = (None if not delays else
                                              {"median": delays[len(delays) // 2], "n": len(delays),
                                               "under_3": sum(d < 3 for d in delays)})
    # where her serves found fall: in a point of her serve, of the opponent's (identity or a smash), or in none read
    within = lambda t, ws: any(a <= t <= b for a, b in ws)
    out["serves_at"] = {"her_points": sum(within(t, her_w) for t in serve_t),
                        "opponent_points": sum(within(t, opp_w) and not within(t, her_w) for t in serve_t),
                        "elsewhere": sum(not within(t, her_w) and not within(t, opp_w) for t in serve_t)}
    return out


def her_serve_points(readings: list[dict], lead_s: float = 5.0) -> list[tuple[float, float]]:
    """(start, end) of each point on HER serve read on the scoreboard (row 0 serving, same game, one point played):
    from the first reading that shows its score (lead_s earlier at most) to the reading that shows the next one."""
    st = clean_states(readings)
    out = []
    since = st[0]["t"] if st else 0.0
    for a, b in zip(st, st[1:]):
        same_score = b["g"] == a["g"] and b["pts"] == a["pts"]
        if not same_score:
            start, since = since, b["t"]
        if b["g"] != a["g"] or a["tb"] or same_score or a["server"] != 0 or not _in_game(a, b):
            continue
        out.append((start - lead_s, b["t"]))
    return out


SERVE_RULE = "primer golpe de quien saca"


def serves_by_rule(strokes: list[dict], readings: list[dict], main_shots: list[tuple[float, float]],
                   behind_m: float = 0.5, max_after_shot_s: float = 15.0, min_contact_pct: float = 95.0,
                   min_toss_bh: float = 0.05) -> int:
    """B4 (04-11): in a point on her serve, her first stroke is her serve (the rules of tennis). Requests 101-102: in the
    points of her serve with no serve found, her first stroke came 4-9 s after the main camera returned and behind her
    baseline, named forehand/backhand by the learned spotter — her serve, misnamed. Each such stroke (the first of hers in
    the point, behind her baseline, at most `max_after_shot_s` after the main camera is back, in a point with no serve of
    hers yet) becomes "overhead"; what it was called stays in stroke_before. Returns how many changed (in place)."""
    changed = 0
    ts = sorted((float(s["match_time_s"]), i) for i, s in enumerate(strokes) if s.get("match_time_s") is not None)
    for t0, t1 in her_serve_points(readings):
        inside = [(t, i) for t, i in ts if t0 <= t <= t1]
        if not inside or any(strokes[i].get("stroke") == "overhead" for _, i in inside):
            continue
        t, i = inside[0]
        s = strokes[i]
        y = (s.get("court_pos_m") or [None, None])[1]
        starts = [a for a, b in main_shots if a <= t <= b]
        shot = max(starts) if starts else None
        if y is None or float(y) > behind_m or shot is None or t - max(shot, t0) > max_after_shot_s:
            continue
        # and her hand above her head at contact (request 104: without it, 31 of F3Set's forehands and backhands —
        # first strokes of a point read across two clips — were made serves)
        # or her free hand above her head before contact (the toss; request 110: the hand-at-contact test alone found
        # none of the real matches' misnamed serves, their contact frame was not the contact)
        mt = s.get("metrics") or {}
        ch, toss = mt.get("contact_height_pct"), mt.get("toss_above_head_bh")
        if not ((ch is not None and float(ch) >= min_contact_pct) or (toss is not None and float(toss) >= min_toss_bh)):
            continue
        s["stroke_before"] = s.get("stroke")
        s["stroke"], s["stroke_rule"] = "overhead", SERVE_RULE
        changed += 1
    return changed
