"""Canvas PNG renderer — Kitty graphics protocol display.

Renders the voyage map as a single PNG image and displays it directly
in the terminal via the Kitty graphics protocol.

Implements ``BaseRenderer`` for the three-layer architecture.

Supported terminals: Ghostty, Kitty, iTerm2, WezTerm.
"""

import math
import random
from dataclasses import fields

from bestman.renderers.base import BaseRenderer
from bestman.renderers.canvas.font import draw_text
from bestman.renderers.canvas.kitty import kitty_available
from bestman.renderers.canvas.palette import Palette, get_palette
from bestman.renderers.canvas.png import make_png
from bestman.renderers.canvas.primitives import (
    draw_cross_star,
    draw_glow,
    draw_line,
    draw_ring,
)

# ── 画布尺寸（对应 MapEngine 50×14 网格） ──────────────────────

CELL = 20              # 每格像素（含 1px 网格线）
PAD_X = 8              # 左边距
PAD_Y = 80             # 上边距（标题区域）
W = 50 * CELL + PAD_X * 2
H = 14 * CELL + PAD_Y + 8


# ── 默认阶段（纹理映射用，保留兼容） ──────────────────────────

_DEFAULT_STAGES = [
    {"name": "启航", "days": [1, 25]},
    {"name": "迷雾之海", "days": [26, 50]},
    {"name": "季风带", "days": [51, 75]},
    {"name": "贸易航线", "days": [76, 100]},
    {"name": "赤道无风带", "days": [101, 125]},
    {"name": "信风带", "days": [126, 150]},
    {"name": "新大陆近海", "days": [151, 175]},
]


# ── 载具像素精灵 ──────────────────────────────────────────────

def _draw_vessel_pixels(vessel_def, cx: int, cy: int, scale: int, pixels: dict):
    """Draw a VesselDef pixel sprite directly into the pixels dict."""
    if not vessel_def:
        return
    sprite_w = vessel_def.width
    sprite_h = vessel_def.height
    origin_x = cx - (sprite_w * scale) // 2
    origin_y = cy - (sprite_h * scale) // 2

    for py, row in enumerate(vessel_def.pixels):
        for px, ch in enumerate(row):
            color = vessel_def.palette.get(ch)
            if color and color[3] > 0:
                for sx in range(scale):
                    for sy in range(scale):
                        dx = origin_x + px * scale + sx
                        dy = origin_y + py * scale + sy
                        if 0 <= dx < W and 0 <= dy < H:
                            pixels[(dx, dy)] = color


# ═══════════════════════════════════════════════════════════════
# 内部渲染函数
# ═══════════════════════════════════════════════════════════════

def _build_base_map(route: list, tiles_revealed: int, pal: Palette) -> dict:
    """Build pixel map with background + ocean cells + grid lines.

    Returns:
        dict of ``{(x, y): (R, G, B, A)}``.
    """
    pixels = {}

    # 已揭示格子集合
    revealed = set()
    for i in range(min(tiles_revealed, len(route))):
        revealed.add(route[i])

    # 确定性海洋颜色
    ocean_rng = random.Random(42)
    ocean_cache = {}
    for c in range(50):
        for r in range(14):
            ocean_cache[(c, r)] = ocean_rng.choice(pal.ocean)

    for y in range(H):
        for x in range(W):
            gx = (x - PAD_X) // CELL
            gy = (y - PAD_Y) // CELL
            lx = (x - PAD_X) % CELL
            ly = (y - PAD_Y) % CELL
            in_grid = 0 <= gx < 50 and 0 <= gy < 14

            # 标题 / 图例区域
            if gy < 0 or gy >= 14:
                pixels[(x, y)] = pal.bg
                continue

            # 网格边框
            is_border = lx < 1 or ly < 1 or lx >= CELL - 1 or ly >= CELL - 1
            if is_border:
                pixels[(x, y)] = pal.grid if in_grid else pal.bg
                continue

            # 格子内部
            if (gx, gy) in revealed:
                pixels[(x, y)] = ocean_cache[(gx, gy)]
            else:
                pixels[(x, y)] = pal.mist

    return pixels


def _draw_trail_cells(pixels: dict, route: list, tiles_revealed: int,
                      milestones: set, pal: Palette):
    """Overlay warm colour on cells that have been traversed.

    Skips milestone cells (they get their own rendering).
    """
    seen = set()
    for i in range(min(tiles_revealed, len(route))):
        cell = route[i]
        if cell in seen or cell in milestones:
            continue
        seen.add(cell)
        gx, gy = cell
        ox = PAD_X + gx * CELL + 1
        oy = PAD_Y + gy * CELL + 1
        ar, ag, ab = pal.trail_cell_add
        for dy in range(CELL - 2):
            for dx in range(CELL - 2):
                px, py = ox + dx, oy + dy
                if (px, py) in pixels:
                    pr, pg, pb, pa = pixels[(px, py)]
                    pixels[(px, py)] = (
                        min(255, pr + ar),
                        min(255, pg + ag),
                        max(0, pb - ab) if ab else pb,
                        pa,
                    )


