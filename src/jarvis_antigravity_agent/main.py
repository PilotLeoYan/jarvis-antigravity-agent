import logging
import sys

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from jarvis_antigravity_agent.config import (
    build_runtime_config,
    get_settings,
    load_config,
    load_state,
)
from jarvis_antigravity_agent.constants import Constants
from jarvis_antigravity_agent.handlers import BotHandlers
from jarvis_antigravity_agent.messages import Messages

_initial_settings = get_settings()
_log_level = getattr(logging, _initial_settings.system.log_level.upper(), logging.INFO)
logging.basicConfig(
    format=_initial_settings.system.log_format,
    level=_log_level,
)
logger = logging.getLogger(_initial_settings.system.logger_name)


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
    app.add_handler(CommandHandler(["boost", "spawn", "agent"], handlers.boost_command))
    app.add_handler(CommandHandler(["agents", "subagents"], handlers.agents_command))
    app.add_handler(
        CommandHandler(["killagent", "cancelagent"], handlers.killagent_command)
    )
    app.add_handler(CommandHandler(["mcp"], handlers.mcp_command))
    app.add_handler(CommandHandler(["update", "actualizar"], handlers.update_command))
    app.add_handler(CommandHandler(["checkupdate"], handlers.checkupdate_command))

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message)
    )
    app.add_handler(
        MessageHandler(filters.VOICE | filters.AUDIO, handlers.handle_voice)
    )

    logger.info(Messages.BRIDGE_STARTING)
    app.run_polling(drop_pending_updates=True)
