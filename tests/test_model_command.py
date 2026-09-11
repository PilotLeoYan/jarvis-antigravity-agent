import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import InlineKeyboardMarkup

from jarvis_antigravity_agent.agent_manager import SubagentManager
from jarvis_antigravity_agent.config import Settings, build_runtime_config
from jarvis_antigravity_agent.constants import Constants
from jarvis_antigravity_agent.executor import execute_agy_prompt
from jarvis_antigravity_agent.handlers import (
    BotHandlers,
    _find_gemini_model,
    _resolve_model_name,
)
from jarvis_antigravity_agent.messages import Messages


@pytest.fixture
def runtime_cfg():
    return {
        "bot_token": "123456:ABC-DEF",
        "allowed_users": {"12345"},
        "working_dir": "/tmp",
        "agy_path": "agy",
        "model": None,
        "effort": None,
        "default_flags": ["--dangerously-skip-permissions"],
        "default_chat_id": 12345,
    }


@pytest.fixture
def state():
    return {
        Constants.STATE_KEY_CONTINUE: False,
        Constants.STATE_KEY_MODEL: None,
        Constants.STATE_KEY_EFFORT: None,
    }


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


class TestModelCommand:
    @pytest.mark.anyio
    async def test_model_command_unauthorized(
        self, runtime_cfg, state, mock_update, mock_context
    ):
        mock_update.effective_user.id = 99999
        handlers = BotHandlers(runtime_cfg, state)
        await handlers.model_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_awaited_once_with(
            Messages.UNAUTHORIZED_ACCESS
        )

    @pytest.mark.anyio
    async def test_model_command_interactive_menu(
        self, runtime_cfg, state, mock_update, mock_context
    ):
        handlers = BotHandlers(runtime_cfg, state)
        await handlers.model_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_awaited_once()

        call_kwargs = mock_update.message.reply_text.call_args[1]
        sent_text = mock_update.message.reply_text.call_args[0][0]
        assert "Gemini Model & Thinking Effort Selection" in sent_text
        reply_markup = call_kwargs.get("reply_markup")
        assert isinstance(reply_markup, InlineKeyboardMarkup)

        callbacks = [
            btn.callback_data for row in reply_markup.inline_keyboard for btn in row
        ]
        assert "model:family:gemini-3.8-flash" in callbacks
        assert "model:family:gemini-3.7-flash" in callbacks
        assert "model:family:gemini-3.6-flash" in callbacks
        assert "model:family:gemini-3.1-pro" in callbacks
        assert "model:reset" in callbacks

    @pytest.mark.anyio
    async def test_model_command_list(
        self, runtime_cfg, state, mock_update, mock_context
    ):
        mock_context.args = ["list"]
        handlers = BotHandlers(runtime_cfg, state)
        await handlers.model_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_awaited_once()
        sent_text = mock_update.message.reply_text.call_args[0][0]
        assert "Available Gemini Models & Reasoning Efforts" in sent_text
        assert "Gemini 3.8 Flash" in sent_text
        assert "Gemini 3.1 Pro" in sent_text

    @pytest.mark.anyio
    async def test_model_command_status(
        self, runtime_cfg, state, mock_update, mock_context
    ):
        state[Constants.STATE_KEY_MODEL] = "gemini-3.8-flash-high"
        state[Constants.STATE_KEY_EFFORT] = "high"
        mock_context.args = ["status"]
        handlers = BotHandlers(runtime_cfg, state)
        await handlers.model_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_awaited_once()
        sent_text = mock_update.message.reply_text.call_args[0][0]
        assert "Current Gemini Model Configuration" in sent_text
        assert "gemini-3.8-flash-high" in sent_text
        assert "high" in sent_text

    @pytest.mark.anyio
    async def test_model_command_reset(
        self, runtime_cfg, state, mock_update, mock_context
    ):
        state[Constants.STATE_KEY_MODEL] = "gemini-3.8-flash-high"
        state[Constants.STATE_KEY_EFFORT] = "high"
        runtime_cfg["model"] = "gemini-3.8-flash-high"
        runtime_cfg["effort"] = "high"
        mock_context.args = ["reset"]

        handlers = BotHandlers(runtime_cfg, state)
        with patch("jarvis_antigravity_agent.handlers.save_state") as mock_save:
            await handlers.model_command(mock_update, mock_context)
            mock_save.assert_called_once()
            assert state.get(Constants.STATE_KEY_MODEL) is None
            assert state.get(Constants.STATE_KEY_EFFORT) is None
            assert runtime_cfg["model"] is None
            assert runtime_cfg["effort"] is None

        mock_update.message.reply_text.assert_awaited_once_with(
            Messages.MODEL_RESET_SUCCESS, parse_mode="Markdown"
        )

    @pytest.mark.anyio
    async def test_model_command_direct_family_and_effort(
        self, runtime_cfg, state, mock_update, mock_context
    ):
        mock_context.args = ["gemini-3.8-flash", "high"]
        handlers = BotHandlers(runtime_cfg, state)
        with patch("jarvis_antigravity_agent.handlers.save_state") as mock_save:
            await handlers.model_command(mock_update, mock_context)
            mock_save.assert_called_once()
            assert state[Constants.STATE_KEY_MODEL] == "gemini-3.8-flash-high"
            assert state[Constants.STATE_KEY_EFFORT] == "high"
            assert runtime_cfg["model"] == "gemini-3.8-flash-high"
            assert runtime_cfg["effort"] == "high"

        sent_text = mock_update.message.reply_text.call_args[0][0]
        assert "Model Configuration Updated" in sent_text
        assert "gemini-3.8-flash-high" in sent_text

    @pytest.mark.anyio
    async def test_model_command_direct_full_id(
        self, runtime_cfg, state, mock_update, mock_context
    ):
        mock_context.args = ["gemini-3.1-pro-high"]
        handlers = BotHandlers(runtime_cfg, state)
        with patch("jarvis_antigravity_agent.handlers.save_state") as mock_save:
            await handlers.model_command(mock_update, mock_context)
            mock_save.assert_called_once()
            assert state[Constants.STATE_KEY_MODEL] == "gemini-3.1-pro-high"
            assert state[Constants.STATE_KEY_EFFORT] == "high"

    @pytest.mark.anyio
    async def test_model_command_alias(
        self, runtime_cfg, state, mock_update, mock_context
    ):
        mock_context.args = ["3.8", "medium"]
        handlers = BotHandlers(runtime_cfg, state)
        with patch("jarvis_antigravity_agent.handlers.save_state"):
            await handlers.model_command(mock_update, mock_context)
            assert state[Constants.STATE_KEY_MODEL] == "gemini-3.8-flash-medium"
            assert state[Constants.STATE_KEY_EFFORT] == "medium"

    @pytest.mark.anyio
    async def test_model_command_invalid_model(
        self, runtime_cfg, state, mock_update, mock_context
    ):
        mock_context.args = ["nonexistent-model-xyz"]
        handlers = BotHandlers(runtime_cfg, state)
        await handlers.model_command(mock_update, mock_context)
        sent_text = mock_update.message.reply_text.call_args[0][0]
        assert "Unknown model `nonexistent-model-xyz`" in sent_text

    @pytest.mark.anyio
    async def test_model_command_invalid_effort_for_model(
        self, runtime_cfg, state, mock_update, mock_context
    ):
        # gemini-3.1-pro only supports high and low
        mock_context.args = ["gemini-3.1-pro", "medium"]
        handlers = BotHandlers(runtime_cfg, state)
        await handlers.model_command(mock_update, mock_context)
        sent_text = mock_update.message.reply_text.call_args[0][0]
        assert "Invalid effort `medium` for *Gemini 3.1 Pro*" in sent_text


