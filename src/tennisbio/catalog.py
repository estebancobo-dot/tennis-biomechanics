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


def load_player(player_id: str, config_dir: Path = CONFIG_DIR) -> Player:
    data = yaml.safe_load((config_dir / "players" / f"{player_id}.yaml").read_text(encoding="utf-8"))
    return Player(id=player_id, **data)


def load_matches(cfg: dict, config_dir: Path = CONFIG_DIR) -> list[Match]:
    path = config_dir / "matches.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Falta {path}: copia config/matches.example.yaml y rellénalo")
    videos = Path(cfg.get("paths", {}).get("videos", "."))
    out = []
    for m in yaml.safe_load(path.read_text(encoding="utf-8"))["matches"]:
        m = dict(m)
        known = {k: m.pop(k) for k in ("opponent", "tournament", "date", "surface", "round") if k in m}
        mid, video, player = m.pop("id"), m.pop("video"), m.pop("player")
        out.append(Match(id=str(mid), video=videos / video, player=load_player(player, config_dir),
                         **{k: str(v) for k, v in known.items()}, extra=m))
    return out
