"""TV scoreboard reading (phase 3): sets, games, points and pressure situations.

OCR with RapidOCR (PaddleOCR models in ONNX Runtime, works on Windows CPU). The scoreboard is
found once per match by looking for both players' surnames; afterwards only that region is read.
Each row: NAME [country] set games... current games [points]. Digits of the set columns often come
glued together by the OCR ("472"), and set scores are single digits, so they are split one by one.
"""
import difflib
import json
import re
import warnings
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

POINTS = {"0", "15", "30", "40", "AD", "A"}
TOKEN = re.compile(r"\d+|AD|A")


@dataclass
class ScoreState:
    games: list[list[int]]                 # per set, [player, opponent]; the last one is the current set
    points: list[str | None]               # [player, opponent], None when not shown
    banner: str = ""                       # e.g. "BREAK POINT", "SET POINT" when the broadcast shows it
    server: int | None = None              # 0 player, 1 opponent (serve marker on the scoreboard)
    flags: list[str] = field(default_factory=list)
    # 09-11: row 0 minus row 1 salience per x-bin (row_profile), for learning where this broadcast's serve
    # marker is (learn_server); not part of the reading written to score.json
    profile: np.ndarray | None = field(default=None, repr=False, compare=False)

    @property
    def set_number(self) -> int:
        return len(self.games)

    @property
    def sets_won(self) -> list[int]:
        done = self.games[:-1]
        return [sum(a > b for a, b in done), sum(b > a for a, b in done)]

    @property
    def tiebreak(self) -> bool:
        return bool(self.games) and self.games[-1] == [6, 6]

    @property
    def pressure(self) -> bool:
        """Tight point: break/set/match point banner, deuce or advantage, 30-40 / 40-30, tie-break."""
        if self.banner or self.tiebreak:
            return True
        p = tuple(self.points)
        return p in {("40", "40"), ("30", "40"), ("40", "30")} or "AD" in p or "A" in p

    def to_dict(self) -> dict:
        return {"games": self.games, "points": self.points, "banner": self.banner, "server": self.server, "set": self.set_number,
                "sets_won": self.sets_won, "tiebreak": self.tiebreak, "pressure": self.pressure, "flags": self.flags}


