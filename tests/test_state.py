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
