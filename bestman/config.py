"""bestman configuration management."""
from pathlib import Path

import yaml

BESTMAN_HOME = Path.home() / ".bestman"

DEFAULT_CONFIG = {
    "voyage": {
        "total_days": 175,
        "default_daily_task": "死虫式 3×10 + 静蹲 2×30秒",
    },
    "profile": {
        "name": "水手",
    },
    "milestones": {},
}


def _deep_merge(base, override):
    """Deep merge override dict into base dict. Returns new dict."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def ensure_home():
    """Create BESTMAN_HOME directory and write default config.yaml if missing."""
    BESTMAN_HOME.mkdir(parents=True, exist_ok=True)
    config_path = BESTMAN_HOME / "config.yaml"
    if not config_path.exists():
        config_path.write_text(yaml.dump(DEFAULT_CONFIG, allow_unicode=True, sort_keys=False))


def load_config():
    """Load configuration, merging user config over defaults."""
    config_path = BESTMAN_HOME / "config.yaml"
    if config_path.exists():
        user_config = yaml.safe_load(config_path.read_text()) or {}
        return _deep_merge(DEFAULT_CONFIG, user_config)
    return dict(DEFAULT_CONFIG)