def _norm(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def _is_name(text: str, surname: str, min_ratio=0.75) -> bool:
    """The OCR text is this player's name: full surname, a close misreading, or the 3-letter
    abbreviation some broadcasters use (RYB, SAB). «A|B»: any of these names (14-11, stages._opponent_on_scoreboard)."""
    if "|" in surname:
        return any(_is_name(text, s, min_ratio) for s in surname.split("|") if s)
    t, n = _norm(text), _norm(surname)
    if not t or not n:
        return False
    if n in t:
        return True
    if len(t) == 3 and t.isalpha() and n.startswith(t):
        return True
    return difflib.SequenceMatcher(None, t[:len(n) + 2], n).ratio() >= min_ratio


def _center(box) -> tuple[float, float]:
    b = np.asarray(box, float)
    return float(b[:, 0].mean()), float(b[:, 1].mean())


def find_rows(items: list, surnames: tuple[str, str]):
    """(row_y_player, row_y_opponent, roi x0,y0,x1,y1) from OCR items [(box, text, conf)], or None."""
    ys, boxes = [None, None], []
    for box, text, _ in items:
        for k, name in enumerate(surnames):
            if ys[k] is None and _is_name(text, name):
                ys[k] = _center(box)[1]
                boxes.append(np.asarray(box, float))
    if None in ys:
        return None
    b = np.vstack(boxes)
    h = abs(ys[0] - ys[1]) or 20.0
    return ys[0], ys[1], (b[:, 0].min() - h, min(ys) - 1.5 * h, b[:, 0].max() + 12 * h, max(ys) + 1.2 * h)


def serve_marker(image: np.ndarray, items: list, rows_y: tuple[float, float], min_area=30) -> int | None:
    """Row (0/1) with the serve marker: a saturated coloured blob that is not text (a ball icon,
    dot or arrow next to the server's name). OCR text boxes are masked out, so coloured digits
    (sets won) and the names do not count."""
    import cv2

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    m = ((hsv[..., 1] > 110) & (hsv[..., 2] > 120)).astype(np.uint8)
    for box, _, _ in items:
        b = np.asarray(box, int)
        cv2.fillPoly(m, [b], 0)
    gap = abs(rows_y[0] - rows_y[1])
    n, _, st, cen = cv2.connectedComponentsWithStats(m)
    cand = []                                                   # (row, x0, x1, area)
    for i in range(1, n):
        x, y, w, h, area = st[i]
        if area < min_area or h > 0.8 * gap or w > 3 * gap:     # banners and big panels are not markers
            continue
        # 09-11 (Miami 2026, diag_scoreboard): a marker is a compact mark (dot, ball, arrow), not the stripes of a flag:
        # the red stripes of the US flag on Pegula's row were read as her serve in 379 of 407 readings, while the real
        # marker, a green dot by the server's score, was there too
        if not (0.4 <= w / max(h, 1) <= 2.5 and area >= 0.45 * w * h and max(w, h) <= 0.7 * gap):
            continue
        for k, ry in enumerate(rows_y):
            if abs(cen[i][1] - ry) < 0.35 * gap:
                cand.append((k, x, x + w, area))
    # 09-11: a coloured element drawn on both rows (a highlighted points cell, a coloured seed or country box, two
    # flags of one colour) is part of the layout, not the marker: it made both rows equal and the reading None
    twin = set()
    for a, ca in enumerate(cand):
        for b, cb in enumerate(cand):
            if ca[0] == 0 and cb[0] == 1:
                ov = min(ca[2], cb[2]) - max(ca[1], cb[1])
                if ov >= 0.5 * min(ca[2] - ca[1], cb[2] - cb[1]) and 0.5 <= ca[3] / max(cb[3], 1) <= 2.0:
                    twin.update((a, b))
    hits = [0.0, 0.0]
    for a, (k, _, _, area) in enumerate(cand):
        if a not in twin:
            hits[k] += area
    if max(hits) == 0 or min(hits) > 0.5 * max(hits):
        return None
    return int(np.argmax(hits))


PROFILE_BINS = (-4.0, 14.0, 0.25)        # x from the names' left edge, in row gaps: from, to, bin width


def row_profile(image: np.ndarray, items: list, rows_y: tuple[float, float], name_boxes: list) -> np.ndarray | None:
    """Row 0 minus row 1 salience (colour distance from the scoreboard's background, the median colour of the
    region) per x-bin, bins in row gaps from the names' left edge (PROFILE_BINS), NaN where there is no image.
    Text other than the names is masked (its digits change with the score); the names are kept, because a
    serve marker drawn next to a name often falls inside its OCR box. Whatever marks the server shows up as
    a difference that flips sign when the serve changes hands, which learn_server finds over the match."""
    import cv2

    if image is None or image.ndim != 3 or not name_boxes:
        return None
    gap = abs(rows_y[0] - rows_y[1])
    if gap < 4:
        return None
    img = image.astype(np.float32)
    mask = np.zeros(image.shape[:2], np.uint8)
    for box, _, _ in items:
        if not any(box is nb for nb in name_boxes):
            cv2.fillPoly(mask, [np.asarray(box, np.int32)], 1)
    keep = mask == 0
    if not keep.any():
        return None
    bg = np.median(img[keep], axis=0)
    sal = np.abs(img - bg).max(axis=2)
    sal[~keep] = np.nan
    h, w = sal.shape
    lo, hi, step = PROFILE_BINS
    x_ref = min(float(np.asarray(b, float)[:, 0].min()) for b in name_boxes)
    nb = int(round((hi - lo) / step))
    edges = x_ref + (lo + step * np.arange(nb + 1)) * gap
    prof = []
    for ry in rows_y:
        y0, y1 = int(max(0, round(ry - 0.3 * gap))), int(min(h, round(ry + 0.3 * gap) + 1))
        band = sal[y0:y1]
        out = np.full(nb, np.nan, np.float32)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)          # columns that are all text
            col = np.nanmean(band, axis=0) if band.size else np.full(w, np.nan)
            for b in range(nb):
                a, c = max(int(np.floor(edges[b])), 0), min(int(np.ceil(edges[b + 1])), w)
                if c - a >= 1 and np.isfinite(col[a:c]).any():
                    out[b] = float(np.nanmean(col[a:c]))
        prof.append(out)
    return prof[0] - prof[1]


