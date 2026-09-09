from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis_antigravity_agent.handlers import BotHandlers
from jarvis_antigravity_agent.messages import Messages


@pytest.fixture
def runtime_cfg():
    return {
        "bot_token": "123456:ABC-DEF",
        "allowed_users": {"12345"},
        "working_dir": "/tmp",
        "agy_path": "agy",
        "model": "Gemini 3.1 Pro (High)",
        "default_flags": ["--dangerously-skip-permissions"],
        "default_chat_id": 12345,
    }


@pytest.fixture
def state():
    return {"continue_session": True}


@pytest.fixture
def mock_update():
    update = MagicMock()
    update.effective_user.id = 12345
    update.effective_chat.id = 12345
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.args = []
    return context


class TestBotHandlersEnglishCommands:
    @pytest.mark.anyio
    async def test_start_command_authorized(
        self, runtime_cfg, state, mock_update, mock_context
    ):
        handlers = BotHandlers(runtime_cfg, state)
        await handlers.start_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_awaited_once()
        sent_text = mock_update.message.reply_text.call_args[0][0]
        assert "Welcome to Jarvis" in sent_text
        assert "/quotas" in sent_text
        assert "/skills" in sent_text
        assert "/mcps" in sent_text

    @pytest.mark.anyio
    async def test_start_command_unauthorized(
        self, runtime_cfg, state, mock_update, mock_context
    ):
        mock_update.effective_user.id = 99999
        handlers = BotHandlers(runtime_cfg, state)
        await handlers.start_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_awaited_once_with(
            Messages.UNAUTHORIZED_ACCESS
        )

    @pytest.mark.anyio
    async def test_help_command(self, runtime_cfg, state, mock_update, mock_context):
        handlers = BotHandlers(runtime_cfg, state)
        await handlers.help_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_awaited_once()
        sent_text = mock_update.message.reply_text.call_args[0][0]
        assert "Jarvis — Antigravity Assistant" in sent_text
        assert "/quotas" in sent_text
        assert "/skills" in sent_text
        assert "/mcps" in sent_text
        assert "/nuevo" not in sent_text
        assert "/ayuda" not in sent_text

    @pytest.mark.anyio
    async def test_quotas_command(self, runtime_cfg, state, mock_update, mock_context):
        handlers = BotHandlers(runtime_cfg, state)
        with patch(
            "jarvis_antigravity_agent.handlers.get_agy_quotas",
            return_value={"groups": [{"displayName": "Gemini", "buckets": []}]},
        ):
            await handlers.quotas_command(mock_update, mock_context)
            mock_update.message.reply_text.assert_awaited_once()
            sent_text = mock_update.message.reply_text.call_args[0][0]
            assert "Google Antigravity Quotas & Limits" in sent_text

    @pytest.mark.anyio
    async def test_skills_command(self, runtime_cfg, state, mock_update, mock_context):
        handlers = BotHandlers(runtime_cfg, state)
        with patch(
            "jarvis_antigravity_agent.handlers.format_skills_markdown",
            return_value="🧠 Mocked Global Skills Output",
        ):
            await handlers.skills_command(mock_update, mock_context)
            mock_update.message.reply_text.assert_awaited_once_with(
                "🧠 Mocked Global Skills Output", parse_mode="Markdown"
            )

    @pytest.mark.anyio
    async def test_mcps_command(self, runtime_cfg, state, mock_update, mock_context):
        handlers = BotHandlers(runtime_cfg, state)
        with patch(
            "jarvis_antigravity_agent.handlers.format_global_mcp_status",
            return_value="🔌 Mocked Global MCP Status Output",
        ):
            await handlers.mcps_command(mock_update, mock_context)
            mock_update.message.reply_text.assert_awaited_once_with(
                "🔌 Mocked Global MCP Status Output", parse_mode="Markdown"
            )

    @pytest.mark.anyio
    async def test_new_command_resets_state(
        self, runtime_cfg, state, mock_update, mock_context
    ):
        handlers = BotHandlers(runtime_cfg, state)
        await handlers.new_command(mock_update, mock_context)
        assert state["continue_session"] is False
        mock_update.message.reply_text.assert_awaited_once_with(
            Messages.CONTEXT_RESET, parse_mode="Markdown"
        )

    @pytest.mark.anyio
    async def test_skills_command_markdown_failure_fallback(
        self, runtime_cfg, state, mock_update, mock_context
    ):
        handlers = BotHandlers(runtime_cfg, state)
        mock_update.message.reply_text.side_effect = [
            Exception("Can't parse entities"),
            AsyncMock(),
        ]
        with patch(
            "jarvis_antigravity_agent.handlers.format_skills_markdown",
            return_value="🧠 Sample Skill with *broken _entities",
        ):
            await handlers.skills_command(mock_update, mock_context)
            assert mock_update.message.reply_text.call_count == 2
            second_call = mock_update.message.reply_text.call_args_list[1]
            assert "🧠 Sample Skill with *broken _entities" in second_call[0][0]
