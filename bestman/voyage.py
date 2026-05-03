"""Voyage 游戏逻辑 — 连接 config + state + map_engine。

本模块是 bestman 的核心游戏逻辑层，协调：
- 配置（config）
- 状态存储（state）
- 地图渲染（map_engine）
"""

from datetime import date

from bestman.config import BESTMAN_HOME, load_config, get_current_stage
from bestman.state import BestmanState
from bestman.map_engine import MapEngine, get_log_entry


class Voyage:
    """航海游戏逻辑核心。

    连接配置、状态存储和地图渲染引擎，
    提供仪表盘状态、打卡推进、日志查看等功能。
    """

    def __init__(self):
        self.config = load_config()
        self.state = BestmanState()
        # MapEngine uses 0-based positions; convert from 1-based day numbers
        raw_milestones = self.config["voyage"]["milestones"]
        self.map_engine = MapEngine(
            total_days=self.config["voyage"]["total_days"],
            milestones={k - 1: v for k, v in raw_milestones.items()},
        )

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
                "streak": int,
                "skip_tokens": int,
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
            "streak": self.state.get_streak(),
            "skip_tokens": self.state.get_available_skip_tokens(),
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

        原子操作：检查 → 记录 → 日志 → 里程碑。

        Args:
            date_str: 日期字符串 (YYYY-MM-DD)，默认今天

        Returns:
            dict: {
                "success": bool,
                "message": str,       # 结果描述
                "tiles_revealed": int,
                "log_entry": str | None,   # 航海日志文本
                "milestone": str | None,   # 里程碑名称（如果触发）
                "error": str | None,       # 错误信息（如果失败）
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
                "error": "今日已经打卡",
            }

        # 记录（state 参数名是 day）
        self.state.record_day(date_str, completed=1, extra=0)

        # 获取新状态
        tiles_revealed = self.state.get_tiles_revealed()
        current_day = tiles_revealed  # revealed 即 current day

        # 生成日志
        log_entry = get_log_entry(current_day)
        self.state.save_log(date_str, log_entry)

        # 检查里程碑
        milestone = None
        milestones = self.config["voyage"]["milestones"]
        if current_day in milestones:
            milestone = milestones[current_day]

        # 检查连击奖励：连击 7 天发放跳过令牌
        streak = self.state.get_streak(date_str)
        if streak == 7:
            self.state.add_skip_token(date_str)

        return {
            "success": True,
            "message": f"完成！推进了 1 格",
            "tiles_revealed": tiles_revealed,
            "log_entry": log_entry,
            "milestone": milestone,
            "error": None,
        }

    def skip(self, date_str=None) -> dict:
        """使用跳过令牌跳过今日任务，不推进地图。

        消耗一枚跳跃令牌记录今天的训练（维持连击），但不推进 tiles。
        需要连续打卡 7 天方可获得一枚跳过令牌。

        Args:
            date_str: 日期字符串 (YYYY-MM-DD)，默认今天

        Returns:
            dict: {
                "success": bool,
                "message": str,
                "tiles_revealed": int,
                "log_entry": str | None,
                "error": str | None,
            }
        """
        if date_str is None:
            date_str = date.today().isoformat()

        # 检查是否有可用令牌
        tokens = self.state.get_available_skip_tokens()
        if tokens == 0:
            return {
                "success": False,
                "message": "没有可用的跳过令牌。连续打卡 7 天可获得一枚。",
                "tiles_revealed": self.state.get_tiles_revealed(),
                "log_entry": None,
                "error": "没有可用令牌",
            }

        # 使用一枚令牌
        self.state.use_skip_token()

        # 记录为跳过日（不推进 tiles）
        self.state.record_day(date_str, completed=0, extra=0, used_skip=1)

        # 生成跳过日志
        log_entry = "今日使用跳过令牌。船队在避风港暂歇，连击得以延续。明日继续航行。"
        self.state.save_log(date_str, log_entry)

        remaining = self.state.get_available_skip_tokens()

        return {
            "success": True,
            "message": f"已使用一枚跳过令牌。剩余令牌：{remaining} 枚",
            "tiles_revealed": self.state.get_tiles_revealed(),
            "log_entry": log_entry,
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
