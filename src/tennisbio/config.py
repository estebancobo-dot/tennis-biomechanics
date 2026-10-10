"""Load config/default.yaml merged with the untracked config/local.yaml."""
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(config_dir: Path = CONFIG_DIR) -> dict:
    cfg = yaml.safe_load((config_dir / "default.yaml").read_text(encoding="utf-8"))
    local = config_dir / "local.yaml"
    if local.exists():
        cfg = _merge(cfg, yaml.safe_load(local.read_text(encoding="utf-8")) or {})
    return cfg
