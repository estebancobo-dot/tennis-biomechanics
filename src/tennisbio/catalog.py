"""Match catalogue (config/matches.yaml) and player profiles (config/players/<id>.yaml)."""
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .config import CONFIG_DIR


@dataclass
class Player:
    id: str
    name: str
    hand: str = "right"
    backhand: str = "two_handed"
    height_m: float = 1.80
    forehand_grip_close_deg: float = 15.0
    backhand_grip_close_deg: float = 0.0
    references: list = field(default_factory=list)    # public videos linked in the report: {u, t, d, stroke}


@dataclass
class Match:
    id: str
    video: Path
    player: Player
    opponent: str = ""
    tournament: str = ""
    date: str = ""
    surface: str = ""
    round: str = ""
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.surface:                    # from the tournament or the file name, when it says which
            self.surface = surface_of(" ".join(str(x) for x in (self.tournament, self.id, getattr(self.video, "name", self.video) or "")))


# the surface of each tournament (public, fixed): the name is read from the tournament field or from
# the video's file name (also transliterated from Cyrillic, e.g. «ЮС Опен» → yusopen / yusipopen)
TOURNAMENT_SURFACE = [
    (r"us ?open|yusi?p?open|flushing", "dura"), (r"australian ?open|avstrali|melbourne", "dura"),
    (r"wimbledon|uimbldon|vimbldon", "hierba"), (r"roland|garros|french ?open|frantsi", "tierra batida"),
    (r"indian ?wells|miami|cincinnati|montreal|toronto|canadian|beijing|pekin|wuhan|doha|dubai|abu ?dhabi|brisbane|adelaide|"
     r"tokyo|tokio|wta ?finals|itogovy|guadalajara|san ?diego|washington|ostrava|linz", "dura"),
    (r"madrid|roma\b|rome|internazionali|stuttgart|shtutgart|charleston|strasbourg|rabat|parma", "tierra batida"),
    (r"eastbourne|berlin|bad ?homburg|hertogenbosch|birmingham|nottingham|queen", "hierba"),
]


def surface_of(text: str) -> str:
    import re
    t = ascii_id(text).lower().replace("-", " ").replace("_", " ") if text else ""
    for rx, s in TOURNAMENT_SURFACE:
        if re.search(rx, t) or re.search(rx, t.replace(" ", "")):
            return s
    return ""


def load_player(player_id: str, config_dir: Path = CONFIG_DIR) -> Player:
    data = yaml.safe_load((config_dir / "players" / f"{player_id}.yaml").read_text(encoding="utf-8-sig")) or {}
    known = set(Player.__dataclass_fields__)
    return Player(id=player_id, **{k: v for k, v in data.items() if k in known})


def load_matches(cfg: dict, config_dir: Path = CONFIG_DIR) -> list[Match]:
    path = config_dir / "matches.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Falta {path}: copia config/matches.example.yaml y rellénalo")
    videos = Path(cfg.get("paths", {}).get("videos", "."))
    out = []
    for m in yaml.safe_load(path.read_text(encoding="utf-8-sig"))["matches"]:
        m = dict(m)
        known = {k: m.pop(k) for k in ("opponent", "tournament", "date", "surface", "round") if k in m}
        mid, video, player = m.pop("id"), m.pop("video"), m.pop("player")
        out.append(Match(id=str(mid), video=videos / video, player=load_player(player, config_dir),
                         **{k: str(v) for k, v in known.items()}, extra=m))
    return out


_CYR = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюяіїєґ",
                ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t",
                 "u", "f", "kh", "ts", "ch", "sh", "shch", "", "y", "", "e", "yu", "ya", "i", "yi", "ye", "g"]))


def ascii_id(name: str, n: int = 60, default: str = "partido") -> str:
    """ASCII id for folders and files: accents removed ("Świątek" → "swiatek"), Cyrillic
    transliterated ("Рыбакина" → "rybakina"). On Windows, OpenCV cannot open non-ASCII paths."""
    import re
    import unicodedata

    # dashes, dots and any other non-letter become separators before the accents are dropped
    t = "".join(_CYR.get(c, c) if (c.isalnum() or c in _CYR) else " " for c in name.lower().replace("ł", "l"))
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:n].strip("-") or default
