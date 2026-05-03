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
from datetime import date, timedelta

from bestman.config import BESTMAN_HOME, load_config, get_current_stage, load_env, save_plan
from bestman.state import BestmanState
from bestman.map_engine import MapEngine, get_log_entry
from bestman.events import EventEngine
from bestman.llm import LLMClient, generate_voyage_log, chat_with_coach, generate_plan, review_summary, weigh_comment


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

    def create_plan(self, answers: dict) -> dict:
        """创建分阶段健身计划。

        调用 LLM 生成计划 stages 和 milestones，组合后写入 plan.yaml。

        Args:
            answers: dict with keys: goal_type, start_weight_kg, target_weight_kg,
                    total_days, fitness_level, preference, custom_goal (optional)

        Returns:
            dict: {
                "success": bool,
                "plan": dict | None,     # 完整计划 dict
                "error": str | None,
            }
        """
        from datetime import date

        goal_type = answers.get("goal_type", "weight_loss")
        profile = {
            "start_weight_kg": answers.get("start_weight_kg"),
            "target_weight_kg": answers.get("target_weight_kg"),
            "total_days": answers.get("total_days", 120),
            "fitness_level": answers.get("fitness_level", "beginner"),
            "preference": answers.get("preference", "bodyweight"),
        }
        if goal_type == "custom":
            profile["custom_goal"] = answers.get("custom_goal", "")

        llm_plan = generate_plan(self.llm, goal_type, profile)

        if llm_plan is None:
            return {
                "success": False,
                "plan": None,
                "error": "LLM 不可用，无法生成计划。请检查 ~/.bestman/.env 中的 API 配置。",
            }

        # 构建完整 plan.yaml 结构
        plan = {
            "name": llm_plan.get("name", f"{answers.get('goal_type', 'custom')}计划"),
            "goal_type": goal_type,
            "start_date": date.today().isoformat(),
            "target_date": llm_plan.get("target_date", ""),
            "total_days": answers.get("total_days"),
            "profile": {
                "height_cm": answers.get("height_cm"),
                "start_weight_kg": answers.get("start_weight_kg"),
                "target_weight_kg": answers.get("target_weight_kg"),
                "fitness_level": answers.get("fitness_level"),
                "preference": answers.get("preference"),
            },
            "stages": llm_plan.get("stages", []),
            "milestones": llm_plan.get("milestones", {}),
        }

        # 计算 target_date
        if not plan["target_date"]:
            from datetime import timedelta
            target = date.today() + timedelta(days=answers.get("total_days", 120))
            plan["target_date"] = target.isoformat()

        save_plan(plan)
        return {
            "success": True,
            "plan": plan,
            "error": None,
        }

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
        """获取今日任务描述，优先使用计划覆盖。

        Returns:
            str: 任务描述
        """
        # 检查是否有活跃的 daily_task 覆盖
        overrides = self.state.get_active_overrides(field="daily_task")
        if overrides:
            return overrides[0]["override_value"]

        # 如果有 plan.yaml，优先用当前 stage 的任务
        plan = self.config.get("plan")
        if plan:
            stage_info = self._get_plan_stage_info()
            if stage_info:
                return stage_info.get("daily_task", self.config["voyage"]["default_daily_task"])

        return self.config["voyage"]["default_daily_task"]

    def render_map(self, today_advance=0, sway_offset=0.0, sway_phase=0.0) -> str:
        """渲染像素地图。

        Args:
            today_advance: 今日推进格数，用于高亮今天的足迹。
            sway_offset: 摇摆幅度，用于船体摇晃动画。
            sway_phase: 波浪相位偏移，每帧不同产生滚动波浪效果。

        Returns:
            str: Rich markup 地图字符串
        """
        return self.map_engine.render(self.state.get_tiles_revealed(),
                                      today_advance=today_advance,
                                      sway_offset=sway_offset,
                                      sway_phase=sway_phase)

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

    def complete(self, date_str=None, extra_tiles=0, force=False, distance=None, message=None) -> dict:
        """完成今日任务，掷骰子推进。

        原子操作：检查 → 掷骰 → 金币计算 → 记录 → LLM 日志（fallback 模板） → 里程碑 → 事件 → 宝藏记录。

        Args:
            date_str: 日期字符串 (YYYY-MM-DD)，默认今天
            extra_tiles: 额外推进格数（-e 参数叠加）
            distance: 互动模式下由 CLI 传入的掷骰结果。传入时跳过 _roll_distance()。
            message: 手动输入航行日志内容。传入时跳过 LLM 和模板生成。

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

        # 生成日志：-m 手动输入优先，否则 LLM → fallback 到模板
        llm_used = False
        if message is not None:
            log_entry = message
        else:
            stage_name = get_current_stage(current_day, self.config)["name"]
            remaining = max(0, self.config["voyage"]["total_days"] - current_day)
            task_done = self.config["voyage"]["default_daily_task"]

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

    def _get_plan_stage_info(self):
        """从 plan 配置中获取当前阶段信息。

        Returns:
            dict | None: 当前阶段的 stage 信息，无计划时返回 None
        """
        plan = self.config.get("plan")
        if not plan:
            return None
        stages = plan.get("stages", [])
        current_day = self.state.get_tiles_revealed() + 1
        for stage in stages:
            start, end = stage.get("days", [0, 0])
            if start <= current_day <= end:
                return stage
        return None

    def review(self) -> dict:
        """生成本周回顾（数据聚合 + LLM 总结）。

        Returns:
            dict: {
                "success": bool,
                "week_number": int,
                "start_date": str, "end_date": str,
                "check_ins": int, "days_in_week": int,
                "skips": int, "streak": int,
                "total_tiles": int, "avg_tiles": float,
                "max_tiles": int, "min_tiles": int,
                "coins": int,
                "summary": str | None,
                "error": str | None,
            }
        """

        today = date.today()
        # 从 voyage start 计算周数（默认用 tiles_revealed 推算）
        start_date_str = self.config.get("voyage", {}).get("start_date")
        if start_date_str:
            voyage_start = date.fromisoformat(start_date_str)
        else:
            # fallback: 用 tiles_revealed 反推，大约一天一 tile
            days_in = self.state.get_tiles_revealed()
            voyage_start = today - timedelta(days=days_in)

        # 计算当前周是第几周（从 voyage_start 起算，周日到周六）
        days_from_start = (today - voyage_start).days
        week_number = (days_from_start // 7) + 1

        # 本周起止日期：从上周日起
        weekday = today.weekday()  # 0=Monday ... 6=Sunday
        days_back = (weekday + 1) % 7
        week_start = today - timedelta(days=days_back)
        if week_start > today:
            week_start = today
        # 本周结束就是今天
        week_end = today

        # Ensure we don't go before voyage start
        if week_start < voyage_start:
            week_start = voyage_start

        stats = self.state.get_weekly_stats(week_start.isoformat(), week_end.isoformat())
        days_in_week = min(7, (week_end - week_start).days + 1)

        avg_tiles = stats["total_tiles"] / max(stats["check_ins"], 1)

        streak = self.state.get_streak()

        # LLM 总结
        context = {
            "week_number": week_number,
            "check_ins": stats["check_ins"],
            "days_in_week": days_in_week,
            "skips": stats["skips"],
            "streak": streak,
            "total_tiles": stats["total_tiles"],
            "avg_tiles": avg_tiles,
            "max_tiles": stats["max_tiles"],
            "min_tiles": stats["min_tiles"],
            "coins": stats["coins"],
        }
        summary = review_summary(self.llm, context)

        return {
            "success": True,
            "week_number": week_number,
            "start_date": week_start.isoformat(),
            "end_date": week_end.isoformat(),
            "check_ins": stats["check_ins"],
            "days_in_week": days_in_week,
            "skips": stats["skips"],
            "streak": streak,
            "total_tiles": stats["total_tiles"],
            "avg_tiles": avg_tiles,
            "max_tiles": stats["max_tiles"],
            "min_tiles": stats["min_tiles"],
            "coins": stats["coins"],
            "summary": summary,
            "error": None,
        }

    def record_weight(self, weight_kg, date_str=None, note="") -> dict:
        """记录体重，返回变化和导航员评论。

        Args:
            weight_kg: 体重（公斤）
            date_str: 日期，默认今天
            note: 备注

        Returns:
            dict: {
                "success": bool,
                "current_weight": float,
                "previous_weight": float | None,
                "delta": float | None,
                "target_weight": float | None,
                "distance_to_target": float | None,
                "comment": str,
                "error": str | None,
            }
        """
        if date_str is None:
            date_str = date.today().isoformat()

        # 获取上次体重
        prev = self.state.get_latest_weight()
        prev_weight = prev["weight_kg"] if prev else None

        # 获取目标体重（优先 plan，其次 config）
        target_weight = None
        plan = self.config.get("plan")
        if plan and plan.get("profile", {}).get("target_weight_kg"):
            target_weight = float(plan["profile"]["target_weight_kg"])

        # 记录
        self.state.record_weight(date_str, weight_kg, note)

        # 计算变化
        delta = None
        if prev_weight is not None:
            delta = weight_kg - prev_weight

        distance_to_target = None
        if target_weight is not None:
            distance_to_target = weight_kg - target_weight

        # 趋势描述
        if delta is not None:
            if delta < -0.5:
                trend = "下降趋势"
            elif delta > 0.5:
                trend = "上升趋势"
            else:
                trend = "平稳"
        else:
            trend = "首次记录"

        # LLM 评论
        comment = weigh_comment(self.llm, weight_kg, prev_weight, target_weight, trend)
        if comment is None:
            # Fallback 评论
            if delta is not None and delta < 0:
                comment = f"趋势在下行线，减了{abs(delta):.1f}公斤。保持节奏。"
            elif delta is not None and delta > 0:
                comment = "体重有所波动，风向会变的。"
            else:
                comment = "记录下来就是胜利。定期称重比体重数字本身更重要。"

        return {
            "success": True,
            "current_weight": weight_kg,
            "previous_weight": prev_weight,
            "delta": delta,
            "target_weight": target_weight,
            "distance_to_target": distance_to_target,
            "comment": comment,
            "error": None,
        }

    def get_weight_progress(self) -> dict:
        """获取体重趋势数据。

        Returns:
            dict: {
                "entries": list[dict],  # 最近 4 次周体重记录
                "weekly_avg_loss": float | None,
                "estimated_completion_date": str | None,
                "target_weight": float | None,
            }
        """
        history = self.state.get_weight_history()
        if not history:
            return {
                "entries": [],
                "weekly_avg_loss": None,
                "estimated_completion_date": None,
                "target_weight": None,
            }

        # 取最近 4 条，翻转时间序
        recent = list(reversed(history[-4:]))

        # 周均变化（每周假设一条）
        weekly_avg_loss = None
        if len(recent) >= 2:
            total_delta = recent[-1]["weight_kg"] - recent[0]["weight_kg"]
            weeks = len(recent) - 1
            weekly_avg_loss = total_delta / max(weeks, 1)

        # 预计达标日期
        target_weight = None
        plan = self.config.get("plan")
        if plan and plan.get("profile", {}).get("target_weight_kg"):
            target_weight = float(plan["profile"]["target_weight_kg"])

        estimated_completion_date = None
        if (target_weight is not None and weekly_avg_loss is not None
                and weekly_avg_loss < 0 and recent):
            remaining = recent[-1]["weight_kg"] - target_weight
            if remaining > 0:
                weeks_needed = int(remaining / abs(weekly_avg_loss))
                completion = date.today() + timedelta(weeks=weeks_needed)
                estimated_completion_date = completion.isoformat()
            else:
                estimated_completion_date = "已达标"

        return {
            "entries": recent,
            "weekly_avg_loss": weekly_avg_loss,
            "estimated_completion_date": estimated_completion_date,
            "target_weight": target_weight,
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
