#!/usr/bin/env python3
"""
终端 Canvas 方案：把整张地图画成一张 PNG，Kitty 协议直接显示
不嵌 ASCII，不分行，不搞光标定位。
"""

import base64
import struct
import zlib
import sys
import math
import random


def kitty_show(png: bytes, cols: int = 80, rows: int = 24):
    """Kitty 协议：显示一张 PNG，占 cols 列 × rows 行"""
    b64 = base64.b64encode(png).decode()
    chunk_size = 4096
    chunks = [b64[i:i+chunk_size] for i in range(0, len(b64), chunk_size)]
    ctrl = f"\033_Ga=T,f=100,c={cols},r={rows}"
    if len(chunks) == 1:
        sys.stdout.write(f"{ctrl};{chunks[0]}\033\\")
    else:
        sys.stdout.write(f"{ctrl},m=1;{chunks[0]}\033\\")
        for i, c in enumerate(chunks[1:-1]):
            sys.stdout.write(f"\033_Gm=1;{c}\033\\")
        sys.stdout.write(f"\033_Gm=0;{chunks[-1]}\033\\")
    sys.stdout.flush()


def make_png(width: int, height: int, draw_fn) -> bytes:
    """生成 PNG：draw_fn(ctx) 在 (0,0,width,height) 上画画"""
    # 构造 RGBA 像素数组
    pixels = bytearray()
    for y in range(height):
        pixels.append(0)  # filter none
        for x in range(width):
            r, g, b, a = draw_fn(x, y)
            pixels.append(r)
            pixels.append(g)
            pixels.append(b)
            pixels.append(a)

    raw = bytes(pixels)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)

    def chunk(ctype, data):
        c = ctype + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


# ────────────────────────────────────────────
# 画布尺寸
# ────────────────────────────────────────────

SCALE = 8       # 每个格子 8×8 像素
COLS = 30
ROWS = 8
CELL = 80       # 每个格子像素（含边框 2px）
PAD_X = 8       # 左边距
PAD_Y = 120     # 上边距（留给标题）
W = COLS * CELL + PAD_X * 2
H = ROWS * CELL + PAD_Y + 8

REVEALED = 23    # 已揭示到第 23 格
SHIP_C = 22      # 船在第 22 列
SHIP_R = 2       # 第 3 行

# ── 颜色 ──
BG      = (8, 16, 24, 255)
OCEAN   = (21, 104, 112, 255)
OCEAN2  = (26, 128, 120, 255)
OCEAN3  = (14, 92, 96, 255)
MIST    = (22, 38, 54, 255)
GOLD    = (255, 215, 0, 255)
GRID    = (20, 60, 80, 80)
BLACK   = (0, 0, 0, 255)
WHITE   = (255, 255, 240, 255)
RED     = (200, 32, 32, 255)
ORANGE  = (240, 80, 16, 255)
DARKRED = (112, 32, 16, 255)
BROWN   = (74, 32, 16, 255)
TAN     = (160, 96, 48, 255)
PURPLE  = (56, 24, 80, 255)
MAGENTA = (136, 48, 160, 255)
CYAN    = (80, 210, 255, 255)
NAVY    = (26, 42, 64, 255)
GREEN   = (96, 176, 64, 255)
DARKGREEN=(26, 90, 48, 255)
ORANGE2 = (208, 144, 16, 255)
DARK    = (24, 24, 24, 255)
BRIGHT  = (255, 96, 0, 255)
GRAY    = (128, 128, 144, 255)
LIME    = (48, 208, 112, 255)
TRANS   = (0, 0, 0, 0)


# ── 载具像素画 ──

def draw_schooner(x, y):
    """12×9 初阶帆船"""
    pixels = [
        '..BBBBB....',
        '.BWWWWWB...',
        '.BMWWWMB...',
        'BBBBBBBBBB.',
        'BBGBBGBBBB.',
        '.BBBBBBBBB.',
        '..BBBBB....',
    ]
    pal = {'B': BROWN, 'W': WHITE, 'M': TAN, 'G': GOLD}
    return [(px, py, pal.get(ch, TRANS))
            for py, row in enumerate(pixels)
            for px, ch in enumerate(row) if pal.get(ch)]


