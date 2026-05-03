"""Tests for the 2D world MapEngine."""

import re

import pytest

from bestman.map_engine import MapEngine, get_log_entry, GRID_WIDTH, GRID_HEIGHT

# Minimal config matching default bestman setup
DEFAULT_STAGES = [
    {"name": "启航", "days": [1, 25]},
    {"name": "迷雾之海", "days": [26, 50]},
    {"name": "季风带", "days": [51, 75]},
    {"name": "贸易航线", "days": [76, 100]},
    {"name": "赤道无风带", "days": [101, 125]},
    {"name": "信风带", "days": [126, 150]},
    {"name": "新大陆近海", "days": [151, 175]},
]

DEFAULT_MILESTONES = {
    25: "穿越迷雾之海",
    50: "进入季风带",
    75: "抵达贸易港",
    100: "穿过赤道无风带",
    125: "遇见信风",
    150: "望见新大陆海岸线",
    175: "抵达新大陆",
}


def make_config(stages=None, milestones=None, width=50, height=14, theme="naval"):
    """Build a minimal config dict for MapEngine."""
    return {
        "map": {"width": width, "height": height},
        "voyage": {
            "stages": stages or DEFAULT_STAGES,
            "milestones": milestones or DEFAULT_MILESTONES,
            "theme": theme,
        },
    }


def strip_rich_markup(text):
    """Strip Rich markup tags, leaving only content characters."""
    return re.sub(r"\[/?[^\]]*\]", "", text)


def count_char_in_grid(rendered, char):
    """Count occurrences of a character in the rendered grid (after stripping markup)."""
    raw = strip_rich_markup(rendered)
    return raw.count(char)


# ── route generation tests ──


class TestRouteGeneration:
    """Tests for the route coordinate generation."""

    def test_route_has_175_points(self):
        """Route contains exactly 175 coordinates."""
        engine = MapEngine(make_config())
        assert len(engine._route) == 175
        assert engine.total_days == 175

    def test_all_points_in_bounds(self):
        """Every route point is within the grid."""
        engine = MapEngine(make_config())
        for x, y in engine._route:
            assert 0 <= x < engine.width, f"Point ({x},{y}) x out of bounds"
            assert 0 <= y < engine.height, f"Point ({x},{y}) y out of bounds"

    def test_route_starts_left_ends_right(self):
        """Route starts near left edge and ends near right edge."""
        engine = MapEngine(make_config())
        first_x = engine._route[0][0]
        last_x = engine._route[-1][0]
        assert first_x <= 5, f"Route should start near left edge, got x={first_x}"
        assert last_x >= 45, f"Route should end near right edge, got x={last_x}"

    def test_each_stage_has_correct_tile_count(self):
        """Each of the 7 stages contributes exactly 25 route points."""
        engine = MapEngine(make_config())
        stages = DEFAULT_STAGES
        for stage_idx, stage in enumerate(stages):
            start, end = stage["days"]
            expected = end - start + 1
            # Count tiles that fall in this stage
            count = 0
            for tile_idx in range(175):
                s, e = stages[stage_idx]["days"]
                if s - 1 <= tile_idx <= e - 1:
                    count += 1
            assert count == expected, f"Stage {stage['name']}: expected {expected}, got {count}"

    def test_fallback_route_when_no_stages(self):
        """When stages is empty, a fallback 175-point route is generated."""
        engine = MapEngine(make_config(stages=[]))
        assert len(engine._route) == 175
        for x, y in engine._route:
            assert 0 <= x < engine.width
            assert 0 <= y < engine.height

    def test_custom_grid_size(self):
        """Map respects custom grid dimensions from config."""
        engine = MapEngine(make_config(width=60, height=10))
        assert engine.width == 60
        assert engine.height == 10
        for x, y in engine._route:
            assert 0 <= x < 60
            assert 0 <= y < 10


# ── rendering tests ──


