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


CATALOG_FIELDS = ("opponent", "tournament", "date", "surface", "round")
TEST_INFO = "partido.json"             # what a test run knew of its match (catalogue entry or command line)


def catalog_entry(cfg: dict, source_name: str | None = None, match_id: str | None = None,
                  config_dir: Path = CONFIG_DIR) -> Match | None:
    """The entry of config/matches.yaml for a video: by its file name (also compared as an ASCII id,
    so a transliterated copy matches) or by the id of a test run (smoke_<ascii name>). None when there
    is no catalogue, it cannot be read or no entry matches (a test run must still run)."""
    try:
        entries = load_matches(cfg, config_dir)
    except Exception:                     # no catalogue, a broken one or a missing player profile
        return None
    for m in entries:
        vname = Path(str(m.video)).name
        if source_name and (vname == Path(source_name).name
                            or ascii_id(Path(vname).stem) == ascii_id(Path(source_name).stem)):
            return m
        if match_id and match_id in (m.id, f"smoke_{ascii_id(Path(vname).stem, 40)}"):
            return m
    return None


def trial_match(match_id: str, video: Path, player: Player, cfg: dict, source: Path | None = None,
               match_dir: Path | None = None, config_dir: Path = CONFIG_DIR, **given) -> Match:
    """The Match of a test run (scripts/smoke_test.py, recompute_measures.py, rebuild_report.py).
    Its data (rival, tournament, date, surface, round) come, in this order, from what the command line
    gives (non-empty values of `given`), the catalogue entry of its video, and what the run saved in
    <match_dir>/partido.json (the command line of the run that cut the clip); what is still missing
    is inferred from the names (Match)."""
    import json

    fields, extra = {}, {}
    info = (match_dir / TEST_INFO) if match_dir else None
    if info is not None and info.exists():
        try:
            saved = json.loads(info.read_text(encoding="utf-8"))
            fields.update({k: str(v) for k, v in saved.items() if k in CATALOG_FIELDS and v})
        except (OSError, ValueError, AttributeError):
            pass
    entry = catalog_entry(cfg, source.name if source else None, match_id, config_dir)
    if entry is not None:
        fields.update({k: getattr(entry, k) for k in CATALOG_FIELDS if getattr(entry, k)})
        extra = dict(entry.extra)
    fields.update({k: str(v) for k, v in given.items() if k in CATALOG_FIELDS and v})
    return Match(match_id, video, player, extra=extra, **fields)


def save_test_info(match: Match, match_dir: Path) -> None:
    """Remembers the data of a test run's match next to its outputs (for later recomputations)."""
    import json

    match_dir.mkdir(parents=True, exist_ok=True)
    (match_dir / TEST_INFO).write_text(json.dumps({k: getattr(match, k) for k in CATALOG_FIELDS}, ensure_ascii=False, indent=1),
                                       encoding="utf-8")


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
