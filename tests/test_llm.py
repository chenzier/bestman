"""test_llm.py — LLM 客户端和 prompt 函数测试。

全部使用 mock，不依赖真实 API 调用。
"""

from unittest.mock import MagicMock, patch

import pytest

from bestman.llm import LLMClient, generate_voyage_log, chat_with_coach, COACH_SYSTEM_PROMPT


class TestLLMClientInit:
    """LLMClient.__init__() 测试。"""

    def test_creates_openai_client_when_key_provided(self):
        """有效 API key 时创建 OpenAI 客户端。"""
        with patch("bestman.llm.OpenAI") as mock_openai:
            client = LLMClient(
                api_key="sk-real-key",
                base_url="https://api.deepseek.com",
                model="deepseek-v4-pro",
            )
            mock_openai.assert_called_once_with(
                api_key="sk-real-key",
                base_url="https://api.deepseek.com",
            )
            assert client.available is True
            assert client.model == "deepseek-v4-pro"

    def test_does_not_create_client_for_placeholder_key(self):
        """sk-placeholder 时不创建客户端。"""
        with patch("bestman.llm.OpenAI") as mock_openai:
            client = LLMClient(
                api_key="sk-placeholder",
                base_url="https://api.deepseek.com",
                model="deepseek-v4-pro",
            )
            mock_openai.assert_not_called()
            assert client.available is False

    def test_does_not_create_client_for_empty_key(self):
        """空 API key 时不创建客户端。"""
        with patch("bestman.llm.OpenAI") as mock_openai:
            client = LLMClient(
                api_key="",
                base_url="https://api.openai.com/v1",
                model="gpt-4o-mini",
            )
            mock_openai.assert_not_called()
            assert client.available is False


class TestLLMClientChat:
    """LLMClient.chat() 测试。"""

    def test_chat_returns_none_when_not_available(self):
        """LLM 不可用时返回 None。"""
        client = LLMClient(api_key="", base_url="", model="test")
        result = client.chat([{"role": "user", "content": "Hello"}])
        assert result is None

    def test_chat_returns_content_when_available(self):
        """LLM 可用时返回内容。"""
        with patch("bestman.llm.OpenAI") as mock_openai:
            mock_client = mock_openai.return_value
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "生成的内容"
            mock_client.chat.completions.create.return_value = mock_response

            client = LLMClient(
                api_key="sk-real-key",
                base_url="https://api.deepseek.com",
                model="deepseek-v4-pro",
            )
            result = client.chat([{"role": "user", "content": "Hello"}])
            assert result == "生成的内容"
            mock_client.chat.completions.create.assert_called_once()

    def test_chat_handles_api_error(self):
        """API 错误时返回 None。"""
        with patch("bestman.llm.OpenAI") as mock_openai:
            mock_client = mock_openai.return_value
            mock_client.chat.completions.create.side_effect = Exception("API Error")

            client = LLMClient(
                api_key="sk-real-key",
                base_url="https://api.deepseek.com",
                model="deepseek-v4-pro",
            )
            result = client.chat([{"role": "user", "content": "Hello"}])
            assert result is None

    def test_chat_passes_temperature_and_max_tokens(self):
        """chat() 传递温度值和 max_tokens 参数。"""
        with patch("bestman.llm.OpenAI") as mock_openai:
            mock_client = mock_openai.return_value
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "ok"
            mock_client.chat.completions.create.return_value = mock_response

            client = LLMClient(
                api_key="sk-real-key",
                base_url="https://api.deepseek.com",
                model="deepseek-v4-pro",
            )
            client.chat(
                [{"role": "user", "content": "Hello"}],
                temperature=0.5,
                max_tokens=200,
            )
            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert call_kwargs["temperature"] == 0.5
            assert call_kwargs["max_tokens"] == 200
            assert call_kwargs["model"] == "deepseek-v4-pro"


class TestGenerateVoyageLog:
    """generate_voyage_log() 测试。"""

    def test_returns_none_when_not_available(self):
        """LLM 不可用时返回 None。"""
        client = LLMClient(api_key="", base_url="", model="test")
        result = generate_voyage_log(client, "启航", 174, 1, "死虫式 3×10")
        assert result is None

    def test_calls_chat_with_correct_prompt(self):
        """构建正确的 prompt 并调用 chat()。"""
        with patch("bestman.llm.OpenAI") as mock_openai:
            mock_inst = mock_openai.return_value
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "日志内容"
            mock_inst.chat.completions.create.return_value = mock_response

            client = LLMClient(
                api_key="sk-real",
                base_url="https://api.deepseek.com",
                model="deepseek-v4-pro",
            )
            result = generate_voyage_log(client, "季风带", 128, 47, "静蹲 2×30秒")

            assert result == "日志内容"
            # 验证传给 API 的 messages 内容
            call_args = mock_inst.chat.completions.create.call_args
            messages = call_args.kwargs["messages"]
            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert "航海日志官" in messages[0]["content"]
            assert messages[1]["role"] == "user"
            assert "47" in messages[1]["content"]
            assert "季风带" in messages[1]["content"]
            assert "静蹲" in messages[1]["content"]


class TestChatWithCoach:
    """chat_with_coach() 测试。"""

    def test_returns_none_when_not_available(self):
        """LLM 不可用时返回 None。"""
        client = LLMClient(api_key="", base_url="", model="test")
        context = {
            "current_day": 10,
            "stage_name": "启航",
            "remaining": 165,
            "today_done": False,
            "today_task": "死虫式",
            "completed_days": 9,
        }
        result = chat_with_coach(client, "今天好累", context)
        assert result is None

    def test_calls_chat_with_coach_prompt(self):
        """构建教练 prompt + 上下文并调用 chat()。"""
        with patch("bestman.llm.OpenAI") as mock_openai:
            mock_inst = mock_openai.return_value
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "慢慢来，水手。"
            mock_inst.chat.completions.create.return_value = mock_response

            client = LLMClient(
                api_key="sk-real",
                base_url="https://api.deepseek.com",
                model="deepseek-v4-pro",
            )
            context = {
                "current_day": 47,
                "stage_name": "季风带",
                "remaining": 128,
                "today_done": True,
                "today_task": "死虫式 3×10 + 静蹲 2×30秒",
                "completed_days": 45,
            }
            result = chat_with_coach(client, "今天腿有点酸", context)

            assert result == "慢慢来，水手。"
            call_args = mock_inst.chat.completions.create.call_args
            messages = call_args.kwargs["messages"]
            assert len(messages) == 3
            assert messages[0]["role"] == "system"
            assert "导航员" in messages[0]["content"]
            assert messages[1]["role"] == "system"
            assert "47" in messages[1]["content"]
            assert "季风带" in messages[1]["content"]
            assert messages[2]["role"] == "user"
            assert messages[2]["content"] == "今天腿有点酸"

    def test_coach_prompt_has_core_rules(self):
        """教练 system prompt 包含核心规则。"""
        assert "完成 > 完美" in COACH_SYSTEM_PROMPT
        assert "不施压" in COACH_SYSTEM_PROMPT
        assert "航海" in COACH_SYSTEM_PROMPT