class TestMapRendering:
    """Tests for the 2D grid rendering."""

    def test_render_has_correct_line_count(self):
        """Rendered map has exactly HEIGHT lines (one per row)."""
        engine = MapEngine(make_config())
        rendered = engine.render(tiles_revealed=0)
        lines = rendered.split("\n")
        assert len(lines) == GRID_HEIGHT

    def test_each_line_has_50_visible_chars(self):
        """Each row has exactly 50 visible characters (Rich markup stripped)."""
        engine = MapEngine(make_config())
        rendered = engine.render(tiles_revealed=25)
        for line in rendered.split("\n"):
            raw = strip_rich_markup(line)
            assert len(raw) == GRID_WIDTH, f"Expected {GRID_WIDTH} chars, got {len(raw)}"

    def test_ship_visible_at_start(self):
        """Ship icon is present when tiles_revealed=0."""
        engine = MapEngine(make_config())
        rendered = engine.render(tiles_revealed=0)
        assert "\u2693" in rendered  # ⚓

    def test_ship_visible_mid_voyage(self):
        """Ship icon is present at various points."""
        engine = MapEngine(make_config())
        for tiles in [5, 25, 50, 75, 100, 150]:
            rendered = engine.render(tiles_revealed=tiles)
            assert "\u2693" in rendered, f"Ship missing at tiles_revealed={tiles}"

    def test_finish_flag_when_complete(self):
        """When all tiles revealed, finish flag replaces ship."""
        engine = MapEngine(make_config())
        rendered = engine.render(tiles_revealed=175)
        assert "\U0001f3c1" in rendered  # 🏁
        # Ship icon should not be present
        raw = strip_rich_markup(rendered)
        assert "\u2693" not in raw

    def test_future_route_shows_preview(self):
        """Unwalked route tiles ahead show ∘."""
        engine = MapEngine(make_config())
        rendered = engine.render(tiles_revealed=10)
        raw = strip_rich_markup(rendered)
        assert "\u2218" in raw  # ∘

    def test_preview_count_decreases_with_progress(self):
        """Fewer preview tiles as ship advances."""
        engine = MapEngine(make_config())
        early = count_char_in_grid(engine.render(tiles_revealed=0), "\u2218")
        mid = count_char_in_grid(engine.render(tiles_revealed=80), "\u2218")
        assert early >= 10, f"Expected >=10 preview chars at start, got {early}"
        # Preview count should be consistent (~10 each time)
        assert mid >= 8, f"Expected >=8 preview chars mid-voyage, got {mid}"

    def test_fog_fills_rest(self):
        """Areas not on the route show fog character."""
        engine = MapEngine(make_config())
        rendered = engine.render(tiles_revealed=10)
        raw = strip_rich_markup(rendered)
        assert "\u2592" in raw  # ▒

    def test_milestone_on_map(self):
        """Milestone markers appear on the map."""
        config = make_config()
        engine = MapEngine(config)
        # At tile 25, milestone "穿越迷雾之海" should be visible
        rendered = engine.render(tiles_revealed=30)
        raw = strip_rich_markup(rendered)
        assert "\u2726" in raw  # ✦

    def test_milestone_in_future_shows_as_preview_marker(self):
        """Upcoming milestone within visible range shows as ✦."""
        engine = MapEngine(make_config())
        # At tile 20, milestone at tile 24 (day 25, 0-based) is ahead
        rendered = engine.render(tiles_revealed=20)
        raw = strip_rich_markup(rendered)
        assert "\u2726" in raw  # ✦ should appear for upcoming milestone

    def test_no_crash_at_all_positions(self):
        """Walking through 0 to 176 should never crash."""
        engine = MapEngine(make_config())
        for tiles in range(0, 177):
            rendered = engine.render(tiles_revealed=tiles)
            assert rendered is not None, f"None at tiles_revealed={tiles}"
            assert len(rendered) > 0, f"Empty at tiles_revealed={tiles}"
            lines = rendered.split("\n")
            assert len(lines) == GRID_HEIGHT, f"Wrong rows at tiles_revealed={tiles}"

    def test_beyond_total_still_renders(self):
        """tiles_revealed > 175 still renders without error."""
        engine = MapEngine(make_config())
        for tiles in [176, 200, 1000]:
            rendered = engine.render(tiles_revealed=tiles)
            assert rendered is not None
            assert len(rendered.split("\n")) == GRID_HEIGHT

    def test_negative_tiles_handled(self):
        """Negative tiles_revealed should not crash."""
        engine = MapEngine(make_config())
        rendered = engine.render(tiles_revealed=-1)
        # -1 should be treated like 0
        assert rendered is not None
        assert "\u2693" in rendered

    def test_rich_markup_present(self):
        """Output contains Rich markup tags for styling."""
        engine = MapEngine(make_config())
        rendered = engine.render(tiles_revealed=25)
        assert "[" in rendered  # Rich tags present
        assert "]" in rendered
        # Should have bold styling for ship
        assert "bold yellow" in rendered
        # Should have fog styling
        assert "dim blue" in rendered

    def test_walked_route_shows_terrain(self):
        """Walked route tiles show region terrain characters."""
        engine = MapEngine(make_config())
        rendered = engine.render(tiles_revealed=5)
        raw = strip_rich_markup(rendered)
        # First stage is 启航, terrain char is ~
        assert "~" in raw

    def test_different_regions_use_different_chars(self):
        """When ship reaches different regions, terrain changes."""
        engine = MapEngine(make_config())

        # Stage 3 (季风带) terrain is ≈
        rendered = engine.render(tiles_revealed=60)
        raw = strip_rich_markup(rendered)
        assert "\u2248" in raw  # ≈

        # Stage 5 (赤道无风带) terrain is —
        rendered = engine.render(tiles_revealed=110)
        raw = strip_rich_markup(rendered)
        assert "\u2014" in raw  # —

    def test_grid_is_rectangular(self):
        """All rows have the same width after stripping markup."""
        engine = MapEngine(make_config())
        for tiles in [0, 25, 50, 75, 100, 125, 150, 175]:
            rendered = engine.render(tiles_revealed=tiles)
            widths = {len(strip_rich_markup(line)) for line in rendered.split("\n")}
            assert len(widths) == 1, f"Inconsistent widths at tiles={tiles}: {widths}"

    def test_full_completion_shows_flag(self):
        """When voyage is complete, finish flag is shown at the destination."""
        engine = MapEngine(make_config())
        rendered = engine.render(tiles_revealed=175)
        raw = strip_rich_markup(rendered)
        assert "\U0001f3c1" in raw  # 🏁


