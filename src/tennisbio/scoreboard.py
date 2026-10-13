"""TV scoreboard reading (phase 3): sets, games, points and pressure situations.

OCR with RapidOCR (PaddleOCR models in ONNX Runtime, works on Windows CPU). The scoreboard is
found once per match by looking for both players' surnames; afterwards only that region is read.
Each row: NAME [country] set games... current games [points]. Digits of the set columns often come
glued together by the OCR ("472"), and set scores are single digits, so they are split one by one.
"""
import difflib
import re
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
    abbreviation some broadcasters use (RYB, SAB)."""
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
    hits = [0.0, 0.0]
    for i in range(1, n):
        x, y, w, h, area = st[i]
        if area < min_area or h > 0.8 * gap or w > 3 * gap:     # banners and big panels are not markers
            continue
        for k, ry in enumerate(rows_y):
            if abs(cen[i][1] - ry) < 0.35 * gap:
                hits[k] += area
    if max(hits) == 0 or min(hits) > 0.5 * max(hits):
        return None
    return int(np.argmax(hits))


def parse(items: list, surnames: tuple[str, str], image: np.ndarray | None = None) -> ScoreState | None:
    """Score state from OCR items of the scoreboard region (any coordinates); with the region
    image, also who serves."""
    rows = find_rows(items, surnames)
    if rows is None:
        return None
    y_p, y_o, _ = rows
    tol = abs(y_p - y_o) * 0.45 or 10
    banner = ""
    cells = {0: [], 1: []}
    name_x = {}
    for box, text, _ in items:
        x, y = _center(box)
        up = _norm(text)
        if "BREAK" in up or "SETPOINT" in up or "MATCHPOINT" in up or "CHAMPIONSHIP" in up:
            banner = "BREAK POINT" if "BREAK" in up else "MATCH POINT" if ("MATCH" in up or "CHAMP" in up) else "SET POINT"
            continue
        for k, yr in enumerate((y_p, y_o)):
            if abs(y - yr) <= tol:
                if _is_name(text, surnames[k]):
                    name_x[k] = x
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
    return ScoreState(games, pts, banner, server, flags)


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
            except TypeError:
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
        dy = abs(b[:, 1].mean() - y0)
        if 0.6 * h0 <= dy <= 2.6 * h0 and abs(b[:, 0].min() - x0) <= 2.5 * h0:
            if best is None or dy < best[0]:
                best = (dy, word.split()[-1])
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