class TestEffortCommand:
    @pytest.mark.anyio
    async def test_effort_command_interactive(
        self, runtime_cfg, state, mock_update, mock_context
    ):
        handlers = BotHandlers(runtime_cfg, state)
        await handlers.effort_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_awaited_once()
        call_kwargs = mock_update.message.reply_text.call_args[1]
        reply_markup = call_kwargs.get("reply_markup")
        assert isinstance(reply_markup, InlineKeyboardMarkup)
        callbacks = [
            btn.callback_data for row in reply_markup.inline_keyboard for btn in row
        ]
        assert "model:set:gemini-3.8-flash:high" in callbacks
        assert "model:set:gemini-3.8-flash:medium" in callbacks
        assert "model:set:gemini-3.8-flash:low" in callbacks

    @pytest.mark.anyio
    async def test_effort_command_set_valid(
        self, runtime_cfg, state, mock_update, mock_context
    ):
        state[Constants.STATE_KEY_MODEL] = "gemini-3.8-flash-high"
        mock_context.args = ["low"]
        handlers = BotHandlers(runtime_cfg, state)
        with patch("jarvis_antigravity_agent.handlers.save_state"):
            await handlers.effort_command(mock_update, mock_context)
            assert state[Constants.STATE_KEY_EFFORT] == "low"
            assert state[Constants.STATE_KEY_MODEL] == "gemini-3.8-flash-low"
            assert runtime_cfg["effort"] == "low"
            assert runtime_cfg["model"] == "gemini-3.8-flash-low"

        sent_text = mock_update.message.reply_text.call_args[0][0]
        assert "Reasoning effort set to *low*" in sent_text

    @pytest.mark.anyio
    async def test_effort_command_reset(
        self, runtime_cfg, state, mock_update, mock_context
    ):
        state[Constants.STATE_KEY_MODEL] = "gemini-3.8-flash-high"
        state[Constants.STATE_KEY_EFFORT] = "high"
        mock_context.args = ["auto"]
        handlers = BotHandlers(runtime_cfg, state)
        with patch("jarvis_antigravity_agent.handlers.save_state"):
            await handlers.effort_command(mock_update, mock_context)
            assert state[Constants.STATE_KEY_EFFORT] is None
            assert state[Constants.STATE_KEY_MODEL] == "gemini-3.8-flash"
            assert runtime_cfg["effort"] is None

        sent_text = mock_update.message.reply_text.call_args[0][0]
        assert "Reasoning effort reset to default" in sent_text

    @pytest.mark.anyio
    async def test_effort_command_invalid(
        self, runtime_cfg, state, mock_update, mock_context
    ):
        mock_context.args = ["ultra-super"]
        handlers = BotHandlers(runtime_cfg, state)
        await handlers.effort_command(mock_update, mock_context)
        sent_text = mock_update.message.reply_text.call_args[0][0]
        assert "/effort <low|medium|high|auto>" in sent_text