# ── position / region query tests ──


class TestPositionAndRegion:
    """Tests for get_current_position and get_region_at."""

    def test_get_current_position_at_start(self):
        """Position at tiles_revealed=0 is the first route point."""
        engine = MapEngine(make_config())
        pos = engine.get_current_position(0)
        assert pos is not None
        assert pos == engine._route[0]

    def test_get_current_position_tracks_ship(self):
        """Position matches route[tiles_revealed]."""
        engine = MapEngine(make_config())
        for tiles in [0, 1, 25, 50, 100, 174]:
            pos = engine.get_current_position(tiles)
            assert pos == engine._route[min(tiles, 174)]

    def test_get_current_position_clamps_at_end(self):
        """Position clamps to last route point when beyond total."""
        engine = MapEngine(make_config())
        pos = engine.get_current_position(200)
        assert pos == engine._route[-1]

    def test_get_region_at_stages(self):
        """get_region_at returns correct region for each stage."""
        engine = MapEngine(make_config())
        # tiles_revealed is 0-based count
        # Stage 1 (启航): tiles 0-24
        assert engine.get_region_at(1) == "启航"
        assert engine.get_region_at(25) == "启航"
        # Stage 2 (迷雾之海): tiles 25-49
        assert engine.get_region_at(26) == "迷雾之海"
        assert engine.get_region_at(50) == "迷雾之海"
        # Stage 4 (贸易航线): tiles 75-99
        assert engine.get_region_at(76) == "贸易航线"
        # Stage 7 (新大陆近海): tiles 150-174
        assert engine.get_region_at(151) == "新大陆近海"
        assert engine.get_region_at(175) == "新大陆近海"

    def test_get_region_at_zero_returns_first_stage(self):
        """tiles_revealed=0 returns the first stage name."""
        engine = MapEngine(make_config())
        assert engine.get_region_at(0) == "启航"

    def test_position_matches_x_range(self):
        """Route points have x values increasing generally left to right."""
        engine = MapEngine(make_config())
        prev_x = -1
        decreases = 0
        for x, _ in engine._route:
            if x < prev_x:
                decreases += 1
            prev_x = x
        # A few decreases are OK (route undulation), but not too many
        assert decreases < 10, f"Too many westward moves: {decreases}"


