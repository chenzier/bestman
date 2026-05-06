#!/usr/bin/env python3
"""
终端渲染可行性验证：用项目的真实渲染器跑 4 个风格的效果。
- ASCII 回退：所有终端可用，但能做的有限
- Canvas PNG：Kitty/Ghostty/iTerm2/WezTerm，能做渐变、光晕、纹理

输出：
  1. 终端直接打印 ASCII 地图（4 阶段）
  2. 保存 PNG 到 demo_maps/ 目录（如果 Kitty 可用则直接显示）
"""

import sys, os, random, math, base64, struct, zlib

# 确保项目在 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bestman.core.config import DEFAULT_CONFIG
from bestman.core.map_engine import MapEngine, GRID_WIDTH, GRID_HEIGHT


# ═══════════════════════════════════════════════════════════
# 1. 真实 MapEngine 初始化
# ═══════════════════════════════════════════════════════════

config = DEFAULT_CONFIG
engine = MapEngine(config)


# ═══════════════════════════════════════════════════════════
# 2. 四个阶段
# ═══════════════════════════════════════════════════════════

STAGES = [
    ("启航 · Day 10", 10),
    ("季风带 · Day 87", 87),
    ("近大陆 · Day 150", 150),
    ("抵达 · Day 175", 175),
]


# ═══════════════════════════════════════════════════════════
# 3. ASCII 渲染器 — 改进版（支持航迹、起点、图例）
# ═══════════════════════════════════════════════════════════

# Rich 颜色
RICH = {
    'cyan': 'cyan', 'blue': 'blue', 'green': 'green',
    'yellow': 'yellow', 'white': 'white', 'magenta': 'magenta',
    'bright_red': 'bright_red', 'bright_yellow': 'bright_yellow',
}

# Unicode 字符
CHARS = {
    'fog':           '\u2592',  # ▒ 迷雾
    'ocean':         '\u00b7',  # · 已探索海域
    'ocean_wake':    '\u2248',  # ≈ 近期航迹
    'ocean_trail':   '\u25e6',  # ◦ 更早期轨迹
    'ship':          '\u2693',  # ⚓ 当前船位
    'start':         '\u25c9',  # ◉ 起点
    'milestone':     '\u2726',  # ✦ 里程碑
    'preview':       '\u2218',  # ∘ 前方预览
    'finish':        '\u2605',  # ★ 终点（避免 emoji 兼容问题）
    'trail_line':    '\u2575',  # ╵ 竖线
    'grid_v':        '\u2502',  # │
    'grid_h':        '\u2500',  # ─
}


def ascii_render_stage(engine, day, style='improved'):
    """生成 Rich markup 格式的 ASCII 地图"""
    data = engine.build_render_data(tiles_revealed=day)
    grid = data['grid']
    ship_pos = data['ship_pos']
    route = data['route']
    h, w = engine.height, engine.width

    # 计算去重航迹格子
    trail_set = set()
    for i in range(day):
        x, y = route[i]
        trail_set.add((x, y))

    # 起点
    start_pos = route[0]

    lines = []
    # 标题行
    pct = round(day / engine.total_days * 100)
    lines.append(f"[bold cyan]DAY {day:>3d} / {engine.total_days}  ({pct}%)[/]")

    for y in range(h):
        parts = []
        for x in range(w):
            cell = grid[y][x]
            status = cell['status']
            char = cell.get('terrain_char', CHARS['fog'])
            color = cell.get('terrain_color', 'blue')

            # 起点（Day 1 格子）
            if (x, y) == start_pos:
                char = CHARS['start']
                style_str = 'bold cyan'
            # 终点 / 船 / 里程碑
            elif cell.get('has_finish'):
                char = CHARS['finish']
                style_str = 'bold green on black'
            elif cell.get('has_ship'):
                char = CHARS['ship']
                style_str = 'bold yellow'
            elif cell.get('has_milestone') and status != 'fog':
                char = CHARS['milestone']
                style_str = 'bold magenta'
            # 航迹格子
            elif status in ('wake', 'explored') and (x, y) in trail_set:
                if cell.get('is_today_trail'):
                    char = CHARS['ocean_wake']
                    style_str = f'bold {color}'
                else:
                    char = CHARS['ocean_trail']
                    style_str = f'{color}'
            elif status == 'fog':
                char = CHARS['fog']
                style_str = 'dim blue'
            elif status == 'preview':
                char = CHARS['preview']
                style_str = 'blue'
            else:
                # 其他已探索
                char = CHARS['ocean']
                style_str = f'dim {color}'

            parts.append(f'[{style_str}]{char}[/]')

        lines.append(''.join(parts))

    # 图例行
    legend = (
        f"[dim]图例: [/]"
        f"[bold cyan]◉[/][dim]起点  [/]"
        f"[bold yellow]⚓[/][dim]船  [/]"
        f"[bold magenta]✦[/][dim]里程碑  [/]"
        f"[dim blue]▒[/][dim]迷雾  [/]"
        f"[green]◦[/][dim]航迹[/]"
    )
    lines.append(legend)

    return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════
