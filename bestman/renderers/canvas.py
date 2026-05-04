"""Canvas PNG renderer — Kitty graphics protocol display.

Renders the voyage map as a single PNG image and displays it directly
in the terminal via the Kitty graphics protocol.  No ASCII grid,
no line-by-line cursor positioning — one image, one escape sequence.

Supported terminals: Ghostty, iTerm2, WezTerm, Kitty (any terminal
that implements the Kitty graphics protocol).

Implements ``BaseRenderer`` for the three-layer architecture.
"""

import base64
import math
import os
import random
import struct
import sys
import zlib

from bestman.renderers.base import BaseRenderer
from bestman.themes.naval import get_stage_texture


# ── 画布尺寸 ─────────────────────────────────────────────────────
# 与 map_engine 的 50×14 网格对应

CANVAS_COLS = 50
CANVAS_ROWS = 14
CELL = 20          # 每格像素（含 1px 网格线）
PAD_X = 8          # 左边距
PAD_Y = 80         # 上边距（标题区域）
W = CANVAS_COLS * CELL + PAD_X * 2
H = CANVAS_ROWS * CELL + PAD_Y + 8


# ── 颜色 ─────────────────────────────────────────────────────────

# 基础色
BG      = (8, 16, 24, 255)
BLACK   = (0, 0, 0, 255)
WHITE   = (255, 255, 240, 255)
TRANS   = (0, 0, 0, 0)

# 海洋色（已揭示）
OCEAN_A = (21, 104, 112, 255)   # 深青
OCEAN_B = (26, 128, 120, 255)   # 蓝绿
OCEAN_C = (14, 92, 96, 255)     # 暗青
OCEAN_D = (18, 80, 88, 255)     # 深蓝绿

# 迷雾色（未揭示）
MIST    = (22, 38, 54, 255)

# 网格线
GRID_LINE = (20, 60, 80, 80)

# 高亮色
GOLD    = (255, 215, 0, 255)
CYAN    = (80, 210, 255, 255)

# 里程碑 & 标志
STAR_COLOR      = (255, 215, 0, 255)
ISLAND_COLOR    = (32, 140, 60, 255)
ISLAND_TRUNK    = (100, 60, 30, 255)
FINISH_COLOR    = (48, 208, 112, 255)

# 光晕色
GLOW_R = 255
GLOW_G = 200
GLOW_B = 60

# 标题色
TITLE_COLOR     = (78, 201, 176, 255)
SUBTITLE_COLOR  = (86, 156, 214, 255)


# ── 默认阶段配置（纹理映射用）─────────────────────────────────

_DEFAULT_STAGES = [
    {"name": "启航", "days": [1, 25]},
    {"name": "迷雾之海", "days": [26, 50]},
    {"name": "季风带", "days": [51, 75]},
    {"name": "贸易航线", "days": [76, 100]},
    {"name": "赤道无风带", "days": [101, 125]},
    {"name": "信风带", "days": [126, 150]},
    {"name": "新大陆近海", "days": [151, 175]},
]


# ── 纹理绘制 ─────────────────────────────────────────────────────

def draw_texture(cell_cx: int, cell_cy: int, texture_def, base_map: dict):
    """Draw a texture into a grid cell's interior on the base map.

    Maps each pixel of the texture matrix to the cell interior
    (CELL−2 × CELL−2 pixels, skipping the 1 px grid border).

    Args:
        cell_cx: Grid column of the cell.
        cell_cy: Grid row of the cell.
        texture_def: TextureDef with ``.pixels`` and ``.palette``.
        base_map: Dict ``{(x, y): (R,G,B,A)}`` to draw into.
    """
    origin_x = PAD_X + cell_cx * CELL + 1
    origin_y = PAD_Y + cell_cy * CELL + 1
    inner = CELL - 2  # cell interior size (18 px for CELL=20)

    for ty, row in enumerate(texture_def.pixels):
        if ty >= inner:
            break
        for tx, ch in enumerate(row):
            if tx >= inner:
                break
            color = texture_def.palette.get(ch)
            if color and len(color) >= 4 and color[3] > 0:
                px = origin_x + tx
                py = origin_y + ty
                base_map[(px, py)] = color


# ── PNG 生成 ─────────────────────────────────────────────────────

