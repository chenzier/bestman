"""test_voyage.py — Voyage 类测试，全部使用 mock。

不依赖真实文件系统、SQLite 或外部服务。
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from bestman.voyage import Voyage


@pytest.fixture
def mock_deps():
    """Mock state、config、map engine 和日志模板。"""
    with (
        patch("bestman.voyage.load_config") as mock_load_config,
        patch("bestman.voyage.BestmanState") as mock_state_cls,
        patch("bestman.voyage.MapEngine") as mock_map_cls,
        patch("bestman.voyage.get_log_entry") as mock_get_log,
    ):
        # 配置 mock
        mock_config = {
            "voyage": {
                "total_days": 175,
                "end_date": "2026-10-25",
                "default_daily_task": "死虫式 3×10 + 静蹲 2×30秒",
                "milestones": {
                    5: "测试里程碑-A",
                    10: "测试里程碑-B",
                },
                "stages": [
                    {"name": "启航", "days": (1, 25)},
                ],
            }
        }
        mock_load_config.return_value = mock_config

        # State mock
        mock_state = MagicMock()
        mock_state.get_tiles_revealed.return_value = 0
        mock_state.get_completed_days.return_value = 0
        mock_state.today_recorded.return_value = False
        mock_state.get_logs.return_value = []
        mock_state.get_streak.return_value = 0
        mock_state.get_available_skip_tokens.return_value = 0
        mock_state.use_skip_token.return_value = False
        mock_state_cls.return_value = mock_state

        # Map engine mock
        mock_map = MagicMock()
        mock_map.render.return_value = "MOCK_MAP_HERE"
        mock_map_cls.return_value = mock_map

        # 日志模板 mock
        mock_get_log.return_value = "今天的航海日志测试文本。"

        yield {
            "config": mock_config,
            "state": mock_state,
            "map": mock_map,
            "get_log": mock_get_log,
            "load_config": mock_load_config,
        }


class TestVoyageInit:
    """Voyage.get_status() 测试。"""

    def test_get_status_initial(self, mock_deps):
        """初始状态：tiles_revealed=0, current_day=1, remaining=175。"""
        voyage = Voyage()
        status = voyage.get_status()

        assert status["tiles_revealed"] == 0
        assert status["current_day"] == 1
        assert status["total_days"] == 175
        assert status["remaining"] == 175
        assert status["stage"]["name"] == "启航"
        assert status["today_done"] is False
        assert status["completed_days"] == 0
        assert status["streak"] == 0
        assert status["skip_tokens"] == 0

    def test_get_status_mid_voyage(self, mock_deps):
        """mid-voyage 状态。"""
        mock_deps["state"].get_tiles_revealed.return_value = 42
        mock_deps["state"].get_completed_days.return_value = 40
        mock_deps["state"].today_recorded.return_value = True

        voyage = Voyage()
        status = voyage.get_status()

        assert status["tiles_revealed"] == 42
        assert status["current_day"] == 43
        assert status["remaining"] == 133
        assert status["today_done"] is True
        assert status["completed_days"] == 40


class TestGetDailyTask:
    """get_daily_task() 测试。"""

    def test_get_daily_task_from_config(self, mock_deps):
        """从 config 取值。"""
        voyage = Voyage()
        task = voyage.get_daily_task()
        assert task == "死虫式 3×10 + 静蹲 2×30秒"


class TestRenderMap:
    """render_map() 测试。"""

    def test_render_delegates_to_map_engine(self, mock_deps):
        """委托 map_engine.render()。"""
        voyage = Voyage()
        result = voyage.render_map()
        mock_deps["state"].get_tiles_revealed.assert_called_once()
        mock_deps["map"].render.assert_called_once_with(0)
        assert result == "MOCK_MAP_HERE"


class TestComplete:
    """complete() 测试。"""

    def test_complete_success(self, mock_deps):
        """成功打卡路径。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.return_value = 1

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["success"] is True
        assert result["tiles_revealed"] == 1
        assert "推进了 1 格" in result["message"]
        assert result["log_entry"] is not None
        assert result["milestone"] is None
        assert result["error"] is None

        # 验证 state 调用
        mock_deps["state"].today_recorded.assert_called_with("2026-05-03")
        mock_deps["state"].record_day.assert_called_once_with(
            "2026-05-03", completed=1, extra=0
        )
        mock_deps["state"].save_log.assert_called_once()

    def test_complete_duplicate_rejected(self, mock_deps):
        """同日重复打卡被拒绝。"""
        mock_deps["state"].today_recorded.return_value = True

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["success"] is False
        assert result["error"] == "今日已经打卡"
        mock_deps["state"].record_day.assert_not_called()

    def test_complete_with_milestone(self, mock_deps):
        """抵达里程碑时返回里程碑信息。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.return_value = 5  # 触发 milestone 5

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["success"] is True
        assert result["milestone"] == "测试里程碑-A"
        assert result["tiles_revealed"] == 5

    def test_complete_default_date(self, mock_deps):
        """不传 date_str 时使用今天。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.return_value = 1

        voyage = Voyage()
        result = voyage.complete()

        today = date.today().isoformat()
        mock_deps["state"].today_recorded.assert_called_with(today)
        assert result["success"] is True


