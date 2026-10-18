"""The return of serve: which of her strokes are returns and their variants, from what TV shows.

A stroke is a return when the opponent serves the point (the scoreboard's serve marker: row 0 is the
target player, so server 1 = the opponent) and it is her first hit of the point (the hits of the cheap
pass on her side of the same main-camera shot). Without a scoreboard reading, the older audio rule
stands (the opponent's hit was the first sound of the shot). Its variants:

- serve_number: second serve when the same shot shows an earlier serve of the opponent 4-30 s before
  (a fault: a far hit with none of hers in between) or the scoreboard banner says so; first serve when
  the shot starts before the serve and shows no earlier one. A cut between the two serves makes a second
  serve look like a first: the class is marked as probable in the matrix.
- serve_dir: where the serve bounced in her service box (exact on the ground through the homography):
  T, body or wide, by thirds of the box width.
- return_side: deuce (iguales) or advantage (ventaja) court, from the parity of the points played in
  the game (scoreboard), checked against the side of the box where the serve bounced. If they
  disagree the side is not given.
- return_ready_depth_m: where she waits for the serve (m from the baseline, − behind it), from her feet
  when the opponent hits; return_step_in_m: how far she moves forwards from there to the contact.
- return_type (forehand, near side only): the kind of return coaches name (ITF, Tennis Australia, the
  Ivanovic guide: block, aggressive, sliced), built only from classes and measures her stroke already has,
  with their own boundaries (no new number):
    cortado        the hand path just before contact goes from high to low (class swing «cortado»,
                   swing_low_to_high < −5°): a path, not spin (rpm is not measurable from TV);
    bloqueo        compact preparation (class takeback «compacta»: hand path < 35 % of her height) and a
                   short finish: the hand ends in front of her (it does not cross to the other side of
                   the body, class finish) and below the shoulder (finish.wrist_dom_vs_shoulder under the
                   −3 % of height that finish_class uses for «over the shoulder»);
    armado corto   compact preparation and a full finish (over the shoulder, around the body or reverse);
    swing completo a non-compact preparation (amplia / en bucle alto) and a full finish.
  A wide preparation with a short finish is none of them: not given. Its repeatability (reliability.py)
  is that of its parts: the share of flips of the takeback and finish classes when the phase instants
  move, plus 1 when the finish height is within its own neighbouring-frame change of the boundary.
"""
from __future__ import annotations

NET_Y = 11.885          # her frame: her baseline at y = 0, the net at 11.885 m
SERVICE_Y = NET_Y - 6.40
BOX_W = 4.115
# boundaries reused from technique.py (classes «takeback» and finish_class), never new numbers
FINISH_SHOULDER_PCT = -3.0           # finish_class: the hand at or above the shoulder within 3 % of height
SHORT_FINISH = ("limpiaparabrisas",)  # finish classes with the hand staying in front of her (not crossing)
RETURN_TYPES = ("bloqueo", "armado corto", "swing completo", "cortado")
RANK = {"0": 0, "15": 1, "30": 2, "40": 3, "AD": 4, "A": 4, "AV": 4, "V": 4}


def points_played(points, tiebreak: bool = False) -> int | None:
    """Points played in the current game from the scoreboard points (None when unreadable)."""
    if not points or len(points) != 2:
        return None
    a, b = points
    if a is None and b is None:
        return None
    vals = []
    for p in (a, b):
        if p is None:
            vals.append(0)                     # an empty slot next to a readable one is a love score
            continue
        s = str(p).strip().upper()
        if tiebreak or (s.isdigit() and s not in RANK):
            if not s.isdigit():
                return None
            vals.append(int(s))
        elif s in RANK:
            vals.append(RANK[s])
        else:
            return None
    if not tiebreak and 4 in vals:             # advantage: deuce (6 points) + 1
        return 7
    return sum(vals)


def side_from_score(score: dict | None) -> str | None:
    if not score:
        return None
    n = points_played(score.get("points"), bool(score.get("tiebreak")))
    return None if n is None else ("iguales" if n % 2 == 0 else "ventaja")


def serve_box(bounce) -> tuple[str, str] | None:
    """(side, direction) of a serve bounce in her own court frame (x + = her right), or None when the
    bounce is not in a service box (with 0.3 m of tolerance for the measurement)."""
    if not bounce:
        return None
    x, y = bounce
    if not (SERVICE_Y - 0.3 <= y <= NET_Y + 0.3) or abs(x) > BOX_W + 0.3:
        return None
    side = "iguales" if x > 0 else "ventaja"   # facing the net, the deuce court is on her right
    a = abs(x)
    return side, ("a la T" if a < BOX_W / 3 else "al cuerpo" if a < 2 * BOX_W / 3 else "abierto")


