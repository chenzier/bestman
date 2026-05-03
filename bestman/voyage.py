"""Voyage 游戏逻辑 — 连接 config + state + map_engine + llm。

本模块是 bestman 的核心游戏逻辑层，协调：
- 配置（config）
- 状态存储（state）
- 地图渲染（map_engine）
- LLM 日志生成（llm）
"""

import os
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

    def complete(self, date_str=None) -> dict:
        """完成今日任务，推进一格。

        原子操作：检查 → 记录 → LLM 日志（fallback 模板） → 里程碑。

        Args:
            date_str: 日期字符串 (YYYY-MM-DD)，默认今天

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
            }

        # 记录（state 参数名是 day）
        self.state.record_day(date_str, completed=1, extra=0)

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
            # 确定性 fallback：产品不能崩
            log_entry = get_log_entry(current_day)

        self.state.save_log(date_str, log_entry)

        # 检查里程碑
        milestone = None
        milestones = self.config["voyage"]["milestones"]
        if current_day in milestones:
            milestone = milestones[current_day]

        # 检查随机事件
        event = self.event_engine.check(current_day)
        if event:
            if event["type"] == "bonus_tile":
                self.state.record_day(date_str + "_bonus", completed=0, extra=1)
                tiles_revealed += 1
            self.state.save_log(date_str, event["message"], event_type="event")

        return {
            "success": True,
            "message": "完成！推进了 1 格",
            "tiles_revealed": tiles_revealed,
            "log_entry": log_entry,
            "milestone": milestone,
            "event": event,
            "error": None,
            "llm_used": llm_used,
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
