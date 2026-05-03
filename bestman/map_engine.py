import random


class MapEngine:
    def __init__(self, total_days=175, milestones=None):
        self.total_days = total_days
        self.milestones = milestones or {}
        self.cols = 20
        self.rows = (total_days + self.cols - 1) // self.cols
        self._decorations = {}
        self._generate_decorations()

    def _generate_decorations(self):
        """在已探索区域生成随机装饰，用固定种子保证确定性。"""
        r = random.Random(42)
        for i in range(1, self.total_days):  # 跳过第 0 格
            if i in self.milestones:
                continue
            roll = r.random()
            if roll < 0.15:
                self._decorations[i] = "\U0001f41f"  # 🐟
            elif roll < 0.22:
                self._decorations[i] = "\u2b50"  # ⭐

    def _tile_char(self, i, tiles_revealed):
        """返回 Rich markup 字符串。"""
        # 终点：航程完成，最后一个格子显示 🏁
        if tiles_revealed >= self.total_days and i == self.total_days - 1:
            return "[bold green]\U0001f3c1[/]"  # 🏁

        if i > tiles_revealed:
            # 未探索区域
            r = random.Random(i * 137 + 42)
            if r.random() < 0.1:
                return "[dim blue]\u2591[/]"  # ░
            # 前方 5 格内里程碑线索
            for mi in self.milestones:
                if 0 < mi - tiles_revealed <= 5 and abs(i - mi) <= 1:
                    return "[blue]\u2591[/]"  # ░
            return "[dim blue]\u2593[/]"  # ▓

        if i == tiles_revealed:
            # 船位
            if i in self.milestones:
                return "[bold magenta]\u2726[/]"  # ✦ 到达里程碑
            return "[bold yellow]\u2693[/]"  # ⚓

        # 已探索区域
        distance = tiles_revealed - i

        if i in self.milestones:
            if distance <= 3:
                return "[bold magenta]\u2726[/]"  # ✦ 刚到达
            return "[dim magenta]\u2726[/]"  # ✦ 走过的

        if distance <= 3:
            return "[bold cyan]\u2248[/]"  # ≈ 尾迹

        if i in self._decorations:
            return f"[cyan]{self._decorations[i]}[/]"

        return "[cyan]~[/]"

    def render(self, tiles_revealed=0):
        """Return Rich markup string for the map."""
        total = self.total_days
        lines = []
        for row in range(self.rows):
            start = row * self.cols
            end = min(start + self.cols, total)
            line_chars = [self._tile_char(i, tiles_revealed) for i in range(start, end)]
            lines.append("".join(line_chars))
        return "\n".join(lines)


VOYAGE_LOG_TEMPLATES = [
    "晨光洒在甲板上，bestman 号缓缓驶出港口。水手们精神抖擞，风帆鼓满西风。前方是未知的海洋——但今天，我们只需要航行这一格。",
    "海面平静如镜。瞭望手在主桅上打盹，舵手哼着古老的船歌。平静的一天也是好的一天。",
    "西南风转强，船身微微倾斜。水手们收紧帆索，甲板上响起整齐的号子声。乘风破浪就是这种感觉。",
    "灰云压境，浪头拍打船舷。船长下令缩帆减速。有时候慢一点不是退缩，是为了走得更远。",
    "东方破晓，海上日出如熔金般倾泻。在晨光中做死虫式，甲板就是最好的训练场。",
    "午后遇见一群海豚，在船头追逐嬉戏。它们知道前方有什么——新大陆的轮廓在等待。",
    "薄雾笼罩海面，能见度不足三链。但这正是考验航海术的时候。稳住航向，钟声作伴。",
    "傍晚时分，天边浮现积雨云。暴风雨在逼近，但 bestman 号已做好准备。风浪再大，也大不过一颗坚持的心。",
    "星空璀璨如碎钻，银河横跨天顶。值夜班的水手指着北极星说：那就是我们的方向。",
    "航道偏西三度，舵手调整航向。微小的偏差在175天里会被放大——每天修正一点点，就能准确抵达。",
    "南风送来暖意，甲板上的木桶在阳光下散出焦糖味。今天又是完成训练的一天。",
    "浪涌如玉，船首破开碧波。瞭望手报告：前方有鲸群，左舷三百米。大自然的勋章。",
    "午后雷暴骤至，巨浪如墙。bestman 号在波谷中颠簸，但龙骨稳如磐石。风雨过后，海面如洗。",
    "新月如钩，海面洒满碎银。在静蹲中感受船身的起伏——核心稳，航向就稳。",
    "清晨船钟敲响八下。昨日已逝，今日已至。bestman 号继续向西，不停歇。",
]


def get_log_entry(day, _stage=None):
    """Return a deterministic voyage log entry for the given day."""
    random.seed(day)
    return random.choice(VOYAGE_LOG_TEMPLATES)