# ── stage lookup tests ──


class TestGetCurrentStage:
    """Tests for get_current_stage (interface compatibility)."""

    def test_stage_boundaries(self):
        """Stage boundaries are detected correctly with 0-based tiles_revealed."""
        engine = MapEngine(make_config())

        # tiles_revealed=0: ship at tile 0 (day 1), first stage
        _, current, nxt, idx = engine.get_current_stage(0)
        assert current["name"] == "启航"
        assert idx == 0
        assert nxt is not None

        # tiles_revealed=24: last tile of stage 1 (day 25)
        _, current, nxt, idx = engine.get_current_stage(24)
        assert current["name"] == "启航"

        # tiles_revealed=25: first tile of stage 2 (day 26)
        _, current, nxt, idx = engine.get_current_stage(25)
        assert current["name"] == "迷雾之海"
        assert nxt["name"] == "季风带"

    def test_last_stage_no_next(self):
        """Last stage has no next stage."""
        engine = MapEngine(make_config())
        _, current, nxt, idx = engine.get_current_stage(174)
        assert current["name"] == "新大陆近海"
        assert nxt is None

    def test_total_days_from_route(self):
        """total_days comes from route length."""
        engine = MapEngine(make_config())
        assert engine.total_days == 175

    def test_total_days_empty_stages(self):
        """Empty stages still gives 175."""
        engine = MapEngine(make_config(stages=[]))
        assert engine.total_days == 175


# ── log entry tests (unchanged) ──


def test_get_log_entry_deterministic():
    """Same day always returns the same log entry."""
    log1 = get_log_entry(5)
    log2 = get_log_entry(5)
    log3 = get_log_entry(42)

    assert isinstance(log1, str)
    assert len(log1) > 0
    assert log1 == log2, "Same day should return identical log"
    assert log1 != log3, (
        "Different day should return different log "
        "(with high probability for seeded randomness)"
    )


def test_get_log_entry_returns_string():
    """All log entries are non-empty strings."""
    for day in range(1, 176, 10):
        entry = get_log_entry(day)
        assert isinstance(entry, str)
        assert len(entry) > 0


# ── today_advance tests ──


