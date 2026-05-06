"""Colour palettes for the Canvas PNG renderer.

Each palette is a flat dict of colour keys → (R, G, B, A) tuples.
The renderer uses palette values for all visual elements — switching
themes is just swapping the palette dict.

Palettes:
    naval: default oceanic theme (dark teal ocean, gold trails)
    cultivation: xianxia alternative (ink/ash grey, bamboo green)
"""

from dataclasses import dataclass


@dataclass
class Palette:
    """A colour palette for the Canvas PNG renderer."""

    bg: tuple                         # background colour
    ocean: list[tuple]                # list of ocean cell colours (random pick)
    mist: tuple                       # unrevealed fog colour
    grid: tuple                       # grid line colour

    trail_cell_add: tuple             # RGB additive overlay for trail cells
    trail_line_outer: tuple           # outer glow of the trail line
    trail_line_inner: tuple           # inner solid core of the trail line

    start_ring: tuple                 # start marker ring
    start_label: tuple                # start marker label colour

    milestone_glow: tuple             # milestone outer glow
    milestone_ring: tuple             # milestone ring circle
    milestone_star: tuple             # milestone star / centre
    milestone_label: tuple            # milestone name label

    finish_glow: tuple                # finish marker glow

    vessel_glow_add: tuple            # vessel glow additive (R,G,B)

    title: tuple                      # title text colour
    subtitle: tuple                   # subtitle text colour
    legend: tuple                     # legend label colour
    legend_border: tuple              # legend swatch border


# ── Naval (default) ────────────────────────────────────────────────

NAVAL = Palette(
    bg=(8, 16, 24, 255),
    ocean=[
        (21, 104, 112, 255),
        (26, 128, 120, 255),
        (14, 92, 96, 255),
        (18, 80, 88, 255),
        (16, 96, 104, 255),
    ],
    mist=(22, 38, 54, 255),
    grid=(20, 60, 80, 80),

    trail_cell_add=(48, 32, 0),              # added per-pixel to ocean
    trail_line_outer=(255, 200, 60, 60),     # wide semi-transparent glow
    trail_line_inner=(255, 215, 40, 210),    # bright gold core

    start_ring=(136, 204, 255, 255),
    start_label=(136, 204, 255, 255),

    milestone_glow=(255, 215, 0, 90),
    milestone_ring=(255, 215, 0, 255),
    milestone_star=(255, 255, 255, 255),
    milestone_label=(200, 180, 40, 255),

    finish_glow=(200, 160, 20, 100),

    vessel_glow_add=(100, 75, 20),

    title=(78, 201, 176, 255),
    subtitle=(86, 156, 214, 255),
    legend=(122, 138, 154, 255),
    legend_border=(60, 80, 100, 100),
)


# ── Cultivation (xiānxiá) ─────────────────────────────────────────

CULTIVATION = Palette(
    bg=(12, 12, 16, 255),
    ocean=[
        (28, 32, 36, 255),
        (32, 38, 34, 255),
        (24, 28, 38, 255),
        (30, 34, 32, 255),
    ],
    mist=(18, 20, 26, 255),
    grid=(30, 35, 45, 50),

    trail_cell_add=(32, 36, 20),
    trail_line_outer=(180, 190, 120, 60),
    trail_line_inner=(200, 210, 130, 200),

    start_ring=(160, 200, 160, 255),
    start_label=(160, 200, 160, 255),

    milestone_glow=(180, 190, 100, 90),
    milestone_ring=(190, 200, 110, 255),
    milestone_star=(255, 255, 240, 255),
    milestone_label=(170, 185, 100, 255),

    finish_glow=(180, 190, 90, 100),

    vessel_glow_add=(80, 90, 50),

    title=(150, 190, 150, 255),
    subtitle=(120, 150, 140, 255),
    legend=(100, 110, 120, 255),
    legend_border=(50, 60, 70, 100),
)


# ── Convenience ────────────────────────────────────────────────────

def get_palette(theme_name: str) -> Palette:
    """Return the palette for a given theme name."""
    if theme_name == "cultivation":
        return CULTIVATION
    return NAVAL