def _draw_trail_line(pixels: dict, route: list, tiles_revealed: int,
                     milestones: set, pal: Palette):
    """Draw a two-layer trail line: outer glow + inner gold core.

    The trail is split into segments at milestone cells so the line
    doesn't obscure milestone markers.
    """
    # Build ordered list of unique cells
    seen = set()
    ordered = []
    for i in range(min(tiles_revealed, len(route))):
        cell = route[i]
        if cell not in seen:
            seen.add(cell)
            ordered.append(cell)

    # Convert to pixel centre coords
    pts = [(PAD_X + cx * CELL + CELL // 2, PAD_Y + cy * CELL + CELL // 2)
           for cx, cy in ordered]

    # Split at milestone cells
    segments = []
    seg = []
    for pt, cell in zip(pts, ordered):
        if cell in milestones:
            if seg:
                segments.append(seg)
            seg = []
        else:
            seg.append(pt)
    if seg:
        segments.append(seg)

    outer = pal.trail_line_outer
    inner = pal.trail_line_inner

    for seg in segments:
        if len(seg) < 2:
            continue
        # Outer glow — 2px wide
        for (x1, y1), (x2, y2) in zip(seg, seg[1:]):
            draw_line(pixels, x1, y1, x2, y2, outer)
            draw_line(pixels, x1 - 1, y1, x2 - 1, y2, outer)
            draw_line(pixels, x1 + 1, y1, x2 + 1, y2, outer)
            draw_line(pixels, x1, y1 - 1, x2, y2 - 1, outer)
            draw_line(pixels, x1, y1 + 1, x2, y2 + 1, outer)
        # Inner core
        for (x1, y1), (x2, y2) in zip(seg, seg[1:]):
            draw_line(pixels, x1, y1, x2, y2, inner)


def _draw_start_marker(pixels: dict, route: list, pal: Palette):
    """Draw a start marker (blue ring) at the first route cell."""
    if not route:
        return
    cx, cy = route[0]
    scx = PAD_X + cx * CELL + CELL // 2
    scy = PAD_Y + cy * CELL + CELL // 2
    draw_ring(pixels, scx, scy, 7.0, 9.5, pal.start_ring)


def _draw_milestones(pixels: dict, route: list, tiles_revealed: int,
                     milestones_config: dict, pal: Palette):
    """Draw prominent milestone markers with glow, ring, star, and label.

    Only milestones whose day <= tiles_revealed are drawn.
    """
    if not milestones_config:
        return

    for day, name in milestones_config.items():
        idx = day - 1
        if idx < 0 or idx >= len(route) or idx >= tiles_revealed:
            continue
        cx, cy = route[idx]
        mx = PAD_X + cx * CELL + CELL // 2
        my = PAD_Y + cy * CELL + CELL // 2

        # Outer glow
        draw_glow(pixels, mx, my, 18.0, pal.milestone_glow)
        # Gold ring
        draw_ring(pixels, mx, my, 7.5, 9.5, pal.milestone_ring)
        # White cross star
        draw_cross_star(pixels, mx, my, 5, pal.milestone_star)
        # Label above
        if name and len(name) <= 8:
            label_x = mx + 9
            label_y = my - 18
            for px, py, c in draw_text(name[:8], label_x, label_y,
                                       pal.milestone_label, scale=1):
                if 0 <= px < W and 0 <= py < H and (px, py) in pixels:
                    pixels[(px, py)] = c


def _draw_finish(pixels: dict, route: list, total_days: int,
                 tiles_revealed: int, pal: Palette):
    """Draw a golden glow at the finish cell (only when complete)."""
    if tiles_revealed < total_days or not route:
        return
    fx, fy = route[-1]
    fcx = PAD_X + fx * CELL + CELL // 2
    fcy = PAD_Y + fy * CELL + CELL // 2
    draw_glow(pixels, fcx, fcy, 30.0, pal.finish_glow)


def _draw_fog(pixels: dict, route: list, tiles_revealed: int, pal: Palette):
    """Apply a linear gradient fog covering unrevealed cells."""
    if tiles_revealed >= len(route):
        return

    rv = route[min(tiles_revealed, len(route) - 1)][0]
    fog_x = PAD_X + (rv + 1) * CELL

    for dx in range(-CELL, CELL * 3):
        frac = max(0.0, min(1.0, (dx + CELL) / (CELL * 3)))
        if frac <= 0:
            continue
        for gy in range(14):
            for dy in range(CELL):
                px = fog_x + dx
                py = PAD_Y + gy * CELL + dy
                if (px, py) not in pixels:
                    continue
                # Skip grid border pixels
                lx = (px - PAD_X) % CELL
                if lx < 1 or lx >= CELL - 1:
                    continue
                pr, pg, pb, pa = pixels[(px, py)]
                alpha = frac * 0.7
                pixels[(px, py)] = (
                    int(pr * (1 - alpha) + pal.bg[0] * alpha),
                    int(pg * (1 - alpha) + pal.bg[1] * alpha),
                    int(pb * (1 - alpha) + pal.bg[2] * alpha),
                    pa,
                )


def _overlay_emoji(png_bytes: bytes, emoji: str, center: tuple) -> bytes:
    """Overlay an emoji character onto a PNG at the given pixel centre.

    Uses Pillow to composite the emoji on top of the existing PNG.
    Falls back silently (returns original bytes) if Pillow is unavailable
    or no suitable font is found.

    Args:
        png_bytes: Raw PNG bytes produced by make_png.
        emoji:     A single emoji character (e.g. "🐉").
        center:    (cx, cy) pixel coordinate for the emoji centre.

    Returns:
        PNG bytes with emoji composited in, or original bytes on failure.
    """
    try:
        import io
        from PIL import Image, ImageDraw, ImageFont

        cx, cy = center
        img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
        draw = ImageDraw.Draw(img)

        # Try to load a system emoji font large enough to be visible.
        # Font size is chosen so the emoji fills roughly 2 map cells (40px).
        font_size = 32
        font = None
        _emoji_font_candidates = [
            # macOS — Apple Color Emoji is a TTC, index=0 required
            ("/System/Library/Fonts/Apple Color Emoji.ttc", {"index": 0}),
            # Linux (Noto)
            ("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", {}),
            ("/usr/share/fonts/noto/NotoColorEmoji.ttf", {}),
            # Windows
            ("C:/Windows/Fonts/seguiemj.ttf", {}),
        ]
        for path, kwargs in _emoji_font_candidates:
            try:
                font = ImageFont.truetype(path, font_size, **kwargs)
                break
            except (OSError, IOError, Exception):
                continue

        if font is None:
            # No emoji font found — skip overlay rather than draw □
            return png_bytes

        # Measure text bounding box to centre it precisely
        bbox = draw.textbbox((0, 0), emoji, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = cx - tw // 2 - bbox[0]
        y = cy - th // 2 - bbox[1]

        draw.text((x, y), emoji, font=font, embedded_color=True)

        out = io.BytesIO()
        img.save(out, format="PNG")
        return out.getvalue()

    except Exception:
        return png_bytes


def _draw_vessel(pixels: dict, route: list, tiles_revealed: int,
                 vessel_def, pal: Palette):
    """Draw the ship sprite with beacon and glow.

    Returns:
        (scx, scy) pixel centre of the vessel, or None if not drawn.
    """
    if tiles_revealed <= 0 or tiles_revealed > len(route):
        return None
    sx, sy = route[tiles_revealed - 1]
    scx = PAD_X + sx * CELL + CELL // 2
    scy = PAD_Y + sy * CELL + CELL // 2

    # Glow (additive RGB, may be 3- or 4-tuple)
    ar, ag, ab = pal.vessel_glow_add[:3]
    for dy in range(-16, 17):
        for dx in range(-16, 17):
            d = math.sqrt(dx * dx + dy * dy)
            if d < 16:
                a = int(70 * (1 - d / 16))
                px, py = scx + dx, scy + dy
                if (px, py) in pixels:
                    pr, pg, pb, pa = pixels[(px, py)]
                    pixels[(px, py)] = (
                        min(255, pr + int(ar * a / 70)),
                        min(255, pg + int(ag * a / 70)),
                        min(255, pb + int(ab * a / 70)),
                        pa,
                    )

    # Vessel sprite — skip pixel art when emoji overlay will be used instead
    if getattr(vessel_def, "icon_mode", "emoji") != "emoji" or not getattr(vessel_def, "icon", None):
        sprite_scale = max(1, CELL // 4)
        _draw_vessel_pixels(vessel_def, scx, scy, sprite_scale, pixels)

    # Golden beacon dot below ship
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            if dx * dx + dy * dy <= 9:
                px, py = scx + dx, scy + dy + 12
                if (px, py) in pixels:
                    pixels[(px, py)] = (255, 215, 0, 255)

    return (scx, scy)


def _draw_title(pixels: dict, current_day: int, stage_name: str,
                total_days: int, remaining: int, vessel_name: str, pal: Palette):
    """Draw title and subtitle text."""
    title = f"DAY {current_day} / {total_days}"
    for px, py, c in draw_text(title, 8, 12, pal.title, scale=2):
        if 0 <= py < PAD_Y:
            pixels[(px, py)] = c

    pct = round(current_day / total_days * 100) if total_days else 0
    sub = f"{stage_name}  {pct}%"
    for px, py, c in draw_text(sub, 8, 40, pal.subtitle, scale=2):
        if 0 <= py < PAD_Y:
            pixels[(px, py)] = c



# ═══════════════════════════════════════════════════════════════
# 主渲染入口
# ═══════════════════════════════════════════════════════════════

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
    textures: dict | None = None,          # kept for compat, ignored
    stages: list | None = None,             # kept for compat, ignored
    palette: Palette | None = None,
) -> bytes:
    """Render the full voyage map as PNG bytes.

    All visual parameters are driven by ``palette``.
    """
    if palette is None:
        palette = get_palette("naval")

    milestones_config = milestones_config or {}

    # Build milestone cell set (for trail-line gaps)
    milestone_cells = set()
    for day, _ in milestones_config.items():
        idx = day - 1
        if 0 <= idx < len(route):
            milestone_cells.add(route[idx])

    # ── Layer 1: background + ocean + grid ──
    pixels = _build_base_map(route, tiles_revealed, palette)

    # ── Layer 2: trail cell overlay ──
    _draw_trail_cells(pixels, route, tiles_revealed, milestone_cells, palette)

    # ── Layer 3: trail line (split at milestones) ──
    _draw_trail_line(pixels, route, tiles_revealed, milestone_cells, palette)

    # ── Layer 4: start marker ──
    _draw_start_marker(pixels, route, palette)

    # ── Layer 5: milestones ──
    _draw_milestones(pixels, route, tiles_revealed, milestones_config, palette)

    # ── Layer 6: finish glow ──
    _draw_finish(pixels, route, total_days, tiles_revealed, palette)

    # ── Layer 7: fog mask ──
    _draw_fog(pixels, route, tiles_revealed, palette)

    # ── Layer 8: vessel + beacon ──
    vessel_center = _draw_vessel(pixels, route, tiles_revealed, vessel_def, palette)

    # ── Layer 9: title ──
    _draw_title(pixels, current_day, stage_name, total_days, remaining,
                getattr(vessel_def, "name", "unknown") if vessel_def else "unknown",
                palette)

    png_bytes = make_png(W, H, lambda x, y: pixels.get((x, y), palette.bg))

    # ── Layer 10: emoji overlay (Pillow) ──
    vessel_icon = getattr(vessel_def, "icon", None) if vessel_def else None
    vessel_icon_mode = getattr(vessel_def, "icon_mode", "emoji") if vessel_def else "emoji"
    if vessel_icon and vessel_center and vessel_icon_mode == "emoji":
        png_bytes = _overlay_emoji(png_bytes, vessel_icon, vessel_center)

    return png_bytes


# ═══════════════════════════════════════════════════════════════
# CanvasRenderer (BaseRenderer implementation)
# ═══════════════════════════════════════════════════════════════

class CanvasRenderer(BaseRenderer):
    """Render the voyage map as a PNG for Kitty-compatible terminals."""

    def is_available(self) -> bool:
        """Check whether the terminal supports Kitty graphics protocol."""
        return kitty_available()

    def render_map(self, data: dict, theme, vessel_def=None) -> bytes:
        """Render the map as PNG bytes.

        Args:
            data: dict from ``MapEngine.build_render_data()``.
            theme: Theme instance (used for palette selection).
            vessel_def: VesselDef or None.

        Returns:
            bytes: PNG image data.
        """
        tiles_revealed = data["tiles_revealed"]
        current_day = tiles_revealed + 1
        remaining = max(0, data["total_days"] - tiles_revealed)

        # Select palette from theme
        theme_name = getattr(theme, "name", "naval") if theme else "naval"
        pal = get_palette(theme_name)

        # Determine stage display name
        from bestman.core.config import get_current_stage as _get_stage
        stage_info = _get_stage(min(current_day, data["total_days"]),
                                {"voyage": {"stages": []}})
        stage_name = theme.stage_display_name(stage_info["name"]) if theme else str(stage_info["name"])

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
            palette=pal,
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

    Preserved for backward compatibility.
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
        palette=get_palette("naval"),
    )


# ── Standalone exported helpers (used by backward-compat stubs) ───

draw_text = draw_text   # re-export from font module
draw_vessel_pixels = _draw_vessel_pixels  # re-export