def serve_number(t_serve: float, shot: tuple[float, float] | None, cands: list[dict], side: str,
                 banner: str = "") -> str | None:
    b = (banner or "").upper()
    if "2ND" in b or "SECOND" in b or "2º" in b or "SEGUNDO" in b:
        return "segundo saque"
    if shot is None:
        return None
    a, _ = shot
    other = "far" if side == "near" else "near"
    earlier = [c["t"] for c in cands if c.get("side", "near") == other and a <= c["t"] <= t_serve - 4.0 and t_serve - c["t"] <= 30.0]
    if earlier:
        last = max(earlier)
        mine = [c for c in cands if c.get("side", "near") == side and last < c["t"] < t_serve - 0.3]
        if not mine:
            return "segundo saque"
    return "primer saque" if t_serve - a >= 1.5 else None


def return_of_serve(d: dict, k: int | None, shot: tuple[float, float] | None, cands: list[dict]) -> dict:
    """Return classes and values of one stroke (d: as in strokes.json; k: her shot number in the point,
    None if unknown). Empty when it is not a return (or cannot be told)."""
    sc = d.get("score") or {}
    ta = (d.get("metrics") or {}).get("time_available_s")
    opp_serves = None if sc.get("server") is None else sc["server"] == 1
    if opp_serves is not None and k is not None:
        is_ret = bool(opp_serves and k == 1)
    elif d.get("is_return") is not None:
        is_ret = bool(d["is_return"]) and (k in (None, 1))
    else:
        return {}
    out = {"is_return": is_ret}
    if not is_ret:
        return out
    cl, vals = {"play": "resto"}, {}
    if ta is not None:
        n = serve_number(d["match_time_s"] - ta, shot, cands, d.get("side", "near"), sc.get("banner") or "")
        if n:
            cl["serve_number"] = n
    box = serve_box(d.get("bounce_court_m"))
    if box:
        cl["serve_dir"] = box[1]
    by_score = side_from_score(sc)
    by_box = box[0] if box else None
    if by_score and by_box and by_score != by_box:
        pass                                   # they disagree: the side is not given
    elif by_score or by_box:
        cl["return_side"] = by_score or by_box
    w, c = d.get("pos_at_opp_m"), d.get("court_pos_m")
    if w:
        vals["return_ready_depth_m"] = round(float(w[1]), 2)
        if c:
            vals["return_step_in_m"] = round(float(c[1] - w[1]), 2)
    out.update(classes=cl, values=vals)
    return out


def return_type(tech: dict) -> tuple[str | None, float | None]:
    """(kind of return, its flip estimate) from the classes and measures of one forehand (technique)."""
    cl = tech.get("classes") or {}
    jit = tech.get("jitter") or {}
    tb, fin, sw = cl.get("takeback"), cl.get("finish"), cl.get("swing")
    fh = ((tech.get("phases") or {}).get("finish") or {}).get("wrist_dom_vs_shoulder")
    if isinstance(sw, str) and sw.startswith("cortado"):
        js = jit.get("class.swing")
        return "cortado", (js if isinstance(js, (int, float)) else None)
    flips = [jit[k] for k in ("class.takeback", "class.finish", "class.swing") if isinstance(jit.get(k), (int, float))]
    jf = jit.get("finish.wrist_dom_vs_shoulder")
    if isinstance(fh, (int, float)) and isinstance(jf, (int, float)):
        flips.append(1.0 if abs(fh - FINISH_SHOULDER_PCT) <= jf else 0.0)
    flip = round(min(1.0, sum(flips)), 2) if isinstance(jit.get("class.takeback"), (int, float)) else None
    if tb is None or fin is None or not isinstance(fh, (int, float)):
        return None, None
    short = fin in SHORT_FINISH and fh < FINISH_SHOULDER_PCT
    if tb == "compacta":
        return ("bloqueo" if short else "armado corto"), flip
    return (None if short else "swing completo"), (None if short else flip)


def apply(d: dict, k: int | None, shot: tuple[float, float] | None, cands: list[dict]) -> None:
    """Writes the return into the stroke: is_return, its classes and its values (technique.stroke)."""
    r = return_of_serve(d, k, shot, cands)
    if not r:
        return
    d["is_return"] = r["is_return"]
    tech = d.get("technique")
    if tech is None:
        return
    cl = tech.setdefault("classes", {})
    st = tech.setdefault("stroke", {})
    for key in ("serve_number", "serve_dir", "return_side", "return_type"):
        cl.pop(key, None)
    for key in ("return_ready_depth_m", "return_step_in_m"):
        st.pop(key, None)
    (tech.get("jitter") or {}).pop("class.return_type", None)
    if r["is_return"]:
        cl.update(r["classes"])
        st.update(r["values"])
        # the kind of return: only her forehands seen near (far side: no takeback, finish or swing)
        if d.get("side", "near") != "far" and d.get("stroke", "forehand") == "forehand":
            kind, flip = return_type(tech)
            if kind:
                cl["return_type"] = kind
                if flip is not None:
                    tech.setdefault("jitter", {})["class.return_type"] = flip
    elif cl.get("play") == "resto":
        cl["play"] = "inicio del punto" if (k or 0) <= 2 else "peloteo"
