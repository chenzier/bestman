"""Naval theme — default nautical adventure theme."""

from dataclasses import dataclass, field

from bestman.themes.base import Theme, TextureDef, TileSet, VesselDef


@dataclass
class NavalTileSet(TileSet):
    """Standard nautical tile set."""

    # Use defaults from base — naval is the canonical theme
    pass


# ── 海洋纹理 ─────────────────────────────────────────────────────
# Each texture is an 18×18 pixel matrix designed to fill the interior
# of a 20×20 map cell (1 px border on each side is the grid line).

# Palette key:
#   A = primary base    B = secondary / detail    C = highlight
#   . = transparent

_NAVAL_TEXTURES = {
    # ── calm : 青蓝底 + 浅横纹（启航、赤道无风带） ──────────
    "calm": TextureDef(
        name="calm",
        pixels=[
            "AAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAA",
            "BBBBBBBBBBBBBBBBBB",
            "BBBBBBBBBBBBBBBBBB",
            "AAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAA",
            "BBBBBBBBBBBBBBBBBB",
            "BBBBBBBBBBBBBBBBBB",
            "AAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAA",
            "BBBBBBBBBBBBBBBBBB",
            "BBBBBBBBBBBBBBBBBB",
        ],
        palette={
            "A": (18, 88, 100, 255),   # deep cyan-blue
            "B": (28, 118, 126, 255),  # lighter cyan stripe
        },
    ),

    # ── ripple : 细密波纹深浅交错（贸易航线、新大陆近海） ──
    "ripple": TextureDef(
        name="ripple",
        pixels=[
            "ABABABABABABABABAB",
            "BABABABABABABABABA",
            "ABABABABABABABABAB",
            "BABABABABABABABABA",
            "ABABABABABABABABAB",
            "BABABABABABABABABA",
            "ABABABABABABABABAB",
            "BABABABABABABABABA",
            "ABABABABABABABABAB",
            "BABABABABABABABABA",
            "ABABABABABABABABAB",
            "BABABABABABABABABA",
            "ABABABABABABABABAB",
            "BABABABABABABABABA",
            "ABABABABABABABABAB",
            "BABABABABABABABABA",
            "ABABABABABABABABAB",
            "BABABABABABABABABA",
        ],
        palette={
            "A": (22, 100, 110, 255),  # slightly darker
            "B": (32, 128, 126, 255),  # slightly lighter
        },
    ),

    # ── wave : 深蓝底 + 白浪尖（季风带、信风带） ──────────
    "wave": TextureDef(
        name="wave",
        pixels=[
            "AAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAA",
            "AAAAAAAABAAAAAAAAA",
            "AAAAAAABBBAAAAAAA",
            "AAAAAABBBBBAAAAAA",
            "AAAAABBBBBBBAAAAA",
            "AAAABBBBBCCBBAAAA",
            "AAAABBBBCCCCBBAAA",
            "AAABBBBCCCCCCBBAA",
            "AAABBBCCCCCCBBBAA",
            "AAABBBCCCCCCBBBAA",
            "AAABBCCBBBBBCBAA",
            "AAAABBBBBBBBBBAAA",
            "AAAAABBBBBBBBAAAA",
            "AAAAAABBBBBAAAAAA",
            "AAAAAAABBBAAAAAAA",
            "AAAAAAAAAAAAAAAAAA",
        ],
        palette={
            "A": (10, 56, 72, 255),    # deep navy
            "B": (18, 88, 104, 255),   # mid blue
            "C": (200, 225, 240, 255), # white foam crest
        },
    ),

    # ── foam : 浅底 + 白散点（迷雾之海） ──────────────────
    "foam": TextureDef(
        name="foam",
        pixels=[
            "A.A..A...A.A.A...A",
            "..A...A.A...A.A...",
            "A...A.A.A...A...A.",
            ".A.A...A...A.A.A..",
            "A...A...A.A...A...",
            "..A.A.A...A...A.A.",
            "A...A...A...A.A...",
            ".A...A.A.A...A...A",
            "A.A...A...A.A.A...",
            "..A...A.A...A...A.",
            "A...A...A...A...A.",
            ".A.A.A...A.A...A..",
            "A...A.A...A...A.A.",
            "..A...A...A.A.A...",
            "A.A...A...A...A...",
            "..A.A...A...A.A.A.",
            "A...A...A.A...A...",
            ".A...A.A...A...A..",
        ],
        palette={
            "A": (40, 124, 130, 255),  # pale teal
            "B": (180, 220, 235, 255), # white bubble (used via '.' as transparent)
            ".": (40, 124, 130, 255),  # same as A — background
        },
    ),

    # ── wake : 白底 + 蓝纹（船后尾迹专用） ──────────────
    "wake": TextureDef(
        name="wake",
        pixels=[
            "BBAAAAAABBAAAAAAAA",
            "BBBAAAABBBAAAAAAA",
            "BBAAAAAABBAAAAAAAA",
            "BBBAAAAABBBAAAAAA",
            "BBBBAAAAABBBBAAAA",
            "BBAAAAAAAABBAAAAA",
            "BBBAAAAAABBBBAAAA",
            "BBBBAAAAAABBBAAAA",
            "ABBAAAAAABBBBAAAA",
            "AABBBAAAAAABBBBAA",
            "AABBBBAAAAAABBAAA",
            "AABBBAAAAAAAABBAA",
            "AAABBBAAAAAABBBAA",
            "AAABBBBAAAAAABBBA",
            "AAAABBBAAAAAABBBB",
            "AAAABBBBAAAAAABBA",
            "AAAAABBBBAAAAABBA",
            "AAAAAABBBAAAAAABB",
        ],
        palette={
            "A": (210, 230, 240, 255), # white/light water
            "B": (28, 108, 128, 255),  # blue wake streak
        },
    ),
}

# ── 阶段 → 纹理名映射 ──────────────────────────────────────────

_STAGE_TEXTURE_MAP = {
    "启航": "calm",
    "迷雾之海": "foam",
    "季风带": "wave",
    "贸易航线": "ripple",
    "赤道无风带": "calm",
    "信风带": "wave",
    "新大陆近海": "ripple",
}


def get_stage_texture(stage_name: str) -> str:
    """Return the texture name for a given stage name.

    Args:
        stage_name: Chinese stage name (e.g. "启航", "季风带").

    Returns:
        Texture name string (e.g. "calm", "wave"), or "calm" as fallback.
    """
    return _STAGE_TEXTURE_MAP.get(stage_name, "calm")


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
    textures: dict = field(default_factory=lambda: dict(_NAVAL_TEXTURES))