def _split_stacked(items: list, y_a: float, y_b: float) -> list:
    """11-11 (Rybakina-Pegula, Miami): the text detector boxed the two players' games, one above the other in the same
    column, as one word («02»): the second row then had no games and the reading was dropped (13 min of the match without
    the scoreboard). A digits-only box as tall as both rows, one digit per row, is split into one item per row."""
    lo, hi = sorted((y_a, y_b))
    out = []
    for box, text, conf in items:
        t = str(text).strip()
        b = np.asarray(box, float)
        top, bot = b[:, 1].min(), b[:, 1].max()
        if t.isdigit() and 2 <= len(t) <= 4 and top <= lo + 0.25 * (hi - lo) and bot >= hi - 0.25 * (hi - lo):
            # digits stacked: as many rows as digits only when there are two rows to share (one digit or two each)
            k = len(t) // 2
            first, second = (t[:1], t[1:]) if len(t) == 2 else (t[:k], t[k:])
            for dig, y in ((first, y_a if y_a < y_b else y_b), (second, y_b if y_a < y_b else y_a)):
                bb = b.copy()
                bb[:, 1] = y
                out.append((bb, dig, conf))
            continue
        out.append((box, text, conf))
    return out


def parse(items: list, surnames: tuple[str, str], image: np.ndarray | None = None) -> ScoreState | None:
    """Score state from OCR items of the scoreboard region (any coordinates); with the region
    image, also who serves."""
    rows = find_rows(items, surnames)
    if rows is None:
        return None
    y_p, y_o, _ = rows
    tol = abs(y_p - y_o) * 0.45 or 10
    items = _split_stacked(items, y_p, y_o)
    banner = ""
    cells = {0: [], 1: []}
    name_x, name_box = {}, {}
    for box, text, _ in items:
        x, y = _center(box)
        up = _norm(text)
        if "BREAK" in up or "SETPOINT" in up or "MATCHPOINT" in up or "CHAMPIONSHIP" in up:
            banner = "BREAK POINT" if "BREAK" in up else "MATCH POINT" if ("MATCH" in up or "CHAMP" in up) else "SET POINT"
            continue
        for k, yr in enumerate((y_p, y_o)):
            if abs(y - yr) <= tol:
                if _is_name(text, surnames[k]):
                    name_x[k], name_box[k] = x, box
                else:
                    cells[k].append((x, text))
    if len(name_x) < 2:
        return None
    toks = {}
    for k in (0, 1):
        seq = []
        for x, text in sorted(c for c in cells[k] if c[0] > name_x[k]):
            for t in TOKEN.findall(_norm(text)):
                seq.append(t)
        toks[k] = seq
    pts = []
    digits = {}
    for k in (0, 1):
        seq = toks[k]
        p = seq[-1] if seq and seq[-1] in POINTS and (len(seq) > 1 or seq[-1] in {"AD", "A", "15", "30", "40"}) else None
        rest = seq[:-1] if p is not None else seq
        ds = [int(c) for t in rest if t.isdigit() for c in t]          # glued set columns: "472" → 4 7 2
        pts.append(p if p != "A" else "AD")
        digits[k] = ds
    n = min(len(digits[0]), len(digits[1]))
    if n == 0:
        return None
    flags = [] if len(digits[0]) == len(digits[1]) else ["columns_mismatch"]
    games = [[digits[0][i], digits[1][i]] for i in range(n)]
    if pts[0] is None and pts[1] == "AD":
        pts[0] = "40"
    if pts[1] is None and pts[0] == "AD":
        pts[1] = "40"
    server = serve_marker(image, items, (y_p, y_o)) if image is not None else None
    prof = row_profile(image, items, (y_p, y_o), list(name_box.values())) if image is not None else None
    return ScoreState(games, pts, banner, server, flags, prof)


