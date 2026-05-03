"""Naval theme — default nautical adventure theme."""

from dataclasses import dataclass, field

from bestman.themes.base import Theme, TileSet


@dataclass
class NavalTileSet(TileSet):
    """Standard nautical tile set."""

    # Use defaults from base — naval is the canonical theme
    pass


@dataclass
class NavalTheme(Theme):
    """Classical nautical voyage theme."""

    name: str = "naval"
    tiles: TileSet = field(default_factory=NavalTileSet)
    accent_colour: str = "cyan"
    highlight_colour: str = "bold yellow"
    narrative_prefix: str = "你是一艘古典帆船的船长，正在横渡大洋。"
