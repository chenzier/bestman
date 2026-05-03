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
            "streak": 0,
            "skip_tokens": 0,
            "coins": 0,
            "treasures": [],
        }
        mock_inst.get_daily_task.return_value = "死虫式 3×10 + 静蹲 2×30秒"
        mock_inst.render_map.return_value = "MOCK_MAP_HERE"
        mock_inst.get_logs.return_value = []
        mock_inst.is_initialized.return_value = True
        mock_inst.skip.return_value = {
            "success": True,
            "message": "已使用一枚跳过令牌。剩余令牌：0 枚",
            "tiles_revealed": 5,
            "log_entry": "今日使用跳过令牌。船队在避风港暂歇。",
            "error": None,
        }

        # LLM mock
        mock_llm = MagicMock()
        mock_llm.available = True
        mock_inst.llm = mock_llm

        # complete 默认返回
        mock_inst.complete.return_value = {
            "success": True,
            "message": "完成！推进了 1 格",
            "tiles_revealed": 1,
            "log_entry": "晨光洒在甲板上。",
            "milestone": None,
            "error": None,
            "llm_used": False,
            "dice": {"distance": 1, "description": "风平浪静", "extra_tiles": 0},
            "coins": {
                "total": 10,
                "breakdown": {"每日打卡": 10},
            },
            "treasures": [],
        }

        # config mock
        mock_inst.config = {
            "dice": {"mode": "deterministic", "weights": [60, 30, 10]},
            "voyage": {"total_days": 175},
        }
        mock_inst._get_distance_description = MagicMock(return_value="风平浪静，缓缓前行")

        # talk 默认返回
        mock_inst.talk.return_value = {
            "success": True,
            "response": "慢慢来，水手。今天海面很平静。",
            "error": None,
        }

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
        """仪表盘渲染 Rule + 分段地图 + 状态行。"""
        mock_home.is_dir.return_value = True

        result = runner.invoke(main)

        assert result.exit_code == 0
        # 应有 Rule 标题
        assert "bestman" in result.output.lower()
        # 应有地图（mock 返回 MOCK_MAP_HERE）
        assert "MOCK_MAP_HERE" in result.output
        # 应有状态行：DAY 1/175
        assert "DAY 1/175" in result.output
        assert "启航" in result.output

    @patch("bestman.cli.BESTMAN_HOME")
    def test_dashboard_skip_hint_when_tokens(self, mock_home, mock_voyage, runner):
        """有令牌且今日未完成时显示 skip 提示。"""
        mock_home.is_dir.return_value = True
        mock_voyage["inst"].get_status.return_value["skip_tokens"] = 3

        result = runner.invoke(main)

        assert result.exit_code == 0
        assert "bestman skip" in result.output
        assert "3 枚可用" in result.output

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
    def test_dashboard_shows_streak_and_tokens(self, mock_home, mock_voyage, runner):
        """仪表盘显示连击和令牌。"""
        mock_home.is_dir.return_value = True
        mock_voyage["inst"].get_status.return_value["streak"] = 5
        mock_voyage["inst"].get_status.return_value["skip_tokens"] = 2

        result = runner.invoke(main)

        assert result.exit_code == 0
        assert "5 天连击" in result.output
        assert "2 枚令牌" in result.output

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


