"""Load config/default.yaml merged with the untracked config/local.yaml."""
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
ROOT = CONFIG_DIR.parent


def resolve_path(p: str | Path | None) -> Path | None:
    """A path from the config: relative paths are relative to the repository, not to the current
    directory (scripts may be launched from anywhere)."""
    if not p:
        return None
    p = Path(p)
    return p if p.is_absolute() else ROOT / p


def model_state(p: str | Path | None) -> str | None:
    """Fingerprint of a model file (missing → None), so adding or replacing a model re-runs its stage."""
    f = resolve_path(p)
    if f is None or not f.exists():
        return None
    st = f.stat()
    return f"{st.st_size}-{int(st.st_mtime)}"


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def default_player(cfg: dict | None = None, config_dir: Path = CONFIG_DIR) -> str:
    """The player analysed by default: `player` of the configuration (an id of config/players), else the
    only (or first) player configured. Scripts and the application never write a player's name in code."""
    cfg = cfg if cfg is not None else load_config(config_dir)
    if cfg.get("player"):
        return str(cfg["player"])
    ids = sorted(p.stem for p in (config_dir / "players").glob("*.yaml"))
    if not ids:
        raise RuntimeError("No hay ninguna jugadora en config/players/")
    return ids[0]


def player_surname(player_id: str | None = None, config_dir: Path = CONFIG_DIR) -> str:
    """Surname of a configured player (the default one when no id): «Rybakina» from «Elena Rybakina», as the
    datasets and the searches write it."""
    import yaml
    pid = player_id or default_player(config_dir=config_dir)
    data = yaml.safe_load((config_dir / "players" / f"{pid}.yaml").read_text(encoding="utf-8")) or {}
    return str(data.get("name") or pid).split()[-1]


def load_config(config_dir: Path = CONFIG_DIR) -> dict:
    cfg = yaml.safe_load((config_dir / "default.yaml").read_text(encoding="utf-8"))
    local = config_dir / "local.yaml"
    if local.exists():
        cfg = _merge(cfg, yaml.safe_load(local.read_text(encoding="utf-8-sig")) or {})
    return cfg
