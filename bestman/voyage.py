"""Voyage 游戏逻辑 — 连接 config + state + map_engine + llm。

本模块是 bestman 的核心游戏逻辑层，协调：
- 配置（config）
- 状态存储（state）
- 地图渲染（map_engine）
- LLM 日志生成（llm）
"""

import hashlib
import os
import random
from datetime import date

from bestman.config import BESTMAN_HOME, load_config, get_current_stage, load_env
from bestman.state import BestmanState
from bestman.map_engine import MapEngine, get_log_entry
from bestman.events import EventEngine
from bestman.llm import LLMClient, generate_voyage_log, chat_with_coach


class Voyage:
    """航海游戏逻辑核心。

    连接配置、状态存储、地图渲染引擎和 LLM，
    提供仪表盘状态、打卡推进、日志查看、教练对话等功能。
    """

    def __init__(self):
        load_env()
        self.config = load_config()

        self.llm = LLMClient(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        )

        self.state = BestmanState()
        # MapEngine uses 0-based positions; convert from 1-based day numbers
        raw_milestones = self.config["voyage"]["milestones"]
        self.map_engine = MapEngine(
            total_days=self.config["voyage"]["total_days"],
            milestones={k - 1: v for k, v in raw_milestones.items()},
        )
        self.event_engine = EventEngine(self.config)

    def get_status(self) -> dict:
        """获取当前航行状态。

        Returns:
            dict: {
                "tiles_revealed": int,
                "current_day": int,     # 1-based，revealed + 1
                "total_days": int,
                "remaining": int,
                "stage": dict,          # {"name": str, "start": int, "end": int}
                "today_done": bool,
                "completed_days": int,
            }
        """
        tiles_revealed = self.state.get_tiles_revealed()
        total_days = self.config["voyage"]["total_days"]
        current_day = tiles_revealed + 1
        remaining = max(0, total_days - tiles_revealed)
        stage = get_current_stage(min(current_day, total_days), self.config)

        return {
            "tiles_revealed": tiles_revealed,
            "current_day": current_day,
            "total_days": total_days,
            "remaining": remaining,
            "stage": stage,
            "today_done": self.state.today_recorded(),
            "completed_days": self.state.get_completed_days(),
        }

    def get_daily_task(self) -> str:
        """获取今日任务描述。

        Returns:
            str: 任务描述
        """
        return self.config["voyage"]["default_daily_task"]

    def render_map(self) -> str:
        """渲染像素地图。

        Returns:
            str: Rich markup 地图字符串
        """
        return self.map_engine.render(self.state.get_tiles_revealed())

    def _roll_distance(self, day_seed):
        """掷骰子，决定今日航行距离。

        使用 date_str hash 作为种子，保证同一天掷骰结果确定（可重放）。

        Args:
            day_seed: 种子字符串（日期）

        Returns:
            tuple: (distance: int, description: str)
        """
        dice_config = self.config.get("dice", {})
        weights = dice_config.get("weights", [60, 30, 10])
        descriptions = dice_config.get("descriptions", {
            1: "风平浪静，缓缓前行",
            2: "顺风满帆，航行两格",
            3: "暴风助力，航行三格！",
        })

        seed = int(hashlib.md5(str(day_seed).encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        roll = rng.random()

        w1 = weights[0] / 100
        w2 = (weights[0] + weights[1]) / 100
        if roll < w1:
            return 1, descriptions[1]
        elif roll < w2:
            return 2, descriptions[2]
        else:
            return 3, descriptions[3]

    def _get_distance_description(self, distance):
        """Get description text for a given distance value.

        Args:
            distance: Distance value (1, 2, or 3).

        Returns:
            str: Description text from config.
        """
        dice_config = self.config.get("dice", {})
        descriptions = dice_config.get("descriptions", {
            1: "风平浪静，缓缓前行",
            2: "顺风满帆，航行两格",
            3: "暴风助力，航行三格！",
        })
        return descriptions.get(distance, f"航行 {distance} 格")

    def complete(self, date_str=None, extra_tiles=0, distance=None) -> dict:
        """完成今日任务，掷骰子推进。

        原子操作：检查 → 掷骰 → 记录 → LLM 日志（fallback 模板） → 里程碑。

        Args:
            date_str: 日期字符串 (YYYY-MM-DD)，默认今天
            extra_tiles: 额外推进格数（-e 参数叠加）
            distance: 互动模式下由 CLI 传入的掷骰结果。传入时跳过 _roll_distance()。

        Returns:
            dict: {
                "success": bool,
                "message": str,
                "tiles_revealed": int,
                "log_entry": str | None,   # 航海日志文本
                "milestone": str | None,   # 里程碑名称（如果触发）
                "event": dict | None,      # 触发的事件（如果触发）
                "error": str | None,       # 错误信息（如果失败）
                "llm_used": bool,          # 是否使用了 LLM 生成日志
                "dice": dict | None,       # 掷骰结果
            }
        """
        if date_str is None:
            date_str = date.today().isoformat()

        # 检查是否已记录
        if self.state.today_recorded(date_str):
            return {
                "success": False,
                "message": "今日已经完成过了",
                "tiles_revealed": self.state.get_tiles_revealed(),
                "log_entry": None,
                "milestone": None,
                "event": None,
                "error": "今日已经打卡",
                "llm_used": False,
                "dice": None,
            }

        # 掷骰子 + 手动超额
        old_tiles = self.state.get_tiles_revealed()
        if distance is not None:
            # 互动模式：距离由 CLI 传入
            description = self._get_distance_description(distance)
        else:
            distance, description = self._roll_distance(date_str)
        total_advance = distance + extra_tiles

        # 记录
        self.state.record_day(date_str, completed=total_advance, extra=0)

        # 获取新状态
        tiles_revealed = self.state.get_tiles_revealed()
        current_day = tiles_revealed  # revealed 即 current day

        # 生成日志：优先 LLM，不可用时 fallback 到模板
        stage_name = get_current_stage(current_day, self.config)["name"]
        remaining = max(0, self.config["voyage"]["total_days"] - current_day)
        task_done = self.config["voyage"]["default_daily_task"]

        llm_used = False
        log_entry = generate_voyage_log(
            self.llm, stage_name, remaining, current_day, task_done
        )
        if log_entry is not None:
            llm_used = True
        else:
            log_entry = get_log_entry(current_day)

        self.state.save_log(date_str, log_entry)

        # 检测跨越的里程碑（可能一次跨越多个）
        milestone = None
        milestones = self.config["voyage"]["milestones"]
        crossed = [m_name for m_day, m_name in milestones.items()
                    if old_tiles < m_day <= tiles_revealed]
        if crossed:
            milestone = " | ".join(crossed)

        # 检查随机事件
        event = self.event_engine.check(current_day)
        if event:
            if event["type"] == "bonus_tile":
                self.state.record_day(date_str + "_bonus", completed=0, extra=1)
                tiles_revealed += 1
            self.state.save_log(date_str, event["message"], event_type="event")

        return {
            "success": True,
            "message": f"🎲 掷出：{description}！航行 {total_advance} 海里",
            "tiles_revealed": tiles_revealed,
            "log_entry": log_entry,
            "milestone": milestone,
            "event": event,
            "error": None,
            "llm_used": llm_used,
            "dice": {
                "distance": distance,
                "description": description,
                "extra_tiles": extra_tiles,
            },
        }

    def talk(self, user_message) -> dict:
        """与 AI 导航员对话。

        Args:
            user_message: 水手的消息

        Returns:
            dict: {
                "success": bool,
                "response": str,
                "error": str | None,
            }
        """
        if not self.llm.available:
            return {
                "success": False,
                "response": "导航员正在休息。请先配置 LLM（~/.bestman/.env）。",
                "error": "LLM 未配置",
            }

        status = self.get_status()
        context = {
            "current_day": status["current_day"],
            "stage_name": status["stage"]["name"],
            "remaining": status["remaining"],
            "today_done": status["today_done"],
            "today_task": self.get_daily_task(),
            "completed_days": status["completed_days"],
        }

        reply = chat_with_coach(self.llm, user_message, context)
        if reply is None:
            return {
                "success": False,
                "response": "导航员暂时无法回应。海风太大，信号不好...",
                "error": "LLM 请求失败",
            }

        return {
            "success": True,
            "response": reply,
            "error": None,
        }

    def get_logs(self, limit=10) -> list[dict]:
        """获取最近的航海日志。

        Args:
            limit: 返回条数上限

        Returns:
            list[dict]: 日志条目列表
        """
        return self.state.get_logs(limit)

    @staticmethod
    def is_initialized() -> bool:
        """检查 bestman 是否已初始化。

        Returns:
            bool: BESTMAN_HOME 目录是否存在
        """
        return BESTMAN_HOME.is_dir()
