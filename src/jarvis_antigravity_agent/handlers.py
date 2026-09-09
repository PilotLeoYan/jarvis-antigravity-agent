import asyncio
import logging
import os
import shutil
import tempfile
from typing import Any

from telegram import Message, Update, constants
from telegram.ext import ContextTypes

from jarvis_antigravity_agent.agent_manager import SubagentManager
from jarvis_antigravity_agent.config import is_authorized, save_state
from jarvis_antigravity_agent.constants import Constants
from jarvis_antigravity_agent.executor import execute_agy_prompt, process_lock
from jarvis_antigravity_agent.mcp import (
    add_mcp_server,
    format_mcp_status,
    remove_mcp_server,
)
from jarvis_antigravity_agent.messages import Messages
from jarvis_antigravity_agent.stt import stt_status_label, transcribe_audio_file
from jarvis_antigravity_agent.updater import (
    apply_update,
    check_for_updates,
    restart_daemon,
)

logger = logging.getLogger(Constants.LOGGER_NAME)


class BotHandlers:
    def __init__(self, runtime_cfg: dict[str, Any], state: dict[str, Any]) -> None:
        self._cfg = runtime_cfg
        self._state = state

    def _is_authorized(self, user_id: int) -> bool:
        allowed: set[str] = self._cfg["allowed_users"]
        return bool(is_authorized(user_id, allowed))

    async def handle_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_user is None or update.message is None:
            return
        if not self._is_authorized(update.effective_user.id):
            await update.message.reply_text(Messages.UNAUTHORIZED_ACCESS)
            return

        prompt = update.message.text
        if not prompt or not prompt.strip():
            return

        if process_lock.locked():
            await update.message.reply_text(
                Messages.TASK_RUNNING_WARNING,
                parse_mode=constants.ParseMode.MARKDOWN,
            )
            return

        await execute_agy_prompt(
            prompt, update, context, self._cfg, self._state, save_state
        )

    async def handle_voice(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_user is None or update.message is None:
            return
        if not self._is_authorized(update.effective_user.id):
            await update.message.reply_text(Messages.UNAUTHORIZED_ACCESS)
            return

        if process_lock.locked():
            await update.message.reply_text(
                Messages.TASK_RUNNING_WARNING,
                parse_mode=constants.ParseMode.MARKDOWN,
            )
            return

        voice = update.message.voice or update.message.audio
        if not voice:
            return

        status_msg: Message = await update.message.reply_text(
            Messages.PROCESSING_VOICE, parse_mode=constants.ParseMode.MARKDOWN
        )

        with tempfile.NamedTemporaryFile(
            suffix=Constants.VOICE_TEMP_SUFFIX, delete=False
        ) as tf:
            temp_path = tf.name

        try:
            voice_file = await context.bot.get_file(voice.file_id)
            await voice_file.download_to_drive(custom_path=temp_path)

            transcription, lang = await asyncio.to_thread(
                transcribe_audio_file, temp_path
            )
            logger.info(
                Messages.VOICE_TRANSCRIBED.format(
                    lang=lang, transcription=transcription
                )
            )

            if not transcription or not transcription.strip():
                await status_msg.edit_text(Messages.NO_CLEAR_SPEECH)
                return

            await status_msg.edit_text(
                Messages.TRANSCRIPTION_RESULT.format(transcription=transcription),
                parse_mode=constants.ParseMode.MARKDOWN,
            )

            await execute_agy_prompt(
                transcription, update, context, self._cfg, self._state, save_state
            )

        except Exception as e:
            logger.exception(Messages.AUDIO_ERROR)
            await status_msg.edit_text(Messages.AUDIO_PROCESSING_ERROR.format(error=e))
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as e:
                    logger.debug("Failed to remove temporary voice file: %s", e)

    async def help_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_user is None or update.message is None:
            return
        if not self._is_authorized(update.effective_user.id):
            await update.message.reply_text(Messages.UNAUTHORIZED_ACCESS)
            return
        await update.message.reply_text(
            Messages.HELP_TEXT, parse_mode=constants.ParseMode.MARKDOWN
        )

    async def new_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_user is None or update.message is None:
            return
        if not self._is_authorized(update.effective_user.id):
            return
        self._state[Constants.STATE_KEY_CONTINUE] = False
        save_state(self._state)
        await update.message.reply_text(
            Messages.CONTEXT_RESET, parse_mode=constants.ParseMode.MARKDOWN
        )

    async def status_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_user is None or update.message is None:
            return
        if not self._is_authorized(update.effective_user.id):
            return

        import jarvis_antigravity_agent.executor as _executor

        is_busy = (
            _executor.current_process is not None
            and _executor.current_process.returncode is None
        )
        agy_status = Messages.TASK_PROCESSING if is_busy else Messages.IDLE_READY
        session_status = (
            Messages.SESSION_ACTIVE
            if self._state.get(Constants.STATE_KEY_CONTINUE)
            else Messages.SESSION_READY
        )

        load1_str = "N/A"
        load5_str = "N/A"
        disk_pct = "N/A"
        try:
            if hasattr(os, "getloadavg"):
                load1, load5, _ = os.getloadavg()  # type: ignore[attr-defined]
                load1_str = f"{load1:.2f}"
                load5_str = f"{load5:.2f}"
            total, used, _ = shutil.disk_usage(self._cfg["working_dir"])
            disk_pct = (
                f"{(used / total) * 100:.1f}% "
                f"({used // (1024**3)}GB / {total // (1024**3)}GB)"
            )
        except Exception as e:
            logger.debug("Failed to inspect system metrics: %s", e)

        msg = Messages.SYSTEM_STATUS.format(
            agy_status=agy_status,
            session_status=session_status,
            stt_status=stt_status_label(),
            working_dir=self._cfg["working_dir"],
            load1=load1_str,
            load5=load5_str,
            disk_pct=disk_pct,
        )
        await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)

    async def cancel_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_user is None or update.message is None:
            return
        if not self._is_authorized(update.effective_user.id):
            return

        import jarvis_antigravity_agent.executor as _executor

        proc = _executor.current_process
        if proc and proc.returncode is None:
            try:
                proc.kill()
                await update.message.reply_text(
                    Messages.TASK_CANCELLED, parse_mode=constants.ParseMode.MARKDOWN
                )
            except Exception as e:
                await update.message.reply_text(
                    Messages.ERROR_CANCELLING.format(error=e)
                )
        else:
            await update.message.reply_text(Messages.NO_ACTIVE_TASK)

    async def boost_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_user is None or update.message is None:
            return
        if not self._is_authorized(update.effective_user.id):
            await update.message.reply_text(Messages.UNAUTHORIZED_ACCESS)
            return

        raw_text = update.message.text or ""
        parts = raw_text.split(None, 1)
        prompt = parts[1].strip() if len(parts) > 1 else ""
        if not prompt and context.args:
            prompt = " ".join(context.args).strip()

        if not prompt:
            await update.message.reply_text(
                Messages.SUBAGENT_USAGE, parse_mode=constants.ParseMode.MARKDOWN
            )
            return

        chat_id = update.effective_chat.id if update.effective_chat else None
        manager = SubagentManager.get_instance()
        agent_info = await manager.spawn_agent(
            prompt=prompt,
            chat_id=chat_id,
            working_dir=self._cfg.get("working_dir"),
            model=self._cfg.get("model"),
        )
        await update.message.reply_text(
            Messages.SUBAGENT_SPAWNED.format(
                name=agent_info.name,
                agent_id=agent_info.agent_id,
                prompt=prompt[:100],
            ),
            parse_mode=constants.ParseMode.MARKDOWN,
        )

    async def agents_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_user is None or update.message is None:
            return
        if not self._is_authorized(update.effective_user.id):
            return

        manager = SubagentManager.get_instance()
        summary = manager.format_agents_summary()
        await update.message.reply_text(
            summary, parse_mode=constants.ParseMode.MARKDOWN
        )

    async def killagent_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_user is None or update.message is None:
            return
        if not self._is_authorized(update.effective_user.id):
            return

        if not context.args:
            await update.message.reply_text(
                "ℹ️ *Usage:* `/killagent <agent-id>`",
                parse_mode=constants.ParseMode.MARKDOWN,
            )
            return

        target_id = context.args[0].strip()
        manager = SubagentManager.get_instance()
        success = await manager.cancel_agent(target_id)
        if success:
            await update.message.reply_text(
                Messages.SUBAGENT_KILLED.format(agent_id=target_id),
                parse_mode=constants.ParseMode.MARKDOWN,
            )
        else:
            await update.message.reply_text(
                Messages.SUBAGENT_NOT_FOUND.format(agent_id=target_id),
                parse_mode=constants.ParseMode.MARKDOWN,
            )

    async def mcp_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_user is None or update.message is None:
            return
        if not self._is_authorized(update.effective_user.id):
            return

        args = context.args or []
        if not args or args[0].lower() == "list":
            msg = format_mcp_status()
            await update.message.reply_text(
                msg, parse_mode=constants.ParseMode.MARKDOWN
            )
            return

        action = args[0].lower()
        if action == "add":
            if len(args) < 3:
                await update.message.reply_text(
                    "ℹ️ *Usage:* `/mcp add <name> <command> [args...]`",
                    parse_mode=constants.ParseMode.MARKDOWN,
                )
                return
            s_name = args[1]
            s_cmd = args[2]
            s_args = args[3:] if len(args) > 3 else []
            ok = add_mcp_server(s_name, s_cmd, s_args)
            if ok:
                await update.message.reply_text(
                    f"✅ Registered MCP server `{s_name}` (`{s_cmd}`)",
                    parse_mode=constants.ParseMode.MARKDOWN,
                )
            else:
                await update.message.reply_text("❌ Failed to register MCP server.")
        elif action in {"remove", "rm"}:
            if len(args) < 2:
                await update.message.reply_text(
                    "ℹ️ *Usage:* `/mcp remove <name>`",
                    parse_mode=constants.ParseMode.MARKDOWN,
                )
                return
            s_name = args[1]
            ok = remove_mcp_server(s_name)
            if ok:
                await update.message.reply_text(
                    f"✅ Removed MCP server `{s_name}`",
                    parse_mode=constants.ParseMode.MARKDOWN,
                )
            else:
                await update.message.reply_text(
                    f"⚠️ MCP server `{s_name}` not found.",
                    parse_mode=constants.ParseMode.MARKDOWN,
                )
        else:
            await update.message.reply_text(
                Messages.MCP_USAGE, parse_mode=constants.ParseMode.MARKDOWN
            )

    async def update_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_user is None or update.message is None:
            return
        if not self._is_authorized(update.effective_user.id):
            return

        status_msg = await update.message.reply_text(
            Messages.UPDATE_CHECKING, parse_mode=constants.ParseMode.MARKDOWN
        )

        remote = self._cfg.get("update_remote", "origin")
        branch = self._cfg.get("update_branch", "main")

        has_updates, local_sha, remote_sha, summary = await asyncio.to_thread(
            check_for_updates,
            remote=remote,
            branch=branch,
        )
        if not has_updates:
            await status_msg.edit_text(
                f"✅ *Already Up to Date*\n\nCurrent commit: `{local_sha}`",
                parse_mode=constants.ParseMode.MARKDOWN,
            )
            return

        await status_msg.edit_text(
            Messages.UPDATE_APPLYING, parse_mode=constants.ParseMode.MARKDOWN
        )

        success, msg = await asyncio.to_thread(
            apply_update,
            remote=remote,
            branch=branch,
        )
        if success:
            await status_msg.edit_text(
                f"🎉 *Update Successful*\n\n{msg}\n\n_Restarting service..._",
                parse_mode=constants.ParseMode.MARKDOWN,
            )
            await asyncio.sleep(0.5)
            restart_daemon()
        else:
            await status_msg.edit_text(
                Messages.UPDATE_FAILED.format(error=msg),
                parse_mode=constants.ParseMode.MARKDOWN,
            )

    async def checkupdate_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_user is None or update.message is None:
            return
        if not self._is_authorized(update.effective_user.id):
            return

        remote = self._cfg.get("update_remote", "origin")
        branch = self._cfg.get("update_branch", "main")

        has_updates, local_sha, remote_sha, summary = await asyncio.to_thread(
            check_for_updates,
            remote=remote,
            branch=branch,
        )
        if has_updates:
            msg = (
                f"🚀 *New Version Available!*\n\n"
                f"• Current: `{local_sha}`\n"
                f"• Latest: `{remote_sha}`\n\n"
                f"*Recent Commits:*\n{summary}\n\n"
                f"_Send `/update` to apply this update safely._"
            )
        else:
            msg = f"✅ *System is Up to Date*\n\nCurrent version: `{local_sha}`"

        await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)