def make_png(width: int, height: int, pixel_fn) -> bytes:
    """Generate a raw PNG from a pixel callback.

    Args:
        width: Image width in pixels.
        height: Image height in pixels.
        pixel_fn: Callable ``(x, y) → (R, G, B, A)``.

    Returns:
        PNG file as bytes.
    """
    # Build RGBA pixel array with filter-byte prefix per row
    pixels = bytearray()
    for y in range(height):
        pixels.append(0)  # filter none
        for x in range(width):
            r, g, b, a = pixel_fn(x, y)
            pixels.append(r)
            pixels.append(g)
            pixels.append(b)
            pixels.append(a)

    raw = bytes(pixels)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)

    def _chunk(ctype, data):
        c = ctype + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    return sig + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(raw)) + _chunk(b"IEND", b"")


# ── Kitty 协议 ───────────────────────────────────────────────────

def kitty_display(png_bytes: bytes, cols: int = 90, rows: int = 24):
    """Display a PNG in the terminal via the Kitty graphics protocol.

    Args:
        png_bytes: Raw PNG image data.
        cols: Terminal columns the image should occupy.
        rows: Terminal rows the image should occupy.
    """
    b64 = base64.b64encode(png_bytes).decode()
    chunk_size = 4096
    chunks = [b64[i:i + chunk_size] for i in range(0, len(b64), chunk_size)]
    ctrl = f"\033_Ga=T,f=100,c={cols},r={rows}"
    if len(chunks) == 1:
        sys.stdout.write(f"{ctrl};{chunks[0]}\033\\")
    else:
        sys.stdout.write(f"{ctrl},m=1;{chunks[0]}\033\\")
        for c in chunks[1:-1]:
            sys.stdout.write(f"\033_Gm=1;{c}\033\\")
        sys.stdout.write(f"\033_Gm=0;{chunks[-1]}\033\\")
    sys.stdout.flush()


def kitty_available() -> bool:
    """Check whether the current terminal supports Kitty graphics protocol.

    Detects Ghostty, Kitty, iTerm2, WezTerm via environment variables.
    """
    term_program = os.environ.get("TERM_PROGRAM", "")
    if term_program in ("ghostty", "Kitty", "iTerm.app", "WezTerm"):
        return True
    if "KITTY_WINDOW_ID" in os.environ:
        return True
    # Some terminals set TERM to xterm-kitty
    if os.environ.get("TERM", "") == "xterm-kitty":
        return True
    return False


# ── 像素文字 ─────────────────────────────────────────────────────

