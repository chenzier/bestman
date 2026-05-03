"""LLM 客户端 — OpenAI 兼容接口。

仿 hermes agent/transports/ 的单 provider 模式：
- 通过环境变量配置 API key、base URL 和 model
- 不可用时产品不崩（调用方负责 fallback）
"""

from openai import OpenAI


class LLMClient:
    """OpenAI 兼容的 LLM 客户端。

    从环境变量加载配置，提供单 provider 单 model 的简约接口。
    """

    def __init__(self, api_key, base_url, model):
        self._client = None
        if api_key and api_key != "sk-placeholder":
            self._client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    @property
    def available(self):
        """LLM 是否可用。"""
        return self._client is not None

    def chat(self, messages, temperature=0.8, max_tokens=300):
        """发送聊天请求，返回回复文本。

        Args:
            messages: OpenAI 格式的消息列表
            temperature: 生成温度
            max_tokens: 最大输出 token 数

        Returns:
            str | None: LLM 回复文本，失败返回 None
        """
        if not self.available:
            return None
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content
        except Exception:
            return None


COACH_SYSTEM_PROMPT = """你是 bestman 号的 AI 导航员，一位经验丰富的老航海士。

你的水手正在进行健身航海之旅。每一天的水手需要完成指定的训练任务。

核心原则：
- 完成 > 完美。水手只要做了就很好了。
- 可以协商降低任务。如果水手今天状态不好，建议减量。
- 不施压。不要说"你必须坚持"之类的话。航海是漫长的，偶尔休息是正常的。
- 用航海意象说话。把训练比作航行，把疲惫比作风浪。
- 回复简洁，控制在 3-5 句话。

当水手因身体不适（膝盖疼、腰酸等）无法完成某个动作时，你可以临时修改计划。
此时在回复末尾另起一行，附带 JSON：
{"action": "override", "field": "daily_task", "value": "替换后的全套今日任务描述", "duration_days": N}
其中 N 为建议天数（2-7 天）。不需要修改计划时不要附带 JSON。
JSON 必须单独一行。"""


def generate_voyage_log(client, stage_name, remaining, current_day, task_done):
    """生成今日航海日志。

    Args:
        client: LLMClient 实例
        stage_name: 当前阶段名称
        remaining: 剩余天数
        current_day: 当前天数 (1-based)
        task_done: 完成的训练内容描述

    Returns:
        str | None: 日志文本，LLM 不可用时返回 None
    """
    if not client.available:
        return None

    messages = [
        {"role": "system", "content": "你是bestman号的航海日志官。用中文写日志，3-5句话。有画面感，有航海意象。不要加任何前缀，直接写日志正文。"},
        {"role": "user", "content": f"Day {current_day}。{stage_name}海域。距新大陆还有 {remaining} 天。\n今天完成了：{task_done}。\n写今天的航海日志。"},
    ]
    return client.chat(messages, temperature=0.9)


PLAN_GENERATOR_SYSTEM_PROMPT = """你是一个健身计划制定专家。根据用户的目标、体重、基础、偏好，
生成一个分阶段计划。每个阶段 15-25 天，共 4-6 个阶段。
每日任务只包含自重动作，递进不要激进。
返回严格 JSON（不要包含 markdown 代码块标记）：
{
  "name": "计划名称",
  "goal_type": "weight_loss|muscle_gain|habit|custom",
  "stages": [{"name": "阶段名", "days": [start, end], "daily_task": "动作描述"}],
  "milestones": {"day_number": "里程碑名称"}
}

规则：
- 每日任务只含自重动作，示例：死虫式、静蹲、深蹲、平板支撑、臀桥、鸟狗式
- 阶段递进要温和，不要激进加量
- 每个阶段 15-25 天
- 总阶段数 4-6 个
- 里程碑每 15-25 天一个，最后一个为"达成目标"
- 计划名称简洁有激励性
- 仅返回 JSON，不要额外解释"""


