"""Tests for bestman.state"""
import sqlite3
from datetime import date

import pytest

from bestman.state import BestmanState


@pytest.fixture
def state():
    db = BestmanState(":memory:")
    yield db
    db.close()


class TestTableCreation:
    def test_creates_days_table(self, state):
        cursor = state.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='days'"
        )
        assert cursor.fetchone() is not None

    def test_creates_voyage_logs_table(self, state):
        cursor = state.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='voyage_logs'"
        )
        assert cursor.fetchone() is not None

    def test_days_table_has_required_columns(self, state):
        cursor = state.conn.execute("PRAGMA table_info(days)")
        columns = {row[1] for row in cursor.fetchall()}
        assert columns >= {"date", "completed", "extra", "task_done", "used_skip", "created_at"}

class TestRecordDay:
    def test_records_new_day(self, state):
        state.record_day("2026-05-03", completed=1, extra=0, task_done="done")
        assert state.today_recorded("2026-05-03") is True

    def test_day_has_correct_values(self, state):
        state.record_day("2026-05-03", completed=1, extra=2, task_done="死虫式 3×10")
        row = state.conn.execute(
            "SELECT completed, extra, task_done FROM days WHERE date='2026-05-03'"
        ).fetchone()
        assert row == (1, 2, "死虫式 3×10")

    def test_record_day_with_used_skip(self, state):
        """used_skip=1 记录跳过日，不推进 tiles。"""
        state.record_day("2026-05-03", completed=0, extra=0, used_skip=1)
        row = state.conn.execute(
            "SELECT completed, used_skip FROM days WHERE date='2026-05-03'"
        ).fetchone()
        assert row == (0, 1)
        assert state.get_tiles_revealed() == 0


class TestTodayRecorded:
    def test_returns_false_for_unrecorded_date(self, state):
        assert state.today_recorded("2026-05-03") is False

    def test_returns_true_for_recorded_date(self, state):
        state.record_day("2026-05-03", completed=1, extra=0, task_done="done")
        assert state.today_recorded("2026-05-03") is True

    def test_defaults_to_today(self, state):
        today = date.today().isoformat()
        # Should return False since we haven't recorded today
        assert state.today_recorded() is False


class TestGetTilesRevealed:
    def test_returns_zero_when_no_days(self, state):
        assert state.get_tiles_revealed() == 0

    def test_equals_completed_plus_extra(self, state):
        state.record_day("2026-05-03", completed=1, extra=0, task_done="done")
        state.record_day("2026-05-04", completed=1, extra=3, task_done="done")
        assert state.get_tiles_revealed() == 5  # 1 + (1+3)

    def test_handles_extra_zero(self, state):
        state.record_day("2026-05-03", completed=1, extra=0, task_done="done")
        assert state.get_tiles_revealed() == 1


class TestGetCompletedDays:
    def test_returns_zero_when_no_days(self, state):
        assert state.get_completed_days() == 0

    def test_counts_days_with_completed_set(self, state):
        state.record_day("2026-05-03", completed=1, extra=0, task_done="done")
        state.record_day("2026-05-04", completed=1, extra=0, task_done="done")
        assert state.get_completed_days() == 2


class TestGetStreak:
    """get_streak() 测试。"""

    def test_streak_zero_when_no_days(self, state):
        assert state.get_streak("2026-05-03") == 0

    def test_streak_single_day(self, state):
        state.record_day("2026-05-03", completed=1)
        assert state.get_streak("2026-05-03") == 1

    def test_streak_consecutive_days(self, state):
        for i in range(5):
            state.record_day(f"2026-05-{i + 3:02d}", completed=1)
        assert state.get_streak("2026-05-07") == 5

    def test_streak_breaks_on_missed_day(self, state):
        state.record_day("2026-05-03", completed=1)
        state.record_day("2026-05-04", completed=1)
        # 跳过 05-05
        state.record_day("2026-05-06", completed=1)
        assert state.get_streak("2026-05-06") == 1  # only 05-06 counts

    def test_streak_includes_skip_days(self, state):
        """used_skip=1 的天也计入连击。"""
        state.record_day("2026-05-03", completed=1)
        state.record_day("2026-05-04", completed=0, used_skip=1)
        state.record_day("2026-05-05", completed=1)
        assert state.get_streak("2026-05-05") == 3

    def test_streak_gap_from_reference(self, state):
        """最晚记录和 reference_date 间隔超过 1 天时返回 0。"""
        state.record_day("2026-05-03", completed=1)
        state.record_day("2026-05-04", completed=1)
        assert state.get_streak("2026-05-07") == 0

    def test_streak_defaults_to_today(self, state):
        """默认 reference_date 为今天。"""
        # 没记录时 streak=0
        assert state.get_streak() == 0

    def test_streak_scattered_non_consecutive(self, state):
        """非连续日期只计入最近的连续链。"""
        state.record_day("2026-05-01", completed=1)
        state.record_day("2026-05-02", completed=1)
        state.record_day("2026-05-04", completed=1)
        state.record_day("2026-05-05", completed=1)
        assert state.get_streak("2026-05-05") == 2  # 只有 05-04, 05-05


