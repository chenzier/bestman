"""Segmented map engine with theme support.

Renders a voyage map as stacked stage progress bars instead of a 175-tile grid.
Each stage is a single row showing progress within that segment.
"""

import random

from bestman.themes import get_theme

BAR_WIDTH = 25


class MapEngine:
    """Segmented map renderer.

    Takes a list of stages and renders them as progress bars.
    Shows completed stages + current stage + next stage (at most).
    """

    def __init__(self, stages=None, milestones=None, theme="naval"):
        """
        Args:
            stages: List of stage dicts from config, each with "name" and "days" [start, end].
                    Both start and end are 1-based day numbers.
            milestones: Dict mapping 0-based tile index to milestone name.
            theme: Theme name string ("naval" or "cultivation").
        """
        self.stages = stages or []
        self.milestones = milestones or {}
        self.theme = get_theme(theme)
        self._bar_width = BAR_WIDTH

        # Compute total_days from last stage
        if self.stages:
            self.total_days = self.stages[-1]["days"][1]
        else:
            self.total_days = 175

    def get_current_stage(self, tiles_revealed):
        """Return all stage sections relevant for rendering.

        tiles_revealed is a 0-based count of revealed tiles (ship position in 0-based grid).
        stages use 1-based day numbers in config, so we convert to 0-based for comparison.

        Returns (completed_stages, current_stage, next_stage, current_stage_idx).
        """
        current_day = tiles_revealed  # 0-based; ship is at this tile index

        current_stage_idx = None
        for i, stage in enumerate(self.stages):
            _start, _end = stage["days"]
            # Convert 1-based stage boundaries to 0-based tile indices
            if _start - 1 <= current_day <= _end - 1:
                current_stage_idx = i
                break

        if current_stage_idx is None:
            if not self.stages:
                # No stages configured — treat everything as one big stage
                return [], {"name": "航程", "days": [1, self.total_days]}, None, 0
            if current_day < self.stages[0]["days"][0]:
                current_stage_idx = 0
            else:
                current_stage_idx = len(self.stages) - 1

        completed = self.stages[:current_stage_idx]
        current = self.stages[current_stage_idx]
        nxt = self.stages[current_stage_idx + 1] if current_stage_idx + 1 < len(self.stages) else None

        return completed, current, nxt, current_stage_idx

    def render(self, tiles_revealed=0):
        """Render segmented progress bars.

        Args:
            tiles_revealed: 0-based count of revealed tiles (from state).

        Returns:
            Rich markup string with one row per visible stage.
        """
        if not self.stages:
            return "[dim]No stages configured[/dim]"

        completed, current, nxt, _ = self.get_current_stage(tiles_revealed)

        lines = []

        # Show only the most recent completed stage (keep rows minimal)
        if completed:
            lines.append(self._render_completed(completed[-1]))

        # Current stage
        lines.append(self._render_current(current, tiles_revealed))

        # Next stage (locked)
        if nxt:
            lines.append(self._render_locked(nxt))

        return "\n".join(lines)

    def _stage_display_name(self, stage):
        """Get themed display name for a stage."""
        return self.theme.stage_display_name(stage["name"])

    def _revealed_in_stage(self, stage, tiles_revealed):
        """How many tiles have been revealed within this stage."""
        _start = stage["days"][0]
        _end = stage["days"][1]
        stage_tiles = _end - _start + 1
        revealed = tiles_revealed - _start + 1
        return max(0, min(stage_tiles, revealed))

    def _render_completed(self, stage):
        """Render a filled progress bar for a completed stage."""
        name = self._stage_display_name(stage)
        bar = self.theme.completed_bar(self._bar_width)
        status = f"{self.theme.tiles.complete_markup} 完成"
        return f"{name:<8}  {bar}  {status}"

    def _render_current(self, stage, tiles_revealed):
        """Render the currently active stage bar."""
        name = self._stage_display_name(stage)
        stage_tiles = stage["days"][1] - stage["days"][0] + 1
        revealed = self._revealed_in_stage(stage, tiles_revealed)

        chars = []
        for pos in range(self._bar_width):
            chars.append(
                self.theme.bar_fill(pos, self._bar_width, revealed, stage_tiles)
            )
        bar = "".join(chars)

        # Check for completion — if all tiles revealed, show finish/checkmark
        if revealed >= stage_tiles and revealed > 0:
            status = f"{self.theme.tiles.complete_markup} 完成"
        else:
            status = f"{revealed}/{stage_tiles}"

        return f"{name:<8}  {bar}  {status}"

    def _render_locked(self, stage):
        """Render a locked (unreached) stage bar."""
        name = self._stage_display_name(stage)
        bar = self.theme.locked_bar(self._bar_width)
        status = f"{self.theme.tiles.lock_markup} 即将解锁"
        return f"{name:<8}  {bar}  {status}"


# ── voyage log templates (unchanged) ──

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
