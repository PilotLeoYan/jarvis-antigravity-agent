import logging
import sys

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from jarvis_antigravity_agent.config import (
    build_runtime_config,
    load_config,
    load_state,
)
from jarvis_antigravity_agent.constants import Constants
from jarvis_antigravity_agent.handlers import BotHandlers
from jarvis_antigravity_agent.messages import Messages

logging.basicConfig(
    format=Constants.LOG_FORMAT,
    level=logging.INFO,
)
logger = logging.getLogger(Constants.LOGGER_NAME)


def main() -> None:
    raw_config = load_config()
    runtime_cfg = build_runtime_config(raw_config)
    state = load_state()

    bot_token = runtime_cfg["bot_token"]
    if not bot_token or bot_token == Constants.PLACEHOLDER_BOT_TOKEN:
        logger.error(Messages.MISSING_BOT_TOKEN)
        sys.exit(1)

    handlers = BotHandlers(runtime_cfg, state)

    app = Application.builder().token(bot_token).build()

    app.add_handler(CommandHandler(["start", "help", "ayuda"], handlers.help_command))
    app.add_handler(CommandHandler(["new", "nuevo"], handlers.new_command))
    app.add_handler(CommandHandler(["status", "estado"], handlers.status_command))
    app.add_handler(CommandHandler(["cancel", "cancelar"], handlers.cancel_command))

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message)
    )
    app.add_handler(
        MessageHandler(filters.VOICE | filters.AUDIO, handlers.handle_voice)
    )

    logger.info(Messages.BRIDGE_STARTING)
    app.run_polling(drop_pending_updates=True)