# 4. PNG 生成工具（同 canvas.py 的纯 Python PNG 生成）
# ═══════════════════════════════════════════════════════════

def make_png(width, height, draw_fn):
    """生成 PNG bytes — 每像素调用 draw_fn(x,y)->(R,G,B,A)"""
    pixels = bytearray()
    for y in range(height):
        pixels.append(0)  # filter none
        for x in range(width):
            r, g, b, a = draw_fn(x, y)
            pixels.append(r); pixels.append(g); pixels.append(b); pixels.append(a)
    raw = bytes(pixels)
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    def chunk(ctype, data):
        c = ctype + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)
    return sig + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


# ═══════════════════════════════════════════════════════════
# 5. 四个 Canvas PNG 风格
# ═══════════════════════════════════════════════════════════

# 画布参数
CC = 20          # 每格像素
CPAD_X = 8
CPAD_Y = 80
CW = GRID_WIDTH * CC + CPAD_X * 2
CH = GRID_HEIGHT * CC + CPAD_Y + 8

# 常用颜色
CBG     = (8, 16, 24, 255)
CMIST   = (22, 38, 54, 255)
CGRID   = (20, 60, 80, 80)
CGOLD   = (255, 215, 0, 255)
CTRANS  = (0, 0, 0, 0)

# ── 风格 A: 像素复古（改进版：航迹线 + 起点） ──

