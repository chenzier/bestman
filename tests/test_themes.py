"""Tests for theme system."""

import pytest

from bestman.themes import get_theme, register_theme, list_themes
from bestman.themes.base import Theme, TileSet
from bestman.themes.naval import NavalTheme
from bestman.themes.cultivation import CultivationTheme


class TestTileSet:
    """TileSet tests."""

    def test_default_tileset_has_expected_chars(self):
        """Default TileSet has all required characters."""
        ts = TileSet()
        assert ts.ship == "\u2693"     # ⚓
        assert ts.wake == "\u2248"     # ≈
        assert ts.lock == "\U0001f512"  # 🔒
        assert ts.complete == "\u2713"  # ✓
        assert ts.finish == "\U0001f3c1"  # 🏁

    def test_tileset_markup_is_non_empty(self):
        """All markup strings contain their raw character."""
        ts = TileSet()
        for attr_name in dir(ts):
            if attr_name.endswith("_markup"):
                markup = getattr(ts, attr_name)
                assert isinstance(markup, str)
                assert len(markup) > 0


class TestThemeBase:
    """Theme base class tests."""

    def test_base_theme_defaults(self):
        """Base Theme has sensible defaults."""
        theme = Theme()
        assert theme.name == "base"
        assert theme.stage_display_name("任何名字") == "任何名字"
        assert isinstance(theme.tiles, TileSet)

    def test_stage_display_name_with_override(self):
        """stage_display_name uses override when available."""
        theme = Theme(stage_names={"启航": "练气期"})
        assert theme.stage_display_name("启航") == "练气期"
        assert theme.stage_display_name("未知") == "未知"

    def test_completed_bar(self):
        """completed_bar produces full-width markup."""
        theme = Theme()
        bar = theme.completed_bar(25)
        assert len(bar) > 0
        assert theme.tiles.milestone in bar
        assert theme.tiles.bar_fill in bar

    def test_locked_bar(self):
        """locked_bar produces full-width empty markup."""
        theme = Theme()
        bar = theme.locked_bar(25)
        assert len(bar) > 0
        assert theme.tiles.bar_empty in bar

    def test_bar_fill_at_ship_position(self):
        """bar_fill returns ship markup at the correct position."""
        theme = Theme()
        # 3/25 revealed, ship_pos = int(25*3/25) = 3, limited to 24
        result = theme.bar_fill(3, 25, 3, 25)
        assert theme.tiles.ship_markup in result or theme.tiles.ship in result

    def test_bar_fill_wake_behind_ship(self):
        """bar_fill returns wake markup within 3 positions behind ship."""
        theme = Theme()
        # 10/25 revealed, ship_pos = int(25*10/25) = 10
        # wake at positions 7, 8, 9 (ship_pos-3 to ship_pos-1)
        result = theme.bar_fill(8, 25, 10, 25)
        assert theme.tiles.wake_markup in result or theme.tiles.wake in result

    def test_bar_fill_explored_before_wake(self):
        """bar_fill returns fill chars well behind ship."""
        theme = Theme()
        # 10/25 revealed, ship_pos = 10, fill at positions < 7
        result = theme.bar_fill(3, 25, 10, 25)
        assert theme.tiles.bar_fill_markup in result or theme.tiles.bar_fill in result

    def test_bar_fill_unrevealed_ahead(self):
        """bar_fill returns empty chars ahead of ship."""
        theme = Theme()
        # 5/25 revealed, ship_pos = int(25*5/25) = 5
        # position 20 is ahead
        result = theme.bar_fill(20, 25, 5, 25)
        assert theme.tiles.bar_empty_markup in result or theme.tiles.bar_empty in result

    def test_bar_fill_zero_revealed(self):
        """bar_fill with 0 revealed: ship at pos 0, all else empty."""
        theme = Theme()
        result = theme.bar_fill(0, 25, 0, 25)
        assert theme.tiles.ship_markup in result or theme.tiles.ship in result

        result = theme.bar_fill(10, 25, 0, 25)
        assert theme.tiles.bar_empty_markup in result or theme.tiles.bar_empty in result


class TestNavalTheme:
    """Naval theme tests."""

    def test_naval_theme_identity(self):
        """Naval theme has correct name."""
        theme = NavalTheme()
        assert theme.name == "naval"

    def test_naval_theme_tileset(self):
        """Naval theme uses naval tile set with ⚓."""
        theme = NavalTheme()
        assert theme.tiles.ship == "\u2693"

    def test_naval_no_stage_renames(self):
        """Naval theme does not rename stages."""
        theme = NavalTheme()
        assert theme.stage_display_name("迷雾之海") == "迷雾之海"


class TestCultivationTheme:
    """Cultivation theme tests."""

    def test_cultivation_theme_identity(self):
        """Cultivation theme has correct name."""
        theme = CultivationTheme()
        assert theme.name == "cultivation"

    def test_cultivation_tileset_uses_dagger(self):
        """Cultivation uses 🗡️ as ship."""
        theme = CultivationTheme()
        assert theme.tiles.ship == "\U0001f5e1\ufe0f"

    def test_cultivation_stage_renames(self):
        """Cultivation theme renames stages to xianxia cultivation levels."""
        theme = CultivationTheme()
        assert theme.stage_display_name("启航") == "练气期"
        assert theme.stage_display_name("迷雾之海") == "筑基期"
        assert theme.stage_display_name("季风带") == "金丹期"
        assert theme.stage_display_name("贸易航线") == "元婴期"
        assert theme.stage_display_name("赤道无风带") == "化神期"
        assert theme.stage_display_name("信风带") == "炼虚期"
        assert theme.stage_display_name("新大陆近海") == "渡劫期"

    def test_cultivation_milestone_uses_sparkles(self):
        """Cultivation milestone is ✨ not ✦."""
        theme = CultivationTheme()
        assert theme.tiles.milestone == "\u2728"

    def test_cultivation_accent_colour(self):
        """Cultivation uses magenta accent."""
        theme = CultivationTheme()
        assert theme.accent_colour == "magenta"


class TestThemeRegistry:
    """Theme registry tests."""

    def test_get_naval_theme(self):
        """get_theme("naval") returns NavalTheme."""
        theme = get_theme("naval")
        assert isinstance(theme, NavalTheme)
        assert theme.name == "naval"

    def test_get_cultivation_theme(self):
        """get_theme("cultivation") returns CultivationTheme."""
        theme = get_theme("cultivation")
        assert isinstance(theme, CultivationTheme)
        assert theme.name == "cultivation"

    def test_get_unknown_theme_falls_back(self):
        """Unknown theme name falls back to naval."""
        theme = get_theme("nonexistent_theme")
        assert isinstance(theme, NavalTheme)
        assert theme.name == "naval"

    def test_list_themes(self):
        """list_themes returns all registered theme names."""
        themes = list_themes()
        assert "naval" in themes
        assert "cultivation" in themes

    def test_register_custom_theme(self):
        """Custom themes can be registered."""
        custom = Theme(name="custom", stage_names={"test": "custom_test"})
        register_theme(custom)
        assert "custom" in list_themes()
        retrieved = get_theme("custom")
        assert retrieved.name == "custom"
        assert retrieved.stage_display_name("test") == "custom_test"
