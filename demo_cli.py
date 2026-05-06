#!/usr/bin/env python3
"""
方案A · 终端航海图 Demo
在支持 Kitty 协议的终端中直接显示 Canvas PNG 航海图。
用法：python demo_cli.py
支持的终端：Ghostty / Kitty / iTerm2 / WezTerm
"""

import sys, os, math, random, base64, struct, zlib, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bestman.core.config import DEFAULT_CONFIG
from bestman.core.map_engine import MapEngine

# ── 初始化真实 MapEngine ──
engine = MapEngine(DEFAULT_CONFIG)

# ── 画布 ──
CELL = 20
PAD_X, PAD_Y = 8, 80
W = engine.width * CELL + PAD_X * 2   # 1016
H = engine.height * CELL + PAD_Y + 8   # ~368

# ── 颜色 ──
BG     = (8, 16, 24, 255)
MIST   = (22, 38, 54, 255)
GRID   = (20, 60, 80, 80)
GOLD   = (255, 215, 0, 255)
OCEAN  = [(21,104,112,255),(26,128,120,255),(14,92,96,255),(18,80,88,255)]

# ── PNG 生成 ──
def make_png(draw_fn):
    pixels = bytearray()
    for y in range(H):
        pixels.append(0)
        for x in range(W):
            r,g,b,a = draw_fn(x,y)
            pixels.extend([r,g,b,a])
    raw = bytes(pixels)
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', W, H, 8, 6, 0, 0, 0)
    def chunk(ct, d):
        c = ct + d
        return struct.pack('>I', len(d)) + c + struct.pack('>I', zlib.crc32(c)&0xFFFFFFFF)
    return sig + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')

# ── Kitty 显示 ──
def kitty_show(png, cols=90, rows=24):
    b64 = base64.b64encode(png).decode()
    chunks = [b64[i:i+4096] for i in range(0,len(b64),4096)]
    ctrl = f"\033_Ga=T,f=100,c={cols},r={rows}"
    if len(chunks) == 1:
        sys.stdout.write(f"{ctrl};{chunks[0]}\033\\")
    else:
        sys.stdout.write(f"{ctrl},m=1;{chunks[0]}\033\\")
        for c in chunks[1:-1]:
            sys.stdout.write(f"\033_Gm=1;{c}\033\\")
        sys.stdout.write(f"\033_Gm=0;{chunks[-1]}\033\\")
    sys.stdout.flush()

# ── 像素字体 ──
FONT = {
    'A':['  #  ',' # # ','#   #','#####','#   #','#   #','#   #'],
    'B':['#### ','#   #','#### ','#   #','#   #','#   #','#### '],
    'D':['#### ','#   #','#   #','#   #','#   #','#   #','#### '],
    'E':['#####','#    ','#### ','#    ','#    ','#    ','#####'],
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
    '/':['    #','   # ','  #  ',' #   ','#    ','     ','     '],
}
def draw_text(text, x, y, color, scale=2):
    pxls = []
    cx = x
    for ch in text.upper():
        g = FONT.get(ch, FONT[' '])
        for py,row in enumerate(g):
            for px,c in enumerate(row):
                if c=='#':
                    for sx in range(scale):
                        for sy in range(scale):
                            pxls.append((cx+px*scale+sx, y+py*scale+sy, color))
        cx += 6*scale
    return pxls

# ── 画线 ──
def draw_line(pixels, x1,y1,x2,y2,color):
    dx=abs(x2-x1); dy=abs(y2-y1)
    sx=1 if x1<x2 else -1; sy=1 if y1<y2 else -1
    err=dx-dy
    cx,cy=x1,y1
    while True:
        r,g,b,a=color
        if (cx,cy) in pixels:
            pr,pg,pb,pa=pixels[(cx,cy)]
            aa=a/255
            pixels[(cx,cy)]=(int(pr*(1-aa)+r*aa),int(pg*(1-aa)+g*aa),int(pb*(1-aa)+b*aa),max(pa,a))
        else: pixels[(cx,cy)]=color
        if cx==x2 and cy==y2: break
        e2=2*err
        if e2>-dy: err-=dy; cx+=sx
        if e2<dx: err+=dx; cy+=sy