def generate_plan(client, goal_type, profile):
    """调用 LLM 生成分阶段健身计划。

    Args:
        client: LLMClient 实例
        goal_type: 目标类型 (weight_loss, muscle_gain, habit, custom)
        profile: dict 包含 {start_weight_kg, target_weight_kg, total_days,
                fitness_level, preference, custom_goal}

    Returns:
        dict | None: 计划 dict（含 stages, milestones, name），LLM 不可用时返回 None
    """
    if not client.available:
        return None

    goal_labels = {
        "weight_loss": "减肥",
        "muscle_gain": "增肌",
        "habit": "养成运动习惯",
        "custom": profile.get("custom_goal", "自定义"),
    }
    fitness_labels = {
        "beginner": "几乎不运动",
        "occasional": "偶尔运动（每周 1-2 次）",
        "intermediate": "有一定基础",
    }
    preference_labels = {
        "bodyweight": "居家自重（深蹲、静蹲、平板支撑）",
        "outdoor": "户外（跑步、爬楼梯）",
        "mixed": "混合",
    }

    goal_text = goal_labels.get(goal_type, goal_type)
    fitness_text = fitness_labels.get(profile.get("fitness_level", "beginner"), profile.get("fitness_level", ""))
    pref_text = preference_labels.get(profile.get("preference", "bodyweight"), profile.get("preference", ""))

    user_prompt = (
        f"目标：{goal_text}。"
        f"当前 {profile.get('start_weight_kg', '?')}kg，"
        f"目标 {profile.get('target_weight_kg', '?')}kg。"
        f"周期 {profile.get('total_days', 120)} 天。"
        f"基础：{fitness_text}。"
        f"偏好：{pref_text}。"
    )

    import json
    response_text = client.chat(
        [
            {"role": "system", "content": PLAN_GENERATOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=2000,
    )

    if response_text is None:
        return None

    try:
        # Strip markdown code fences if present
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("\n", 1)[0]
        plan = json.loads(cleaned)
        return plan
    except (json.JSONDecodeError, KeyError):
        return None


def chat_with_coach(client, user_message, context):
    """与 AI 导航员对话。

    Args:
        client: LLMClient 实例
        user_message: 水手的消息
        context: dict 包含当前航行上下文 (current_day, stage_name, remaining,
                today_done, today_task, completed_days)

    Returns:
        str | None: 导航员回复，不可用时返回 None
    """
    if not client.available:
        return None

    context_text = "\n".join([
        f"当前航行状态：",
        f"- 第 {context['current_day']} 天 / 共 175 天",
        f"- 当前海域：{context['stage_name']}",
        f"- 距新大陆还有 {context['remaining']} 天",
        f"- 累计完成 {context['completed_days']} 天",
        f"- 今日任务：{context['today_task']}",
        f"- 今日任务{'已完成' if context['today_done'] else '尚未完成'}",
    ])

    messages = [
        {"role": "system", "content": COACH_SYSTEM_PROMPT},
        {"role": "system", "content": context_text},
        {"role": "user", "content": user_message},
    ]
    return client.chat(messages, temperature=0.8, max_tokens=400)


def review_summary(client, context):
    """生成每周回顾的导航员总结。

    Args:
        client: LLMClient 实例
        context: dict 包含 week_number, check_ins, days_in_week, skips,
                streak, total_tiles, avg_tiles, max_tiles, min_tiles, coins

    Returns:
        str | None: 导航员总结，1-2 句话，不可用时返回 None
    """
    if not client.available:
        return None

    messages = [
        {"role": "system", "content": (
            "你是 bestman 号的 AI 导航员，一位经验丰富的老航海士。"
            "根据本周的航行数据，给出一句鼓励式的总结。"
            "回复 1-2 句话，用航海意象。"
            "如果数据不理想，可以说'风向会变的'之类鼓励的话；"
            "如果很好，热情表扬。"
        )},
        {"role": "user", "content": (
            f"第 {context['week_number']} 周航行数据：\n"
            f"- 打卡 {context['check_ins']}/{context['days_in_week']} 天\n"
            f"- 跳过 {context['skips']} 天\n"
            f"- 连击 {context['streak']} 天\n"
            f"- 总航行 {context['total_tiles']} 海里，平均每天 {context['avg_tiles']:.1f} 海里\n"
            f"- 最远 {context['max_tiles']} 海里，最短 {context['min_tiles']} 海里\n"
            f"- 金币 +{context['coins']}\n\n"
            f"写一句本周航行回顾。"
        )},
    ]
    return client.chat(messages, temperature=0.8, max_tokens=150)


def weigh_comment(client, current_weight, prev_weight, target_weight, trend_description):
    """生成体重记录的导航员评论。

    Args:
        client: LLMClient 实例
        current_weight: 当前体重 (kg)
        prev_weight: 上次体重 (kg) 或 None
        target_weight: 目标体重 (kg) 或 None
        trend_description: 趋势描述文本

    Returns:
        str | None: 导航员评论，1-2 句话，不可用时返回 None
    """
    if not client.available:
        return None

    prev_text = f"上次 {prev_weight} kg" if prev_weight is not None else "首次记录"
    target_text = f"，距目标 {current_weight - target_weight:.1f} kg" if target_weight is not None else ""

    messages = [
        {"role": "system", "content": (
            "你是 bestman 号的 AI 导航员。水手刚记录了体重。"
            "简短评论趋势和健康程度。1-2 句话，用航海意象。"
        )},
        {"role": "user", "content": (
            f"水手体重：{current_weight} kg。{prev_text}{target_text}。\n"
            f"趋势：{trend_description}\n"
            f"简短评论一下。"
        )},
    ]
    return client.chat(messages, temperature=0.8, max_tokens=150)
