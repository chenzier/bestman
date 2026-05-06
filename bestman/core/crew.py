"""Crew Manager — v2.2 船员系统核心逻辑。

协调配置、状态存储和对话选择，提供：
- 招募/解雇/召回
- 对话触发与选择
- 情绪管理
- 每周任务
- 升级系统
"""

import hashlib
import random
from datetime import date, timedelta

from bestman.core.config import BESTMAN_HOME


class CrewManager:
    """船员系统核心管理器。

    封装所有船员相关逻辑，由 Voyage 类持有。
    不直接依赖 LLM——对话由模板驱动，保持离线可用。
    """

    def __init__(self, config, state):
        self.config = config
        self.state = state
        self.crew_config = config.get("crew", {})
        self.characters = self.crew_config.get("characters", {})

    # ═══════════════════════════════════════════════════════════
    # 招募 / 解雇 / 召回
    # ═══════════════════════════════════════════════════════════

    def hire(self, role_id, date_str=None):
        """定向招募指定角色。

        Args:
            role_id: 角色 ID（如 "captain"）
            date_str: 招募日期

        Returns:
            dict: {"success": bool, "crew": dict|None, "error": str|None, "coins_spent": int}
        """
        if date_str is None:
            date_str = date.today().isoformat()

        character = self.get_character(role_id)
        if character is None:
            return {"success": False, "crew": None, "error": f"未知角色：{role_id}", "coins_spent": 0}

        # 检查是否已拥有
        existing = self.state.list_crew(active_only=True)
        for c in existing:
            if c["role_id"] == role_id:
                return {"success": False, "crew": None, "error": f"已经拥有 {character['name']}", "coins_spent": 0}

        # 检查船员上限
        if len(existing) >= self.get_max_crew_slots():
            return {"success": False, "crew": None,
                    "error": f"船员已满（上限 {self.get_max_crew_slots()} 人）。请先解雇一名船员。", "coins_spent": 0}

        hire_cost = character.get("hire_cost", 500)
        total_coins = self.state.get_total_coins()
        if total_coins < hire_cost:
            return {"success": False, "crew": None,
                    "error": f"金币不足（需要 {hire_cost}，当前 {total_coins}）", "coins_spent": 0}

        # 招募
        crew_id = self.state.hire_crew(role_id, character["name"], character.get("rarity", "common"), date_str)
        if crew_id is None:
            return {"success": False, "crew": None, "error": "招募失败", "coins_spent": 0}

        # 如果是第一个船员，自动设为主船员
        if len(existing) == 0:
            self.state.set_main_crew(crew_id)

        # 扣除金币（通过记录一条负金币的 day 记录，或者直接调整）
        # 这里用简化方案：在 days 表记录一笔消费
        self._spend_coins(hire_cost, date_str)

        crew = self.state.get_crew(crew_id)
        self.state.add_recruit_history(date_str, role_id, character.get("rarity", "common"), method="direct")

        return {"success": True, "crew": crew, "error": None, "coins_spent": hire_cost}

    def random_hire(self, date_str=None):
        """随机招募一名船员（扭蛋式）。

        Args:
            date_str: 招募日期

        Returns:
            dict: {"success": bool, "crew": dict|None, "rarity": str, "error": str|None, "coins_spent": int}
        """
        if date_str is None:
            date_str = date.today().isoformat()

        # 检查船员上限
        active = self.state.list_crew(active_only=True)
        if len(active) >= self.get_max_crew_slots():
            return {"success": False, "crew": None, "rarity": None,
                    "error": f"船员已满（上限 {self.get_max_crew_slots()} 人）", "coins_spent": 0}

        # 费用
        cost = self.crew_config.get("random_hire_cost", 100)
        # 每日首次半价
        today_history = self.state.conn.execute(
            "SELECT COUNT(*) FROM crew_recruit_history WHERE date=? AND method='random'",
            (date_str,),
        ).fetchone()[0]
        if today_history == 0:
            cost = self.crew_config.get("random_hire_first_daily_discount", 50)

        total_coins = self.state.get_total_coins()
        if total_coins < cost:
            return {"success": False, "crew": None, "rarity": None,
                    "error": f"金币不足（需要 {cost}，当前 {total_coins}）", "coins_spent": 0}

        # 计算稀有度权重（含保底）
        weights = dict(self.crew_config.get("random_rarity_weights", {"common": 70, "rare": 25, "legendary": 5}))
        pity_after = self.crew_config.get("pity_after_misses", 3)
        pity_mult = self.crew_config.get("pity_multiplier", 3.0)

        for rarity in ["rare", "legendary"]:
            consecutive = self.state.get_consecutive_misses(rarity)
            if consecutive >= pity_after:
                weights[rarity] = int(weights.get(rarity, 10) * pity_mult)

        rarity_roll = random.choices(
            list(weights.keys()),
            weights=list(weights.values()),
            k=1,
        )[0]

        # 从该稀有度中随机选一个未拥有的角色
        available = []
        owned_roles = {c["role_id"] for c in active}
        for rid, char in self.characters.items():
            if char.get("rarity") == rarity_roll and rid not in owned_roles:
                available.append((rid, char))

        if not available:
            # 没有可招募的——退还金币
            self.state.add_recruit_history(date_str, None, rarity_roll, method="random")
            return {"success": False, "crew": None, "rarity": rarity_roll,
                    "error": f"抽中 {rarity_roll} 但该稀有度角色已全部拥有。金币已退还。", "coins_spent": 0}

        chosen_role, chosen_char = random.choice(available)

        # 招募
        self._spend_coins(cost, date_str)
        crew_id = self.state.hire_crew(chosen_role, chosen_char["name"], rarity_roll, date_str)

        if len(active) == 0:
            self.state.set_main_crew(crew_id)

        crew = self.state.get_crew(crew_id)
        self.state.add_recruit_history(date_str, chosen_role, rarity_roll, method="random")

        return {"success": True, "crew": crew, "rarity": rarity_roll, "error": None, "coins_spent": cost}

    def fire(self, crew_id):
        """解雇船员。

        Args:
            crew_id: 船员 id

        Returns:
            dict: {"success": bool, "refund": int, "error": str|None}
        """
        result = self.state.fire_crew(crew_id)
        if result is None:
            return {"success": False, "refund": 0, "error": "船员不存在或已离船"}

        rarity = result["rarity"]
        character = self.get_character(result["role_id"])
        hire_cost = character.get("hire_cost", 500) if character else 500

        refund_rate = self.crew_config.get("legendary_refund_rate" if rarity == "legendary" else "refund_rate", 0.50)
        refund = int(hire_cost * refund_rate)

        # 退款
        self._refund_coins(refund, date.today().isoformat())

        return {"success": True, "refund": refund, "error": None}

    def recall(self, crew_id, date_str=None):
        """召回被解雇船员。

        Args:
            crew_id: 船员 id
            date_str: 召回日期

        Returns:
            dict: {"success": bool, "coins_spent": int, "error": str|None}
        """
        if date_str is None:
            date_str = date.today().isoformat()

        # 检查上限
        active = self.state.list_crew(active_only=True)
        if len(active) >= self.get_max_crew_slots():
            return {"success": False, "coins_spent": 0,
                    "error": f"船员已满（上限 {self.get_max_crew_slots()} 人）"}

        crew = self.state.get_crew(crew_id)
        if crew is None:
            return {"success": False, "coins_spent": 0, "error": "船员不存在"}
        if crew["active"]:
            return {"success": False, "coins_spent": 0, "error": "船员已在船上"}

        character = self.get_character(crew["role_id"])
        hire_cost = character.get("hire_cost", 500) if character else 500
        recall_cost = int(hire_cost * self.crew_config.get("recall_discount", 0.80))

        total_coins = self.state.get_total_coins()
        if total_coins < recall_cost:
            return {"success": False, "coins_spent": 0,
                    "error": f"金币不足（需要 {recall_cost}，当前 {total_coins}）"}

        if self.state.recall_crew(crew_id, date_str):
            self._spend_coins(recall_cost, date_str)
            return {"success": True, "coins_spent": recall_cost, "error": None}
        return {"success": False, "coins_spent": 0, "error": "召回失败"}

    # ═══════════════════════════════════════════════════════════
    # 对话系统
    # ═══════════════════════════════════════════════════════════

    def trigger_dialogue(self, trigger_type, context=None, date_str=None):
        """根据触发类型自动选择一个船员说话。

        对话概率由 auto_dialogue_probability 控制。
        70% 概率触发时，选择一个合适的船员发言。

        Args:
            trigger_type: 触发类型（"completed_day", "missed_day", "streak_7" 等）
            context: 对话上下文 dict（如 {"milestone_name": "穿越迷雾之海"}）
            date_str: 日期

        Returns:
            dict | None: {"crew_id": int, "name": str, "text": str, "trigger": str} 或 None
        """
        if date_str is None:
            date_str = date.today().isoformat()

        prob = self.crew_config.get("auto_dialogue_probability", 0.70)

        # 某些触发类型必然说话
        always_triggers = {"streak_7", "streak_30", "milestone"}
        if trigger_type not in always_triggers:
            seed = int(hashlib.md5(f"{date_str}_{trigger_type}".encode()).hexdigest()[:8], 16)
            if (seed % 100) / 100.0 >= prob:
                return None

        active_crew = self.state.list_crew(active_only=True)
        if not active_crew:
            return None

        # 选择说话者
        speaker = self._select_speaker(trigger_type, active_crew, date_str)
        if speaker is None:
            return None

        character = self.get_character(speaker["role_id"])
        if character is None:
            return None

        # 选择对话
        text = self._select_response(character, trigger_type)
        if text is None:
            return None

        # 替换模板变量
        if context:
            text = self._format_response(text, context)

        # 记录对话
        self.state.add_crew_dialogue(speaker["id"], date_str, trigger_type, text)

        return {
            "crew_id": speaker["id"],
            "role_id": speaker["role_id"],
            "name": speaker["name"],
            "text": text,
            "trigger": trigger_type,
        }

    def manual_talk(self, crew_id, date_str=None):
        """手动触发船员对话。

        Args:
            crew_id: 船员 id
            date_str: 日期

        Returns:
            dict: {"success": bool, "text": str|None, "error": str|None}
        """
        if date_str is None:
            date_str = date.today().isoformat()

        crew = self.state.get_crew(crew_id)
        if crew is None or not crew["active"]:
            return {"success": False, "text": None, "error": "船员不存在或不在船上"}

        character = self.get_character(crew["role_id"])
        if character is None:
            return {"success": False, "text": None, "error": "角色配置缺失"}

        # 选择 idle 对话
        text = self._select_response(character, "idle")

        # 记录对话
        self.state.add_crew_dialogue(crew_id, date_str, "manual_talk", text)

        # 手动对话提升情绪
        self.state.update_crew_mood(crew_id, min(100, crew["mood"] + 5))

        return {"success": True, "text": text, "error": None}

    def _select_speaker(self, trigger_type, active_crew, date_str):
        """选择合适的船员发言。

        优先级：主船员 > 有匹配 trigger 的船员 > 随机。
        三天未说话的船员权重强制优先。
        """
        # 先检查主船员是否有匹配此触发类型的对话
        main_crew = next((c for c in active_crew if c["is_main"]), None)
        if main_crew:
            char = self.get_character(main_crew["role_id"])
            if char and self._has_trigger(char, trigger_type):
                return main_crew

        # 找所有有匹配 trigger 的船员
        candidates = []
        forced = []
        for c in active_crew:
            char = self.get_character(c["role_id"])
            if char and self._has_trigger(char, trigger_type):
                days_silent = self.state.get_days_since_last_dialogue(c["id"], date_str)
                if days_silent >= 3:
                    forced.append(c)
                else:
                    candidates.append(c)

        # 三天未说话的优先
        if forced:
            return random.choice(forced)

        if candidates:
            return random.choice(candidates)

        # 没有匹配的——退回主船员用 idle
        if main_crew:
            return main_crew

        # 随机选一个
        return random.choice(active_crew) if active_crew else None

    def _select_response(self, character, trigger_type):
        """从角色对话模板中选择一条回复。

        Args:
            character: 角色配置 dict
            trigger_type: 触发类型

        Returns:
            str | None
        """
        patterns = character.get("dialogue_patterns", [])
        for pattern in patterns:
            if pattern.get("trigger") == trigger_type:
                responses = pattern.get("responses", [])
                if responses:
                    return random.choice(responses)
        return None

    def _has_trigger(self, character, trigger_type):
        """检查角色是否有对应触发类型的对话。"""
        patterns = character.get("dialogue_patterns", [])
        return any(p.get("trigger") == trigger_type for p in patterns)

    def _format_response(self, text, context):
        """替换模板变量 {name} 等。"""
        for key, value in context.items():
            text = text.replace(f"{{{key}}}", str(value))
        return text

    # ═══════════════════════════════════════════════════════════
    # 情绪管理
    # ═══════════════════════════════════════════════════════════

    def update_moods(self, trigger_type="completed_day", date_str=None):
        """根据触发事件更新所有在船船员的情绪。

        Args:
            trigger_type: 触发类型
            date_str: 日期
        """
        if date_str is None:
            date_str = date.today().isoformat()

        active_crew = self.state.list_crew(active_only=True)
        decay = self.crew_config.get("satisfaction_decay_per_day_silent", 5)

        for c in active_crew:
            mood_delta = 0

            # 事件情绪调整
            if trigger_type == "completed_day":
                mood_delta += 3
            elif trigger_type == "missed_day":
                mood_delta -= 5
            elif trigger_type == "streak_7":
                mood_delta += 8
            elif trigger_type == "streak_30":
                mood_delta += 15
            elif trigger_type == "milestone":
                mood_delta += 10

            # 沉默衰减
            days_silent = self.state.get_days_since_last_dialogue(c["id"], date_str)
            if days_silent > 1:
                mood_delta -= min(decay * (days_silent - 1), 30)

            if mood_delta != 0:
                current = c["mood"]
                new_mood = max(0, min(100, current + mood_delta))
                self.state.update_crew_mood(c["id"], new_mood)

    def boost_mood(self, crew_id, amount):
        """提升船员情绪。

        Args:
            crew_id: 船员 id
            amount: 提升量

        Returns:
            int: 新情绪值
        """
        crew = self.state.get_crew(crew_id)
        if crew is None:
            return 0
        new_mood = min(100, crew["mood"] + amount)
        self.state.update_crew_mood(crew_id, new_mood)
        return new_mood

    # ═══════════════════════════════════════════════════════════
    # 升级系统
    # ═══════════════════════════════════════════════════════════

    def upgrade(self, crew_id):
        """升级船员。

        Args:
            crew_id: 船员 id

        Returns:
            dict: {"success": bool, "new_level": int, "coins_spent": int, "error": str|None}
        """
        crew = self.state.get_crew(crew_id)
        if crew is None or not crew["active"]:
            return {"success": False, "new_level": 0, "coins_spent": 0, "error": "船员不存在或不在船上"}

        max_level = self.crew_config.get("max_level", 10)
        if crew["level"] >= max_level:
            return {"success": False, "new_level": crew["level"], "coins_spent": 0,
                    "error": f"已达到最高等级 {max_level}"}

        base_cost = self.crew_config.get("upgrade_base_cost", 100)
        increment = self.crew_config.get("upgrade_cost_increment", 20)
        cost = base_cost + (crew["level"] - 1) * increment

        total_coins = self.state.get_total_coins()
        if total_coins < cost:
            return {"success": False, "new_level": crew["level"], "coins_spent": 0,
                    "error": f"金币不足（需要 {cost}，当前 {total_coins}）"}

        new_level = crew["level"] + 1
        new_xp = crew["xp"]

        self.state.upgrade_crew(crew_id, new_level, new_xp)
        self._spend_coins(cost, date.today().isoformat())

        # 升级提升情绪
        self.state.update_crew_mood(crew_id, min(100, crew["mood"] + 10))

        return {"success": True, "new_level": new_level, "coins_spent": cost, "error": None}

    def add_xp(self, crew_id, amount):
        """为船员增加经验值，可能触发升级。

        Args:
            crew_id: 船员 id
            amount: 经验值

        Returns:
            dict: {"leveled_up": bool, "new_level": int}
        """
        crew = self.state.get_crew(crew_id)
        if crew is None:
            return {"leveled_up": False, "new_level": 0}

        max_level = self.crew_config.get("max_level", 10)
        if crew["level"] >= max_level:
            return {"leveled_up": False, "new_level": crew["level"]}

        new_xp = crew["xp"] + amount
        new_level = crew["level"]

        # 每级需要 100 XP
        xp_per_level = 100
        while new_xp >= xp_per_level and new_level < max_level:
            new_xp -= xp_per_level
            new_level += 1

        self.state.upgrade_crew(crew_id, new_level, new_xp)
        leveled_up = new_level > crew["level"]

        return {"leveled_up": leveled_up, "new_level": new_level}

    # ═══════════════════════════════════════════════════════════
    # 每周任务
    # ═══════════════════════════════════════════════════════════

    def generate_weekly_quests(self, date_str=None):
        """为所有在船船员生成本周任务。

        Args:
            date_str: 参考日期，会计算本周一的日期

        Returns:
            list[dict]: 新生成的任务列表
        """
        if date_str is None:
            date_str = date.today().isoformat()

        ref_date = date.fromisoformat(date_str)
        # 本周一
        week_start = ref_date - timedelta(days=ref_date.weekday())
        week_start_str = week_start.isoformat()

        # 检查是否已有本周任务
        existing = self.state.get_active_quests(date_str)
        if existing:
            return []

        active_crew = self.state.list_crew(active_only=True)
        new_quests = []

        for c in active_crew:
            character = self.get_character(c["role_id"])
            if character is None:
                continue

            quest_cfg = character.get("quest", {})
            if not quest_cfg:
                continue

            quest_type = quest_cfg.get("weekly_theme", "general")

            # 根据 quest_type 决定 target
            target = 3  # 默认
            if quest_type == "steering":
                target = 5
            elif quest_type == "discipline":
                target = 5
            elif quest_type == "discovery":
                target = 1
            elif quest_type == "health":
                target = 3
            elif quest_type == "nourishment":
                target = 3

            quest_id = self.state.add_crew_quest(c["id"], week_start_str, quest_type, target)
            new_quests.append({
                "id": quest_id, "crew_id": c["id"], "crew_name": c["name"],
                "quest_type": quest_type, "target": target,
            })

        return new_quests

    def check_quest_progress(self, trigger_type, date_str=None):
        """根据触发事件推进所有船员的任务进度。

        Args:
            trigger_type: 触发类型
            date_str: 日期

        Returns:
            list[dict]: 完成的任务列表
        """
        if date_str is None:
            date_str = date.today().isoformat()

        quests = self.state.get_active_quests(date_str)
        completed = []

        for q in quests:
            if q["completed"]:
                continue

            should_progress = False

            # 根据任务类型判断是否应该推进
            if q["quest_type"] == "steering" and trigger_type == "completed_day":
                should_progress = True
            elif q["quest_type"] == "discipline" and trigger_type == "completed_day":
                should_progress = True
            elif q["quest_type"] == "discovery" and trigger_type in ("treasure_found", "bonus_tile"):
                should_progress = True
            elif q["quest_type"] == "health" and trigger_type in ("completed_day", "weigh"):
                should_progress = True
            elif q["quest_type"] == "nourishment" and trigger_type == "completed_day":
                should_progress = True
            elif q["quest_type"] == "general":
                should_progress = True

            if should_progress:
                new_progress = q["progress"] + 1
                self.state.update_quest_progress(q["id"], new_progress)
                if new_progress >= q["target"]:
                    self.state.complete_quest(q["id"])
                    # 奖励 XP
                    self.add_xp(q["crew_id"], 20)
                    completed.append(q)

        return completed

    # ═══════════════════════════════════════════════════════════
    # 状态 / 辅助
    # ═══════════════════════════════════════════════════════════

    def get_max_crew_slots(self):
        """计算当前最大船员数量。

        初始 max_crew，每完成 50 天增加 slots_per_50_completions。

        Returns:
            int
        """
        base = self.crew_config.get("max_crew", 3)
        slots_per = self.crew_config.get("slots_per_50_completions", 1)
        max_abs = self.crew_config.get("max_crew_absolute", 8)

        completed = self.state.get_completed_days_count()
        bonus = (completed // 50) * slots_per
        return min(base + bonus, max_abs)

    def get_available_roles(self):
        """获取可招募的角色 ID 列表。

        Returns:
            list[str]
        """
        active_roles = {c["role_id"] for c in self.state.list_crew(active_only=True)}
        return [rid for rid in self.characters if rid not in active_roles]

    def get_character(self, role_id):
        """获取角色配置。

        Args:
            role_id: 角色 ID

        Returns:
            dict | None
        """
        return self.characters.get(role_id)

    def get_crew_status(self):
        """获取船员系统完整状态。

        Returns:
            dict: {crew, max_slots, quests, total_dialogues}
        """
        active = self.state.list_crew(active_only=True)
        quests = self.state.get_active_quests()

        # 丰富每个船员的信息
        enriched = []
        for c in active:
            char = self.get_character(c["role_id"])
            mood_desc = self._mood_description(c["mood"])
            enriched.append({
                **c,
                "mood_description": mood_desc,
                "special_skill": char.get("special_skill", {}) if char else {},
                "backstory": char.get("backstory", "") if char else "",
            })

        return {
            "crew": enriched,
            "max_slots": self.get_max_crew_slots(),
            "quests": quests,
            "total_dialogues": len(self.state.get_crew_dialogues(limit=999)),
        }

    def _mood_description(self, mood):
        """将情绪数值转为中文描述。"""
        if mood >= 80:
            return "昂扬 ☀️"
        elif mood >= 60:
            return "高兴 😊"
        elif mood >= 40:
            return "平静 😐"
        elif mood >= 30:
            return "低沉 😔"
        else:
            return "低落 🌧️"

    def _spend_coins(self, amount, date_str):
        """扣除金币（在 days 表记录负金币）。

        通过查询最近一天记录并减少其 coins_earned 来模拟消费。
        """
        # 查找 date_str 的记录，如果存在则减少 coins_earned
        from bestman.core.state import BestmanState
        cursor = self.state.conn.execute(
            "SELECT coins_earned FROM days WHERE date=? LIMIT 1",
            (date_str,),
        )
        row = cursor.fetchone()
        if row and row[0] >= amount:
            self.state.conn.execute(
                "UPDATE days SET coins_earned = coins_earned - ? WHERE date=?",
                (amount, date_str),
            )
        else:
            # 记录一笔消费（completed=0 仅扣钱）
            self.state.record_day(date_str, completed=0, extra=0, coins_earned=-amount)
        self.state.conn.commit()

    def _refund_coins(self, amount, date_str):
        """退还金币。"""
        cursor = self.state.conn.execute(
            "SELECT coins_earned FROM days WHERE date=? LIMIT 1",
            (date_str,),
        )
        row = cursor.fetchone()
        if row:
            self.state.conn.execute(
                "UPDATE days SET coins_earned = coins_earned + ? WHERE date=?",
                (amount, date_str),
            )
        else:
            self.state.record_day(date_str, completed=0, extra=0, coins_earned=amount)
        self.state.conn.commit()