def draw_dragon(x, y):
    pixels = [
        '...RRR......',
        '.RRRRRR.....',
        'ROOOOOOR....',
        'RODDDDDOR...',
        'ODDGGGGDDO..',
        '.RDDDDDDR...',
        '..RRRRR.....',
    ]
    pal = {'R': RED, 'O': ORANGE, 'D': DARKRED, 'G': GOLD}
    return [(px, py, pal.get(ch, TRANS))
            for py, row in enumerate(pixels)
            for px, ch in enumerate(row) if pal.get(ch)]


def draw_ghost(x, y):
    pixels = [
        '..PPPPP...',
        '.PPPPPPP..',
        'PPPGPPGPP.',
        'PPPPPPPPP.',
        '.PPPPPPPPP',
        '..PPPPP...',
    ]
    pal = {'P': PURPLE, 'G': MAGENTA}
    return [(px, py, pal.get(ch, TRANS))
            for py, row in enumerate(pixels)
            for px, ch in enumerate(row) if pal.get(ch)]


def draw_sword(x, y):
    pixels = [
        '...CCC....',
        '..CXCXC...',
        '.CXCXCXC..',
        'CXCXCXCXC.',
        '.CXCXCXC..',
        '..CXCXC...',
        '...CCC....',
    ]
    pal = {'C': NAVY, 'X': CYAN}
    return [(px, py, pal.get(ch, TRANS))
            for py, row in enumerate(pixels)
            for px, ch in enumerate(row) if pal.get(ch)]


def draw_yinglong(x, y):
    pixels = [
        '..GGGGGS....',
        '.GJJJJJSG...',
        'GJIIIJJJSG..',
        'JJZJZJZJJ..',
        'JIIJIIJJJ...',
        '.GGGGGGG...',
        '...NN......',
    ]
    pal = {'G': DARKGREEN, 'J': GREEN, 'I': (42, 42, 48, 255),
           'Z': GOLD, 'N': (13, 30, 50, 255)}
    return [(px, py, pal.get(ch, TRANS))
            for py, row in enumerate(pixels)
            for px, ch in enumerate(row) if pal.get(ch)]


def draw_bike(x, y):
    pixels = [
        '..RRRR..',
        '.RROORR.',
        'RROOOORR',
        'RODDDDOR',
        'ROBOOBOR',
        '.RDDDDR.',
        '..RRRR..',
    ]
    pal = {'R': (128, 96, 16, 255), 'O': ORANGE2, 'D': DARK, 'B': BRIGHT}
    return [(px, py, pal.get(ch, TRANS))
            for py, row in enumerate(pixels)
            for px, ch in enumerate(row) if pal.get(ch)]


def draw_ufo(x, y):
    pixels = [
        '..........',
        '...SSS....',
        '..SCCCS...',
        '.SCSSSCS..',
        '.SCCCCCS..',
        '..S...S..',
    ]
    pal = {'S': GRAY, 'C': LIME}
    return [(px, py, pal.get(ch, TRANS))
            for py, row in enumerate(pixels)
            for px, ch in enumerate(row) if pal.get(ch)]


def draw_qilin(x, y):
    pixels = [
        '..GGGG....',
        '.GZGZGZG..',
        'GGGGGGGG..',
        'GGGGGGGGG.',
        'GZGGGGZG..',
        '.GGGGGG...',
        '...NN....',
    ]
    pal = {'G': (192, 144, 32, 255), 'Z': (255, 48, 48, 255), 'N': (13, 30, 50, 255)}
    return [(px, py, pal.get(ch, TRANS))
            for py, row in enumerate(pixels)
            for px, ch in enumerate(row) if pal.get(ch)]


VESSELS_FN = {
    'schooner': draw_schooner,
    'dragon': draw_dragon,
    'ghost': draw_ghost,
    'sword': draw_sword,
    'yinglong': draw_yinglong,
    'bike': draw_bike,
    'ufo': draw_ufo,
    'qilin': draw_qilin,
}

# ── 文字渲染器（手写像素字，不用字体） ──

