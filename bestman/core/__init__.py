"""bestman core — 纯游戏逻辑，零终端/UI 依赖。

Provides:
- Voyage: 游戏逻辑核心，协调 config + state + map_engine + llm
- BestmanState: SQLite 状态管理
- MapEngine: 2D 地图引擎（纯逻辑，不含渲染）
- EventEngine: 随机事件引擎
- LLMClient: OpenAI 兼容 LLM 客户端
- Config helpers: load_config, save_config, load_plan, save_plan, etc.
"""

from bestman.core.config import (  # noqa: F401
    BESTMAN_HOME,
    DEFAULT_CONFIG,
    PLAN_PATH,
    ensure_home,
    get_current_stage,
    get_dice_mode,
    load_config,
    load_env,
    load_plan,
    save_config,
    save_plan,
)
from bestman.core.events import DEFAULT_EVENTS, EventEngine  # noqa: F401
from bestman.core.llm import (  # noqa: F401
    COACH_SYSTEM_PROMPT,
    PLAN_GENERATOR_SYSTEM_PROMPT,
    LLMClient,
    chat_with_coach,
    generate_plan,
    generate_voyage_log,
    review_summary,
    weigh_comment,
)
from bestman.core.map_engine import GRID_WIDTH, GRID_HEIGHT, MapEngine, get_log_entry  # noqa: F401
from bestman.core.state import BestmanState  # noqa: F401
from bestman.core.voyage import Voyage  # noqa: F401