class TestDashboardCoins:
    """仪表盘金币显示测试。"""

    @patch("bestman.cli.BESTMAN_HOME")
    def test_dashboard_shows_coins(self, mock_home, mock_voyage, runner):
        """仪表盘显示金币数。"""
        mock_home.is_dir.return_value = True
        mock_voyage["inst"].get_status.return_value["coins"] = 230

        result = runner.invoke(main)

        assert result.exit_code == 0
        assert "230 金币" in result.output

    @patch("bestman.cli.BESTMAN_HOME")
    def test_dashboard_shows_zero_coins(self, mock_home, mock_voyage, runner):
        """金币为 0 时也显示。"""
        mock_home.is_dir.return_value = True

        result = runner.invoke(main)

        assert result.exit_code == 0
        assert "0 金币" in result.output


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
            "llm_used": False,
            "dice": {"distance": 1, "description": "风平浪静", "extra_tiles": 0},
        }
        mock_voyage["inst"].get_status.return_value["tiles_revealed"] = 1

        result = runner.invoke(main, ["done"])

        assert result.exit_code == 0
        assert "掷出" in result.output
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
            "llm_used": False,
            "dice": {"distance": 1, "description": "风平浪静", "extra_tiles": 0},
        }

        result = runner.invoke(main, ["done"])

        assert result.exit_code == 0
        assert "里程碑达成" in result.output
        assert "穿越迷雾之海" in result.output

    @patch("bestman.cli.BESTMAN_HOME")
    def test_done_shows_coins(self, mock_home, mock_voyage, runner):
        """done 后显示金币获取。"""
        mock_home.is_dir.return_value = True
        mock_voyage["inst"].complete.return_value = {
            "success": True,
            "message": "完成！推进了 1 格",
            "tiles_revealed": 1,
            "log_entry": "晨光洒在甲板上。",
            "milestone": None,
            "error": None,
            "llm_used": False,
            "coins": {
                "total": 15,
                "breakdown": {"每日打卡": 10, "暴风加成": 5},
            },
            "treasures": [],
            "dice": {"distance": 1, "description": "风平浪静", "extra_tiles": 0},
        }

        result = runner.invoke(main, ["done"])

        assert result.exit_code == 0
        assert "+15 金币" in result.output
        assert "每日打卡" in result.output
        assert "暴风加成" in result.output

    @patch("bestman.cli.BESTMAN_HOME")
    def test_done_shows_treasure(self, mock_home, mock_voyage, runner):
        """done 后显示发现的宝藏。"""
        mock_home.is_dir.return_value = True
        mock_voyage["inst"].complete.return_value = {
            "success": True,
            "message": "完成！推进了 1 格",
            "tiles_revealed": 8,
            "log_entry": "测试日志。",
            "milestone": None,
            "error": None,
            "llm_used": False,
            "coins": {
                "total": 60,
                "breakdown": {"每日打卡": 10},
            },
            "treasures": [
                {
                    "name": "沉船宝藏",
                    "type": "explicit",
                    "coins": 50,
                    "message": "你发现了一艘古代沉船！",
                },
            ],
            "dice": {"distance": 1, "description": "风平浪静", "extra_tiles": 0},
        }

        result = runner.invoke(main, ["done"])

        assert result.exit_code == 0
        assert "沉船宝藏" in result.output
        assert "+50 金币" in result.output
        assert "古代沉船" in result.output

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
            "llm_used": False,
            "dice": {"distance": 1, "description": "风平浪静", "extra_tiles": 0},
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


class TestSkipCommand:
    """bestman skip 测试。"""

    @patch("bestman.cli.BESTMAN_HOME")
    def test_skip_success(self, mock_home, mock_voyage, runner):
        """skip 成功消耗令牌。"""
        mock_home.is_dir.return_value = True

        result = runner.invoke(main, ["skip"])

        assert result.exit_code == 0
        assert "已使用一枚跳过令牌" in result.output
        assert "船队在避风港暂歇" in result.output

    @patch("bestman.cli.BESTMAN_HOME")
    def test_skip_no_tokens(self, mock_home, mock_voyage, runner):
        """无令牌时 skip 显示提示。"""
        mock_home.is_dir.return_value = True
        mock_voyage["inst"].skip.return_value = {
            "success": False,
            "message": "没有可用的跳过令牌。连续打卡 7 天可获得一枚。",
            "tiles_revealed": 5,
            "log_entry": None,
            "error": "没有可用令牌",
        }

        result = runner.invoke(main, ["skip"])

        assert result.exit_code == 0
        assert "没有可用令牌" in result.output

    @patch("bestman.cli.BESTMAN_HOME")
    def test_skip_not_initialized(self, mock_home, runner):
        """未 init 时 skip 提示 init。"""
        mock_home.is_dir.return_value = False

        result = runner.invoke(main, ["skip"])

        assert result.exit_code == 1
        assert "尚未初始化" in result.output


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
        assert "skip" in result.output
        assert "log" in result.output
        assert "talk" in result.output

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

    def test_talk_help(self, runner):
        """bestman talk --help。"""
        result = runner.invoke(main, ["talk", "--help"])
        assert result.exit_code == 0
        assert "导航员" in result.output


class TestTalkCommand:
    """bestman talk 测试。"""

    @patch("bestman.cli.BESTMAN_HOME")
    def test_talk_single_message(self, mock_home, mock_voyage, runner):
        """talk -m 单次对话。"""
        mock_home.is_dir.return_value = True
        mock_voyage["inst"].talk.return_value = {
            "success": True,
            "response": "今天海面很平静，适合训练。",
            "error": None,
        }

        result = runner.invoke(main, ["talk", "-m", "今天感觉不错"])

        assert result.exit_code == 0
        assert "今天海面很平静" in result.output
        mock_voyage["inst"].talk.assert_called_once_with("今天感觉不错")

    @patch("bestman.cli.BESTMAN_HOME")
    def test_talk_llm_not_available(self, mock_home, mock_voyage, runner):
        """LLM 未配置时提示配置。"""
        mock_home.is_dir.return_value = True
        mock_voyage["inst"].llm.available = False

        result = runner.invoke(main, ["talk", "-m", "hello"])

        assert result.exit_code == 0
        assert "LLM 未配置" in result.output
        assert "OPENAI_API_KEY" in result.output
        mock_voyage["inst"].talk.assert_not_called()

    @patch("bestman.cli.BESTMAN_HOME")
    def test_talk_not_initialized(self, mock_home, runner):
        """未 init 时 talk 提示 init。"""
        mock_home.is_dir.return_value = False

        result = runner.invoke(main, ["talk"])

        assert result.exit_code == 1
        assert "尚未初始化" in result.output

    @patch("bestman.cli.BESTMAN_HOME")
    def test_talk_error_handling(self, mock_home, mock_voyage, runner):
        """talk 失败时显示错误消息。"""
        mock_home.is_dir.return_value = True
        mock_voyage["inst"].talk.return_value = {
            "success": False,
            "response": "导航员暂时无法回应。",
            "error": "LLM 请求失败",
        }

        result = runner.invoke(main, ["talk", "-m", "今天好累"])

        assert result.exit_code == 0
        assert "导航员暂时无法回应" in result.output


