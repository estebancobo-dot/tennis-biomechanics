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
