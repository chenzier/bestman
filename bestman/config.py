"""bestman configuration management."""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

BESTMAN_HOME = Path.home() / ".bestman"

DEFAULT_CONFIG = {
    "voyage": {
        "theme": "naval",
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
    "events": [
        {
            "id": "tailwind",
            "type": "bonus_tile",
            "probability": 0.15,
            "message": "顺风！海风推着船帆，今天额外航行了1格。",
        },
        {
            "id": "dolphin_escort",
            "type": "encouragement",
            "probability": 0.10,
            "message": "一群海豚出现在船首，伴游了整个上午。它们似乎在为你加油。",
        },
        {
            "id": "starry_night",
            "type": "encouragement",
            "probability": 0.12,
            "message": "今晚的星空格外明亮。北极星就在正前方——你没有偏航。",
        },
        {
            "id": "whale_challenge",
            "type": "challenge",
            "probability": 0.08,
            "message": "远处有鲸群喷水。导航员说：如果今天多做一组深蹲，明天顺风概率翻倍。",
        },
        {
            "id": "treasure_chest",
            "type": "bonus_tile",
            "probability": 0.05,
            "message": "🎁 捞到漂流瓶！瓶中信写着'继续前进'。系统额外+1格。",
        },
    ],
    "profile": {
        "name": "水手",
    },
}


def load_env():
    """从 ~/.bestman/.env 加载环境变量。

    仿 hermes 的 load_hermes_dotenv() 模式。
    用户 .env 优先于项目 .env。
    """
    user_env = BESTMAN_HOME / ".env"
    project_env = Path(__file__).parent.parent / ".env"

    # 用户 .env 优先
    if user_env.exists():
        load_dotenv(dotenv_path=user_env, override=True)
    if project_env.exists():
        load_dotenv(dotenv_path=project_env, override=not user_env.exists())


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
