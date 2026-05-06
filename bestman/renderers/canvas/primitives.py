"""Low-level drawing primitives for the Canvas PNG renderer.

Operates directly on a pixel dict ``{(x, y): (R, G, B, A)}``.
All functions mutate `pixels` in place.
"""

import math


def draw_line(pixels: dict, x1: int, y1: int, x2: int, y2: int, color: tuple):
    """Bresenham line with alpha blending.

    Overlays `color` onto existing pixels using its alpha channel.
    Pixels not yet in the dict are created.
    """
    r, g, b, a = color
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    sx = 1 if x1 < x2 else -1
    sy = 1 if y1 < y2 else -1
    err = dx - dy
    cx, cy = x1, y1

    while True:
        if (cx, cy) in pixels:
            pr, pg, pb, pa = pixels[(cx, cy)]
            aa = a / 255.0
            pixels[(cx, cy)] = (
                int(pr * (1 - aa) + r * aa),
                int(pg * (1 - aa) + g * aa),
                int(pb * (1 - aa) + b * aa),
                max(pa, a),
            )
        else:
            pixels[(cx, cy)] = color

        if cx == x2 and cy == y2:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            cx += sx
        if e2 < dx:
            err += dx
            cy += sy


def draw_ring(pixels: dict, cx: int, cy: int, inner_r: float, outer_r: float, color: tuple):
    """Draw a ring (hollow circle) centred at (cx, cy).

    Pixels in the range ``inner_r <= distance < outer_r`` are set to
    `color`.  Useful for start markers and milestone borders.
    """
    r, g, b, a = color
    ir = math.ceil(inner_r)
    oR = math.ceil(outer_r)
    for dy in range(-oR, oR + 1):
        for dx in range(-oR, oR + 1):
            d = math.sqrt(dx * dx + dy * dy)
            if inner_r <= d < outer_r:
                px, py = cx + dx, cy + dy
                pixels[(px, py)] = (r, g, b, a)


def draw_glow(pixels: dict, cx: int, cy: int, radius: float, color: tuple):
    """Draw a radial glow (additive blending, fading with distance).

    ``color`` is added to existing pixel values proportionally to
    ``1 - distance / radius``.
    """
    r, g, b, a = color
    # max alpha used per pixel; scaled by distance
    for dy in range(-int(radius) - 1, int(radius) + 2):
        for dx in range(-int(radius) - 1, int(radius) + 2):
            d = math.sqrt(dx * dx + dy * dy)
            if d < radius:
                px, py = cx + dx, cy + dy
                frac = 1.0 - d / radius if radius > 0 else 0.0
                # Effective additive alpha
                ea = int(a * frac)
                if ea <= 0:
                    continue
                aa = ea / 255.0
                if (px, py) in pixels:
                    pr, pg, pb, pa = pixels[(px, py)]
                    pixels[(px, py)] = (
                        min(255, pr + int(r * aa)),
                        min(255, pg + int(g * aa)),
                        min(255, pb + int(b * aa)),
                        pa,
                    )
                else:
                    pixels[(px, py)] = (r, g, b, ea)


def draw_cross_star(pixels: dict, cx: int, cy: int, size: int, color: tuple):
    """Draw a 4-point cross star (diamond shape) centred at (cx, cy)."""
    r, g, b, a = color
    for dy in range(-size, size + 1):
        for dx in range(-size, size + 1):
            if abs(dx) + abs(dy) <= size and abs(abs(dx) - abs(dy)) <= max(1, size // 3):
                px, py = cx + dx, cy + dy
                pixels[(px, py)] = (r, g, b, a)
