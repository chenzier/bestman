"""bestman renderers — 地图渲染后端。

Provides:
- BaseRenderer: ABC for renderer backends
- AsciiRenderer: Rich markup text renderer
- CanvasRenderer: Kitty PNG renderer
"""

from bestman.renderers.ascii import AsciiRenderer  # noqa: F401
from bestman.renderers.base import BaseRenderer  # noqa: F401
from bestman.renderers.canvas import CanvasRenderer  # noqa: F401
