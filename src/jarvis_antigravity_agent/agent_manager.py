import argparse
import asyncio
import logging
import os
import shutil
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from jarvis_antigravity_agent.config import build_runtime_config, get_settings
from jarvis_antigravity_agent.constants import Constants
from jarvis_antigravity_agent.notifier import send_telegram_chunk
from jarvis_antigravity_agent.utils import split_message

logger = logging.getLogger(Constants.LOGGER_NAME)


@dataclass
class SubagentInfo:
    agent_id: str
    name: str
    prompt: str
    status: str  # "running", "completed", "failed", "cancelled"
    start_time: float
    end_time: float | None = None
    chat_id: int | str | None = None
    pid: int | None = None
    output: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SubagentManager:
    """Manages background autonomous Antigravity (agy) subagent tasks."""

    _instance: "SubagentManager | None" = None

    def __init__(self) -> None:
        self._agents: dict[str, SubagentInfo] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._processes: dict[str, asyncio.subprocess.Process] = {}

    @classmethod
    def get_instance(cls) -> "SubagentManager":
        if cls._instance is None:
            cls._instance = SubagentManager()
        return cls._instance

    def list_agents(self) -> list[SubagentInfo]:
        return sorted(self._agents.values(), key=lambda a: a.start_time, reverse=True)

    def get_agent(self, agent_id: str) -> SubagentInfo | None:
        return self._agents.get(agent_id)

    async def cancel_agent(self, agent_id: str) -> bool:
        agent = self._agents.get(agent_id)
        if not agent or agent.status != "running":
            return False

        proc = self._processes.get(agent_id)
        if proc and proc.returncode is None:
            try:
                proc.kill()
            except Exception as e:
                logger.debug("Failed to kill subagent process %s: %s", agent_id, e)

        task = self._tasks.get(agent_id)
        if task and not task.done():
            task.cancel()

        agent.status = "cancelled"
        agent.end_time = time.time()
        logger.info("Subagent %s (%s) was cancelled", agent_id, agent.name)
        return True

    async def spawn_agent(
        self,
        prompt: str,
        name: str | None = None,
        chat_id: int | str | None = None,
        working_dir: str | None = None,
        model: str | None = None,
        timeout: float = Constants.AGY_PROCESS_TIMEOUT,
    ) -> SubagentInfo:
        short_id = uuid.uuid4().hex[:8]
        agent_id = f"agy-{short_id}"
        agent_name = name.strip() if name and name.strip() else f"agent-{short_id}"

        settings = get_settings()
        runtime_cfg = build_runtime_config()

        target_chat = chat_id or runtime_cfg.get("default_chat_id")
        target_work_dir = working_dir or runtime_cfg.get(
            "working_dir", Constants.DEFAULT_WORKING_DIR
        )
        target_model = model or runtime_cfg.get("model") or Constants.AGY_DEFAULT_MODEL
        agy_path = (
            runtime_cfg.get("agy_path")
            or shutil.which("agy")
            or Constants.AGY_FALLBACK_BIN
        )

        agent_info = SubagentInfo(
            agent_id=agent_id,
            name=agent_name,
            prompt=prompt,
            status="running",
            start_time=time.time(),
            chat_id=target_chat,
        )
        self._agents[agent_id] = agent_info

        cmd = [
            agy_path,
            *runtime_cfg.get("default_flags", Constants.AGY_DEFAULT_FLAGS),
            Constants.AGY_OUTPUT_FORMAT_FLAG,
            Constants.AGY_OUTPUT_FORMAT,
        ]
        if target_model:
            cmd.extend([Constants.AGY_MODEL_FLAG, target_model])
        cmd.extend([Constants.AGY_PROMPT_FLAG, prompt])

        task = asyncio.create_task(
            self._run_subagent(
                agent_info=agent_info,
                cmd=cmd,
                working_dir=target_work_dir,
                timeout=timeout,
                bot_token=settings.telegram.bot_token,
            )
        )
        self._tasks[agent_id] = task
        logger.info(
            "Spawned autonomous subagent %s (%s) with model %s",
            agent_id,
            agent_name,
            target_model,
        )
        return agent_info

    async def _run_subagent(
        self,
        agent_info: SubagentInfo,
        cmd: list[str],
        working_dir: str,
        timeout: float,
        bot_token: str | None,
    ) -> None:
        agent_id = agent_info.agent_id
        path_extra = Constants.PATH_EXTRA
        local_bin = Constants.AGY_LOCAL_BIN
        env = os.environ.copy()
        env["PATH"] = f"{local_bin}:{path_extra}:{env.get('PATH', '')}"

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=working_dir,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._processes[agent_id] = proc
            agent_info.pid = proc.pid

            async def read_stdout() -> None:
                if proc.stdout:
                    while True:
                        line = await proc.stdout.readline()
                        if not line:
                            break
                        decoded = line.decode("utf-8", errors="replace").strip()
                        if decoded:
                            stdout_lines.append(decoded)

            async def read_stderr() -> None:
                if proc.stderr:
                    while True:
                        line = await proc.stderr.readline()
                        if not line:
                            break
                        decoded = line.decode("utf-8", errors="replace").strip()
                        if decoded:
                            stderr_lines.append(decoded)

            try:
                await asyncio.wait_for(
                    asyncio.gather(read_stdout(), read_stderr(), proc.wait()),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                if proc.returncode is None:
                    proc.kill()
                agent_info.status = "failed"
                agent_info.error = f"Subagent timed out after {int(timeout)}s."
                logger.warning("Subagent %s timed out", agent_id)

            agent_info.end_time = time.time()
            if agent_info.status != "failed" and agent_info.status != "cancelled":
                if proc.returncode == 0:
                    agent_info.status = "completed"
                else:
                    agent_info.status = "failed"

            # Parse outputs
            full_out = "\n".join(stdout_lines).strip()
            full_err = "\n".join(stderr_lines).strip()
            agent_info.output = full_out
            agent_info.error = full_err

            # Deliver completion notification to Telegram
            if agent_info.chat_id and bot_token:
                await self._notify_telegram(agent_info, bot_token)

        except asyncio.CancelledError:
            agent_info.status = "cancelled"
            agent_info.end_time = time.time()
        except Exception as e:
            agent_info.status = "failed"
            agent_info.end_time = time.time()
            agent_info.error = str(e)
            logger.exception("Error executing subagent %s: %s", agent_id, e)
            if agent_info.chat_id and bot_token:
                await self._notify_telegram(agent_info, bot_token)
        finally:
            self._processes.pop(agent_id, None)
            self._tasks.pop(agent_id, None)

    async def _notify_telegram(self, agent_info: SubagentInfo, bot_token: str) -> None:
        elapsed = (
            (agent_info.end_time - agent_info.start_time)
            if agent_info.end_time
            else 0.0
        )
        status_emoji = "✅" if agent_info.status == "completed" else "⚠️"
        header = (
            f"{status_emoji} *Autonomous Subagent Finished: {agent_info.name}*\n"
            f"• Agent ID: `{agent_info.agent_id}`\n"
            f"• Status: *{agent_info.status.upper()}*\n"
            f"• Duration: `{elapsed:.1f}s`\n"
        )

        content = agent_info.output or agent_info.error or "(No text output)"
        # Try to extract cleanest response text if stream-json
        clean_text = self._extract_response_text(content)

        full_message = f"{header}\n{clean_text}"
        chunks = split_message(full_message)
        for chunk in chunks:
            try:
                await asyncio.to_thread(
                    send_telegram_chunk, bot_token, agent_info.chat_id, chunk
                )
            except Exception as e:
                logger.debug("Failed to deliver subagent Telegram notification: %s", e)

    @staticmethod
    def _extract_response_text(raw_output: str) -> str:
        """Extract clean result response if output contains stream-json."""
        import json

        lines = raw_output.split("\n")
        for line in reversed(lines):
            line_s = line.strip()
            if line_s.startswith("{") and line_s.endswith("}"):
                try:
                    data = json.loads(line_s)
                    if data.get("event") == "result":
                        resp = str(data.get("result", {}).get("response", "")).strip()
                        if resp:
                            return resp
                except Exception as e:
                    logger.debug("Failed to parse stream json line: %s", e)
        return raw_output

    def format_agents_summary(self) -> str:
        agents = self.list_agents()
        if not agents:
            return (
                "🤖 *Autonomous Subagents*\n\n"
                "No subagents currently registered or running.\n\n"
                "_Use `/boost <prompt>` or `jarvis-spawn-agent` to deploy one._"
            )

        lines = [f"🤖 *Autonomous Subagents ({len(agents)})*\n"]
        for a in agents[:10]:
            icon = (
                "⏳"
                if a.status == "running"
                else ("✅" if a.status == "completed" else "❌")
            )
            elapsed = (
                (a.end_time - a.start_time)
                if a.end_time
                else (time.time() - a.start_time)
            )
            lines.append(
                f"{icon} *{a.name}* (`{a.agent_id}`)\n"
                f"   Status: `{a.status}` | Time: `{elapsed:.1f}s`\n"
                f"   Task: _{a.prompt[:60]}..._"
            )
        return "\n".join(lines)


def main_cli() -> None:
    """CLI entry point for jarvis-spawn-agent."""
    parser = argparse.ArgumentParser(
        description="Deploy autonomous Antigravity subagent"
    )
    parser.add_argument(
        "--prompt", "-p", required=True, help="Task prompt for the subagent"
    )
    parser.add_argument(
        "--name", "-n", default=None, help="Descriptive name for the subagent"
    )
    parser.add_argument(
        "--chat-id", "-c", default=None, help="Telegram Chat ID to notify upon finish"
    )
    parser.add_argument(
        "--working-dir", "-w", default=None, help="Working directory for execution"
    )
    parser.add_argument(
        "--model", "-m", default=None, help="Specific model override for agy"
    )
    parser.add_argument(
        "--timeout",
        "-t",
        type=float,
        default=Constants.AGY_PROCESS_TIMEOUT,
        help="Process timeout in seconds",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait synchronously for completion instead of running detached",
    )

    args = parser.parse_args()

    async def _async_main() -> None:
        manager = SubagentManager.get_instance()
        agent = await manager.spawn_agent(
            prompt=args.prompt,
            name=args.name,
            chat_id=args.chat_id,
            working_dir=args.working_dir,
            model=args.model,
            timeout=args.timeout,
        )
        print(f"Spawned subagent '{agent.name}' (ID: {agent.agent_id})")

        if args.wait:
            task = manager._tasks.get(agent.agent_id)
            if task:
                await task
            print(f"Subagent finished with status: {agent.status}")
            if agent.output:
                print("\nOutput:")
                print(agent.output)

    if args.wait:
        asyncio.run(_async_main())
    else:
        # Spawn detached background invocation
        import subprocess

        cmd = [
            sys.executable,
            "-m",
            "jarvis_antigravity_agent.agent_manager",
            "--prompt",
            args.prompt,
            "--wait",
        ]
        if args.name:
            cmd.extend(["--name", args.name])
        if args.chat_id:
            cmd.extend(["--chat-id", str(args.chat_id)])
        if args.working_dir:
            cmd.extend(["--working-dir", args.working_dir])
        if args.model:
            cmd.extend(["--model", args.model])
        if args.timeout:
            cmd.extend(["--timeout", str(args.timeout)])

        subprocess.Popen(  # noqa: S603
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        target_desc = args.name or "agent"
        print(f"Autonomous subagent detached in background: {target_desc}")


if __name__ == "__main__":
    main_cli()
