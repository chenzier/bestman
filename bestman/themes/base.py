"""Theme system base classes.

A Theme defines the visual vocabulary for the segmented map:
characters, colours, stage names, narrative tone, and vessel pixel art.
"""

from dataclasses import dataclass, field


@dataclass
class VesselDef:
    """A vessel (载具) definition with pixel art and metadata.

    The pixel art is defined as a list of strings (one per row), where
    each character maps to a colour in the palette dict.  Characters
    not in the palette are treated as transparent.

    Example::

        VesselDef(
            name="初阶帆船", icon="⛵",
            pixels=['..BB..', '.BWWB.', '..BB..'],
            palette={'B': (74,32,16,255), 'W': (255,255,240,255)},
            price=0, theme="naval",
        )
    """

    name: str
    icon: str                       # emoji identifier
    pixels: list[str]               # pixel art row strings ("BBWWBB" format)
    palette: dict[str, tuple]       # char → (R, G, B, A)
    theme: str = "naval"
    price: int = 0
    width: int = 12
    height: int = 9


@dataclass
class TextureDef:
    """A texture pattern for filling map cells (仿 VesselDef.pixels).

    The texture is defined as a list of strings (one per row), where
    each character maps to a colour in the palette dict.  Characters
    not in the palette are treated as transparent.
    """

    name: str                       # "calm" / "ripple" / "wave" / "foam" / "wake"
    pixels: list[str]               # character matrix
    palette: dict[str, tuple]       # char → (R,G,B,A)


@dataclass
class TileSet:
    """Visual tile characters and Rich markup for a theme."""

    # Map bar characters
    ship: str = "\u2693"            # ⚓
    ship_markup: str = "[bold yellow]\u2693[/]"
    explored: str = "~"             # explored tile
    explored_markup: str = "[cyan]~[/]"
    wake: str = "\u2248"            # ≈ wake
    wake_markup: str = "[bold cyan]\u2248[/]"
    hidden_dark: str = "\u2593"     # ▓
    hidden_dark_markup: str = "[dim blue]\u2593[/]"
    hidden_light: str = "\u2591"    # ░
    hidden_light_markup: str = "[dim blue]\u2591[/]"
    milestone: str = "\u2726"       # ✦
    milestone_markup: str = "[bold magenta]\u2726[/]"
    milestone_dim: str = "\u2726"   # ✦
    milestone_dim_markup: str = "[dim magenta]\u2726[/]"
    finish: str = "\U0001f3c1"      # 🏁
    finish_markup: str = "[bold green]\U0001f3c1[/]"

    # Segment markers (new in v0.3)
    lock: str = "\U0001f512"        # 🔒
    lock_markup: str = "[dim]\U0001f512[/]"
    complete: str = "\u2713"        # ✓
    complete_markup: str = "[bold green]\u2713[/]"

    # Bar fill chars
    bar_fill: str = "\u2550"        # ═
    bar_fill_markup: str = "[green]\u2550[/]"
    bar_empty: str = "\u2591"       # ░
    bar_empty_markup: str = "[dim]\u2591[/]"


@dataclass
class Theme:
    """A visual/narrative theme for the voyage.

    Subclass and override to create new themes.
    """

    name: str = "base"
    tiles: TileSet = field(default_factory=TileSet)

    # Stage name overrides (maps config stage name -> themed name)
    stage_names: dict = field(default_factory=dict)

    # Colour hints for CLI rendering
    accent_colour: str = "cyan"
    highlight_colour: str = "bold yellow"

    # Narrative prefix for LLM prompts (empty = no override)
    narrative_prefix: str = ""

    # Vessel (载具) definitions keyed by vessel ID
    vessels: dict = field(default_factory=dict)

    # Texture definitions keyed by texture name ("calm", "ripple", …)
    textures: dict = field(default_factory=dict)

    def stage_display_name(self, config_name: str) -> str:
        """Get themed display name for a stage, with fallback to config name."""
        return self.stage_names.get(config_name, config_name)

    def bar_fill(self, position: int, width: int, revealed: int, stage_tiles: int):
        """Generate a single bar character with markup for the current stage.

        Args:
            position: 0-based position in the bar.
            width: total bar width.
            revealed: number of tiles revealed in this stage.
            stage_tiles: total tiles in this stage.

        Returns:
            Rich markup string for this bar position.
        """
        # Calculate ship position
        if stage_tiles <= 0:
            ship_pos = 0
        else:
            ship_pos = min(width - 1, int(width * revealed / stage_tiles))

        if position < ship_pos - 3:
            return self.tiles.bar_fill_markup
        elif position < ship_pos:
            return self.tiles.wake_markup
        elif position == ship_pos:
            return self.tiles.ship_markup
        else:
            return self.tiles.bar_empty_markup

    def completed_bar(self, width: int) -> str:
        """Render a completed stage bar."""
        return self.tiles.milestone_markup + self.tiles.bar_fill_markup * (width - 1)

    def locked_bar(self, width: int) -> str:
        """Render a locked stage bar."""
        return self.tiles.bar_empty_markup * width