class TestModelCallbacks:
    @pytest.mark.anyio
    async def test_callback_unauthorized(self, runtime_cfg, state):
        query = MagicMock()
        query.from_user.id = 99999
        query.answer = AsyncMock()
        update = MagicMock()
        update.callback_query = query
        context = MagicMock()

        handlers = BotHandlers(runtime_cfg, state)
        await handlers.model_callback_handler(update, context)
        query.answer.assert_awaited_once_with("Unauthorized", show_alert=True)

    @pytest.mark.anyio
    async def test_callback_menu_navigation(self, runtime_cfg, state):
        query = MagicMock()
        query.from_user.id = 12345
        query.data = "model:menu"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update = MagicMock()
        update.callback_query = query
        context = MagicMock()

        handlers = BotHandlers(runtime_cfg, state)
        await handlers.model_callback_handler(update, context)
        query.answer.assert_awaited_once()
        query.edit_message_text.assert_awaited_once()
        sent_text = query.edit_message_text.call_args[1]["text"]
        assert "Gemini Model & Thinking Effort Selection" in sent_text

    @pytest.mark.anyio
    async def test_callback_family_selection(self, runtime_cfg, state):
        query = MagicMock()
        query.from_user.id = 12345
        query.data = "model:family:gemini-3.8-flash"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update = MagicMock()
        update.callback_query = query
        context = MagicMock()

        handlers = BotHandlers(runtime_cfg, state)
        await handlers.model_callback_handler(update, context)
        query.edit_message_text.assert_awaited_once()
        sent_text = query.edit_message_text.call_args[1]["text"]
        assert "Reasoning Effort for Gemini 3.8 Flash" in sent_text

        reply_markup = query.edit_message_text.call_args[1]["reply_markup"]
        callbacks = [
            btn.callback_data for row in reply_markup.inline_keyboard for btn in row
        ]
        assert "model:set:gemini-3.8-flash:high" in callbacks
        assert "model:set:gemini-3.8-flash:medium" in callbacks
        assert "model:set:gemini-3.8-flash:low" in callbacks
        assert "model:set:gemini-3.8-flash:default" in callbacks

    @pytest.mark.anyio
    async def test_callback_set_model_and_effort(self, runtime_cfg, state):
        query = MagicMock()
        query.from_user.id = 12345
        query.data = "model:set:gemini-3.8-flash:high"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update = MagicMock()
        update.callback_query = query
        context = MagicMock()

        handlers = BotHandlers(runtime_cfg, state)
        with patch("jarvis_antigravity_agent.handlers.save_state") as mock_save:
            await handlers.model_callback_handler(update, context)
            mock_save.assert_called_once()
            assert state[Constants.STATE_KEY_MODEL] == "gemini-3.8-flash-high"
            assert state[Constants.STATE_KEY_EFFORT] == "high"
            assert runtime_cfg["model"] == "gemini-3.8-flash-high"
            assert runtime_cfg["effort"] == "high"

        sent_text = query.edit_message_text.call_args[1]["text"]
        assert "Model Configuration Updated" in sent_text
        assert "gemini-3.8-flash-high" in sent_text

    @pytest.mark.anyio
    async def test_callback_reset(self, runtime_cfg, state):
        state[Constants.STATE_KEY_MODEL] = "gemini-3.8-flash-high"
        state[Constants.STATE_KEY_EFFORT] = "high"
        runtime_cfg["model"] = "gemini-3.8-flash-high"
        runtime_cfg["effort"] = "high"

        query = MagicMock()
        query.from_user.id = 12345
        query.data = "model:reset"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update = MagicMock()
        update.callback_query = query
        context = MagicMock()

        handlers = BotHandlers(runtime_cfg, state)
        with patch("jarvis_antigravity_agent.handlers.save_state"):
            await handlers.model_callback_handler(update, context)
            assert state.get(Constants.STATE_KEY_MODEL) is None
            assert state.get(Constants.STATE_KEY_EFFORT) is None
            assert runtime_cfg["model"] is None
            assert runtime_cfg["effort"] is None

        sent_text = query.edit_message_text.call_args[1]["text"]
        assert "Model Reset to Autonomous Default" in sent_text


