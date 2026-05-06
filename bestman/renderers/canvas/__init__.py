"""Canvas PNG renderer package.

Provides:
- CanvasRenderer: BaseRenderer implementation for Kitty protocol terminals
- make_png: raw PNG byte generator
- kitty_available / kitty_display: Kitty graphics protocol helpers
- draw_text / draw_vessel_pixels: pixel art utilities
- render_map: backward-compatible standalone function
- get_palette / NAVAL / CULTIVATION: colour palettes
"""

from bestman.renderers.canvas.font import draw_text  # noqa: F401
from bestman.renderers.canvas.kitty import kitty_available, kitty_display  # noqa: F401
from bestman.renderers.canvas.palette import CULTIVATION, NAVAL, get_palette  # noqa: F401
from bestman.renderers.canvas.png import make_png  # noqa: F401
from bestman.renderers.canvas.renderer import (
    CanvasRenderer,         # noqa: F401
    draw_vessel_pixels,     # noqa: F401
    render_map,             # noqa: F401
)
