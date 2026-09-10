import asyncio
import logging
import sys
from typing import Any

from telegram import constants
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
from jarvis_antigravity_agent.updater import (
    apply_update,
    check_for_updates,
    restart_daemon,
)

_initial_settings = get_settings()
_log_level = getattr(logging, _initial_settings.system.log_level.upper(), logging.INFO)
logging.basicConfig(
    format=_initial_settings.system.log_format,
    level=_log_level,
)
logger = logging.getLogger(_initial_settings.system.logger_name)


async def auto_update_checker(app: Application, runtime_cfg: dict[str, Any]) -> None:
    """Continuously poll upstream GitHub repository for new releases or commits."""
    remote = str(runtime_cfg.get("update_remote", "origin"))
    branch = str(runtime_cfg.get("update_branch", "main"))
    interval = float(runtime_cfg.get("update_check_interval_seconds", 3600.0))
    auto_apply = bool(runtime_cfg.get("update_auto_apply", False))
    auto_restart = bool(runtime_cfg.get("update_auto_restart", True))
    default_chat_id = runtime_cfg.get("default_chat_id")

    last_notified_sha: str | None = None

    # Wait briefly after startup
    await asyncio.sleep(15.0)

    while True:
        try:
            has_updates, local_sha, remote_sha, summary = await asyncio.to_thread(
                check_for_updates, remote=remote, branch=branch
            )
            if has_updates and remote_sha != last_notified_sha:
                last_notified_sha = remote_sha
                logger.info(
                    "Detected newer commit on GitHub (%s..%s)", local_sha, remote_sha
                )
                if auto_apply:
                    logger.info("Auto-update enabled: applying update...")
                    success, msg = await asyncio.to_thread(
                        apply_update, remote=remote, branch=branch
                    )
                    if default_chat_id:
                        try:
                            await app.bot.send_message(
                                chat_id=default_chat_id,
                                text=(
                                    f"🎉 *Autonomous Code Update Applied*\n\n"
                                    f"{msg}\n\n_Restarting service..._"
                                ),
                                parse_mode=constants.ParseMode.MARKDOWN,
                            )
                        except Exception as e:
                            logger.debug("Failed to notify auto-update: %s", e)
                    if success and auto_restart:
                        await asyncio.sleep(1.0)
                        restart_daemon()
                elif default_chat_id:
                    try:
                        await app.bot.send_message(
                            chat_id=default_chat_id,
                            text=(
                                f"🚀 *New Version Available on GitHub!*\n\n"
                                f"• Current: `{local_sha}`\n"
                                f"• Latest: `{remote_sha}`\n\n"
                                f"*Commits:*\n{summary}\n\n"
                                f"_Send `/update` to apply this update safely._"
                            ),
                            parse_mode=constants.ParseMode.MARKDOWN,
                        )
                    except Exception as e:
                        logger.debug("Failed to send update alert: %s", e)
        except Exception as e:
            logger.debug("Error checking for updates in background: %s", e)

        await asyncio.sleep(max(60.0, interval))


def main() -> None:
    raw_config = load_config()
    runtime_cfg = build_runtime_config(raw_config)
    state = load_state()

    bot_token = runtime_cfg["bot_token"]
    if not bot_token or bot_token == Constants.PLACEHOLDER_BOT_TOKEN:
        logger.error(Messages.MISSING_BOT_TOKEN)
        sys.exit(1)

    # Sync custom skills and cognitive rules to standard AGY locations
    try:
        from jarvis_antigravity_agent.uninstaller import (
            copy_cognitive_rules,
            copy_project_skills,
        )

        copy_project_skills()
        copy_cognitive_rules()
    except Exception as e:
        logger.debug(
            "Non-fatal: failed syncing project skills or rules on startup: %s", e
        )

    handlers = BotHandlers(runtime_cfg, state)

    async def post_init(application: Application) -> None:
        try:
            from telegram import BotCommand

            bot_commands = [
                BotCommand("start", "Welcome message and agent overview"),
                BotCommand("help", "Show available commands and usage guide"),
                BotCommand("new", "Reset session and conversation context"),
                BotCommand("status", "Show system metrics and runtime status"),
                BotCommand("quotas", "Inspect Google Antigravity quotas and limits"),
                BotCommand("skills", "List active workspace and user skills"),
                BotCommand("mcps", "Inspect configured MCP servers"),
                BotCommand("cancel", "Cancel current active Antigravity task"),
                BotCommand("boost", "Spawn autonomous background subagent"),
                BotCommand("agents", "List background subagent tasks"),
                BotCommand("killagent", "Terminate running subagent by ID"),
                BotCommand("mcp", "Manage MCP servers (list/add/remove)"),
                BotCommand("checkupdate", "Check for updates from GitHub"),
                BotCommand("update", "Apply latest updates and restart"),
                BotCommand("uninstall", "Display uninstallation instructions"),
            ]
            await application.bot.set_my_commands(bot_commands)
            logger.info("Registered %d Telegram bot commands", len(bot_commands))
        except Exception as e:
            logger.warning("Failed to register Telegram bot commands: %s", e)

        asyncio.create_task(auto_update_checker(application, runtime_cfg))

    app = Application.builder().token(bot_token).post_init(post_init).build()

    app.add_handler(CommandHandler(["start"], handlers.start_command))
    app.add_handler(CommandHandler(["help"], handlers.help_command))
    app.add_handler(CommandHandler(["new"], handlers.new_command))
    app.add_handler(CommandHandler(["status"], handlers.status_command))
    app.add_handler(CommandHandler(["quotas", "quota"], handlers.quotas_command))
    app.add_handler(CommandHandler(["skills", "globalskills"], handlers.skills_command))
    app.add_handler(CommandHandler(["mcps", "globalmcps"], handlers.mcps_command))
    app.add_handler(CommandHandler(["cancel"], handlers.cancel_command))
    app.add_handler(CommandHandler(["boost", "spawn", "agent"], handlers.boost_command))
    app.add_handler(CommandHandler(["agents", "subagents"], handlers.agents_command))
    app.add_handler(
        CommandHandler(["killagent", "cancelagent"], handlers.killagent_command)
    )
    app.add_handler(CommandHandler(["mcp"], handlers.mcp_command))
    app.add_handler(CommandHandler(["update"], handlers.update_command))
    app.add_handler(CommandHandler(["checkupdate"], handlers.checkupdate_command))
    app.add_handler(CommandHandler(["uninstall"], handlers.uninstall_command))

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message)
    )
    app.add_handler(
        MessageHandler(filters.VOICE | filters.AUDIO, handlers.handle_voice)
    )

    logger.info(Messages.BRIDGE_STARTING)
    app.run_polling(drop_pending_updates=True)
