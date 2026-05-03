"""随机事件引擎 — 每天打卡后概率触发。

事件类型三种：
- bonus_tile: 顺风，自动推进 +1 格
- encouragement: 纯文本奖励，传递正向情绪
- challenge: 提示用户多做一组动作
"""

import random

DEFAULT_EVENTS = [
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
]


class EventEngine:
    """随机事件引擎。

    用 day 作为随机种子，保证同一天永远返回同一事件。"""

    def __init__(self, config=None):
        if config is None:
            config = {}
        self.events = config.get("events", DEFAULT_EVENTS)

    def check(self, day):
        """检查今天是否触发事件。

        Args:
            day: 当前天数（1-based）。

        Returns:
            dict | None: 触发的事件 dict，或 None（无事件）。
        """
        r = random.Random(day * 997 + 13)
        roll = r.random()
        cumulative = 0.0
        for evt in self.events:
            cumulative += evt.get("probability", 0)
            if roll < cumulative:
                return dict(evt)
        return None
