"""Cultivation (修仙) theme — xianxia-inspired voyage."""

from dataclasses import dataclass, field

from bestman.themes.base import Theme, TileSet


@dataclass
class CultivationTileSet(TileSet):
    """Xianxia cultivation tile set with Chinese cultivation imagery."""

    ship: str = "\U0001f5e1\ufe0f"       # 🗡️
    ship_markup: str = "[bold yellow]\U0001f5e1\ufe0f[/]"
    milestone: str = "\u2728"             # ✨
    milestone_markup: str = "[bold magenta]\u2728[/]"
    milestone_dim: str = "\u2728"         # ✨
    milestone_dim_markup: str = "[dim magenta]\u2728[/]"
    finish: str = "\U0001f451"            # 👑
    finish_markup: str = "[bold yellow]\U0001f451[/]"
    wake: str = "\U0001f4a8"              # 💨
    wake_markup: str = "[bold cyan]\U0001f4a8[/]"

    # Bar styling
    bar_fill: str = "\u2501"              # ━
    bar_fill_markup: str = "[cyan]\u2501[/]"
    bar_empty: str = "\u2592"             # ▒
    bar_empty_markup: str = "[dim]\u2592[/]"


@dataclass
class CultivationTheme(Theme):
    """Xianxia cultivation voyage theme.

    Re-flavours the nautical journey as a cultivator's path to immortality.
    """

    name: str = "cultivation"
    tiles: TileSet = field(default_factory=CultivationTileSet)
    accent_colour: str = "magenta"
    highlight_colour: str = "bold yellow"

    stage_names: dict = field(default_factory=lambda: {
        "启航": "练气期",
        "迷雾之海": "筑基期",
        "季风带": "金丹期",
        "贸易航线": "元婴期",
        "赤道无风带": "化神期",
        "信风带": "炼虚期",
        "新大陆近海": "渡劫期",
    })

    narrative_prefix: str = "你是一位修仙者，正在修炼之路上前行。"