FONT_5x7 = {
    'A': ['  #  ', ' # # ', '#   #', '#####', '#   #', '#   #', '#   #'],
    'B': ['#### ', '#   #', '#### ', '#   #', '#   #', '#   #', '#### '],
    'C': [' ### ', '#   #', '#    ', '#    ', '#    ', '#   #', ' ### '],
    'D': ['#### ', '#   #', '#   #', '#   #', '#   #', '#   #', '#### '],
    'E': ['#####', '#    ', '#### ', '#    ', '#    ', '#    ', '#####'],
    'F': ['#####', '#    ', '#### ', '#    ', '#    ', '#    ', '#    '],
    'G': [' ### ', '#   #', '#    ', '#  ##', '#   #', '#   #', ' ### '],
    'H': ['#   #', '#   #', '#####', '#   #', '#   #', '#   #', '#   #'],
    'I': [' ### ', '  #  ', '  #  ', '  #  ', '  #  ', '  #  ', ' ### '],
    'J': ['   ##', '    #', '    #', '    #', '    #', '#   #', ' ### '],
    'K': ['#   #', '#  # ', '###  ', '#  # ', '#   #', '#   #', '#   #'],
    'L': ['#    ', '#    ', '#    ', '#    ', '#    ', '#    ', '#####'],
    'M': ['#   #', '## ##', '# # #', '#   #', '#   #', '#   #', '#   #'],
    'N': ['#   #', '##  #', '# # #', '#  ##', '#   #', '#   #', '#   #'],
    'O': [' ### ', '#   #', '#   #', '#   #', '#   #', '#   #', ' ### '],
    'P': ['#### ', '#   #', '#   #', '#### ', '#    ', '#    ', '#    '],
    'Q': [' ### ', '#   #', '#   #', '#   #', '# # #', ' ####', '    #'],
    'R': ['#### ', '#   #', '#   #', '#### ', '#  # ', '#   #', '#   #'],
    'S': [' ### ', '#    ', ' ### ', '    #', '    #', '    #', ' ### '],
    'T': ['#####', '  #  ', '  #  ', '  #  ', '  #  ', '  #  ', '  #  '],
    'U': ['#   #', '#   #', '#   #', '#   #', '#   #', '#   #', ' ### '],
    'V': ['#   #', '#   #', '#   #', '#   #', ' # # ', '  #  ', '   # '],
    'W': ['#   #', '#   #', '#   #', '# # #', '## ##', '#   #', '#   #'],
    'X': ['#   #', ' # # ', '  #  ', ' # # ', '#   #', '#   #', '#   #'],
    'Y': ['#   #', '#   #', ' # # ', '  #  ', '  #  ', '  #  ', '  #  '],
    'Z': ['#####', '    #', '   # ', '  #  ', ' #   ', '#    ', '#####'],
    '0': [' ### ', '#   #', '#  ##', '# # #', '##  #', '#   #', ' ### '],
    '1': ['  #  ', ' ##  ', '# #  ', '  #  ', '  #  ', '  #  ', '#####'],
    '2': [' ### ', '#   #', '    #', '   # ', '  #  ', ' #   ', '#####'],
    '3': [' ### ', '#   #', '    #', '  ## ', '    #', '#   #', ' ### '],
    '4': ['   # ', '  ## ', ' # # ', '#  # ', '#####', '   # ', '   # '],
    '5': ['#####', '#    ', '#### ', '    #', '    #', '#   #', ' ### '],
    '6': [' ### ', '#    ', '#### ', '#   #', '#   #', '#   #', ' ### '],
    '7': ['#####', '    #', '   # ', '  #  ', '  #  ', ' #   ', ' #   '],
    '8': [' ### ', '#   #', '#   #', ' ### ', '#   #', '#   #', ' ### '],
    '9': [' ### ', '#   #', '#   #', ' ####', '    #', '    #', ' ### '],
    ' ': ['     ', '     ', '     ', '     ', '     ', '     ', '     '],
    '.': ['     ', '     ', '     ', '     ', '     ', '  #  ', '     '],
    '/': ['    #', '   # ', '  #  ', ' #   ', '#    ', '     ', '     '],
    '-': ['     ', '     ', '     ', '#####', '     ', '     ', '     '],
    '·': ['     ', '  #  ', '     ', '     ', '     ', '     ', '     '],
}


def draw_text(text: str, x: int, y: int, color: tuple, scale: int = 2) -> list:
    """Render pixel text and return list of (px, py, color) tuples.

    Args:
        text: String to render (ASCII uppercase supported).
        x: Left-edge x position.
        y: Top-edge y position.
        color: (R, G, B, A) tuple.
        scale: Pixel scale factor (1 = 5×7 native, 2 = 10×14, etc.).

    Returns:
        List of (x, y, color) tuples for each filled pixel.
    """
    pixels = []
    cx = x
    for ch in text.upper():
        glyph = FONT_5x7.get(ch, FONT_5x7[' '])
        for py, row in enumerate(glyph):
            for px, c in enumerate(row):
                if c == '#':
                    for sx in range(scale):
                        for sy in range(scale):
                            pixels.append((cx + px * scale + sx, y + py * scale + sy, color))
        cx += 6 * scale  # char width 5 + gap 1
    return pixels


# ── 载具绘制 ─────────────────────────────────────────────────────

def draw_vessel_pixels(vessel_def, cx: int, cy: int, scale: int = 2) -> list:
    """Convert a VesselDef pixel definition into screen-space pixels.

    Args:
        vessel_def: VesselDef with .pixels and .palette.
        cx: Cell centre x (pixels).
        cy: Cell centre y (pixels).
        scale: Scale factor for each sprite pixel.

    Returns:
        List of (x, y, color) tuples.
    """
    sprite_w = vessel_def.width
    sprite_h = vessel_def.height
    half_w = (sprite_w * scale) // 2
    half_h = (sprite_h * scale) // 2
    origin_x = cx - half_w
    origin_y = cy - half_h

    pixels = []
    for py, row in enumerate(vessel_def.pixels):
        for px, ch in enumerate(row):
            color = vessel_def.palette.get(ch)
            if color and color[3] > 0:
                for sx in range(scale):
                    for sy in range(scale):
                        px_screen = origin_x + px * scale + sx
                        py_screen = origin_y + py * scale + sy
                        pixels.append((px_screen, py_screen, color))
    return pixels


# ── 地图渲染（核心）─────────────────────────────────────────────

