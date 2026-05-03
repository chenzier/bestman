class MapEngine:
    def __init__(self, total_days=175, milestones=None):
        self.total_days = total_days
        self.milestones = milestones or {}
        self.cols = 20
        self.rows = (total_days + self.cols - 1) // self.cols

    def _tile_char(self, i, tiles_revealed):
        """Return Rich markup for tile at position i."""
        if tiles_revealed == 0 or i > tiles_revealed:
            return "[dim blue]\u2592[/]"
        if i < tiles_revealed:
            if i in self.milestones:
                return "[bold magenta]\u2726[/]"
            return "[cyan]~[/]"
        # i == tiles_revealed
        return "[bold yellow]\u2693[/]"

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
    import random

    random.seed(day)
    return random.choice(VOYAGE_LOG_TEMPLATES)
