"""Theme registry for bestman.

Usage:
    from bestman.themes import get_theme
    theme = get_theme("naval")        # -> NavalTheme
    theme = get_theme("cultivation")  # -> CultivationTheme
"""

from bestman.themes.base import Theme
from bestman.themes.naval import NavalTheme
from bestman.themes.cultivation import CultivationTheme

# Registry of available themes
_THEMES: dict[str, Theme] = {
    "naval": NavalTheme(),
    "cultivation": CultivationTheme(),
}


def get_theme(name: str) -> Theme:
    """Get a theme by name. Falls back to naval if unknown."""
    return _THEMES.get(name, _THEMES["naval"])


def register_theme(theme: Theme):
    """Register a custom theme."""
    _THEMES[theme.name] = theme


def list_themes() -> list[str]:
    """List all registered theme names."""
    return list(_THEMES.keys())