def serve_parity(reading: dict) -> int | None:
    """Games played in the match mod 2 (the serve changes hands every game, a tie-break counting as one game
    in the set's score), or None in a tie-break (the serve changes every two points) or without games."""
    g = reading.get("games")
    if not g or reading.get("tiebreak"):
        return None
    try:
        return int(sum(int(a) + int(b) for a, b in g)) % 2
    except (TypeError, ValueError):  # esperado: games that are not numbers: unknown
        return None


def _parity_agreement(values, parities) -> tuple[float, int]:
    """Share of readings (server 0/1 with a known parity) that follow «server = first server XOR parity» for
    the better of the two first servers, and how many readings it is measured on."""
    pairs = [(v, p) for v, p in zip(values, parities) if v in (0, 1) and p is not None]
    if not pairs:
        return 0.0, 0
    same = sum(v == p for v, p in pairs)
    return max(same, len(pairs) - same) / len(pairs), len(pairs)


def learn_server(readings: list[dict], profiles: list, min_readings=20, min_corr=0.6, min_agree=0.8,
                 marker_agree=0.7) -> tuple[list, dict]:
    """Who serves in each reading, wherever this broadcast draws its serve marker (09-11: on the Indian Wells and
    Miami 2026 broadcasts the colour-blob rule of serve_marker read no server at all, 0 serve votes).

    The rule of tennis gives the times the serve changes hands (every game: games played mod 2), never who
    serves. The x-bins of the row-difference profile (row_profile) whose value flips with that parity are where
    the marker is; in each reading, the sign of the profile there says which row has it (the marker is drawn
    on the server's row: more salient than the scoreboard's background). The learned marker is kept only when
    its readings follow the alternation (≥ min_agree) on ≥ min_readings readings.

    The per-frame colour marker (reading["server"]) is kept when it follows the alternation (≥ marker_agree: some
    readings fall between a game's end and the marker moving); a marker that does
    not (a coloured flag or panel on one row read as the server) is replaced by the learned one, or dropped.
    Returns (server per reading: 0/1/None, summary for score.json)."""
    n = len(readings)
    par = [serve_parity(r) for r in readings]
    raw = [r.get("server") for r in readings]
    raw_agree, raw_n = _parity_agreement(raw, par)
    summ = {"marker_read": sum(v in (0, 1) for v in raw), "marker_agree": round(raw_agree, 3), "marker_checked": raw_n,
            "learned": False, "learned_agree": None, "learned_checked": 0, "bins": [], "source": "marker"}
    learned = [None] * n
    rows = [i for i, p in enumerate(profiles) if p is not None and par[i] is not None]
    if len(rows) >= min_readings and len({par[i] for i in rows}) == 2:
        P = np.vstack([np.asarray(profiles[i], np.float64) for i in rows])
        z = np.array([1.0 if par[i] == 0 else -1.0 for i in rows])
        corr = np.zeros(P.shape[1])
        for b in range(P.shape[1]):
            ok = np.isfinite(P[:, b])
            if ok.sum() < min_readings or len(set(z[ok])) < 2:
                continue
            x, y = P[ok, b], z[ok]
            if x.std() < 1e-6:
                continue
            corr[b] = float(np.corrcoef(x, y)[0, 1])
        # the marker: every bin that flips with the serve as the strongest one does (the icon right after each name
        # sits at a different x on each row when the names differ in length; both spots flip the same way), at
        # least two bins (a small icon spans a few; one isolated bin is noise)
        best = int(np.argmax(np.abs(corr)))
        sgn = np.sign(corr[best])
        bins = [b for b in range(len(corr)) if corr[b] * sgn >= 0.75 * min_corr]
        if abs(corr[best]) >= min_corr and len(bins) >= 2:
            means = np.full(n, np.nan)
            for i, p in enumerate(profiles):
                if p is not None:
                    v = np.asarray(p, np.float64)[bins]
                    if np.isfinite(v).any():
                        means[i] = float(np.nanmean(v))
            # a reading says who serves only when its difference there is clear (≥ a quarter of the typical one)
            amp = float(np.nanmedian(np.abs(means))) if np.isfinite(means).any() else 0.0
            for i, m in enumerate(means):
                if np.isfinite(m) and amp > 0 and abs(m) >= 0.25 * amp:
                    learned[i] = 0 if m > 0 else 1
            agree, checked = _parity_agreement(learned, par)
            lo, step = PROFILE_BINS[0], PROFILE_BINS[2]
            summ.update(learned_agree=round(agree, 3), learned_checked=checked, corr=round(float(corr[best]), 3),
                        bins=[[round(lo + step * b, 2), round(lo + step * (b + 1), 2)] for b in bins])
            summ["learned"] = checked >= min_readings and agree >= min_agree
    if not summ["learned"]:
        learned = [None] * n
    raw_ok = raw_n >= 6 and raw_agree >= marker_agree
    if raw_ok or (raw_n < 6 and not summ["learned"]):
        out = [v if v is not None else learned[i] for i, v in enumerate(raw)]      # few or good marker readings: as before
        summ["source"] = "marker" + (" + aprendido" if summ["learned"] and any(v is None for v in raw) else "")
    elif summ["learned"]:
        out = learned
        summ["source"] = "aprendido"
    else:
        out = [None] * n
        summ["source"] = "ninguno: el marcador no sigue la alternancia del saque"
    out, summ["alternation"] = by_alternation(readings, out, par, marker=raw if raw_ok else None)
    if summ["alternation"].get("changed") or summ["alternation"].get("filled"):
        summ["source"] += " + alternancia"
    summ["server_read"] = sum(v in (0, 1) for v in out)
    return out, summ


