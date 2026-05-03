"""test_voyage.py — Voyage 类测试，全部使用 mock。

不依赖真实文件系统、SQLite 或外部服务。
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from bestman.voyage import Voyage


@pytest.fixture
def mock_deps():
    """Mock state、config、map engine、LLM 和日志模板。"""
    with (
        patch("bestman.voyage.load_config") as mock_load_config,
        patch("bestman.voyage.load_env") as mock_load_env,
        patch("bestman.voyage.BestmanState") as mock_state_cls,
        patch("bestman.voyage.MapEngine") as mock_map_cls,
        patch("bestman.voyage.LLMClient") as mock_llm_cls,
        patch("bestman.voyage.get_log_entry") as mock_get_log,
        patch("bestman.voyage.generate_voyage_log") as mock_gen_log,
        patch("bestman.voyage.chat_with_coach") as mock_coach,
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

        # LLM mock
        mock_llm = MagicMock()
        mock_llm.available = False
        mock_llm_cls.return_value = mock_llm

        # State mock
        mock_state = MagicMock()
        mock_state.get_tiles_revealed.return_value = 0
        mock_state.get_completed_days.return_value = 0
        mock_state.today_recorded.return_value = False
        mock_state.get_logs.return_value = []
        mock_state_cls.return_value = mock_state

        # Map engine mock
        mock_map = MagicMock()
        mock_map.render.return_value = "MOCK_MAP_HERE"
        mock_map_cls.return_value = mock_map

        # 日志模板 mock
        mock_get_log.return_value = "今天的航海日志测试文本。"

        # LLM 日志生成默认返回 None（fallback）
        mock_gen_log.return_value = None

        # 教练对话默认返回
        mock_coach.return_value = None

        yield {
            "config": mock_config,
            "state": mock_state,
            "map": mock_map,
            "llm": mock_llm,
            "get_log": mock_get_log,
            "gen_log": mock_gen_log,
            "coach": mock_coach,
            "load_config": mock_load_config,
            "load_env": mock_load_env,
            "llm_cls": mock_llm_cls,
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


class TestCompleteWithLLM:
    """LLM 日志生成测试。"""

    def test_complete_uses_llm_when_available(self, mock_deps):
        """LLM 可用时使用 LLM 生成日志。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.return_value = 1
        mock_deps["gen_log"].return_value = "LLM 生成的航海日志。"

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["success"] is True
        assert result["llm_used"] is True
        assert result["log_entry"] == "LLM 生成的航海日志。"
        # 不应调用模板 fallback
        mock_deps["get_log"].assert_not_called()

    def test_complete_falls_back_to_template(self, mock_deps):
        """LLM 不可用时退回模板日志。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.return_value = 1
        mock_deps["gen_log"].return_value = None  # LLM 不可用

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["success"] is True
        assert result["llm_used"] is False
        assert result["log_entry"] == "今天的航海日志测试文本。"
        # 应调用模板 fallback
        mock_deps["get_log"].assert_called_once()

    def test_complete_duplicate_returns_llm_used_false(self, mock_deps):
        """重复打卡时 llm_used 为 False。"""
        mock_deps["state"].today_recorded.return_value = True

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["success"] is False
        assert result["llm_used"] is False


class TestTalk:
    """talk() 方法测试。"""

    def test_talk_success(self, mock_deps):
        """成功与导航员对话。"""
        mock_deps["llm"].available = True
        mock_deps["coach"].return_value = "风浪有点大，但船很稳。今天可以减量。"

        voyage = Voyage()
        result = voyage.talk("今天好累")

        assert result["success"] is True
        assert result["response"] == "风浪有点大，但船很稳。今天可以减量。"
        assert result["error"] is None
        mock_deps["coach"].assert_called_once()

    def test_talk_llm_not_available(self, mock_deps):
        """LLM 未配置时返回友好提示。"""
        mock_deps["llm"].available = False

        voyage = Voyage()
        result = voyage.talk("今天好累")

        assert result["success"] is False
        assert "LLM 未配置" in result["error"]
        assert "导航员正在休息" in result["response"]

    def test_talk_llm_error(self, mock_deps):
        """LLM 请求失败时返回错误。"""
        mock_deps["llm"].available = True
        mock_deps["coach"].return_value = None  # 返回 None 表示失败

        voyage = Voyage()
        result = voyage.talk("今天好累")

        assert result["success"] is False
        assert "LLM 请求失败" in result["error"]

    def test_talk_passes_context_to_coach(self, mock_deps):
        """验证传递航行上下文给教练。"""
        mock_deps["llm"].available = True
        mock_deps["state"].get_tiles_revealed.return_value = 4
        mock_deps["state"].get_completed_days.return_value = 4
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["coach"].return_value = "继续前进。"

        voyage = Voyage()
        result = voyage.talk("今天做什么？")

        assert result["success"] is True
        call_args = mock_deps["coach"].call_args
        context = call_args[0][2]  # 第三个参数是 context
        assert context["current_day"] == 5  # tiles_revealed(4) + 1
        assert context["today_done"] is False
        assert "死虫式" in context["today_task"]


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
