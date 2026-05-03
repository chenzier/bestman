"""Tests for Map Engine."""

import re

from bestman.map_engine import MapEngine, get_log_entry


def strip_rich_markup(text: str) -> str:
    """Strip Rich markup tags, leaving only the content characters."""
    return re.sub(r"\[/?[^\]]*\]", "", text)


# ── existing tests adapted for new rendering ──

def test_initial_map_all_hidden():
    """tiles_revealed=0: ship at pos 0, all else hidden (▓ or ░)."""
    engine = MapEngine(total_days=175)
    rendered = engine.render(tiles_revealed=0)

    raw = strip_rich_markup(rendered)

    hidden_dark = raw.count("\u2593")  # ▓
    hidden_light = raw.count("\u2591")  # ░
    hidden_total = hidden_dark + hidden_light
    ship_count = raw.count("\u2693")  # ⚓
    revealed_count = raw.count("~")

    assert ship_count == 1, f"Expected 1 ship, got {ship_count}"
    assert hidden_total == 174, f"Expected 174 hidden, got {hidden_total}"
    assert revealed_count == 0, f"Expected 0 revealed ~, got {revealed_count}"
    assert hidden_total + ship_count + revealed_count == 175


def test_advance_tiles_shows_revealed_and_ship():
    """tiles_revealed=5: 2 ~, 3 ≈ (wake), 1 ⚓, 169 hidden."""
    engine = MapEngine(total_days=175)
    rendered = engine.render(tiles_revealed=5)

    raw = strip_rich_markup(rendered)

    hidden_dark = raw.count("\u2593")  # ▓
    hidden_light = raw.count("\u2591")  # ░
    hidden_total = hidden_dark + hidden_light
    wake_count = raw.count("\u2248")    # ≈
    revealed_count = raw.count("~")
    ship_count = raw.count("\u2693")    # ⚓

    assert wake_count == 3, f"Expected 3 wake tiles, got {wake_count}"
    assert revealed_count == 2, f"Expected 2 revealed tiles, got {revealed_count}"
    assert ship_count == 1, f"Expected 1 ship, got {ship_count}"
    assert hidden_total == 169, f"Expected 169 hidden, got {hidden_total}"
    total = wake_count + revealed_count + ship_count + hidden_total
    assert total == 175, f"Total should be 175, got {total}"


def test_milestone_positions_show_marker():
    """Milestone tiles show ✦ when revealed."""
    engine = MapEngine(total_days=175, milestones={5: "first week", 50: "equator"})
    rendered = engine.render(tiles_revealed=10)

    raw = strip_rich_markup(rendered)

    milestone_count = raw.count("\u2726")  # ✦
    revealed_count = raw.count("~")
    ship_count = raw.count("\u2693")       # ⚓
    hidden_dark = raw.count("\u2593")      # ▓
    hidden_light = raw.count("\u2591")     # ░

    assert milestone_count >= 1, f"Expected at least 1 milestone, got {milestone_count}"
    assert ship_count == 1
    assert hidden_dark + hidden_light == 164  # 175 - 11


def test_full_reveal_does_not_crash():
    """Rendering all 175 tiles revealed should not crash; shows 🏁 at end."""
    engine = MapEngine(total_days=175)
    rendered = engine.render(tiles_revealed=175)

    raw = strip_rich_markup(rendered)

    hidden_dark = raw.count("\u2593")
    hidden_light = raw.count("\u2591")
    ship_count = raw.count("\u2693")       # ⚓
    finish_count = raw.count("\U0001f3c1")  # 🏁

    assert hidden_dark + hidden_light == 0, "No hidden tiles remain"
    assert ship_count == 0, "Ship should be replaced by finish flag"
    assert finish_count == 1, "Should show finish flag at last position"

    # tiles_revealed > total_days should also work
    rendered2 = engine.render(tiles_revealed=200)
    raw2 = strip_rich_markup(rendered2)
    hidden2 = raw2.count("\u2593") + raw2.count("\u2591")
    assert hidden2 == 0, "All tiles should still be revealed"


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


# ── new tests for visual upgrade ──

def test_decorations_deterministic():
    """Same map rendered twice produces identical decorations."""
    engine = MapEngine(total_days=175)
    r1 = engine.render(tiles_revealed=80)
    r2 = engine.render(tiles_revealed=80)
    assert r1 == r2, "Two renders should be identical"
    # Verify decorations appear (🐟 or ⭐)
    raw = strip_rich_markup(r1)
    assert "\U0001f41f" in raw or "\u2b50" in raw, "Should have decorations"


def test_wake_effect():
    """Tiles within 3 of the ship should show wake (≈)."""
    engine = MapEngine(total_days=175)
    rendered = engine.render(tiles_revealed=42)

    raw = strip_rich_markup(rendered)

    # Positions 39, 40, 41 should be ≈ (wake, distance 1-3)
    # Position 42 is ⚓ (ship)
    wake_count = raw.count("\u2248")
    assert wake_count == 3, f"Expected 3 wake tiles, got {wake_count}"

    # At tiles_revealed=3, positions 0,1,2 should be ≈
    rendered2 = engine.render(tiles_revealed=3)
    raw2 = strip_rich_markup(rendered2)
    wake2 = raw2.count("\u2248")
    assert wake2 == 3, f"Expected 3 wake at tiles=3, got {wake2}"


def test_milestone_dims_after_passing():
    """Milestones that have been passed dim after the wake zone."""
    engine = MapEngine(total_days=175, milestones={5: "first week"})
    # At tiles_revealed=10, milestone at 5 is distance=5, should be dim
    rendered = engine.render(tiles_revealed=10)
    assert "[dim magenta]" in rendered
    assert "\u2726" in rendered  # ✦


def test_milestone_bright_on_arrival():
    """Milestone at current ship position shows bright."""
    engine = MapEngine(total_days=175, milestones={10: "arrival point"})
    # Ship at milestone position 10
    rendered = engine.render(tiles_revealed=10)
    raw = strip_rich_markup(rendered)
    # Position 10 should be ✦, not ⚓
    assert "\u2726" in raw, "Should show milestone marker"
    assert "\u2693" not in raw, "Ship icon should be replaced by milestone"


def test_ship_at_current_position():
    """Ship is rendered at tiles_revealed position."""
    engine = MapEngine(total_days=175)
    for pos in [1, 7, 42, 100, 174]:
        rendered = engine.render(tiles_revealed=pos)
        raw = strip_rich_markup(rendered)
        assert "\u2693" in raw, f"Ship should be present at pos {pos}"


def test_no_crash_at_all_positions():
    """Walking through 0→175 should not crash."""
    engine = MapEngine(total_days=175)
    for tiles in range(0, 176):
        rendered = engine.render(tiles_revealed=tiles)
        assert rendered is not None
        raw = strip_rich_markup(rendered).replace("\n", "")
        assert len(raw) == 175, f"Failed at tiles_revealed={tiles}"
    # Beyond total_days should also work
    for tiles in [176, 200, 1000]:
        rendered = engine.render(tiles_revealed=tiles)
        raw = strip_rich_markup(rendered).replace("\n", "")
        assert len(raw) == 175


def test_finish_flag_at_destination():
    """When all days complete, finish flag appears at the last tile."""
    engine = MapEngine(total_days=175)
    rendered = engine.render(tiles_revealed=175)
    raw = strip_rich_markup(rendered)
    assert "\U0001f3c1" in raw, "Should show finish flag"
    assert "\u2693" not in raw, "Ship should not be present"
