"""test_voyage.py — Voyage 类测试，全部使用 mock。

不依赖真实文件系统、SQLite 或外部服务。
"""

from datetime import date
from unittest.mock import ANY, MagicMock, patch

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
        patch("bestman.voyage.EventEngine") as mock_event_cls,
        patch("bestman.voyage.LLMClient") as mock_llm_cls,
        patch("bestman.voyage.get_log_entry") as mock_get_log,
        patch("bestman.voyage.generate_voyage_log") as mock_gen_log,
        patch("bestman.voyage.chat_with_coach") as mock_coach,
    ):
        # 配置 mock — dice weights [100, 0, 0] 保证测试确定性（永远掷出 1 格）
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
            },
            "coins": {
                "daily_complete": 10,
                "dice_3": 5,
                "extra_per_tile": 5,
                "streak_7": 25,
                "streak_30": 50,
                "milestone": 100,
            },
            "treasures": {
                "explicit": [
                    {
                        "name": "测试宝藏",
                        "position": 8,
                        "coins": 50,
                        "message": "你发现了一个测试宝藏！",
                    },
                ],
                "implicit": {
                    "pool": [
                        {
                            "name": "测试隐式宝藏",
                            "coins": 20,
                            "message": "隐式宝藏触发！",
                        },
                    ],
                    "probability": 0.0,  # 默认关闭，测试手动开启
                },
            },
            "dice": {
                "weights": [100, 0, 0],
                "descriptions": {
                    1: "风平浪静，缓缓前行",
                    2: "顺风满帆",
                    3: "暴风助力",
                },
            },
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
        mock_state.get_streak.return_value = 0
        mock_state.get_available_skip_tokens.return_value = 0
        mock_state.use_skip_token.return_value = False
        mock_state.get_total_coins.return_value = 0
        mock_state.get_treasures.return_value = []
        mock_state.get_active_overrides.return_value = []
        mock_state.get_latest_weight.return_value = None
        mock_state.get_weight_history.return_value = []
        mock_state_cls.return_value = mock_state

        # Map engine mock
        mock_map = MagicMock()
        mock_map.render.return_value = "MOCK_MAP_HERE"
        mock_map_cls.return_value = mock_map

        # Event engine mock
        mock_event = MagicMock()
        mock_event.check.return_value = None
        mock_event_cls.return_value = mock_event

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
            "event": mock_event,
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

    def test_get_status_includes_coins(self, mock_deps):
        """status 包含 coins 字段。"""
        mock_deps["state"].get_total_coins.return_value = 150

        voyage = Voyage()
        status = voyage.get_status()

        assert status["coins"] == 150

    def test_get_status_includes_treasures(self, mock_deps):
        """status 包含 treasures 字段。"""
        mock_treasures = [
            {"name": "沉船宝藏", "type": "explicit", "coins": 50, "discovered_date": "2026-05-03"},
        ]
        mock_deps["state"].get_treasures.return_value = mock_treasures

        voyage = Voyage()
        status = voyage.get_status()

        assert len(status["treasures"]) == 1
        assert status["treasures"][0]["name"] == "沉船宝藏"


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
        mock_deps["map"].render.assert_called_once_with(0, today_advance=0, sway_offset=0.0, sway_phase=0.0)
        assert result == "MOCK_MAP_HERE"


