import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from jarvis_antigravity_agent.constants import Constants
from jarvis_antigravity_agent.messages import Messages

logger = logging.getLogger(Constants.LOGGER_NAME)


def find_config_path(explicit_path: str | Path | None = None) -> Path | None:
    """Locate the active configuration file in priority order.

    Priority:
    1. Explicit path parameter
    2. JARVIS_CONFIG_PATH environment variable
    3. AGY_TELEGRAM_CONFIG environment variable
    4. config.yaml in current dir or base dir
    5. config.yml in current dir or base dir
    6. config.json in current dir or base dir
    """
    if explicit_path is not None:
        p = Path(explicit_path)
        if p.is_file():
            return p

    for env_var in ("JARVIS_CONFIG_PATH", "AGY_TELEGRAM_CONFIG"):
        val = os.environ.get(env_var)
        if val:
            p = Path(val)
            if p.is_file():
                return p

    search_dirs = [Path.cwd(), Path(Constants.BASE_DIR)]
    candidate_names = ["config.yaml", "config.yml", "config.json"]

    for d in search_dirs:
        for name in candidate_names:
            candidate = d / name
            if candidate.is_file():
                return candidate

    return None


class TelegramSettings(BaseModel):
    bot_token: str | None = None
    allowed_users: list[int | str] = Field(default_factory=list)
    default_chat_id: int | str | None = None
    request_timeout: float = Constants.TELEGRAM_REQ_TIMEOUT
    max_message_length: int = Constants.MAX_MESSAGE_LENGTH
    typing_wait_timeout: float = Constants.TYPING_WAIT_TIMEOUT
    api_send_url: str = Constants.TELEGRAM_API_SEND_URL


class AgySettings(BaseModel):
    model: str | None = Field(default=Constants.AGY_DEFAULT_MODEL)
    working_dir: str = Field(default_factory=lambda: Constants.DEFAULT_WORKING_DIR)
    agy_path: str = Field(
        default_factory=lambda: shutil.which("agy") or Constants.AGY_FALLBACK_BIN
    )
    default_flags: list[str] = Field(
        default_factory=lambda: list(Constants.AGY_DEFAULT_FLAGS)
    )
    process_timeout: float = Constants.AGY_PROCESS_TIMEOUT
    communicate_timeout: float = Constants.AGY_COMMUNICATE_TIMEOUT
    edit_throttle_seconds: float = Constants.EDIT_THROTTLE_SECONDS
    max_status_items: int = Constants.MAX_STATUS_ITEMS
    max_completed_items: int = Constants.MAX_COMPLETED_ITEMS
    path_extra: str = Constants.PATH_EXTRA
    local_bin: str = Constants.AGY_LOCAL_BIN


class WhisperSettings(BaseModel):
    model_size: str = Constants.WHISPER_MODEL_SIZE
    device: str = Constants.WHISPER_DEVICE
    compute_type: str = Constants.WHISPER_COMPUTE_TYPE
    beam_size: int = Constants.WHISPER_BEAM_SIZE


class SystemSettings(BaseModel):
    state_path: str = Field(default_factory=lambda: Constants.STATE_PATH)
    logger_name: str = Constants.LOGGER_NAME
    log_level: str = "INFO"
    log_format: str = Constants.LOG_FORMAT


class McpSettings(BaseModel):
    config_path: str | None = None


class UpdateSettings(BaseModel):
    remote: str = "origin"
    branch: str = "main"
    auto_restart: bool = True
    check_interval_seconds: float = 3600.0
    auto_apply: bool = False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    agy: AgySettings = Field(default_factory=AgySettings)
    whisper: WhisperSettings = Field(default_factory=WhisperSettings)
    system: SystemSettings = Field(default_factory=SystemSettings)
    mcp: McpSettings = Field(default_factory=McpSettings)
    update: UpdateSettings = Field(default_factory=UpdateSettings)

    @model_validator(mode="before")
    @classmethod
    def handle_legacy_and_flat_keys(cls, data: Any) -> Any:
        """Harmonize flat keys, legacy formats, and fallback env variables."""
        if not isinstance(data, dict):
            return data

        d = dict(data)

        # Telegram sub-dict setup
        telegram_data = d.get("telegram")
        if not isinstance(telegram_data, dict):
            telegram_data = {}
            d["telegram"] = telegram_data

        # Map top-level legacy keys to telegram
        if "bot_token" in d and "bot_token" not in telegram_data:
            telegram_data["bot_token"] = d.pop("bot_token")
        if "allowed_users" in d and "allowed_users" not in telegram_data:
            telegram_data["allowed_users"] = d.pop("allowed_users")
        if "default_chat_id" in d and "default_chat_id" not in telegram_data:
            telegram_data["default_chat_id"] = d.pop("default_chat_id")

        # Environment variable fallback for bot token and chat id
        if not telegram_data.get("bot_token"):
            env_token = os.environ.get("TELEGRAM_BOT_TOKEN")
            if env_token:
                telegram_data["bot_token"] = env_token
        if not telegram_data.get("default_chat_id"):
            env_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
            if env_chat_id:
                telegram_data["default_chat_id"] = env_chat_id

        # Agy sub-dict setup
        agy_data = d.get("agy")
        if not isinstance(agy_data, dict):
            agy_data = {}
            d["agy"] = agy_data

        # Map top-level legacy keys to agy
        if "working_directory" in d and "working_dir" not in agy_data:
            agy_data["working_dir"] = d.pop("working_directory")
        elif "working_dir" in d and "working_dir" not in agy_data:
            agy_data["working_dir"] = d.pop("working_dir")

        if "agy_path" in d and "agy_path" not in agy_data:
            agy_data["agy_path"] = d.pop("agy_path")
        if "model" in d and "model" not in agy_data:
            agy_data["model"] = d.pop("model")
        if "default_flags" in d and "default_flags" not in agy_data:
            agy_data["default_flags"] = d.pop("default_flags")
        if "process_timeout" in d and "process_timeout" not in agy_data:
            agy_data["process_timeout"] = d.pop("process_timeout")

        # System sub-dict setup
        system_data = d.get("system")
        if not isinstance(system_data, dict):
            system_data = {}
            d["system"] = system_data

        if "state_path" in d and "state_path" not in system_data:
            system_data["state_path"] = d.pop("state_path")

        return d

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        sources: list[PydanticBaseSettingsSource] = [
            init_settings,
            env_settings,
            dotenv_settings,
        ]

        cfg_file = find_config_path()
        if cfg_file and cfg_file.is_file():
            ext = cfg_file.suffix.lower()
            if ext in {".yaml", ".yml"}:
                sources.append(
                    YamlConfigSettingsSource(
                        settings_cls,
                        yaml_file=cfg_file,
                        yaml_file_encoding="utf-8",
                    )
                )
            elif ext == ".json":
                sources.append(
                    JsonConfigSettingsSource(
                        settings_cls,
                        json_file=cfg_file,
                        json_file_encoding="utf-8",
                    )
                )

        sources.append(file_secret_settings)
        return tuple(sources)

    # Convenience properties for backward compatibility
    @property
    def bot_token(self) -> str | None:
        return self.telegram.bot_token

    @property
    def allowed_users(self) -> list[int | str]:
        return self.telegram.allowed_users

    @property
    def default_chat_id(self) -> int | str | None:
        return self.telegram.default_chat_id

    @property
    def working_dir(self) -> str:
        return self.agy.working_dir

    @property
    def agy_path(self) -> str:
        return self.agy.agy_path

    @property
    def model(self) -> str | None:
        return self.agy.model

    @property
    def default_flags(self) -> list[str]:
        return self.agy.default_flags