FONT_5x7 = {
    # 每个字符 5×7 像素
    'A': ['  #  ', ' # # ', '#   #', '#####', '#   #', '#   #', '#   #'],
    'B': ['#### ', '#   #', '#### ', '#   #', '#   #', '#   #', '#### '],
    'C': [' ### ', '#   #', '#    ', '#    ', '#    ', '#   #', ' ### '],
    'D': ['#### ', '#   #', '#   #', '#   #', '#   #', '#   #', '#### '],
    'E': ['#####', '#    ', '#### ', '#    ', '#    ', '#    ', '#####'],
    'F': ['#####', '#    ', '#### ', '#    ', '#    ', '#    ', '#    '],
    'G': [' ### ', '#   #', '#    ', '#  ##', '#   #', '#   #', ' ### '],
    'H': ['#   #', '#   #', '#####', '#   #', '#   #', '#   #', '#   #'],
    'I': [' ### ', '  #  ', '  #  ', '  #  ', '  #  ', '  #  ', ' ### '],
    'L': ['#    ', '#    ', '#    ', '#    ', '#    ', '#    ', '#####'],
    'M': ['#   #', '## ##', '# # #', '#   #', '#   #', '#   #', '#   #'],
    'N': ['#   #', '##  #', '# # #', '#  ##', '#   #', '#   #', '#   #'],
    'O': [' ### ', '#   #', '#   #', '#   #', '#   #', '#   #', ' ### '],
    'P': ['#### ', '#   #', '#   #', '#### ', '#    ', '#    ', '#    '],
    'R': ['#### ', '#   #', '#   #', '#### ', '#  # ', '#   #', '#   #'],
    'S': [' ### ', '#    ', ' ### ', '    #', '    #', '    #', ' ### '],
    'T': ['#####', '  #  ', '  #  ', '  #  ', '  #  ', '  #  ', '  #  '],
    'U': ['#   #', '#   #', '#   #', '#   #', '#   #', '#   #', ' ### '],
    'V': ['#   #', '#   #', '#   #', '#   #', ' # # ', '  #  ', '   # '],
    'Y': ['#   #', '#   #', ' # # ', '  #  ', '  #  ', '  #  ', '  #  '],
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
    '·': ['     ', '  #  ', '     ', '     ', '     ', '     ', '     '],
}

def draw_text(text, x, y, color, scale=2):
    """画像素文字，scale 倍放大"""
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
        cx += 6 * scale  # 字符宽 + 间距
    return pixels


# ── 绘制整张地图 ──

