import asyncio
import logging
import os
import shutil
import tempfile
from typing import Any

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    Update,
    constants,
)
from telegram.ext import ContextTypes

from jarvis_antigravity_agent.agent_manager import SubagentManager
from jarvis_antigravity_agent.config import is_authorized, save_state
from jarvis_antigravity_agent.constants import Constants
from jarvis_antigravity_agent.executor import execute_agy_prompt, process_lock
from jarvis_antigravity_agent.mcp import (
    add_mcp_server,
    format_global_mcp_status,
    format_mcp_status,
    remove_mcp_server,
)
from jarvis_antigravity_agent.messages import Messages
from jarvis_antigravity_agent.quotas import format_quotas_markdown, get_agy_quotas
from jarvis_antigravity_agent.skills_inspector import format_skills_markdown
from jarvis_antigravity_agent.stt import stt_status_label, transcribe_audio_file
from jarvis_antigravity_agent.updater import (
    apply_update,
    check_for_updates,
    restart_daemon,
)
from jarvis_antigravity_agent.utils import send_reply_chunks

logger = logging.getLogger(Constants.LOGGER_NAME)


def _find_gemini_model(query: str) -> dict[str, Any] | None:
    """Find matching model definition from query string."""
    q = query.strip().lower()
    for m in Constants.GEMINI_MODELS:
        model_dict: dict[str, Any] = dict(m)
        m_id = str(model_dict["id"])
        m_name = str(model_dict["name"]).lower()
        if q == m_id or q == m_name:
            return model_dict
        if q.startswith(m_id) or m_id.startswith(q) or q in m_id:
            return model_dict
        version = m_id.replace("gemini-", "").replace("-flash", "").replace("-pro", "")
        if q in {version, f"flash-{version}", f"pro-{version}"}:
            return model_dict
    return None


