"""bestman configuration management."""
from pathlib import Path

import yaml

BESTMAN_HOME = Path.home() / ".bestman"

DEFAULT_CONFIG = {
    "voyage": {
        "total_days": 175,
        "end_date": "2026-10-25",
        "default_daily_task": "死虫式 3×10 + 静蹲 2×30秒",
        "milestones": {
            25: "穿越迷雾之海",
            50: "进入季风带",
            75: "抵达贸易港",
            100: "穿过赤道无风带",
            125: "遇见信风",
            150: "望见新大陆海岸线",
            175: "抵达新大陆",
        },
        "stages": [
            {"name": "启航", "days": [1, 25]},
            {"name": "迷雾之海", "days": [26, 50]},
            {"name": "季风带", "days": [51, 75]},
            {"name": "贸易航线", "days": [76, 100]},
            {"name": "赤道无风带", "days": [101, 125]},
            {"name": "信风带", "days": [126, 150]},
            {"name": "新大陆近海", "days": [151, 175]},
        ],
    },
    "profile": {
        "name": "水手",
    },
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


def get_current_stage(day, config):
    """Return current stage info for the given day.

    Args:
        day: Current day number (1-based).
        config: Full configuration dict.

    Returns:
        dict: {"name": str, "start": int, "end": int}
    """
    stages = config.get("voyage", {}).get("stages", [])
    for stage in stages:
        start, end = stage["days"]
        if start <= day <= end:
            return {"name": stage["name"], "start": start, "end": end}
    if stages:
        last = stages[-1]
        return {"name": last["name"], "start": last["days"][0], "end": last["days"][1]}
    return {"name": "未知", "start": 1, "end": 175}