def render_map(vessel_name):
    cells = {}

    # 每个格子的颜色（带天气随机）
    rng = random.Random(42)
    for c in range(COLS):
        for r in range(ROWS):
            if c <= REVEALED:
                rr = rng.random()
                if rr < 0.5: cells[(c, r)] = OCEAN
                elif rr < 0.75: cells[(c, r)] = OCEAN2
                else: cells[(c, r)] = OCEAN3
            else:
                cells[(c, r)] = MIST

    # 里程碑和驿站颜色覆盖
    if (14, 1) in cells: cells[(14, 1)] = (24, 100, 100, 255)  # 深一点，准备画星
    if (6, 4) in cells: cells[(6, 4)] = (24, 100, 80, 255)

    def draw_pixel(x, y):
        """(x, y) → (R, G, B, A)"""
        cx = (x - PAD_X) // CELL
        cy = (y - PAD_Y) // CELL
        lx = (x - PAD_X) % CELL
        ly = (y - PAD_Y) % CELL

        # 边框（2px 粗）
        is_border = (lx < 2 or ly < 2 or lx >= CELL - 2 or ly >= CELL - 2)

        if is_border:
            # 只有格子内边界才有网格线
            return GRID

        # 格子内部
        if 0 <= cx < COLS and 0 <= cy < ROWS:
            cell_color = cells.get((cx, cy), MIST)
            return cell_color

        return BG

    # 先构建基础像素
    # 然后叠加里程碑、船等

    # 用列表缓存像素颜色
    # 实际上用 draw_fn 回调太慢，改用预计算
    base_map = {}
    for x in range(W):
        for y in range(H):
            base_map[(x, y)] = draw_pixel(x, y)

    # 特殊标记
    # 里程碑 ✦ (在 14,1 格) — 放大
    star_cx = PAD_X + 14 * CELL + CELL // 2
    star_cy = PAD_Y + 1 * CELL + CELL // 2
    sr = 18  # 星半径
    for dy in range(-sr, sr + 1):
        w = sr - abs(dy)
        for dx in range(-w, w + 1):
            px, py = star_cx + dx, star_cy + dy
            if 0 <= px < W and 0 <= py < H:
                base_map[(px, py)] = GOLD

    # 驿站 🏝️ (在 6,4 格) — 放大
    isle_cx = PAD_X + 6 * CELL + CELL // 2
    isle_cy = PAD_Y + 4 * CELL + CELL // 2
    for dy in range(-20, 12):
        for dx in range(-14, 15):
            if abs(dx) + abs(dy) <= 20 and dy < 6:
                px, py = isle_cx + dx, isle_cy + dy
                if 0 <= px < W and 0 <= py < H:
                    base_map[(px, py)] = (32, 140, 60, 255)
    for dy in range(0, 16):
        for dx in range(-4, 5):
            px, py = isle_cx + dx, isle_cy + dy
            if 0 <= px < W and 0 <= py < H:
                base_map[(px, py)] = (100, 60, 30, 255)

    # 船 —— 画在 SHIP_C, SHIP_R
    ship_cx = PAD_X + SHIP_C * CELL + CELL // 2
    ship_cy = PAD_Y + SHIP_R * CELL + CELL // 2

    vessel_fn = VESSELS_FN.get(vessel_name)
    vs = 7  # 精灵像素放大倍数（CELL=80 时每个精灵像素 = 7 图像像素）
    if vessel_fn:
        for dx, dy, color in vessel_fn(ship_cx, ship_cy):
            # 船像素偏移：从船中心偏移，按 vs 放大
            for sx in range(vs):
                for sy in range(vs):
                    px = ship_cx + dx * vs - 6 * vs + sx  # 居中（12 像素宽精灵）
                    py = ship_cy + dy * vs - 5 * vs + sy  # 偏上
                    if 0 <= px < W and 0 <= py < H and color[3] > 0:
                        base_map[(px, py)] = color

    # 光晕（在船周围）
    for dy in range(-40, 41):
        for dx in range(-40, 41):
            d = math.sqrt(dx*dx + dy*dy)
            if d < 40:
                px, py = ship_cx + dx, ship_cy + dy
                if 0 <= px < W and 0 <= py < H:
                    alpha = int(max(0, 100 * (1 - d/40)))
                    r, g, b, a = base_map.get((px, py), BG)
                    glow_r = min(255, r + alpha)
                    glow_g = min(255, g + int(alpha * 0.8))
                    glow_b = min(255, b)
                    base_map[(px, py)] = (glow_r, glow_g, glow_b, a)

    # 标题文字（3x 放大）
    text_pixels = draw_text(f"bestman · {vessel_name.upper()}", 10, 15, (78, 201, 176, 255), scale=3)
    text2 = draw_text(f"DAY {SHIP_C+1} · JIFENGDAI · 149 DAYS LEFT", 10, 50, (86, 156, 214, 255), scale=3)
    for px, py, color in text_pixels + text2:
        if 0 <= px < W and 0 <= py < PAD_Y:
            base_map[(px, py)] = color

    # 返回 draw_fn
    return lambda x, y: base_map.get((x, y), BG)


def main():
    # 清屏
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()

    vessels_list = [
        ('schooner', '⛵ 初阶帆船 - 默认载具'),
        ('dragon', '🐉 龙头战船 - 300 金币'),
        ('sword', '🗡️ 飞剑 - 修仙默认'),
        ('yinglong', '🦅 应龙 - 800 金币'),
    ]

    import time

    for vessel_id, desc in vessels_list:
        print(f"\n  {desc}")
        png = make_png(W, H, render_map(vessel_id))
        kitty_show(png, cols=COLS * 3, rows=ROWS + 12)
        time.sleep(1.5)
        print()

    print(f"""
  ╔══════════════════════════════════════╗
  ║  终端 Canvas 方案                     ║
  ║  整张地图 = 1 张 PNG = 1 个转义序列   ║
  ║  零光标定位  零分行  零 ASCII 拼接     ║
  ╚══════════════════════════════════════╝
""")
    # 不删图，留在终端
    sys.stdout.flush()


if __name__ == '__main__':
    main()
