import json
import logging
import os
import shutil
from typing import Any

from jarvis_antigravity_agent.constants import Constants
from jarvis_antigravity_agent.messages import Messages

logger = logging.getLogger(Constants.LOGGER_NAME)


def load_config() -> dict[str, Any]:
    if os.path.exists(Constants.CONFIG_PATH):
        try:
            with open(Constants.CONFIG_PATH, encoding="utf-8") as f:
                result: dict[str, Any] = json.load(f)
                return result
        except Exception as e:
            logger.error(Messages.CONFIG_LOAD_ERROR.format(error=e))
    return {}


def load_state() -> dict[str, Any]:
    if os.path.exists(Constants.STATE_PATH):
        try:
            with open(Constants.STATE_PATH, encoding="utf-8") as f:
                result: dict[str, Any] = json.load(f)
                return result
        except Exception as e:
            logger.debug("Failed to load state: %s", e)
    return {Constants.STATE_KEY_CONTINUE: False}


def save_state(state: dict[str, Any]) -> None:
    try:
        with open(Constants.STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(Messages.STATE_SAVE_ERROR.format(error=e))


def build_runtime_config(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "bot_token": config.get("bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN"),
        "allowed_users": {str(u) for u in config.get("allowed_users", [])},
        "working_dir": config.get("working_directory", Constants.DEFAULT_WORKING_DIR),
        "agy_path": config.get(
            "agy_path",
            shutil.which("agy") or Constants.AGY_FALLBACK_BIN,
        ),
        "default_flags": config.get("default_flags", Constants.AGY_DEFAULT_FLAGS),
    }


def is_authorized(user_id: int, allowed_users: set[str]) -> bool:
    if not allowed_users:
        return True
    return str(user_id) in allowed_users
