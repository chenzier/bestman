"""Base renderer interface and shared data structures."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class BaseRenderer(ABC):
    """Abstract base for map renderers.

    Each concrete renderer produces a different output format
    (Rich text, PNG bytes, HTML, etc.) from the same render data.
    """

    @abstractmethod
    def render_map(self, data: dict, theme, vessel_def=None) -> Any:
        """Render a voyage map.

        Args:
            data: dict from ``MapEngine.build_render_data()``.
            theme: Theme instance (e.g. NavalTheme).
            vessel_def: VesselDef or None.

        Returns:
            Renderer-specific output (str, bytes, etc.).
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether this renderer can be used in the current environment.

        Returns:
            bool: True if the renderer's dependencies are available.
        """
        ...