class TestCompleteStreakAward:
    """complete() 连击奖励测试。"""

    def test_awards_token_on_streak_seven(self, mock_deps):
        """连击达到 7 天时发放跳过令牌。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.return_value = 1
        mock_deps["state"].get_streak.return_value = 7

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["success"] is True
        mock_deps["state"].add_skip_token.assert_called_once_with("2026-05-03")

    def test_no_token_below_streak_seven(self, mock_deps):
        """连击不足 7 天时不发放令牌。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.return_value = 1
        mock_deps["state"].get_streak.return_value = 6

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["success"] is True
        mock_deps["state"].add_skip_token.assert_not_called()


class TestSkip:
    """skip() 测试。"""

    def test_skip_success(self, mock_deps):
        """使用令牌跳过成功。"""
        mock_deps["state"].get_available_skip_tokens.return_value = 2
        mock_deps["state"].use_skip_token.return_value = True
        mock_deps["state"].get_tiles_revealed.return_value = 5

        voyage = Voyage()
        result = voyage.skip("2026-05-03")

        assert result["success"] is True
        assert "已使用一枚跳过令牌" in result["message"]
        assert "剩余令牌" in result["message"]
        assert result["tiles_revealed"] == 5
        assert result["log_entry"] is not None
        assert result["error"] is None

        # 验证调用
        mock_deps["state"].use_skip_token.assert_called_once()
        mock_deps["state"].record_day.assert_called_once_with(
            "2026-05-03", completed=0, extra=0, used_skip=1
        )
        mock_deps["state"].save_log.assert_called_once()

    def test_skip_no_tokens(self, mock_deps):
        """无可用令牌时 skip 失败。"""
        mock_deps["state"].get_available_skip_tokens.return_value = 0
        mock_deps["state"].get_tiles_revealed.return_value = 5

        voyage = Voyage()
        result = voyage.skip("2026-05-03")

        assert result["success"] is False
        assert result["error"] == "没有可用令牌"
        mock_deps["state"].use_skip_token.assert_not_called()
        mock_deps["state"].record_day.assert_not_called()

    def test_skip_does_not_advance_tiles(self, mock_deps):
        """跳过不推进地图（completed=0）。"""
        mock_deps["state"].get_available_skip_tokens.return_value = 1
        mock_deps["state"].use_skip_token.return_value = True
        mock_deps["state"].get_tiles_revealed.return_value = 5

        voyage = Voyage()
        result = voyage.skip("2026-05-03")

        assert result["tiles_revealed"] == 5  # 不变
        mock_deps["state"].record_day.assert_called_with(
            "2026-05-03", completed=0, extra=0, used_skip=1
        )

    def test_skip_default_date(self, mock_deps):
        """不传 date_str 时使用今天。"""
        mock_deps["state"].get_available_skip_tokens.return_value = 1
        mock_deps["state"].use_skip_token.return_value = True
        mock_deps["state"].get_tiles_revealed.return_value = 0

        voyage = Voyage()
        result = voyage.skip()

        today = date.today().isoformat()
        mock_deps["state"].record_day.assert_called_with(
            today, completed=0, extra=0, used_skip=1
        )
        assert result["success"] is True


class TestGetLogs:
    """get_logs() 测试。"""

    def test_get_logs_delegates_to_state(self, mock_deps):
        """委托 state.get_logs()。"""
        mock_logs = [
            {"date": "2026-05-03", "text": "日志一"},
            {"date": "2026-05-04", "text": "日志二"},
        ]
        mock_deps["state"].get_logs.return_value = mock_logs

        voyage = Voyage()
        logs = voyage.get_logs(5)

        mock_deps["state"].get_logs.assert_called_once_with(5)
        assert logs == mock_logs

    def test_get_logs_default_limit(self, mock_deps):
        """默认 limit=10。"""
        voyage = Voyage()
        voyage.get_logs()
        mock_deps["state"].get_logs.assert_called_once_with(10)


class TestIsInitialized:
    """is_initialized() 测试。"""

    @patch("bestman.voyage.BESTMAN_HOME")
    def test_is_initialized_true(self, mock_home):
        """BESTMAN_HOME 存在时返回 True。"""
        mock_home.is_dir.return_value = True
        assert Voyage.is_initialized() is True

    @patch("bestman.voyage.BESTMAN_HOME")
    def test_is_initialized_false(self, mock_home):
        """BESTMAN_HOME 不存在时返回 False。"""
        mock_home.is_dir.return_value = False
        assert Voyage.is_initialized() is False
