import asyncio
import logging

from telegram import Message, Update, constants
from telegram.ext import ContextTypes

from jarvis_antigravity_agent.constants import Constants

logger = logging.getLogger(Constants.LOGGER_NAME)


def split_message(
    text: str, max_length: int = Constants.MAX_MESSAGE_LENGTH
) -> list[str]:
    if len(text) <= max_length:
        return [text]
    chunks: list[str] = []
    lines = text.split("\n")
    current_chunk = ""
    for line in lines:
        if len(current_chunk) + len(line) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            if len(line) > max_length:
                for i in range(0, len(line), max_length):
                    chunks.append(line[i : i + max_length])
            else:
                current_chunk = line
        else:
            current_chunk = (current_chunk + "\n" + line) if current_chunk else line
    if current_chunk:
        chunks.append(current_chunk)
    return chunks


async def send_reply_chunks(update: Update, text: str) -> None:
    if update.message is None:
        return
    msg: Message = update.message
    chunks = split_message(text.strip() or Constants.EMPTY_RESPONSE_PLACEHOLDER)
    for chunk in chunks:
        try:
            await msg.reply_text(chunk, parse_mode=constants.ParseMode.MARKDOWN)
        except Exception:
            await msg.reply_text(chunk)


async def keep_typing(
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        try:
            await context.bot.send_chat_action(
                chat_id=chat_id, action=constants.ChatAction.TYPING
            )
        except Exception as e:
            logger.debug("Failed to send typing chat action: %s", e)
        try:
            await asyncio.wait_for(
                stop_event.wait(), timeout=Constants.TYPING_WAIT_TIMEOUT
            )
        except asyncio.TimeoutError:
            pass
