"""2D world map engine for bestman — pure logic, zero terminal dependencies.

Generates a predefined voyage route across a 50×14 grid and provides
position queries, stage information, and a ``build_render_data()`` method
that produces a dict suitable for consumption by any renderer backend
(ASCII / Canvas / Web).

Rendering is delegated to ``bestman.renderers``.
"""

import math
import random

# Grid constants
GRID_WIDTH = 50
GRID_HEIGHT = 14

# How many route tiles ahead of the ship to show as preview
FUTURE_VISIBLE = 10
# How many tiles behind the ship count as "near wake" (bold styling)
NEAR_WAKE = 5

# Fog defaults
FOG_CHAR = "\u2592"   # ▒
FOG_STYLE = "dim blue"

# Future route preview
PREVIEW_CHAR = "\u2218"  # ∘
PREVIEW_STYLE = "blue"

# Ship icon
SHIP_CHAR = "\u2693"   # ⚓
SHIP_STYLE = "bold yellow"

# Finish flag
FINISH_CHAR = "\U0001f3c1"  # 🏁
FINISH_STYLE = "bold green"

# Milestone marker
MILESTONE_CHAR = "\u2726"  # ✦
MILESTONE_STYLE = "bold magenta"

# Region terrain: maps stage name → (character, base_color)
STAGE_TERRAIN = {
    "启航": ("~", "cyan"),
    "迷雾之海": ("\u2592", "white"),
    "季风带": ("\u2248", "green"),
    "贸易航线": ("\u223f", "yellow"),
    "赤道无风带": ("\u2014", "yellow"),
    "信风带": ("/", "blue"),
    "新大陆近海": ("~", "cyan"),
}