class TestConfigCommand:
    """bestman config 测试。"""

    @patch("bestman.cli.BESTMAN_HOME")
    @patch("bestman.cli.load_config")
    def test_config_dice_mode_show(self, mock_load, mock_home, runner):
        """config dice-mode 无参数时显示当前模式。"""
        mock_home.is_dir.return_value = True
        mock_load.return_value = {"dice": {"mode": "deterministic"}}

        result = runner.invoke(main, ["config", "dice-mode"])

        assert result.exit_code == 0
        assert "确定性" in result.output
        assert "deterministic" in result.output

    @patch("bestman.cli.BESTMAN_HOME")
    @patch("bestman.cli.load_config")
    def test_config_dice_mode_show_interactive(self, mock_load, mock_home, runner):
        """config dice-mode 显示互动模式。"""
        mock_home.is_dir.return_value = True
        mock_load.return_value = {"dice": {"mode": "interactive"}}

        result = runner.invoke(main, ["config", "dice-mode"])

        assert result.exit_code == 0
        assert "互动" in result.output
        assert "interactive" in result.output

    @patch("bestman.cli.BESTMAN_HOME")
    @patch("bestman.cli.save_config")
    @patch("bestman.cli.load_config")
    def test_config_dice_mode_set_interactive(self, mock_load, mock_save, mock_home, runner):
        """config dice-mode interactive 切换模式并显示成功。"""
        mock_home.is_dir.return_value = True
        mock_load.return_value = {"dice": {"mode": "deterministic"}}

        result = runner.invoke(main, ["config", "dice-mode", "interactive"])

        assert result.exit_code == 0
        mock_save.assert_called_once()
        assert "切换" in result.output

    @patch("bestman.cli.BESTMAN_HOME")
    def test_config_not_initialized(self, mock_home, runner):
        """未 init 时 config 提示 init。"""
        mock_home.is_dir.return_value = False

        result = runner.invoke(main, ["config", "dice-mode"])

        assert result.exit_code == 1
        assert "尚未初始化" in result.output


class TestDoneInteractiveMode:
    """bestman done --mode interactive 测试。"""

    @patch("bestman.cli.BESTMAN_HOME")
    @patch("bestman.cli._interactive_roll")
    def test_done_interactive_mode(self, mock_roll, mock_home, mock_voyage, runner):
        """互动模式下调用 _interactive_roll 并将结果传给 complete()。"""
        mock_home.is_dir.return_value = True
        mock_roll.return_value = 2

        result = runner.invoke(main, ["done", "--mode", "interactive"])

        assert result.exit_code == 0
        mock_roll.assert_called_once()
        mock_voyage["inst"].complete.assert_called_once()
        call_kwargs = mock_voyage["inst"].complete.call_args.kwargs
        assert call_kwargs["distance"] == 2

    @patch("bestman.cli.BESTMAN_HOME")
    @patch("bestman.cli._interactive_roll")
    def test_done_interactive_from_config(self, mock_roll, mock_home, mock_voyage, runner):
        """配置为 interactive 时即使不传 --mode 也用互动模式。"""
        mock_home.is_dir.return_value = True
        mock_roll.return_value = 3
        mock_voyage["inst"].config["dice"]["mode"] = "interactive"

        result = runner.invoke(main, ["done"])

        assert result.exit_code == 0
        mock_roll.assert_called_once()

    @patch("bestman.cli.BESTMAN_HOME")
    def test_done_deterministic_mode_explicit(self, mock_home, mock_voyage, runner):
        """--mode deterministic 覆盖配置，用确定性模式。"""
        mock_home.is_dir.return_value = True
        mock_voyage["inst"].config["dice"]["mode"] = "interactive"

        result = runner.invoke(main, ["done", "--mode", "deterministic"])

        assert result.exit_code == 0
        mock_voyage["inst"].complete.assert_called_once()
        assert "distance" not in mock_voyage["inst"].complete.call_args.kwargs