class TestExecutorModelAndEffortFlags:
    @pytest.mark.anyio
    async def test_execute_agy_prompt_appends_model_and_effort(
        self, runtime_cfg, state, mock_update, mock_context
    ):
        state[Constants.STATE_KEY_MODEL] = "gemini-3.8-flash-high"
        state[Constants.STATE_KEY_EFFORT] = "high"

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout.readline = AsyncMock(side_effect=[b"", b""])
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        mock_save = MagicMock()

        with patch(
            "asyncio.create_subprocess_exec", return_value=mock_proc
        ) as mock_exec:
            with patch(
                "jarvis_antigravity_agent.executor.keep_typing",
                return_value=AsyncMock(),
            ):
                await execute_agy_prompt(
                    prompt="Hello world",
                    update=mock_update,
                    context=mock_context,
                    runtime_cfg=runtime_cfg,
                    state=state,
                    save_state_fn=mock_save,
                )

                mock_exec.assert_called_once()
                exec_cmd = mock_exec.call_args[0]
                assert "--model" in exec_cmd
                model_idx = exec_cmd.index("--model")
                assert exec_cmd[model_idx + 1] == "gemini-3.8-flash-high"

                assert "--effort" in exec_cmd
                effort_idx = exec_cmd.index("--effort")
                assert exec_cmd[effort_idx + 1] == "high"


class TestAgentManagerEffort:
    @pytest.mark.anyio
    async def test_spawn_agent_propagates_effort(self):
        manager = SubagentManager()
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_proc.returncode = 0
            mock_proc.stdout.readline = AsyncMock(side_effect=[b"", b""])
            mock_proc.stderr.readline = AsyncMock(side_effect=[b"", b""])
            mock_proc.wait = AsyncMock(return_value=0)
            mock_exec.return_value = mock_proc

            agent = await manager.spawn_agent(
                prompt="Explore architecture",
                model="gemini-3.8-flash-high",
                effort="high",
            )
            assert agent.status == "running"

            # Allow the task to run
            await asyncio.sleep(0.01)

            mock_exec.assert_called_once()
            cmd = mock_exec.call_args[0]
            assert "--model" in cmd
            assert cmd[cmd.index("--model") + 1] == "gemini-3.8-flash-high"
            assert "--effort" in cmd
            assert cmd[cmd.index("--effort") + 1] == "high"


class TestConfigAndResolvers:
    def test_settings_effort_mapping(self):
        settings = Settings(
            agy={"model": "gemini-3.8-flash", "effort": "high"},
            _ignore_config_file=True,
        )
        assert settings.model == "gemini-3.8-flash"
        assert settings.effort == "high"

        cfg = build_runtime_config({"effort": "medium", "model": "gemini-3.7-flash"})
        assert cfg["effort"] == "medium"
        assert cfg["model"] == "gemini-3.7-flash"

    def test_find_gemini_model_helpers(self):
        m = _find_gemini_model("gemini-3.8-flash")
        assert m is not None
        assert m["id"] == "gemini-3.8-flash"

        m_alias = _find_gemini_model("3.1")
        assert m_alias is not None
        assert m_alias["id"] == "gemini-3.1-pro"

        name = _resolve_model_name("gemini-3.8-flash-high")
        assert name == "Gemini 3.8 Flash"
