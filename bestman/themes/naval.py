"""Naval theme — default nautical adventure theme."""

from dataclasses import dataclass, field

from bestman.themes.base import Theme, TileSet, VesselDef


@dataclass
class NavalTileSet(TileSet):
    """Standard nautical tile set."""

    # Use defaults from base — naval is the canonical theme
    pass


# ── 航海主题载具像素画 ──────────────────────────────────────────

_NAVAL_VESSELS = {
    "schooner": VesselDef(
        name="初阶帆船", icon="⛵",
        pixels=[
            '..BBBBB....',
            '.BWWWWWB...',
            '.BMWWWMB...',
            'BBBBBBBBBB.',
            'BBGBBGBBBB.',
            '.BBBBBBBBB.',
            '..BBBBB....',
        ],
        palette={
            'B': (74, 32, 16, 255),
            'W': (255, 255, 240, 255),
            'M': (160, 96, 48, 255),
            'G': (255, 215, 0, 255),
        },
        theme="naval", price=0,
    ),
    "dragon": VesselDef(
        name="龙头战船", icon="🐉",
        pixels=[
            '...RRR......',
            '.RRRRRR.....',
            'ROOOOOOR....',
            'RODDDDDOR...',
            'ODDGGGGDDO..',
            '.RDDDDDDR...',
            '..RRRRR.....',
        ],
        palette={
            'R': (200, 32, 32, 255),
            'O': (240, 80, 16, 255),
            'D': (112, 32, 16, 255),
            'G': (255, 215, 0, 255),
        },
        theme="naval", price=300,
    ),
    "ghost": VesselDef(
        name="幽灵船", icon="👻",
        pixels=[
            '..PPPPP...',
            '.PPPPPPP..',
            'PPPGPPGPP.',
            'PPPPPPPPP.',
            '.PPPPPPPPP',
            '..PPPPP...',
        ],
        palette={
            'P': (56, 24, 80, 255),
            'G': (136, 48, 160, 255),
        },
        theme="naval", price=500, width=10, height=6,
    ),
}


@dataclass
class NavalTheme(Theme):
    """Classical nautical voyage theme."""

    name: str = "naval"
    tiles: TileSet = field(default_factory=NavalTileSet)
    accent_colour: str = "cyan"
    highlight_colour: str = "bold yellow"
    narrative_prefix: str = "你是一艘古典帆船的船长，正在横渡大洋。"
    vessels: dict = field(default_factory=lambda: dict(_NAVAL_VESSELS))
