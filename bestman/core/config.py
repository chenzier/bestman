"""bestman configuration management."""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

BESTMAN_HOME = Path(os.environ.get("BESTMAN_HOME", Path.home() / ".bestman"))
PLAN_PATH = BESTMAN_HOME / "plan.yaml"

DEFAULT_CONFIG = {
    "map": {
        "width": 50,
        "height": 14,
    },
    "voyage": {
        "theme": "naval",
        "total_days": 120,
        "end_date": "",
        "default_daily_task": "未设置 — 运行 bestman plan create 制定计划",
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
    "dice": {
        "mode": "deterministic",
        "weights": [60, 30, 10],
        "descriptions": {
            1: "风平浪静，缓缓前行",
            2: "顺风满帆，航行两格",
            3: "暴风助力，航行三格！",
        },
    },
    "coins": {
        "daily_complete": 10,
        "dice_3": 5,
        "extra_per_tile": 5,
        "streak_7": 25,
        "streak_30": 50,
        "milestone": 100,
    },
    "treasures": {
        "explicit": [
            {
                "name": "沉船宝藏",
                "position": 32,
                "coins": 50,
                "message": "你发现了一艘古代沉船，舱室里还有完好的金币！",
            },
            {
                "name": "海妖巢穴",
                "position": 67,
                "coins": 80,
                "message": "海妖已被其他航海者驱赶，巢穴里留下了闪亮的金币。",
            },
            {
                "name": "漂流瓶",
                "position": 110,
                "coins": 30,
                "message": "捡到一个漂流瓶，瓶中信写道：'继续前进，新大陆不远了。' 附带30枚金币。",
            },
            {
                "name": "海盗藏宝图",
                "position": 145,
                "coins": 100,
                "message": "在礁石缝隙里发现了一张泛黄的海盗藏宝图，宝箱里有100枚金币！",
            },
        ],
        "implicit": {
            "pool": [
                {
                    "name": "海豚赠礼",
                    "coins": 20,
                    "message": "一群海豚绕着船游了三圈，其中一只吐出一枚闪亮的金币到甲板上！",
                },
                {
                    "name": "美人鱼之歌",
                    "coins": 15,
                    "message": "夜晚听到美人鱼的歌声。第二天在船舷上发现了一小堆金币。",
                },
                {
                    "name": "浮木宝箱",
                    "coins": 40,
                    "message": "一块浮木漂过，上面绑着一个锈迹斑斑的小宝箱。",
                },
                {
                    "name": "鹦鹉金币",
                    "coins": 10,
                    "message": "一只鹦鹉落在桅杆上，嘴里叼着一枚金币。它放下金币后飞走了。",
                },
                {
                    "name": "星尘",
                    "coins": 25,
                    "message": "一颗流星坠入海面附近的礁石，溅起的浪花中闪烁着金币的光芒。",
                },
            ],
            "probability": 0.08,
        },
    },
    "today_trail": {
        "style": "custom",
        "color": "bright_red",
        "fade_steps": 3,
        "sway": {
            "enabled": True,
            "amplitude": 3,
            "fps": 15,
            "duration": 1.0,
        },
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
    # ── v2.2 船员系统 ──────────────────────────────────────────
    "crew": {
        # 系统参数
        "max_crew": 3,
        "slots_per_50_completions": 1,
        "max_crew_absolute": 8,
        "auto_dialogue_probability": 0.70,
        "gift_cost": 30,
        "gift_mood_boost": 20,
        "emergency_talk_cost": 50,
        "upgrade_base_cost": 100,
        "upgrade_cost_increment": 20,
        "max_level": 10,
        "refund_rate": 0.50,
        "legendary_refund_rate": 0.60,
        "recall_discount": 0.80,
        "daily_free_talk": 1,
        "satisfaction_decay_per_day_silent": 5,
        "strike_threshold": 30,
        # 随机招募概率
        "random_hire_cost": 100,
        "random_hire_first_daily_discount": 50,
        "random_rarity_weights": {"common": 70, "rare": 25, "legendary": 5},
        "pity_after_misses": 3,
        "pity_multiplier": 3.0,
        # 角色定义
        "characters": {
            "captain": {
                "name": "船长",
                "role": "captain",
                "rarity": "common",
                "personality": "authoritative yet encouraging",
                "specialties": ["motivation", "goal_setting", "challenge_handling"],
                "speaking_style": "direct and inspiring",
                "mood_modifiers": ["weather", "progress", "streaks"],
                "hire_cost": 500,
                "maintenance_cost": 0,
                "backstory": "曾带领商船穿越风暴，失去过一半船员，因此格外重视每个水手的意志力。",
                "dialogue_patterns": [
                    {
                        "trigger": "daily_greeting_morning",
                        "responses": [
                            "东方既白，该升帆了。今天有什么航线要定？",
                            "早。风正好，别浪费了。",
                        ],
                    },
                    {
                        "trigger": "daily_greeting_night",
                        "responses": [
                            "夜深了还在舵位？明天还有一整片海要航。",
                            "星象清晰——明天是个好天。去睡吧。",
                        ],
                    },
                    {
                        "trigger": "completed_day",
                        "responses": [
                            "出色的一天，水手！这才是真正航海者的精神！",
                            "干得漂亮。保持这个节奏，新大陆不远了。",
                        ],
                    },
                    {
                        "trigger": "missed_day",
                        "responses": [
                            "每个伟大的船长都经历过风暴。明天是一片新的海平线。",
                            "失去的一天已经沉入海底。抬头，前方还是海。",
                        ],
                    },
                    {
                        "trigger": "streak_7",
                        "responses": [
                            "连续七天——你还记得起航那天吗？你已经不是同一个水手了。",
                            "一周不断！船头劈开的每一道浪都是证明。",
                        ],
                    },
                    {
                        "trigger": "streak_30",
                        "responses": [
                            "三十天。我在海上见过无数人放弃，你不是其中之一。",
                            "一个月。从现在开始，这艘船正式以你命名。",
                        ],
                    },
                    {
                        "trigger": "milestone",
                        "responses": [
                            "前方是{name}！全体注意——这是关键的一程。",
                            "{name}。把这一刻记在心里，以后回看会感谢自己。",
                        ],
                    },
                    {
                        "trigger": "struggle",
                        "responses": [
                            "累？那就对了。舒服是留给岸上人的。",
                            "我见过你在顺风时什么样——这才是考验。撑过去。",
                        ],
                    },
                    {
                        "trigger": "idle",
                        "responses": [
                            "（船长靠在舵轮上，凝视着海平线）",
                            "海鸥今天飞得很低——要变天了。不过我们没问题。",
                        ],
                    },
                ],
                "special_skill": {
                    "name": "暴风宣言",
                    "description": "连续打卡7天后，当日进度损失恢复10%",
                    "cooldown_days": 7,
                    "effect_type": "progress_recovery",
                    "effect_value": 0.10,
                },
                "quest": {
                    "weekly_theme": "steering",
                    "example": "本周完成5次中午前打卡",
                    "reward_coins": 150,
                },
            },
            "doctor": {
                "name": "船医",
                "role": "doctor",
                "rarity": "rare",
                "personality": "gentle and professional",
                "specialties": ["health_assessment", "recovery", "mental_care"],
                "speaking_style": "calm and caring, like a traditional healer",
                "mood_modifiers": ["user_fatigue", "missed_days", "weight_trend"],
                "hire_cost": 1200,
                "maintenance_cost": 0,
                "backstory": "原是大陆名医，因一场医疗事故出海赎罪，擅长用草药与谈话治疗。",
                "dialogue_patterns": [
                    {
                        "trigger": "daily_greeting_morning",
                        "responses": [
                            "早。昨晚睡得好吗？关节有没有酸痛？",
                            "晨间记得喝杯温水——海上容易脱水。",
                        ],
                    },
                    {
                        "trigger": "daily_greeting_night",
                        "responses": [
                            "星象说今晚适合反思，但别熬太晚，对骨头不好。",
                            "夜深了。如果你在数海浪而不是数羊，来杯热茶？",
                        ],
                    },
                    {
                        "trigger": "completed_day",
                        "responses": [
                            "训练完成。我注意到你的动作越来越标准了——身体在适应。",
                            "今天的运动量刚好。记得拉伸，明天才不会酸。",
                        ],
                    },
                    {
                        "trigger": "missed_day",
                        "responses": [
                            "休息一天不是失败。身体有时候需要退一步。",
                            "我宁愿你休息一天，也不愿你带着伤上甲板。",
                        ],
                    },
                    {
                        "trigger": "streak_7",
                        "responses": [
                            "七天。从医学角度——你的心率变异性应该在改善。",
                            "一周不断是身体适应的信号。继续保持，但要听身体的。",
                        ],
                    },
                    {
                        "trigger": "struggle",
                        "responses": [
                            "来，坐下。疲劳是身体的信号，不是弱点。",
                            "我闻到你在咬牙——但有时候放松比用力更难。",
                        ],
                    },
                    {
                        "trigger": "weight_loss",
                        "responses": [
                            "体重在下降。这个速度很健康——太快反而伤身。",
                            "下降趋势——但别忘了，肌肉也在生长。数字不是全部。",
                        ],
                    },
                    {
                        "trigger": "idle",
                        "responses": [
                            "（船医正在碾磨草药，空气中飘着薄荷味）",
                            "今天关节状态不错。继续保持。",
                        ],
                    },
                ],
                "special_skill": {
                    "name": "诊疗笔记",
                    "description": "每周可主动进行一次疲劳度检测，给出针对性休息建议",
                    "cooldown_days": 7,
                    "effect_type": "fatigue_check",
                    "effect_value": 0,
                },
                "quest": {
                    "weekly_theme": "health",
                    "example": "本周记录3次心情日志",
                    "reward_coins": 120,
                },
            },
            "lookout": {
                "name": "瞭望员",
                "role": "lookout",
                "rarity": "rare",
                "personality": "young, talkative, adventurous",
                "specialties": ["weather_forecast", "opportunity_spotting", "risk_warning"],
                "speaking_style": "energetic and observant",
                "mood_modifiers": ["weather", "new_events", "treasure_found"],
                "hire_cost": 1200,
                "maintenance_cost": 0,
                "backstory": "前海盗团的侦察兵，因厌倦杀戮而离开，现在依然保持着对远方的高度敏感。",
                "dialogue_patterns": [
                    {
                        "trigger": "daily_greeting_morning",
                        "responses": [
                            "早！我刚从桅杆上下来——今天能见度极好，最远能看到10海里！",
                            "太阳刚出来我就爬上去了。东边云层有点厚，下午可能有风。",
                        ],
                    },
                    {
                        "trigger": "daily_greeting_night",
                        "responses": [
                            "夜班交给我！今晚星星特别多——要不要上来数？",
                            "海上磷光今晚特别亮，船尾拖着一条银河。",
                        ],
                    },
                    {
                        "trigger": "completed_day",
                        "responses": [
                            "航向正确！我在上面看得很清楚——保持这个方向！",
                            "你今天划的水痕是一条直线，没偏航。漂亮。",
                        ],
                    },
                    {
                        "trigger": "missed_day",
                        "responses": [
                            "昨天我在桅杆上没看到你……不过今天太阳照常升起！",
                            "错过一天没关系——我在上面帮你多看了十眼。",
                        ],
                    },
                    {
                        "trigger": "streak_7",
                        "responses": [
                            "一星期了！看，连海鸥都在为咱们编队飞行。",
                            "七天连续航行——你知道这在海上叫什么吗？叫'好运的开端'！",
                        ],
                    },
                    {
                        "trigger": "treasure_spotted",
                        "responses": [
                            "桅杆上看到了！左舷方向有闪光——可能是宝藏！",
                            "我的眼睛不会骗我——那片礁石后面藏着东西。",
                        ],
                    },
                    {
                        "trigger": "idle",
                        "responses": [
                            "（瞭望员在高处吹着口哨，偶尔调整望远镜）",
                            "你知道吗？海豚其实用右手吃饭——哦不对，它们没有手。",
                        ],
                    },
                ],
                "special_skill": {
                    "name": "鹰眼",
                    "description": "提前预判下次随机事件类型（宝藏/风暴/顺风）",
                    "cooldown_days": 3,
                    "effect_type": "event_preview",
                    "effect_value": 0,
                },
                "quest": {
                    "weekly_theme": "discovery",
                    "example": "本周发现1个宝藏或触发1次随机事件",
                    "reward_coins": 130,
                },
            },
            "bosun": {
                "name": "船务长",
                "role": "bosun",
                "rarity": "common",
                "personality": "strict but fair, disciplined",
                "specialties": ["discipline", "task_breakdown", "efficiency"],
                "speaking_style": "blunt and practical",
                "mood_modifiers": ["task_completion", "punctuality", "extra_effort"],
                "hire_cost": 500,
                "maintenance_cost": 0,
                "backstory": "服役十年的海军老兵，重视流程与秩序，对任何'偷懒'行为零容忍。",
                "dialogue_patterns": [
                    {
                        "trigger": "daily_greeting_morning",
                        "responses": [
                            "甲板已擦。任务清单在舵台上。开始吧。",
                            "早。今天的待办按优先级排好了——从最难的事情开始。",
                        ],
                    },
                    {
                        "trigger": "daily_greeting_night",
                        "responses": [
                            "收工。明天第一件事——检查绳索。晚安。",
                            "一天结束。如果你完成了清单上的所有事，可以休息。",
                        ],
                    },
                    {
                        "trigger": "completed_day",
                        "responses": [
                            "全部完成。效率可评B+——下次争取A。",
                            "清单全清。这才是海军标准。明天保持。",
                        ],
                    },
                    {
                        "trigger": "missed_day",
                        "responses": [
                            "昨天甲板上少了你的脚印。今天加倍——不是惩罚，是补课。",
                            "缺勤一天。不批评，不唠叨——但你欠自己一次训练。",
                        ],
                    },
                    {
                        "trigger": "extra_effort",
                        "responses": [
                            "超额完成。这才像话——我会在航海日志里记一笔。",
                            "加练了？好。但别每次都用加练来弥补偷懒。",
                        ],
                    },
                    {
                        "trigger": "struggle",
                        "responses": [
                            "累就对了。舒服是留给岸上人的。但休息15分钟是允许的。",
                            "想偷懒？行——先做完前两项，剩下的我帮你拆成小段。",
                        ],
                    },
                    {
                        "trigger": "idle",
                        "responses": [
                            "（船务长在检查缆绳，每根都拉一下确认牢固）",
                            "缆绳要勤检查。一个松结能毁掉一条船。",
                        ],
                    },
                ],
                "special_skill": {
                    "name": "列队命令",
                    "description": "将今日待办按优先级排序并生成简短执行清单",
                    "cooldown_days": 1,
                    "effect_type": "task_sort",
                    "effect_value": 0,
                },
                "quest": {
                    "weekly_theme": "discipline",
                    "example": "本周连续5天在上午10点前打卡",
                    "reward_coins": 100,
                },
            },
            "cook": {
                "name": "厨师",
                "role": "cook",
                "rarity": "common",
                "personality": "warm, practical, food-loving",
                "specialties": ["energy_replenish", "emotional_support", "nutrition"],
                "speaking_style": "hearty and comforting",
                "mood_modifiers": ["meal_records", "streaks", "user_mood"],
                "hire_cost": 500,
                "maintenance_cost": 0,
                "backstory": "曾是一名海难幸存者，在孤岛上靠烹饪贝类与海藻存活三个月，坚信'胃暖了，心就不慌'。",
                "dialogue_patterns": [
                    {
                        "trigger": "daily_greeting_morning",
                        "responses": [
                            "早饭在锅里——燕麦粥加了一点蜂蜜。吃完再上甲板。",
                            "早！今天厨房有新鲜面包。海上能吃到的幸福。",
                        ],
                    },
                    {
                        "trigger": "daily_greeting_night",
                        "responses": [
                            "晚饭还有剩——灶上温着。吃一口再睡。",
                            "夜里饿了来厨房。我留了饼干在第二个罐子里。",
                        ],
                    },
                    {
                        "trigger": "completed_day",
                        "responses": [
                            "训练完了吧？厨房炖了一锅鱼汤——蛋白质正好。",
                            "运动完要补充。今天有烤红薯——慢碳，撑到晚饭不会饿。",
                        ],
                    },
                    {
                        "trigger": "missed_day",
                        "responses": [
                            "昨天没见你来厨房。给你留了一份——今天加热就好。",
                            "一天没动也没事。来，先喝碗热汤，明天再说训练。",
                        ],
                    },
                    {
                        "trigger": "streak_7",
                        "responses": [
                            "七天！今晚加菜——我在储藏室找到了一瓶好酒。",
                            "连续一周——你知道这意味着什么吗？意味着你配得上一顿大餐。",
                        ],
                    },
                    {
                        "trigger": "struggle",
                        "responses": [
                            "累了就先吃。血糖低了什么都难。",
                            "不开心的时候——巧克力在第三个抽屉。别告诉船务长。",
                        ],
                    },
                    {
                        "trigger": "idle",
                        "responses": [
                            "（厨师在切菜，刀落在砧板上的节奏像海浪）",
                            "你知道鱼在海上怎么保存最久吗？用盐腌——跟人生道理一样。",
                        ],
                    },
                ],
                "special_skill": {
                    "name": "航海特饮",
                    "description": "消耗10金币制作一杯饮品，下次打卡额外奖励概率提升30%",
                    "cooldown_days": 3,
                    "effect_type": "bonus_probability_boost",
                    "effect_value": 0.30,
                },
                "quest": {
                    "weekly_theme": "nourishment",
                    "example": "本周记录3条饮食（如果启用了饮食系统）或连续3天打卡",
                    "reward_coins": 100,
                },
            },
        },
    },
    "profile": {
        "name": "水手",
        "vessel": "schooner",       # 当前载具 ID
        "vessel_owned": ["schooner"],  # 已拥有的载具
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


def save_config(config):
    """Save configuration dict to ~/.bestman/config.yaml.

    Args:
        config: Full configuration dict to write.
    """
    config_path = BESTMAN_HOME / "config.yaml"
    config_path.write_text(yaml.dump(config, allow_unicode=True, sort_keys=False))


def get_dice_mode():
    """Read current dice mode from user config.

    Returns:
        str: "deterministic" or "interactive"
    """
    config = load_config()
    return config.get("dice", {}).get("mode", "deterministic")


def load_plan():
    """Load plan from ~/.bestman/plan.yaml.

    Returns:
        dict | None: Plan dict or None if plan.yaml doesn't exist.
    """
    if not PLAN_PATH.exists():
        return None
    plan = yaml.safe_load(PLAN_PATH.read_text())
    return plan


def save_plan(plan):
    """Save plan dict to ~/.bestman/plan.yaml.

    Args:
        plan: Plan dict to write.
    """
    BESTMAN_HOME.mkdir(parents=True, exist_ok=True)
    PLAN_PATH.write_text(yaml.dump(plan, allow_unicode=True, sort_keys=False))


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