def style_a_pixel(engine, day):
    """像素复古风 — 网格海洋 + 金色航迹 + 起点标记"""
    data = engine.build_render_data(tiles_revealed=day)
    grid = data['grid']
    ship_pos = data['ship_pos']
    route = data['route']

    h, w = engine.height, engine.width

    # 去重航迹
    trail_set = set()
    for i in range(day):
        tx, ty = route[i]
        trail_set.add((tx, ty))

    # 构建基础图
    pixels = {}
    rng = random.Random(42)
    ocean = [(21,104,112,255), (26,128,120,255), (14,92,96,255), (18,80,88,255)]

    for gy in range(h):
        for gx in range(w):
            cell = grid[gy][gx]
            ox, oy = CPAD_X + gx*CC, CPAD_Y + gy*CC
            is_trail = (gx, gy) in trail_set
            is_start = (gx, gy) == route[0]

            for dy in range(CC):
                for dx in range(CC):
                    px, py = ox+dx, oy+dy
                    border = (dx<1 or dy<1 or dx>=CC-1 or dy>=CC-1)

                    if border:
                        pixels[(px,py)] = CGRID
                    elif cell['status'] == 'fog':
                        pixels[(px,py)] = CMIST
                    elif cell.get('has_ship'):
                        pixels[(px,py)] = (30,80,90,255)  # 船底深色（船精灵覆盖）
                    elif cell.get('has_finish'):
                        pixels[(px,py)] = CGOLD
                    elif cell.get('has_milestone'):
                        pixels[(px,py)] = (24, 100, 100, 255)
                    else:
                        oc = rng.choice(ocean)
                        pixels[(px,py)] = oc

                    # 航迹格叠加暖色
                    if is_trail and not border and not cell.get('has_ship') and not cell.get('has_finish'):
                        r, g, b, a = pixels[(px,py)]
                        pixels[(px,py)] = (min(255, r+15), min(255, g+8), b, a)

    # 航迹线（连续曲线）
    trail_points = []
    for i in range(day):
        tx, ty = route[i]
        trail_points.append((CPAD_X + tx*CC + CC//2, CPAD_Y + ty*CC + CC//2))

    for (x1,y1), (x2,y2) in zip(trail_points, trail_points[1:]):
        steps = max(abs(x2-x1), abs(y2-y1), 1) * 2
        for t in range(steps):
            frac = t / steps
            px = int(x1 + (x2-x1)*frac)
            py = int(y1 + (y2-y1)*frac)
            if (px, py) in pixels:
                r, g, b, a = pixels[(px,py)]
                pixels[(px,py)] = (min(255,r+60), min(255,g+40), min(255,b+10), a)

    # 起点标记 — 蓝色圈
    sx, sy = route[0]
    scx = CPAD_X + sx*CC + CC//2
    scy = CPAD_Y + sy*CC + CC//2
    for dy in range(-8, 9):
        for dx in range(-8, 9):
            d = math.sqrt(dx*dx + dy*dy)
            if 6.5 <= d <= 8:
                px, py = scx+dx, scy+dy
                if (px,py) in pixels: pixels[(px,py)] = (136, 204, 255, 255)

    # 船精灵（像素）
    if ship_pos and day < engine.total_days:
        draw_vessel(pixels, CPAD_X + ship_pos[0]*CC + CC//2,
                    CPAD_Y + ship_pos[1]*CC + CC//2)

    # 终点标记
    if day >= engine.total_days and route:
        fx, fy = route[-1]
        fcx = CPAD_X + fx*CC + CC//2
        fcy = CPAD_Y + fy*CC + CC//2
        for dy in range(-30, 31):
            for dx in range(-30, 31):
                d = math.sqrt(dx*dx + dy*dy)
                if d < 30:
                    px, py = fcx+dx, fcy+dy
                    if (px,py) in pixels:
                        a = int(max(0, 80*(1-d/30)))
                        r, g, b, _ = pixels[(px,py)]
                        pixels[(px,py)] = (min(255,r+a), min(255,g+int(a*0.8)), min(255,b), 255)

    # 迷雾边缘
    if day < engine.total_days:
        rv = route[day][0] if day > 0 else route[0][0]
        fog_x = CPAD_X + (rv+1)*CC
        for dx in range(-CC, CC*2):
            for gy in range(h):
                for dy in range(CC):
                    px = fog_x + dx
                    py = CPAD_Y + gy*CC + dy
                    if (px,py) in pixels:
                        frac = max(0, min(1, (dx+CC)/(CC*3)))
                        if frac > 0 and pixels[(px,py)] != CGRID:
                            r, g, b, a = pixels[(px,py)]
                            alpha = frac * 0.7
                            pixels[(px,py)] = (
                                int(r*(1-alpha) + CBG[0]*alpha),
                                int(g*(1-alpha) + CBG[1]*alpha),
                                int(b*(1-alpha) + CBG[2]*alpha),
                                a
                            )

    # 标题文字
    title_px = FONT_5x7_render(f"DAY {day} / {engine.total_days}", CPAD_X, 10, (78,201,176,255), 2)
    for px, py, c in title_px:
        if (px,py) in pixels: pixels[(px,py)] = c

    return lambda x, y: pixels.get((x,y), CBG)


# ── 风格 B: 古典航海图 ──

def style_b_parchment(engine, day):
    """古典航海图 — 羊皮纸底色 + 罗盘 + Rhumb线 + 墨线航迹"""
    data = engine.build_render_data(tiles_revealed=day)
    grid = data['grid']
    ship_pos = data['ship_pos']
    route = data['route']
    h, w = engine.height, engine.width

    parchment = (240, 217, 181, 255)
    parchment_dark = (200, 173, 126, 255)
    ink = (90, 56, 32, 255)

    # 去重航迹
    trail_set = set()
    for i in range(day):
        tx, ty = route[i]
        trail_set.add((tx, ty))

    pixels = {}
    rng = random.Random(99)

    for gy in range(h):
        for gx in range(w):
            cell = grid[gy][gx]
            ox, oy = CPAD_X + gx*CC, CPAD_Y + gy*CC

            for dy in range(CC):
                for dx in range(CC):
                    px, py = ox+dx, oy+dy

                    if dx<1 or dy<1 or dx>=CC-1 or dy>=CC-1:
                        pixels[(px,py)] = (80, 50, 30, 40)  # 淡棕网格线
                    elif cell['status'] == 'fog':
                        pixels[(px,py)] = parchment_dark
                    else:
                        # 已探索 = 浅羊皮纸（加轻微噪点）
                        r = 240 + int((rng.random()-0.5)*6)
                        g = 217 + int((rng.random()-0.5)*6)
                        b = 181 + int((rng.random()-0.5)*6)
                        pixels[(px,py)] = (r, g, b, 255)

    # Rhumb 线（从中心辐射）
    cxM = CPAD_X + w*CC/2
    cyM = CPAD_Y + h*CC/2
    for angle in range(0, 360, 15):
        rad = angle * math.pi / 180
        length = max(CW, CH)
        x2 = cxM + math.cos(rad) * length
        y2 = cyM + math.sin(rad) * length
        draw_line(pixels, int(cxM), int(cyM), int(x2), int(y2), (120, 80, 40, 30))

    # 航迹墨线
    trail_pts = []
    for i in range(day):
        tx, ty = route[i]
        trail_pts.append((CPAD_X + tx*CC + CC//2, CPAD_Y + ty*CC + CC//2))

    for (x1,y1), (x2,y2) in zip(trail_pts, trail_pts[1:]):
        draw_line(pixels, x1, y1, x2, y2, (90, 40, 20, 120))

    # 起点
    sx, sy = route[0]
    scx, scy = CPAD_X + sx*CC + CC//2, CPAD_Y + sy*CC + CC//2
    for dy in range(-7, 8):
        for dx in range(-7, 8):
            d = math.sqrt(dx*dx + dy*dy)
            if 5.5 <= d <= 7:
                px, py = scx+dx, scy+dy
                if (px,py) in pixels: pixels[(px,py)] = (139, 69, 19, 255)

    # 罗盘
    draw_compass(pixels, CPAD_X + w*CC - 30, CPAD_Y + 20, 20, ink)

    # 船
    if ship_pos and day < engine.total_days:
        draw_vessel(pixels, CPAD_X + ship_pos[0]*CC + CC//2,
                    CPAD_Y + ship_pos[1]*CC + CC//2)

    # 外边框
    for bx in range(CPAD_X-4, CPAD_X + w*CC + 4):
        for by in range(CPAD_Y-4, CPAD_Y + h*CC + 4):
            if (CPAD_X-6 <= bx < CPAD_X-3 or CPAD_X + w*CC + 3 <= bx < CPAD_X + w*CC + 6 or
                CPAD_Y-6 <= by < CPAD_Y-3 or CPAD_Y + h*CC + 3 <= by < CPAD_Y + h*CC + 6):
                pixels[(bx,by)] = (90, 56, 32, 180)

    # 迷雾
    if day < engine.total_days:
        rv = route[day][0] if day > 0 else route[0][0]
        fog_x = CPAD_X + (rv+1)*CC
        for dx in range(-CC, CC*2):
            frac = max(0, min(1, (dx+CC)/(CC*3)))
            if frac > 0:
                for gy in range(h):
                    for dy in range(CC):
                        px, py = fog_x + dx, CPAD_Y + gy*CC + dy
                        if (px,py) in pixels:
                            r, g, b, a = pixels[(px,py)]
                            alpha = frac * 0.6
                            pixels[(px,py)] = (
                                int(r*(1-alpha) + parchment_dark[0]*alpha),
                                int(g*(1-alpha) + parchment_dark[1]*alpha),
                                int(b*(1-alpha) + parchment_dark[2]*alpha),
                                a
                            )

    # 标题
    title_px = FONT_5x7_render(f"DAY {day}", CPAD_X, 10, (74, 48, 32, 255), 2)
    for px, py, c in title_px:
        if (px,py) in pixels: pixels[(px,py)] = c

    return lambda x, y: pixels.get((x,y), parchment)


# ── 风格 C: 极简暗色 ──

def style_c_minimal(engine, day):
    """极简暗色 — 纯黑底 + 发光航迹 + 进度条"""
    data = engine.build_render_data(tiles_revealed=day)
    route = data['route']
    h, w = engine.height, engine.width
    bg = (6, 8, 12, 255)

    pixels = {}
    # 背景
    for x in range(CW):
        for y in range(CH):
            pixels[(x,y)] = bg

    # 全航线虚线
    pt_map = {}
    route_pixels = []
    for i in range(engine.total_days):
        rx, ry = route[i]
        px = CPAD_X + rx*CC + CC//2
        py = CPAD_Y + ry*CC + CC//2
        route_pixels.append((px, py))
        # 标记航线区域
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                pt_map[(px+dx, py+dy)] = True

    # 全航线淡底色
    for (x1,y1), (x2,y2) in zip(route_pixels, route_pixels[1:]):
        draw_line(pixels, x1, y1, x2, y2, (30, 35, 45, 80))

    # 已走航线 — 渐变
    for (x1,y1), (x2,y2) in zip(route_pixels[:day], route_pixels[1:day]):
        frac = route_pixels.index((x1,y1)) / max(1, day-1)
        # 红 → 橙 → 蓝 → 绿渐变
        if frac < 0.25:
            c = (224, 108, 117, 200)
        elif frac < 0.5:
            c = (209, 154, 102, 200)
        elif frac < 0.8:
            c = (97, 175, 239, 200)
        else:
            c = (152, 195, 121, 200)
        draw_line(pixels, x1, y1, x2, y2, c)

    # 光晕
    for (x1,y1), (x2,y2) in zip(route_pixels[:day], route_pixels[1:day]):
        draw_line(pixels, x1-1, y1, x2-1, y2, (120, 200, 255, 40))
        draw_line(pixels, x1+1, y1, x2+1, y2, (120, 200, 255, 40))

    # 起点光点
    px0, py0 = route_pixels[0]
    for dy in range(-8, 9):
        for dx in range(-8, 9):
            d = math.sqrt(dx*dx+dy*dy)
            if d < 8:
                a = int(200 * (1-d/8))
                x, y = px0+dx, py0+dy
                if (x,y) in pixels:
                    r, g, b, _ = pixels[(x,y)]
                    pixels[(x,y)] = (min(255,r+200), min(255,g+200), min(255,b+200), 255)
    pixels[(px0, py0)] = (255, 255, 255, 255)

    # 船
    if day < engine.total_days:
        px, py = route_pixels[day]
        for dy in range(-12, 13):
            for dx in range(-12, 13):
                d = math.sqrt(dx*dx+dy*dy)
                if d < 12:
                    a = int(200*(1-d/12))
                    x, y = px+dx, py+dy
                    if (x,y) in pixels:
                        r, g, b, _ = pixels[(x,y)]
                        pixels[(x,y)] = (min(255,r+150), min(255,g+200), min(255,b+255), 255)
        # 三角船标
        for dy in range(-6, 7):
            for dx in range(-5, 6):
                if abs(dx)*2 + abs(dy) <= 10 and dy >= -3:
                    if (px+dx, py+dy) in pixels:
                        pixels[(px+dx, py+dy)] = (255, 255, 255, 255)

    # 进度条
    bar_y = CPAD_Y - 15
    bar_w = w * CC
    for bx in range(CPAD_X, CPAD_X + bar_w):
        for by in range(bar_y, bar_y+3):
            if bx < CPAD_X + bar_w * (day/engine.total_days):
                t = (bx - CPAD_X) / bar_w
                if t < 0.25:
                    c = (224, 108, 117, 255)
                elif t < 0.5:
                    c = (209, 154, 102, 255)
                elif t < 0.8:
                    c = (97, 175, 239, 255)
                else:
                    c = (152, 195, 121, 255)
                pixels[(bx,by)] = c
            else:
                pixels[(bx,by)] = (30, 30, 40, 255)

    # 标题
    title_px = FONT_5x7_render(f"DAY {day} / {engine.total_days}", CPAD_X, 10, (74, 85, 104, 255), 2)
    for px, py, c in title_px:
        if (px,py) in pixels: pixels[(px,py)] = c

    return lambda x, y: pixels.get((x,y), bg)


# ── 风格 D: 深蓝海洋 ──

def style_d_ocean(engine, day):
    """深蓝海洋 — 星空渐变 + 荧光尾迹 + 呼吸光晕"""
    data = engine.build_render_data(tiles_revealed=day)
    grid = data['grid']
    ship_pos = data['ship_pos']
    route = data['route']
    h, w = engine.height, engine.width

    # 去重航迹
    trail_set = set()
    for i in range(day):
        tx, ty = route[i]
        trail_set.add((tx, ty))

    pixels = {}
    rng = random.Random(42)

    # 海洋渐变背景
    for y in range(CH):
        frac = y / CH
        bg_r = int(10 * (1-frac) + 6 * frac)
        bg_g = int(22 * (1-frac) + 18 * frac)
        bg_b = int(40 * (1-frac) + 32 * frac)
        for x in range(CW):
            pixels[(x,y)] = (bg_r, bg_g, bg_b, 255)

    # 星星
    srng = random.Random(1337)
    for _ in range(60):
        sx = srng.randint(0, CW-1)
        sy = srng.randint(0, CPAD_Y)
        pixels[(sx,sy)] = (255, 255, 255, int(50 + srng.random()*100))

    ocean_cells = [(10,40,60,255), (8,48,72,255), (12,36,56,255), (14,44,64,255)]
    crng = random.Random(42)

    for gy in range(h):
        for gx in range(w):
            cell = grid[gy][gx]
            ox, oy = CPAD_X + gx*CC, CPAD_Y + gy*CC

            for dy in range(CC):
                for dx in range(CC):
                    px, py = ox+dx, oy+dy

                    if dx<1 or dy<1 or dx>=CC-1 or dy>=CC-1:
                        pixels[(px,py)] = (20, 50, 70, 40)
                    elif cell['status'] == 'fog':
                        pixels[(px,py)] = (11, 26, 42, 255)
                    else:
                        base = crng.choice(ocean_cells)
                        v = 0.85 + crng.random()*0.3
                        pixels[(px,py)] = (
                            int(base[0]*v), int(base[1]*v), int(base[2]*v), 255
                        )

                    # 波纹
                    if cell['status'] != 'fog' and not (dx<1 or dy<1 or dx>=CC-1 or dy>=CC-1):
                        if crng.random() > 0.92:
                            pixels[(px,py)] = (
                                min(255, pixels[(px,py)][0]+3),
                                min(255, pixels[(px,py)][1]+3),
                                min(255, pixels[(px,py)][2]+3),
                                255
                            )

    # 航迹荧光
    trail_pts = []
    for i in range(day):
        tx, ty = route[i]
        trail_pts.append((CPAD_X + tx*CC + CC//2, CPAD_Y + ty*CC + CC//2))
    for (x1,y1), (x2,y2) in zip(trail_pts, trail_pts[1:]):
        draw_line(pixels, x1-1, y1-1, x2-1, y2-1, (100, 200, 220, 60))
        draw_line(pixels, x1, y1, x2, y2, (100, 200, 220, 40))

    # 起点
    sx, sy = route[0]
    scx, scy = CPAD_X + sx*CC + CC//2, CPAD_Y + sy*CC + CC//2
    for dy in range(-8, 9):
        for dx in range(-8, 9):
            d = math.sqrt(dx*dx + dy*dy)
            if d < 8:
                a = int(150*(1-d/8))
                px, py = scx+dx, scy+dy
                if (px,py) in pixels:
                    r, g, b, _ = pixels[(px,py)]
                    pixels[(px,py)] = (min(255,r+150), min(255,g+200), min(255,b+255), 255)

    # 船
    if ship_pos and day < engine.total_days:
        draw_vessel(pixels, CPAD_X + ship_pos[0]*CC + CC//2,
                    CPAD_Y + ship_pos[1]*CC + CC//2)

    # 船光晕
    if ship_pos and day < engine.total_days:
        scx = CPAD_X + ship_pos[0]*CC + CC//2
        scy = CPAD_Y + ship_pos[1]*CC + CC//2
        for dy in range(-20, 21):
            for dx in range(-20, 21):
                d = math.sqrt(dx*dx + dy*dy)
                if d < 20:
                    a = int(60 * (1-d/20))
                    px, py = scx+dx, scy+dy
                    if (px,py) in pixels:
                        r, g, b, _ = pixels[(px,py)]
                        pixels[(px,py)] = (min(255,r+a), min(255,g+int(a*0.8)), min(255,b+int(a*0.3)), 255)

    # 迷雾
    if day < engine.total_days:
        rv = route[day][0] if day > 0 else route[0][0]
        fog_x = CPAD_X + (rv+1)*CC
        for dx in range(-CC, CC*2):
            frac = max(0, min(1, (dx+CC)/(CC*3)))
            if frac > 0:
                for gy in range(h):
                    for dy in range(CC):
                        px, py = fog_x + dx, CPAD_Y + gy*CC + dy
                        if (px,py) in pixels:
                            r, g, b, a = pixels[(px,py)]
                            alpha = frac * 0.7
                            pixels[(px,py)] = (
                                int(r*(1-alpha) + 6*alpha),
                                int(g*(1-alpha) + 18*alpha),
                                int(b*(1-alpha) + 32*alpha),
                                a
                            )

    # 标题
    title_px = FONT_5x7_render(f"DAY {day}", CPAD_X, 10, (150, 200, 230, 255), 2)
    for px, py, c in title_px:
        if (px,py) in pixels: pixels[(px,py)] = c

    return lambda x, y: pixels.get((x,y), (6, 18, 32, 255))


# ═══════════════════════════════════════════════════════════
# 绘制辅助函数
# ═══════════════════════════════════════════════════════════

def draw_line(pixels, x1, y1, x2, y2, color):
    """Bresenham 画线"""
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    sx = 1 if x1 < x2 else -1
    sy = 1 if y1 < y2 else -1
    err = dx - dy
    cx, cy = x1, y1
    while True:
        r, g, b, a = color
        if (cx, cy) in pixels:
            pr, pg, pb, pa = pixels[(cx,cy)]
            pixels[(cx,cy)] = (
                int(pr*(1-a/255) + r*a/255),
                int(pg*(1-a/255) + g*a/255),
                int(pb*(1-a/255) + b*a/255),
                max(pa, a)
            )
        else:
            pixels[(cx,cy)] = color
        if cx == x2 and cy == y2: break
        e2 = 2 * err
        if e2 > -dy: err -= dy; cx += sx
        if e2 < dx: err += dx; cy += sy


def draw_vessel(pixels, cx, cy):
    """像素帆船精灵 — 从 naval theme 简化"""
    sprite = [
        '..BBBBB....', '.BWWWWWB...', '.BMWWWMB...',
        'BBBBBBBBBB.', 'BBGBBGBBBB.', '.BBBBBBBBB.', '..BBBBB....',
    ]
    pal = {'B':(74,32,16,255), 'W':(255,255,240,255), 'M':(160,96,48,255), 'G':(212,176,32,255)}
    vs = 2  # 像素放大
    w, h = len(sprite[0]), len(sprite)
    ox = cx - w*vs//2
    oy = cy - h*vs//2 - 4

    for py in range(h):
        for px in range(len(sprite[py])):
            ch = sprite[py][px]
            if pal.get(ch):
                c = pal[ch]
                for sy in range(vs):
                    for sx in range(vs):
                        x, y = ox + px*vs + sx, oy + py*vs + sy
                        if (x,y) in pixels: pixels[(x,y)] = c


def draw_compass(pixels, cx, cy, r, color):
    """罗盘玫瑰"""
    rr, rg, rb, ra = color
    # 外圈
    for angle in range(360):
        rad = angle * math.pi / 180
        for d in range(int(r*0.85), r+1):
            px = int(cx + math.cos(rad)*d)
            py = int(cy + math.sin(rad)*d)
            pixels[(px,py)] = (rr, rg, rb, int(ra*0.8))
    # 四向线
    for d_idx, (dx, dy) in enumerate([(0,-1),(1,0),(0,1),(-1,0)]):
        for i in range(1, r):
            px, py = cx + dx*i, cy + dy*i
            pixels[(px,py)] = (rr, rg, rb, ra)
        for i in range(1, int(r*0.6)):
            px, py = cx + dx*1*i + (dy if dy==0 else 0)*i, cy + dy*1*i + (dx if dx==0 else 0)*i
            pixels[(px,py)] = (rr, rg, rb, int(ra*0.5))
            px, py = cx + dx*1*i - (dy if dy==0 else 0)*i, cy + dy*1*i - (dx if dx==0 else 0)*i
            pixels[(px,py)] = (rr, rg, rb, int(ra*0.5))


# ═══════════════════════════════════════════════════════════
# 像素字体
# ═══════════════════════════════════════════════════════════

FONT_5x7 = {
    'A':['  #  ',' # # ','#   #','#####','#   #','#   #','#   #'],
    'B':['#### ','#   #','#### ','#   #','#   #','#   #','#### '],
    'C':[' ### ','#   #','#    ','#    ','#    ','#   #',' ### '],
    'D':['#### ','#   #','#   #','#   #','#   #','#   #','#### '],
    'E':['#####','#    ','#### ','#    ','#    ','#    ','#####'],
    'F':['#####','#    ','#### ','#    ','#    ','#    ','#    '],
    'G':[' ### ','#   #','#    ','#  ##','#   #','#   #',' ### '],
    'H':['#   #','#   #','#####','#   #','#   #','#   #','#   #'],
    'I':[' ### ','  #  ','  #  ','  #  ','  #  ','  #  ',' ### '],
    'L':['#    ','#    ','#    ','#    ','#    ','#    ','#####'],
    'M':['#   #','## ##','# # #','#   #','#   #','#   #','#   #'],
    'N':['#   #','##  #','# # #','#  ##','#   #','#   #','#   #'],
    'O':[' ### ','#   #','#   #','#   #','#   #','#   #',' ### '],
    'P':['#### ','#   #','#   #','#### ','#    ','#    ','#    '],
    'R':['#### ','#   #','#   #','#### ','#  # ','#   #','#   #'],
    'S':[' ### ','#    ',' ### ','    #','    #','    #',' ### '],
    'T':['#####','  #  ','  #  ','  #  ','  #  ','  #  ','  #  '],
    'U':['#   #','#   #','#   #','#   #','#   #','#   #',' ### '],
    'V':['#   #','#   #','#   #','#   #',' # # ','  #  ','   # '],
    'Y':['#   #','#   #',' # # ','  #  ','  #  ','  #  ','  #  '],
    '0':[' ### ','#   #','#  ##','# # #','##  #','#   #',' ### '],
    '1':['  #  ',' ##  ','# #  ','  #  ','  #  ','  #  ','#####'],
    '2':[' ### ','#   #','    #','   # ','  #  ',' #   ','#####'],
    '3':[' ### ','#   #','    #','  ## ','    #','#   #',' ### '],
    '4':['   # ','  ## ',' # # ','#  # ','#####','   # ','   # '],
    '5':['#####','#    ','#### ','    #','    #','#   #',' ### '],
    '6':[' ### ','#    ','#### ','#   #','#   #','#   #',' ### '],
    '7':['#####','    #','   # ','  #  ','  #  ',' #   ',' #   '],
    '8':[' ### ','#   #','#   #',' ### ','#   #','#   #',' ### '],
    '9':[' ### ','#   #','#   #',' ####','    #','    #',' ### '],
    ' ' :['     ','     ','     ','     ','     ','     ','     '],
    '/' :['    #','   # ','  #  ',' #   ','#    ','     ','     '],
}

def FONT_5x7_render(text, x, y, color, scale=2):
    pixels = []
    cx = x
    for ch in text.upper():
        glyph = FONT_5x7.get(ch, FONT_5x7[' '])
        for py, row in enumerate(glyph):
            for px, c in enumerate(row):
                if c == '#':
                    for sx in range(scale):
                        for sy in range(scale):
                            pixels.append((cx + px*scale + sx, y + py*scale + sy, color))
        cx += 6 * scale
    return pixels


# ═══════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════

def main():
    os.makedirs('demo_maps', exist_ok=True)

    print("\n" + "=" * 60)
    print("  bestman 终端渲染可行性验证")
    print("=" * 60)

    # ── Part 1: ASCII 渲染 ──
    from rich.console import Console

    console = Console(highlight=False)

    console.print("\n[bold white][ 1 ][/] ASCII 回退渲染（所有终端可用）\n")

    for name, day in STAGES:
        console.print(f"  [bold]── {name} ──[/]")
        output = ascii_render_stage(engine, day)
        console.print(output)
        console.print()

    # ── Part 2: Canvas PNG 渲染 ──
    print("\n[ 2 ] Canvas PNG 渲染（Kitty/Ghostty/iTerm2/WezTerm）")
    print("      已保存到 demo_maps/ 目录\n")

    styles = [
        ('A_像素复古', style_a_pixel),
        ('B_古典航海图', style_b_parchment),
        ('C_极简暗色', style_c_minimal),
        ('D_深蓝海洋', style_d_ocean),
    ]

    for sname, sfn in styles:
        for sname_zh, day in STAGES:
            fname = f"demo_maps/{sname}_day{day:03d}.png"
            print(f"  生成 {fname} ...", end=' ')
            draw_fn = sfn(engine, day)
            png = make_png(CW, CH, draw_fn)
            with open(fname, 'wb') as f:
                f.write(png)
            print("OK")

    # ── 总结 ──
    console.print(f"""
  ╔══════════════════════════════════════════════════════╗
  ║  可渲染性总结                                        ║
  ╠══════════════════════════════════════════════════════╣
  ║  ASCII 回退（所有终端）：                             ║
  ║    • 50×14 Unicode 网格 ✓                            ║
  ║    • Rich 颜色标记 ✓                                 ║
  ║    • 航迹 + 起点 + 里程碑 ✓                           ║
  ║    • 无渐变、无曲线、无纹理 ✗                          ║
  ╠══════════════════════════════════════════════════════╣
  ║  Canvas PNG（Kitty 协议终端）：                       ║
  ║    • 全像素控制 ✓                                    ║
  ║    • 渐变、光晕、纹理 ✓                               ║
  ║    • 羊皮纸风格、荧光航迹、星空 ✓                      ║
  ║    • Ghostty / iTerm2 / WezTerm / Kitty 限定         ║
  ╚══════════════════════════════════════════════════════╝

  ASCII 输出已打印在终端上方（真实终端渲染）。
  PNG 文件保存在 demo_maps/ 目录。
  如果有 Kitty 兼容终端，可以用 `kitty +kitten icat demo_maps/A_像素复古_day087.png` 查看 PNG。
""")

    # 尝试 Kitty 显示第一张 PNG
    png_file = 'demo_maps/A_像素复古_day087.png'
    if os.path.exists(png_file):
        try:
            import base64
            with open(png_file, 'rb') as f:
                png_bytes = f.read()
            b64 = base64.b64encode(png_bytes).decode()
            chunk_size = 4096
            chunks = [b64[i:i+chunk_size] for i in range(0, len(b64), chunk_size)]
            ctrl = "\033_Ga=T,f=100,c=80,r=24"
            if len(chunks) == 1:
                sys.stdout.write(f"{ctrl};{chunks[0]}\033\\")
            else:
                sys.stdout.write(f"{ctrl},m=1;{chunks[0]}\033\\")
                for c in chunks[1:-1]:
                    sys.stdout.write(f"\033_Gm=1;{c}\033\\")
                sys.stdout.write(f"\033_Gm=0;{chunks[-1]}\033\\")
            sys.stdout.flush()
            print("\n  ↑ 如果看到一张图，说明 Kitty 协议可用")
        except Exception:
            pass


if __name__ == '__main__':
    main()