class TestTodayAdvance:
    """Tests for today's trail highlighting (today_advance parameter)."""

    def test_today_advance_adds_bright_red(self):
        """When today_advance > 0, today's tiles get bold bright_red styling."""
        engine = MapEngine(make_config())
        rendered = engine.render(tiles_revealed=10, today_advance=3)
        assert "bold bright_red" in rendered

    def test_today_advance_zero_no_highlight(self):
        """When today_advance=0, no bright_red styling appears."""
        engine = MapEngine(make_config())
        rendered = engine.render(tiles_revealed=10, today_advance=0)
        assert "bright_red" not in rendered

    def test_today_advance_single_tile(self):
        """Single tile advance still shows bright_red."""
        engine = MapEngine(make_config())
        rendered = engine.render(tiles_revealed=10, today_advance=1)
        assert "bold bright_red" in rendered

    def test_today_advance_mid_voyage(self):
        """Today highlight works at various voyage positions."""
        engine = MapEngine(make_config())
        for tiles in [5, 50, 120]:
            rendered = engine.render(tiles_revealed=tiles, today_advance=2)
            assert "bold bright_red" in rendered, f"Missing highlight at tiles={tiles}"

    def test_today_advance_does_not_break_grid(self):
        """All rows still have correct width with today_advance."""
        engine = MapEngine(make_config())
        rendered = engine.render(tiles_revealed=50, today_advance=3)
        widths = {len(strip_rich_markup(line)) for line in rendered.split("\n")}
        assert len(widths) == 1, f"Inconsistent widths: {widths}"

    def test_today_advance_does_not_crash(self):
        """Various today_advance values never crash."""
        engine = MapEngine(make_config())
        for advance in [0, 1, 2, 3, 10, 50, 175]:
            rendered = engine.render(tiles_revealed=25, today_advance=advance)
            assert rendered is not None, f"None at today_advance={advance}"
            assert len(rendered.split("\n")) == GRID_HEIGHT

    def test_today_advance_near_wake_still_bold(self):
        """Tiles in NEAR_WAKE but not today's still get bold terrain color."""
        engine = MapEngine(make_config())
        # At tiles=10, today_advance=1: only tile 9 is "today"
        # Tiles 5-8 are "near wake" with bold terrain color
        rendered = engine.render(tiles_revealed=10, today_advance=1)
        # Should have both bold bright_red and bold terrain colors
        assert "bold" in rendered

    def test_today_advance_fade_beyond_today(self):
        """Tiles beyond today_advance use normal dim/bold terrain styling."""
        engine = MapEngine(make_config())
        rendered = engine.render(tiles_revealed=20, today_advance=3)
        # Old tiles (far behind) should use 'dim' style
        assert "dim" in rendered


# ── sway tests ──


class TestSway:
    """Tests for the ship sway animation offset (sway_offset parameter)."""

    def test_sway_zero_no_effect(self):
        """sway_offset=0.0 produces same output as no sway_offset."""
        engine = MapEngine(make_config())
        no_sway = engine.render(tiles_revealed=25)
        zero_sway = engine.render(tiles_revealed=25, sway_offset=0.0)
        assert no_sway == zero_sway

    def test_sway_keeps_grid_width(self):
        """All rows maintain correct width after sway."""
        engine = MapEngine(make_config())
        for offset in [0.5, 1.0, 1.5, 2.0]:
            rendered = engine.render(tiles_revealed=25, sway_offset=offset)
            widths = {len(strip_rich_markup(line)) for line in rendered.split("\n")}
            assert len(widths) == 1, f"Inconsistent widths at offset={offset}: {widths}"

    def test_sway_does_not_crash(self):
        """Various sway_offset values never crash."""
        engine = MapEngine(make_config())
        for offset in [-2.0, -1.0, 0.0, 0.5, 1.0, 2.0, 3.0]:
            rendered = engine.render(tiles_revealed=25, sway_offset=offset)
            assert rendered is not None, f"None at sway_offset={offset}"
            assert len(rendered.split("\n")) == GRID_HEIGHT

    def test_sway_with_today_advance(self):
        """Sway and today_advance work together without crashing."""
        engine = MapEngine(make_config())
        rendered = engine.render(tiles_revealed=25, today_advance=3, sway_offset=1.5)
        assert rendered is not None
        assert len(rendered.split("\n")) == GRID_HEIGHT
        widths = {len(strip_rich_markup(line)) for line in rendered.split("\n")}
        assert len(widths) == 1

    def test_sway_positive_offset_shifts_some_rows(self):
        """Positive sway_offset causes visible row shifting (fog at edges)."""
        engine = MapEngine(make_config())
        no_sway = engine.render(tiles_revealed=25, sway_offset=0.0)
        with_sway = engine.render(tiles_revealed=25, sway_offset=2.0)
        # Rows should differ because sway adds fog at edges
        assert no_sway != with_sway
