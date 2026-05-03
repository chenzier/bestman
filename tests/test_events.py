"""test_events.py — EventEngine 测试。"""

import pytest

from bestman.events import EventEngine, DEFAULT_EVENTS


class TestEventEngineCheck:
    """check() 方法测试。"""

    def test_returns_event_or_none(self):
        """check() 返回 dict 或 None。"""
        engine = EventEngine()
        result = engine.check(1)
        assert result is None or isinstance(result, dict)

    def test_deterministic(self):
        """同一天永远返回同一事件（或不触发）。"""
        engine = EventEngine()
        results = [engine.check(7) for _ in range(10)]
        first = results[0]
        for r in results[1:]:
            assert r == first

    def test_different_days_may_differ(self):
        """不同天可能返回不同结果。"""
        engine = EventEngine()
        results = [engine.check(day) for day in range(1, 21)]
        # 20 天中至少有一个事件触发
        assert any(r is not None for r in results)

    def test_bonus_tile_is_returned(self):
        """bonus_tile 类型的事件有正确的字段。"""
        engine = EventEngine()
        # 用多个 day 来确保找到一个 bonus_tile 事件
        found = None
        for day in range(1, 200):
            result = engine.check(day)
            if result and result["type"] == "bonus_tile":
                found = result
                break
        assert found is not None
        assert "message" in found
        assert "id" in found

    def test_custom_events(self):
        """自定义事件列表替换默认。"""
        config = {
            "events": [
                {
                    "id": "test_event",
                    "type": "encouragement",
                    "probability": 1.0,
                    "message": "必定触发！",
                }
            ]
        }
        engine = EventEngine(config)
        result = engine.check(100)
        assert result is not None
        assert result["id"] == "test_event"
        assert result["type"] == "encouragement"

    def test_no_events_returns_none(self):
        """空事件列表永远返回 None。"""
        engine = EventEngine({"events": []})
        for day in range(1, 100):
            assert engine.check(day) is None

    def test_uses_default_events_when_no_config(self):
        """无 config 时使用 DEFAULT_EVENTS。"""
        engine = EventEngine()
        assert engine.events == DEFAULT_EVENTS