class TestComplete:
    """complete() 测试 — 掷骰子推进。"""

    def test_complete_success(self, mock_deps):
        """成功打卡路径：掷骰 1 格。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.side_effect = [0, 1]

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["success"] is True
        assert result["tiles_revealed"] == 1
        assert "掷出" in result["message"]
        assert "航行" in result["message"]
        assert result["log_entry"] is not None
        assert result["milestone"] is None
        assert result["error"] is None

        # 验证 state 调用
        mock_deps["state"].today_recorded.assert_called_with("2026-05-03")
        # record_day 被调用两次（preliminary + final），均含 coins_earned
        mock_deps["state"].record_day.assert_any_call(
            "2026-05-03", completed=1, extra=0, coins_earned=10
        )
        mock_deps["state"].save_log.assert_called_once()

    def test_complete_duplicate_rejected(self, mock_deps):
        """同日重复打卡被拒绝。"""
        mock_deps["state"].today_recorded.return_value = True

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["success"] is False
        assert result["error"] == "今日已经打卡"
        assert result["dice"] is None
        mock_deps["state"].record_day.assert_not_called()

    def test_complete_with_milestone(self, mock_deps):
        """跨越里程碑时返回里程碑信息。"""
        mock_deps["state"].today_recorded.return_value = False
        # old_tiles=4, dice=1 → new=5, crosses milestone 5
        mock_deps["state"].get_tiles_revealed.side_effect = [4, 5]

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["success"] is True
        assert result["milestone"] == "测试里程碑-A"
        assert result["tiles_revealed"] == 5

    def test_complete_multiple_milestones(self, mock_deps):
        """一次掷骰跨越多个里程碑。"""
        mock_deps["state"].today_recorded.return_value = False
        # old_tiles=3, dice + extra = 8 → crosses milestones 5 and 10
        mock_deps["state"].get_tiles_revealed.side_effect = [3, 10]

        voyage = Voyage()
        result = voyage.complete("2026-05-03", extra_tiles=7)

        assert result["success"] is True
        assert "测试里程碑-A" in result["milestone"]
        assert "测试里程碑-B" in result["milestone"]
        assert " | " in result["milestone"]

    def test_complete_default_date(self, mock_deps):
        """不传 date_str 时使用今天。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.side_effect = [0, 1]

        voyage = Voyage()
        result = voyage.complete()

        today = date.today().isoformat()
        mock_deps["state"].today_recorded.assert_called_with(today)
        assert result["success"] is True

    def test_complete_no_event(self, mock_deps):
        """无事件触发时 result['event'] 为 None。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.side_effect = [0, 1]
        mock_deps["event"].check.return_value = None

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["event"] is None
        mock_deps["event"].check.assert_called_once_with(1)

    def test_complete_with_bonus_tile_event(self, mock_deps):
        """bonus_tile 事件触发时额外推进 +1 格。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.side_effect = [0, 1]
        mock_event_data = {
            "id": "tailwind",
            "type": "bonus_tile",
            "probability": 0.15,
            "message": "顺风！",
        }
        mock_deps["event"].check.return_value = mock_event_data

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["event"] == mock_event_data
        assert result["tiles_revealed"] == 2  # 1 (dice) + 1 (bonus)
        mock_deps["state"].record_day.assert_any_call(
            "2026-05-03_bonus", completed=0, extra=1
        )
        mock_deps["state"].save_log.assert_any_call(
            "2026-05-03", "顺风！", event_type="event"
        )

    def test_complete_with_encouragement_event(self, mock_deps):
        """encouragement 事件触发，不推进格数但写日志。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.side_effect = [0, 1]
        mock_event_data = {
            "id": "dolphin_escort",
            "type": "encouragement",
            "probability": 0.10,
            "message": "海豚伴游！",
        }
        mock_deps["event"].check.return_value = mock_event_data

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["event"] == mock_event_data
        assert result["tiles_revealed"] == 1  # 没有额外推进
        mock_deps["state"].save_log.assert_any_call(
            "2026-05-03", "海豚伴游！", event_type="event"
        )

    def test_complete_with_challenge_event(self, mock_deps):
        """challenge 事件触发，不推进格数但写日志。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.side_effect = [0, 1]
        mock_event_data = {
            "id": "whale_challenge",
            "type": "challenge",
            "probability": 0.08,
            "message": "鲸群挑战！",
        }
        mock_deps["event"].check.return_value = mock_event_data

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["event"] == mock_event_data
        assert result["tiles_revealed"] == 1
        mock_deps["state"].save_log.assert_any_call(
            "2026-05-03", "鲸群挑战！", event_type="event"
        )

    def test_complete_with_manual_message(self, mock_deps):
        """-m 参数传入手动日志文本，跳过 LLM 和模板。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.side_effect = [0, 1]

        voyage = Voyage()
        result = voyage.complete("2026-05-03", message="今天下雨改室内，俯卧撑 50×3")

        assert result["success"] is True
        assert result["log_entry"] == "今天下雨改室内，俯卧撑 50×3"
        assert result["llm_used"] is False
        # 不应调用 LLM 或模板
        mock_deps["gen_log"].assert_not_called()
        mock_deps["get_log"].assert_not_called()


class TestCompleteCoins:
    """complete() 金币产出测试。"""

    def test_complete_returns_coins_breakdown(self, mock_deps):
        """成功打卡后 result 包含 coins 字段。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.side_effect = [0, 1]
        mock_deps["state"].get_streak.return_value = 0

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["success"] is True
        assert result["coins"] is not None
        assert result["coins"]["total"] == 10  # daily only
        assert "每日打卡" in result["coins"]["breakdown"]

    def test_complete_coins_dice_3_bonus(self, mock_deps):
        """掷骰 3 格时获得额外 5 金币。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.side_effect = [0, 3]
        mock_deps["state"].get_streak.return_value = 0
        # 修改 dice weights 让掷出 3
        mock_deps["config"]["dice"]["weights"] = [0, 0, 100]

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["coins"]["total"] == 15  # daily(10) + dice3(5)
        assert "暴风加成" in result["coins"]["breakdown"]

    def test_complete_coins_extra_tiles(self, mock_deps):
        """手动超额获得 5 金币/格。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.side_effect = [0, 3]
        mock_deps["state"].get_streak.return_value = 0

        voyage = Voyage()
        result = voyage.complete("2026-05-03", extra_tiles=2)

        assert result["coins"]["total"] == 20  # daily(10) + extra(5*2=10)
        assert "额外推进" in result["coins"]["breakdown"]

    def test_complete_coins_milestone(self, mock_deps):
        """跨越里程碑获得 100 金币。"""
        mock_deps["state"].today_recorded.return_value = False
        # old_tiles=4, dice=1 → crosses milestone at 5
        mock_deps["state"].get_tiles_revealed.side_effect = [4, 5]
        mock_deps["state"].get_streak.return_value = 0

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["coins"]["total"] == 110  # daily(10) + milestone(100)
        assert "里程碑" in result["coins"]["breakdown"]

    def test_complete_coins_explicit_treasure(self, mock_deps):
        """到达显式宝藏位置获得宝藏金币。"""
        mock_deps["state"].today_recorded.return_value = False
        # old_tiles=7, dice=1 → crosses treasure at position 8
        mock_deps["state"].get_tiles_revealed.side_effect = [7, 8]
        mock_deps["state"].get_streak.return_value = 0

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["coins"]["total"] == 60  # daily(10) + treasure(50)
        assert len(result["treasures"]) == 1
        assert result["treasures"][0]["name"] == "测试宝藏"
        assert result["treasures"][0]["coins"] == 50

    def test_complete_explicit_treasure_not_crossed(self, mock_deps):
        """未到达宝藏位置时不触发宝藏。"""
        mock_deps["state"].today_recorded.return_value = False
        # old_tiles=3, dice=1 → reaches 4, treasure at 8 not crossed
        mock_deps["state"].get_tiles_revealed.side_effect = [3, 4]
        mock_deps["state"].get_streak.return_value = 0

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["treasures"] == []
        assert result["coins"]["total"] == 10  # daily only

    def test_complete_implicit_treasure_triggered(self, mock_deps):
        """隐式宝藏概率 100% 时必定触发。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.side_effect = [0, 1]
        mock_deps["state"].get_streak.return_value = 0
        # 将隐式宝藏概率设为 1.0
        mock_deps["config"]["treasures"]["implicit"]["probability"] = 1.0

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert len(result["treasures"]) == 1
        assert result["treasures"][0]["type"] == "implicit"
        assert result["treasures"][0]["coins"] == 20
        assert result["coins"]["total"] == 30  # daily(10) + implicit treasure(20)

    def test_complete_treasure_persisted(self, mock_deps):
        """发现宝藏后调用 discover_treasure 持久化。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.side_effect = [7, 8]  # crosses position 8
        mock_deps["state"].get_streak.return_value = 0

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        mock_deps["state"].discover_treasure.assert_called_once_with(
            "测试宝藏", "explicit", 50, "2026-05-03"
        )

    def test_complete_treasure_saves_log(self, mock_deps):
        """发现宝藏后写入 voyage_logs。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.side_effect = [7, 8]
        mock_deps["state"].get_streak.return_value = 0

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        # Check save_log was called with treasure_found event_type
        treasure_calls = [
            call for call in mock_deps["state"].save_log.call_args_list
            if (len(call.args) > 2 and call.args[2] == "treasure_found")
            or call.kwargs.get("event_type") == "treasure_found"
        ]
        assert len(treasure_calls) == 1

    def test_complete_coins_streak_7(self, mock_deps):
        """连击 7 天获得额外 25 金币。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.side_effect = [0, 1]
        mock_deps["state"].get_streak.return_value = 7

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["coins"]["total"] == 35  # daily(10) + streak_7(25)
        assert "连击7天" in result["coins"]["breakdown"]

    def test_complete_coins_streak_30(self, mock_deps):
        """连击 30 天获得额外 50 金币。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.side_effect = [0, 1]
        mock_deps["state"].get_streak.return_value = 30

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["coins"]["total"] == 60  # daily(10) + streak_30(50)
        assert "连击30天" in result["coins"]["breakdown"]

    def test_complete_no_coins_on_duplicate(self, mock_deps):
        """重复打卡时 coins 为 None。"""
        mock_deps["state"].today_recorded.return_value = True

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["coins"] is None


class TestCompleteStreakAward:
    """complete() 连击奖励测试。"""

    def test_awards_token_on_streak_seven(self, mock_deps):
        """连击达到 7 天时发放跳过令牌。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.side_effect = [0, 1]
        mock_deps["state"].get_streak.return_value = 7

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["success"] is True
        mock_deps["state"].add_skip_token.assert_called_once_with("2026-05-03")

    def test_no_token_below_streak_seven(self, mock_deps):
        """连击不足 7 天时不发放令牌。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.side_effect = [0, 1]
        mock_deps["state"].get_streak.return_value = 6

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["success"] is True
        mock_deps["state"].add_skip_token.assert_not_called()


class TestDiceRolling:
    """掷骰子专属测试。"""

    def test_dice_info_in_result(self, mock_deps):
        """result['dice'] 包含距离、描述和额外格数。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.side_effect = [0, 1]

        voyage = Voyage()
        result = voyage.complete("2026-05-03")

        assert result["dice"] is not None
        assert result["dice"]["distance"] == 1
        assert "风平浪静" in result["dice"]["description"]
        assert result["dice"]["extra_tiles"] == 0

    def test_extra_tiles_stacked_on_dice(self, mock_deps):
        """-e 参数叠加在掷骰结果上。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.side_effect = [10, 13]

        voyage = Voyage()
        result = voyage.complete("2026-05-03", extra_tiles=2)

        assert result["success"] is True
        assert result["tiles_revealed"] == 13  # 10 + 1 (dice) + 2 (extra)
        assert result["dice"]["distance"] == 1
        assert result["dice"]["extra_tiles"] == 2
        # record_day 的 completed = dice + extra，coins = 10(daily) + 5*2(extra)
        mock_deps["state"].record_day.assert_any_call(
            "2026-05-03", completed=3, extra=0, coins_earned=20
        )
        assert "航行 3 海里" in result["message"]

    def test_dice_deterministic_same_date(self, mock_deps):
        """同一天多次掷骰结果确定一致（即使 mock 不同）。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.side_effect = [0, 1]

        voyage = Voyage()
        d1, desc1 = voyage._roll_distance("2026-05-03")
        d2, desc2 = voyage._roll_distance("2026-05-03")

        assert d1 == d2
        assert desc1 == desc2

    def test_dice_different_dates_differ(self, mock_deps):
        """不同天掷骰结果通常不同。"""
        voyage = Voyage()
        d1, _ = voyage._roll_distance("2026-05-03")
        d2, _ = voyage._roll_distance("2026-05-04")

        # 两天的结果不一定不同，但概率极高；只验证两者都是合法距离
        assert d1 in (1, 2, 3)
        assert d2 in (1, 2, 3)

    def test_dice_from_config_weights(self, mock_deps):
        """修改 weights 配置可改变掷骰分布。"""
        mock_deps["config"]["dice"]["weights"] = [0, 100, 0]
        voyage = Voyage()
        distance, desc = voyage._roll_distance("2026-05-03")
        assert distance == 2

    def test_dice_minimum_one_tile(self, mock_deps):
        """最差情况（每天 1 格）正好在 total_days 内到达。"""
        mock_deps["config"]["dice"]["weights"] = [100, 0, 0]

        voyage = Voyage()
        # 175 天每天 1 格 = 175 格
        for day_offset in range(175):
            date_str = f"2026-05-{(3 + day_offset):02d}" if day_offset < 28 else f"2026-06-{((3 + day_offset - 31)):02d}"
            distance, _ = voyage._roll_distance(date_str)
            assert distance == 1

    def test_dice_max_three_tiles(self, mock_deps):
        """最快情况每天 3 格。"""
        mock_deps["config"]["dice"]["weights"] = [0, 0, 100]
        voyage = Voyage()
        distance, _ = voyage._roll_distance("2026-05-03")
        assert distance == 3


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


