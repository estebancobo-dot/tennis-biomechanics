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
    t, n = _norm(text), _norm(surname)
    if not t or not n:
        return False
    if n in t:
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


class ScoreReader:
    """Reads the scoreboard of one match; finds it on the first frames where both names appear."""

    def __init__(self, player_surname: str, opponent_surname: str):
        from rapidocr_onnxruntime import RapidOCR

        self.ocr = RapidOCR()
        self.names = (player_surname, opponent_surname)
        self.roi = None

    def _items(self, img):
        res, _ = self.ocr(img)
        return res or []

    def locate(self, frame) -> bool:
        rows = find_rows(self._items(frame), self.names)
        if rows is None:
            return False
        h, w = frame.shape[:2]
        x0, y0, x1, y1 = rows[2]
        self.roi = (max(0, int(x0)), max(0, int(y0)), min(w, int(x1)), min(h, int(y1)))
        return True

    def read(self, frame) -> ScoreState | None:
        if self.roi is None and not self.locate(frame):
            return None
        x0, y0, x1, y1 = self.roi
        roi = frame[y0:y1, x0:x1]
        return parse(self._items(roi), self.names, roi)
