"""Tests for segmented MapEngine with theme support."""

import re

import pytest

from bestman.map_engine import MapEngine, get_log_entry, BAR_WIDTH

# Sample stages matching default config (1-based days)
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
    24: "穿越迷雾之海",  # 0-based: day 25
    49: "进入季风带",     # day 50
}


def strip_rich_markup(text: str) -> str:
    """Strip Rich markup tags, leaving only the content characters."""
    return re.sub(r"\[/?[^\]]*\]", "", text)


# ── segmented map rendering tests ──


class TestSegmentedRendering:
    """Tests for the new segmented map rendering."""

    def test_initial_render_shows_ship_at_position_zero(self):
        """tiles_revealed=0: ship at start of first stage, next stage locked."""
        engine = MapEngine(stages=DEFAULT_STAGES, theme="naval")
        rendered = engine.render(tiles_revealed=0)
        raw = strip_rich_markup(rendered)

        # Should show first stage and second stage (locked), not more
        lines = rendered.split("\n")
        assert len(lines) == 2, f"Expected 2 rows (current + next), got {len(lines)}"
        assert "启航" in raw
        assert "迷雾之海" in raw
        assert "季风带" not in raw  # third stage should be hidden
        assert "\u2693" in raw, f"Should show ship icon, got: {raw[:80]}"
        assert "\U0001f512" in raw, f"Should show lock icon on next stage, got: {raw[:80]}"
        # First stage shows 0/N
        assert "0/25" in raw

    def test_progress_shows_revealed_count(self):
        """After 5 reveals, stage shows 5/25."""
        engine = MapEngine(stages=DEFAULT_STAGES, theme="naval")
        rendered = engine.render(tiles_revealed=5)
        raw = strip_rich_markup(rendered)

        assert "5/25" in raw
        assert "\u2693" in raw  # ship icon visible
        # Ship should still be in first stage
        assert "启航" in raw

    def test_stage_completed_shows_checkmark(self):
        """When a stage is fully revealed, it shows ✓ 完成."""
        engine = MapEngine(stages=DEFAULT_STAGES, theme="naval")
        # Stage 1 ends at day 25, so tiles_revealed=25 means stage 1 is done
        # (ship is now at position 25 which is the start of stage 2)
        rendered = engine.render(tiles_revealed=25)
        raw = strip_rich_markup(rendered)

        assert "\u2713" in raw, f"Should show checkmark for completed stage: {raw[:120]}"
        # First stage should show "完成"
        assert "完成" in raw

    def test_stage_transition_shows_next_stage_as_current(self):
        """When moving to second stage, it becomes current."""
        engine = MapEngine(stages=DEFAULT_STAGES, theme="naval")
        # Day 26 (tiles_revealed=25) is start of stage 2
        rendered = engine.render(tiles_revealed=26)
        raw = strip_rich_markup(rendered)

        # Stage 1 should be completed
        assert "\u2713" in raw
        # Stage 2 should be current (has ship)
        assert "\u2693" in raw
        # Stage 3 should be locked
        assert "\U0001f512" in raw

    def test_only_shows_completed_current_and_next(self):
        """Only 3 stages at most: completed + current + next."""
        engine = MapEngine(stages=DEFAULT_STAGES, theme="naval")
        # Stage 3 is current
        rendered = engine.render(tiles_revealed=51)
        raw = strip_rich_markup(rendered)

        lines = rendered.split("\n")
        # Should show stage 2 (completed), stage 3 (current), stage 4 (next)
        assert len(lines) == 3, f"Expected 3 rows, got {len(lines)}"
        for name in ["季风带", "贸易航线"]:
            assert name in raw
        # Stage 5 (赤道无风带) should NOT be shown
        assert "赤道无风带" not in raw

    def test_last_stage_no_next_locked(self):
        """On the last stage, only completed + current (no next)."""
        engine = MapEngine(stages=DEFAULT_STAGES, theme="naval")
        # Stage 7 (last stage) is current
        rendered = engine.render(tiles_revealed=151)
        raw = strip_rich_markup(rendered)

        lines = rendered.split("\n")
        # Should show most recent completed + current, no next
        assert len(lines) == 2, f"Expected 2 rows, got {len(lines)}"
        # No lock icon
        assert "\U0001f512" not in raw

    def test_full_completion_renders_all_completed(self):
        """When all 175 tiles revealed, map shows all stages completed."""
        engine = MapEngine(stages=DEFAULT_STAGES, theme="naval")
        rendered = engine.render(tiles_revealed=175)
        raw = strip_rich_markup(rendered)

        # At full completion, final stage shows completed status and all rows have checkmarks
        lines = rendered.split("\n")
        assert len(lines) == 2, f"Expected 2 rows (completed + final), got {len(lines)}"
        # Both rows should show checkmarks (completed stage + current/final completed)
        assert raw.count("\u2713") >= 2, f"Expected at least 2 checkmarks, got {raw.count(chr(0x2713))}"
        # Final stage name should be present
        assert "新大陆近海" in raw

    def test_stage_with_single_row_stages(self):
        """Custom stages also work for different layout."""
        stages = [
            {"name": "Phase A", "days": [1, 50]},
            {"name": "Phase B", "days": [51, 100]},
        ]
        engine = MapEngine(stages=stages, theme="naval")
        rendered = engine.render(tiles_revealed=60)
        raw = strip_rich_markup(rendered)

        lines = rendered.split("\n")
        assert len(lines) == 2
        assert "Phase A" in raw
        assert "Phase B" in raw
        # Phase A completed
        assert "\u2713" in raw

    def test_empty_stages_graceful(self):
        """Empty stages list returns a dim message."""
        engine = MapEngine(stages=[], theme="naval")
        rendered = engine.render(tiles_revealed=0)
        assert "No stages configured" in rendered

    def test_no_crash_at_all_positions(self):
        """Walking through 0→175 should not crash."""
        engine = MapEngine(stages=DEFAULT_STAGES, theme="naval")
        for tiles in range(0, 176):
            rendered = engine.render(tiles_revealed=tiles)
            assert rendered is not None, f"Failed at tiles_revealed={tiles}"
            assert len(rendered) > 0
        # Beyond total should also work
        for tiles in [176, 200, 1000]:
            rendered = engine.render(tiles_revealed=tiles)
            assert rendered is not None

    def test_bar_width_is_consistent(self):
        """All stage bars should be BAR_WIDTH characters of content (after stripping markup)."""
        engine = MapEngine(stages=DEFAULT_STAGES, theme="naval")
        for tiles in [0, 5, 25, 50, 100, 175]:
            rendered = engine.render(tiles_revealed=tiles)
            for line in rendered.split("\n"):
                raw = strip_rich_markup(line)
                # Each line contains the stage name and a bar
                assert len(raw) > 10, f"Line too short at tiles={tiles}: {raw}"
                # Bar must be at least BAR_WIDTH characters of visible content
                visible_content = raw.strip()
                assert len(visible_content) >= BAR_WIDTH