class TestCompleteWithLLM:
    """LLM 日志生成测试。"""

    def test_complete_uses_llm_when_available(self, mock_deps):
        """LLM 可用时使用 LLM 生成日志。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.side_effect = [0, 1]
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
        mock_deps["state"].get_tiles_revealed.side_effect = [0, 1]
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
        assert result["dice"] is None


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


class TestCompleteWithDistance:
    """complete(distance=N) 互动模式测试。"""

    def test_complete_with_distance_skips_roll(self, mock_deps):
        """传入 distance 时跳过 _roll_distance，直接使用给定值。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.side_effect = [0, 3]

        voyage = Voyage()
        result = voyage.complete("2026-05-03", distance=3)

        assert result["success"] is True
        assert result["tiles_revealed"] == 3
        assert result["dice"]["distance"] == 3
        assert result["dice"]["extra_tiles"] == 0
        assert "暴风助力" in result["dice"]["description"]

    def test_complete_with_distance_and_extra(self, mock_deps):
        """distance + extra_tiles 正确叠加。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.side_effect = [5, 9]

        voyage = Voyage()
        result = voyage.complete("2026-05-03", extra_tiles=2, distance=2)

        assert result["success"] is True
        assert result["tiles_revealed"] == 9
        assert result["dice"]["distance"] == 2
        assert result["dice"]["extra_tiles"] == 2
        assert "航行 4 海里" in result["message"]
        mock_deps["state"].record_day.assert_any_call(
            "2026-05-03", completed=4, extra=0, coins_earned=ANY
        )

    def test_complete_with_distance_duplicate_rejected(self, mock_deps):
        """互动模式下重复打卡仍然被拒绝。"""
        mock_deps["state"].today_recorded.return_value = True

        voyage = Voyage()
        result = voyage.complete("2026-05-03", distance=2)

        assert result["success"] is False
        assert result["error"] == "今日已经打卡"
        mock_deps["state"].record_day.assert_not_called()

    def test_complete_with_distance_default_date(self, mock_deps):
        """不传 date_str 时使用今天。"""
        mock_deps["state"].today_recorded.return_value = False
        mock_deps["state"].get_tiles_revealed.side_effect = [0, 1]

        voyage = Voyage()
        result = voyage.complete(distance=1)

        today = date.today().isoformat()
        mock_deps["state"].today_recorded.assert_called_with(today)
        assert result["success"] is True


class TestGetDistanceDescription:
    """_get_distance_description() 测试。"""

    def test_get_description_one(self, mock_deps):
        """距离 1 的描述。"""
        voyage = Voyage()
        desc = voyage._get_distance_description(1)
        assert "风平浪静" in desc

    def test_get_description_two(self, mock_deps):
        """距离 2 的描述。"""
        voyage = Voyage()
        desc = voyage._get_distance_description(2)
        assert "顺风满帆" in desc

    def test_get_description_three(self, mock_deps):
        """距离 3 的描述。"""
        voyage = Voyage()
        desc = voyage._get_distance_description(3)
        assert "暴风助力" in desc

    def test_get_description_fallback(self, mock_deps):
        """不支持的 distance 值返回 fallback 文本。"""
        mock_deps["config"]["dice"]["descriptions"] = {}
        voyage = Voyage()
        desc = voyage._get_distance_description(5)
        assert "航行 5 格" in desc