ALTERNATION_MIN = 4          # games with a server in a set before that set's first server is taken from them alone
ALTERNATION_SHARE = 0.6      # the first server must be clear: below this share of agreeing games nothing is changed


def _tiebreak(r: dict) -> bool:
    g = r.get("games") or []
    try:
        return bool(r.get("tiebreak")) or (bool(g) and [int(x) for x in g[-1]] == [6, 6])
    except (TypeError, ValueError):  # esperado: games that are not numbers: not a tie-break
        return False


def by_alternation(readings: list[dict], servers: list, par: list, marker: list | None = None) -> tuple[list, dict]:
    """12-11 (Osaka – Rybakina, B4: 8 of the 9 points «of her serve without her serve» were Osaka's): who serves in
    every game from the rule of tennis, not from each reading. The serve changes hands every game, so one first server
    per set says who serves every game of it. It is voted by games, not by readings: each game votes «server XOR games
    played» with the majority of its readings, those of the colour marker (`marker`, when it follows the alternation)
    when the game has any, since a learned marker misreads whole games (on Osaka the colour marker was read on 57
    readings, 100 % right, the learned one filled 95 more with 87 % right, and 4 of Osaka's 8 service games came out as
    Rybakina's; voted by readings the first server won with only 61 %). A set with fewer than ALTERNATION_MIN games
    voting takes the match's. Each reading with its games read then takes that game's server; tie-break readings (the
    serve changes every two points) and readings without games keep what was read. Nothing changes when the games do
    not agree clearly on a first server (< ALTERNATION_SHARE): the marker is then too unreliable to correct anything.
    Returns (servers, summary)."""
    n = len(readings)
    tb = [_tiebreak(r) for r in readings]
    marker = marker if marker is not None else [None] * n
    ok = lambda v, i: v in (0, 1) and par[i] is not None and not tb[i]
    games: dict = {}                                  # game (games read) → {"set": k, "marker": Counter, "all": Counter}
    for i, r in enumerate(readings):
        if not ok(servers[i], i) and not ok(marker[i], i):
            continue
        key = json.dumps(r.get("games"))
        g = games.setdefault(key, {"set": len(r.get("games") or []), "marker": Counter(), "all": Counter()})
        if ok(marker[i], i):
            g["marker"][marker[i] ^ par[i]] += 1
        if ok(servers[i], i):
            g["all"][servers[i] ^ par[i]] += 1
    votes = [(g["set"], (g["marker"] or g["all"]).most_common(1)[0][0]) for g in games.values()]

    def first(vs):
        c = Counter(v for _, v in vs)
        if not c:
            return None, 0.0, 0
        s0, k = c.most_common(1)[0]
        return s0, k / sum(c.values()), sum(c.values())

    g0, g_share, g_n = first(votes)
    summ = {"first_server": g0, "share": round(g_share, 3), "games": g_n, "changed": 0, "filled": 0, "by_set": {}}
    if g0 is None or g_share < ALTERNATION_SHARE:
        summ["first_server"] = None
        return list(servers), summ
    s0_of = {}
    for k in sorted({k for k, _ in votes}):
        s0, share, m = first([x for x in votes if x[0] == k])
        s0_of[k] = s0 if m >= ALTERNATION_MIN and share >= ALTERNATION_SHARE else g0
        summ["by_set"][str(k)] = {"first_server": s0_of[k], "share": round(share, 3), "games": m}
    out = list(servers)
    for i in range(n):
        if par[i] is None or tb[i]:
            continue
        v = s0_of.get(len(readings[i].get("games") or []), g0) ^ par[i]
        if out[i] is None:
            summ["filled"] += 1
        elif out[i] != v:
            summ["changed"] += 1
        out[i] = v
    return out, summ


