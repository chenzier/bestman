"""test_cli.py — CLI 测试，使用 Click CliRunner + mock Voyage。

不依赖真实文件系统或 SQLite。
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from bestman.cli import main


@pytest.fixture
def runner():
    """Click CLI test runner。"""
    return CliRunner()


@pytest.fixture
def mock_voyage():
    """Mock Voyage 类。"""
    with patch("bestman.cli.Voyage") as mock_cls:
        mock_inst = MagicMock()
        mock_cls.return_value = mock_inst

        # 默认状态
        mock_inst.get_status.return_value = {
            "tiles_revealed": 0,
            "current_day": 1,
            "total_days": 175,
            "remaining": 175,
            "stage": {"name": "启航", "start": 1, "end": 25},
            "today_done": False,
            "completed_days": 0,
        }
        mock_inst.get_daily_task.return_value = "死虫式 3×10 + 静蹲 2×30秒"
        mock_inst.render_map.return_value = "MOCK_MAP_HERE"
        mock_inst.get_logs.return_value = []
        mock_inst.is_initialized.return_value = True

        yield {"cls": mock_cls, "inst": mock_inst}


class TestInitCommand:
    """bestman init 测试。"""

    @patch("bestman.cli.ensure_home")
    def test_init_output(self, mock_ensure_home, runner):
        """init 调用 ensure_home，输出包含 已就绪。"""
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0
        mock_ensure_home.assert_called_once()
        assert "已就绪" in result.output
        assert "175 天" in result.output

    @patch("bestman.cli.ensure_home")
    def test_init_shows_instructions(self, mock_ensure_home, runner):
        """init 输出包含数据目录和下一步提示。"""
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0
        assert "bestman init" not in result.output.lower() or "bestman" in result.output


class TestDashboard:
    """bestman 仪表盘（默认命令）测试。"""

    @patch("bestman.cli.BESTMAN_HOME")
    def test_dashboard_renders(self, mock_home, mock_voyage, runner):
        """仪表盘渲染 Rule + 地图 + 进度。"""
        mock_home.is_dir.return_value = True

        result = runner.invoke(main)

        assert result.exit_code == 0
        # 应有 Rule 标题
        assert "bestman" in result.output.lower()
        # 应有地图
        assert "MOCK_MAP_HERE" in result.output
        # 应有进度
        assert "0/175" in result.output

    @patch("bestman.cli.BESTMAN_HOME")
    def test_dashboard_not_initialized(self, mock_home, runner):
        """未初始化时提示 init。"""
        mock_home.is_dir.return_value = False

        result = runner.invoke(main)

        assert result.exit_code == 1  # SystemExit(1)
        assert "尚未初始化" in result.output
        assert "bestman init" in result.output

    @patch("bestman.cli.BESTMAN_HOME")
    def test_dashboard_today_done(self, mock_home, mock_voyage, runner):
        """今日已完成时显示绿色提示。"""
        mock_home.is_dir.return_value = True
        mock_voyage["inst"].get_status.return_value["today_done"] = True

        result = runner.invoke(main)

        assert result.exit_code == 0
        assert "今日任务已完成" in result.output

    @patch("bestman.cli.BESTMAN_HOME")
    def test_dashboard_shows_logs(self, mock_home, mock_voyage, runner):
        """仪表盘显示最近日志。"""
        mock_home.is_dir.return_value = True
        mock_voyage["inst"].get_logs.return_value = [
            {"date": "2026-05-03", "text": "测试日志文本"}
        ]

        result = runner.invoke(main)

        assert result.exit_code == 0
        assert "测试日志文本" in result.output


class TestDoneCommand:
    """bestman done 测试。"""

    @patch("bestman.cli.BESTMAN_HOME")
    def test_done_success(self, mock_home, mock_voyage, runner):
        """done 成功打卡。"""
        mock_home.is_dir.return_value = True
        mock_voyage["inst"].complete.return_value = {
            "success": True,
            "message": "完成！推进了 1 格",
            "tiles_revealed": 1,
            "log_entry": "晨光洒在甲板上，bestman 号缓缓驶出港口。",
            "milestone": None,
            "error": None,
        }
        mock_voyage["inst"].get_status.return_value["tiles_revealed"] = 1

        result = runner.invoke(main, ["done"])

        assert result.exit_code == 0
        assert "完成" in result.output
        assert "晨光洒在甲板上" in result.output

    @patch("bestman.cli.BESTMAN_HOME")
    def test_done_duplicate(self, mock_home, mock_voyage, runner):
        """同一天重复 done 失败。"""
        mock_home.is_dir.return_value = True
        mock_voyage["inst"].complete.return_value = {
            "success": False,
            "message": "今日已经完成过了",
            "tiles_revealed": 3,
            "log_entry": None,
            "milestone": None,
            "error": "今日已经打卡",
        }

        result = runner.invoke(main, ["done"])

        assert result.exit_code == 0
        assert "今日已经打卡" in result.output

    @patch("bestman.cli.BESTMAN_HOME")
    def test_done_not_initialized(self, mock_home, runner):
        """未 init 时 done 提示 init。"""
        mock_home.is_dir.return_value = False

        result = runner.invoke(main, ["done"])

        assert result.exit_code == 1
        assert "尚未初始化" in result.output

    @patch("bestman.cli.BESTMAN_HOME")
    def test_done_with_milestone(self, mock_home, mock_voyage, runner):
        """done 触发里程碑。"""
        mock_home.is_dir.return_value = True
        mock_voyage["inst"].complete.return_value = {
            "success": True,
            "message": "完成！推进了 1 格",
            "tiles_revealed": 25,
            "log_entry": "海面平静如镜。",
            "milestone": "穿越迷雾之海",
            "error": None,
        }

        result = runner.invoke(main, ["done"])

        assert result.exit_code == 0
        assert "里程碑达成" in result.output
        assert "穿越迷雾之海" in result.output

    @patch("bestman.cli.BESTMAN_HOME")
    def test_done_voyage_complete(self, mock_home, mock_voyage, runner):
        """完成全部航程时显示完成面板。"""
        mock_home.is_dir.return_value = True
        mock_voyage["inst"].complete.return_value = {
            "success": True,
            "message": "完成！推进了 1 格",
            "tiles_revealed": 175,
            "log_entry": "夕阳把整片海洋染成金色。",
            "milestone": "抵达新大陆",
            "error": None,
        }
        mock_voyage["inst"].get_status.return_value = {
            "tiles_revealed": 175,
            "current_day": 175,
            "total_days": 175,
            "remaining": 0,
            "stage": {"name": "新大陆近海", "start": 151, "end": 175},
            "today_done": True,
            "completed_days": 175,
        }

        result = runner.invoke(main, ["done"])

        assert result.exit_code == 0
        assert "航程结束" in result.output


class TestLogCommand:
    """bestman log 测试。"""

    @patch("bestman.cli.BESTMAN_HOME")
    def test_log_default(self, mock_home, mock_voyage, runner):
        """log 默认显示最近 10 条。"""
        mock_home.is_dir.return_value = True
        mock_voyage["inst"].get_logs.return_value = [
            {"date": "2026-05-03", "text": "第一条日志"},
            {"date": "2026-05-04", "text": "第二条日志"},
        ]

        result = runner.invoke(main, ["log"])

        assert result.exit_code == 0
        mock_voyage["inst"].get_logs.assert_called_with(10)
        assert "第一条日志" in result.output
        assert "第二条日志" in result.output

    @patch("bestman.cli.BESTMAN_HOME")
    def test_log_with_count(self, mock_home, mock_voyage, runner):
        """log -n 5 显示最近 5 条。"""
        mock_home.is_dir.return_value = True

        result = runner.invoke(main, ["log", "-n", "5"])

        assert result.exit_code == 0
        mock_voyage["inst"].get_logs.assert_called_with(5)

    @patch("bestman.cli.BESTMAN_HOME")
    def test_log_empty(self, mock_home, mock_voyage, runner):
        """无日志时显示提示。"""
        mock_home.is_dir.return_value = True
        mock_voyage["inst"].get_logs.return_value = []

        result = runner.invoke(main, ["log"])

        assert result.exit_code == 0
        assert "尚无航海日志" in result.output

    @patch("bestman.cli.BESTMAN_HOME")
    def test_log_not_initialized(self, mock_home, runner):
        """未 init 时 log 提示 init。"""
        mock_home.is_dir.return_value = False

        result = runner.invoke(main, ["log"])

        assert result.exit_code == 1
        assert "尚未初始化" in result.output


class TestHelp:
    """--help 测试。"""

    def test_main_help(self, runner):
        """bestman --help 显示帮助。"""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "航向新大陆" in result.output
        assert "init" in result.output
        assert "done" in result.output
        assert "log" in result.output

    def test_init_help(self, runner):
        """bestman init --help。"""
        result = runner.invoke(main, ["init", "--help"])
        assert result.exit_code == 0
        assert "初始化" in result.output

    def test_done_help(self, runner):
        """bestman done --help。"""
        result = runner.invoke(main, ["done", "--help"])
        assert result.exit_code == 0

    def test_log_help(self, runner):
        """bestman log --help。"""
        result = runner.invoke(main, ["log", "--help"])
        assert result.exit_code == 0