def _resolve_model_name(model_id: str) -> str:
    """Resolve a user-friendly display name for a model ID."""
    for m in Constants.GEMINI_MODELS:
        if model_id == m["id"] or model_id.startswith(m["id"]):
            return str(m["name"])
    return model_id


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

    async def start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_user is None or update.message is None:
            return
        if not self._is_authorized(update.effective_user.id):
            await update.message.reply_text(Messages.UNAUTHORIZED_ACCESS)
            return
        await send_reply_chunks(update, Messages.START_WELCOME)

    async def help_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_user is None or update.message is None:
            return
        if not self._is_authorized(update.effective_user.id):
            await update.message.reply_text(Messages.UNAUTHORIZED_ACCESS)
            return
        await send_reply_chunks(update, Messages.HELP_TEXT)

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

        active_model = (
            self._state.get(Constants.STATE_KEY_MODEL)
            or self._cfg.get("model")
            or "Autonomous (Default)"
        )
        active_effort = (
            self._state.get(Constants.STATE_KEY_EFFORT)
            or self._cfg.get("effort")
            or "Auto / Default"
        )

        msg = Messages.SYSTEM_STATUS.format(
            agy_status=agy_status,
            model=active_model,
            effort=active_effort,
            session_status=session_status,
            stt_status=stt_status_label(),
            working_dir=self._cfg["working_dir"],
            load1=load1_str,
            load5=load5_str,
            disk_pct=disk_pct,
        )
        await send_reply_chunks(update, msg)

    async def quotas_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_user is None or update.message is None:
            return
        if not self._is_authorized(update.effective_user.id):
            return

        agy_path = self._cfg.get("agy_path", "agy")
        quota_data = await asyncio.to_thread(get_agy_quotas, agy_path=agy_path)
        msg = format_quotas_markdown(quota_data)
        await send_reply_chunks(update, msg)

    async def skills_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_user is None or update.message is None:
            return
        if not self._is_authorized(update.effective_user.id):
            return

        msg = await asyncio.to_thread(format_skills_markdown)
        await send_reply_chunks(update, msg)

    async def mcps_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_user is None or update.message is None:
            return
        if not self._is_authorized(update.effective_user.id):
            return

        msg = await asyncio.to_thread(format_global_mcp_status)
        await send_reply_chunks(update, msg)

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

    async def uninstall_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_user is None or update.message is None:
            return
        if not self._is_authorized(update.effective_user.id):
            return

        await send_reply_chunks(update, Messages.UNINSTALL_GUIDE)

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

    async def model_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_user is None or update.message is None:
            return
        if not self._is_authorized(update.effective_user.id):
            await update.message.reply_text(Messages.UNAUTHORIZED_ACCESS)
            return

        args = context.args or []
        if not args:
            current_model = (
                self._state.get(Constants.STATE_KEY_MODEL)
                or self._cfg.get("model")
                or "Autonomous (Default)"
            )
            current_effort = (
                self._state.get(Constants.STATE_KEY_EFFORT)
                or self._cfg.get("effort")
                or "Auto / Default"
            )
            text = Messages.MODEL_MENU_TITLE.format(
                model=current_model, effort=current_effort
            )
            keyboard = [
                [
                    InlineKeyboardButton(
                        f"✨ {m['name']}",
                        callback_data=f"model:family:{m['id']}",
                    )
                ]
                for m in Constants.GEMINI_MODELS
            ]
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "⚡ Reset to Autonomous Default",
                        callback_data="model:reset",
                    )
                ]
            )
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=constants.ParseMode.MARKDOWN,
            )
            return

        subcmd = args[0].lower()
        if subcmd in {"list", "ls"}:
            lines = ["🧠 *Available Gemini Models & Reasoning Efforts:*\n"]
            for m in Constants.GEMINI_MODELS:
                efforts_str = ", ".join(f"`{e}`" for e in m["efforts"])
                lines.append(f"• *{m['name']}* (`{m['id']}`)")
                lines.append(f"  _{m['description']}_")
                lines.append(f"  Efforts: {efforts_str}\n")
            lines.append("ℹ️ _Use `/model <name> [effort]` to switch directly._")
            await send_reply_chunks(update, "\n".join(lines))
            return

        if subcmd in {"status", "current", "info"}:
            current_model = (
                self._state.get(Constants.STATE_KEY_MODEL)
                or self._cfg.get("model")
                or "Autonomous (Default)"
            )
            current_effort = (
                self._state.get(Constants.STATE_KEY_EFFORT)
                or self._cfg.get("effort")
                or "Auto / Default"
            )
            name = _resolve_model_name(str(current_model))
            msg = (
                f"🧠 *Current Gemini Model Configuration*\n\n"
                f"• *Model*: `{current_model}` ({name})\n"
                f"• *Reasoning Effort*: `{current_effort}`\n"
            )
            await update.message.reply_text(
                msg, parse_mode=constants.ParseMode.MARKDOWN
            )
            return

        if subcmd in {"reset", "default", "auto", "clear"}:
            self._state[Constants.STATE_KEY_MODEL] = None
            self._state[Constants.STATE_KEY_EFFORT] = None
            save_state(self._state)
            self._cfg["model"] = None
            self._cfg["effort"] = None
            await update.message.reply_text(
                Messages.MODEL_RESET_SUCCESS,
                parse_mode=constants.ParseMode.MARKDOWN,
            )
            return

        target_model_query = args[0]
        target_effort = args[1].lower() if len(args) > 1 else None

        matched_model = None
        matched_effort = None
        for m in Constants.GEMINI_MODELS:
            if target_model_query.lower() == m["id"]:
                matched_model = m
                break
            for eff in m["efforts"]:
                if target_model_query.lower() == f"{m['id']}-{eff}":
                    matched_model = m
                    matched_effort = eff
                    break
            if matched_model:
                break

        if not matched_model:
            matched_model = _find_gemini_model(target_model_query)

        if not matched_model:
            await update.message.reply_text(
                f"⚠️ Unknown model `{target_model_query}`.\n\n"
                + Messages.MODEL_INVALID_USAGE,
                parse_mode=constants.ParseMode.MARKDOWN,
            )
            return

        effective_effort = (
            target_effort or matched_effort or matched_model["default_effort"]
        )
        if (
            effective_effort
            and effective_effort not in matched_model["efforts"]
            and effective_effort not in {"auto", "default"}
        ):
            valid_efforts = ", ".join(f"`{e}`" for e in matched_model["efforts"])
            await update.message.reply_text(
                (
                    f"⚠️ Invalid effort `{effective_effort}` for "
                    f"*{matched_model['name']}*.\nSupported efforts: {valid_efforts}"
                ),
                parse_mode=constants.ParseMode.MARKDOWN,
            )
            return

        if effective_effort in {"auto", "default"}:
            effective_model = str(matched_model["id"])
            effective_effort_stored = None
        else:
            effective_model = f"{matched_model['id']}-{effective_effort}"
            effective_effort_stored = effective_effort

        self._state[Constants.STATE_KEY_MODEL] = effective_model
        self._state[Constants.STATE_KEY_EFFORT] = effective_effort_stored
        save_state(self._state)
        self._cfg["model"] = effective_model
        self._cfg["effort"] = effective_effort_stored

        await update.message.reply_text(
            Messages.MODEL_UPDATED_SUCCESS.format(
                model=effective_model,
                model_name=matched_model["name"],
                effort=effective_effort_stored or "Auto / Default",
            ),
            parse_mode=constants.ParseMode.MARKDOWN,
        )

    async def effort_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_user is None or update.message is None:
            return
        if not self._is_authorized(update.effective_user.id):
            await update.message.reply_text(Messages.UNAUTHORIZED_ACCESS)
            return

        args = context.args or []
        if not args:
            current_model_id = (
                self._state.get(Constants.STATE_KEY_MODEL)
                or self._cfg.get("model")
                or "gemini-3.8-flash"
            )
            model_info = (
                _find_gemini_model(str(current_model_id)) or Constants.GEMINI_MODELS[0]
            )
            current_effort = (
                self._state.get(Constants.STATE_KEY_EFFORT)
                or self._cfg.get("effort")
                or "Default"
            )

            keyboard = [
                [
                    InlineKeyboardButton(
                        "🟢 High",
                        callback_data=f"model:set:{model_info['id']}:high",
                    ),
                    InlineKeyboardButton(
                        "🟡 Medium",
                        callback_data=f"model:set:{model_info['id']}:medium",
                    ),
                    InlineKeyboardButton(
                        "🔵 Low",
                        callback_data=f"model:set:{model_info['id']}:low",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "⚡ Auto / Default",
                        callback_data=f"model:set:{model_info['id']}:default",
                    ),
                    InlineKeyboardButton(
                        "⬅️ Back to Models", callback_data="model:menu"
                    ),
                ],
            ]
            await update.message.reply_text(
                Messages.MODEL_EFFORT_PROMPT.format(
                    model_name=model_info["name"],
                    model_id=model_info["id"],
                    current_effort=current_effort,
                ),
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=constants.ParseMode.MARKDOWN,
            )
            return

        effort_arg = args[0].lower()
        if effort_arg in {"auto", "default", "reset"}:
            self._state[Constants.STATE_KEY_EFFORT] = None
            curr = self._state.get(Constants.STATE_KEY_MODEL)
            if curr:
                for eff in ("-high", "-medium", "-low"):
                    if curr.endswith(eff):
                        curr = curr[: -len(eff)]
                        self._state[Constants.STATE_KEY_MODEL] = curr
                        self._cfg["model"] = curr
                        break
            save_state(self._state)
            self._cfg["effort"] = None
            await update.message.reply_text(
                "⚡ *Reasoning effort reset to default.*",
                parse_mode=constants.ParseMode.MARKDOWN,
            )
            return

        if effort_arg in Constants.VALID_EFFORT_LEVELS:
            curr = (
                self._state.get(Constants.STATE_KEY_MODEL)
                or self._cfg.get("model")
                or "gemini-3.8-flash"
            )
            model_info = _find_gemini_model(str(curr))
            if model_info:
                if effort_arg in model_info["efforts"]:
                    new_model = f"{model_info['id']}-{effort_arg}"
                    self._state[Constants.STATE_KEY_MODEL] = new_model
                    self._cfg["model"] = new_model
                else:
                    valid_efforts = ", ".join(f"`{e}`" for e in model_info["efforts"])
                    await update.message.reply_text(
                        (
                            f"⚠️ Effort `{effort_arg}` is not supported by "
                            f"{model_info['name']}.\nSupported: {valid_efforts}"
                        ),
                        parse_mode=constants.ParseMode.MARKDOWN,
                    )
                    return
            self._state[Constants.STATE_KEY_EFFORT] = effort_arg
            self._cfg["effort"] = effort_arg
            save_state(self._state)
            model_name = model_info["name"] if model_info else str(curr)
            await update.message.reply_text(
                f"✅ Reasoning effort set to *{effort_arg}* for *{model_name}*.",
                parse_mode=constants.ParseMode.MARKDOWN,
            )
            return

        await update.message.reply_text(
            Messages.EFFORT_INVALID_USAGE,
            parse_mode=constants.ParseMode.MARKDOWN,
        )

    async def model_callback_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        if query is None:
            return

        user_id = query.from_user.id if query.from_user else 0
        if not self._is_authorized(user_id):
            await query.answer("Unauthorized", show_alert=True)
            return

        await query.answer()

        data = query.data or ""
        if data == "model:menu":
            current_model = (
                self._state.get(Constants.STATE_KEY_MODEL)
                or self._cfg.get("model")
                or "Autonomous (Default)"
            )
            current_effort = (
                self._state.get(Constants.STATE_KEY_EFFORT)
                or self._cfg.get("effort")
                or "Auto / Default"
            )
            text = Messages.MODEL_MENU_TITLE.format(
                model=current_model, effort=current_effort
            )
            keyboard = [
                [
                    InlineKeyboardButton(
                        f"✨ {m['name']}",
                        callback_data=f"model:family:{m['id']}",
                    )
                ]
                for m in Constants.GEMINI_MODELS
            ]
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "⚡ Reset to Autonomous Default",
                        callback_data="model:reset",
                    )
                ]
            )
            try:
                await query.edit_message_text(
                    text=text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=constants.ParseMode.MARKDOWN,
                )
            except Exception as e:
                logger.debug("Failed to edit model menu message: %s", e)
            return

        if data == "model:reset":
            self._state[Constants.STATE_KEY_MODEL] = None
            self._state[Constants.STATE_KEY_EFFORT] = None
            save_state(self._state)
            self._cfg["model"] = None
            self._cfg["effort"] = None
            keyboard = [
                [InlineKeyboardButton("⚙️ Select Model", callback_data="model:menu")]
            ]
            try:
                await query.edit_message_text(
                    text=Messages.MODEL_RESET_SUCCESS,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=constants.ParseMode.MARKDOWN,
                )
            except Exception as e:
                logger.debug("Failed to edit reset message: %s", e)
            return

        if data.startswith("model:family:"):
            family_id = data.split(":", 2)[2]
            model_info = next(
                (m for m in Constants.GEMINI_MODELS if m["id"] == family_id), None
            )
            if not model_info:
                try:
                    await query.edit_message_text("⚠️ Model family not found.")
                except Exception as e:
                    logger.debug("Failed to edit family not found message: %s", e)
                return

            current_effort = (
                self._state.get(Constants.STATE_KEY_EFFORT)
                or self._cfg.get("effort")
                or "Default"
            )
            keyboard = []
            row = []
            for eff in model_info["efforts"]:
                icon = "🟢" if eff == "high" else ("🟡" if eff == "medium" else "🔵")
                row.append(
                    InlineKeyboardButton(
                        f"{icon} {eff.capitalize()}",
                        callback_data=f"model:set:{family_id}:{eff}",
                    )
                )
            keyboard.append(row)
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "⚡ Default / Auto",
                        callback_data=f"model:set:{family_id}:default",
                    )
                ]
            )
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "⬅️ Back to Models",
                        callback_data="model:menu",
                    )
                ]
            )
            try:
                await query.edit_message_text(
                    text=Messages.MODEL_EFFORT_PROMPT.format(
                        model_name=model_info["name"],
                        model_id=model_info["id"],
                        current_effort=current_effort,
                    ),
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=constants.ParseMode.MARKDOWN,
                )
            except Exception as e:
                logger.debug("Failed to edit effort prompt message: %s", e)
            return

        if data.startswith("model:set:"):
            parts = data.split(":")
            if len(parts) < 4:
                return
            family_id = parts[2]
            effort = parts[3]

            model_info = next(
                (m for m in Constants.GEMINI_MODELS if m["id"] == family_id), None
            )
            model_name = model_info["name"] if model_info else family_id

            if effort == "default":
                effective_model = str(family_id)
                effective_effort = None
            else:
                effective_model = f"{family_id}-{effort}"
                effective_effort = effort

            self._state[Constants.STATE_KEY_MODEL] = effective_model
            self._state[Constants.STATE_KEY_EFFORT] = effective_effort
            save_state(self._state)
            self._cfg["model"] = effective_model
            self._cfg["effort"] = effective_effort

            keyboard = [
                [InlineKeyboardButton("⚙️ Change Model", callback_data="model:menu")]
            ]
            try:
                await query.edit_message_text(
                    text=Messages.MODEL_UPDATED_SUCCESS.format(
                        model=effective_model,
                        model_name=model_name,
                        effort=effective_effort or "Auto / Default",
                    ),
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=constants.ParseMode.MARKDOWN,
                )
            except Exception as e:
                logger.debug("Failed to edit model updated message: %s", e)
            return