class MapEngine:
    """2D world map logic engine.

    Generates a voyage route as a sequence of 175 (x, y) coordinates
    and provides position/region queries.  The ``build_render_data()``
    method produces a dict that renderers consume — this class itself
    never touches terminal output, Rich markup, or PNG pixels.
    """

    def __init__(self, config):
        """Initialise the 2D map engine.

        Args:
            config: Full bestman configuration dict, containing:
                - map.width, map.height (grid dimensions)
                - voyage.stages (7 stages with 1-based day ranges)
                - voyage.milestones (day → name mapping)
                - voyage.today_trail (highlight config)
        """
        map_cfg = config.get("map", {})
        self.width = map_cfg.get("width", GRID_WIDTH)
        self.height = map_cfg.get("height", GRID_HEIGHT)
        self.stages = config.get("voyage", {}).get("stages", [])
        self.milestones = config.get("voyage", {}).get("milestones", {})
        self.today_trail = config.get("today_trail", {
            "style": "custom",
            "color": "bright_red",
            "fade_steps": 3,
            "sway": {"enabled": True, "amplitude": 2, "fps": 8, "duration": 0.6},
        })

        # Generate route from stage definitions
        self.route = self._generate_route()
        self.total_days = len(self.route) if self.route else 175

        # Build milestone lookup: 0-based tile index → name
        self._milestone_tiles = {}
        milestones = self.milestones
        if milestones:
            for day, name in milestones.items():
                tile_idx = day - 1
                if 0 <= tile_idx < self.total_days:
                    self._milestone_tiles[tile_idx] = name

    # ── route generation ──────────────────────────────────────────

    def _generate_route(self):
        """Generate route coordinates from stage definitions.

        Uses a step-by-step walk that guarantees every tile maps to a
        distinct grid cell. The overall shape follows stage-specific
        sinusoidal patterns for visual variety, moving generally
        left-to-right across the grid.

        Returns:
            list of (x, y) tuples, one per tile (175 total).
        """
        if not self.stages:
            return self._fallback_route()

        route = []
        # Scale starting position to grid height
        start_y = max(1, min(self.height - 2, 10))
        px, py = 2, start_y
        route.append((px, py))
        used = {(px, py)}

        for stage_idx, stage in enumerate(self.stages):
            start_day, end_day = stage["days"]
            n = end_day - start_day + 1

            for i in range(n):
                tile_idx = start_day - 1 + i

                if tile_idx == 0:
                    continue

                t = tile_idx / 174.0
                target_x = int(round(2 + t * 46))
                local_t = (tile_idx - (start_day - 1)) / max(1, n - 1)
                target_y = int(round(self._stage_y(stage_idx, local_t)))
                target_y = max(1, min(self.height - 2, target_y))

                # Pick next step: prefer moving toward target, avoid used cells
                nx, ny = self._next_step(px, py, target_x, target_y, used)

                route.append((nx, ny))
                used.add((nx, ny))
                px, py = nx, ny

        return route

    def _next_step(self, px, py, target_x, target_y, used):
        """Compute the next grid cell toward (target_x, target_y).

        Prefers moves that advance toward the target while avoiding
        already-visited cells. Tries candidates in priority order.
        """
        candidates = []

        dx = target_x - px
        dy = target_y - py

        if dx > 0:
            # Priority: right, right+up, right+down, up, down
            candidates = [(px + 1, py), (px + 1, py + 1), (px + 1, py - 1),
                          (px, py + 1), (px, py - 1)]
        elif dx < 0:
            # Behind target x — move vertically or force right
            candidates = [(px, py + 1), (px, py - 1), (px + 1, py),
                          (px + 1, py + 1), (px + 1, py - 1)]
        else:
            # Same column — move vertically toward target, or right
            if dy > 0:
                candidates = [(px, py + 1), (px + 1, py + 1), (px + 1, py),
                              (px + 1, py - 1), (px, py - 1)]
            elif dy < 0:
                candidates = [(px, py - 1), (px + 1, py - 1), (px + 1, py),
                              (px + 1, py + 1), (px, py + 1)]
            else:
                candidates = [(px + 1, py), (px, py + 1), (px, py - 1),
                              (px + 1, py + 1), (px + 1, py - 1)]

        for cx, cy in candidates:
            cx = max(0, min(self.width - 1, cx))
            cy = max(0, min(self.height - 1, cy))
            if (cx, cy) not in used:
                return (cx, cy)

        # Fallback: any adjacent unused cell
        for dx2 in (1, 0, -1):
            for dy2 in (1, 0, -1):
                cx, cy = px + dx2, py + dy2
                cx = max(0, min(self.width - 1, cx))
                cy = max(0, min(self.height - 1, cy))
                if (cx, cy) not in used:
                    return (cx, cy)

        # Shouldn't happen: no unused adjacent cells
        return (px + 1, py)  # force right

    def _fallback_route(self):
        """Generate a simple zigzag route when no stages are configured."""
        route = [(2, 10)]
        px, py = 2, 10
        direction = 1
        for i in range(1, 175):
            t = i / 174.0
            target_x = int(round(2 + t * 46))
            if target_x > px:
                px = target_x
                py = max(1, min(12, py + direction))
                direction *= -1
            else:
                py = max(1, min(12, py + direction))
            route.append((px, py))
        return route

    def _stage_y(self, stage_idx, local_t):
        """Compute y-coordinate for a point within a stage.

        Each stage uses a different wave pattern for visual variety.
        local_t ranges from 0.0 (stage start) to 1.0 (stage end).
        """
        if stage_idx == 0:  # 启航: gentle departure from port
            return 10 - local_t * 2.5 + 0.5 * math.sin(local_t * math.pi * 1.5)
        elif stage_idx == 1:  # 迷雾之海: erratic wandering through fog
            return 7.5 - local_t * 1.5 + 2.5 * math.sin(local_t * math.pi * 4)
        elif stage_idx == 2:  # 季风带: steady push upward
            return 6 - local_t * 3.5 + math.sin(local_t * math.pi * 2.5)
        elif stage_idx == 3:  # 贸易航线: gentle meander
            return 2.5 + local_t * 3 + math.sin(local_t * math.pi * 3)
        elif stage_idx == 4:  # 赤道无风带: slow drift
            return 5.5 + local_t * 1 + 2 * math.sin(local_t * math.pi * 2)
        elif stage_idx == 5:  # 信风带: fast straight push
            return 6.5 - local_t * 2
        elif stage_idx == 6:  # 新大陆近海: approach to land
            return 4.5 - local_t * 1 + 2 * math.sin(local_t * math.pi * 5)
        return 7  # fallback

    # ── position / region queries ─────────────────────────────────

    def get_current_position(self, tiles_revealed):
        """Return the (x, y) coordinate of the ship.

        Args:
            tiles_revealed: Number of tiles revealed so far (0-based count).

        Returns:
            (x, y) tuple, or None if the route is empty.
        """
        if not self.route:
            return None
        idx = min(tiles_revealed, self.total_days - 1)
        return self.route[idx]

    def get_region_at(self, tiles_revealed):
        """Return the region name at the current tile position.

        Args:
            tiles_revealed: Number of tiles revealed so far.

        Returns:
            Region name string (e.g. "贸易航线").
        """
        if tiles_revealed <= 0:
            return self.stages[0]["name"] if self.stages else "未知"
        tile_idx = min(tiles_revealed - 1, self.total_days - 1)
        return self._stage_for_tile(tile_idx)["name"]

    def _stage_for_tile(self, tile_idx):
        """Return the stage dict for a 0-based tile index."""
        for stage in self.stages:
            start, end = stage["days"]
            if start - 1 <= tile_idx <= end - 1:
                return stage
        return {"name": "未知"}

    def _terrain_for_tile(self, tile_idx):
        """Get (character, color) for the terrain at a route tile."""
        stage = self._stage_for_tile(tile_idx)
        return STAGE_TERRAIN.get(stage["name"], ("~", "cyan"))

    # ── render data building ──────────────────────────────────────

    def build_render_data(self, tiles_revealed=0, today_advance=0,
                          sway_offset=0.0, sway_phase=0.0):
        """Build a renderer-agnostic data dict for map display.

        This replaces the old ``render()`` method.  The returned dict
        contains all the information any renderer backend needs —
        no Rich markup, no PNG pixels, no terminal escape sequences.

        Args:
            tiles_revealed: Number of tiles revealed (0-based count).
            today_advance: Number of tiles advanced today (distance + extra).
            sway_offset: Sway amplitude multiplier for ship sway animation.
            sway_phase: Phase shift for the sin wave.

        Returns:
            dict with keys:
                grid: 2D list of cell dicts (see _build_grid)
                ship_pos: (x, y) or None
                route: list of (x, y) tuples
                tiles_revealed, total_days, today_advance
                milestones: {day: name} dict
                sway_offset, sway_phase
        """
        tiles_revealed = max(0, min(tiles_revealed, self.total_days))
        grid = self._build_grid(tiles_revealed, today_advance, sway_offset, sway_phase)

        # Ship position (0-based index)
        ship_pos = None
        if self.route and tiles_revealed < self.total_days:
            ship_pos = self.route[tiles_revealed]
        elif self.route:
            ship_pos = self.route[-1]

        return {
            "grid": grid,
            "ship_pos": ship_pos,
            "route": self.route,
            "tiles_revealed": tiles_revealed,
            "total_days": self.total_days,
            "today_advance": today_advance,
            "milestones": dict(self.milestones),
            "sway_offset": sway_offset,
            "sway_phase": sway_phase,
            "width": self.width,
            "height": self.height,
        }

    def _build_grid(self, tiles_revealed, today_advance, sway_offset, sway_phase):
        """Build a 2D list of cell dicts for the map grid.

        Each cell dict has:
            x, y: grid coordinates
            status: "fog" | "explored" | "preview" | "wake"
            terrain_char: str
            terrain_color: str
            has_ship: bool
            has_milestone: bool
            has_finish: bool
            is_today_trail: bool
            trail_fade: int (0=newest, higher=older)

        Returns:
            list[list[dict]]: ``height × width`` grid of cell dicts.
        """
        walked_count = min(tiles_revealed, self.total_days)

        # Build default fog grid
        grid = [[{
            "x": x, "y": y,
            "status": "fog",
            "terrain_char": FOG_CHAR,
            "terrain_color": FOG_STYLE.replace("dim ", ""),
            "has_ship": False,
            "has_milestone": False,
            "has_finish": False,
            "is_today_trail": False,
            "trail_fade": 0,
        } for x in range(self.width)] for y in range(self.height)]

        # Draw walked route
        for i in range(walked_count):
            x, y = self.route[i]
            if not (0 <= x < self.width and 0 <= y < self.height):
                continue
            char, color = self._terrain_for_tile(i)
            dist_behind = tiles_revealed - i

            cell = grid[y][x]
            cell["terrain_char"] = char
            cell["terrain_color"] = color

            if today_advance > 0 and dist_behind <= today_advance:
                # Today's trail with fade levels
                step = today_advance - dist_behind  # 0=oldest
                fade_steps = self.today_trail.get("fade_steps", 3)
                divisor = max(1, today_advance // fade_steps) + 1
                fade_level = step // divisor
                cell["status"] = "explored"
                cell["is_today_trail"] = True
                cell["trail_fade"] = fade_level
                cell["today_color"] = self.today_trail.get("color", "bright_red")
            elif dist_behind <= NEAR_WAKE:
                cell["status"] = "wake"
            else:
                cell["status"] = "explored"

        # Draw future route preview (next FUTURE_VISIBLE tiles)
        preview_start = tiles_revealed + 1
        preview_end = min(preview_start + FUTURE_VISIBLE, self.total_days)
        for i in range(preview_start, preview_end):
            x, y = self.route[i]
            if not (0 <= x < self.width and 0 <= y < self.height):
                continue
            if i in self._milestone_tiles:
                grid[y][x] = {
                    "x": x, "y": y,
                    "status": "preview",
                    "terrain_char": MILESTONE_CHAR,
                    "terrain_color": MILESTONE_STYLE.replace("bold ", ""),
                    "has_ship": False,
                    "has_milestone": True,
                    "has_finish": False,
                    "is_today_trail": False,
                    "trail_fade": 0,
                }
            else:
                grid[y][x] = {
                    "x": x, "y": y,
                    "status": "preview",
                    "terrain_char": PREVIEW_CHAR,
                    "terrain_color": PREVIEW_STYLE,
                    "has_ship": False,
                    "has_milestone": False,
                    "has_finish": False,
                    "is_today_trail": False,
                    "trail_fade": 0,
                }

        # Place milestone markers on walked route
        for mile_tile in self._milestone_tiles:
            if mile_tile < tiles_revealed:
                x, y = self.route[mile_tile]
                if 0 <= x < self.width and 0 <= y < self.height:
                    grid[y][x]["has_milestone"] = True
                    grid[y][x]["terrain_char"] = MILESTONE_CHAR

        # Place ship or finish flag
        if self.route and tiles_revealed >= self.total_days:
            x, y = self.route[-1]
            if 0 <= x < self.width and 0 <= y < self.height:
                grid[y][x]["has_finish"] = True
                grid[y][x]["terrain_char"] = FINISH_CHAR
        elif self.route and tiles_revealed < self.total_days:
            x, y = self.route[tiles_revealed]
            if 0 <= x < self.width and 0 <= y < self.height:
                grid[y][x]["has_ship"] = True
                grid[y][x]["terrain_char"] = SHIP_CHAR

        # Apply sway offset to each row
        if sway_offset != 0.0:
            import math as _math
            for y in range(self.height):
                offset = int(sway_offset * _math.sin(y * 0.8 + sway_phase))
                if offset == 0:
                    continue
                row = grid[y]
                fog_cell = {
                    "x": 0, "y": y,
                    "status": "fog",
                    "terrain_char": FOG_CHAR,
                    "terrain_color": FOG_STYLE.replace("dim ", ""),
                    "has_ship": False,
                    "has_milestone": False,
                    "has_finish": False,
                    "is_today_trail": False,
                    "trail_fade": 0,
                }
                if offset > 0:
                    grid[y] = [fog_cell] * offset + row[:-offset]
                else:
                    offset = -offset
                    grid[y] = row[offset:] + [fog_cell] * offset

        return grid

    # ── stage interface ────────────────────────────────────────────

    def get_current_stage(self, tiles_revealed):
        """Return stage sections for interface compatibility.

        Preserved for any remaining callers. Returns the current stage
        name alongside stage metadata.
        """
        # Ship is at tile index = tiles_revealed
        current_idx = None
        for i, stage in enumerate(self.stages):
            s, e = stage["days"]
            if s - 1 <= tiles_revealed <= e - 1:
                current_idx = i
                break

        if current_idx is None:
            if not self.stages:
                return [], {"name": "航程", "days": [1, self.total_days]}, None, 0
            current_idx = max(0, min(len(self.stages) - 1,
                                     sum(1 for _ in self.stages)))
            # Clamp to first or last
            if tiles_revealed < 0:
                current_idx = 0
            else:
                current_idx = len(self.stages) - 1

        completed = self.stages[:current_idx]
        current = self.stages[current_idx]
        nxt = self.stages[current_idx + 1] if current_idx + 1 < len(self.stages) else None

        return completed, current, nxt, current_idx


# ── voyage log templates ──────────────────────────────────────────

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