class TestSkipTokens:
    """skip_tokens 表相关测试。"""

    def test_migrate_creates_table(self, state):
        cursor = state.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='skip_tokens'"
        )
        assert cursor.fetchone() is not None

    def test_get_available_skip_tokens_zero(self, state):
        assert state.get_available_skip_tokens() == 0

    def test_add_and_get_tokens(self, state):
        state.add_skip_token("2026-05-03")
        state.add_skip_token("2026-05-10")
        assert state.get_available_skip_tokens() == 2

    def test_use_skip_token_success(self, state):
        state.add_skip_token("2026-05-03")
        assert state.use_skip_token() is True
        assert state.get_available_skip_tokens() == 0

    def test_use_skip_token_no_tokens(self, state):
        assert state.use_skip_token() is False

    def test_multiple_tokens_use_one(self, state):
        state.add_skip_token("2026-05-03")
        state.add_skip_token("2026-05-10")
        assert state.use_skip_token() is True
        assert state.get_available_skip_tokens() == 1

    def test_double_migrate_is_idempotent(self, state):
        """第二次调用 _migrate 不会报错。"""
        state._migrate()  # 不应抛异常
        cursor = state.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='skip_tokens'"
        )
        assert cursor.fetchone() is not None


class TestSaveLog:
    def test_saves_and_retrieves_log(self, state):
        state.save_log("2026-05-03", "晨光洒在甲板上...")
        logs = state.get_logs(limit=10)
        assert len(logs) == 1
        assert logs[0]["date"] == "2026-05-03"
        assert logs[0]["text"] == "晨光洒在甲板上..."

    def test_logs_ordered_by_date_desc(self, state):
        state.save_log("2026-05-03", "Day 1")
        state.save_log("2026-05-04", "Day 2")
        state.save_log("2026-05-05", "Day 3")
        logs = state.get_logs(limit=10)
        assert len(logs) == 3
        assert logs[0]["date"] == "2026-05-05"
        assert logs[1]["date"] == "2026-05-04"
        assert logs[2]["date"] == "2026-05-03"

    def test_get_logs_respects_limit(self, state):
        for i in range(5):
            state.save_log(f"2026-05-{i + 3:02d}", f"Day {i}")
        logs = state.get_logs(limit=3)
        assert len(logs) == 3


class TestCoins:
    """coins_earned 和 get_total_coins 测试。"""

    def test_days_table_has_coins_earned_column(self, state):
        cursor = state.conn.execute("PRAGMA table_info(days)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "coins_earned" in columns

    def test_get_total_coins_zero_when_no_days(self, state):
        assert state.get_total_coins() == 0

    def test_record_day_with_coins(self, state):
        state.record_day("2026-05-03", completed=1, extra=0, coins_earned=15)
        assert state.get_total_coins() == 15

    def test_get_total_coins_sums_across_days(self, state):
        state.record_day("2026-05-03", completed=1, extra=0, coins_earned=10)
        state.record_day("2026-05-04", completed=2, extra=0, coins_earned=25)
        state.record_day("2026-05-05", completed=1, extra=0, coins_earned=10)
        assert state.get_total_coins() == 45

    def test_record_day_coins_default_to_zero(self, state):
        """不传 coins_earned 时默认为 0。"""
        state.record_day("2026-05-03", completed=1)
        assert state.get_total_coins() == 0

    def test_skip_day_no_coins(self, state):
        """跳过日通常不产金币。"""
        state.record_day("2026-05-03", completed=0, extra=0, used_skip=1, coins_earned=0)
        assert state.get_total_coins() == 0


class TestTreasures:
    """treasures 表和宝藏持久化测试。"""

    def test_migrate_creates_treasures_table(self, state):
        cursor = state.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='treasures'"
        )
        assert cursor.fetchone() is not None

    def test_discover_treasure_stores_record(self, state):
        state.discover_treasure("沉船宝藏", "explicit", 50, "2026-05-03")
        treasures = state.get_treasures()
        assert len(treasures) == 1
        assert treasures[0]["name"] == "沉船宝藏"
        assert treasures[0]["type"] == "explicit"
        assert treasures[0]["coins"] == 50
        assert treasures[0]["discovered_date"] == "2026-05-03"

    def test_get_treasures_ordered_by_date(self, state):
        state.discover_treasure("First", "explicit", 30, "2026-05-03")
        state.discover_treasure("Second", "implicit", 20, "2026-05-01")
        treasures = state.get_treasures()
        assert treasures[0]["name"] == "Second"  # earlier date first
        assert treasures[1]["name"] == "First"

    def test_multiple_treasures(self, state):
        state.discover_treasure("A", "explicit", 50, "2026-05-03")
        state.discover_treasure("B", "implicit", 20, "2026-05-04")
        assert len(state.get_treasures()) == 2

    def test_no_treasures_returns_empty_list(self, state):
        assert state.get_treasures() == []

    def test_save_log_with_treasure_found_event_type(self, state):
        """treasure_found 事件类型可用于 voyage_logs。"""
        state.save_log("2026-05-03", "发现了沉船宝藏！", event_type="treasure_found")
        logs = state.get_logs(limit=10)
        assert len(logs) == 1
        assert logs[0]["text"] == "发现了沉船宝藏！"
