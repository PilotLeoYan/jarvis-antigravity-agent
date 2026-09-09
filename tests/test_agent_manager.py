import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis_antigravity_agent.agent_manager import SubagentInfo, SubagentManager


class TestSubagentManager:
    def test_subagent_info_to_dict(self):
        now = time.time()
        info = SubagentInfo(
            agent_id="agy-123",
            name="TestAgent",
            prompt="do something",
            status="running",
            start_time=now,
            chat_id=999,
        )
        d = info.to_dict()
        assert d["agent_id"] == "agy-123"
        assert d["name"] == "TestAgent"
        assert d["status"] == "running"
        assert d["chat_id"] == 999

    def test_singleton_instance(self):
        m1 = SubagentManager.get_instance()
        m2 = SubagentManager.get_instance()
        assert m1 is m2

    def test_format_agents_summary_empty(self):
        manager = SubagentManager()
        summary = manager.format_agents_summary()
        assert "No subagents currently registered" in summary

    def test_format_agents_summary_with_agents(self):
        manager = SubagentManager()
        info = SubagentInfo(
            agent_id="agy-abc",
            name="AuditAgent",
            prompt="Run full repo audit",
            status="completed",
            start_time=time.time() - 10,
            end_time=time.time(),
        )
        manager._agents["agy-abc"] = info
        summary = manager.format_agents_summary()
        assert "AuditAgent" in summary
        assert "agy-abc" in summary
        assert "Run full repo audit" in summary

    def test_extract_response_text_from_stream_json(self):
        raw = (
            '{"event": "step", "step_update": {"state": "ACTIVE"}}\n'
            '{"event": "result", "result": {"response": "Final computed result"}}\n'
        )
        extracted = SubagentManager._extract_response_text(raw)
        assert extracted == "Final computed result"

    def test_extract_response_text_fallback_plain(self):
        raw = "Plain text response from subagent"
        assert SubagentManager._extract_response_text(raw) == raw

    @pytest.mark.anyio
    async def test_spawn_and_cancel_agent(self):
        import asyncio

        manager = SubagentManager()
        block_event = asyncio.Event()

        # Mock create_subprocess_exec
        mock_proc = MagicMock()
        mock_proc.pid = 4321
        mock_proc.returncode = None
        mock_proc.kill = MagicMock(side_effect=block_event.set)
        mock_proc.wait = AsyncMock(side_effect=block_event.wait)
        mock_proc.stdout = MagicMock()
        mock_proc.stdout.readline = AsyncMock(side_effect=[b"", b""])
        mock_proc.stderr = MagicMock()
        mock_proc.stderr.readline = AsyncMock(side_effect=[b"", b""])

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            agent = await manager.spawn_agent(
                prompt="Quick test task",
                name="QuickAgent",
                chat_id=12345,
            )
            assert agent.agent_id.startswith("agy-")
            assert agent.name == "QuickAgent"

            # Allow the background task to start and register proc
            await asyncio.sleep(0.01)

            # Cancel it
            cancelled = await manager.cancel_agent(agent.agent_id)
            assert cancelled is True
            assert agent.status == "cancelled"
            mock_proc.kill.assert_called_once()