# ── theme tests ──


class TestThemeSwitching:
    """Tests for theme switching between naval and cultivation."""

    def test_naval_theme_uses_anchor(self):
        """Naval theme shows ⚓ ship icon."""
        engine = MapEngine(stages=DEFAULT_STAGES, theme="naval")
        rendered = engine.render(tiles_revealed=5)
        assert "\u2693" in rendered  # ⚓

    def test_cultivation_theme_uses_dagger(self):
        """Cultivation theme shows 🗡️ instead of ⚓."""
        engine = MapEngine(stages=DEFAULT_STAGES, theme="cultivation")
        rendered = engine.render(tiles_revealed=5)
        assert "\U0001f5e1\ufe0f" in rendered  # 🗡️

    def test_cultivation_theme_has_renamed_stages(self):
        """Cultivation theme renames stages to xianxia terms."""
        engine = MapEngine(stages=DEFAULT_STAGES, theme="cultivation")
        rendered = engine.render(tiles_revealed=5)
        raw = strip_rich_markup(rendered)
        assert "练气期" in raw
        assert "筑基期" in raw

    def test_unknown_theme_falls_back_to_naval(self):
        """An unknown theme name falls back to naval."""
        engine = MapEngine(stages=DEFAULT_STAGES, theme="nonexistent")
        rendered = engine.render(tiles_revealed=5)
        assert "\u2693" in rendered  # ⚓ naval ship

    def test_naval_theme_preserves_stage_names(self):
        """Naval theme does not rename stages."""
        engine = MapEngine(stages=DEFAULT_STAGES, theme="naval")
        rendered = engine.render(tiles_revealed=30)
        raw = strip_rich_markup(rendered)
        assert "迷雾之海" in raw

    def test_cultivation_milestone_uses_sparkles(self):
        """Cultivation milestone uses ✨ instead of ✦."""
        engine = MapEngine(
            stages=DEFAULT_STAGES,
            milestones={24: "穿越迷雾之海"},
            theme="cultivation",
        )
        rendered = engine.render(tiles_revealed=30)
        assert "\u2728" in rendered  # ✨ (cultivation milestone)


# ── get_current_stage tests ──


class TestGetCurrentStage:
    """Tests for get_current_stage()."""

    def test_stage_boundaries(self):
        """Stage boundaries are detected correctly."""
        engine = MapEngine(stages=DEFAULT_STAGES, theme="naval")

        # tiles_revealed 0-24 should be stage 1 (days 1-25)
        completed, current, nxt, idx = engine.get_current_stage(0)
        assert current["name"] == "启航"
        assert idx == 0

        # tiles_revealed 24 is last day of stage 1
        completed, current, nxt, idx = engine.get_current_stage(24)
        assert current["name"] == "启航"
        assert nxt is not None and nxt["name"] == "迷雾之海"

        # tiles_revealed 25 is first day of stage 2
        completed, current, nxt, idx = engine.get_current_stage(25)
        assert current["name"] == "迷雾之海"
        assert len(completed) == 1
        assert completed[0]["name"] == "启航"

        # Last stage
        completed, current, nxt, idx = engine.get_current_stage(174)
        assert current["name"] == "新大陆近海"
        assert nxt is None

    def test_total_days_from_stages(self):
        """total_days is derived from the last stage's end."""
        engine = MapEngine(stages=DEFAULT_STAGES, theme="naval")
        assert engine.total_days == 175

    def test_total_days_empty_stages(self):
        """Empty stages fall back to 175."""
        engine = MapEngine(stages=[], theme="naval")
        assert engine.total_days == 175


# ── get_log_entry tests (unchanged from original) ──


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