# ── 船精灵 ──
def draw_vessel(pixels, cx, cy):
    sprite = [
        '..BBBBB....','.BWWWWWB...','.BMWWWMB...',
        'BBBBBBBBBB.','BBGBBGBBBB.','.BBBBBBBBB.','..BBBBB....',
    ]
    pal={'B':(74,32,16,255),'W':(255,255,240,255),'M':(160,96,48,255),'G':(212,176,32,255)}
    vs=2; ws,hs=len(sprite[0]),len(sprite)
    ox=cx-ws*vs//2; oy=cy-hs*vs//2-4
    for py in range(hs):
        for px in range(len(sprite[py])):
            ch=sprite[py][px]
            if pal.get(ch):
                c=pal[ch]
                for sy in range(vs):
                    for sx in range(vs):
                        pixels[(ox+px*vs+sx,oy+py*vs+sy)]=c

# ── 画一轮地图 ──
def render_map(day):
    data = engine.build_render_data(tiles_revealed=day)
    grid = data['grid']
    ship = data['ship_pos']
    route = data['route']
    h, w = engine.height, engine.width

    # 去重航迹
    trail = set()
    trail_list = []
    for i in range(day):
        tx,ty = route[i]
        if (tx,ty) not in trail:
            trail.add((tx,ty))
            trail_list.append((tx,ty))

    pixels = {}
    rng = random.Random(42)

    # ── 海洋格子 ──
    for gy in range(h):
        for gx in range(w):
            cell = grid[gy][gx]
            ox, oy = PAD_X + gx*CELL, PAD_Y + gy*CELL
            for dy in range(CELL):
                for dx in range(CELL):
                    px, py = ox+dx, oy+dy
                    border = (dx<1 or dy<1 or dx>=CELL-1 or dy>=CELL-1)
                    if border:
                        pixels[(px,py)] = GRID
                    elif cell['status'] == 'fog':
                        pixels[(px,py)] = MIST
                    else:
                        pixels[(px,py)] = rng.choice(OCEAN)

    # ── 收集里程碑格子（统一用） ──
    ms_cells = {}
    for day_idx, name in DEFAULT_CONFIG['voyage']['milestones'].items():
        idx = int(day_idx)-1
        if idx < len(route):
            ms_cells[route[idx]] = (int(day_idx), name)

    # ── 已航轨迹 ──
    # 格子叠加暖色（加强，但跳过里程碑格子）
    for gx, gy in trail:
        if (gx,gy) in ms_cells: continue
        ox, oy = PAD_X + gx*CELL, PAD_Y + gy*CELL
        for dy in range(1, CELL-1):
            for dx in range(1, CELL-1):
                px, py = ox+dx, oy+dy
                if (px,py) in pixels and (px-PAD_X)//CELL == gx and (py-PAD_Y)//CELL == gy:
                    pr,pg,pb,pa = pixels[(px,py)]
                    pixels[(px,py)] = (min(255,pr+45), min(255,pg+30), max(pb-5, 0), pa)

    # 航迹连线 — 两层：外层光晕 + 内层主线
    # 里程碑格子处断开航迹
    ms_positions = set(ms_cells.keys())

    trail_pts = [(PAD_X+tx*CELL+CELL//2, PAD_Y+ty*CELL+CELL//2) for tx,ty in trail_list]

    # 按里程碑分组：每段单独绘制
    segments = []
    current_seg = []
    for pt, (tx,ty) in zip(trail_pts, trail_list):
        if (tx,ty) in ms_positions:
            if current_seg: segments.append(current_seg)
            current_seg = []
        else:
            current_seg.append(pt)
    if current_seg: segments.append(current_seg)

    for seg in segments:
        if len(seg) < 2: continue
        # 外层光晕
        for (x1,y1),(x2,y2) in zip(seg, seg[1:]):
            draw_line(pixels, x1, y1, x2, y2, (255, 200, 60, 60))
            draw_line(pixels, x1-1, y1, x2-1, y2, (255, 200, 60, 40))
            draw_line(pixels, x1+1, y1, x2+1, y2, (255, 200, 60, 40))
            draw_line(pixels, x1, y1-1, x2, y2-1, (255, 200, 60, 40))
            draw_line(pixels, x1, y1+1, x2, y2+1, (255, 200, 60, 40))
        # 内层主线
        for (x1,y1),(x2,y2) in zip(seg, seg[1:]):
            draw_line(pixels, x1, y1, x2, y2, (255, 215, 40, 200))

    # ── 起点标记 ◉ ──
    sx0, sy0 = route[0]
    scx = PAD_X + sx0*CELL + CELL//2
    scy = PAD_Y + sy0*CELL + CELL//2
    for dy in range(-9, 10):
        for dx in range(-9, 10):
            d = math.sqrt(dx*dx+dy*dy)
            if 7 <= d <= 9:
                px,py = scx+dx, scy+dy
                if (px,py) in pixels: pixels[(px,py)] = (136, 204, 255, 255)

    # ── 里程碑 ✦ ──
    for (mx,my), (mday, mname) in ms_cells.items():
        if mday > day: continue
        mcx = PAD_X + mx*CELL + CELL//2
        mcy = PAD_Y + my*CELL + CELL//2

        # 外层大光晕（金色弥漫）
        for dy in range(-18, 19):
            for dx in range(-18, 19):
                d = math.sqrt(dx*dx+dy*dy)
                if d < 18:
                    a = int(90 * (1 - d/18))
                    px,py = mcx+dx, mcy+dy
                    if (px,py) in pixels:
                        pr,pg,pb,pa = pixels[(px,py)]
                        pixels[(px,py)] = (min(255,pr+a), min(255,pg+int(a*0.85)), max(0,pb-int(a*0.1)), pa)

        # 中层光环（明亮金圈）
        for dy in range(-9, 10):
            for dx in range(-9, 10):
                d = math.sqrt(dx*dx+dy*dy)
                if 7.5 <= d <= 9.5:
                    px,py = mcx+dx, mcy+dy
                    if (px,py) in pixels: pixels[(px,py)] = (255, 215, 0, 255)

        # 内层星形本体（4角星 = 航线交叉）
        for dy in range(-5, 6):
            for dx in range(-5, 6):
                if abs(dx) + abs(dy) <= 6 and abs(abs(dx)-abs(dy)) <= 2:
                    px,py = mcx+dx, mcy+dy
                    if (px,py) in pixels: pixels[(px,py)] = (255, 255, 255, 255)

        # 标签（里程碑名）
        if mname and len(mname) <= 6:
            label_x = mcx + 8
            label_y = mcy - 16
            for px,py,c in draw_text(mname[:6], label_x, label_y, (255, 215, 0, 255), 1):
                if 0<=px<W and 0<=py<H and (px,py) in pixels: pixels[(px,py)] = c

    # ── 终点 ★ ──
    if day >= engine.total_days:
        fx, fy = route[-1]
        fcx = PAD_X + fx*CELL + CELL//2
        fcy = PAD_Y + fy*CELL + CELL//2
        for dy in range(-32, 33):
            for dx in range(-32, 33):
                d = math.sqrt(dx*dx+dy*dy)
                if d < 32:
                    a = int(100*(1-d/32))
                    px,py = fcx+dx, fcy+dy
                    if (px,py) in pixels:
                        pr,pg,pb,pa = pixels[(px,py)]
                        pixels[(px,py)] = (min(255,pr+a), min(255,pg+int(a*0.85)), min(255,pb), pa)

    # ── 迷雾渐变 ──
    if day < engine.total_days:
        rv = route[min(day, engine.total_days-1)][0]
        fog_x = PAD_X + (rv+1)*CELL
        for dx in range(-CELL, CELL*3):
            frac = max(0, min(1, (dx+CELL)/(CELL*3)))
            if frac > 0:
                for gy in range(h):
                    for dy in range(CELL):
                        px, py = fog_x+dx, PAD_Y+gy*CELL+dy
                        if (px,py) in pixels:
                            pr,pg,pb,pa = pixels[(px,py)]
                            # 跳过网格线
                            border = ((px-PAD_X)%CELL < 1 or (py-PAD_Y)%CELL < 1 or
                                       (px-PAD_X)%CELL >= CELL-1 or (py-PAD_Y)%CELL >= CELL-1)
                            if not border:
                                alpha = frac*0.7
                                pixels[(px,py)] = (
                                    int(pr*(1-alpha)+BG[0]*alpha),
                                    int(pg*(1-alpha)+BG[1]*alpha),
                                    int(pb*(1-alpha)+BG[2]*alpha), pa)

    # ── 船 ──
    if ship and day < engine.total_days:
        shx, shy = ship
        draw_vessel(pixels, PAD_X + shx*CELL + CELL//2, PAD_Y + shy*CELL + CELL//2)

        # 船光晕
        scx = PAD_X + shx*CELL + CELL//2
        scy = PAD_Y + shy*CELL + CELL//2
        for dy in range(-16, 17):
            for dx in range(-16, 17):
                d = math.sqrt(dx*dx+dy*dy)
                if d < 16:
                    a = int(70*(1-d/16))
                    px,py = scx+dx, scy+dy
                    if (px,py) in pixels:
                        pr,pg,pb,pa = pixels[(px,py)]
                        pixels[(px,py)] = (min(255,pr+a), min(255,pg+int(a*0.75)), min(255,pb+int(a*0.2)), pa)

        # 金色信标点
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                if dx*dx+dy*dy <= 9:
                    px,py = scx+dx, scy+dy+12
                    if (px,py) in pixels: pixels[(px,py)] = GOLD

    # ── 标题 ──
    title = f"DAY {day} / {engine.total_days}"
    for px,py,c in draw_text(title, PAD_X, 10, (78,201,176,255), 2):
        if 0<=px<W and 0<=py<PAD_Y: pixels[(px,py)] = c

    subtitle = f"{engine.get_region_at(day)}  ·  {int(day/engine.total_days*100)}%"
    for px,py,c in draw_text(subtitle, PAD_X, 38, (86,156,214,255), 1):
        if 0<=px<W and 0<=py<PAD_Y: pixels[(px,py)] = c

    # ── 图例 ──
    ly = PAD_Y + h*CELL + 12
    items = [
        ([(255,200,80,255)]*4, '航迹'), ([(136,204,255,255)]*4, '起点'),
        ([(74,32,16,255)]*4, '船'), (GOLD, '里程碑'),
        (MIST, '迷雾'),
    ]
    lx = PAD_X + 10
    for color,label in items:
        c8 = color if isinstance(color, tuple) else color[0]
        # 色块
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                px,py = lx+dx, ly+dy
                if 0<=px<W and 0<=py<H: pixels[(px,py)] = c8
        lx += 12
        # 标签
        for px,py,c in draw_text(label, lx-4, ly-5, (122,138,154,255), 1):
            if 0<=px<W and py<H: pixels[(px,py)] = c
        lx += len(label)*6 + 8

    return lambda x,y: pixels.get((x,y), BG)


# ── 主流程 ──
STAGES = [
    ("启航", 10),
    ("季风带", 87),
    ("近大陆", 150),
    ("抵达！", 175),
]

def main():
    # 检测终端
    term = os.environ.get('TERM_PROGRAM', '未知')
    print(f"\033[2J\033[H", end='')  # 清屏
    print(f"  bestman · 方案A 像素复古 — 终端航海图 Demo")
    print(f"  检测到终端: {term}")
    print(f"  提示: 如果你的终端不支持 Kitty 协议，PNG 将不会显示")
    print()
    time.sleep(1)

    for name, day in STAGES:
        print(f"  ═══ {name} · Day {day} ═══")
        png = make_png(render_map(day))
        kitty_show(png, cols=90, rows=24)
        print()
        time.sleep(1.5)

    print()
    print(f"  已完成 4 阶段展示。")
    print(f"  方案A 特点: 暗色网格 + 金色航迹线 + 像素帆船 + 迷雾渐变 + 起点/里程碑标记 + 图例")
    print()

if __name__ == '__main__':
    main()
