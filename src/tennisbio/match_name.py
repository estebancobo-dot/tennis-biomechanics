"""What a video's file name says about its match (11-11, R6 of the review of the Base, #226; the start of #258).

The catalogue (scripts/auto_catalog.py) wrote only the id, the video and the player: on 11-11 the 6 matches of the
registry had no rival and their library folders were all «sin-fecha», although the names say it, e.g.
«US Open 2026.R4.Naomi Osaka - Elena Rybakina.ts» or «Теннис.ЮСИПОПЕН.Финал.Соболенко—Рыбакина.12.09.2026…mkv».
`parse` reads the tournament, the date (a full date, else the year), the round and the two players; the rival is the
player who is not the analysed one. Only what the name says: the rest stays empty (#258 will look it up)."""
from __future__ import annotations

import re
import unicodedata

CYR = {"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i", "й": "y",
       "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
       "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya"}

TOURNAMENTS = [
    ("US Open", r"\bus\s*open\b|юсипопен|юс\s*опен|yusipopen"), ("Australian Open", r"australian\s*open|\bao\b|австрали"),
    ("Roland Garros", r"roland\s*garros|french\s*open|ролан"), ("Wimbledon", r"wimbledon|уимблдон"),
    ("Indian Wells", r"indian\s*wells"), ("Miami", r"\bmiami\b|майами"), ("Madrid", r"\bmadrid\b|мадрид"),
    ("Roma", r"\brome\b|\broma\b|internazionali"), ("Cincinnati", r"cincinnati"), ("Montreal", r"montreal"),
    ("Toronto", r"toronto"), ("Beijing", r"beijing|пекин"), ("Wuhan", r"wuhan"), ("Dubai", r"\bdubai\b"),
    ("Doha", r"\bdoha\b"), ("Stuttgart", r"stuttgart"), ("Berlin", r"\bberlin\b"), ("WTA Finals", r"wta\s*finals"),
    ("ATP Finals", r"atp\s*finals"), ("Brisbane", r"brisbane"), ("Adelaide", r"adelaide"), ("Eastbourne", r"eastbourne"),
]
ROUNDS = [  # checked in this order: «полуфинал» and «semi final» contain «финал» / «final»
    ("QF", r"quarter[\s-]*finals?|cuartos|четвертьфинал|\bqf\b"), ("SF", r"semi[\s-]*finals?|semifinal|полуфинал|\bsf\b"),
    ("F", r"\bfinals?\b|финал|\bfinal\b"),
]
FILLER = r"^(tennis|теннис|tenis|wta|atp|\d{3,4}[pр]|\d+fps|мосгортранс|full\s*match|highlights)$"


def translit(s: str) -> str:
    out = []
    for c in s:
        t = CYR.get(c.lower())
        out.append(c if t is None else (t.capitalize() if c.isupper() else t))
    return "".join(out)


def _ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", translit(s)).encode("ascii", "ignore").decode().lower()


def _round(text: str) -> str:
    low = text.lower()
    m = re.search(r"\b(?:r|round\s*of\s*)(\d{1,3})\b", low)
    for code, pat in ROUNDS:
        if re.search(pat, low):
            return code
    return f"R{m.group(1)}" if m else ""


def _tournament(text: str) -> str:
    low = text.lower()
    return next((name for name, pat in TOURNAMENTS if re.search(pat, low)), "")


def _date(text: str) -> str:
    m = re.search(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/](20\d{2})\b", text)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    m = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", text)
    if m:
        return m.group(0)
    m = re.search(r"(?<!\d)(20\d{2})(?!\d)", text)
    return m.group(1) if m else ""


def _is_name(seg: str) -> bool:
    s = seg.strip()
    if not s or re.search(r"\d", s) or re.match(FILLER, s.lower()):
        return False
    if _tournament(s) or _round(s):
        return False
    return bool(re.fullmatch(r"[^\W\d_]+(?:[\s'’-][^\W\d_]+){0,3}", s))


def players(stem: str) -> list[str]:
    """The two players of a file name: the names on each side of the first separator between two names (« - », «—»,
    «–»), each side cut at its dots («US Open 2026.R4.Naomi Osaka - Elena Rybakina»)."""
    parts = [p for p in re.split(r"\s+-\s+|\s*[—–]\s*", stem) if p.strip()]
    segs = [[x.strip() for x in re.split(r"[._]", p) if x.strip()] for p in parts]
    for a, b in zip(segs, segs[1:]):
        if a and b and _is_name(a[-1]) and _is_name(b[0]):
            return [a[-1], b[0]]
    return []                  # no two names around a separator: none (never «Prueba» and «App» from prueba_app_35m)


def _display(name: str) -> str:
    t = translit(name)
    return " ".join(w[:1].upper() + w[1:] for w in t.split())


def parse(stem: str, player_name: str = "", player_id: str = "") -> dict:
    """{tournament, date, round, players, opponent} of a file name (empty strings for what it does not say)."""
    ps = players(stem)
    keys = {k for k in (_ascii(player_id),) if k} | ({_ascii(player_name.split()[-1])} if player_name.strip() else set())
    other = [p for p in ps if not (set(_ascii(p).replace("-", " ").split()) & keys)]
    return {"tournament": _tournament(stem), "date": _date(stem), "round": _round(stem),
            "players": [_display(p) for p in ps], "opponent": _display(other[0]) if len(ps) == 2 and len(other) == 1 else ""}
