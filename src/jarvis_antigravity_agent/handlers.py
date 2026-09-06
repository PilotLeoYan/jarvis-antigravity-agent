import asyncio
import logging
import os
import shutil
import tempfile
from typing import Any

from telegram import Message, Update, constants
from telegram.ext import ContextTypes

from jarvis_antigravity_agent.config import is_authorized, save_state
from jarvis_antigravity_agent.constants import Constants
from jarvis_antigravity_agent.executor import execute_agy_prompt, process_lock
from jarvis_antigravity_agent.messages import Messages
from jarvis_antigravity_agent.stt import stt_status_label, transcribe_audio_file

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
