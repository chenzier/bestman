"""Tests for Map Engine."""

import re

from bestman.map_engine import MapEngine, get_log_entry


def strip_rich_markup(text: str) -> str:
    """Strip Rich markup tags, leaving only the content characters."""
    # Remove inline styles like [bold yellow], [cyan], [dim blue], [/]
    return re.sub(r"\[/?[^\]]*\]", "", text)


def test_initial_map_all_hidden():
    """Initial map (tiles_revealed=0) should show all hidden tiles."""
    engine = MapEngine(total_days=175)
    rendered = engine.render(tiles_revealed=0)

    raw = strip_rich_markup(rendered)

    # 175 tiles, all should be ▒ hidden tiles
    hidden_count = raw.count("\u2592")  # ▒
    revealed_count = raw.count("~")
    ship_count = raw.count("\u2693")  # ⚓
    milestone_count = raw.count("\u2726")  # ✦

    assert hidden_count == 175, f"Expected 175 hidden tiles, got {hidden_count}"
    assert revealed_count == 0, f"Expected 0 revealed tiles, got {revealed_count}"
    assert ship_count == 0, f"Expected 0 ship icons, got {ship_count}"
    assert milestone_count == 0, f"Expected 0 milestone icons, got {milestone_count}"


def test_advance_tiles_shows_revealed_and_ship():
    """Advancing N tiles shows N ~ + 1 ⚓, rest ▒."""
    engine = MapEngine(total_days=175)
    rendered = engine.render(tiles_revealed=5)

    raw = strip_rich_markup(rendered)

    hidden_count = raw.count("\u2592")  # ▒
    revealed_count = raw.count("~")
    ship_count = raw.count("\u2693")  # ⚓

    assert revealed_count == 5, f"Expected 5 revealed tiles, got {revealed_count}"
    assert ship_count == 1, f"Expected 1 ship icon, got {ship_count}"
    assert hidden_count == 169, f"Expected 169 hidden tiles, got {hidden_count}"
    assert revealed_count + ship_count + hidden_count == 175


def test_milestone_positions_show_marker():
    """Milestone tiles show ✦ marker instead of ~."""
    engine = MapEngine(total_days=175, milestones={5: "first week", 50: "equator"})
    rendered = engine.render(tiles_revealed=10)

    raw = strip_rich_markup(rendered)

    milestone_count = raw.count("\u2726")  # ✦
    revealed_count = raw.count("~")
    ship_count = raw.count("\u2693")  # ⚓
    hidden_count = raw.count("\u2592")  # ▒

    assert milestone_count == 1, f"Expected 1 milestone at pos 5, got {milestone_count}"
    # At tiles_revealed=10: ~ at 0-4,6-9 (9 ~), ✦ at 5 (1 ✦), ⚓ at 10 (1 ⚓)
    assert revealed_count == 9, f"Expected 9 revealed tiles, got {revealed_count}"
    assert ship_count == 1
    assert hidden_count == 164  # 175 - 11


def test_full_reveal_does_not_crash():
    """Rendering all 175 tiles revealed should not crash."""
    engine = MapEngine(total_days=175)
    rendered = engine.render(tiles_revealed=175)

    raw = strip_rich_markup(rendered)

    # All tiles revealed, no hidden tiles, ship at destination (finished)
    hidden_count = raw.count("\u2592")  # ▒
    revealed_count = raw.count("~")
    ship_count = raw.count("\u2693")  # ⚓

    assert hidden_count == 0, f"Expected 0 hidden tiles, got {hidden_count}"
    assert revealed_count == 175, f"Expected 175 revealed tiles, got {revealed_count}"
    assert ship_count == 0, "Ship should be gone after completing all tiles"

    # Should also work for tiles_revealed > total_days
    rendered2 = engine.render(tiles_revealed=200)
    raw2 = strip_rich_markup(rendered2)
    hidden_count2 = raw2.count("\u2592")
    assert hidden_count2 == 0, "All tiles should still be revealed"


def test_get_log_entry_deterministic():
    """Same day always returns the same log entry."""
    log1 = get_log_entry(5)
    log2 = get_log_entry(5)
    log3 = get_log_entry(42)

    assert isinstance(log1, str)
    assert len(log1) > 0
    assert log1 == log2, "Same day should return identical log"
    assert log1 != log3, "Different day should return different log (with high probability for seeded randomness)"
