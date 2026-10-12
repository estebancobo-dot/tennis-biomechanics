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


def load_config(config_dir: Path = CONFIG_DIR) -> dict:
    cfg = yaml.safe_load((config_dir / "default.yaml").read_text(encoding="utf-8"))
    local = config_dir / "local.yaml"
    if local.exists():
        cfg = _merge(cfg, yaml.safe_load(local.read_text(encoding="utf-8-sig")) or {})
    return cfg