def crop_changed(a: np.ndarray | None, b: np.ndarray | None, thresh: float = 20.0, k: int = 5) -> bool:
    """Has the scoreboard region changed between two crops of it? Largest local (k×k) mean of the
    per-pixel difference (strongest colour channel): a new digit, serve marker or banner changes a
    few small spots strongly, while compression noise is weak and spread out."""
    import cv2

    if a is None or b is None or a.shape != b.shape:
        return True
    d = cv2.absdiff(a, b)
    if d.ndim == 3:
        d = d.max(axis=2)
    return float(cv2.blur(d, (k, k)).max()) > thresh


class ScoreReader:
    """Reads the scoreboard of one match; finds it on the first frames where both names appear.

    Once the region is known, the OCR of the region is only repeated when the region's pixels
    changed (crop_changed) or after max_reuse reads that reused it: the scoreboard only changes
    between points, and OCR is the expensive part. The reading is still parsed from each frame
    (the serve marker is looked for in the new crop)."""

    def __init__(self, player_surname: str, opponent_surname: str, relocate_after=6, max_reuse=5, ocr=None):
        if ocr is None:
            from rapidocr_onnxruntime import RapidOCR

            ocr = RapidOCR()
        self.ocr = ocr
        self.names = (player_surname, opponent_surname)
        self.roi = None
        self.misses = 0                 # consecutive reads without the names in the region
        self.full_fails = 0             # consecutive full-frame searches without both names
        self.calls = 0
        self.relocate_after = relocate_after
        self.max_reuse = max_reuse
        self.last = None                # (crop, OCR items) of the last OCR of the region
        self.reused = 0                 # reads since that OCR that reused it
        self.ocr_calls = 0
        self._cls_kw = True             # rapidocr >= 1.3: the angle classifier can be skipped per call

    def _items(self, img, cls=True):
        self.ocr_calls += 1
        if not cls and self._cls_kw:
            try:
                res, _ = self.ocr(img, use_cls=False)
                return res or []
            except TypeError:  # esperado: an OCR version without use_cls: called without it
                self._cls_kw = False
        res, _ = self.ocr(img)
        return res or []

    def locate(self, frame) -> bool:
        self.last = None
        rows = find_rows(self._items(frame), self.names)
        if rows is None:
            return False
        h, w = frame.shape[:2]
        x0, y0, x1, y1 = rows[2]
        roi = (max(0, int(x0)), max(0, int(y0)), min(w, int(x1)), min(h, int(y1)))
        # a scoreboard is a small box near an edge; a statistics panel in a break is big and central
        area = (roi[2] - roi[0]) * (roi[3] - roi[1]) / float(w * h)
        cy = (roi[1] + roi[3]) / 2 / h
        if area > 0.2 or 0.35 < cy < 0.65:
            return False
        self.roi = roi
        return True

    def _roi_items(self, roi):
        if self.last is not None and self.reused < self.max_reuse and not crop_changed(roi, self.last[0]):
            self.reused += 1
            return self.last[1]
        # the scoreboard text is horizontal: the 180° angle classifier is not needed in the region
        items = self._items(roi, cls=False)
        self.last, self.reused = (roi.copy(), items), 0
        return items

    def read(self, frame) -> ScoreState | None:
        self.calls += 1
        if self.roi is None:
            # after many failed full-frame searches (no scoreboard on screen, names not readable),
            # search only one frame in four: OCR of the whole frame is the expensive part
            if self.full_fails > 20 and self.calls % 4:
                return None
            if not self.locate(frame):
                self.full_fails += 1
                return None
            self.full_fails = 0
        x0, y0, x1, y1 = self.roi
        roi = frame[y0:y1, x0:x1]
        st = parse(self._roi_items(roi), self.names, roi)
        if st is None:
            self.misses += 1
            if self.misses >= self.relocate_after:      # moved, resized or was the wrong box: look again
                self.roi, self.misses, self.last = None, 0, None
        else:
            self.misses = 0
        return st