def _render_png(
    route: list,
    tiles_revealed: int,
    current_day: int,
    stage_name: str,
    remaining: int,
    total_days: int,
    vessel_name: str,
    vessel_def,
    milestones_config: dict | None = None,
    textures: dict | None = None,
    stages: list | None = None,
) -> bytes:
    """Render the full voyage map as a PNG.

    Args:
        route: List of 175 ``(x, y)`` grid coordinates.
        tiles_revealed: Number of tiles revealed so far.
        current_day: 1-based current day number.
        stage_name: Display name of the current voyage stage.
        remaining: Days remaining in the voyage.
        total_days: Total voyage length.
        vessel_name: Vessel ID string (e.g. "schooner").
        vessel_def: VesselDef with pixel art data.
        milestones_config: Dict mapping ``day_int → name_str``.
        textures: Dict of ``texture_name → TextureDef`` from the theme.
        stages: List of ``{"name": str, "days": [start, end]}`` stage
            configs for mapping tile index → stage → texture.

    Returns:
        PNG image as bytes.
    """
    # 1. 构建已揭示格子集合
    revealed_cells = set()
    for i in range(min(tiles_revealed, len(route))):
        revealed_cells.add(route[i])

    # 预计算每个格子的海洋颜色（确定性随机）
    ocean_rng = random.Random(42)
    ocean_colors = {}
    for c in range(CANVAS_COLS):
        for r in range(CANVAS_ROWS):
            rr = ocean_rng.random()
            if rr < 0.4:
                ocean_colors[(c, r)] = OCEAN_A
            elif rr < 0.7:
                ocean_colors[(c, r)] = OCEAN_B
            elif rr < 0.85:
                ocean_colors[(c, r)] = OCEAN_C
            else:
                ocean_colors[(c, r)] = OCEAN_D

    # 2. 船舶位置
    ship_pos = None
    if tiles_revealed > 0 and tiles_revealed <= len(route):
        ship_pos = route[tiles_revealed - 1]

    # 3. 里程碑位置（格坐标 → 名称）
    milestone_cells = {}
    if milestones_config:
        for day, name in milestones_config.items():
            idx = day - 1
            if 0 <= idx < len(route):
                milestone_cells[route[idx]] = name

    # --- 绘制基础图层 ---

    def pixel_fn(x, y):
        """(x, y) → (R, G, B, A) pixel colour."""
        cx = (x - PAD_X) // CELL
        cy = (y - PAD_Y) // CELL
        lx = (x - PAD_X) % CELL
        ly = (y - PAD_Y) % CELL

        # 标题区域（在格子上方）
        if cy < 0 or cy >= CANVAS_ROWS:
            return BG

        # 边框 / 网格线（1px 粗）
        is_border = (lx < 1 or ly < 1 or lx >= CELL - 1 or ly >= CELL - 1)
        in_bounds = 0 <= cx < CANVAS_COLS and 0 <= cy < CANVAS_ROWS

        if is_border:
            return GRID_LINE if in_bounds else BG

        if not in_bounds:
            return BG

        # 格子内部
        cell = (cx, cy)
        if cell in revealed_cells:
            return ocean_colors.get(cell, OCEAN_A)
        else:
            return MIST

    # 使用 pixel_fn 构建 base_map
    base_map = {}
    for x in range(W):
        for y in range(H):
            base_map[(x, y)] = pixel_fn(x, y)

    # ── 纹理绘制 ──────────────────────────────────────────────

    # 构建 route index → stage name 映射（用于查纹理）
    _stages = stages if stages is not None else _DEFAULT_STAGES
    idx_to_stage_name = {}
    for stage in _stages:
        start, end = stage["days"]
        for i in range(start - 1, end):
            idx_to_stage_name[i] = stage["name"]

    if textures:
        # 4a. 阶段底纹 — 已揭示 tile 上画对应阶段纹理
        for idx in range(min(tiles_revealed, len(route))):
            cx, cy = route[idx]
            stage_name_tile = idx_to_stage_name.get(idx, "未知")
            texture_name = get_stage_texture(stage_name_tile)
            texture_def = textures.get(texture_name)
            if texture_def:
                draw_texture(cx, cy, texture_def, base_map)

        # 4b. 尾迹 — 船身后 5 格覆盖 wake 纹理
        if tiles_revealed > 0 and tiles_revealed <= len(route):
            wake_def = textures.get("wake")
            if wake_def:
                ship_idx = tiles_revealed - 1
                for i in range(max(0, ship_idx - 5), ship_idx):
                    wx, wy = route[i]
                    draw_texture(wx, wy, wake_def, base_map)

    # 5. 里程碑标记 — 金色菱形
    for (mcx, mcy), mname in milestone_cells.items():
        star_cx = PAD_X + mcx * CELL + CELL // 2
        star_cy = PAD_Y + mcy * CELL + CELL // 2
        sr = 7
        for dy in range(-sr, sr + 1):
            w = sr - abs(dy)
            for dx in range(-w, w + 1):
                px, py = star_cx + dx, star_cy + dy
                if 0 <= px < W and 0 <= py < H:
                    base_map[(px, py)] = STAR_COLOR

    # 6. 终点标记（仅在最后 tile 已揭示时显示）
    if tiles_revealed >= total_days and len(route) > 0:
        finish_pos = route[-1]
        fcx, fcy = finish_pos
        fin_cx = PAD_X + fcx * CELL + CELL // 2
        fin_cy = PAD_Y + fcy * CELL + CELL // 2
        for dy in range(-6, 7):
            for dx in range(-6, 7):
                px, py = fin_cx + dx, fin_cy + dy
                if 0 <= px < W and 0 <= py < H:
                    base_map[(px, py)] = FINISH_COLOR

    # 7. 岛屿标记
    island_milestones = {day: name for day, name in (milestones_config or {}).items()
                         if "港" in name or "海岸" in name}
    for day, name in island_milestones.items():
        idx = day - 1
        if 0 <= idx < len(route) and idx < tiles_revealed:
            icx, icy = route[idx]
            isle_cx = PAD_X + icx * CELL + CELL // 2
            isle_cy = PAD_Y + icy * CELL + CELL // 2
            for dy in range(-8, 5):
                for dx in range(-6, 7):
                    if abs(dx) + abs(dy) <= 8 and dy < 3:
                        px, py = isle_cx + dx, isle_cy + dy
                        if 0 <= px < W and 0 <= py < H:
                            base_map[(px, py)] = ISLAND_COLOR
            for dy in range(0, 7):
                for dx in range(-2, 3):
                    px, py = isle_cx + dx, isle_cy + dy
                    if 0 <= px < W and 0 <= py < H:
                        base_map[(px, py)] = ISLAND_TRUNK

    # 8. 载具精灵
    if ship_pos and vessel_def:
        ship_cx = PAD_X + ship_pos[0] * CELL + CELL // 2
        ship_cy = PAD_Y + ship_pos[1] * CELL + CELL // 2
        sprite_scale = max(1, CELL // 8)
        for dx, dy, color in draw_vessel_pixels(vessel_def, ship_cx, ship_cy, sprite_scale):
            if 0 <= dx < W and 0 <= dy < H and color[3] > 0:
                base_map[(dx, dy)] = color

    # 9. 金色光晕（船周围）
    if ship_pos:
        ship_cx = PAD_X + ship_pos[0] * CELL + CELL // 2
        ship_cy = PAD_Y + ship_pos[1] * CELL + CELL // 2
        glow_radius = CELL + 4
        for dy in range(-glow_radius, glow_radius + 1):
            for dx in range(-glow_radius, glow_radius + 1):
                d = math.sqrt(dx * dx + dy * dy)
                if d < glow_radius:
                    px, py = ship_cx + dx, ship_cy + dy
                    if 0 <= px < W and 0 <= py < H:
                        alpha = int(max(0, 80 * (1 - d / glow_radius)))
                        r, g, b, a = base_map.get((px, py), BG)
                        glow_r = min(255, r + alpha)
                        glow_g = min(255, g + int(alpha * 0.7))
                        glow_b = min(255, b + int(alpha * 0.2))
                        base_map[(px, py)] = (glow_r, glow_g, glow_b, a)

    # 10. 标题文字
    title_text = f"bestman · {vessel_name.upper()}"
    title_pixels = draw_text(title_text, 10, 15, TITLE_COLOR, scale=3)

    sub_text = f"DAY {current_day} · {stage_name.upper()} · {remaining} DAYS LEFT"
    sub_pixels = draw_text(sub_text, 10, 50, SUBTITLE_COLOR, scale=2)

    for px, py, color in title_pixels + sub_pixels:
        if 0 <= px < W and 0 <= py < PAD_Y:
            base_map[(px, py)] = color

    return make_png(W, H, lambda x, y: base_map.get((x, y), BG))


# ── CanvasRenderer (BaseRenderer implementation) ──────────────────

class CanvasRenderer(BaseRenderer):
    """Render the voyage map as a PNG for Kitty-compatible terminals."""

    def is_available(self) -> bool:
        """Check whether the terminal supports Kitty graphics protocol."""
        return kitty_available()

    def render_map(self, data: dict, theme, vessel_def=None) -> bytes:
        """Render the map as PNG bytes.

        Args:
            data: dict from ``MapEngine.build_render_data()``.
            theme: Theme instance (used for stage display name).
            vessel_def: VesselDef or None.

        Returns:
            bytes: PNG image data.
        """
        tiles_revealed = data["tiles_revealed"]
        current_day = tiles_revealed + 1
        remaining = max(0, data["total_days"] - tiles_revealed)

        # Determine stage name from route position
        # (delegated to theme for display name)
        from bestman.core.config import get_current_stage as _get_stage
        stage = _get_stage(min(current_day, data["total_days"]), {"voyage": {"stages": []}})
        stage_name = theme.stage_display_name(stage["name"]) if theme else str(stage["name"])

        return _render_png(
            route=data["route"],
            tiles_revealed=tiles_revealed,
            current_day=current_day,
            stage_name=stage_name,
            remaining=remaining,
            total_days=data["total_days"],
            vessel_name=getattr(vessel_def, "name", "unknown") if vessel_def else "unknown",
            vessel_def=vessel_def,
            milestones_config=data.get("milestones", {}),
            textures=getattr(theme, "textures", None) if theme else None,
            stages=data.get("stages", None),
        )


# ── Backward-compatible standalone function ────────────────────────

def render_map(
    route: list,
    tiles_revealed: int,
    current_day: int,
    stage_name: str,
    remaining: int,
    total_days: int,
    vessel_name: str,
    vessel_def,
    milestones_config: dict | None = None,
) -> bytes:
    """Render the full voyage map as a PNG (old signature).

    Preserved for backward compatibility with code that imports
    ``render_map`` from ``bestman.canvas_renderer``.
    Prefer ``CanvasRenderer().render_map()`` for new code.
    """
    return _render_png(
        route=route,
        tiles_revealed=tiles_revealed,
        current_day=current_day,
        stage_name=stage_name,
        remaining=remaining,
        total_days=total_days,
        vessel_name=vessel_name,
        vessel_def=vessel_def,
        milestones_config=milestones_config,
        textures=None,
        stages=None,
    )


# ── 自测 ─────────────────────────────────────────────────────────

def _self_test():
    """Quick self-test: render a demo map and display it."""
    from bestman.themes.base import VesselDef
    from bestman.themes.naval import _NAVAL_TEXTURES

    # 生成简单的直线 route（50×14 网格，从左到右蜿蜒）
    rng = random.Random(7)
    route = []
    for i in range(175):
        x = 2 + int(i * 46 / 174)
        y = 7 + int(rng.uniform(-3, 3))
        y = max(1, min(CANVAS_ROWS - 2, y))
        route.append((x, y))

    # 简易载具
    demo_vessel = VesselDef(
        name="测试船", icon="⛵",
        pixels=[
            '..BBBBB....',
            '.BWWWWWB...',
            '.BMWWWMB...',
            'BBBBBBBBBB.',
            'BBGBBGBBBB.',
            '.BBBBBBBBB.',
            '..BBBBB....',
        ],
        palette={
            'B': (74, 32, 16, 255),
            'W': (255, 255, 240, 255),
            'M': (160, 96, 48, 255),
            'G': (255, 215, 0, 255),
        },
    )

    milestones = {25: "穿越迷雾之海", 50: "进入季风带", 75: "抵达贸易港",
                   100: "穿过赤道无风带", 125: "遇见信风", 150: "望见新大陆海岸线",
                   175: "抵达新大陆"}

    png = _render_png(
        route=route,
        tiles_revealed=62,
        current_day=63,
        stage_name="JIFENGDAI",
        remaining=113,
        total_days=175,
        vessel_name="schooner",
        vessel_def=demo_vessel,
        milestones_config=milestones,
        textures=_NAVAL_TEXTURES,
        stages=_DEFAULT_STAGES,
    )

    if kitty_available():
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()
        kitty_display(png, cols=90, rows=24)
    else:
        print(f"PNG generated ({len(png)} bytes). "
              "Kitty protocol not available — run in Ghostty/iTerm2/Kitty to see.")

    print()


if __name__ == '__main__':
    _self_test()
