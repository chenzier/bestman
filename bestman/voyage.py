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
        self.map_engine = MapEngine(self.config)
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
                "streak": int,
                "skip_tokens": int,
                "coins": int,
                "treasures": list[dict],
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
            "region": self.map_engine.get_region_at(tiles_revealed),
            "today_done": self.state.today_recorded(),
            "completed_days": self.state.get_completed_days(),
            "streak": self.state.get_streak(),
            "skip_tokens": self.state.get_available_skip_tokens(),
            "coins": self.state.get_total_coins(),
            "treasures": self.state.get_treasures(),
        }

    def get_daily_task(self) -> str:
        """获取今日任务描述。

        Returns:
            str: 任务描述
        """
        return self.config["voyage"]["default_daily_task"]

    def render_map(self, today_advance=0, sway_offset=0.0) -> str:
        """渲染像素地图。

        Args:
            today_advance: 今日推进格数，用于高亮今天的足迹。
            sway_offset: 摇摆幅度，用于船体摇晃动画。

        Returns:
            str: Rich markup 地图字符串
        """
        return self.map_engine.render(self.state.get_tiles_revealed(),
                                      today_advance=today_advance,
                                      sway_offset=sway_offset)

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

    def complete(self, date_str=None, extra_tiles=0, force=False, distance=None) -> dict:
        """完成今日任务，掷骰子推进。

        原子操作：检查 → 掷骰 → 金币计算 → 记录 → LLM 日志（fallback 模板） → 里程碑 → 事件 → 宝藏记录。

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
                "coins": dict | None,      # 金币获取详情
                "treasures": list | None,  # 发现的宝藏列表
            }
        """
        if date_str is None:
            date_str = date.today().isoformat()

        # 检查是否已记录（-f/--force 跳过）
        if not force and self.state.today_recorded(date_str):
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
                "coins": None,
                "treasures": None,
            }

        # -f/--force：删除今日旧记录
        if force:
            self.state.delete_day(date_str)

        # 掷骰子 + 手动超额
        old_tiles = self.state.get_tiles_revealed()
        if distance is not None:
            # 互动模式：距离由 CLI 传入
            description = self._get_distance_description(distance)
        else:
            distance, description = self._roll_distance(date_str)
        total_advance = distance + extra_tiles

        # ── 金币与宝藏 ──
        coins_config = self.config.get("coins", {})
        coins_breakdown = {}
        discovered_treasures = []

        # 每日完成
        daily_coins = coins_config.get("daily_complete", 10)
        coins_breakdown["每日打卡"] = daily_coins

        # 骰子 3 格奖励
        if distance == 3:
            dice_bonus = coins_config.get("dice_3", 5)
            coins_breakdown["暴风加成"] = dice_bonus

        # 手动超额
        if extra_tiles > 0:
            extra_coins = coins_config.get("extra_per_tile", 5) * extra_tiles
            coins_breakdown["额外推进"] = extra_coins

        # 显式宝藏检测（基于掷骰推进，不含 bonus 事件）
        treasures_config = self.config.get("treasures", {})
        new_tiles_from_advance = old_tiles + total_advance
        for treasure in treasures_config.get("explicit", []):
            pos = treasure["position"]
            if old_tiles < pos <= new_tiles_from_advance:
                discovered_treasures.append({
                    "name": treasure["name"],
                    "type": "explicit",
                    "coins": treasure["coins"],
                    "message": treasure["message"],
                })

        # 隐式宝藏检测（确定性随机，基于日期种子）
        implicit_config = treasures_config.get("implicit", {})
        if implicit_config:
            seed = int(hashlib.md5(str(date_str + "_treasure_imp").encode()).hexdigest()[:8], 16)
            rng = random.Random(seed)
            if rng.random() < implicit_config.get("probability", 0.08):
                pool = implicit_config.get("pool", [])
                if pool:
                    implicit_treasure = rng.choice(pool)
                    discovered_treasures.append({
                        "name": implicit_treasure["name"],
                        "type": "implicit",
                        "coins": implicit_treasure["coins"],
                        "message": implicit_treasure["message"],
                    })

        # 汇总当前已确定金币（不含里程碑/连击，这两项待后续计算）
        pre_coins = sum(coins_breakdown.values())
        for t in discovered_treasures:
            pre_coins += t["coins"]

        # 记录（先写入基础金币，里程碑和连击在后处理中更新）
        self.state.record_day(date_str, completed=total_advance, extra=0, coins_earned=pre_coins)

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
                # 检查 bonus tile 是否跨过更多里程碑
                crossed_after = [m_name for m_day, m_name in milestones.items()
                                 if old_tiles < m_day <= tiles_revealed]
                if crossed_after != crossed:
                    crossed = crossed_after
                    milestone = " | ".join(crossed) if crossed else None
            self.state.save_log(date_str, event["message"], event_type="event")

        # 检查连击奖励：连击 7 天发放跳过令牌
        streak = self.state.get_streak(date_str)
        if streak == 7:
            self.state.add_skip_token(date_str)

        # ── 最终金币汇总（里程碑 + 连击）──
        if crossed:
            milestone_coins = coins_config.get("milestone", 100) * len(crossed)
            coins_breakdown["里程碑"] = milestone_coins
        else:
            milestone_coins = 0

        streak_coins = 0
        if streak == 7:
            streak_coins = coins_config.get("streak_7", 25)
            coins_breakdown["连击7天"] = streak_coins
        elif streak == 30:
            streak_coins = coins_config.get("streak_30", 50)
            coins_breakdown["连击30天"] = streak_coins

        final_coins = pre_coins + milestone_coins + streak_coins

        # 持久化宝藏
        for t in discovered_treasures:
            self.state.discover_treasure(t["name"], t["type"], t["coins"], date_str)
            treasure_coins_key = f'💎 {t["name"]}'
            if treasure_coins_key not in coins_breakdown:
                coins_breakdown[treasure_coins_key] = t["coins"]
            self.state.save_log(date_str, t["message"], event_type="treasure_found")

        # 重新记录（写入最终金币数）
        self.state.record_day(date_str, completed=total_advance, extra=0, coins_earned=final_coins)

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
            "coins": {
                "total": final_coins,
                "breakdown": coins_breakdown,
            },
            "treasures": discovered_treasures,
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