BANNED = {"BREAK", "POINT", "SET", "MATCH", "GAME", "DEUCE", "ADV", "SERVE", "SPEED", "MPH", "KMH", "TIEBREAK",
          "CHALLENGE", "REVIEW", "STATS", "ACES", "WINNERS"}


def opponent_from_items(items: list, player_surname: str) -> str | None:
    """The other name on the scoreboard: an alphabetic word left-aligned with the player's name
    one row above or below it (country codes and captions are excluded)."""
    me = None
    for box, text, _ in items:
        if _is_name(text, player_surname):
            me = (np.asarray(box, float), text)
            break
    if me is None:
        return None
    b0 = me[0]
    x0, h0 = b0[:, 0].min(), b0[:, 1].max() - b0[:, 1].min()
    y0 = b0[:, 1].mean()
    best = None
    for box, text, _ in items:
        b = np.asarray(box, float)
        word = re.sub(r"[^A-Za-zÀ-ÿ\- ]", "", text).strip()
        letters = re.sub(r"[^A-Za-zÀ-ÿ]", "", word)
        if len(letters) < 4 or _norm(word) in BANNED or _is_name(text, player_surname):
            continue
        # 14-11 (Gauff's 10-minute test in the cloud read «Usa»: the box held «C. GAUFF USA»): the surname is the last
        # word with 4 letters or more, never the country code or an initial after it
        tokens = [w for w in word.split() if len(re.sub(r"[^A-Za-zÀ-ÿ]", "", w)) >= 4 and _norm(w) not in BANNED]
        if not tokens:
            continue
        dy = abs(b[:, 1].mean() - y0)
        if 0.6 * h0 <= dy <= 2.6 * h0 and abs(b[:, 0].min() - x0) <= 2.5 * h0:
            if best is None or dy < best[0]:
                best = (dy, tokens[-1])
    return best[1].capitalize() if best else None


def discover_opponent(frames, player_surname: str, need=3) -> str | None:
    """Opponent's surname read from the scoreboard over several frames (majority of readings)."""
    from collections import Counter

    from rapidocr_onnxruntime import RapidOCR

    ocr, votes = RapidOCR(), Counter()
    for frame in frames:
        res, _ = ocr(frame)
        name = opponent_from_items(res or [], player_surname)
        if name:
            votes[_norm(name)] += 1
            if votes.most_common(1)[0][1] >= need:
                break
    return votes.most_common(1)[0][0].capitalize() if votes else None