_global_settings: Settings | None = None


def load_settings(config_path: str | Path | None = None, **overrides: Any) -> Settings:
    """Load settings from a specific file path or dynamically."""
    if config_path is not None:
        p = Path(config_path)
        if p.is_file():
            with open(p, encoding="utf-8") as f:
                if p.suffix.lower() in {".yaml", ".yml"}:
                    raw_data = yaml.safe_load(f) or {}
                else:
                    raw_data = json.load(f) or {}
            raw_data.update(overrides)
            return Settings(**raw_data)
    return Settings(**overrides)


def get_settings(reload: bool = False) -> Settings:
    """Retrieve or initialize the cached global Settings instance."""
    global _global_settings
    if _global_settings is None or reload:
        try:
            _global_settings = Settings()
        except Exception as e:
            logger.error(Messages.CONFIG_LOAD_ERROR.format(error=e))
            _global_settings = Settings()
    return _global_settings


def load_config() -> dict[str, Any]:
    """Backward-compatible function returning raw configuration dictionary."""
    cfg_file = find_config_path()
    if cfg_file and cfg_file.is_file():
        try:
            with open(cfg_file, encoding="utf-8") as f:
                if cfg_file.suffix.lower() in {".yaml", ".yml"}:
                    result: dict[str, Any] = yaml.safe_load(f) or {}
                    return result
                result = json.load(f) or {}
                return result
        except Exception as e:
            logger.error(Messages.CONFIG_LOAD_ERROR.format(error=e))
    return {}


def load_state(state_path: str | Path | None = None) -> dict[str, Any]:
    target_path = state_path or Constants.STATE_PATH
    if os.path.exists(target_path):
        try:
            with open(target_path, encoding="utf-8") as f:
                result: dict[str, Any] = json.load(f)
                return result
        except Exception as e:
            logger.debug("Failed to load state: %s", e)
    return {Constants.STATE_KEY_CONTINUE: False}


def save_state(state: dict[str, Any], state_path: str | Path | None = None) -> None:
    target_path = state_path or Constants.STATE_PATH
    try:
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(Messages.STATE_SAVE_ERROR.format(error=e))


def build_runtime_config(
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build runtime configuration dictionary.

    Accepts an optional raw config dictionary or uses current global settings.
    Guarantees backward compatibility with dict-based consumers.
    """
    if config is not None:
        settings = Settings(**config)
    else:
        settings = get_settings()

    return {
        "bot_token": settings.telegram.bot_token,
        "allowed_users": {str(u) for u in settings.telegram.allowed_users},
        "working_dir": settings.agy.working_dir,
        "agy_path": settings.agy.agy_path,
        "model": settings.agy.model,
        "default_flags": settings.agy.default_flags,
        "default_chat_id": settings.telegram.default_chat_id,
        "process_timeout": settings.agy.process_timeout,
        "communicate_timeout": settings.agy.communicate_timeout,
        "edit_throttle_seconds": settings.agy.edit_throttle_seconds,
        "max_status_items": settings.agy.max_status_items,
        "max_completed_items": settings.agy.max_completed_items,
        "path_extra": settings.agy.path_extra,
        "local_bin": settings.agy.local_bin,
        "mcp_config_path": settings.mcp.config_path,
        "update_remote": settings.update.remote,
        "update_branch": settings.update.branch,
        "update_auto_restart": settings.update.auto_restart,
        "update_check_interval_seconds": settings.update.check_interval_seconds,
        "update_auto_apply": settings.update.auto_apply,
    }


def is_authorized(user_id: int, allowed_users: set[str] | list[Any]) -> bool:
    if not allowed_users:
        return True
    str_set = {str(u) for u in allowed_users}
    return str(user_id) in str_set
